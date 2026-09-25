import React from 'react';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n, { changePlatformLanguage } from '../../i18n/config';

import MarketplacePage from '../marketplace/MarketplacePage';
import AgencyProfilePage from '../marketplace/AgencyProfilePage';
import PermissionMatrix from '../../components/marketplace/PermissionMatrix';
import PendingDashboard from '../PendingDashboard';
import EndUserShell from '../end-user/EndUserShell';
import ApprovalsPage from '../end-user/ApprovalsPage';
import ActivityLogPage from '../end-user/ActivityLogPage';
import NotificationPreferencesPage from '../end-user/NotificationPreferencesPage';

import { useAuth } from '../../hooks/useAuth';
import { marketplaceAPI, agencyRelationsAPI, approvalAPI, activityAPI, notificationPrefsAPI, authAPI } from '../../services/api';

import enAgencyPortal from '../../locales/en/agency_portal.json';
import esAgencyPortal from '../../locales/es/agency_portal.json';

// Helper for deep key extraction
function getDeepKeys(obj, prefix = '') {
  let keys = [];
  for (const key of Object.keys(obj)) {
    const fullPath = prefix ? `${prefix}.${key}` : key;
    if (obj[key] && typeof obj[key] === 'object' && !Array.isArray(obj[key])) {
      keys = keys.concat(getDeepKeys(obj[key], fullPath));
    } else {
      keys.push(fullPath);
    }
  }
  return keys.sort();
}

// Mock auth & API hooks
jest.mock('../../hooks/useAuth', () => ({
  useAuth: jest.fn(),
}));

jest.mock('../../services/api', () => ({
  marketplaceAPI: {
    list: jest.fn(),
    featured: jest.fn(),
    categories: jest.fn(),
    directory: jest.fn(),
    profile: jest.fn(),
    myProfile: jest.fn(),
    updateMyProfile: jest.fn(),
    reviews: jest.fn(),
    invite: jest.fn(),
    sendRequest: jest.fn(),
  },
  agencyRelationsAPI: {
    list: jest.fn(),
    detail: jest.fn(),
    pause: jest.fn(),
    resume: jest.fn(),
    terminate: jest.fn(),
    updatePermissions: jest.fn(),
  },
  approvalAPI: {
    pending: jest.fn(),
    history: jest.fn(),
    approve: jest.fn(),
    reject: jest.fn(),
  },
  activityAPI: {
    list: jest.fn(),
    flag: jest.fn(),
    revert: jest.fn(),
    exportCsvUrl: jest.fn(),
  },
  notificationPrefsAPI: {
    get: jest.fn(),
    update: jest.fn(),
  },
  authAPI: {
    me: jest.fn(),
    logout: jest.fn(),
  },
}));

