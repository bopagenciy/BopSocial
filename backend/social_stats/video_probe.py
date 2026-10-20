# ============================================================================
#  Social Stats / Bop Social — Canonical Video Metadata Introspection
# ============================================================================
"""
Canonical ffprobe-based video metadata inspection and thumbnail generation.

Authoritative video metadata contract:
  - duration_seconds : float (finite, > 0)
  - width            : int (effective display width after rotation)
  - height           : int (effective display height after rotation)
  - aspect_ratio     : float (width / height, rounded to 4 decimals)
  - fps              : float or None (from avg_frame_rate or r_frame_rate)
  - video_codec      : str or None (e.g., 'h264', 'hevc', lowercase)
  - codec_profile    : str or None (e.g., 'High', 'Main')
  - pixel_format     : str or None (e.g., 'yuv420p', lowercase)
  - bitrate          : int or None (video stream or format bitrate)
  - audio_codec      : str or None (e.g., 'aac', lowercase)
  - audio_channels   : int or None
  - audio_sample_rate: int or None
  - rotation         : int (normalized to 0, 90, 180, or 270)
  - format_name      : str or None
  - format_long_name : str or None
  - stream_count     : int
  - has_audio        : bool
"""
from __future__ import annotations

import contextlib
import io
import json
import logging
import math
import os
import subprocess
import tempfile
from typing import Any, Generator, Optional, Union

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


class VideoProbeError(Exception):
    """Raised when video metadata extraction fails or video is malformed/incompatible."""
    pass


