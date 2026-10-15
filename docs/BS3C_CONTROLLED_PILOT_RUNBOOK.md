# BS-3C: Controlled Publishing Pilot Runbook
**Bop Social — Pilot Operational & Rollout Guide**
**Version:** BS-3C
**Date:** October 2026

---

## 1. Prerequisites
Before initiating any real-world social publishing pilot with Bop Social, verify:
- Bop Social stack is built and running (`bopsocial-backend-local:bs-3b`, `bopsocial-frontend-local:bs-3b`).
- PostgreSQL database migrations are applied up to `0071_canonical_tenant_and_contact_identity`.
- Redis service is healthy on port 6379 for Celery broker, result backend, and Channel Layers.
- A dedicated staging/test Facebook Page and linked Instagram Creator/Business account are provisioned (do NOT use production customer accounts).
- Dedicated AWS S3 bucket or reverse-proxy public HTTPS origin (`BACKEND_PUBLIC_URL`) is active for Meta media retrieval.

---

## 2. Supported Providers

| Provider | Publishing Modes | Requirements |
|---|---|---|
| **Facebook Pages** | Text, Single Image, Multi-Image Carousel, Video, Reels | Meta Graph API v21.0, Public HTTPS media URLs |
| **Instagram Business/Creator** | Single Image, Carousel (2-10 items), Video, Reels, Stories | Two-step Container API, Public HTTPS media URLs |
| **LinkedIn Pages** | Text, Single Image, Carousel, Video | LinkedIn v2 Posts API, Direct byte upload |
| **YouTube (Optional)** | Video, Shorts | YouTube Data API v3 Resumable Upload |
| **Google Business Profile (Optional)** | Standard Local Post, Image Post | Google My Business v4 Local Posts API |

---

## 3. Required Environment Variables

```bash
# Core Application URLs
FRONTEND_URL=http://localhost:3010
BACKEND_URL=http://localhost:8000
BACKEND_PUBLIC_URL=https://api.bopsocial.com   # Required if S3 is not used

# Meta Integration (Facebook & Instagram)
FACEBOOK_APP_ID=your_meta_app_id
FACEBOOK_APP_SECRET=your_meta_app_secret
FACEBOOK_CONSUMER_REDIRECT_URI=http://localhost:3010/oauth/callback/
META_REDIRECT_URI=http://localhost:8000/api/oauth/facebook/business-callback/

# LinkedIn Integration
LINKEDIN_CLIENT_ID=your_linkedin_client_id
LINKEDIN_CLIENT_SECRET=your_linkedin_client_secret
LINKEDIN_REDIRECT_URI=http://localhost:8000/api/oauth/linkedin/callback/

# Google Integration (YouTube & GMB)
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/oauth/google/callback/
```

---

## 4. S3 / Public Media Configuration

Meta's ingestion servers cannot fetch files from `localhost` or private IP addresses. S3 hosting must be configured:

```bash
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_STORAGE_BUCKET_NAME=bopsocial-pilot-media
AWS_S3_REGION_NAME=us-east-1
AWS_S3_CUSTOM_DOMAIN=cdn.bopsocial.com  # Optional CloudFront CDN
```

Run preflight verification in Django shell:
```python
from social_stats.media_service import validate_s3_configuration
print(validate_s3_configuration())
# Must return: {'valid': True, 'errors': [], ...}
```

---

## 5. Social Account Connection Steps

1. **Log in** to Bop Social as an agency administrator.
2. Navigate to **Settings → Integrations** (`/admin/settings`).
3. Under **Social Accounts**, click **Connect Facebook & Instagram**.
4. In the Meta OAuth prompt, grant permissions for:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `instagram_basic`
   - `instagram_content_publish`
5. Select the designated **Bop Staging Facebook Page**.
6. Verify both **Facebook** and **Instagram** show green connected status badges in the UI.

---

## 6. Pilot Approval Workflow

```
[Agency Member]       [Client / Internal Approver]          [Celery Worker]
       │                             │                             │
       ├── Create Draft Post         │                             │
       ├── Add Image & Platforms     │                             │
       ├── Click "Submit Approval" ─►│                             │
       │                             ├── Review in /approvals      │
       │                             ├── Click "Approve Post" ────►│
       │                             │                             ├── Scheduled / Queued
       │                             │                             ├── Preflight media URL
       │                             │                             ├── GraphClient POST
       │                             │                             └── Success / Log Row
```

