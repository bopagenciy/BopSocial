# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Author    : Chandrabhan Shekhawat
#  Company   : Gigai Kripa Services
#  Website   : https://gigaikripaservices.com/
#  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
#  Released under the MIT License — see LICENSE. Keep this notice.
# ============================================================================
"""
Media handling for the Unified Composer.

Responsibilities:
  - upload_media:  persist a file (S3 if configured, else local FileField)
                   into a MediaAsset row, generate a thumbnail, extract
                   image/video metadata.
  - validate_for_platform:  per-platform size / format / duration / aspect-ratio rules.
  - transcode_for_platform: best-effort resize/compress when the asset doesn't
                            meet a platform's rules. Lazy-imports moviepy so
                            the module loads cleanly even when ffmpeg isn't
                            installed in dev.

Storage:
  When `AWS_ACCESS_KEY_ID` and `AWS_S3_BUCKET` are set in settings, files are
  uploaded to S3 (returns presigned URLs). Otherwise we fall back to Django's
  default storage (local filesystem in dev).
"""
from __future__ import annotations

import io
import ipaddress
import logging
import mimetypes
import os
import uuid
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.utils.text import slugify
from PIL import Image, ImageOps

from .models import MediaAsset

logger = logging.getLogger(__name__)


# ── Per-platform limits ───────────────────────────────────────────────────────
# Conservative limits — under official caps to leave headroom for re-encoding.
PLATFORM_LIMITS: dict[str, dict] = {
    'facebook': {
        'image': {'max_bytes': 10 * 1024 * 1024,        'allowed_mime': {'image/jpeg', 'image/png', 'image/gif'}},
        'video': {'max_bytes': 4 * 1024 * 1024 * 1024,  'max_seconds': 240 * 60, 'allowed_mime': {'video/mp4', 'video/quicktime'}},
    },
    'instagram': {
        # IG Feed
        'image': {'max_bytes': 8 * 1024 * 1024, 'allowed_mime': {'image/jpeg'},
                  'aspect_min': 4 / 5, 'aspect_max': 1.91, 'min_width': 320, 'max_width': 1440},
        'video': {'max_bytes': 1024 * 1024 * 1024, 'max_seconds': 60, 'allowed_mime': {'video/mp4', 'video/quicktime'},
                  'aspect_min': 4 / 5, 'aspect_max': 16 / 9},
        'reel':  {'max_bytes': 1024 * 1024 * 1024, 'max_seconds': 90, 'allowed_mime': {'video/mp4'},
                  'aspect_target': 9 / 16},
        'story': {'max_bytes': 100 * 1024 * 1024, 'max_seconds': 60, 'allowed_mime': {'video/mp4', 'image/jpeg'},
                  'aspect_target': 9 / 16},
    },
    'youtube': {
        'video': {'max_bytes': 256 * 1024 * 1024 * 1024, 'max_seconds': 12 * 3600,
                  'allowed_mime': {'video/mp4', 'video/quicktime', 'video/x-matroska', 'video/webm'}},
        'reel':  {'max_bytes': 256 * 1024 * 1024, 'max_seconds': 60, 'allowed_mime': {'video/mp4'},
                  'aspect_target': 9 / 16},
    },
    'linkedin': {
        'image': {'max_bytes': 5 * 1024 * 1024, 'allowed_mime': {'image/jpeg', 'image/png'}},
        'video': {'max_bytes': 5 * 1024 * 1024 * 1024, 'max_seconds': 10 * 60,
                  'allowed_mime': {'video/mp4', 'video/quicktime'}},
    },
    'google_my_business': {
        'image': {'max_bytes': 5 * 1024 * 1024, 'allowed_mime': {'image/jpeg', 'image/png'},
                  'min_width': 250, 'min_height': 250},
        'video': {'max_bytes': 100 * 1024 * 1024, 'max_seconds': 30, 'allowed_mime': {'video/mp4'}},
    },
}


# ── Result dataclasses ────────────────────────────────────────────────────────
@dataclass
class ValidationResult:
    ok: bool
    errors: list
    warnings: list

    def add_error(self, msg):    self.errors.append(msg);   self.ok = False
    def add_warning(self, msg):  self.warnings.append(msg)


