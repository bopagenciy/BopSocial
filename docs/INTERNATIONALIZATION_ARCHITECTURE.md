# Bop Social Internationalization (i18n) Architecture

## 1. Executive Summary

Bop Social is built from the core up to support multi-language capabilities across its marketing OS and workspace platform. Starting in **Phase BS-2.0**, Bop Social provides complete foundational support for **English (`en`)** and **Spanish (`es`)**.

- **English (`en`)** is the primary platform language, source of truth, and canonical fallback.
- **Spanish (`es`)** is supported across the foundational vertical slice (public navigation, authentication shell, login workflows, profile preferences) and serves as the architectural template for future phases.

---

## 2. Core Architectural Principles

1. **Strict Machine Contract Preservation**:
   - Machine keys, API endpoint routes, JSON schema attributes, database column names, third-party OAuth scopes (Meta, LinkedIn, YouTube, etc.), and error codes (`ERR_*`) are **never** translated.
   - Translation is strictly a presentation-layer concern.

2. **Language & Currency Decoupling**:
   - Currency display is completely independent from user interface language.
   - A Spanish-speaking user can view subscriptions or ad spend in `USD`, `EUR`, or `COP` without currency conversion assumptions.

3. **Multi-Tenant & Multi-User Preference Isolation**:
   - Authenticated user language is persisted in the database (`UserProfile.language`).
   - Anonymous language selections are persisted in `localStorage` under `bop_social_language`.
   - On logout or session revocation, credentials and active preferences are cleared to prevent cross-tenant or cross-user leakage.

---

## 3. Language Precedence Hierarchy

When a user visits Bop Social, the active language is resolved using the following order of precedence:

```mermaid
flowchart TD
    Start([User Request / Page Load]) --> IsAuth{Authenticated User?}
    IsAuth -- Yes --> UserPref{User Profile language set?}
    UserPref -- Yes --> ApplyUser[Apply User Profile Language]
    UserPref -- No --> TenantDefault{Tenant / Company Default?}
    IsAuth -- No --> LocalStore{localStorage bop_social_language?}
    TenantDefault -- Yes --> ApplyTenant[Apply Tenant Default]
    TenantDefault -- No --> LocalStore
    LocalStore -- Yes --> ApplyLocal[Apply LocalStorage Language]
    LocalStore -- No --> BrowserDetect{Browser navigator.language?}
    BrowserDetect -- Matches Supported --> ApplyBrowser[Apply Browser Language]
    BrowserDetect -- No / Unsupported --> FallbackEn[Default Fallback: English 'en']
```

1. **User Explicit Preference**: Value stored in `UserProfile.language` (retrieved via `/api/auth/me/` or `/api/profile/`).
2. **Tenant / Company Default**: Organization-wide default configured for the workspace (if present).
3. **Anonymous Browser Storage**: `localStorage.getItem('bop_social_language')`.
4. **Browser Language Detection**: `navigator.language` (e.g. matching `es-*` -> `es`).
5. **Canonical Platform Fallback**: English (`en`).

---

## 4. Frontend Architecture

### 4.1 Technology Stack & Directory Structure
- **Engine**: `i18next` (`^23.x`) and `react-i18next` (`^14.x`).
- **Configuration**: `frontend/src/i18n/config.js`.
- **Locale Storage**:
  ```text
  frontend/src/locales/
  ├── en/
  │   ├── common.json        # Shared actions, status badges, global labels
  │   ├── navigation.json    # Navbar, mega-menus, drawer, footer
  │   └── auth.json          # Login, MFA, signup, password reset
  └── es/
      ├── common.json
      ├── navigation.json
      └── auth.json
  ```

### 4.2 Namespaces & Usage Guidelines
Translations are partitioned into modular namespaces to prevent bloated bundles and facilitate independent translation cycles:

| Namespace | Purpose | Example Keys |
| :--- | :--- | :--- |
| `common` | Shared buttons, statuses, confirmations, language labels | `actions.save`, `status.loading`, `languages.preferred_language` |
| `navigation` | Public top navbar, mega-menus, mobile drawer, footer | `nav.product`, `products.composer`, `footer.tagline` |
| `auth` | Sign-in, sign-up, MFA verification, auth layout copy | `login.title`, `login.email_label`, `mfa.code_label` |

#### React Component Usage:
```jsx
import { useTranslation } from 'react-i18next';

export default function MyComponent() {
  const { t } = useTranslation('navigation');
  return <button>{t('nav.sign_in', 'Sign in')}</button>;
}
```

---

## 5. UI Components: LanguageSelector

The `LanguageSelector` (`frontend/src/components/ui/LanguageSelector.jsx`) is a reusable, accessible component conforming to Bop Social design tokens:

- **Accessibility**:
  - Implements `aria-haspopup="listbox"`, `aria-expanded`, and ARIA `listbox` / `option` roles.
  - Complete keyboard navigation (`ArrowDown`, `ArrowUp`, `Enter`, `Space`, `Escape`, `Tab`).
- **Design Tokens**:
  - Automatically adapts between light and dark themes using CSS variables (`var(--surface-card)`, `var(--text-primary)`, `var(--border-subtle)`).
  - Supports a `darkHero` prop for transparent overlays on high-contrast hero backgrounds.
- **Integration Points**:
  - Desktop public navigation bar (beside `ThemeToggle`).
  - Mobile navigation drawer.
  - Authentication shell (`AuthLayout`).
  - User profile settings (`/account-settings`).

---

## 6. Locale-Aware Formatting Utilities

All formatting functions are centralized in `frontend/src/utils/formatters.js`:

