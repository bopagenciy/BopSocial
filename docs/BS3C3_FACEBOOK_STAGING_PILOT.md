# Phase BS-3C.3 — Meta Facebook Staging Pilot: Formal Closure

**Bop Social — Staging Connection & E2E Controlled Publishing Pilot Closure**

---

## 1. Executive Summary

Phase **BS-3C.3** (and follow-up fix **BS-3C.3A**) achieved the first end-to-end controlled real social media publication from **Bop Social** through the **Meta Graph API** to a live Facebook Page.

The end-to-end pipeline was executed cleanly under strict internal governance protocols without impacting any client or production assets:
$$\text{Bop Social Web/API} \longrightarrow \text{Approval Gate} \longrightarrow \text{Queued State} \longrightarrow \text{Celery Task} \longrightarrow \text{FacebookPublisher} \longrightarrow \text{Meta Graph API} \longrightarrow \text{Bo Projects Page}$$

The post was delivered to Facebook, logged with platform confirmation IDs, marked `published` with zero errors, and verified accessible on Meta's infrastructure.

---

## 2. Pilot Tenant & Entity Mapping

All actions were strictly bounded within the authorized internal pilot tenant (`Client.id = 3`):

| Entity / Dimension | Value | Architectural Significance |
| :--- | :--- | :--- |
| **Workspace Tenant** | `Bop Agencia` | Official internal pilot tenant |
| **Local Relational PK (`Client.id`)** | `3` | Scoped multi-tenant execution boundary |
| **Canonical UUID (`bop_organization_id`)** | `d4c60c86-30a4-4360-8464-81c0af1d813c` | Canonical Bop Universe correlation key |
| **Associated Agency (`Agency.id`)** | `2` (`bop-agencia`) | Internal agency management entity |
| **Pilot Operator User** | `pilot.operator@bopagencia.local` | Authorized internal operator (User ID `5`) |
| **Target Facebook Page** | `Bo Projects` | Internal staging Facebook Page |
| **Meta Page ID** | `657647337668646` | Dedicated staging asset |
| **PlatformCredential ID** | `1` | `client_id=3`, `platform='facebook'`, `is_active=True`, `auth_method='oauth'` |

---

## 3. Meta OAuth Flow & Token Validation

### 3.1 OAuth Handshake Configuration
- **Endpoint**: `/api/social/oauth/facebook/<client_id>/`
- **Dialog URL**: `https://www.facebook.com/dialog/oauth`
- **Redirect URI**: Configured via `META_REDIRECT_URI`
- **Scope Configuration (Facebook-only)**:
  `pages_show_list,pages_read_engagement,pages_manage_metadata,pages_manage_posts,read_insights`
- **Rationale for Scopes**:
  - `pages_manage_posts` is required for automated page publishing via Graph API.
  - Instagram scopes (e.g. `instagram_manage_insights`, `instagram_basic`) were removed temporarily because Meta rejected the authorization request with `Invalid Scopes` in the current App review / development tier.
  - Multi-platform / capability-aware scope negotiation is deferred to a future dedicated phase.

### 3.2 Meta Debug Token Inspection
Inspection via `debug_token` confirmed:
- `is_valid`: `True`
- `type`: `PAGE`
- `app_id_match`: `True`
- `scopes`: `pages_show_list`, `pages_read_engagement`, `pages_manage_metadata`, `pages_manage_posts`, `read_insights` granted.
- **Granular Scopes**: `pages_manage_posts` granted specifically for Page `657647337668646` (`Bo Projects`).

---

## 4. Authentication & Frontend Fix (BS-3C.3A)

During the pilot verification on the frontend (`http://localhost:3010`), a blocker in user authentication was identified and resolved:

- **Root Cause**: The backend login endpoint enforces terms acceptance (`terms_accepted: true`). The frontend `LoginPage.jsx` had a terms checkbox visually, but did not pass `accepted` into `doLogin(email, password, accepted)`, causing the API to return HTTP 400 (`terms_required`).
- **Remediation**:
  1. Updated `LoginPage.jsx` to pass `accepted` boolean in `doLogin(email, password, accepted)` and in `signInAsDemo(demoEmail)`.
  2. Enhanced frontend validation so the sign-in button remains disabled unless terms are accepted, displaying inline localized validation errors.
  3. Added localized server error handling for terms validation rejection (`auth.json` en/es).
  4. Updated test suite in `LoginPageTranslation.test.jsx` verifying terms acceptance enforcement and parameter forwarding.

---

## 5. First E2E Real Facebook Pilot Publication

### 5.1 Post Details
- **UnifiedPost Local ID**: `1`
- **Tenant**: `Client.id = 3` (`Bop Agencia`)
- **Title**: `Bop Social Staging Pilot Test Post #1`
- **Content**:
  ```text
  Bop Social Staging Pilot Test Post #1
  Publicación de prueba interna de Bop Social.
  ```
