/* ============================================================================
 *  Bop Social — Internationalization Engine (i18n)
 *  Configured with i18next & react-i18next.
 *  Supports English (en - default/fallback) and Spanish (es).
 * ========================================================================== */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import enCommon from '../locales/en/common.json';
import esCommon from '../locales/es/common.json';
import enNavigation from '../locales/en/navigation.json';
import esNavigation from '../locales/es/navigation.json';
import enAuth from '../locales/en/auth.json';
import esAuth from '../locales/es/auth.json';
import enMarketing from '../locales/en/marketing.json';
import esMarketing from '../locales/es/marketing.json';
import enApp from '../locales/en/app.json';
import esApp from '../locales/es/app.json';
import enDashboard from '../locales/en/dashboard.json';
import esDashboard from '../locales/es/dashboard.json';
import enSettings from '../locales/en/settings.json';
import esSettings from '../locales/es/settings.json';
import enAnalytics from '../locales/en/analytics.json';
import esAnalytics from '../locales/es/analytics.json';
import enReports from '../locales/en/reports.json';
import esReports from '../locales/es/reports.json';
import enContent from '../locales/en/content.json';
import esContent from '../locales/es/content.json';
import enEngagement from '../locales/en/engagement.json';
import esEngagement from '../locales/es/engagement.json';
import enConnections from '../locales/en/connections.json';
import esConnections from '../locales/es/connections.json';
import enManagement from '../locales/en/management.json';
import esManagement from '../locales/es/management.json';
import enOnboarding from '../locales/en/onboarding.json';
import esOnboarding from '../locales/es/onboarding.json';

export const LANGUAGE_STORAGE_KEY = 'bop_social_language';
export const SUPPORTED_LANGUAGES = [
  { code: 'en', label: 'English', shortLabel: 'EN' },
  { code: 'es', label: 'Español', shortLabel: 'ES' },
];

/**
 * Determine the initial language based on strict precedence:
 * 1. User explicit preference stored in localStorage
 * 2. Navigator/browser language (if starts with 'es', use 'es')
 * 3. Default fallback: 'en'
 */
export function getInitialLanguage() {
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (stored && (stored === 'en' || stored === 'es')) {
      return stored;
    }
  } catch (err) {
    // localStorage might be restricted in private browsing mode
  }

  if (typeof navigator !== 'undefined' && navigator.language) {
    const browserLang = navigator.language.toLowerCase();
    if (browserLang.startsWith('es')) {
      return 'es';
    }
  }

  return 'en';
}

const resources = {
  en: {
    common: enCommon,
    navigation: enNavigation,
    auth: enAuth,
    marketing: enMarketing,
    app: enApp,
    dashboard: enDashboard,
    settings: enSettings,
    analytics: enAnalytics,
    reports: enReports,
    content: enContent,
    engagement: enEngagement,
    connections: enConnections,
    management: enManagement,
    onboarding: enOnboarding,
  },
  es: {
    common: esCommon,
    navigation: esNavigation,
    auth: esAuth,
    marketing: esMarketing,
    app: esApp,
    dashboard: esDashboard,
    settings: esSettings,
    analytics: esAnalytics,
    reports: esReports,
    content: esContent,
    engagement: esEngagement,
    connections: esConnections,
    management: esManagement,
    onboarding: esOnboarding,
  },
};

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: getInitialLanguage(),
    fallbackLng: 'en',
    supportedLngs: ['en', 'es'],
    ns: ['common', 'navigation', 'auth', 'marketing', 'app', 'dashboard', 'settings', 'analytics', 'reports', 'content', 'engagement', 'connections', 'management', 'onboarding'],
    defaultNS: 'common',
    interpolation: {
      escapeValue: false, // React already escapes values safely
    },
    react: {
      useSuspense: false,
    },
  });

/**
 * Helper to update platform language across i18n and local storage
 * @param {string} lang - 'en' | 'es'
 */
export async function changePlatformLanguage(lang) {
  const target = lang === 'es' ? 'es' : 'en';
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, target);
  } catch (err) {
    // Ignore storage errors
  }
  await i18n.changeLanguage(target);
  document.documentElement.lang = target;
  return target;
}

export default i18n;