```javascript
import { formatDate, formatTime, formatRelativeTime, formatNumber, formatPercent, formatCurrency } from '../utils/formatters';

// Dates & Times
formatDate(new Date(), { dateStyle: 'medium' }); // English: "Jun 15, 2026", Spanish: "15 jun 2026"
formatRelativeTime(twoHoursAgo);                  // English: "2 hours ago", Spanish: "hace 2 horas"

// Numbers & Percentages
formatNumber(1250000.5);                          // English: "1,250,000.5", Spanish: "1.250.000,5"
formatPercent(0.155, 1);                          // English: "15.5%", Spanish: "15,5 %"

// Decoupled Currency Formatting
formatCurrency(2500, 'USD', 'es');                // Spanish: "2500,00 US$"
formatCurrency(2500, 'EUR', 'en');                // English: "€2,500.00"
```

---

## 7. Backend Localization Architecture

### 7.1 Django Settings
In `backend/dashboard/settings.py`:
```python
LANGUAGE_CODE = 'en'
LANGUAGES = [
    ('en', 'English'),
    ('es', 'Spanish'),
]
USE_I18N = True
USE_TZ = True

MIDDLEWARE = [
    ...
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    ...
]
```

### 7.2 Database & User Profile
The `UserProfile` model in `backend/social_stats/models.py` includes a safe, additive field:
```python
language = models.CharField(
    max_length=10,
    choices=[('en', 'English'), ('es', 'Spanish')],
    default='en',
)
```
- Migration: `0065_add_userprofile_language.py`.
- Exposing endpoints:
  - `GET /api/auth/me/` returns `'language'`.
  - `GET /api/profile/` returns `'language'`.
  - `PATCH /api/profile/` accepts `'language'` (`'en'` or `'es'`) and persists updates immediately.

---

## 8. Adding New Languages in Subsequent Phases

To add a new language (e.g. Portuguese `pt` or French `fr`) in future phases:

1. **Add Language Definition**:
   Update `SUPPORTED_LANGUAGES` in `frontend/src/i18n/config.js`:
   ```javascript
   { code: 'pt', label: 'Português', shortLabel: 'PT' }
   ```
2. **Create Locale Dictionaries**:
   Add `frontend/src/locales/pt/common.json`, `navigation.json`, `auth.json`.
3. **Register Backend Language**:
   Add `('pt', 'Portuguese')` to `LANGUAGES` in `backend/dashboard/settings.py` and `UserProfile.language` choices.

---

## 9. Phase BS-2.1 — Marketing & Authentication Translation Architecture

### 9.1 Overview & Scope
Phase BS-2.1 completes end-to-end Spanish and English bilingual support across Bop Social's entire public surface and authentication lifecycle:
- **Authentication Flows**: Sign-in, organization onboarding / sign-up, password reset, email verification, team invitation acceptance, end-user client portal onboarding, and OAuth callback error handling.
- **Transactional Communications**: Password reset emails and email verification communications delivered in the user's selected language.
- **Public Marketing Experience**: All 13 dedicated marketing pages, legal layouts, error/maintenance views, and data-driven marketing modules (Products, Solutions, Case Studies, Partner Agencies Showcase, and Blog).

### 9.2 Positioning & Brand Invariants
- **Brand Name**: `Bop Social` (never translated or altered).
- **Canonical Positioning Tagline**:
  - English: `Built for the Bop Universe`
  - Spanish: `Diseñado para el Universo Bop`
- **Machine Contract Preservation**:
  - Slugs (e.g. `/products/composer`, `/customers/urban-nest-realty`, `/blog/unified-marketing-os-is-here`), API routes, database fields, and error codes (`ERR_*`) remain canonical and untranslated.

### 9.3 Data-Driven Modular Companion Pattern
For content-heavy and structured marketing modules (products, solutions, case studies, agency directory, blog articles), Bop Social employs a **companion localization pattern**:
- **Canonical Structure**: English content and component metadata (Lucide icons, cover gradients, route anchors) reside in canonical files (`productPages.js`, `solutionPages.js`, `caseStudies.js`, `agencyProfiles.js`, `blogPosts.js`).
- **Localized Companions**: Complete Spanish content overrides reside in lightweight companion files:
  - `frontend/src/pages/marketing/productPages.es.js` (10 products)
  - `frontend/src/pages/marketing/solutionPages.es.js` (7 industry solutions)
  - `frontend/src/pages/marketing/caseStudies.es.js` (3 customer case studies)
  - `frontend/src/pages/marketing/agencyProfiles.es.js` (6 partner agency showcases)
  - `frontend/src/pages/marketing/blogPosts.es.jsx` (6 full-length blog articles with JSX body nodes)
- **Runtime Resolution**:
  Getter helpers (`getProductPage(slug, lang)`, `getSolutionPage(slug, lang)`, `getCaseStudy(slug, lang)`, `getAgency(slug, lang)`, `getPost(slug, lang)`, `getPosts(lang)`) inspect `i18n.language` and cleanly merge Spanish overrides while maintaining fallback to English.

### 9.4 Backend & Client Default Language
- **Organization Tenant Default**: Added `Client.default_language` (`CharField(max_length=10, choices=[('en', 'English'), ('es', 'Spanish')], default='en')`) via migration `0066_client_default_language_alter_mediaasset_file_and_more.py`.
- **Transactional Email Localization**:
  `auth_views._send_verification_email` and `auth_views._send_reset_email` resolve the recipient's language preference (`user.profile.language` or `client.default_language`) and render localized email subject lines, greeting, body instructions, and button labels.

---

## 10. Phase BS-2.1.1 — Translation Coverage Closure & Migration 0066 Audit

