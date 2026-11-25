# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Bop Social Security Hardening — Media Serving Endpoints (SEC-01)
# ============================================================================
"""
Secure media serving views.
Enforces tenant authorization on every file and thumbnail request.
"""
from __future__ import annotations

import logging
import urllib.parse
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Client, MediaAsset
from .media_access import (
    serve_secure_file,
    serve_secure_rel_path,
    user_has_media_access,
    verify_client_asset_token,
    verify_media_token,
    verify_public_publishing_token,
)

logger = logging.getLogger(__name__)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def secure_media_serve_view(request, pk: int):
    """
    Serve a private MediaAsset file or thumbnail.
    Authenticates via:
      1. Signed query token (?token=...)
      2. Authenticated user session or Authorization: Bearer <jwt> header
    """
    asset = get_object_or_404(MediaAsset, id=pk)
    thumb = request.query_params.get('thumb') in ('1', 'true', 'yes')

    # 1. Check signed media token
    token = request.query_params.get('token') or request.headers.get('X-Media-Token')
    is_authorized = False

    if token:
        valid, payload = verify_media_token(token, asset.id)
        if valid and payload.get('client_id') == asset.client_id:
            is_authorized = True

    # 2. Check user authentication if token not present / invalid
    if not is_authorized:
        # Check standard user authentication
        user = getattr(request, 'user', None)
        # If unauthenticated, try to extract DRF JWT authentication manually if header present
        if (not user or not user.is_authenticated) and 'HTTP_AUTHORIZATION' in request.META:
            try:
                from rest_framework_simplejwt.authentication import JWTAuthentication
                auth_res = JWTAuthentication().authenticate(request)
                if auth_res:
                    user = auth_res[0]
            except Exception:
                pass

        if user and user.is_authenticated:
            if user_has_media_access(user, asset):
                is_authorized = True
            else:
                return Response({'detail': 'You do not have permission to access this media asset.'}, status=403)
        else:
            return Response({'detail': 'Authentication required to access private media.'}, status=401)

    file_to_serve = asset.thumbnail if (thumb and asset.thumbnail) else asset.file
    return serve_secure_file(request, file_to_serve, asset.id, is_thumbnail=thumb)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def secure_media_thumb_view(request, pk: int):
    """Shortcut endpoint to serve thumbnail for a MediaAsset."""
    asset = get_object_or_404(MediaAsset, id=pk)
    token = request.query_params.get('token') or request.headers.get('X-Media-Token')
    is_authorized = False

    if token:
        valid, payload = verify_media_token(token, asset.id)
        if valid and payload.get('client_id') == asset.client_id:
            is_authorized = True

    if not is_authorized:
        user = getattr(request, 'user', None)
        if (not user or not user.is_authenticated) and 'HTTP_AUTHORIZATION' in request.META:
            try:
                from rest_framework_simplejwt.authentication import JWTAuthentication
                auth_res = JWTAuthentication().authenticate(request)
                if auth_res:
                    user = auth_res[0]
            except Exception:
                pass

        if user and user.is_authenticated:
            if user_has_media_access(user, asset):
                is_authorized = True
            else:
                return Response({'detail': 'You do not have permission to access this media asset.'}, status=403)
        else:
            return Response({'detail': 'Authentication required to access private media.'}, status=401)

    file_to_serve = asset.thumbnail or asset.file
    return serve_secure_file(request, file_to_serve, asset.id, is_thumbnail=True)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_publishing_media_view(request, signed_token: str):
    """
    Public endpoint for social media platform crawlers (Meta Graph API, Google API)
    to fetch media during publishing workflows using narrow, time-limited signed tokens.
    """
    valid, asset_id, client_id = verify_public_publishing_token(signed_token)
    if not valid or not asset_id:
        return Response({'detail': 'Invalid or expired publishing media token.'}, status=403)

    asset = get_object_or_404(MediaAsset, id=asset_id, client_id=client_id)
    return serve_secure_file(request, asset.file, asset.id)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def legacy_media_proxy_view(request):
    """
    Proxy endpoint handling direct /media/media_assets/... requests forwarded by Nginx.
    Finds the asset by file path and ensures tenant authorization.
    """
    raw_path = request.query_params.get('path') or request.META.get('PATH_INFO', '')
    if raw_path.startswith('/media/'):
        rel_path = raw_path[len('/media/'):]
    elif raw_path.startswith('media/'):
        rel_path = raw_path[len('media/'):]
    else:
        rel_path = raw_path.lstrip('/')

    rel_path = urllib.parse.unquote(rel_path)

    # Locate the asset in the database
    asset = MediaAsset.objects.filter(
        Q(file=rel_path) | Q(thumbnail=rel_path)
    ).first()

    if not asset:
        return Response({'detail': 'Media asset not found.'}, status=404)

    # Authenticate request
    user = getattr(request, 'user', None)
    if (not user or not user.is_authenticated) and 'HTTP_AUTHORIZATION' in request.META:
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication
            auth_res = JWTAuthentication().authenticate(request)
            if auth_res:
                user = auth_res[0]
        except Exception:
            pass

    # Check token if provided
    token = request.query_params.get('token')
    if token:
        valid, payload = verify_media_token(token, asset.id)
        if valid and payload.get('client_id') == asset.client_id:
            target_field = asset.thumbnail if (asset.thumbnail and asset.thumbnail.name == rel_path) else asset.file
            return serve_secure_file(request, target_field, asset.id)

    if not user or not user.is_authenticated:
        return Response({'detail': 'Authentication required to access private media.'}, status=401)

    if not user_has_media_access(user, asset):
        return Response({'detail': 'You do not have permission to access this media asset.'}, status=403)

    target_field = asset.thumbnail if (asset.thumbnail and asset.thumbnail.name == rel_path) else asset.file
    return serve_secure_file(request, target_field, asset.id)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def client_asset_proxy_view(request):
    """
    Proxy endpoint handling /media/profile_images/... and /media/product_images/...
    forwarded by Nginx. Enforces signed-token or authenticated tenant authorization.
    """
    raw_path = (
        request.META.get('HTTP_X_ORIGINAL_URI')
        or request.query_params.get('path')
        or request.META.get('PATH_INFO', '')
    )
    raw_path = raw_path.split('?', 1)[0]
    if raw_path.startswith('/media/'):
        rel_path = raw_path[len('/media/'):]
    elif raw_path.startswith('media/'):
        rel_path = raw_path[len('media/'):]
    else:
        rel_path = raw_path.lstrip('/')

    rel_path = urllib.parse.unquote(rel_path).lstrip('/')

    client_obj = None
    if rel_path.startswith('profile_images/'):
        client_obj = Client.objects.filter(profile_image=rel_path).first()
    elif rel_path.startswith('product_images/'):
        media_url = f'/media/{rel_path}'
        client_obj = Client.objects.filter(product_images__contains=[media_url]).first()
        if client_obj is None:
            import re
            match = re.match(r'^product_images/client_(\d+)/', rel_path)
            if match:
                candidate = Client.objects.filter(id=int(match.group(1))).first()
                if candidate and isinstance(candidate.product_images, list) and media_url in candidate.product_images:
                    client_obj = candidate

    if not client_obj:
        return Response({'detail': 'Client media asset not found.'}, status=404)

    token = request.query_params.get('token')
    if token and verify_client_asset_token(token, client_obj.id, rel_path):
        return serve_secure_rel_path(request, rel_path)

    user = getattr(request, 'user', None)
    if (not user or not user.is_authenticated) and 'HTTP_AUTHORIZATION' in request.META:
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication
            auth_res = JWTAuthentication().authenticate(request)
            if auth_res:
                user = auth_res[0]
        except Exception:
            pass

    if not user or not user.is_authenticated:
        return Response({'detail': 'Authentication required to access private media.'}, status=401)

    from types import SimpleNamespace
    if not user_has_media_access(user, SimpleNamespace(client=client_obj, client_id=client_obj.id)):
        return Response({'detail': 'You do not have permission to access this client media.'}, status=403)

    return serve_secure_rel_path(request, rel_path)
