import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n from '../../../i18n/config';
import TopBar, { buildBreadcrumbs, humanize } from '../TopBar';

// Mock useAuth
jest.mock('../../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, name: 'Admin User', email: 'admin@bopsocial.com', role: 'superadmin' },
    logout: jest.fn(),
    can: () => true,
  }),
}));

// Mock useData
jest.mock('../../../hooks/useData', () => ({
  useClients: () => ({ clients: [] }),
  useLookups: () => ({ lookups: { platforms: [] } }),
  useAlerts: () => ({ alerts: [], unreadCount: 0, markRead: jest.fn(), markAllRead: jest.fn() }),
}));

// Mock appStore
jest.mock('../../../stores/appStore', () => ({
  useAppStore: () => ({
    activeModule: 'analytics',
    setActiveModule: jest.fn(),
    commandPaletteOpen: false,
    setCommandPaletteOpen: jest.fn(),
    mobileDrawerOpen: false,
    setMobileDrawerOpen: jest.fn(),
    activeClientId: null,
    setActiveClientId: jest.fn(),
  }),
  useBadgeCount: () => 0,
}));

describe('Phase BS-2.6B.2.1 — Account Settings Breadcrumb Visual Acceptance Closure', () => {
  beforeEach(async () => {
    localStorage.clear();
    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  describe('buildBreadcrumbs pure function resolution', () => {
    test('resolves /admin/account-settings properly in English and Spanish without falling back to humanize', async () => {
      const enT = i18n.getFixedT('en', 'app');
      const esT = i18n.getFixedT('es', 'app');

      const enCrumbs = buildBreadcrumbs('/admin/account-settings', '/admin', enT);
      expect(enCrumbs).toHaveLength(1);
      expect(enCrumbs[0].label).toBe('Account Settings');
      expect(enCrumbs[0].label).not.toBe(humanize('account-settings-untranslated'));

      const esCrumbs = buildBreadcrumbs('/admin/account-settings', '/admin', esT);
      expect(esCrumbs).toHaveLength(1);
      expect(esCrumbs[0].label).toBe('Configuración de cuenta');
      // Must NOT fall back to humanize("account-settings") -> "Account Settings"
      expect(esCrumbs[0].label).not.toBe('Account Settings');
      expect(esCrumbs[0].label).not.toBe(humanize('account-settings'));
    });

    test('resolves /dashboard/account-settings properly in English and Spanish', async () => {
      const enT = i18n.getFixedT('en', 'app');
      const esT = i18n.getFixedT('es', 'app');

      const enCrumbs = buildBreadcrumbs('/dashboard/account-settings', '/dashboard', enT);
      expect(enCrumbs).toHaveLength(1);
      expect(enCrumbs[0].label).toBe('Account Settings');

      const esCrumbs = buildBreadcrumbs('/dashboard/account-settings', '/dashboard', esT);
      expect(esCrumbs).toHaveLength(1);
      expect(esCrumbs[0].label).toBe('Configuración de cuenta');
      expect(esCrumbs[0].label).not.toBe('Account Settings');
    });

    test('handles trailing slashes, query parameters, and hashes defensively', () => {
      const esT = i18n.getFixedT('es', 'app');

      const crumbsWithQuery = buildBreadcrumbs('/admin/account-settings?tab=security#top', '/admin', esT);
      expect(crumbsWithQuery).toHaveLength(1);
      expect(crumbsWithQuery[0].label).toBe('Configuración de cuenta');

      const crumbsWithSlash = buildBreadcrumbs('/admin/account-settings/', '/admin', esT);
      expect(crumbsWithSlash).toHaveLength(1);
      expect(crumbsWithSlash[0].label).toBe('Configuración de cuenta');
    });

    test('handles missing or empty basePath defensively', () => {
      const esT = i18n.getFixedT('es', 'app');

      const crumbsNoBase = buildBreadcrumbs('/admin/account-settings', '', esT);
      expect(crumbsNoBase).toHaveLength(2);
      expect(crumbsNoBase[0].label).toBe('Administración');
      expect(crumbsNoBase[1].label).toBe('Configuración de cuenta');
    });
  });

  describe('TopBar component rendering at /admin/account-settings', () => {
    test('renders translated breadcrumb in English ("Account Settings")', async () => {
      await act(async () => {
        await i18n.changeLanguage('en');
      });

      render(
        <MemoryRouter initialEntries={['/admin/account-settings']}>
          <TopBar basePath="/admin" />
        </MemoryRouter>
      );

      const nav = screen.getByRole('navigation');
      expect(nav).toBeInTheDocument();
      expect(screen.getByText('Account Settings')).toBeInTheDocument();
    });

    test('renders translated breadcrumb in Spanish ("Configuración de cuenta") and never "Account Settings"', async () => {
      await act(async () => {
        await i18n.changeLanguage('es');
      });

      render(
        <MemoryRouter initialEntries={['/admin/account-settings']}>
          <TopBar basePath="/admin" />
        </MemoryRouter>
      );

      const nav = screen.getByRole('navigation');
      expect(nav).toBeInTheDocument();
      expect(screen.getByText('Configuración de cuenta')).toBeInTheDocument();
      expect(screen.queryByText('Account Settings')).toBeNull();
    });

    test('updates breadcrumb dynamically on language change without page reload', async () => {
      let renderResult;
      await act(async () => {
        await i18n.changeLanguage('en');
        renderResult = render(
          <MemoryRouter initialEntries={['/admin/account-settings']}>
            <TopBar basePath="/admin" />
          </MemoryRouter>
        );
      });

      expect(screen.getByText('Account Settings')).toBeInTheDocument();

      await act(async () => {
        await i18n.changeLanguage('es');
      });

      renderResult.rerender(
        <MemoryRouter initialEntries={['/admin/account-settings']}>
          <TopBar basePath="/admin" />
        </MemoryRouter>
      );

      expect(screen.getByText('Configuración de cuenta')).toBeInTheDocument();
      expect(screen.queryByText('Account Settings')).toBeNull();
    });
  });
});
