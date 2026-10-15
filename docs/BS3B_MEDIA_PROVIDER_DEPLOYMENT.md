# BS-3B: Media Pipeline & Provider Hardening Deployment Guide
**Bop Social — Platform Publishing & Media Hosting Subsystem**
**Version:** BS-3B
**Date:** October 2026

---

## 1. Executive Summary

Phase BS-3B hardens Bop Social's media publishing pipeline and social provider layer for controlled production deployment. Prior to BS-3B, publishing media to Meta (Facebook Pages and Instagram Professional accounts) could fail silently or return raw upstream exceptions when assets were served from local disk or unresolvable internal network hosts. Furthermore, legacy OAuth fallbacks redirected to upstream domains (`socialstats.app`), and unsupported platforms lacked clear UI/API defenses.

This hardening milestone establishes:
1. **Provider-Safe Public HTTPS Media Resolution:** Guaranteed public HTTPS URL resolution for Meta Graph API with preflight validation preventing invalid or private URLs from reaching Meta servers.
2. **Local Development Preservation:** Direct-upload platforms (YouTube, LinkedIn, Google Business Profile) continue to work seamlessly with local media storage.
3. **Reusable S3 Configuration Validation:** Non-secret-leaking health checks for AWS S3 bucket and credentials configuration.
4. **Unsupported Platform Defense:** TikTok, X/Twitter, and Pinterest are explicitly surfaced as "Coming Soon" in the UI (disabled) and rejected with structured validation errors at the API layer.
5. **Secure OAuth Hierarchy:** Elimination of all hardcoded upstream domain fallbacks, enforcing environment-controlled redirect URLs and tenant isolation.

---

## 2. Public Media URL Architecture

### 2.1 The Meta Ingestion Constraint
Unlike platforms that accept direct byte streaming (e.g. YouTube multipart upload or LinkedIn upload sessions), Meta's Graph API (`/{page_id}/photos`, `/{page_id}/videos`, `/{ig_id}/media`) requires a publicly reachable URL (`url`, `file_url`, or `image_url`) that Meta's servers pull over HTTPS.

If an asset is stored only locally or addressed via `localhost`, `127.0.0.1`, private IP subnets (RFC 1918), Docker bridge hostnames (`backend`, `host.docker.internal`), or internal domain suffixes (`.local`, `.internal`), Meta's crawlers cannot reach the media file.

### 2.2 Resolution & Preflight Layer
`social_stats.media_service` implements a unified, defense-in-depth resolution layer:

- `is_public_https_url(url)`:
  - Enforces `https://` protocol.
  - Rejects `localhost`, `127.0.0.1`, `::1`, `testserver`, `example.com`, and Docker hostnames.
  - Rejects private IP ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback, link-local, and reserved IP spaces.
  - Rejects `.local`, `.internal`, `.localhost`, `.invalid`, `.test` TLDs.

- `get_provider_media_url(asset, provider, lang='en')`:
  - **Meta (`facebook`, `instagram`):** Resolves S3 presigned URL or `BACKEND_PUBLIC_URL` signed publishing token. If the candidate URL is not a valid public HTTPS URL, raises `PublishError(code='public_media_required')` with actionable bilingual error copy.
  - **Direct Upload (`youtube`, `linkedin`, `google_my_business`):** Returns presigned S3 URL if available, or falls back to local filesystem URL (`asset.file.url`) without raising errors.

- `validate_media_url_for_provider(url, provider, lang='en')`:
  - Enforced in `FacebookPublisher` (`_publish_single_photo`, `_publish_multi_photo`, `publish_video`, `publish_reel`) and `InstagramPublisher` (`_create_image_container`, `publish_video`, `publish_reel`, `publish_story`, `publish_carousel`).
  - Guarantees no invalid URL reaches Meta's endpoints even if invoked outside the orchestrator.

---

## 3. Storage Configuration & AWS S3 Validation

### 3.1 Environment Configuration
Add the following variables to `.env` in production:

