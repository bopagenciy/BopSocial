import React from 'react';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n, { changePlatformLanguage } from '../../i18n/config';

import SettingsPage from '../SettingsPage';
import ClientOnboardingPage from '../ClientOnboardingPage';
import CompetitorSection from '../../components/ui/CompetitorSection';

import { useAuth } from '../../hooks/useAuth';
import { useOAuthStatus, useLookups } from '../../hooks/useData';
import { clientsAPI } from '../../services/api';

import enOnboarding from '../../locales/en/onboarding.json';
import esOnboarding from '../../locales/es/onboarding.json';
import enApp from '../../locales/en/app.json';
import esApp from '../../locales/es/app.json';

// Mock dependencies
jest.mock('../../hooks/useAuth', () => ({
  useAuth: jest.fn(),
}));

jest.mock('../../hooks/useData', () => ({
  useOAuthStatus: jest.fn(),
  useLookups: jest.fn(),
}));

jest.mock('../../services/api', () => ({
  clientsAPI: {
    get: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
  },
}));

// Mock ConnectedAccounts
jest.mock('../../components/ui/ConnectedAccounts', () => {
  return function MockConnectedAccounts() {
    return <div data-testid="mock-connected-accounts">Connected Accounts Component</div>;
  };
});

describe('Phase BS-2.6B.3: Client Onboarding & Workspace Configuration i18n', () => {
  const mockClient = {
    id: 1,
    client_id: 1,
    name: 'Jane Doe',
    company: 'Acme Social Studio',
    email: 'contact@acmesocial.com',
    phone: '+1 555 123 4567',
    whatsapp_number: '+1 555 987 6543',
    website: 'https://acmesocial.com',
    gmb_url: 'https://g.page/acmesocial',
    default_language: 'es',
    business_category: 'Technology',
    business_subcategories: ['Software'],
    brand_description: 'We build great social tools.',
    usp: 'Fast and reliable social management.',
    brand_tone: 'professional',
    target_audience: 'Small and medium business owners.',
    gender: 'all',
    business_location: 'Austin, TX',
    target_locations: ['National', 'Local (Same City)'],
    competitors: [
      {
        name: 'Competitor X',
        social_links: {
          facebook: 'https://facebook.com/competitorx',
        },
      },
    ],
  };

  const mockUser = {
    id: 10,
    first_name: 'Jane',
    last_name: 'Doe',
    email: 'jane@example.com',
    client_id: 1,
    role: 'client',
  };

  beforeEach(() => {
    jest.clearAllMocks();
    window.scrollTo = jest.fn();

    useAuth.mockReturnValue({
      user: mockUser,
      refreshUser: jest.fn().mockResolvedValue(mockUser),
    });

    useOAuthStatus.mockReturnValue({
      status: {
        facebook: { status: 'active' },
      },
    });

    useLookups.mockReturnValue({
      lookups: {},
    });

    clientsAPI.get.mockResolvedValue({
      data: mockClient,
    });

    clientsAPI.update.mockResolvedValue({
      data: { ...mockClient },
    });
  });

  afterEach(async () => {
    await act(async () => {
      await changePlatformLanguage('en');
    });
  });

  // --------------------------------------------------------------------------
  // 1. Catalog Parity & Key Completeness
  // --------------------------------------------------------------------------
  describe('Catalog Parity and Configuration', () => {
    test('en/onboarding.json and es/onboarding.json have identical key structures', () => {
      const getDeepKeys = (obj, prefix = '') => {
        return Object.keys(obj).reduce((acc, key) => {
          const path = prefix ? `${prefix}.${key}` : key;
          if (typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
            acc.push(...getDeepKeys(obj[key], path));
          } else {
            acc.push(path);
          }
          return acc;
        }, []);
      };

      const enKeys = getDeepKeys(enOnboarding).sort();
      const esKeys = getDeepKeys(esOnboarding).sort();

      expect(esKeys).toEqual(enKeys);
    });

    test('app.json has onboarding breadcrumb translated in both languages', () => {
      expect(enApp.breadcrumbs.onboarding).toBe('Onboarding');
      expect(esApp.breadcrumbs.onboarding).toBe('Incorporación');
    });

    test('onboarding namespace is registered in i18n resources', () => {
      expect(i18n.hasResourceBundle('en', 'onboarding')).toBe(true);
      expect(i18n.hasResourceBundle('es', 'onboarding')).toBe(true);
    });
  });

  // --------------------------------------------------------------------------
  // 2. SettingsPage (Client Workspace Settings & Business Profile)
  // --------------------------------------------------------------------------
  describe('SettingsPage (Client Workspace Settings)', () => {
    test('renders in English with full localized copy and no missing translations', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      render(
        <MemoryRouter>
          <SettingsPage clientId="1" />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Settings')).toBeInTheDocument();
      });

      // Header and Hero
      expect(screen.getByText('Manage your account and business profile.')).toBeInTheDocument();
      expect(screen.getAllByText('Business Profile').length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText('Keep your settings aligned with onboarding')).toBeInTheDocument();
      expect(screen.getByText('Profile coverage')).toBeInTheDocument();
      expect(screen.getByText('Core profile areas completed')).toBeInTheDocument();

      // Switch to Business Profile tab to view sections
      fireEvent.click(screen.getAllByText('Business Profile')[1]);

      // Section titles
      expect(screen.getByText('Business Basics')).toBeInTheDocument();
      expect(screen.getByText('Brand Profile')).toBeInTheDocument();
      expect(screen.getByText('Target Audience')).toBeInTheDocument();
      expect(screen.getByText('Brand Assets')).toBeInTheDocument();

      // Save bar
      expect(screen.getByText('Changes here keep your settings aligned with onboarding.')).toBeInTheDocument();
      expect(screen.getByText('Save Changes')).toBeInTheDocument();
    });

    test('renders in Spanish with exact required acceptance terms (fixing browser defect)', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      render(
        <MemoryRouter>
          <SettingsPage clientId="1" />
        </MemoryRouter>
      );

      await waitFor(() => {
        // Main heading must say "Configuración" (not "Settings")
        expect(screen.getByText('Configuración')).toBeInTheDocument();
      });

      // Subtitle
      expect(screen.getByText('Administra tu cuenta y perfil empresarial.')).toBeInTheDocument();

      // Hero title & badge
      expect(screen.getByText('Mantén tu configuración alineada con el proceso de incorporación')).toBeInTheDocument();
      expect(screen.getAllByText('Perfil empresarial').length).toBeGreaterThanOrEqual(2);

      // Coverage
      expect(screen.getByText('Información del perfil')).toBeInTheDocument();
      expect(screen.getByText('Áreas principales del perfil completadas')).toBeInTheDocument();

      // Tabs
      expect(screen.getByText('Conectar cuentas')).toBeInTheDocument();

      // Switch to Perfil empresarial tab
      fireEvent.click(screen.getAllByText('Perfil empresarial')[1]);

      // Section titles
      expect(screen.getByText('Datos básicos del negocio')).toBeInTheDocument();
      expect(screen.getByText('Perfil de marca')).toBeInTheDocument();
      expect(screen.getByText('Público objetivo')).toBeInTheDocument();
      expect(screen.getByText('Recursos de marca')).toBeInTheDocument();

      // Field labels & placeholders
      expect(screen.getByText('Idioma del espacio de trabajo')).toBeInTheDocument();
      expect(screen.getByText('Nombre del negocio')).toBeInTheDocument();
      expect(screen.getByText('Categoría del negocio')).toBeInTheDocument();
      expect(screen.getByText('Tono de marca')).toBeInTheDocument();
      expect(screen.getByText('Descripción del público objetivo')).toBeInTheDocument();
      expect(screen.getByText('Ubicación del negocio')).toBeInTheDocument();
      expect(screen.getByText('Ubicaciones objetivo')).toBeInTheDocument();

      // Save bar
      expect(screen.getByText('Los cambios aquí mantienen tu configuración alineada con el proceso de incorporación.')).toBeInTheDocument();
      expect(screen.getByText('Guardar cambios')).toBeInTheDocument();
    });

    test('preserves canonical data and form state when switching language', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      const { rerender } = render(
        <MemoryRouter>
          <SettingsPage clientId="1" />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Settings')).toBeInTheDocument();
      });

      // Switch to profile tab in English
      fireEvent.click(screen.getAllByText('Business Profile')[1]);

      await waitFor(() => {
        expect(screen.getByDisplayValue('Acme Social Studio')).toBeInTheDocument();
      });

      // Switch language to Spanish
      await act(async () => {
        await changePlatformLanguage('es');
      });

      rerender(
        <MemoryRouter>
          <SettingsPage clientId="1" />
        </MemoryRouter>
      );

      // Switch to profile tab in Spanish
      fireEvent.click(screen.getAllByText('Perfil empresarial')[1]);

      // Company name and email inputs retain exact stored values
      expect(screen.getByDisplayValue('Acme Social Studio')).toBeInTheDocument();
      expect(screen.getByDisplayValue('contact@acmesocial.com')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Austin, TX')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // 3. ClientOnboardingPage
  // --------------------------------------------------------------------------
  describe('ClientOnboardingPage', () => {
    test('renders onboarding in English and verifies Bop Social branding replacement', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      render(
        <MemoryRouter>
          <ClientOnboardingPage />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Complete Your Profile')).toBeInTheDocument();
      });

      // Check Bop Social branding residual replacement!
      expect(screen.getByText('Set up your business profile to get the most out of Bop Social')).toBeInTheDocument();
      expect(screen.queryByText(/Social Stats/i)).not.toBeInTheDocument();

      // Hero & steps
      expect(screen.getByText('Onboarding Flow')).toBeInTheDocument();
      expect(screen.getByText('Build a dashboard that already feels tailored to your business')).toBeInTheDocument();
      expect(screen.getByText('Setup progress')).toBeInTheDocument();

      // Navigation buttons
      expect(screen.getByText('Skip for now')).toBeInTheDocument();
      expect(screen.getByText('Next')).toBeInTheDocument();
    });

    test('renders onboarding in Spanish with localized copy and steps', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      render(
        <MemoryRouter>
          <ClientOnboardingPage />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Completa tu perfil')).toBeInTheDocument();
      });

      // Localized subtitle with Bop Social
      expect(screen.getByText('Configura tu perfil empresarial para aprovechar al máximo Bop Social')).toBeInTheDocument();

      // Hero
      expect(screen.getByText('Flujo de incorporación')).toBeInTheDocument();
      expect(screen.getByText('Crea un panel que se sienta adaptado a tu negocio desde el primer día')).toBeInTheDocument();
      expect(screen.getByText('Progreso de configuración')).toBeInTheDocument();

      // Step 0 contents
      expect(screen.getByText('Dale a tu espacio de trabajo un punto de partida sólido')).toBeInTheDocument();
      expect(screen.getByText('Quién eres')).toBeInTheDocument();
      expect(screen.getByText('Dónde pueden encontrarte')).toBeInTheDocument();

      // Buttons
      expect(screen.getByText('Omitir por ahora')).toBeInTheDocument();
      expect(screen.getByText('Siguiente')).toBeInTheDocument();
    });

    test('triggers step validation and displays localized error message in Spanish', async () => {
      // Return empty company name to trigger validation
      clientsAPI.get.mockResolvedValueOnce({
        data: { ...mockClient, company: '' },
      });

      await act(async () => {
        await changePlatformLanguage('es');
      });

      render(
        <MemoryRouter>
          <ClientOnboardingPage />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Completa tu perfil')).toBeInTheDocument();
      });

      // Clear the company input
      const companyInput = screen.getByPlaceholderText('El nombre de tu empresa');
      fireEvent.change(companyInput, { target: { value: '' } });

      // Click Next
      const nextBtn = screen.getByText('Siguiente');
      fireEvent.click(nextBtn);

      await waitFor(() => {
        expect(screen.getByText('El nombre del negocio es obligatorio.')).toBeInTheDocument();
      });
    });
  });

  // --------------------------------------------------------------------------
  // 4. CompetitorSection (Shared Component)
  // --------------------------------------------------------------------------
  describe('CompetitorSection', () => {
    test('renders empty state in English and Spanish', async () => {
      // English
      await act(async () => {
        await changePlatformLanguage('en');
      });

      const { rerender } = render(
        <CompetitorSection
          competitors={[]}
          onAddCompetitor={jest.fn()}
        />
      );

      expect(screen.getByText('Competitive Snapshot')).toBeInTheDocument();
      expect(screen.getByText('Start with one competitor')).toBeInTheDocument();
      expect(screen.getByText('Add Competitor')).toBeInTheDocument();

      // Spanish
      await act(async () => {
        await changePlatformLanguage('es');
      });

      rerender(
        <CompetitorSection
          competitors={[]}
          onAddCompetitor={jest.fn()}
        />
      );

      expect(screen.getByText('Resumen competitivo')).toBeInTheDocument();
      expect(screen.getByText('Comienza con un competidor')).toBeInTheDocument();
      expect(screen.getByText('Añadir competidor')).toBeInTheDocument();
    });

    test('renders competitor rows and fields in Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      render(
        <CompetitorSection
          competitors={[
            {
              name: 'Competidor Alfa',
              social_links: [{ platform: 'facebook', url: 'https://facebook.com/alfa' }],
            },
          ]}
          onAddCompetitor={jest.fn()}
          onUpdateCompetitor={jest.fn()}
          onRemoveCompetitor={jest.fn()}
          onAddLink={jest.fn()}
          onUpdateLink={jest.fn()}
          onRemoveLink={jest.fn()}
        />
      );

      expect(screen.getByText('Perfil del competidor')).toBeInTheDocument();
      expect(screen.getByText('Nombre del competidor')).toBeInTheDocument();
      expect(screen.getByText('Eliminar competidor')).toBeInTheDocument();
      expect(screen.getByText('Enlaces sociales')).toBeInTheDocument();
      expect(screen.getByText('Añadir enlace')).toBeInTheDocument();
      expect(screen.getByText('Plataforma')).toBeInTheDocument();
      expect(screen.getByText('URL del perfil')).toBeInTheDocument();
    });
  });
});