describe('Phase BS-2.6D: Agency Marketplace & Client Portal Internationalization', () => {
  const mockUser = {
    id: 101,
    client_id: 50,
    first_name: 'Morgan',
    email: 'morgan@example.com',
    role: 'client_user',
    is_client_user: true,
  };

  beforeEach(() => {
    jest.clearAllMocks();

    useAuth.mockReturnValue({
      user: mockUser,
      logout: jest.fn(),
    });

    marketplaceAPI.list.mockResolvedValue({
      data: {
        agencies: [
          {
            id: 1,
            name: 'Apex Growth Marketing',
            slug: 'apex-growth',
            tagline: 'Scale your social media with precision',
            city: 'New York',
            country: 'US',
            avg_rating: 4.9,
            review_count: 28,
            services: ['content_creation', 'paid_ads'],
            is_verified: true,
          },
        ],
        count: 1,
      },
    });

    marketplaceAPI.categories.mockResolvedValue({
      data: {
        industries: [],
        services: [],
      },
    });

    marketplaceAPI.featured.mockResolvedValue({
      data: {
        agencies: [],
      },
    });

    marketplaceAPI.directory.mockResolvedValue({
      data: {
        agencies: [
          {
            id: 1,
            name: 'Apex Growth Marketing',
            slug: 'apex-growth',
            tagline: 'Scale your social media with precision',
            city: 'New York',
            country: 'US',
            avg_rating: 4.9,
            review_count: 28,
            services: ['content_creation', 'paid_ads'],
            is_verified: true,
          },
        ],
        filters: {
          services: ['content_creation', 'paid_ads'],
        },
      },
    });

    marketplaceAPI.profile.mockResolvedValue({
      data: {
        agency: {
          id: 1,
          name: 'Apex Growth Marketing',
          slug: 'apex-growth',
          tagline: 'Scale your social media with precision',
          bio: 'Top tier marketing team serving high growth brands.',
          city: 'New York',
          country: 'US',
          rating_avg: 4.9,
          review_count: 28,
          services: ['content_creation', 'paid_ads'],
          is_verified: true,
          case_studies: [],
          team_members: [],
        },
        reviews: [],
      },
    });

    approvalAPI.pending.mockResolvedValue({
      data: {
        rows: [
          {
            id: 'app-1',
            action_type: 'publish_post',
            status: 'pending',
            agency_name: 'Apex Growth Marketing',
            requested_by_name: 'Sarah Connor',
            preview: 'Exciting news coming soon!',
            payload: { content: 'Exciting news coming soon!' },
            expires_at: new Date(Date.now() + 86400000).toISOString(),
          },
        ],
      },
    });

    approvalAPI.history.mockResolvedValue({
      data: { rows: [] },
    });

    activityAPI.list.mockResolvedValue({
      data: {
        rows: [
          {
            id: 'act-1',
            actor_type: 'agency',
            actor_user_name: 'Sarah Connor',
            actor_agency_name: 'Apex Growth Marketing',
            severity: 'notice',
            description: 'Scheduled campaign for next week.',
            created_at: new Date().toISOString(),
            is_reversible: false,
            flagged_by_user: false,
          },
        ],
      },
    });

    notificationPrefsAPI.get.mockResolvedValue({
      data: {
        matrix: [
          {
            event_type: 'manage_request_received',
            label: 'Manage request received',
            channels: { in_app: true, email: true, whatsapp: false, browser: false },
          },
        ],
      },
    });
  });

  describe('Translation Catalog Parity & Integrity', () => {
    it('verifies 100% key symmetry between English and Spanish agency_portal catalogs', () => {
      const enKeys = getDeepKeys(enAgencyPortal);
      const esKeys = getDeepKeys(esAgencyPortal);

      const missingInEs = enKeys.filter((k) => !esKeys.includes(k));
      const missingInEn = esKeys.filter((k) => !enKeys.includes(k));

      expect(missingInEs).toEqual([]);
      expect(missingInEn).toEqual([]);
      expect(enKeys.length).toBe(esKeys.length);
      expect(enKeys.length).toBeGreaterThan(450);
    });

    it('verifies that no legacy Social Stats branding exists in agency_portal catalogs', () => {
      const enJsonStr = JSON.stringify(enAgencyPortal);
      const esJsonStr = JSON.stringify(esAgencyPortal);

      expect(enJsonStr).not.toContain('Social Stats');
      expect(esJsonStr).not.toContain('Social Stats');
    });
  });

  describe('MarketplacePage i18n & Language Switch', () => {
    it('renders marketplace directory in English and Spanish without missing keys', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      const { rerender } = render(
        <MemoryRouter>
          <MarketplacePage />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText(/Find an agency that fits your business/i)).toBeInTheDocument();
      });

      expect(screen.getByPlaceholderText(/Search agencies by name, industry, or location/i)).toBeInTheDocument();

      // Switch to Spanish
      await act(async () => {
        await changePlatformLanguage('es');
      });

      rerender(
        <MemoryRouter>
          <MarketplacePage />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText(/Encuentra una agencia que se adapte a tu negocio/i)).toBeInTheDocument();
      });

      expect(screen.getByPlaceholderText(/Buscar agencias por nombre, industria o ubicación/i)).toBeInTheDocument();
    });
  });

  describe('PendingDashboard Branding & Internationalization', () => {
    it('renders Bop Social onboarding choices in English and Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      const { rerender } = render(
        <MemoryRouter>
          <PendingDashboard />
        </MemoryRouter>
      );

      expect(screen.getByText(/Choose how you'd like to use Bop Social/i)).toBeInTheDocument();
      expect(screen.getByText(/Use Solo/i)).toBeInTheDocument();
      expect(screen.getByText(/Connect with an Agency/i)).toBeInTheDocument();

      // Switch to Spanish
      await act(async () => {
        await changePlatformLanguage('es');
      });

      rerender(
        <MemoryRouter>
          <PendingDashboard />
        </MemoryRouter>
      );

      expect(screen.getByText(/Elige cómo deseas usar Bop Social/i)).toBeInTheDocument();
      expect(screen.getByText(/Usar de forma individual/i)).toBeInTheDocument();
      expect(screen.getByText(/Conectar con una agencia/i)).toBeInTheDocument();
    });
  });

  describe('EndUserShell Navigation & Branding', () => {
    it('renders end-user navigation links in English and Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      const { rerender } = render(
        <MemoryRouter initialEntries={['/u']}>
          <EndUserShell />
        </MemoryRouter>
      );

      expect(screen.getByText(/Dashboard/i)).toBeInTheDocument();
      expect(screen.getByText(/My agency/i)).toBeInTheDocument();
      expect(screen.getByText(/Activity log/i)).toBeInTheDocument();
      expect(screen.getByText(/Approvals/i)).toBeInTheDocument();
      expect(screen.getByText(/Notifications/i)).toBeInTheDocument();

      // Switch to Spanish
      await act(async () => {
        await changePlatformLanguage('es');
      });

      rerender(
        <MemoryRouter initialEntries={['/u']}>
          <EndUserShell />
        </MemoryRouter>
      );

      expect(screen.getByText(/Panel/i)).toBeInTheDocument();
      expect(screen.getByText(/Mi agencia/i)).toBeInTheDocument();
      expect(screen.getByText(/Registro de actividad/i)).toBeInTheDocument();
      expect(screen.getByText(/Aprobaciones/i)).toBeInTheDocument();
      expect(screen.getByText(/Notificaciones/i)).toBeInTheDocument();
    });
  });

  describe('ApprovalsPage & ActivityLogPage Internationalization', () => {
    it('renders ApprovalsPage tabs and actions correctly in Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      render(
        <MemoryRouter>
          <ApprovalsPage />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Aprobaciones')).toBeInTheDocument();
      });

      expect(screen.getByText(/Acciones delicadas que tu agencia desea realizar/i)).toBeInTheDocument();
      expect(screen.getByText(/Pendientes/i)).toBeInTheDocument();
      expect(screen.getByText(/Historial/i)).toBeInTheDocument();
    });

    it('renders ActivityLogPage filters and summary correctly in Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      render(
        <MemoryRouter>
          <ActivityLogPage />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Registro de actividad')).toBeInTheDocument();
      });

      expect(screen.getByText(/Exportar CSV/i)).toBeInTheDocument();
      expect(screen.getByText(/Actualizar/i)).toBeInTheDocument();
      expect(screen.getByText(/Filtrar/i)).toBeInTheDocument();
      expect(screen.getByText(/Todos los actores/i)).toBeInTheDocument();
      expect(screen.getByText(/Solo marcadas/i)).toBeInTheDocument();
    });
  });

  describe('PermissionMatrix Internationalization', () => {
    const mockCatalog = {
      publish_posts: {
        label: 'Publish Posts',
        category: 'Content',
        risk: 'medium',
        default: true,
      },
    };

    it('renders category and permission rows in English and Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      const { rerender } = render(
        <PermissionMatrix
          catalog={mockCatalog}
          permissions={{ publish_posts: true }}
          requiresApprovalFor={['publish_posts']}
          onChange={jest.fn()}
        />
      );

      expect(screen.getByText('Content')).toBeInTheDocument();
      expect(screen.getByText('Publish Posts')).toBeInTheDocument();
      expect(screen.getByText('Ask me first')).toBeInTheDocument();
      expect(screen.getByText('Medium')).toBeInTheDocument();

      // Switch to Spanish
      await act(async () => {
        await changePlatformLanguage('es');
      });

      rerender(
        <PermissionMatrix
          catalog={mockCatalog}
          permissions={{ publish_posts: true }}
          requiresApprovalFor={['publish_posts']}
          onChange={jest.fn()}
        />
      );

      expect(screen.getByText('Contenido')).toBeInTheDocument();
      expect(screen.getByText('Publicar contenido')).toBeInTheDocument();
      expect(screen.getByText('Consultarme primero')).toBeInTheDocument();
      expect(screen.getByText('Medio')).toBeInTheDocument();
    });
  });
});