# ── Public surface ────────────────────────────────────────────────────────────
def upload_media(
    file: UploadedFile,
    client_id: int,
    *,
    uploaded_by_id: Optional[int] = None,
    folder: str = '',
    alt_text: str = '',
    tags: Optional[list] = None,
) -> MediaAsset:
    """
    Persist `file` and return a MediaAsset row. Generates a thumbnail when the
    file is an image; extracts image dimensions; for video, attempts to read
    duration via moviepy (lazy-imported, optional).
    """
    if not file:
        raise ValueError('file is required')

    mime = file.content_type or mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
    name = _safe_filename(file.name)
    asset = MediaAsset(
        client_id=client_id,
        uploaded_by_id=uploaded_by_id,
        mime_type=mime,
        file_size=file.size or 0,
        alt_text=alt_text or '',
        tags=tags or [],
        folder=(folder or '').strip(),
    )
    asset.file.save(name, file, save=False)

    # Image metadata + thumbnail
    if mime.startswith('image/'):
        try:
            file.seek(0)
            with Image.open(file) as img:
                img = ImageOps.exif_transpose(img)
                asset.width, asset.height = img.size
                thumb_buffer = io.BytesIO()
                thumb = img.copy()
                thumb.thumbnail((480, 480))
                if thumb.mode in ('RGBA', 'LA', 'P'):
                    thumb = thumb.convert('RGB')
                thumb.save(thumb_buffer, format='JPEG', quality=80)
                asset.thumbnail.save(
                    f'{os.path.splitext(name)[0]}_thumb.jpg',
                    ContentFile(thumb_buffer.getvalue()),
                    save=False,
                )
        except Exception:
            logger.exception('Failed to process image metadata for %s', name)

    # Video duration via moviepy if available.
    elif mime.startswith('video/'):
        duration = _probe_video_duration(asset.file.path if asset.file else None)
        if duration:
            asset.duration_seconds = duration

    asset.save()
    return asset


def validate_for_platform(asset: MediaAsset, platform: str, post_type: str) -> ValidationResult:
    """
    Check `asset` against the platform's rules for the given `post_type`
    (one of 'image', 'video', 'reel', 'story').

    Returns a ValidationResult; never raises. Caller decides whether warnings
    are blocking.
    """
    result = ValidationResult(ok=True, errors=[], warnings=[])

    rules = (PLATFORM_LIMITS.get(platform) or {}).get(post_type)
    if not rules:
        result.add_warning(f'No validation rules defined for {platform}/{post_type}')
        return result

    if asset.file_size and rules.get('max_bytes') and asset.file_size > rules['max_bytes']:
        result.add_error(
            f'File too large for {platform} {post_type}: '
            f'{asset.file_size:,} bytes > {rules["max_bytes"]:,} bytes'
        )

    allowed = rules.get('allowed_mime') or set()
    if allowed and asset.mime_type and asset.mime_type not in allowed:
        result.add_error(
            f'{platform} {post_type} requires one of {sorted(allowed)} — got {asset.mime_type}'
        )

    if rules.get('max_seconds') and asset.duration_seconds:
        if asset.duration_seconds > rules['max_seconds']:
            result.add_error(
                f'Video too long for {platform} {post_type}: '
                f'{asset.duration_seconds:.0f}s > {rules["max_seconds"]:.0f}s'
            )

    # Image dimension constraints
    if rules.get('min_width') and asset.width and asset.width < rules['min_width']:
        result.add_error(f'Image width {asset.width}px below minimum {rules["min_width"]}px')
    if rules.get('min_height') and asset.height and asset.height < rules['min_height']:
        result.add_error(f'Image height {asset.height}px below minimum {rules["min_height"]}px')

    # Aspect ratio for image posts (warn rather than block — it's recoverable)
    if asset.width and asset.height:
        ar = asset.width / asset.height
        if rules.get('aspect_min') and ar < rules['aspect_min']:
            result.add_warning(f'Aspect ratio {ar:.2f} is narrower than {platform} expects ({rules["aspect_min"]:.2f})')
        if rules.get('aspect_max') and ar > rules['aspect_max']:
            result.add_warning(f'Aspect ratio {ar:.2f} is wider than {platform} expects ({rules["aspect_max"]:.2f})')
        target = rules.get('aspect_target')
        if target and abs(ar - target) > 0.05:
            result.add_warning(f'{platform} prefers aspect ratio {target:.2f}, got {ar:.2f}')

    return result


