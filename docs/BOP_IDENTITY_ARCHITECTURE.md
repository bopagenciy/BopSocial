# Bop Universe Identity Architecture Foundation
## Canonical Tenant & Contact Identity Contract (Bop Social Side)

---

### 1. Overview & Strategic Purpose

The Bop Universe comprises three core platforms:
1. **Bop Social** (Marketing, social publishing, CTWA campaign attribution, visual bot builder).
2. **Bop Chatbot / Chatwoot** (Omnichannel conversational gateway, conversation state machine, human agent triage).
3. **Bop CRM** (Canonical commercial contacts, qualified leads, sales opportunities, pipeline tracking).

To enable seamless, secure cross-application integration without circular dependencies or primary key coupling, a decoupled **Canonical Identity Architecture** is established.

This document defines the Bop Social foundation implemented in **Phase BOP-CONV-B1A**.

---

### 2. Canonical Organization Identity (`bop_organization_id`)

#### Definition
`bop_organization_id` is the globally unique, immutable, system-level identifier representing a business organization or agency tenant across all Bop Universe applications.

#### Model Implementation
* **Host Entity:** `Client` model (`social_stats.models.Client`).
* **Field Definition:**
  ```python
  bop_organization_id = models.UUIDField(
      default=uuid.uuid4,
      unique=True,
      editable=False,
      db_index=True,
      help_text="Canonical Bop Universe organization identifier (UUIDv4).",
  )
  ```

#### Strategy & Generation Method
* **UUIDv4 Strategy:** Evaluated against UUIDv7. Because Python runtime standard library (`3.12.14`) does not have native UUIDv7 support without introducing third-party C/Rust dependencies, cryptographically secure **UUIDv4** (`uuid.uuid4()`) was selected. It provides 122 bits of entropy, guaranteeing zero collisions across the universe without external dependencies.
* **Auto-Generation:** Automatically assigned upon initial model instantiation and persistence.
* **Deterministic Backfill:** Pre-existing `Client` records in the database receive a permanent, unique UUIDv4 during migration `0071`.

#### Immutability Enforcement
`bop_organization_id` is permanent and cannot be modified:
1. **Model-Level Guard:** In `Client.save()`, any attempt to alter `bop_organization_id` on an existing persisted record raises a Python `ValueError("bop_organization_id is immutable once assigned.")`.
2. **Serializer-Level Guard:** `ClientSerializer` marks `bop_organization_id = serializers.UUIDField(read_only=True)`. Furthermore, `validate()` explicitly raises `serializers.ValidationError` if a client submits an update payload attempting to alter the ID.
3. **UI Guard:** The field is marked `editable=False` and is never rendered as an editable input in workspace settings, client onboarding, or admin edit screens.

#### Local PK vs. Canonical Identifier
* **Local PK (`Client.id`):** Continues to serve as the local relational primary key (Integer auto-increment) for foreign keys, internal table joins, and frontend route parameters (`/admin/clients/:id`).
* **Canonical Identifier (`bop_organization_id`):** Used exclusively as the external correlation key for cross-app API calls, event payloads, and integration contracts.

#### Tenant Authorization Distinction
**CRITICAL SECURITY PRINCIPLE:** The canonical UUID is an integration identifier, **NOT an authorization token or secret**. Possession of a `bop_organization_id` does NOT grant access to a workspace. Authorization continues to be enforced strictly by Django user sessions, role checks (`TenantScopedMixin`), and workspace memberships.

---

### 3. Contact Identity Inventory & Design

#### Inventory of Person-Representing Entities in Bop Social:

| Model | Represents a Person? | Tenant Scoped? | Current External Identifiers | Assigned `bop_contact_id`? | Architectural Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`WhatsAppContact`** | **YES** (External customer / lead) | Yes (`client_id`) | E.164 `phone`, `wa_id` | **YES (CANONICAL)** | Primary entity representing external human contacts interacting via messaging. Synchronizes with Chatwoot and Bop CRM. |
| **`Lead`** | **YES** (Marketing prospect) | Yes (`client_id`) | `contact_id`, CTWA UTMs, phone | **NO (DERIVED)** | `Lead` is a marketing attribution and pipeline record pointing to `WhatsAppContact`. It exposes `bop_contact_id` via a property derived from `self.contact.bop_contact_id` to prevent duplicate canonical IDs for the same human. |
| **`Conversation` (Social)** | **NO** (Social thread) | Yes (`client_id`) | `platform_thread_id`, `contact_handle` | **NO** | Denormalized social comment/review thread; not a canonical customer record. |
| **`UserProfile` / `User`** | **NO** (Internal staff / agent) | Yes (`client_id`) | `email`, `username` | **NO** | Agency operators and employees; completely separate domain from customer contacts. |
| **`Competitor`** | **NO** (Benchmark entity) | Yes (`client_id`) | `page_id`, handle | **NO** | Social media tracking entity, not a person. |

