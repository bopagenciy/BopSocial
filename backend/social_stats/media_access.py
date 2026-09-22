# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Bop Social Security Hardening — Media Tenant Isolation (SEC-01)
# ============================================================================
"""
Cryptographic token generation, access control checks, and secure serving
for private multi-tenant media assets and public publishing assets.
"""
from __future__ import annotations

import logging
import mimetypes
import os
from typing import Optional, Tuple

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import FileResponse, Http404, HttpResponse

logger = logging.getLogger(__name__)

MEDIA_TOKEN_SALT = 'bop-social-media-access-v1'
PUBLIC_MEDIA_SALT = 'bop-social-public-publish-v1'


def generate_media_token(asset_id: int, client_id: int, user_id: int, max_age: int = 86400) -> str:
    """
    Generate a tamper-proof signed token for in-browser media rendering (<img>, <video>).
    Valid for max_age seconds (default: 24 hours).
    """
    signer = TimestampSigner(salt=MEDIA_TOKEN_SALT)
    payload = f"{asset_id}:{client_id}:{user_id}"
    return signer.sign(payload)


def verify_media_token(token: str, asset_id: int, max_age: int = 86400) -> Tuple[bool, dict]:
    """
    Validate a media access token against asset_id and expiration.
    Returns (is_valid, payload_dict).
    """
    if not token:
        return False, {}
    signer = TimestampSigner(salt=MEDIA_TOKEN_SALT)
    try:
        payload = signer.unsign(token, max_age=max_age)
        t_asset_id, t_client_id, t_user_id = payload.split(':')
        if int(t_asset_id) != int(asset_id):
            return False, {}
        return True, {
            'asset_id': int(t_asset_id),
            'client_id': int(t_client_id),
            'user_id': int(t_user_id),
        }
    except (BadSignature, SignatureExpired, ValueError):
        return False, {}


def generate_public_publishing_token(asset_id: int, client_id: int, max_age: int = 172800) -> str:
    """
    Generate a signed publishing URL token for external social platforms (Meta, Google)
    to fetch media during publishing workflows. Valid for 48 hours.
    """
    signer = TimestampSigner(salt=PUBLIC_MEDIA_SALT)
    payload = f"pub:{asset_id}:{client_id}"
    return signer.sign(payload)


def verify_public_publishing_token(token: str, max_age: int = 172800) -> Tuple[bool, int, int]:
    """
    Validate a public publishing token. Returns (is_valid, asset_id, client_id).
    """
    if not token:
        return False, 0, 0
    signer = TimestampSigner(salt=PUBLIC_MEDIA_SALT)
    try:
        payload = signer.unsign(token, max_age=max_age)
        parts = payload.split(':')
        if len(parts) != 3 or parts[0] != 'pub':
            return False, 0, 0
        return True, int(parts[1]), int(parts[2])
    except (BadSignature, SignatureExpired, ValueError):
        return False, 0, 0


def user_has_media_access(user, asset) -> bool:
    """
    Strict authorization verification for private media assets:
      1. Superadmin -> unconditional access.
      2. Direct Client ownership (user owns workspace or user.profile.client == asset.client).
      3. Staff users assigned to asset.client.
      4. Agency members with an active AgencyClientRelation against asset.client.
    """
    if not user or not user.is_authenticated:
        return False

    profile = getattr(user, 'profile', None)
    if not profile:
        return False

    if profile.role == 'superadmin':
        return True

    client_id = asset.client_id

    # Direct client association
    if profile.client_id == client_id:
        return True

    # Client owner user
    if asset.client and asset.client.owner_user_id == user.id:
        return True

    # Staff assignment
    if profile.role == 'staff' and profile.assigned_clients.filter(id=client_id).exists():
        return True

    # Agency membership check via active AgencyClientRelation
    from .marketplace_models import AgencyMembership, AgencyClientRelation
    user_agency_ids = list(
        AgencyMembership.objects.filter(user=user, is_active=True).values_list('agency_id', flat=True)
    )
    if user_agency_ids and AgencyClientRelation.objects.filter(
        agency_id__in=user_agency_ids, client_id=client_id, status='active'
    ).exists():
        return True

    return False


def generate_media_asset_url(asset, request=None, thumb: bool = False) -> str:
    """
    Construct an authorized media URL for a MediaAsset instance.
    If request is authenticated, attaches a signed media access token.
    """
    suffix = '?thumb=1' if thumb else ''
    connector = '&' if suffix else '?'

    user = getattr(request, 'user', None) if request else None
    if user and user.is_authenticated and user_has_media_access(user, asset):
        token = generate_media_token(asset.id, asset.client_id, user.id)
        return f"/api/media/serve/{asset.id}/{suffix}{connector}token={token}"

    action = 'thumbnail' if thumb else 'file'
    return f"/api/composer/media/{asset.id}/{action}/"


def serve_secure_file(request, file_field, asset_id: int, is_thumbnail: bool = False):
    """
    Safely stream an authorized media file.
    Enforces directory traversal checks and leverages X-Accel-Redirect when available.
    """
    if not file_field or not file_field.name:
        raise Http404("Media file is not present on this asset")

    storage_root = getattr(getattr(file_field, 'storage', None), 'location', None) or settings.MEDIA_ROOT
    media_root = os.path.normcase(os.path.realpath(os.path.abspath(str(storage_root))))
    try:
        file_path = os.path.normcase(os.path.realpath(os.path.abspath(file_field.path)))
    except Exception:
        raise Http404("Media storage error resolving file path")

    # Defense against directory traversal
    if os.path.commonpath([file_path, media_root]) != media_root:
        logger.error("Directory traversal attempt blocked: %s", file_path)
        raise PermissionDenied("Invalid media file path")

    if not os.path.exists(file_path):
        raise Http404("Media file does not exist on disk")

    mime, _ = mimetypes.guess_type(file_path)
    content_type = mime or 'application/octet-stream'

    # Check for Nginx X-Accel-Redirect (production reverse proxy offload)
    use_x_accel = getattr(settings, 'USE_X_ACCEL_REDIRECT', False) or (
        request and request.META.get('HTTP_X_ACCEL_MAPPING')
    )
    if use_x_accel:
        rel_path = os.path.relpath(file_path, media_root).replace('\\', '/')
        response = HttpResponse(content_type=content_type)
        response['X-Accel-Redirect'] = f"/internal_media/{rel_path}"
        response['X-Content-Type-Options'] = 'nosniff'
        response['Cache-Control'] = 'private, no-transform, max-age=3600'
        return response

    # Development / direct Daphne streaming
    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-transform, max-age=3600'
    return response