- **Target Platform**: `['facebook']`
- **Media**: None (text-only test to isolate Graph API publishing from storage/media dependencies)
- **Approved By**: `pilot.operator@bopagencia.local` (User ID `5`)

### 5.2 Execution Timestamps & Evidence

| Stage / Event | Timestamp (UTC) | Record / Status |
| :--- | :--- | :--- |
| **Credential Connected** | `2026-10-16 16:05:50` | `PlatformCredential.id = 1` connected |
| **Credential Updated** | `2026-10-16 16:10:08` | Stored Page access token and Page ID `657647337668646` |
| **UnifiedPost Created** | `2026-10-16 15:29:38` | Initial creation in `draft` state |
| **Approval Gate Triggered** | `2026-10-17 16:56:22.305` | `approved_by_id = 5`, transition `pending_approval` $\to$ `queued` |
| **Celery Dispatch Attempt** | `2026-10-17 16:56:22.337` | `PlatformPublishLog.attempted_at` |
| **Meta Graph API Response** | `2026-10-17 16:56:27.267` | `PlatformPublishLog.completed_at` (duration: 4.93s) |
| **Final Post Status** | `published` | `UnifiedPost.status = 'published'`, `error_message = ''` |

### 5.3 Publishing Verification Output
- **PlatformPublishLog ID**: `1`
- **Status**: `success`
- **Platform Post ID**: `657647337668646_1659782972329595`
- **Platform URL**: [https://www.facebook.com/657647337668646_1659782972329595](https://www.facebook.com/657647337668646_1659782972329595)
- **Error Code / Message**: None (empty strings)

---

## 6. Architectural Insights & Technical Gaps

### 6.1 PlatformCredential Scope Persistence Gap
- **Observation**: `PlatformCredential.scope` is currently an empty string (`''`) in the database, even though Meta successfully granted granular scopes including `pages_manage_posts`.
- **Impact**: Does not break publishing, because the Page access token itself carries granted permissions on Meta's servers.
- **Recommendation**: In a future hardening phase, parse the token introspection / callback parameters and persist granted scopes into `PlatformCredential.scope` for auditable in-app permission checks.

### 6.2 Platform Capability & Scope Decoupling
- **Observation**: Requesting Instagram scopes together with Facebook scopes in the same OAuth URL caused Meta to return `Invalid Scopes`.
- **Design Requirement**: Implement capability-aware OAuth request flows:
  - Facebook Page publishing requests only Page scopes (`pages_manage_posts`, `pages_show_list`, `pages_read_engagement`).
  - Instagram Professional connection requests Instagram scopes only when explicitly initiated by an Instagram connection flow.

### 6.3 UnifiedPost Approval Workflow Reality
- **Observation**: In `UnifiedPost.approve()`, the model transitions directly from `pending_approval` to `queued`, which immediately triggers publication scheduling/dispatch via `publish_unified_post`.
- **Reality**: There is no intermediate static state named `'approved'`. A post is either `pending_approval`, `queued`, or `published`/`failed`. Future pilot runbooks and UI indicators should account for this behavior.

### 6.4 Disambiguation: UnifiedPost Approval vs. ApprovalRequest
- **UnifiedPost Approval Gate**: Internal content governance gate on `UnifiedPost` (`requires_approval = True`), controlling whether a draft can advance to `queued` for social dispatch.
- **ApprovalRequest**: Marketplace agency $\leftrightarrow$ client workflow model (`AgencyApprovalRequest`) used for broader client service approvals.
- **Clarification**: These two mechanisms operate independently; the pilot relies strictly on the `UnifiedPost` content governance gate.

---

## 7. Rollback & Reconnection Runbook

If the staging credential needs to be revoked or re-authorized:
1. **Deactivate Credential**:
   ```python
   cred = PlatformCredential.objects.get(client_id=3, platform='facebook')
   cred.is_active = False
   cred.save()
   ```
2. **Re-authorize via UI / OAuth**:
   - Access: `http://localhost:3010/settings` (or `/api/social/oauth/facebook/3/`)
   - Complete the Meta OAuth dialog with the authorized Meta user.
   - Verify `Bo Projects` (`657647337668646`) is mapped to `client_id=3`.
3. **Emergency Cleanup**:
   - Deleting the test post from Facebook can be done directly on the Facebook Page UI or via Graph API `DELETE /{platform_post_id}`.

---

## 8. Verification & Sign-Off Checklist

- [x] Client Scoping isolated to `Client.id = 3` (`Bop Agencia`).
- [x] Operator user `pilot.operator@bopagencia.local` authenticated and authorized.
- [x] Terms acceptance bug resolved in frontend login flow.
- [x] Staging Facebook Page `Bo Projects` connected via OAuth.
- [x] `pages_manage_posts` granted and verified via `debug_token`.
- [x] First real post (`UnifiedPost.id = 1`) published end-to-end to Facebook.
- [x] `PlatformPublishLog` recorded with status `success` and `platform_post_id = 657647337668646_1659782972329595`.
- [x] Zero duplicate posts, zero unauthorized tenant access, zero secret exposure.
