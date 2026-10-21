# BOP SOCIAL — INSTAGRAM MIXED CAROUSEL ARCHITECTURE & ROUTING HARDENING
## Phase BS-3F.7B Specification & Reference Guide

### 1. Overview & Context

During the **BS-3F.7A** audit, Instagram carousel validation constraints and publishing mechanisms were scrutinized for mixed media compatibility (combining images and video items within a single Instagram carousel post).

While aspect-ratio uniformity validation (`validate_carousel_for_platform`) correctly blocks mismatched geometries (such as `1:1` square images paired with `9:16` vertical videos), a critical routing vulnerability was identified in `InstagramPublisher.publish_carousel`: child media routing previously relied on checking URL file extensions using `str(url).lower().endswith(...)` on raw provider URLs.

When AWS S3 presigned URLs containing AWS Signature Version 4 (SigV4) query parameters (`?...&X-Amz-Signature=...`) were supplied:
- `endswith(('.mp4', ...))` returned `False`.
- Video items were erroneously dispatched as `image_url` instead of `video_url` with `media_type: 'VIDEO'`.
- Status polling (`_wait_for_container_ready`) on child video items was bypassed, leading to container failure.

Phase **BS-3F.7B** resolves this defect by establishing canonical media-type routing anchored in authoritative database metadata (`MediaAsset.mime_type`).

---

### 2. Architecture & Contract Hardening

#### 2.1 Canonical Child Media-Kind Resolution
Authoritative metadata is derived directly from `MediaAsset.mime_type`:
- `mime_type.startswith('video/')` $\to$ `media_kind = 'VIDEO'`
- `mime_type.startswith('image/')` $\to$ `media_kind = 'IMAGE'`
- Unsupported MIME types (e.g. `application/pdf`, `audio/mp3`) $\to$ controlled `PublishError(code='unsupported_media_type')` without calling Meta.

#### 2.2 Orchestrator Metadata Propagation
`social_stats.orchestrator` implements `_resolve_carousel_children(post, raw_urls, resolved_urls)`. It maps each item in `raw_urls` (preserving exact UnifiedPost order) to:
```json
[
  {
    "url": "https://bucket.s3.amazonaws.com/media/client_3/asset.jpg?X-Amz-...",
    "media_kind": "IMAGE",
    "mime_type": "image/jpeg",
    "asset_id": 2
  },
  {
    "url": "https://bucket.s3.amazonaws.com/media/client_3/asset.mp4?X-Amz-...",
    "media_kind": "VIDEO",
    "mime_type": "video/mp4",
    "asset_id": 5
  }
]
```
Child metadata is propagated to `InstagramPublisher.publish_carousel(credential, content, media_urls, children_metadata=children_metadata)`.

#### 2.3 Publisher Resolution Priority
`_resolve_carousel_child_kind(url, meta)` follows a strict 3-tier precedence:
1. **Explicit `media_kind`** from canonical `MediaAsset` (`'VIDEO'` or `'IMAGE'`).
2. **Trusted `mime_type`** hint if available in child metadata.
3. **Safe URL path parsing** (`urllib.parse.urlparse(url).path.lower()`) strictly as a fallback for legacy callers without asset metadata.
   - Recognizes: `.mp4`, `.mov`, `.webm` $\to$ `VIDEO`
   - Recognizes: `.jpg`, `.jpeg`, `.png` $\to$ `IMAGE`
   - Unknown extension $\to$ raises `PublishError(code='unsupported_media_type')`. Never defaults to `IMAGE`.

Raw URL string suffix matching is completely deprecated.

---

### 3. Container & Payload Contracts

#### 3.1 Child Video Container
- Endpoint: `POST /{ig_id}/media`
- Payload:
  ```python
  {
      'is_carousel_item': 'true',
      'media_type': 'VIDEO',
      'video_url': provider_url
  }
  ```
- Must **NOT** contain `image_url` or `caption`.
- Readiness polling: `_wait_for_container_ready(credential, container_id)` is invoked (polling interval 3s, timeout 180s) until status is `FINISHED`.

#### 3.2 Child Image Container
- Endpoint: `POST /{ig_id}/media`
- Payload:
  ```python
  {
      'is_carousel_item': 'true',
      'image_url': provider_url
  }
  ```
- Must **NOT** contain `video_url`, `media_type = 'VIDEO'`, or `caption`.
- Readiness polling: Not required for image containers in Meta Graph API.

#### 3.3 Parent Carousel Container
- Endpoint: `POST /{ig_id}/media`
- Payload:
  ```python
  {
      'media_type': 'CAROUSEL',
      'children': ','.join(ordered_child_ids),
      'caption': post_content or ''
  }
  ```
- Single caption applied only at parent level.
- Readiness polling: `_wait_for_container_ready(credential, parent_container_id)` is invoked before `media_publish`.

---

### 4. Failure Safety & Guardrails

1. **Child Creation / Polling Failure**: If any child container fails to create or video transcoding status returns `ERROR` / timeouts, execution halts immediately. The parent carousel container is never created.
2. **Count Mismatch Protection**: If `len(children_metadata) != len(image_urls)`, a controlled `PublishError(code='media_count_mismatch')` is raised prior to any Graph API interaction.
3. **MIME Validation Gate**: Unsupported MIME types halt execution before Meta calls.
4. **Order Invariance**: The order of `children` supplied to Meta strictly matches `post.media_urls`, regardless of whether images or videos lead.
5. **No Automatic Retries**: Failures are permanently recorded to `PlatformPublishLog` without duplicate publishing loops.

---

### 5. Future 9:16 Companion Asset Requirement for Pilot

To pair with existing vertical video asset `MediaAsset #5` (720x1280, aspect ratio `0.5625`), the companion image must meet:
- **Dimensions**: `1080 x 1920` px (or `720 x 1280` px)
- **Aspect Ratio**: Exact `9:16` (`0.5625`), tolerance $\le 0.01$
- **Format**: `image/jpeg`
- **Color Profile**: sRGB
- **File Size**: $< 8$ MB
- **Canonical Filename**: `bopsocial6_mixed_carousel.jpg`