def transcode_for_platform(asset: MediaAsset, platform: str, post_type: str) -> MediaAsset:
    """
    Best-effort transcoder. Currently:
      - Re-encodes too-large JPEGs at lower quality.
      - For video, lazy-imports moviepy; if absent, returns the asset unchanged
        with a warning logged.

    Returns the (possibly new) MediaAsset. Real per-platform transcoding will
    expand here in this.
    """
    rules = (PLATFORM_LIMITS.get(platform) or {}).get(post_type) or {}
    max_bytes = rules.get('max_bytes')

    # Image: re-compress JPEG/PNG until under max_bytes.
    if asset.mime_type and asset.mime_type.startswith('image/') and max_bytes:
        if asset.file_size <= max_bytes:
            return asset
        try:
            asset.file.open('rb')
            with Image.open(asset.file) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                quality = 90
                buf = io.BytesIO()
                while quality >= 40:
                    buf.seek(0); buf.truncate(0)
                    img.save(buf, format='JPEG', quality=quality, optimize=True)
                    if buf.tell() <= max_bytes:
                        break
                    quality -= 10
                buf.seek(0)
                new_name = f"{os.path.splitext(asset.file.name)[0]}_trans.jpg"
                asset.file.save(os.path.basename(new_name), ContentFile(buf.getvalue()), save=False)
                asset.mime_type = 'image/jpeg'
                asset.file_size = buf.tell()
                asset.save(update_fields=['file', 'mime_type', 'file_size'])
        except Exception:
            logger.exception('Image transcode failed for asset %s', asset.id)
        finally:
            try: asset.file.close()
            except Exception: pass
        return asset

    # Video: lazy moviepy. A later iteration will expand this with smart-crop / resize.
    if asset.mime_type and asset.mime_type.startswith('video/'):
        try:
            from moviepy.editor import VideoFileClip  # noqa: F401
        except ImportError:
            logger.info('moviepy not installed — skipping video transcode for asset %s', asset.id)
            return asset
        # No-op for now — placeholder so callers can rely on the symbol existing.
        return asset

    return asset


# ── S3 helpers (used when settings configure S3) ──────────────────────────────
LOCAL_HOSTNAMES = frozenset({
    'localhost', '127.0.0.1', '::1', '0.0.0.0',
    'testserver', 'web', 'example.com',
    'host.docker.internal', 'backend', 'frontend', 'postgres', 'redis', 'worker', 'beat',
})
LOCAL_SUFFIXES = ('.local', '.internal', '.localhost', '.invalid', '.test')


def get_s3_bucket_name() -> str:
    """Return configured S3 bucket name checking both canonical variable names."""
    return getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '') or getattr(settings, 'AWS_S3_BUCKET', '') or ''


def get_s3_region_name() -> Optional[str]:
    """Return configured S3 region checking both canonical variable names."""
    return getattr(settings, 'AWS_S3_REGION_NAME', None) or getattr(settings, 'AWS_S3_REGION', None)


def _s3_enabled() -> bool:
    """Return True if AWS credentials and bucket name are configured."""
    return bool(getattr(settings, 'AWS_ACCESS_KEY_ID', None) and get_s3_bucket_name())


def validate_s3_configuration() -> dict:
    """
    Validate AWS S3 storage configuration without exposing secrets.

    Returns:
      dict with keys: 'valid' (bool), 'errors' (list[str]), 'warnings' (list[str]),
      'bucket_configured' (bool), 'credentials_configured' (bool).
    """
    errors = []
    warnings = []

    access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', '') or ''
    secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', '') or ''
    bucket = get_s3_bucket_name()
    region = get_s3_region_name()
    custom_domain = getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', '') or ''

    if not access_key:
        errors.append('AWS_ACCESS_KEY_ID is missing or empty')
    if not secret_key:
        errors.append('AWS_SECRET_ACCESS_KEY is missing or empty')
    if not bucket:
        errors.append('AWS_STORAGE_BUCKET_NAME / AWS_S3_BUCKET is missing or empty')
    if not region:
        warnings.append('AWS_S3_REGION / AWS_S3_REGION_NAME is not explicitly set; defaulting to AWS SDK standard resolution')

    if custom_domain:
        if 'localhost' in custom_domain or '127.0.0.1' in custom_domain:
            errors.append(f'AWS_S3_CUSTOM_DOMAIN contains local address: {custom_domain}')
        elif not custom_domain.startswith('https://') and not custom_domain.startswith('http://'):
            warnings.append(f'AWS_S3_CUSTOM_DOMAIN does not include https:// scheme: {custom_domain}')

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'bucket_configured': bool(bucket),
        'credentials_configured': bool(access_key and secret_key),
    }


def is_public_https_url(url: str) -> tuple[bool, str]:
    """
    Validate that a media URL is externally accessible over HTTPS for external providers
    such as Meta Graph API.

    Returns (is_valid: bool, failure_reason: str).
    """
    if not url or not isinstance(url, str):
        return False, 'URL is empty'

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() != 'https':
        return False, f"URL scheme must be HTTPS, got '{parsed.scheme or 'none'}'"

    host = (parsed.hostname or '').lower().strip()
    if not host:
        return False, 'URL has no hostname'

    if host in LOCAL_HOSTNAMES or any(host.endswith(sfx) for sfx in LOCAL_SUFFIXES):
        return False, f"Host '{host}' is local/internal and not publicly reachable"

    # Check for private/reserved IP addresses
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private:
            return False, f"Host '{host}' is in a private IP address range"
        if ip.is_loopback:
            return False, f"Host '{host}' is a loopback address"
        if ip.is_link_local:
            return False, f"Host '{host}' is a link-local address"
        if ip.is_reserved:
            return False, f"Host '{host}' is a reserved IP address"
    except ValueError:
        pass

    return True, ''


