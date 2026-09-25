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

---

## 16. Phase BS-2.6A — Social Connections & Provider States Translation

### 16.1 Scope and Objectives
Phase BS-2.6A delivers the first remediation phase defined in the BS-2.6 audit, providing complete English and Spanish internationalization for Bop Social's Social Account Connections and Provider States management:
1. **Connected Accounts Dashboard Panel** (`frontend/src/components/ui/ConnectedAccounts.jsx`):
   - Section heading (`Connected Accounts` / `Cuentas Conectadas`) and descriptive subtitle.
   - Platform status badges (`Active` / `Activo`, `Expired` / `Vencido`, `Not connected` / `No conectado`).
   - Shared account notes (`Connected via Facebook` / `Conectado vía Facebook`).
   - Token expiration date display localized using `formatDate(s.expires_at, { dateStyle: 'medium' }, i18n?.language)` (`Token expires: ...` / `El token vence: ...`).
   - Connect and disconnect button labels (`Connect {{platform}} →`, `Disconnect`, `Disconnecting…`).
   - Workspace preparation alert dialog and disconnect confirmation prompt.
   - Educational help box explaining authentication flow and shared platform logins.
2. **Meta Permissions Consent Modal** (`frontend/src/components/FacebookConnectModal.jsx`):
   - Modal title (`Connect Your Facebook & Instagram` / `Conecta tu Facebook e Instagram`), instructions, section headers (`Required Permissions`, `Optional Permissions`, `Optional` badge).
   - Localized human-readable permission titles and descriptions for Meta scopes:
     - `pages_show_list`: "Access your Facebook Pages list" / "Acceder a tu lista de Páginas de Facebook".
     - `pages_read_engagement`: "Read Page engagement data" / "Leer datos de interacción de la Página".
     - `instagram_manage_insights`: "Read Instagram insights" / "Leer estadísticas de Instagram".
   - Tooltip explanations, close and cancel button labels, continue button states (`Connecting…`, `Loading Facebook…`, `Continue with Facebook`).
   - Legal terms and privacy policy disclaimers.
   - Error messages (Facebook SDK loading failure, denied permissions, login cancellation, profile fetch errors).
3. **Corporate Branding Correction**:
   - Replaced legacy `appName="Social Stats"` in `ConnectedAccounts.jsx` and `FacebookConnectModal.jsx` with canonical `appName="Bop Social"`.

### 16.2 Mandatory Invariants & Rules Enforced
- **Strict Machine Contract Preservation**:
  - Technical OAuth scope identifiers (`pages_show_list`, `pages_read_engagement`, `instagram_manage_insights`) remain verbatim and untranslated in API contracts and code tags.
  - Platform identifiers (`facebook`, `instagram`, `youtube`, `google_my_business`, `linkedin`) and machine status codes (`active`, `expired`, `not_connected`) remain strictly invariant.
- **Brand & Proper Noun Preservation**:
  - The corporate brand `Bop Social` and platform names (`Facebook`, `Instagram`, `YouTube`, `LinkedIn`, `Google My Business`, `WhatsApp`) are strictly preserved.
- **Locale-Aware Date Formatting**:
  - Token expiration dates utilize `formatDate()` with the active language locale instead of host-dependent native JS date calls.
- **Tenant Isolation**:
  - Client workspace isolation is preserved; users can only connect or view social accounts tied to their active tenant workspace.

### 16.3 Translation Namespace Architecture
- Registered **`connections.json`** (`frontend/src/locales/en/connections.json` & `es/connections.json`) in `frontend/src/i18n/config.js` with 100% key parity (50 keys):
  - `title`, `subtitle`: Section headings.
  - `status`: Active, expired, not connected, connected via Facebook, token expiration.
  - `actions`: Connect platform, disconnect, disconnecting, continue with Facebook, cancel, trigger button.
  - `alerts`, `confirm`: Workspace preparation alert, disconnect confirmation prompt.
  - `help`: Multi-step educational guide.
  - `modal`: Permissions consent modal headers, buttons, accessible ARIA labels, legal disclaimer.
  - `permissions`: Human-readable labels, descriptions, and technical scope tooltips.
  - `errors`: Facebook SDK and OAuth failure messages.

