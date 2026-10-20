# BOP SOCIAL — PHASE BS-3F.4B
## Video Media Introspection & Validation Hardening Implementation Report

### Executive Summary
Phase BS-3F.4B establishes a production-grade, secure, and authoritative technical introspection pipeline for video media assets across AgencyOS (Bop Social). Prior to this implementation, the upload pipeline relied exclusively on MoviePy for extracting video duration, failed silently on `InMemoryUploadedFile` objects, left video dimensions (`width` and `height`) at `0`, ignored video/audio codecs and rotation metadata, and lacked poster-frame thumbnail generation.

This phase replaces runtime MoviePy duration probing with an authoritative `ffprobe`-based introspector (`probe_video_metadata`), adds the `technical_metadata` JSONField to `MediaAsset`, normalizes effective display dimensions accounting for orientation/rotation matrices, implements best-effort ffmpeg poster extraction, and hardens platform validators for Instagram Reels, Video Stories, and Mixed Carousels.

---

### Architectural Changes & Invariants

#### 1. Authoritative Video Introspection (`social_stats/video_probe.py`)
- **Single Canonical Implementation**: `probe_video_metadata(source)` extracts complete technical stream and container specifications using `ffprobe`.
- **Subprocess Security Controls**:
  - Argument array invocation (`['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-print_format', 'json', path]`).
  - Strict `shell=False`.
  - 15-second subprocess execution timeout.
  - Sanitized and bounded stderr logging (never logs payloads or sensitive details).
  - Malformed JSON output and nonzero exit codes raise `VideoProbeError`.
- **MemoryUploadedFile & TemporaryUploadedFile Support**:
  - Context manager `get_probe_path(source)` accepts file paths, `TemporaryUploadedFile` instances, and in-memory streams (`InMemoryUploadedFile`, `BytesIO`).
  - In-memory streams are spooled to a secure temporary file (`tempfile.mkstemp(prefix='bop_probe_', suffix='.mp4')`), closed, probed, safely unlinked in a `finally` block, and have their seek pointer restored to `0`.

#### 2. Canonical Video Metadata Contract
The introspector returns a strictly typed dictionary:
```json
{
  "duration_seconds": 15.04,
  "width": 1080,
  "height": 1920,
  "aspect_ratio": 0.5625,
  "fps": 30.0,
  "video_codec": "h264",
  "codec_profile": "High",
  "pixel_format": "yuv420p",
  "bitrate": 4500000,
  "audio_codec": "aac",
  "audio_channels": 2,
  "audio_sample_rate": 44100,
  "rotation": 0,
  "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
  "format_long_name": "QuickTime / MOV",
  "stream_count": 2,
  "has_audio": true
}
```

#### 3. Stream Selection & Rotation Handling
- **Primary Video Stream**: Selected deterministically by evaluating the first stream where `codec_type == 'video'`, ignoring cover art and attached pictures (`disposition.attached_pic == 1` or `cover_art == 1`).
- **Primary Audio Stream**: Selected by evaluating the first stream where `codec_type == 'audio'`. Absence of audio does not fail generic probing (`has_audio = False`).
- **Rotation Normalization**:
  - Evaluates both `side_data_list` Display Matrix rotation and `stream.tags.rotate`.
  - Normalizes angles to standard integers in `{0, 90, 180, 270}`.
  - When rotation is 90° or 270° (or -90°), effective display dimensions are transposed (`width = raw_height`, `height = raw_width`).
  - Effective display dimensions are stored directly in `MediaAsset.width` and `MediaAsset.height`.

#### 4. Database Schema Migration
- Added `technical_metadata = models.JSONField(default=dict, blank=True)` to `MediaAsset`.
- Created and executed migration: `social_stats/migrations/0072_add_mediaasset_technical_metadata.py`.
- Preserved existing columns `duration_seconds`, `width`, and `height` as first-class queried attributes.
- Existing database records (`MediaAsset #1` through `#4`) remain untouched with `technical_metadata={}`.

#### 5. Safe Upload Pipeline & Probe Failure Policy
- In `media_service.upload_media`:
  - Uploaded videos are probed **once** before persistence.
  - If technical probing fails, `VideoProbeError` is raised. The upload terminates immediately with HTTP 400, no database rows are created, and no S3 objects are retained.
  - Localized user-facing error message: `"Video metadata could not be verified."` / `"No se pudieron verificar los metadatos del video."`.