### 10.1 Root-Cause Analysis of Browser Inspection Defects
During user verification of BS-2.1 on `http://localhost:3010/`, inspection revealed that the homepage hero and login panels were rendering in English even when Spanish was selected:
1. **Docker Container Stale Image**:
   - `docker ps -a` inspection showed that `agencyos-frontend-1` and `agencyos-backend-1` were running images built 41 hours prior, tagged `bs-2.0` (`bopsocial-frontend-local:bs-2.0`). At commit `b207c02` (BS-2.0), `HomePage.jsx` and `AuthLayout.jsx` were hardcoded English.
   - The user's browser was accessing the stale `bs-2.0` container because compose had not forced an image rebuild with fresh tags.
2. **Uncovered Code Gaps in BS-2.1**:
   - `LoginPage.jsx`: Hardcoded `"or continue with"`, `"local only · password demo"`, and demo account role labels (`Superadmin`, `Agency`, `End user`).
   - `AuthLayout.jsx`: `es/auth.json` retained `"eyebrow": "Marketing OS"` instead of `"Sistema Operativo de Marketing"`.
   - `PasswordStrength.jsx`: Hardcoded `"Password strength: ..."` meter label and level names.
   - `EndUserSignupPage.jsx`: Hardcoded industry options and Step 3 summary review labels.
   - `HomePage.jsx`: Floating hero cards (`NotificationCard`, `CampaignMetricCard`, `LeadCapturedCard`, `AIPopupCard`) contained static strings.
   - `BentoPreviews.jsx`: Interactive mock copy across all 8 bento cards contained static English strings.

### 10.2 Database Migration 0066 Comprehensive Audit
File: `backend/social_stats/migrations/0066_client_default_language_alter_mediaasset_file_and_more.py`.

- **Internationalization Operations**:
  - `AddField('client', 'default_language')`: Adds the tenant default language column (`models.CharField(max_length=10, choices=[('en', 'English'), ('es', 'Spanish')], null=True, blank=True)`).
  - `AlterField('userprofile', 'language')`: Alters `UserProfile.language` to allow `null=True, blank=True, default=None`, enabling fallback to tenant default when unset.
- **Bundled Non-i18n Operations**:
  - `AlterField('mediaasset', 'file')` and `AlterField('mediaasset', 'thumbnail')`: Bundled automatically because `models.py` referenced `upload_to=media_asset_upload_path` without a previous migration.
  - **Schema Impact Assessment**: In PostgreSQL, these fields remain standard `varchar` paths. There was zero change to underlying database column types, constraints, or table structure. The migration is strictly backward-compatible with zero migration failure risk.

### 10.3 Precedence Formalization & Automated Test Suite
The backend preference hierarchy (`User Preference` -> `Tenant Default` -> `Platform Default 'en'`) was formalized and verified across 10 comprehensive tests in `backend/social_stats/tests/test_language_preferences.py`:
1. `test_user_preference_overrides_tenant_default`: Explicit user preference wins over company default.
2. `test_tenant_default_applies_when_user_has_no_preference`: Company default applies when user has no explicit language.
3. `test_user_preference_persists_across_sessions`: Updates to user profile language persist.
4. `test_default_fallback_to_english`: Canonical English fallback when neither is set.
5. `test_anonymous_user_uses_default`: Unauthenticated requests receive canonical fallback.
6. `test_invalid_language_code_fallback`: Unsupported codes gracefully fall back.
7. `test_multi_tenant_isolation`: Verifies that language preference does not leak between tenant workspaces.
8. `test_existing_users_without_language_behave_as_unset`: Verifies backward compatibility for existing records.
9. `test_switching_between_authorized_tenants`: Switching tenant context resolves the active tenant's default.
10. `test_transactional_email_locale_resolution`: Transactional email sender renders localized templates based on recipient preference.

### 10.4 Frontend Coverage Implementation & Verification
- **Catalog Synchronization**:
  - `es/auth.json`: Added `or_continue_with`, `demo_local_notice`, `demo_password_label`, `demo_role_*`, updated `auth_layout.eyebrow` to `"Sistema Operativo de Marketing"`, and added complete `password_strength` and `end_user_signup` dictionaries.
  - `en/marketing.json` & `es/marketing.json`: Added `home.hero_float_*` keys and `bento_preview` blocks covering all 8 interactive previews.
- **Component Updates**:
  - `LoginPage.jsx`: All demo labels, notices, and divider text wired to `t()`.
  - `PasswordStrength.jsx`: Translated meter label and levels.
  - `EndUserSignupPage.jsx`: Dynamic translation for industry options and summary review fields.
  - `HomePage.jsx`: Floating hero cards dynamically translated.
  - `BentoPreviews.jsx`: Interactive mock copy wired to `t('bento_preview.*')`.
- **Regression Tests**:
  - `frontend/src/i18n/__tests__/i18n.test.js`: Verified 5/5 test suites covering BS-2.1.1 keys in English and Spanish.
  - `frontend/src/pages/__tests__/LoginPageTranslation.test.jsx`: Verified 3/3 tests confirming full Spanish rendering of `LoginPage` and `PasswordStrength`.
- **Docker Deployment**:
  - Tagged local images `bopsocial-frontend-local:bs-2.1.1` and `bopsocial-backend-local:bs-2.1.1` in `docker-compose.local.yml`.
  - Executed `docker compose up -d --build frontend backend` and verified healthy containers running live on `http://localhost:3010/`.

---

## 11. Phase BS-2.2 — Bop Social Dashboard & Application Shell Translation

### 11.1 Architectural Scope and Namespace Strategy
Phase BS-2.2 extended the English/Spanish internationalization architecture into the authenticated Bop Social application shell, core navigation, main client dashboard, agency admin overview, and user settings.
English remains the canonical fallback, and Spanish is fully functional across the defined shell and dashboard scope.
Internal slugs, permissions, database keys, routes, and brand invariants (`Bop Social`) remain strictly intact.