### 16.4 Automated Testing & Verification
- **Dedicated Automated Test Suite**:
  - `frontend/src/components/ui/__tests__/ConnectedAccountsTranslation.test.jsx`: **15 / 15 passing tests** verifying:
    1. `ConnectedAccounts` English rendering.
    2. `ConnectedAccounts` Spanish rendering.
    3. Active status label translation in English and Spanish.
    4. Expired status label translation in English and Spanish.
    5. Not connected status label translation in English and Spanish.
    6. Token expiration date formatting with active locale.
    7. Human-readable permission descriptions and labels in `FacebookConnectModal`.
    8. `FacebookConnectModal` English rendering.
    9. `FacebookConnectModal` Spanish rendering.
    10. Component state and checkbox selection preservation across language toggling.
    11. Technical OAuth scopes invariance (`pages_show_list`, `pages_read_engagement`, `instagram_manage_insights`).
    12. Disconnect confirmation prompt translation and active confirmation gate.
    13. Complete removal of user-visible `Social Stats` branding and replacement with `Bop Social`.
    14. 100% key parity between `en/connections.json` and `es/connections.json`.
    15. Strict mocking of provider API endpoints and verification of scope parameters.
- **Full Frontend Test Suite**: **19 / 19 test suites passed, 120 / 120 tests passed**.
- **Backend Test Suite**: **10 / 10 tests passed** in `social_stats.tests.test_language_preferences`.
- **Production Build**: `npm run build` executed cleanly with exit code 0.
- **Docker Deployment**: Frontend image updated to `bopsocial-frontend-local:bs-2.6a` in `docker-compose.local.yml`, container recreated and verified live with HTTP 200 health checks on `http://localhost:3010/` and `http://localhost:3010/login`.

---

## 17. Phase BS-2.6B.1 — User Settings & Security Internationalization

### 17.1 Mission & Scope
Phase BS-2.6B.1 internationalized the authenticated User Settings, Account Security, Notifications, Appearance, Keyboard Shortcuts, Developer Integrations (API Keys and Webhooks), Data & Privacy, and Danger Zone interfaces.

- **Files Internationalized**:
  - `frontend/src/locales/en/auth.json` & `frontend/src/locales/es/auth.json` (Auth namespace parity resolution).
  - `frontend/src/locales/en/settings.json` & `frontend/src/locales/es/settings.json` (Expanded to 296 keys with 100% key parity).
  - `frontend/src/pages/UserSettingsPage.jsx`: Navigation tabs, `DeleteAccountSection`, `SecurityTab`, `AgencyTab`.
  - `frontend/src/pages/settings/SecuritySections.jsx`: `MFAManager` (2FA TOTP setup wizard, backup codes, disable modal) and `ActiveSessionsList` (session list, revoked status, revoke prompt, sign-out-all).
  - `frontend/src/pages/settings/SettingsSections.jsx`: `NotificationsSection`, `AppearanceSection` (Theme + Density), `KeyboardShortcutsSection`, `APIKeysSection`, `DataPrivacySection`, `WebhooksSection`, `CrossLinksSection`.
  - `docker-compose.local.yml`: Updated local frontend image to `bopsocial-frontend-local:bs-2.6b.1`.

### 17.2 Architecture & Invariants Preservation
- **Authentication & Security Non-Regression**:
  - No authentication contracts, session management mechanisms, password hashing algorithms, TOTP generation algorithms, or JWT handling logic were modified.
- **Auth Catalog Parity Closure**:
  - Resolved the 7 missing keys in `frontend/src/locales/en/auth.json` (`step_about`, `step_account`, `step_confirm`, `subtitle_step_2`, `subtitle_step_3`, `title_step_2`, `title_step_3` under `end_user_signup`), achieving 100% parity across all 173 keys with `frontend/src/locales/es/auth.json`.
- **Machine-Readable Invariants Preserved**:
  - Webhook and telemetry event identifiers (`composer.post_published`, `composer.post_failed`, `inbox.new_message`, `credential.token_expired`, `goal.milestone_hit`) remain untranslated.
  - API scopes (`read:posts`, `write:leads`, etc.) and key prefix structures remain verbatim.
  - Internal storage keys (`socialstats_notif_prefs`, `socialstats_density`, `socialstats_webhook_endpoints`) were preserved for backward compatibility.
  - Danger Zone confirmation keyword `DELETE` preserved as universal invariant token while localizing prompts and explanations.
- **Residual Branding Eradication**:
  - Completely removed residual `Social Stats` text from user-facing surfaces (`DeleteAccountSection` reason prompt, `AgencyTab` description, `AppearanceSection` subtitle, and `APIKeysSection` empty state) replacing them with `Bop Social`.
- **Locale-Aware Formatting**:
  - Formatted dates in `AgencyTab`, `MFAManager`, `ActiveSessionsList`, `APIKeysSection`, and `DataPrivacySection` using locale-sensitive formatting based on active i18n language (`es-ES` / `en-US`).

