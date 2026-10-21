import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n, { changePlatformLanguage } from '../../../i18n/config';
import ModuleRail from '../ModuleRail';
import TopBar from '../TopBar';
import FeatureSidebar from '../FeatureSidebar';

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
  useLookups: () => ({
    lookups: { platforms: [] },
  }),
  useAlerts: () => ({
    alerts: [],
    unreadCount: 0,
    markRead: jest.fn(),
    markAllRead: jest.fn(),
  }),
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

describe('AppShell & Shell Components Translation (BS-2.2)', () => {
  beforeEach(async () => {
    localStorage.clear();
    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  test('ModuleRail renders navigation and tooltips in English by default', () => {
    render(
      <MemoryRouter>
        <ModuleRail modules={[{ id: 'analytics', label: 'Analytics', icon: () => null }]} />
      </MemoryRouter>
    );

    expect(screen.getByRole('button', { name: /Bop Social home/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Notifications/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Settings/i })).toBeInTheDocument();
  });

  test('ModuleRail updates to Spanish when active language changes', async () => {
    await act(async () => {
      await changePlatformLanguage('es');
    });

    render(
      <MemoryRouter>
        <ModuleRail modules={[{ id: 'analytics', label: 'Analytics', icon: () => null }]} />
      </MemoryRouter>
    );

    expect(screen.getByRole('button', { name: /Inicio de Bop Social/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Notificaciones/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Configuración/i })).toBeInTheDocument();
  });

  test('TopBar includes LanguageSelector and localized search trigger', async () => {
    const { rerender } = render(
      <MemoryRouter>
        <TopBar module="analytics" basePath="/dashboard" />
      </MemoryRouter>
    );

    expect(screen.getByText(/Search anything/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /select language/i })).toBeInTheDocument();

    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <TopBar module="analytics" basePath="/dashboard" />
      </MemoryRouter>
    );

    expect(screen.getByText(/Buscar lo que sea…/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /seleccionar idioma/i })).toBeInTheDocument();
  });

  test('FeatureSidebar renders localized module titles and items', async () => {
    const { rerender } = render(
      <MemoryRouter>
        <FeatureSidebar module="analytics" basePath="/dashboard" />
      </MemoryRouter>
    );

    expect(screen.getAllByText('Analytics').length).toBeGreaterThan(0);
    expect(screen.getByText('Calendar')).toBeInTheDocument();

    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <FeatureSidebar module="analytics" basePath="/dashboard" />
      </MemoryRouter>
    );

    expect(screen.getAllByText('Analítica').length).toBeGreaterThan(0);
    expect(screen.getByText('Calendario')).toBeInTheDocument();
  });
});