Four dedicated namespaces structure the translation assets:
1. `app.json`: Shell navigation, module rail, feature sidebar sections and items, top bar, mobile drawer & navigation, command palette, notification bell, client switcher, and realtime notifications.
2. `dashboard.json`: Client dashboard (greeting, highlights, quick links, KPI metrics for YouTube, Facebook, Instagram, Google My Business, and general platforms, platform breakdown table, upcoming posts, and brand profile strip) and agency overview (hero command center, signals, summary bar, performance snapshot, operational detail, monthly goal manager, smart alerts, top posts panel, and ROI summary panel).
3. `settings.json`: User settings page header, tab group titles (Account, Workspace, Developer, Privacy), tab labels, and profile tab fields, hints, and feedback messages.
4. `common.json`: Reusable UI elements (`accept`, `reject`, `from`, `to`, `soon`).

### 11.2 Shell and Navigation Integration
- **`ModuleRail.jsx`**:
  - Localized brand home aria-label, module button labels and tooltips (with localized `Soon` pill), bottom action buttons (`Notifications`, `Settings`), and `UserMenu` actions.
  - Safe default array handling for `modules = []` to prevent runtime regressions during asynchronous module loading.
- **`FeatureSidebar.jsx`**:
  - Dynamic module header and section title translation via `t('sidebar.sections.<key>')` and `t('sidebar.items.<key>')`.
  - Localized client switcher toggle and search inputs.
- **`TopBar.jsx` & `AppShell.jsx`**:
  - Integrated `<LanguageSelector size="sm" />` beside `ThemeToggle` in both desktop `TopBar` and `MobileTopBar`.
  - Localized dynamic breadcrumb generator (`buildBreadcrumbs`) mapping route segments through `app` catalog keys with graceful fallback.
  - Localized command palette search trigger, what's new pill, mobile drawer title, and realtime toasts.
- **`MobileNav.jsx`**:
  - Localized primary mobile navigation bar (`Home`, `Calendar`, `Reports`, `Alerts`, etc.).
- **`CommandPalette.jsx`**:
  - Localized input placeholders, search loading states, empty results, category group headers (`Recent`, `Pages`, `Quick actions`, `Clients`, `Help & resources`, `Posts`, `Leads`, `Conversations`, `Contacts`), keyboard navigation hints, and quick action labels.
- **`NotificationBell.jsx`**:
  - Localized dropdown title, unread badges, mark-all-read action, tab switchers (`Alerts`, `Notifications`), empty states, and invitation actions (`Accept`, `Reject`).
- **`DateRangePicker.jsx`**:
  - Localized date bounds labels (`From`, `To`) using `common` namespace.

### 11.3 Dashboard & Settings Localization
- **`ClientDashboard.jsx`**:
  - Localized page header, greeting, highlight cards, quick action links, control bar quick stats (`Connected`, `Posts`, `Data`) with dynamic status badges (`Live`, `Waiting`).
  - Standardized KPI cards across all platform views (YouTube, Facebook, Instagram, Google My Business, Default) referencing localized metric labels from `dashboard.json`.
  - Platform breakdown table headers dynamically mapped via `dashboard:breakdown.headers.*`.
  - Collapsible brand profile strip translated (`Brand Profile ▼`, `Hide ▲`, `About`, `USP`, `Target Audience`, `Subcategories`).
  - Upcoming posts widget and empty state notices translated.
- **`AdminOverview.jsx`**:
  - Agency command center hero panel copy, signal cards (`Active Users`, `Top Platform`, `Click Efficiency`, `Sync Health`), and summary bar items.
  - Performance snapshot stat cards and operational tables (`Platform Performance`, `Recent Sync Activity`).
  - Embedded panels: `GoalManager`, `AlertsPanel`, `TopPostsPanel`, and `ROIOverviewPanel` completely wired to `dashboard:admin.*` keys with localized table headers and actions.
- **`UserSettingsPage.jsx`**:
  - Localized page header, sidebar tab groups (`Account`, `Workspace`, `Developer`, `Privacy`) and tab items.
  - Complete `ProfileTab` localization: photo upload hints, name and email labels, email immutability disclaimer, language selection radio controls, validation messages, and save button states.

### 11.4 Verification and Deployment
- **Automated Regression Test Suites**:
  - `frontend/src/components/shell/__tests__/AppShellTranslation.test.jsx`: 4/4 passing tests verifying English default rendering, dynamic switching to Spanish, `LanguageSelector` integration in `TopBar`, and localized module items in `FeatureSidebar`.
  - `frontend/src/pages/__tests__/DashboardTranslation.test.jsx`: 3/3 passing tests verifying key resolution across `app`, `dashboard`, and `settings` namespaces in English and Spanish, and `UserSettingsPage` Spanish rendering.
  - Frontend test suite execution: **14/14 test suites passed, 71/71 tests passed**.
  - Backend test suite execution: **10/10 tests passed** in `social_stats.tests.test_language_preferences`.
  - Production build: `npm run build` completed cleanly with exit code 0.
- **Container Deployment**:
  - Image tag updated in `docker-compose.local.yml`: `bopsocial-frontend-local:bs-2.2`.
  - Container recreated and started: `bopsocial-frontend-local:bs-2.2` built and running.
  - Live HTTP health check: `curl.exe --max-time 10 -I http://localhost:3010/` returned **HTTP/1.1 200 OK** from Nginx.

---

## 12. Phase BS-2.2.1 — Dashboard Translation & Locale Formatting Closure