### 17.3 Automated Testing & Verification
- **Dedicated Automated Test Suite**:
  - `frontend/src/pages/__tests__/UserSettingsSecurityTranslation.test.jsx`: **18 / 18 passing tests** covering:
    1. 100% key parity and symmetry in `settings.json` (296 keys in EN and ES).
    2. 100% key parity in `auth.json` (173 keys in EN and ES) confirming resolution of the 7 missing keys.
    3. Absence of residual "Social Stats" branding in settings catalogs.
    4. English navigation tab and category rendering in `UserSettingsPage`.
    5. Spanish navigation tab and category rendering after language switch.
    6. Password change form labels and placeholders in English and Spanish.
    7. Form validation and localized error messages.
    8. Disabled MFA state rendering in English and Spanish.
    9. Enabled MFA state, badge, and backup codes count rendering in English and Spanish.
    10. Active sessions list, revoked badge, and device/OS descriptions in English and Spanish.
    11. Notifications channel and event matrix in English and Spanish.
    12. Appearance theme and density controls in English and Spanish.
    13. Keyboard shortcuts categories and action labels in English and Spanish.
    14. API Keys form, key list, scopes invariant preservation in English and Spanish.
    15. Webhooks form, empty state, and events invariant preservation in English and Spanish.
    16. Data & Privacy export, consents, and pause processing in English and Spanish.
    17. Danger Zone deletion multi-step flow with invariant `DELETE` confirmation keyword in English and Spanish.
    18. Agency connection card, permissions checklist, and disconnect dialog in English and Spanish.
- **Full Frontend Test Suite**: **20 / 20 test suites passed, 138 / 138 tests passed**.
- **Production Build**: `npm run build` executed cleanly with exit code 0.
- **Docker Deployment**: Frontend image updated to `bopsocial-frontend-local:bs-2.6b.1` in `docker-compose.local.yml`, container recreated and verified live with HTTP 200 health checks on `http://localhost:3010/` and `http://localhost:3010/account-settings`.

---

## 18. Phase BS-2.6B.1.1 — API Key Error & Tenant Context Closure

### 18.1 Problem Statement & Root Cause
- **Observed Behavior**:
  - A superadmin navigating to `/admin/account-settings` and switching to the API Keys section immediately saw a red error toast: `"No se pudo crear la clave"` (or `"Could not create key"` in English) without clicking "Generate".
- **Diagnostic Root Cause Analysis**:
  1. **Backend Scoping Invariant**: The backend endpoint `GET /api/api-keys/` requires a tenant/client context (`_resolve_client_for_user()` returns `None` for superadmins without an active `client_id`), correctly returning HTTP 403 Forbidden with `{"error": "no client context"}`.
  2. **Frontend Error Key Misattribution**: In `APIKeysSection.load().catch()`, the failure handler incorrectly referenced translation key `api_keys.err_create` (`"No se pudo crear la clave"`) instead of an API load error key.
  3. **Zero Mutation / Idempotency**: Zero POST requests were sent, zero keys were created, and zero backend security boundaries were breached.

### 18.2 Remediation & Architectural Invariants
- **Translation Catalog Parity**:
  - Added the following keys to `frontend/src/locales/en/settings.json` and `frontend/src/locales/es/settings.json`:
    - `api_keys.err_load`: `"Could not load API keys"` / `"No se pudieron cargar las claves de API"`
    - `api_keys.no_client_title`: `"Client workspace required"` / `"Se requiere un espacio de trabajo de cliente"`
    - `api_keys.no_client_desc`: `"API keys are scoped to specific client workspaces. Please select or switch to a client workspace to manage its API keys."` / `"Las claves de API están asociadas a espacios de trabajo de clientes específicos. Selecciona o cambia a un espacio de trabajo de cliente para gestionar sus claves de API."`
  - Re-verified 100% key parity between English and Spanish (299 keys in both catalogs).
- **Graceful Tenant Context Handling**:
  - `UserSettingsPage.jsx` passes `user={user}` to `<APIKeysSection user={user} />`.
  - `APIKeysSection` resolves the current user context via props or `useAuth()`.
  - When the user is a superadmin without a selected `client_id` or when the backend returns HTTP 403 with `"no client context"`, the component enters a clean informational state (`missingContext = true`):
    - Red error toast is completely suppressed.
    - Informational card is rendered with an intuitive icon and bilingual explanation.
    - Key generation and revocation controls are not rendered, preventing invalid operations.
- **Accurate Error Localization**:
  - On genuine load failures (HTTP 500 / network error), `APIKeysSection` invokes `toast.error(t('api_keys.err_load'))`, cleanly distinguishing load errors from key creation errors.