@contextlib.contextmanager
def get_probe_path(source: Any) -> Generator[str, None, None]:
    """
    Context manager yielding a filesystem path for a video source.
    Handles:
      - Path string / os.PathLike
      - Django TemporaryUploadedFile (has temporary_file_path())
      - Django InMemoryUploadedFile / BytesIO / file-like objects (spooled to temp file)
    Guarantees cleanup of temporary files and restoration of read pointers.
    """
    # 1. Existing filesystem path
    if isinstance(source, (str, os.PathLike)):
        p = str(source)
        if not os.path.exists(p):
            raise VideoProbeError(f"Video file does not exist: {p}")
        yield p
        return

    # 2. UploadedFile with temporary_file_path()
    if hasattr(source, 'temporary_file_path'):
        try:
            yield source.temporary_file_path()
            return
        except Exception as exc:
            logger.debug("temporary_file_path() failed, falling back to temp spool: %s", exc)

    # 3. In-memory file, BytesIO, or stream: spool to a secure temporary file
    temp_fd, temp_path = tempfile.mkstemp(prefix='bop_probe_', suffix='.mp4')
    os.close(temp_fd)
    try:
        if hasattr(source, 'seek'):
            try:
                source.seek(0)
            except Exception:
                pass

        with open(temp_path, 'wb') as dst:
            if hasattr(source, 'chunks'):
                for chunk in source.chunks():
                    dst.write(chunk)
            elif hasattr(source, 'read'):
                dst.write(source.read())
            elif isinstance(source, (bytes, bytearray)):
                dst.write(source)
            else:
                raise VideoProbeError(f"Unsupported video source type: {type(source)}")

        yield temp_path
    finally:
        if hasattr(source, 'seek'):
            try:
                source.seek(0)
            except Exception:
                pass
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def _select_primary_video_stream(streams: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """
    Select the primary video stream deterministically.
    Ignores attached pictures, album artwork, and cover art.
    """
    for stream in streams:
        if stream.get('codec_type') != 'video':
            continue
        disposition = stream.get('disposition') or {}
        if disposition.get('attached_pic') == 1 or disposition.get('cover_art') == 1:
            continue
        return stream
    return None


def _select_primary_audio_stream(streams: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Select the first audio stream if present."""
    for stream in streams:
        if stream.get('codec_type') == 'audio':
            return stream
    return None


def _parse_rotation(stream: dict[str, Any]) -> int:
    """
    Extract and normalize video rotation to {0, 90, 180, 270}.
    Precedence:
      1. side_data_list Display Matrix rotation
      2. stream.tags.rotate
    """
    raw_rot: Optional[float] = None
    side_data = stream.get('side_data_list') or []
    for item in side_data:
        if isinstance(item, dict) and 'rotation' in item:
            try:
                raw_rot = float(item['rotation'])
                break
            except (ValueError, TypeError):
                pass

    if raw_rot is None:
        tags = stream.get('tags') or {}
        rot_val = tags.get('rotate') or tags.get('ROTATION') or tags.get('rotation')
        if rot_val is not None:
            try:
                raw_rot = float(rot_val)
            except (ValueError, TypeError):
                pass

    if raw_rot is None:
        return 0

    norm = int(round(raw_rot)) % 360
    if norm < 0:
        norm += 360
    return norm


def _parse_fps(val: Any) -> Optional[float]:
    """Parse rational fps string (e.g. '30000/1001', '30/1') safely into a float."""
    if not val:
        return None
    try:
        if isinstance(val, (int, float)):
            f = float(val)
            return round(f, 3) if math.isfinite(f) and f > 0 else None
        s = str(val).strip()
        if '/' in s:
            num_s, den_s = s.split('/', 1)
            num = float(num_s)
            den = float(den_s)
            if den <= 0 or not math.isfinite(num) or not math.isfinite(den):
                return None
            res = num / den
            return round(res, 3) if math.isfinite(res) and res > 0 else None
        f = float(s)
        return round(f, 3) if math.isfinite(f) and f > 0 else None
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def probe_video_metadata(source: Any) -> dict[str, Any]:
    """
    Authoritative technical video metadata introspection using ffprobe.

    Executes ffprobe via subprocess with argument list (shell=False) and 15s timeout.
    Returns normalized technical metadata contract dictionary.
    Raises VideoProbeError if video is unreadable, corrupted, or contains no video stream.
    """
    with get_probe_path(source) as path:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_streams',
            '-show_format',
            '-print_format', 'json',
            path,
        ]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=15,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.warning("ffprobe timed out on video source")
            raise VideoProbeError("Video inspection timed out.")
        except FileNotFoundError:
            logger.error("ffprobe executable not found")
            raise VideoProbeError("ffprobe is not installed on this system.")

        if res.returncode != 0:
            err_msg = (res.stderr or '').strip()[:200]
            logger.warning("ffprobe failed with returncode %s: %s", res.returncode, err_msg)
            raise VideoProbeError("Video metadata could not be verified.")

        try:
            data = json.loads(res.stdout)
        except json.JSONDecodeError as exc:
            logger.warning("ffprobe output is not valid JSON: %s", exc)
            raise VideoProbeError("Video metadata could not be verified.")

    streams = data.get('streams') or []
    fmt = data.get('format') or {}

    # Primary video stream
    v_stream = _select_primary_video_stream(streams)
    if not v_stream:
        raise VideoProbeError("No valid video stream found in file.")

    # Audio stream (optional)
    a_stream = _select_primary_audio_stream(streams)

    # 1. Duration extraction
    duration_val: Optional[float] = None
    for cand in (fmt.get('duration'), v_stream.get('duration'), a_stream.get('duration') if a_stream else None):
        if cand is not None:
            try:
                d = float(cand)
                if math.isfinite(d) and d > 0:
                    duration_val = round(d, 3)
                    break
            except (ValueError, TypeError):
                pass

    if duration_val is None or duration_val <= 0:
        raise VideoProbeError("Invalid or missing video duration.")

    # 2. Dimensions & Rotation
    try:
        raw_w = int(v_stream.get('width', 0))
        raw_h = int(v_stream.get('height', 0))
    except (ValueError, TypeError):
        raw_w, raw_h = 0, 0

    if raw_w <= 0 or raw_h <= 0:
        raise VideoProbeError("Invalid video dimensions.")

    rotation = _parse_rotation(v_stream)
    if rotation in (90, 270):
        effective_w, effective_h = raw_h, raw_w
    else:
        effective_w, effective_h = raw_w, raw_h

    aspect_ratio = round(effective_w / effective_h, 4)

    # 3. FPS
    fps = _parse_fps(v_stream.get('avg_frame_rate'))
    if fps is None:
        fps = _parse_fps(v_stream.get('r_frame_rate'))

    # 4. Codecs & pixel format
    v_codec = (v_stream.get('codec_name') or '').lower() or None
    codec_profile = v_stream.get('profile') or None
    pix_fmt = (v_stream.get('pix_fmt') or '').lower() or None

    # 5. Bitrate
    bitrate: Optional[int] = None
    for br_cand in (v_stream.get('bit_rate'), fmt.get('bit_rate')):
        if br_cand is not None:
            try:
                b = int(br_cand)
                if b > 0:
                    bitrate = b
                    break
            except (ValueError, TypeError):
                pass

    # 6. Audio metadata
    if a_stream:
        audio_codec = (a_stream.get('codec_name') or '').lower() or None
        try:
            audio_sample_rate = int(a_stream.get('sample_rate')) if a_stream.get('sample_rate') else None
        except (ValueError, TypeError):
            audio_sample_rate = None
        try:
            audio_channels = int(a_stream.get('channels')) if a_stream.get('channels') else None
        except (ValueError, TypeError):
            audio_channels = None
        has_audio = True
    else:
        audio_codec = None
        audio_sample_rate = None
        audio_channels = None
        has_audio = False

    return {
        'duration_seconds': duration_val,
        'width': effective_w,
        'height': effective_h,
        'aspect_ratio': aspect_ratio,
        'fps': fps,
        'video_codec': v_codec,
        'codec_profile': codec_profile,
        'pixel_format': pix_fmt,
        'bitrate': bitrate,
        'audio_codec': audio_codec,
        'audio_channels': audio_channels,
        'audio_sample_rate': audio_sample_rate,
        'rotation': rotation,
        'format_name': fmt.get('format_name') or None,
        'format_long_name': fmt.get('format_long_name') or None,
        'stream_count': len(streams),
        'has_audio': has_audio,
    }


def generate_video_thumbnail(source: Any, duration: float = 0.0) -> Optional[bytes]:
    """
    Generate a JPEG thumbnail buffer for a video source using ffmpeg.
    Picks a deterministic timestamp: min(1.0, max(0.1, duration * 0.25)) if duration > 0.0 else 0.0.
    Returns JPEG bytes (max 480x480) or None if extraction fails. Never raises.
    """
    ts = 0.0
    if duration > 0.0:
        ts = min(1.0, max(0.1, duration * 0.25))

    try:
        with get_probe_path(source) as path:
            cmd = [
                'ffmpeg',
                '-y',
                '-ss', f"{ts:.3f}",
                '-i', path,
                '-vframes', '1',
                '-q:v', '2',
                '-f', 'image2pipe',
                '-vcodec', 'mjpeg',
                '-',
            ]
            res = subprocess.run(
                cmd,
                capture_output=True,
                timeout=15,
                check=False,
            )
            if res.returncode != 0 or not res.stdout:
                logger.warning("ffmpeg thumbnail extraction returned non-zero (%s)", res.returncode)
                return None

            raw_bytes = res.stdout
            with Image.open(io.BytesIO(raw_bytes)) as img:
                img = ImageOps.exif_transpose(img)
                thumb = img.copy()
                thumb.thumbnail((480, 480))
                if thumb.mode in ('RGBA', 'LA', 'P'):
                    thumb = thumb.convert('RGB')
                buf = io.BytesIO()
                thumb.save(buf, format='JPEG', quality=80)
                return buf.getvalue()
    except Exception as exc:
        logger.warning("Failed to generate video thumbnail: %s", exc)
        return None