### 12.1 Defect Closure Overview
During authenticated inspection of `/admin/analytics/dashboard` as local superadministrator, specific dynamic messages, empty states, and date displays were identified as remaining in English when Spanish was selected. Phase BS-2.2.1 closed these gaps without redesigning the dashboard or altering internal database entities or routes:

1. **"No data yet"**:
   - Replaced hardcoded fallback in `AdminOverview.jsx` with `t('admin.no_data_yet', 'No data yet')` ("Sin datos todavía" in Spanish).
2. **"Waiting for synced performance data"**:
   - Replaced hardcoded string in top platform SignalCard with `t('admin.waiting_for_synced_data', 'Waiting for synced performance data')` ("Esperando datos de rendimiento sincronizados" in Spanish).
3. **"0 active platforms in this window"**:
   - Wired to `t('admin.active_platforms_count', { count: activePlatforms })` supporting i18next pluralization (`_one` / `_other`). Translates to `"0 plataformas activas en este período"` in Spanish.
4. **"0 clicks from 0 impressions"**:
   - Wired to `t('admin.clicks_from_impressions', { clicks: fmt(totalClicks), impressions: fmt(totalImpressions) })` with localized metric interpolation. Translates to `"0 clics de 0 impresiones"` in Spanish.
5. **"No recent syncs"**:
   - Replaced hardcoded fallback in `AdminOverview.jsx` and summary bar with `t('admin.no_recent_syncs', 'No recent syncs')` ("Sin sincronizaciones recientes" in Spanish). In addition, sync status tokens (`success`, `failed`, `running`, `queued`) are translated dynamically via `t('admin.sync_status.<status>')`.
6. **Date Formatting Defect (`2026-08-25 to 2026-09-24`)**:
   - Replaced `${overview.period.since} to ${overview.period.until}` with `formatDateRange(overview.period.since, overview.period.until, { dateStyle: 'medium' }, i18n?.language)`.
   - In English: renders `"Aug 25 – Sep 24, 2026"`.
   - In Spanish: renders `"25 ago – 24 sept 2026"`.

### 12.2 Locale Formatting Infrastructure
- **`frontend/src/utils/formatters.js`**:
  - Implemented `parseDateSafe(val)` to safely parse `YYYY-MM-DD` date strings into local date objects, avoiding negative UTC midnight offset date shifting.
  - Implemented `formatDateRange(startDate, endDate, options, locale)` utilizing native `Intl.DateTimeFormat.prototype.formatRange` with graceful fallback for older runtimes.
  - Updated `formatDate` to use `parseDateSafe`.
- **`frontend/src/i18n/formatters.js`**:
  - Created canonical export mapping forwarding all formatters from `../utils/formatters`.

### 12.3 Verification & Deployment
- **Dedicated Automated Test Suite**:
  - `frontend/src/pages/__tests__/AdminOverviewTranslationClosure.test.jsx`: 4/4 passing tests verifying English default rendering of all 6 reported states, full Spanish rendering upon switching language, runtime language switching without reload, and populated overview metrics invariance.
  - `frontend/src/utils/__tests__/formatters.test.js`: Added date range tests across English and Spanish (7/7 tests passed).
- **Full Frontend Test Suite**:
  - **15 / 15 test suites passed, 76 / 76 tests passed**.
- **Production Build**:
  - `npm run build` completed cleanly with exit code 0.
- **Docker Deployment**:
  - Image tag updated in `docker-compose.local.yml`: `bopsocial-frontend-local:bs-2.2.1`.
  - Rebuilt and started container: `agencyos-frontend-1` running `bopsocial-frontend-local:bs-2.2.1`.
  - HTTP health check verified: `curl.exe --max-time 10 -I http://localhost:3010/` returned **HTTP/1.1 200 OK**.
  - Direct login verification on port 3010 verified: `LOGIN_CHECK: SUCCESS, has_access=True`.

---

## 13. Phase BS-2.3 — Analytics & Reporting Internationalization

### 13.1 Scope and Objective
Phase BS-2.3 delivered complete English and Spanish internationalization for Bop Social's authenticated Analytics (`/admin/analytics/analytics`, `/dashboard/analytics`) and Reporting (`/admin/analytics/reports`, `/dashboard/reports`) modules. Every dynamic label, metric card, section title, empty/loading state, table header, chart legend/tooltip, and modal control was brought under translation catalogs while preserving calculations, chart structures, routes, API contracts, brand invariants (`Bop Social`), and platform proper nouns (`Facebook`, `Instagram`, `YouTube`, `LinkedIn`, `Google My Business`).

### 13.2 Architecture & Namespace Organization
Two new dedicated translation namespaces were introduced, modularizing Analytics and Reporting cleanly alongside `dashboard`, `app`, `auth`, `marketing`, and `settings`:
- **`analytics.json`** (`frontend/src/locales/en/analytics.json` & `es/analytics.json`):
  - Metric labels (`Impressions` / `Impresiones`, `Reach` / `Alcance`, `Clicks` / `Clics`, `Video Views` / `Visualizaciones de video`, `Followers` / `Seguidores`, `Likes` / `Me gusta`, `CTR`).
  - Section titles and subtitles (`Performance Over Time — {{client}}`, `Performance by Platform`, `Platform Distribution`, `Platform Metrics Comparison`, `All Metrics Over Time`, `Platform Balance Radar`, `Platform Breakdown`, `User Overview`).
  - Dropdown options (`All Users` / `Todos los usuarios`, `All Platforms` / `Todas las plataformas`).
  - Dynamic comparison suffixes (`vs prev period` / `vs período anterior`).
  - Chart empty & loading states (`Loading chart…`, `No data for this period. Try syncing the user first.`, `No data yet. Sync your users to see platform analytics.`, `No platform data yet.`, `No timeseries data.`, `No platform data. Sync clients to populate analytics.`, `No clients yet. Add a client to get started.`).
  - Table headers, statuses, and action controls (`Client`, `Platform`, `Status`, `Created`, `Website`, `Active`, `Inactive`, `View Analytics →`).
