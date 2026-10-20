# Phase BS-3F — Instagram Carousel Publishing Pilot: Formal Closure

**Bop Social — Instagram Multi-Image Carousel Publishing, Aspect-Ratio Uniformity Hardening & Feature Closure**

---

## 1. Executive Summary

Phase **BS-3F** (encompassing operational subphases BS-3F.1 through BS-3F.2D) achieved the first controlled end-to-end multi-image carousel publication from **Bop Social** through the **Meta Graph API** to a live Instagram Professional account (**@bopsoluciones** / Professional ID `17841464843082253`), followed by systematic application-level hardening to enforce child aspect-ratio uniformity.

The complete lifecycle was executed under strict internal governance protocols without impacting existing client data or cross-tenant boundaries:
$$\text{Readiness Audit} \longrightarrow \text{Asset Preparation} \longrightarrow \text{Draft \& Preflight} \longrightarrow \text{Live Publication} \longrightarrow \text{Gap Audit} \longrightarrow \text{Validation Hardening}$$

The live carousel publication was containerized on Meta Graph API via two individual image containers (`is_carousel_item=true`) bundled under a parent `CAROUSEL` container, published with platform confirmation ID `18230543227329937`, and verified live at `https://www.instagram.com/p/DescoPwDflU/`. Following the live verification, the system identified an architectural gap (individual per-item validation without cross-item uniformity enforcement) and hardened the Composer preflight, serializer, and orchestrator pipelines with deterministic aspect-ratio uniformity validation.

---

## 2. Pilot Tenant & Entity Mapping

All activities were strictly scoped to the internal staging tenant (`Client.id = 3`):

| Entity / Dimension | Value | Architectural Significance |
| :--- | :--- | :--- |
| **Workspace Tenant** | `Bop Agencia` | Official internal staging workspace |
| **Relational Primary Key (`Client.id`)** | `3` | Multi-tenant boundary key |
| **Canonical UUID (`bop_organization_id`)** | `d4c60c86-30a4-4360-8464-81c0af1d813c` | Bop Universe correlation identifier |
| **Associated Agency (`Agency.id`)** | `2` (`bop-agencia`) | Internal agency management entity |
| **Authorized Operator User** | `pilot.operator@bopagencia.local` | Internal operator (User ID `5`) |
| **Target Instagram Account** | `@bopsoluciones` | Live professional business account |
| **Instagram Account ID** | `17841464843082253` | Meta Graph API Professional ID |
| **Linked Facebook Page** | `Bo Projects` (ID `657647337668646`) | Dedicated staging Facebook Page |
| **PlatformCredential ID** | `2` | `client_id=3`, `platform='instagram'`, `is_active=True` |
| **Persisted Scopes** | `read_insights`, `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `business_management`, `pages_read_engagement` | Authorized publishing scopes |

---

## 3. Subphase Execution Breakdown

### 3.1 Subphase BS-3F.1: Readiness Audit
- Audited codebase for multi-image publishing capability on Instagram.
- Verified `InstagramPublisher.publish_carousel` implementation with two-step container flow:
  1. `POST /{ig_id}/media` with `is_carousel_item=true` per child URL.
  2. `POST /{ig_id}/media` with `media_type=CAROUSEL` and comma-separated `children` IDs.
  3. `POST /{ig_id}/media_publish` to release the container.
- Identified operational readiness: Single-image publishing, permalink retrieval, S3 private media delivery, and basic analytics were confirmed closed.
- Recommended proceeding to a 2-slide JPEG carousel pilot.

### 3.2 Subphase BS-3F.2A: Asset Preparation & Preflight
- Selected primary asset: `MediaAsset #2` (`1254 x 1254`, `image/jpeg`, aspect ratio `1.0`).
- Processed operator-provided secondary image (`bopsocial3.png`):
  - Transcoded from PNG to JPEG (`image/jpeg`).
  - Resized from `1024 x 1024` to exact `1254 x 1254` geometry matching `MediaAsset #2`.
  - Ingested as `MediaAsset #3` (`bopsocial3_carousel_68db88cd.jpg`, Content-Length `393,975` bytes, S3 key `media_assets/tenant_3/2026/10/bopsocial3_carousel_68db88cd.jpg`).
  - Verified S3 SigV4 presigned URLs: HTTP 200 with `Content-Type: image/jpeg` for both assets.

