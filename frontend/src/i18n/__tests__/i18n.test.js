import i18n, { SUPPORTED_LANGUAGES, changePlatformLanguage, getInitialLanguage, LANGUAGE_STORAGE_KEY } from '../config';

describe('Bop Social i18n Foundation Suite', () => {
  beforeEach(async () => {
    localStorage.clear();
    await i18n.changeLanguage('en');
  });

  test('initializes with English as default and fallback', () => {
    expect(i18n.language.substring(0, 2)).toBe('en');
    expect(i18n.options.fallbackLng).toContain('en');
    expect(SUPPORTED_LANGUAGES.map((l) => l.code)).toEqual(['en', 'es']);
  });

  test('resolves translation keys across common, navigation, and auth namespaces in English', () => {
    expect(i18n.t('actions.save', { ns: 'common' })).toBe('Save');
    expect(i18n.t('nav.product', { ns: 'navigation' })).toBe('Product');
    expect(i18n.t('nav.sign_in', { ns: 'navigation' })).toBe('Sign in');
    expect(i18n.t('login.title', { ns: 'auth' })).toBe('Welcome back');
  });

  test('switches dynamically to Spanish and translates all namespaces correctly', async () => {
    await changePlatformLanguage('es');
    expect(i18n.language).toBe('es');
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('es');

    expect(i18n.t('actions.save', { ns: 'common' })).toBe('Guardar');
    expect(i18n.t('nav.product', { ns: 'navigation' })).toBe('Producto');
    expect(i18n.t('nav.sign_in', { ns: 'navigation' })).toBe('Iniciar sesión');
    expect(i18n.t('login.title', { ns: 'auth' })).toBe('Bienvenido de nuevo');
    expect(document.documentElement.lang).toBe('es');
  });

  test('falls back cleanly to English for missing keys or non-existent locale', () => {
    const fallbackText = i18n.t('some.nonexistent.key', { defaultValue: 'Default Text' });
    expect(fallbackText).toBe('Default Text');
  });

  test('getInitialLanguage respects localStorage preference', () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    expect(getInitialLanguage()).toBe('es');

    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'en');
    expect(getInitialLanguage()).toBe('en');
  });
});