- **`reports.json`** (`frontend/src/locales/en/reports.json` & `es/reports.json`):
  - Page header title, subtitle, and filter dropdown options (`Reports` / `Informes`, `All clients` / `Todos los clientes`).
  - Segmented tabs (`Shared Links` / `Enlaces compartidos`, `ROI Reports` / `Informes de ROI`).
  - Shared Links panel: header, refresh action, loading/empty states, expired tags, view counts, creation/expiration relative dates, and action button tooltips (`Copy link`, `Open report`, `Deactivate`).
  - ROI Reports panel: header, month selector options (`Jan`..`Dec` / `Ene`..`Dic`), loading/empty states, table headers (`User`, `Month`, `ROI %`, `Investment`, `Revenue`, `Leads`, `Status`, `View →`), and rating badges (`Excellent`, `Good`, `Average`, `Review`).
  - Share Report modal (`ShareReportModal.jsx`): title, date range picker, platform selectors, expiry options (`Never`, `24 hours`, `7 days`, `30 days`), password protection controls, link generation button, copied feedback, and existing client links list.
  - Public shared report view (`PublicReportPage.jsx`): password verification gate, section titles, headers, and localized date range representations.

### 13.3 Localization Implementation Highlights
- **`AnalyticsPage.jsx`**:
  - Replaced hardcoded strings with `t()` calls using `useTranslation('analytics')`.
  - Date ranges formatted with `formatDateRange(range.since, range.until, { dateStyle: 'medium' }, i18n?.language)`.
  - Recharts radar axes, area charts, line charts, and bar charts dynamically localized via `METRIC_META` mapping.
  - Subtitle updates dynamically based on client selection (`Viendo <Cliente> — <fecha>` vs `Resumen de todos los clientes — <fecha>`).
- **`ReportsPage.jsx`**:
  - Wired all tab panels, cards, and tables to `reports` namespace using `useTranslation('reports')`.
  - ROI currency and numbers formatted with locale-sensitive separators via `formatNumber()`.
  - Relative creation times formatted via `formatRelativeTime(link.created_at, i18n?.language)`.
- **`ShareReportModal.jsx`**:
  - Translated all expiry options, validation alerts, password toggles, and copy states.
- **`PublicReportPage.jsx`**:
  - Localized password gate form, public header, PDF download trigger, and table columns.

### 13.4 Verification & Deployment
- **Dedicated Automated Test Suite**:
  - `frontend/src/pages/__tests__/AnalyticsReportingTranslation.test.jsx`: 7/7 passing tests verifying:
    - English default rendering for all 12 reported defects and components.
    - Spanish rendering upon switching platform language.
    - Client-specific drill-down view translation and dynamic title generation.
    - Empty and loading states across both modules in Spanish.
    - ReportsPage tabs, ROI reports table, localized badges, and month names.
    - ShareReportModal form controls and expiry options in Spanish.
- **Full Frontend Test Suite**:
  - **16 / 16 test suites passed, 83 / 83 tests passed**.
- **Production Build**:
  - `npm run build` completed cleanly with exit code 0.
- **Docker Deployment**:
  - Image tag updated in `docker-compose.local.yml`: `bopsocial-frontend-local:bs-2.3`.
  - Rebuilt and started container: `agencyos-frontend-1` running `bopsocial-frontend-local:bs-2.3`.
  - HTTP health check verified: `curl.exe --max-time 10 -I http://localhost:3010/` returned **HTTP/1.1 200 OK**.

---

## 14. Phase BS-2.4 — Content & Publishing Internationalization

### 14.1 Scope and Objectives
Phase BS-2.4 delivered complete English and Spanish internationalization for Bop Social's authenticated Content & Publishing modules:
1. **Content Composer** (`/composer`, `/composer/:id`, `frontend/src/pages/composer/ComposerPage.jsx`):
   - Multi-platform post composition header, action controls, platform toggles, media type selectors, scheduling strip, validation warnings, preflight checks, toast alerts, and platform previews.
2. **Media Library** (`/composer/media`, `frontend/src/pages/composer/MediaLibraryPage.jsx`):
   - Header action buttons, drag-and-drop file upload zone, media type dropdowns, search input, folder navigation, bulk deletion confirmations, and empty states.
3. **Publishing Queues** (`/composer/queues`, `frontend/src/pages/composer/QueueManagerPage.jsx`):
   - Auto-post queue manager, cron slot badges, execution status badges, queue pause/resume controls, create queue modal, and add item modal.
4. **Editorial Calendar & Drawers** (`/calendar`, `frontend/src/pages/CalendarPage.jsx`, `CalendarGrid.jsx`, `PostDrawer.jsx`, `PostFormDrawer.jsx`):
   - Calendar grid with localized weekday headers and month/year navigation, view toggles (`Month`, `List`, `Stats`), upcoming scheduled strip, post detail inspection drawer, performance metric tiles, and scheduling form drawer with date/time pickers and suggested best times.
5. **My Posts** (`/posts`, `frontend/src/pages/MyPostsPage.jsx`):
   - Performance review grid, date range filters, platform tabs, empty state, localized date representations, and pagination controls.
