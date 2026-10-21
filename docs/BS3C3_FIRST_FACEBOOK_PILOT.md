# Phase BS-3C.3 — Meta Staging Connection & First Controlled Facebook Test
**Bop Social — Pilot Publishing Runbook & Readiness Gate**

---

### 1. Objective & Scope

Establish the first controlled social publishing test using an internal **Bop Agencia** staging Facebook Page. This test strictly verifies the text-only publishing pathway through the live Bop Social scheduler and orchestrator without public media or S3 dependencies.

---

### 2. Tenant & Entity Configuration

| Property | Value | Architectural Significance |
| :--- | :--- | :--- |
| **Workspace Tenant** | `Bop Agencia` | Official internal pilot tenant |
| **Local Relational PK (`Client.id`)** | `3` | Scoped execution boundary |
| **Canonical UUID (`bop_organization_id`)** | `d4c60c86-30a4-4360-8464-81c0af1d813c` | Canonical Bop Universe correlation key |
| **Associated Agency (`Agency.id`)** | `2` (`bop-agencia`) | Internal agency management entity |
| **Operator User** | `pilot.operator@bopagencia.local` | Authorized internal operator (User ID `5`) |
| **Approval Policy (`requires_approval`)** | `ENABLED` (`True`) | Governance active; two-step publishing enforced |

---

### 3. Meta App & Staging Requirements

- **Meta App ID**: Configured in environment.
- **Meta App Mode**: Development Mode (requires Facebook personal account to hold **Administrator**, **Developer**, or **Tester** role in Meta Developer Dashboard).
- **Target Asset**: Internal Bop Agencia dedicated test/staging Facebook Page.
- **Strict Prohibition**: Production client accounts and "The Industrial Depot" assets are strictly excluded.

---

### 4. Prepared Pilot Post Record

- **UnifiedPost Local ID**: `1`
- **Target Platform**: `['facebook']` (Facebook Page only)
- **Media Type**: `text` (zero media files, zero S3 dependency)
- **Title**: `Bop Social Staging Pilot Test Post #1`
- **Content**:
  ```text
  Bop Social Staging Pilot Test Post #1
  Publicación de prueba interna de Bop Social.
  ```
- **Current Status**: `approved` (advanced through `draft` $\to$ `pending_approval` $\to$ `approved`)
- **Approved By**: `pilot.operator@bopagencia.local` (User ID `5`)
- **Scheduled Time**: Stored in UTC (displayed in `America/New_York`)

---

### 5. Preflight Checklist & Readiness Matrix

| Preflight Check | Requirement | Current Status | Notes |
| :--- | :--- | :---: | :--- |
| **Client Scoping** | Must be Client ID `3` | **PASS** | `UnifiedPost.client_id = 3` |
| **Approval Workflow** | Must be approved | **PASS** | `approved_by_id = 5` |
| **Media Exclusion** | Must contain NO media | **PASS** | `media_urls = []`, `media_type = 'text'` |
| **Platform Target** | Facebook only | **PASS** | `target_platforms = ['facebook']` |
| **Unsupported Platform Guards** | TikTok/X/Pinterest blocked | **PASS** | Hardened in serializers and publisher factory |
| **Celery Stack** | Worker & Beat healthy | **PASS** | `agencyos-worker-1` and `agencyos-beat-1` running |
| **Idempotency Guard** | Zero duplicate dispatches | **PASS** | `PublishedPost` tracking + atomic state transition |
| **Staging Facebook Page** | Connected via OAuth | **PENDING** | Awaiting operator OAuth authorization |

---

### 6. Human Authorization Gate (Section 22)

In accordance with strict pilot safety protocols:
- **No external post will be published** until explicit human authorization is granted.
- The post remains safely staged in `approved` state.