#### Contact Identifier (`bop_contact_id`)
* **Host Entity:** `WhatsAppContact` (`social_stats.models.WhatsAppContact`).
* **Field Definition:**
  ```python
  bop_contact_id = models.UUIDField(
      default=uuid.uuid4,
      unique=True,
      editable=False,
      db_index=True,
      help_text="Canonical Bop Universe contact identifier (UUIDv4).",
  )
  ```
* **Immutability:** Enforced via `WhatsAppContact.save()` model guard and `WhatsAppContactSerializer.validate()`.
* **Lead Reference:** `Lead.bop_contact_id` returns `self.contact.bop_contact_id`. Serialized in `LeadListSerializer` and `LeadDetailSerializer` as a read-only field.

---

### 4. Channel Identity Map

External communication channels attach to the canonical contact through metadata attributes:

| Channel | Identity Fields Stored in Bop Social | Canonical Correlation |
| :--- | :--- | :--- |
| **WhatsApp** | `phone` (E.164, e.g. `+15551234567`), `wa_id` (Meta phone number) | `WhatsAppContact.bop_contact_id` |
| **Instagram** | `instagram_account_id`, `contact_handle` | Future: Scoped user ID (`IGSID`) attached via contact inboxes |
| **Facebook** | `page_id`, `contact_name` | Future: Page-scoped user ID (`PSID`) |
| **Email** | `email` (RFC 5322 lowercase) | Correlated via Bop CRM Master Contact |

---

### 5. Cross-System Mapping Contracts (Target Design)

#### Organization Mapping Contract:
* **Bop Social:** `Client.bop_organization_id`
* **Chatwoot:** `Account.custom_attributes['bop_organization_id']` *(To be implemented in BOP-CONV-B1B)*
* **Bop CRM:** `Organization.bop_organization_id` *(Future phase)*

```
[ Bop Social Client ]                           [ Chatwoot Account ]
  id: 2                                           id: 105
  bop_organization_id: "8f7e2a1b-..." <─────────> custom_attributes:
                                                    bop_organization_id: "8f7e2a1b-..."
```

#### Contact Mapping Contract:
* **Bop Social:** `WhatsAppContact.bop_contact_id`
* **Chatwoot:** `Contact.custom_attributes['bop_contact_id']` *(To be implemented in BOP-CONV-B1B)*
* **Bop CRM:** `Contact.bop_contact_id` *(Canonical Master Contact)*

```
[ Bop Social Contact ]                          [ Chatwoot Contact ]
  id: 42                                          id: 889
  bop_contact_id: "3c9d4e5f-..." <─────────────> custom_attributes:
                                                    bop_contact_id: "3c9d4e5f-..."
```

---

### 6. API Lookup Interfaces

To support future service-to-service lookups without breaking tenant boundaries:

1. **Client Lookup by `bop_organization_id`:**
   * `GET /api/clients/?bop_organization_id=<uuid>`
   * Filtered through role-based queryset. Staff or client users can only retrieve organizations they have explicit access to.
2. **Contact Lookup by `bop_contact_id`:**
   * `GET /api/whatsapp/contacts/?bop_contact_id=<uuid>`
   * Enforced via `TenantScopedMixin`. Queries are strictly scoped to the caller's active tenant (`client_id`). Tenant A cannot query Tenant B's contact even with a valid UUID.

---

### 7. Migration Safety & Backfill Guarantees

* **Migration File:** `0071_canonical_tenant_and_contact_identity.py`
* **Phased Steps:**
  1. Add nullable UUID fields (`null=True, blank=True`).
  2. Execute deterministic Python backfill (`backfill_canonical_identities`) assigning unique UUIDv4s to all existing rows.
  3. Alter fields to `null=False, unique=True, default=uuid.uuid4, db_index=True`.
* **Zero Disruptions:** All existing primary keys (`Client.id`, `WhatsAppContact.id`), foreign keys, and relationships remain 100% intact.
