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
    expect(i18n.t('login.or_continue_with', { ns: 'auth' })).toBe('or continue with');
    expect(i18n.t('login.demo_local_notice', { ns: 'auth' })).toBe('local only');
    expect(i18n.t('password_strength.label', { ns: 'auth' })).toBe('Password strength:');
    expect(i18n.t('home.hero_title_highlight', { ns: 'marketing' })).toBe('Marketing OS');
    expect(i18n.t('bento_preview.bot_start', { ns: 'marketing' })).toBe('Start');
  });

  test('switches dynamically to Spanish and translates all namespaces correctly', async () => {
    await changePlatformLanguage('es');
    expect(i18n.language).toBe('es');
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('es');

    expect(i18n.t('actions.save', { ns: 'common' })).toBe('Guardar');
    expect(i18n.t('nav.product', { ns: 'navigation' })).toBe('Producto');
    expect(i18n.t('nav.sign_in', { ns: 'navigation' })).toBe('Iniciar sesión');
    expect(i18n.t('login.title', { ns: 'auth' })).toBe('Bienvenido de nuevo');
    expect(i18n.t('login.or_continue_with', { ns: 'auth' })).toBe('o continuar con');
    expect(i18n.t('login.demo_local_notice', { ns: 'auth' })).toBe('solo local');
    expect(i18n.t('login.demo_password_label', { ns: 'auth' })).toBe('contraseña');
    expect(i18n.t('login.demo_role_superadmin', { ns: 'auth' })).toBe('Superadministrador');
    expect(i18n.t('login.demo_role_agency', { ns: 'auth' })).toBe('Agencia');
    expect(i18n.t('login.demo_role_enduser', { ns: 'auth' })).toBe('Usuario final');
    expect(i18n.t('auth_layout.eyebrow', { ns: 'auth' })).toBe('Sistema Operativo de Marketing');
    expect(i18n.t('password_strength.label', { ns: 'auth' })).toBe('Seguridad de la contraseña:');
    expect(i18n.t('password_strength.strong', { ns: 'auth' })).toBe('Fuerte');
    expect(i18n.t('end_user_signup.summary_industry', { ns: 'auth' })).toBe('Industria');
    expect(i18n.t('end_user_signup.industries.real_estate', { ns: 'auth' })).toBe('Bienes raíces');
    expect(i18n.t('home.hero_title_highlight', { ns: 'marketing' })).toBe('Sistema Operativo de Marketing');
    expect(i18n.t('home.hero_float_new_msg', { ns: 'marketing' })).toBe('NUEVO MENSAJE · IG');
    expect(i18n.t('bento_preview.bot_start', { ns: 'marketing' })).toBe('Inicio');
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