### 3.3 Subphase BS-3F.2B: Draft Assembly & Preflight
- Assembled UnifiedPost draft (`UnifiedPost.id = 4`) for tenant `3` with `media_type = 'carousel'` and `media_urls = ['asset:2', 'asset:3']`.
- Set pilot caption:
  ```text
  Bop Social Instagram Carousel Pilot #1

  Publicación de prueba interna con carrusel desde Bop Social.
  ```
- Evaluated Composer preflight check: HTTP 200 OK, `ok = True`, 0 errors.

### 3.4 Subphase BS-3F.2C: Controlled Live Publication
- Explicit operator authorization received for `UnifiedPost.id = 4`.
- Two-step governance pipeline executed:
  1. `POST /api/composer/posts/4/publish_now/` $\longrightarrow$ HTTP 202 Accepted (`status='pending_approval'`).
  2. `POST /api/composer/posts/4/approve/` $\longrightarrow$ HTTP 200 OK (`approved_by=5`).
- Celery task dispatched `publish_unified_post(4)` $\longrightarrow$ `publish_to_platform(4, 'instagram')`.
- Meta Graph API execution:
  - Child Container #1 created for `MediaAsset #2`.
  - Child Container #2 created for `MediaAsset #3`.
  - Parent Carousel Container created bundling children.
  - Container polled to `status_code = FINISHED`.
  - `POST /{ig_id}/media_publish` executed successfully.
- Published Media Record:
  - **Instagram Media ID**: `18230543227329937`
  - **Canonical Permalink**: `https://www.instagram.com/p/DescoPwDflU/`
  - **Database Persistence**: `PlatformPublishLog.id = 4` marked `status='success'`; `UnifiedPost.id = 4` marked `status='published'`.

---

## 4. Root Gap & Architecture Hardening (BS-3F.2D)

### 4.1 Identified Gap
Meta requires that all items in an Instagram carousel share the same aspect ratio (between 4:5 and 1.91:1). In the previous implementation:
- `PLATFORM_LIMITS['instagram']` contained rules for `'image'`, `'video'`, `'reel'`, and `'story'`, but lacked `'carousel'`.
- Individual assets received a warning (`'No validation rules defined for instagram/carousel'`) rather than strict checks.
- Preflight only validated assets in isolation and did not enforce cross-item aspect-ratio consistency.
- A user submitting mixed ratios (e.g. 1:1 and 4:5) would pass preflight and fail downstream during Meta container creation.

### 4.2 Hardening Implementation
1. **Aspect-Ratio Uniformity Rule**:
   - Compares each child asset against the base aspect ratio ($w_0 / h_0$) established by item #1.
   - Evaluates with deterministic floating tolerance: $|ar_i - ar_0| \le 0.01$.
   - **Dimension Policy**: Identical aspect ratio is enforced; identical pixel dimensions are *not* required (e.g. `1080x1080` and `1254x1254` both equal $1.00$ and pass).
2. **Individual Asset Rule Inheritance**:
   - `validate_for_platform` delegates `'carousel'` assets to `'image'` or `'video'` platform limits based on MIME type (`image/jpeg` $\le 8\text{ MB}$; `video/mp4` $\le 1\text{ GB}$).
3. **Item Count Constraints**:
   - Requires between 2 and 10 items.
4. **Mixed Media & Unknown Dimensions Safeguard**:
   - If a video asset has unverified dimensions (`width is None` or `height is None`), the preflight safely blocks before any Meta Graph API calls.