def presigned_url(asset: MediaAsset, *, expires: int = 3600) -> str:
    """
    Return a signed URL the platform APIs can fetch the file from.
    Falls back to the local MEDIA_URL path when S3 isn't configured.
    """
    if not asset or not asset.file:
        return ''
    if _s3_enabled():
        try:
            import boto3
            client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=get_s3_region_name(),
            )
            return client.generate_presigned_url(
                'get_object',
                Params={'Bucket': get_s3_bucket_name(), 'Key': asset.file.name},
                ExpiresIn=expires,
            )
        except Exception:
            logger.exception('Failed to sign S3 URL for asset %s', asset.id)
    # Controlled public publishing fallback — signed token with narrow scope (SEC-01)
    try:
        return asset.get_public_publishing_url(expires_in=expires)
    except Exception:
        try:
            return asset.file.url
        except Exception:
            return ''


def get_provider_media_url(asset: MediaAsset, provider: str, *, lang: str = 'en') -> str:
    """
    Resolve and validate a media URL for a specific target publishing provider.

    Meta (Facebook & Instagram) requires a publicly accessible HTTPS URL.
    Direct-upload providers (YouTube, LinkedIn, GMB) can use local or presigned URLs.
    """
    if not asset or not asset.file:
        return ''

    prov = (provider or '').lower()
    from .publishers.base import PublishError
    from .locale_helpers import get_media_error_message

    # 1. Direct upload providers (YouTube, LinkedIn, Google Business Profile)
    # These platforms stream/download bytes on the backend server and upload directly.
    # Local filesystem storage remains fully supported for dev and internal workflows.
    if prov in ('youtube', 'linkedin', 'google_my_business', 'gmb'):
        url = presigned_url(asset)
        return url or asset.file.url

    # 2. Meta (Facebook, Instagram) — strictly requires publicly accessible HTTPS URLs
    if prov in ('facebook', 'instagram', 'meta'):
        candidate_url = ''
        if _s3_enabled():
            candidate_url = presigned_url(asset)
        elif getattr(settings, 'BACKEND_PUBLIC_URL', ''):
            candidate_url = asset.get_public_publishing_url()
        else:
            candidate_url = presigned_url(asset)

        is_valid, reason = is_public_https_url(candidate_url)
        if not is_valid:
            msg = get_media_error_message(
                'public_media_required', prov, lang=lang, reason=reason,
            )
            logger.warning(
                'Public media URL required for %s publish (asset=%s): candidate=%s rejected: %s',
                prov, asset.id, candidate_url, reason
            )
            raise PublishError(
                msg,
                code='public_media_required',
                status_code=400,
                supported=True,
            )
        return candidate_url

    # Fallback for unrecognized providers
    return presigned_url(asset) or asset.file.url


def validate_media_url_for_provider(url: str, provider: str, *, lang: str = 'en') -> str:
    """
    Validate that an existing URL string satisfies the provider's hosting requirements.
    Raises PublishError if unsuitable.
    """
    prov = (provider or '').lower()
    if prov in ('facebook', 'instagram', 'meta'):
        is_valid, reason = is_public_https_url(url)
        if not is_valid:
            from .publishers.base import PublishError
            from .locale_helpers import get_media_error_message
            msg = get_media_error_message('invalid_media_url', prov, lang=lang, reason=reason)
            raise PublishError(msg, code='invalid_media_url', status_code=400, supported=True)
    return url


# ── Internals ─────────────────────────────────────────────────────────────────
def _safe_filename(original: str) -> str:
    base, ext = os.path.splitext(original or 'upload')
    base = slugify(base) or 'upload'
    short = uuid.uuid4().hex[:8]
    return f'{base}_{short}{ext.lower()}'


def _probe_video_duration(path: Optional[str]) -> float:
    if not path:
        return 0.0
    try:
        from moviepy.editor import VideoFileClip
    except ImportError:
        return 0.0
    try:
        with VideoFileClip(path) as clip:
            return float(clip.duration or 0)
    except Exception:
        logger.exception('Failed to probe video duration for %s', path)
        return 0.0
