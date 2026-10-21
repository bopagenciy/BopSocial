# Bop Social — Two-Level Branding Architecture

## Overview

Bop Social is engineered as a multi-tenant social media management platform within the **Bop Universe** ecosystem. A core architectural principle of Bop Social is the strict separation between **Level 1 Platform Identity** and **Level 2 Tenant Branding**.

This document outlines the two-level branding hierarchy, token structure, asset governance, component consumption rules, and future white-label readiness.

---

## 1. Branding Hierarchy

```
┌────────────────────────────────────────────────────────┐
│             LEVEL 1: PLATFORM IDENTITY                 │
│                   "Bop Social"                         │
│  - System Navigation & Module Rails                    │
│  - Authentication & Account Recovery Pages             │
│  - System Notification & Verification Emails           │
│  - PWA Manifest, Favicon, Browser Tab Titles           │
│  - Global Design System Tokens & Base Palette          │
│  - Report Engine Attribution ("Powered by Bop Social") │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│             LEVEL 2: TENANT BRANDING                   │
│          "Client Organization / Workspace"             │
│  - Client Dashboard & Workspace Switcher               │
│  - Client Profile Assets (client.logo, client.avatar)  │
│  - Connected Social Channel Identities & Previews      │
│  - Client-Facing Analytics Header & Reports            │
│  - Future Workspace Theme Customization (White-label)  │
└────────────────────────────────────────────────────────┘
```

---

## 2. Level 1: Platform Corporate Identity

The Level 1 identity establishes Bop Social as a high-performance marketing platform aligned with the Bop Universe corporate guidelines.

### 2.1 Corporate Palette

| Token / Role | Hex Value | RGB / HSL | Usage |
| :--- | :--- | :--- | :--- |
| **Brand Gold** (`primary`) | `#F5A623` | `rgb(245, 166, 35)` | Primary CTAs, brand badges, active indicators, accent bars |
| **Brand Gold Hover** | `#E09612` | `rgb(224, 150, 18)` | Interactive button hover states |
| **Brand Gold Active** | `#C88204` | `rgb(200, 130, 4)` | Pressed / active interactive states |
| **Brand Gold Soft** | `rgba(245, 166, 35, 0.12)` | — | Badge backgrounds, focused input rings, subtle highlights |
| **Brand Gold Glow** | `rgba(245, 166, 35, 0.22)` | — | Focused shadows, elevated highlights |
| **Charcoal** | `#2D3142` | `rgb(45, 49, 66)` | Secondary surfaces, dark mode cards, table borders |
| **Dark Charcoal** | `#1E202A` | `rgb(30, 32, 42)` | Application shell, ModuleRail sidebar, dark backgrounds |
| **Canvas White** | `#FFFFFF` | `rgb(255, 255, 255)` | Light mode primary surface, card backgrounds |

### 2.2 Official Platform Assets

* **Master Vector / High-Res Asset**: `docs/images/LogoBopSocial.png` (1254x1254 PNG, official corporate insignia)
* **Web Serving Asset**: `frontend/public/LogoBopSocial.png`
* **Favicon & Web App Icons**:
  * `frontend/public/favicon.png` (64x64)
  * `frontend/public/apple-touch-icon.png` (180x180)
  * `frontend/public/icons/icon-192.png` (192x192)
  * `frontend/public/icons/icon-512.png` (512x512)

### 2.3 Level 1 Component Suite (`BrandLogo.jsx`)

All platform brand references must import from `frontend/src/components/ui/BrandLogo.jsx`:

1. `<BrandMark size={28} />`: Isolated emblem (e.g. for `ModuleRail` collapsed sidebar, mobile navigation header).
2. `<BrandMarkInverted size={28} />`: Emblem on dark surfaces.
3. `<BrandWordmark />`: Typographic wordmark rendered in corporate styling with Gold accent.
4. `<BrandLogoHorizontal size={28} />`: Primary lockup combining the emblem and wordmark horizontally.
5. `<BrandLogoStacked size={48} />`: Centered lockup for login pages, splash screens, and modal dialogs.

---

## 3. Level 2: Tenant Workspace & Client Branding

Within tenant workspaces, the interface prioritizes the client organization being managed.

### 3.1 Client Entities & Metadata

* **`client.name`**: Display name of the client organization.
* **`client.logo`**: High-resolution brand logo uploaded by the client / agency administrator.
* **`client.avatar`**: Compact square or circular avatar for workspace switchers and activity feeds.
* **`client.color` / `client.theme`** (extensible): Accent color specific to the client's brand.

### 3.2 Tenant Isolation Guarantees

* Tenant branding is strictly scoped to the active workspace (`client_id` or `workspace_id`).
* Cross-tenant data leakage is prevented via backend database queries (`tenant_isolation`) and Row-Level Security checks.
* When a user switches workspaces, Level 2 assets dynamically re-render without reloading the application shell.

### 3.3 Export & Reporting Guidelines

In generated PDF and export reports:
* **Header Area**: Displays the client's Level 2 branding (`client.logo` and `client.name`) prominently as the subject of the report.
* **Header Accents**: Styled using dark charcoal `[30, 32, 42]` with gold accent bar `[245, 166, 35]`.
* **Footer Area**: Features discrete platform attribution: `"Generated by Bop Social — Confidential"`.

---

## 4. Component Consumption Matrix

| Context / Surface | Branding Level | Allowed Components & Tokens |
| :--- | :--- | :--- |
| **ModuleRail (Global Sidebar)** | Level 1 | `<BrandMark />`, `tokens.css` (`--sidebar-bg: #1E202A`) |
| **Login / Register / Auth** | Level 1 | `<BrandLogoStacked />`, Gold primary button tokens |
| **System Emails (Verification, Reset)**| Level 1 | Bop Social header, Gold CTA, corporate footer |
| **Browser Tab & PWA Manifest** | Level 1 | Bop Social title, `favicon.png`, `manifest.json` |
| **Workspace Selector** | Level 1 + Level 2 | Level 1 dropdown frame, Level 2 client avatars |
| **Client Analytics Dashboard** | Level 2 | `client.name`, `client.logo`, client stats cards |
| **Post Composer & Social Preview** | Level 2 | Target social network avatars + Client account identity |
| **PDF Analytics Export** | Hybrid | Client logo top header; Bop Social footer attribution |

---

## 5. White-Label Readiness (Future Phases)

The design token architecture (`tokens.css`, `theme.js`, and CSS custom properties) allows future white-labeling for enterprise agency tiers:
1. **Dynamic CSS Variables**: Variables like `--blue` (alias for `--brand-gold`), `--primary`, and `--primary-hover` can be overridden dynamically at runtime by injecting tenant theme overrides at the root container.
2. **Decoupled BrandLogo**: The `BrandLogo` component encapsulates all platform lockups; an enterprise white-label hook can swap `<BrandLogoHorizontal />` for a tenant's custom white-label logo based on the active license without modifying layout code.
