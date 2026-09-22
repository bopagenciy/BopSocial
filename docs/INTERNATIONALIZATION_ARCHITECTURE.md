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