### 18.3 Verification & Deployment
- **Automated Unit & Integration Tests**:
  - `frontend/src/pages/__tests__/UserSettingsSecurityTranslation.test.jsx`: **22 / 22 passing tests** (added 4 new tests specifically verifying missing client context suppression, 403 handling, localized load error reporting, and zero POST calls on mount).
  - Full frontend suite: **20 / 20 test suites passed, 142 / 142 tests passed**.
- **Production Build**:
  - `npm run build` executed cleanly with exit code 0.
- **Docker Deployment**:
  - Image tag updated in `docker-compose.local.yml`: `bopsocial-frontend-local:bs-2.6b.1.1`.
  - Container recreated and healthy on `http://localhost:3010/` (HTTP 200).

## 19. Phase BS-2.6B.2 — Client & Tenant Management Internationalization

### 19.1 Scope & Architecture
- **Dedicated Namespace**: Registered `management` namespace across `frontend/src/i18n/config.js` (`resources` and `ns` array).
- **Target Administration Interfaces**:
  - `/admin/clients` (`AllClientsPage.jsx`): Client statistics, invitations panel, invitation tracking with localized badges, connected client directory, client-level and global platform sync triggers, and onboarding guides.
  - `/admin/management` (`ManagementPage.jsx`): Staff members and role assignment, permissions editor with granular ability groups, user access and custom portal configuration, role default permission matrix, and staff creation modal.
  - `/admin/client/:clientId/edit` (`EditClientPage.jsx`): Client organization settings, contact info, default language preference (`en`, `es`, system), validation feedback, and status.
  - `/admin/trust` (`AdminTrustQueuePage.jsx`): Agency verification queue, decision prompts (approval note, rejection reason), dispute handling with category and status filters, evidence inspection, and resolution workflow.
  - `/admin/analytics/approvals` (`ApprovalQueuePage.jsx`): Post approval queue with count-based subtitle pluralization, inbox-zero empty state, review action buttons (Approve, Reject, Edit), and confirmation dialogs.
  - `/admin/analytics/audit-log` (`AuditLogPage.jsx`): Write action audit history, action search, result filter dropdown (`all`, `success`, `partial`, `failed`), and tabular log inspection.
- **Shared Breadcrumb Resolution (BS-2.6B.1 residual closure)**:
  - Updated `TopBar.jsx` (`buildBreadcrumbs`) to look up `breadcrumbs.${key}` in `app.json`.
  - Added full admin routing segments in `frontend/src/locales/en/app.json` and `frontend/src/locales/es/app.json`:
    - `account_settings`: `"Account Settings"` / `"Configuración de cuenta"`
    - `clients`: `"Clients"` / `"Clientes"`
    - `management`: `"Team Management"` / `"Gestión de equipo"`
    - `client`: `"Client"` / `"Cliente"`
    - `edit`: `"Edit"` / `"Editar"`
    - `trust`: `"Trust & Approvals"` / `"Confianza y aprobaciones"`
    - `approvals`: `"Approvals"` / `"Aprobaciones"`
    - `audit_log`: `"Audit Log"` / `"Registro de auditoría"`

### 19.2 Invariants Preserved
- **Data Isolation & Backend Schemas**: Preserved exact backend role values (`superadmin`, `staff`, `client`, `agency_member`, `end_user`) and entity IDs.
- **Customer Content Integrity**: Company names, user names, emails, and post content remain completely unmutated across language transitions.
- **100% Key Parity**:
  - `management.json`: 247 keys in both English and Spanish (0 missing in ES, 0 missing in EN).
  - `app.json`: 152 keys in both English and Spanish (0 missing in ES, 0 missing in EN).

### 19.3 Verification & Deployment
- **Automated Tests**:
  - Created `frontend/src/pages/__tests__/ClientTenantManagementTranslation.test.jsx`: **11 / 11 passing tests**.
  - Full frontend suite: **21 / 21 test suites passed, 153 / 153 tests passed**.
  - Backend regression test suite: **334 / 334 tests passed**.
- **Production Build**:
  - `npm run build` executed with zero warnings/errors.
- **Local Docker Deployment**:
  - Built frontend image: `bopsocial-frontend-local:bs-2.6b.2`.
  - Backend image retained: `bopsocial-backend-local:bs-2.1.1`.
  - Verified container recreation and endpoints:
    - `http://localhost:3010/` -> HTTP 200 OK
    - `http://localhost:3010/login` -> HTTP 200 OK

---

## 20. Phase BS-2.6B.2.1 — Account Settings Breadcrumb Visual Acceptance Closure