6. **Video Studio** (`/video-studio`, `frontend/src/pages/video/VideoStudioPage.jsx`):
   - Video upload and URL import card, video player, derived clips tray, tool navigation tabs (`Trim`, `Resize`, `Thumbnail`, `Captions`, `Publish`), trim sliders, aspect ratio selectors, frame extractor, automatic transcription/captioning, and YouTube direct publisher.

### 14.2 Mandatory Invariants & Rules Enforced
- **Customer Content Integrity**: Customer post titles, captions, hashtags, user mentions, media URLs, queue names, and comments are never translated or mutated.
- **Machine-readable Status Values**: Backend status codes (`draft`, `scheduled`, `publishing`, `published`, `failed`, `queued`, `cancelled`) and provider IDs (`facebook`, `instagram`, `youtube`, `linkedin`, `google_my_business`) remain invariant in API contracts. User-facing labels are mapped dynamically via `t('status.<key>')` and `t('content:...')`.
- **Brand & Proper Noun Preservation**: The brand name `Bop Social` remains invariant across all files. Social network proper nouns (`Facebook`, `Instagram`, `YouTube`, `LinkedIn`, `Google My Business`) remain as authored.
- **Locale-Aware Date & Number Formatting**: All dates, times, and numeric values utilize `formatDate()`, `formatTime()`, and Intl formatters, decoupling language selection from currency and date parsing integrity.

### 14.3 Translation Namespace Architecture
- Registered **`content.json`** (`frontend/src/locales/en/content.json` & `es/content.json`) into `frontend/src/i18n/config.js` (`resources` and `ns` array):
  - `composer`: Actions, media types, character counters, preflight checks, validation alerts, toast notifications, platform preview badges.
  - `calendar`: Navigation, weekday headers (`Mon`..`Sun` / `Lun`..`Dom`), view toggles, post count interpolations, drawer actions, performance metrics, form fields, and suggested posting time guidance.
  - `queues`: Headers, empty states, creation modal, item insertion modal, execution strategies (`FIFO`, `LIFO`, `Round-robin`), slot badges, and pause/resume statuses.
  - `media`: Upload buttons, drag-and-drop triggers, file type filters, search placeholders, deletion confirmations, and upload success/failure toasts.
  - `video`: Dropzone, URL importer, player preview, tool tabs, trim controls, aspect ratios with feed placement hints, thumbnail frame capture, auto-captions configuration alerts, and YouTube upload metadata fields.
  - `posts`: Summary metrics, view links, and load more pagination.
  - `status`: Machine-readable post lifecycle and queue status mappings (`published`, `scheduled`, `draft`, `failed`, `publishing`, `queued`, `cancelled`, `pending`, `active`, `paused`).

### 14.4 Automated Testing & Verification
- **Test Suite**: `frontend/src/pages/__tests__/ContentPublishingTranslation.test.jsx` (11 passing unit tests):
  - English and Spanish rendering across Composer, Calendar, Drawers, Queues, Media Library, My Posts, and Video Studio.
  - Verification of Customer Content Integrity (untranslated customer captions and titles preserved verbatim across language switches).
  - Verification of Machine-Readable Status Translations (`draft` -> `Draft`/`Borrador`, `scheduled` -> `Scheduled`/`Programado`, `published` -> `Published`/`Publicado`).
  - Strict preservation of proper nouns and brand name `Bop Social`.
- **Full Frontend Test Suite**: 17 / 17 test suites passing, 94 / 94 tests passing.
- **Production Build**: `npm run build` executed cleanly.
- **Deployment**: Image tag `bopsocial-frontend-local:bs-2.4` in `docker-compose.local.yml`, rebuilt frontend container, verified HTTP 200 health check.

---

## 15. Phase BS-2.5 — Interaction & Engagement Internationalization

### 15.1 Scope and Objectives
Phase BS-2.5 delivered complete English and Spanish internationalization for Bop Social's operational Interaction & Engagement modules:
1. **Unified Inbox** (`/inbox`, `frontend/src/pages/inbox/UnifiedInboxPage.jsx`):
   - Page header title, subtitle, search input placeholder, message filter columns (type, platform, sentiment), quick filter pills (`Unread only`, `Starred only`), conversation list cards, thread conversation view with message balloons, action icon tooltips (`Star`, `Archive`, `Resolve`, `Mark read`), reply composer, character counters, channel hints, delivery feedback toasts, and empty state fallbacks.
2. **Reviews** (`/reviews`, `frontend/src/pages/inbox/ReviewsPage.jsx`):
   - Page header title, subtitle, status filter chips (`All`, `New`, `Replied`, `Flagged`), star rating filters (5 to 1 stars), review card rendering, sentiment badges, star rating displays, reply trigger, flag trigger, review reply composition form, owner reply display, flag confirmation dialog with reasons (`Inappropriate`, `Spam`, `Competitor`), and action toasts.
3. **Automations** (`/automations`, `frontend/src/pages/automations/AutomationsPage.jsx`):
   - Page header, subtitle, new rule trigger button, automation rule list, trigger badges, action badges, status switches, run counters, execution timestamps, edit trigger, deletion confirmation, prebuilt automation templates sidebar, and comprehensive rule builder modal with trigger selection (`New comment`, `New DM`, `New review`, `Keyword mention`, `Negative sentiment`), action selection (`Auto-reply`, `AI smart reply`, `Notify team`, `Add tag`, `Assign agent`, `Send webhook`), configuration inputs, and execution feedback toasts.
4. **AI Reply Suggestions** (`frontend/src/components/ai/AIReplySuggestions.jsx`):
   - Suggestion block header with sparkles icon, regenerate suggestions action, drafting state, error state, suggestion pills, recommended pill badge, tone badges (`Professional`, `Friendly`, `Empathetic`, `Warm`, `Apologetic`), and insertion feedback toasts.