```bash
# AWS S3 Media Storage Configuration
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_STORAGE_BUCKET_NAME=bopsocial-production-media
# AWS_S3_BUCKET is supported as an alias
AWS_S3_REGION_NAME=us-east-1
# AWS_S3_REGION is supported as an alias
AWS_S3_CUSTOM_DOMAIN=cdn.bopsocial.com   # Optional: CloudFront / CDN distribution
```

### 3.2 Automated Configuration Validator
Run the validator in Django shell or health check routines:

```python
from social_stats.media_service import validate_s3_configuration

status = validate_s3_configuration()
print(status)
# Returns:
# {
#   'valid': True,
#   'errors': [],
#   'warnings': [],
#   'bucket_configured': True,
#   'credentials_configured': True
# }
```

Safety guarantees:
- Never prints or logs `AWS_SECRET_ACCESS_KEY`.
- Identifies missing bucket or credentials.
- Flags local or non-HTTPS `AWS_S3_CUSTOM_DOMAIN`.

---

## 4. Platform Capability Registry

### 4.1 Centralized Registry
Located in `social_stats.publishers.base`:

| Platform Identifier | Label | Status | Publication Mode |
|---|---|---|---|
| `facebook` | Facebook | **Supported** | Meta Graph API (Public HTTPS URL) |
| `instagram` | Instagram | **Supported** | Content Publishing Container API (Public HTTPS URL) |
| `youtube` | YouTube | **Supported** | Google YouTube Data API v3 (Direct Byte Streaming) |
| `linkedin` | LinkedIn | **Supported** | LinkedIn Posts API v2 (Direct Byte Streaming) |
| `google_my_business` / `gmb` | Google Business | **Supported** | GMB API (Direct Byte Streaming) |
| `tiktok` | TikTok | *Unsupported* | UI disabled ("Coming Soon"), API rejects |
| `twitter` / `x` | X (Twitter) | *Unsupported* | UI disabled ("Coming Soon"), API rejects |
| `pinterest` | Pinterest | *Unsupported* | UI disabled ("Coming Soon"), API rejects |

### 4.2 Frontend & Backend Defense
- **Frontend Composer (`ComposerPage.jsx`):** Unsupported platforms are rendered as disabled pills with an uppercase `COMING SOON` / `PRÓXIMAMENTE` badge. Clicks are ignored and cannot be added to `targetPlatforms`.
- **Backend Serializers (`UnifiedPostSerializer`):** `validate_target_platforms` inspects all requested platforms via `is_platform_supported(platform)`. Any unsupported entry immediately returns a 400 Bad Request with a clear message: `"Platform '<platform>' is not currently supported for automated publishing. Coming soon."`
- **Publisher Factory (`get_publisher`):** Requesting an unsupported platform raises `PublishError(code='unsupported_platform', supported=False)`.

---

## 5. OAuth Callback & Upstream Isolation

### 5.1 Removed Fallbacks
All hardcoded instances of `https://socialstats.app/` have been removed from runtime code:
- `oauth_views.py`: Replaced with `_get_facebook_consumer_redirect()`, which resolves:
  1. `settings.FACEBOOK_CONSUMER_REDIRECT_URI`
  2. `settings.FRONTEND_URL` + `/oauth/facebook/callback/`
  3. `settings.BACKEND_URL` fallback
- `profile_views.py`, `manage_request_views.py`, `agency_invite_views.py`, `auth_views.py`, `invitation_views.py`: `DEFAULT_FROM_EMAIL` fallbacks updated from `noreply@socialstats.app` to `noreply@bopsocial.com`.
- `platform_compliance_views.py` & `privacy_tasks.py`: Updated to use `settings.PRIVACY_EMAIL` (`privacy@bopsocial.com`).

---

## 6. Verification & Test Suite Summary

- **Frontend Test Suite:** 31/31 suites passed, 264/264 tests passed (100%).
- **Flaky Test Fix:** `AnalyticsReportingTranslation.test.jsx` resolved with dynamic current-date fixtures.
- **Backend BS-3B Test Suite:** 23/23 tests passed in `test_bs3b_media_provider_hardening.py`.
- **Publisher Guardrail Tests:** Validated in `test_publishers_facebook.py` and `test_publishers_instagram.py`.