#### 6. Video Poster-Frame Thumbnail Generation
- `generate_video_thumbnail(source, duration)` uses `ffmpeg` to extract a frame at timestamp `min(1.0, max(0.1, duration * 0.25))`.
- Image data is piped directly through stdout (`-f image2pipe -vcodec mjpeg -`), converted and resized to max 480x480 JPEG via Pillow.
- Failure resilience: If thumbnail extraction fails or ffmpeg is unavailable, a warning is logged, `thumbnail` remains blank, and the upload completes successfully without failing.

---

### Platform Validation Hardening

#### Instagram Reel
- **MIME**: `video/mp4`, `video/quicktime`.
- **Duration**: Enforces `min_seconds: 3.0` and `max_seconds: 90.0`.
- **Dimensions**: Rejects assets with missing or zero dimensions.
- **Codecs**: Requires H.264 or HEVC (`h264`, `hevc`, `h265`). Rejects incompatible codecs (e.g., VP9, ProRes).
- **Audio**: Flags warning if audio codec is not AAC (`aac`).
- **Geometry**: Recommended aspect target 9:16 (warns if deviation exceeds 0.05).

#### Instagram Video Story
- **MIME**: `video/mp4`, `video/quicktime`, `image/jpeg`.
- **Duration**: Enforces `max_seconds: 60.0` for video stories.
- **Dimensions & Codec**: Validates dimensions and H.264/HEVC codecs.
- **Image Story Regression**: Image stories bypass video-specific rules; existing 1080x1920 JPEG stories continue to pass validation with 0 errors.

#### Mixed Image/Video Carousel
- Because video `MediaAsset` records now contain valid `width` and `height`, the carousel aspect ratio uniformity rule checks video aspect against slide 1.
- Matching aspect ratios (within 0.01 tolerance) pass validation.
- Mismatched aspect ratios or assets with unknown dimensions are safely blocked with localized error messages.

---

### Verification and Test Suite Coverage

A dedicated test suite, `social_stats/tests/test_video_introspection.py`, covers all 34 required test conditions:
1. `test_01_temporary_uploaded_file_probe` (PASS)
2. `test_02_in_memory_uploaded_file_probe` (PASS)
3. `test_03_duration_extraction` (PASS)
4. `test_04_width_height_extraction` (PASS)
5. `test_05_rotation_90` (PASS)
6. `test_06_rotation_270` (PASS)
7. `test_07_avg_frame_rate_rational_parsing` (PASS)
8. `test_08_r_frame_rate_fallback` (PASS)
9. `test_09_h264_codec_extraction` (PASS)
10. `test_10_hevc_codec_extraction` (PASS)
11. `test_11_aac_audio_extraction` (PASS)
12. `test_12_no_audio_file` (PASS)
13. `test_13_bitrate_extraction` (PASS)
14. `test_14_malformed_ffprobe_json` (PASS)
15. `test_15_ffprobe_nonzero_exit` (PASS)
16. `test_16_ffprobe_timeout` (PASS)
17. `test_17_missing_video_stream` (PASS)
18. `test_18_upload_fails_cleanly_when_probe_fails` (PASS)
19. `test_19_successful_upload_populates_width` (PASS)
20. `test_20_successful_upload_populates_height` (PASS)
21. `test_21_successful_upload_populates_duration_seconds` (PASS)
22. `test_22_successful_upload_populates_technical_metadata` (PASS)
23. `test_23_reel_valid_metadata_pass` (PASS)
24. `test_24_reel_invalid_codec_fail` (PASS)
25. `test_25_reel_invalid_duration_fail` (PASS)
26. `test_26_video_story_valid_pass` (PASS)
27. `test_27_video_story_duration_limit_fail` (PASS)
28. `test_28_image_story_regression_pass` (PASS)
29. `test_29_mixed_carousel_known_ratio_pass` (PASS)
30. `test_30_mixed_carousel_mismatched_ratio_fail` (PASS)
31. `test_31_mixed_carousel_unknown_dimensions_fail` (PASS)
32. `test_32_tenant_isolation_unaffected` (PASS)
33. `test_33_video_thumbnail_graceful_fallback` (PASS)
34. `test_34_zero_meta_calls_during_validation` (PASS)

All regression suites covering Instagram publishing, carousel validation, media provider hardening, and analytics resilience (153 additional tests) passed with zero regressions.

---

### Invariant & Integrity Verification
- **Meta Graph API Calls**: Exactly 0.
- **Published Posts Created**: 0 (Post count remains 5: Post #1 Facebook Text, Post #2 Facebook Image, Post #3 Instagram Image, Post #4 Instagram Carousel, Post #5 Instagram Image Story).
- **Publish Logs Created**: 0 (Log count remains 5).
- **Operator Video Assets Ingested**: 0 (Video MediaAsset count remains 0).
- **Secrets / Credentials Leaked**: None.