### 20.1 Root Cause & Defect Analysis
During visual browser acceptance verification for Phase BS-2.6B.2 at `http://localhost:3010/admin/account-settings`, the page heading correctly displayed `"Configuración"` (via `settings.json`), but the TopBar breadcrumb continued displaying `"Account Settings"` in Spanish instead of `"Configuración de cuenta"`.

Root cause investigation revealed a dual deployment / caching defect:
1. **Aggressive PWA Service Worker Cache-First Strategy**:
   - `frontend/public/sw.js` previously used `CACHE_NAME = 'socialstats-v1'` with a cache-first return strategy (`return cached || fetched;`).
   - Browsers that previously loaded Bop Social under BS-2.6B.1 or earlier held cached copies of `index.html` referencing pre-BS-2.6B.2 compiled script bundles (`main.cffde830.js` or older).
   - Because `request.mode === 'navigate'` served the cached `index.html` first, the browser never requested the updated bundle containing the breadcrumb translations.
2. **Missing Nginx Cache Invalidation Headers**:
   - In `frontend/docker/nginx.conf`, `/index.html`, `/sw.js`, and the SPA fallback `/` lacked explicit `Cache-Control` headers, permitting browser heuristic caching.

### 20.2 Minimal Correct Fix
1. **Service Worker (`frontend/public/sw.js`)**:
   - Bumped `CACHE_NAME` to `'bopsocial-v2.6b.2.1'`.
   - Upgraded navigation requests (`request.mode === 'navigate'`) to a **Network-First** strategy: fetches fresh HTML from the server first, updates the cache, and falls back to cached `index.html` only when offline.
   - Preserved automated cleanup of legacy caches in the `activate` event and forced immediate takeover with `self.skipWaiting()` and `self.clients.claim()`.
2. **Nginx Server Configuration (`frontend/docker/nginx.conf`)**:
   - Added explicit location block for `= /sw.js` with `Cache-Control "no-cache, no-store, must-revalidate"`, `Pragma "no-cache"`, and `expires 0`.
   - Added explicit location block for `= /index.html` and SPA fallback `/` with `Cache-Control "no-cache, no-store, must-revalidate"`.
   - Retained 30-day immutable caching for hashed static assets in `/static/`.
3. **TopBar Breadcrumb Defensive Resolution (`frontend/src/components/shell/TopBar.jsx`)**:
   - Sanitized `pathname` in `buildBreadcrumbs` to strip query parameters (`?tab=...`), URL hashes (`#top`), and trailing slashes.
   - Hardened `basePath` stripping against missing or empty values.
   - Broadened fallback key lookup across `breadcrumbs.${key}`, `sidebar.items.${key}`, `modules.${key}.label`, `rail.${key}`, `mobile_nav.${key}`, `settings.${key}`, and `navigation.${key}`.
4. **Locale Dictionaries (`en/app.json` & `es/app.json`)**:
   - Added `"account_settings"` to `sidebar.items` as a secondary fallback.
   - Added `"admin"` breadcrumb translation (`"Admin"` in EN, `"Administración"` in ES).

### 20.3 Focused Regression Verification
- **New Test Suite**: `frontend/src/components/shell/__tests__/TopBarBreadcrumb.test.jsx`:
  - Verified pure function `buildBreadcrumbs` resolves `/admin/account-settings` and `/dashboard/account-settings` to `"Account Settings"` in EN and `"Configuración de cuenta"` in ES.
  - Verified that Spanish resolution never falls back to `humanize("account-settings")`.
  - Verified safe handling of query strings, hashes, trailing slashes, and missing `basePath`.
  - Verified live `TopBar` component rendering in both languages and dynamic language switching without page reload.
  - Result: **7 / 7 tests passed**.
- **Full Frontend Suite**: **22 / 22 test suites passed, 160 / 160 tests passed**.
- **Production Build**: `npm run build` executed successfully.

### 20.4 Local Docker Deployment
- **Built Frontend Image**: `bopsocial-frontend-local:bs-2.6b.2.1`.
- **Compose Update**: Updated `docker-compose.local.yml` frontend image tag to `bopsocial-frontend-local:bs-2.6b.2.1`.
- **Deployed Container**: Recreated `agencyos-frontend-1` and verified via HTTP inspection:
  - `curl -i http://localhost:3010/` -> HTTP 200 with `Cache-Control: max-age=0, no-cache, no-store, must-revalidate` serving new bundle `main.ffd0d98b.js`.
  - `curl -i http://localhost:3010/sw.js` -> HTTP 200 with `Cache-Control: no-cache, no-store, must-revalidate` and `CACHE_NAME = 'bopsocial-v2.6b.2.1'`.
  - `curl -i http://localhost:3010/admin/account-settings` -> HTTP 200 with no-cache headers.