5. **WhatsApp Inbox** (`frontend/src/pages/WhatsAppInboxPage.jsx`):
   - Page header, conversation count badge, conversation list rows, 24-hour customer window status badges and warnings (`24h window open` / `24h window closed. Send an approved template message instead.`), message bubbles with relative time formatting, status delivery ticks tooltips (`Sent`, `Delivered`, `Read`, `Failed`), and free-form reply composer.
6. **BS-2.4 Residual Closures**:
   - Resolved untranslated `"Write with AI"` button in `frontend/src/components/ai/AIWriteButton.jsx` via `content.json` (`content:write_with_ai` and `content:ai_assistant`).
   - Resolved Spanish month-year formatting in `frontend/src/pages/CalendarPage.jsx` by creating a dedicated `formatMonthYear(date, locale)` helper in `frontend/src/utils/formatters.js`, eliminating `"Septiembre De 2026"` capitalization bug and ensuring compliant `"Septiembre de 2026"`.

### 15.2 Mandatory Invariants & Rules Enforced
- **Customer Content & Reviewer Integrity**: Customer inbound messages, usernames, handles, review comments, reviewer names, reviewer avatars, and direct quotes are NEVER modified, translated, or corrupted across language toggling.
- **Machine-Readable Identifiers**: Trigger identifiers (`new_comment`, `new_dm`, `new_review`, `keyword_mention`, `negative_sentiment`), action types (`auto_reply`, `ai_smart_reply`, `notify_team`, `add_tag`, `assign_agent`, `send_webhook`), platform identifiers, and status codes remain invariant in backend payloads.
- **Brand & Proper Noun Preservation**: The brand name `Bop Social` remains invariant across all files, and legacy `"Social Stats"` references have been purged. Social network proper nouns (`Facebook`, `Instagram`, `YouTube`, `LinkedIn`, `Google My Business` / `Google Business Profile`, `WhatsApp`) remain as authored.

### 15.3 Translation Namespace Architecture
- Registered **`engagement.json`** (`frontend/src/locales/en/engagement.json` & `es/engagement.json`) into `frontend/src/i18n/config.js` (`resources` and `ns` array):
  - `inbox`: Action buttons, filters, quick chips, conversation states, sentiment labels, thread controls, reply placeholders, toast feedback.
  - `reviews`: Filter labels, status chips, sentiment labels, action triggers, reply form, owner response header, flag modal reasons.
  - `automations`: Page titles, rule cards, run count text, trigger/action badges, modal form labels, prebuilt templates, execution toasts.
  - `ai_replies`: Header, regenerate action, tone pills, recommended badge, insertion toast, unavailable alert.
  - `whatsapp_inbox`: Headers, conversation counters, 24-hour window open/closed badges and alerts, message bubble delivery statuses.

### 15.4 Automated Testing & Verification
- **Dedicated Automated Test Suite**:
  - `frontend/src/pages/__tests__/InteractionEngagementTranslation.test.jsx`: 10 passing tests verifying:
    - BS-2.4 residual closures (`formatMonthYear` lowercase preposition `"Septiembre de 2026"` and `AIWriteButton` localization).
    - UnifiedInboxPage English and Spanish rendering with full Customer Message Content Integrity.
    - ReviewsPage English and Spanish rendering with full Reviewer Content Integrity.
    - AutomationsPage English and Spanish rendering of rules, templates, and builder controls.
    - AIReplySuggestions English and Spanish tone badges and recommended chips.
    - WhatsAppInboxPage English and Spanish header, 24h window badge, and message history.
- **Full Frontend Test Suite**:
  - **18 / 18 test suites passed, 104 / 104 tests passed**.
- **Production Build**:
  - `npm run build` completed cleanly with exit code 0.
- **Docker Deployment**:
  - Image tag updated in `docker-compose.local.yml`: `bopsocial-frontend-local:bs-2.5`.
  - Rebuilt and started container: `agencyos-frontend-1` running `bopsocial-frontend-local:bs-2.5`.
  - HTTP health check verified: `curl.exe --max-time 10 -I http://localhost:3010/` and `http://localhost:3010/login` returned **HTTP/1.1 200 OK**.

### 15.5 Phase BS-2.5.1 — Automations Template Translation Closure
- **Visual Residual Defect**: During browser verification of `/admin/analytics/automations`, the Templates sidebar displayed English system-controlled titles and descriptions served by `/api/automations/templates/` (`automation_engine.RULE_TEMPLATES`).
- **Closed Strings**:
  - `"Auto-thank for 5-star reviews"` / `"Agradecimiento automático por reseñas de 5 estrellas"`
  - `"Alert me on negative sentiment"` / `"Avisarme ante sentimiento negativo"`
  - `"AI smart-reply to comments"` / `"Respuesta inteligente con IA a comentarios"`
  - `"Tag urgent keywords"` / `"Etiquetar palabras clave urgentes"`
  - `"Webhook on new DM"` / `"Webhook ante nuevo mensaje directo"`
  - `"Assign 1-2★ reviews to support lead"` / `"Asignar reseñas de 1-2★ al líder de soporte"`
  - Associated descriptions, prefilled rule names, and action templates.
- **Source & Resolution**: Preserved backend API contracts in `automation_engine.py`; resolved on the frontend display layer by registering `automations.templates` in `en/engagement.json` and `es/engagement.json`, localized via `getLocalizedTemplate(tpl, t)` in `AutomationsPage.jsx`.
- **Verification**: 11 / 11 tests passing in `InteractionEngagementTranslation.test.jsx`, 105 / 105 passing across full frontend suite, image updated to `bopsocial-frontend-local:bs-2.5.1`.