1. An internal user drafts a post in **Composer** (`/composer`).
2. If the workspace has `requires_approval = True`, clicking publish transitions the post to `pending_approval`.
3. An authorized approver visits `/approvals` and clicks **Approve**.
4. The post transitions to `queued`, triggers `publish_unified_post`, and dispatches to Celery.

---

## 7. First Real Post Checklist

- [ ] Operator authorization confirmed (no automated posting without approval).
- [ ] Target account verified as staging Facebook Page (NOT production customer page).
- [ ] Staging image uploaded; dimensions and aspect ratio verified (e.g. 1080x1080 JPG).
- [ ] Media public URL verified accessible over HTTPS via `curl -I <url>`.
- [ ] Scheduled time set for 5–10 minutes in the future to observe Celery scheduler dispatch.
- [ ] Celery worker and beat logs observed actively (`docker compose logs -f worker beat`).
- [ ] PlatformPublishLog row inspected for `status='published'` and valid `platform_post_id`.
- [ ] Facebook staging page checked to confirm post rendered properly.
- [ ] Post manually deleted or archived after verification if temporary.

---

## 8. Publishing Monitoring

Monitor Celery task queues in real time:
```bash
docker compose logs -f worker beat
```
Key log markers:
- `process_scheduled_posts dispatched N posts`
- `publish_unified_post: fan-out to platforms`
- `publish_to_platform: facebook result success=True post_id=...`
- `update_unified_post_status: post N -> published`

---

## 9. Error Handling & In-App Alerts

| Error Condition | Error Code | System Action | Resolution |
|---|---|---|---|
| **Expired Meta Token** | `token_expired` | Credential deactivated, Alert created in `/alerts` | Reconnect via OAuth in `/admin/settings` |
| **Missing S3 Hosting** | `public_media_required` | Post marked `failed`, detailed error logged | Set `AWS_ACCESS_KEY_ID` / `AWS_STORAGE_BUCKET_NAME` |
| **Rate Limited by Meta** | `rate_limited` | Celery exponential backoff retry (up to 3x) | Wait for retry or adjust posting frequency |
| **Media File Too Large** | `media_too_large` | Post marked `failed`, immediate user alert | Re-encode/compress file within provider caps |

---

## 10. Operational Rollback Procedure

If a pilot post is misconfigured or published with erroneous content:
1. In Bop Social, navigate to **Calendar** or **Posts** (`/admin/analytics/posts`).
2. Click **Revert / Delete Post**.
3. Bop Social will call `delete_post` on the target provider API using the stored `platform_post_id`.
4. If API deletion fails due to provider constraints, immediately open Facebook/Instagram natively and delete the post manually.

---

## 11. Token Expiration Handling
- Tokens for Facebook and Instagram are extended to long-lived tokens (valid for ~60 days).
- Background sync tasks monitor token health.
- If a token is revoked or expires, Bop Social creates an in-app `Alert(alert_type='token_expired')` and pushes a realtime UI banner directing the operator to reconnect.

---

## 12. Support Procedure
- **Internal Technical Escalation:** Bop Platform Team.
- **Log Inspection:** Run `docker compose exec backend python manage.py shell` or inspect Docker logs:
  ```bash
  docker compose logs --tail=200 backend worker
  ```
- **Diagnostic Endpoint:** `GET /api/health/services/` returns Redis, Database, Celery, and storage health.

---

## 13. Features Disabled During Pilot

The following modules and providers are strictly non-operational during the controlled pilot:
- **TikTok Publishing:** Disabled in UI ("Coming Soon" badge), blocked at DRF serializer.
- **X / Twitter Publishing:** Disabled in UI ("Coming Soon" badge), blocked at DRF serializer.
- **Pinterest Publishing:** Disabled in UI ("Coming Soon" badge), blocked at DRF serializer.
- **Ads Automation:** Disabled in sidebar navigation ("Coming soon").
- **WhatsApp Outbound Broadcasts:** Excluded from social publishing pilot scope.
- **Chatwoot Real-Time Messaging:** Kept isolated within canonical omnichannel boundary.
