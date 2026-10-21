import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n, { changePlatformLanguage } from '../../i18n/config';
import UserSettingsPage from '../UserSettingsPage';
import { profileAPI } from '../../services/api';

// Mock useAuth
jest.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, name: 'Jane Smith', email: 'jane@bopsocial.com', role: 'client' },
    refreshAuth: jest.fn(),
    logout: jest.fn(),
    can: () => true,
  }),
}));

// Mock profileAPI
jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {},
  profileAPI: {
    get: jest.fn(),
    update: jest.fn(),
    agencyInfo: jest.fn(),
  },
}));

describe('Dashboard & Settings Translation (BS-2.2)', () => {
  beforeEach(async () => {
    localStorage.clear();
    profileAPI.get.mockResolvedValue({
      data: {
        first_name: 'Jane',
        last_name: 'Smith',
        email: 'jane@bopsocial.com',
        language: 'en',
        is_social: false,
      },
    });
    profileAPI.update.mockResolvedValue({ data: {} });
    if (profileAPI.agencyInfo) {
      profileAPI.agencyInfo.mockResolvedValue({ data: {} });
    }
    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  test('resolves app, dashboard, and settings catalog keys in English', () => {
    // App namespace
    expect(i18n.t('rail.brand_home', { ns: 'app' })).toBe('Bop Social home');
    expect(i18n.t('modules.analytics.label', { ns: 'app' })).toBe('Analytics');
    expect(i18n.t('command_palette.quick_actions', { ns: 'app' })).toBe('Quick actions');

    // Dashboard namespace
    expect(i18n.t('subtitle', { ns: 'dashboard' })).toBe('Social Media Analytics');
    expect(i18n.t('sync_now', { ns: 'dashboard' })).toBe('Sync Now');
    expect(i18n.t('tabs.overview', { ns: 'dashboard' })).toBe('Overview');
    expect(i18n.t('metrics.impressions', { ns: 'dashboard' })).toBe('Impressions');
    expect(i18n.t('metrics.reach', { ns: 'dashboard' })).toBe('Reach');
    expect(i18n.t('breakdown.title', { ns: 'dashboard' })).toBe('Platform Breakdown');
    expect(i18n.t('admin.hero_eyebrow', { ns: 'dashboard' })).toBe('Agency Command Center');

    // Settings namespace
    expect(i18n.t('title', { ns: 'settings' })).toBe('Settings');
    expect(i18n.t('groups.account', { ns: 'settings' })).toBe('Account');
    expect(i18n.t('tabs.profile', { ns: 'settings' })).toBe('Profile');
    expect(i18n.t('profile.title', { ns: 'settings' })).toBe('Profile Information');
  });

  test('resolves app, dashboard, and settings catalog keys in Spanish', async () => {
    await act(async () => {
      await changePlatformLanguage('es');
    });

    // App namespace
    expect(i18n.t('rail.brand_home', { ns: 'app' })).toBe('Inicio de Bop Social');
    expect(i18n.t('modules.analytics.label', { ns: 'app' })).toBe('Analítica');
    expect(i18n.t('command_palette.quick_actions', { ns: 'app' })).toBe('Acciones rápidas');

    // Dashboard namespace
    expect(i18n.t('subtitle', { ns: 'dashboard' })).toBe('Analítica de redes sociales');
    expect(i18n.t('sync_now', { ns: 'dashboard' })).toBe('Sincronizar ahora');
    expect(i18n.t('tabs.overview', { ns: 'dashboard' })).toBe('Resumen');
    expect(i18n.t('metrics.impressions', { ns: 'dashboard' })).toBe('Impresiones');
    expect(i18n.t('metrics.reach', { ns: 'dashboard' })).toBe('Alcance');
    expect(i18n.t('breakdown.title', { ns: 'dashboard' })).toBe('Desglose por plataforma');
    expect(i18n.t('admin.hero_eyebrow', { ns: 'dashboard' })).toBe('Centro de control de agencia');

    // Settings namespace
    expect(i18n.t('title', { ns: 'settings' })).toBe('Configuración');
    expect(i18n.t('groups.account', { ns: 'settings' })).toBe('Cuenta');
    expect(i18n.t('tabs.profile', { ns: 'settings' })).toBe('Perfil');
    expect(i18n.t('profile.title', { ns: 'settings' })).toBe('Información del perfil');
  });

  test('UserSettingsPage renders translated headings and tabs in Spanish', async () => {
    await act(async () => {
      await changePlatformLanguage('es');
    });

    await act(async () => {
      render(
        <MemoryRouter>
          <UserSettingsPage />
        </MemoryRouter>
      );
    });

    expect(screen.getByRole('heading', { name: 'Configuración', level: 1 })).toBeInTheDocument();
    expect(screen.getByText('Cuenta')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Perfil/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Cuenta y seguridad/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Agencia/i })).toBeInTheDocument();
  });
});