5. **Multi-Tiered Defense**:
   - **Preflight Check**: Evaluates draft payload before submission.
   - **Serializer Validation**: `UnifiedPostSerializer.validate` enforces 2–10 item limits on creation/update.
   - **Publish Now Action**: `UnifiedPostViewSet.publish_now` runs carousel uniformity validation before approval gating.
   - **Orchestrator Safeguard**: `orchestrator.publish_to_platform` performs pre-execution validation before dispatching to publisher.
6. **Bilingual Localization**:
   - English: `"All Instagram carousel items must use the same aspect ratio."`
   - Spanish: `"Todos los elementos del carrusel de Instagram deben usar la misma proporción."`

---

## 5. Test Suite Verification

Comprehensive unit and integration test suite implemented in `backend/social_stats/tests/test_carousel_validation.py`:

| Test Case | Scenario Description | Expected Outcome | Actual Result |
| :--- | :--- | :--- | :--- |
| **CASE 1** | 2 JPEG images (`1254x1254` + `1254x1254`) | PASS | PASS |
| **CASE 2** | `1080x1080` + `1254x1254` (same 1:1 ratio, different dimensions) | PASS | PASS |
| **CASE 3** | `1080x1080` + `1080x1350` (1:1 vs 4:5 mismatched ratio) | FAIL | FAIL (error localized EN/ES) |
| **CASE 4** | 3-item carousel, all matching 1:1 ratio | PASS | PASS |
| **CASE 5** | 3 items where third item differs in aspect ratio | FAIL | FAIL (ratio uniformity error) |
| **CASE 6** | Fewer than 2 items (< 2) | FAIL | FAIL (minimum item error) |
| **CASE 7** | More than 10 items (> 10) | FAIL | FAIL (maximum item error) |
| **CASE 8** | Invalid individual asset (e.g. `image/png` for IG carousel) | FAIL | FAIL (per-item MIME error) |
| **CASE 9** | Mixed image and video with known identical ratio | PASS | PASS |
| **CASE 10** | Mixed image and video with unverified video dimensions | FAIL | FAIL (safe blocking error) |
| **CASE 11** | Tenant isolation preventing preflight cross-tenant resolution | PASS | PASS (tenant isolation preserved) |
| **CASE 12** | Preflight execution produces zero external Meta calls | PASS | PASS (0 external HTTP calls) |

### Regression Suites Verified:
- `test_carousel_validation`: 14 passed in 1.050s
- `test_publishers_instagram`: 17 passed in 0.013s
- `test_regressions`: 12 passed in 0.915s
- `test_facebook_analytics_resilience` + `test_instagram_analytics_resilience`: 18 passed in 1.011s
- `test_dashboard_endpoints` + `test_bs3b_media_provider_hardening`: 45 passed in 2.447s
- `python manage.py check`: 0 issues identified.

---

## 6. Live Publication Verification

- **Post Object**: `UnifiedPost.id = 4`
- **Publish Log**: `PlatformPublishLog.id = 4`
- **Platform**: `instagram`
- **Status**: `published` / `success`
- **Published Items**:
  1. Slide 1: `MediaAsset #2` (`1254 x 1254 px`, JPEG)
  2. Slide 2: `MediaAsset #3` (`1254 x 1254 px`, JPEG)
- **Instagram Media ID**: `18230543227329937`
- **Canonical Permalink**: [https://www.instagram.com/p/DescoPwDflU/](https://www.instagram.com/p/DescoPwDflU/)

---

## 7. Production-Ready Conclusion

With Phase BS-3F.2D successfully implemented and verified:
- Instagram multi-image carousel publishing is officially certified as **Production-Ready**.
- Application-level uniformity guards prevent invalid API calls to Meta.
- Baseline database records (`UnifiedPost = 4`, `PlatformPublishLog = 4`, `MediaAsset = 3`) remain intact with 100% integrity.
- Zero secrets or sensitive access tokens are committed or exposed.
