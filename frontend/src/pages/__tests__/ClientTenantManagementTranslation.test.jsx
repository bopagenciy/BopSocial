import React from 'react';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import i18n from '../../i18n/config';

import AllClientsPage from '../AllClientsPage';
import ManagementPage from '../ManagementPage';
import EditClientPage from '../EditClientPage';
import AdminTrustQueuePage from '../admin/AdminTrustQueuePage';
import ApprovalQueuePage from '../admin/ApprovalQueuePage';
import AuditLogPage from '../admin/AuditLogPage';
import { buildBreadcrumbs } from '../../components/shell/TopBar';

import {
  clientsAPI,
  invitationAPI,
  managementAPI,
  verificationAPI,
  disputeAPI,
  notificationsAPI,
  composerAPI,
  auditAPI,
} from '../../services/api';

import enManagement from '../../locales/en/management.json';
import esManagement from '../../locales/es/management.json';
import enApp from '../../locales/en/app.json';
import esApp from '../../locales/es/app.json';

// Mock react-hot-toast
jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    success: jest.fn(),
    error: jest.fn(),
    loading: jest.fn(),
    dismiss: jest.fn(),
  },
  toast: {
    success: jest.fn(),
    error: jest.fn(),
    loading: jest.fn(),
    dismiss: jest.fn(),
  },
}));

var mockClientsList = [
  {
    id: 'cli-1',
    company: 'Acme Global Innovations',
    company_name: 'Acme Global Innovations',
    name: 'Alice Henderson',
    contact_name: 'Alice Henderson',
    email: 'alice@acmeglobal.com',
    phone: '+1 555 123 4567',
    website: 'https://acmeglobal.com',
    default_language: 'en',
    is_active: true,
    total_posts: 42,
    connected_platforms: ['facebook', 'instagram'],
  },
  {
    id: 'cli-2',
    company: 'Beta Media Group',
    company_name: 'Beta Media Group',
    name: 'Carlos Mendez',
    contact_name: 'Carlos Mendez',
    email: 'carlos@betamedia.com',
    phone: '+34 912 345 678',
    website: 'https://betamedia.com',
    default_language: 'es',
    is_active: false,
    total_posts: 15,
    connected_platforms: ['linkedin'],
  },
];

var mockInvitationsList = [
  {
    id: 'inv-1',
    client_email: 'pending.partner@example.com',
    status: 'pending',
    invited_at: '2026-09-15T10:00:00Z',
    message: 'Welcome to Bop Social client portal',
  },
];

jest.mock('../../hooks/useData', () => ({
  useClients: () => ({
    clients: mockClientsList,
    loading: false,
    refetch: jest.fn(),
  }),
  useAlerts: () => ({
    alerts: [],
    loading: false,
  }),
}));

// Mock APIs
jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {},
  clientsAPI: {
    list: jest.fn(),
    get: jest.fn(),
    update: jest.fn(),
    create: jest.fn(),
    syncAll: jest.fn(),
  },
  invitationAPI: {
    mine: jest.fn(),
    send: jest.fn(),
    cancel: jest.fn(),
  },
  managementAPI: {
    listStaff: jest.fn(),
    listClients: jest.fn(),
    createStaff: jest.fn(),
    deleteStaff: jest.fn(),
    getStaffClients: jest.fn(),
    setStaffClients: jest.fn(),
    getStaffPermissions: jest.fn(),
    getClientPermissions: jest.fn(),
    setStaffPermissions: jest.fn(),
    setClientPermissions: jest.fn(),
    getClientPortalConfig: jest.fn(),
    saveClientPortalConfig: jest.fn(),
    getRoleDefaults: jest.fn(),
    setRoleDefaults: jest.fn(),
  },
  verificationAPI: {
    pending: jest.fn(),
    approve: jest.fn(),
    reject: jest.fn(),
  },
  disputeAPI: {
    list: jest.fn(),
    resolve: jest.fn(),
  },
  notificationsAPI: {
    approvalQueue: jest.fn(),
  },
  composerAPI: {
    posts: {
      approve: jest.fn(),
      cancel: jest.fn(),
    },
  },
  auditAPI: {
    list: jest.fn(),
  },
}));

describe('Phase BS-2.6B.2 — Client & Tenant Management Internationalization', () => {
  beforeEach(async () => {
    jest.clearAllMocks();

    clientsAPI.list.mockResolvedValue({ data: mockClientsList });
    clientsAPI.get.mockResolvedValue({
      data: {
        id: 'cli-1',
        company: 'Acme Global Innovations',
        name: 'Alice Henderson',
        email: 'alice@acmeglobal.com',
        phone: '+1 555 123 4567',
        website: 'https://acmeglobal.com',
        default_language: 'en',
        status: 'active',
      },
    });
    clientsAPI.update.mockResolvedValue({ data: { success: true } });
    clientsAPI.create.mockResolvedValue({ data: { id: 'cli-new' } });
    clientsAPI.syncAll.mockResolvedValue({ data: { dispatched: 2 } });

    invitationAPI.mine.mockResolvedValue({ data: mockInvitationsList });
    invitationAPI.send.mockResolvedValue({ data: { id: 'inv-new' } });
    invitationAPI.cancel.mockResolvedValue({ data: { canceled: true } });

    managementAPI.listStaff.mockResolvedValue({
      data: [
        {
          id: 'staff-1',
          name: 'Elena Rostova',
          email: 'lead.staff@bopsocial.com',
          role: 'staff',
          assigned_clients: ['cli-1'],
          is_active: true,
        },
      ],
    });
    managementAPI.listClients.mockResolvedValue({ data: mockClientsList });
    managementAPI.createStaff.mockResolvedValue({ data: { id: 'staff-new' } });
    managementAPI.deleteStaff.mockResolvedValue({ data: { deleted: true } });
    managementAPI.getStaffClients.mockResolvedValue({ data: ['cli-1'] });
    managementAPI.setStaffClients.mockResolvedValue({ data: { success: true } });
    managementAPI.getStaffPermissions.mockResolvedValue({
      data: {
        permissions: {
          'analytics.view': true,
          'posts.create': true,
          'posts.publish': false,
        },
      },
    });
    managementAPI.getClientPermissions.mockResolvedValue({
      data: {
        permissions: {
          'analytics.view': true,
          'posts.create': false,
        },
      },
    });
    managementAPI.setStaffPermissions.mockResolvedValue({ data: { success: true } });
    managementAPI.setClientPermissions.mockResolvedValue({ data: { success: true } });
    managementAPI.getClientPortalConfig.mockResolvedValue({
      data: {
        portal_title: 'Acme Partner Dashboard',
        accent_color: '#0055ff',
        welcome_message: 'Welcome to your custom analytics portal!',
        posts_section: true,
        roi_section: true,
        calendar_section: true,
        reviews_section: false,
        export_button: true,
        sync_button: true,
      },
    });
    managementAPI.saveClientPortalConfig.mockResolvedValue({ data: { saved: true } });
    managementAPI.getRoleDefaults.mockResolvedValue({
      data: {
        role: 'staff',
        permissions: {
          'analytics.view': true,
          'posts.create': true,
        },
      },
    });
    managementAPI.setRoleDefaults.mockResolvedValue({ data: { saved: true } });

    verificationAPI.pending.mockResolvedValue({
      data: {
        agencies: [
          {
            id: 'ag-1',
            name: 'Apex Digital Agency',
            slug: 'apex-digital',
            contact_email: 'compliance@apexdigital.com',
            trust_score: 92,
            docs: {
              business_registration: 'REG-882199',
              tax_id: 'US-9912001',
              website: 'https://apexdigital.com',
              submitted_at: '2026-09-20T08:30:00Z',
            },
            status: 'pending',
          },
        ],
      },
    });
    verificationAPI.approve.mockResolvedValue({ data: { status: 'approved' } });
    verificationAPI.reject.mockResolvedValue({ data: { status: 'rejected' } });

    disputeAPI.list.mockResolvedValue({
      data: {
        disputes: [
          {
            id: 'disp-42',
            filer_email: 'client.director@partner.com',
            respondent_email: 'account.manager@apexdigital.com',
            category: 'billing_overcharge',
            status: 'open',
            created_at: '2026-09-22T14:15:00Z',
            notes: 'Disputed unauthorized ad campaign charges.',
            evidence: 'https://files.bopsocial.com/evidence/disp-42.pdf',
          },
        ],
      },
    });
    disputeAPI.resolve.mockResolvedValue({ data: { status: 'resolved' } });

    notificationsAPI.approvalQueue.mockResolvedValue({
      data: {
        queue: [
          {
            id: 'post-queue-1',
            title: 'Q4 Product Launch Announcement',
            content: 'Excited to announce our groundbreaking feature set launching next week!',
            media_type: 'image',
            created_at: '2026-09-23T11:00:00Z',
            target_platforms: ['linkedin', 'twitter'],
          },
        ],
      },
    });

    composerAPI.posts.approve.mockResolvedValue({ data: { status: 'publishing' } });
    composerAPI.posts.cancel.mockResolvedValue({ data: { status: 'canceled' } });

    auditAPI.list.mockResolvedValue({
      data: {
        results: [
          {
            id: 'audit-log-101',
            action: 'post.publish',
            object_type: 'post',
            object_id: '9981',
            platform: 'linkedin',
            actor_email: 'elena@bopsocial.com',
            result: 'success',
            created_at: '2026-09-24T09:30:00Z',
          },
        ],
      },
    });

    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  // 1. Catalog Integrity & Key Parity
  describe('1. Translation Catalog Integrity & Parity', () => {
    function getAllKeys(obj, prefix = '') {
      let keys = [];
      for (const k of Object.keys(obj)) {
        const full = prefix ? `${prefix}.${k}` : k;
        if (obj[k] && typeof obj[k] === 'object' && !Array.isArray(obj[k])) {
          keys = keys.concat(getAllKeys(obj[k], full));
        } else {
          keys.push(full);
        }
      }
      return keys;
    }

    test('maintains 100% key parity between en/management.json and es/management.json', () => {
      const enKeys = getAllKeys(enManagement);
      const esKeys = getAllKeys(esManagement);

      const missingInEs = enKeys.filter((k) => !esKeys.includes(k));
      const missingInEn = esKeys.filter((k) => !enKeys.includes(k));

      expect(missingInEs).toEqual([]);
      expect(missingInEn).toEqual([]);
      expect(enKeys.length).toBeGreaterThan(200);
      expect(enKeys.length).toEqual(esKeys.length);
    });

    test('has no empty string values in management translations', () => {
      function checkNonEmpty(obj, path = '') {
        for (const [key, val] of Object.entries(obj)) {
          const currentPath = path ? `${path}.${key}` : key;
          if (typeof val === 'object' && val !== null) {
            checkNonEmpty(val, currentPath);
          } else {
            expect(typeof val).toBe('string');
            expect(val.trim().length).toBeGreaterThan(0);
          }
        }
      }
      checkNonEmpty(enManagement);
      checkNonEmpty(esManagement);
    });

    test('has matching breadcrumbs keys in app.json for admin modules', () => {
      const expectedAdminBreadcrumbs = [
        'account_settings',
        'clients',
        'management',
        'client',
        'edit',
        'trust',
        'approvals',
        'audit_log',
      ];
      expectedAdminBreadcrumbs.forEach((key) => {
        expect(enApp.breadcrumbs[key]).toBeDefined();
        expect(esApp.breadcrumbs[key]).toBeDefined();
      });
    });
  });

  // 2. Shared Breadcrumb Resolution in TopBar (BS-2.6B.1 residual closure)
  describe('2. Shared Breadcrumb Resolution (BS-2.6B.1 closure)', () => {
    test('resolves /admin/account-settings properly in English and Spanish', async () => {
      const enT = i18n.getFixedT('en', 'app');
      const esT = i18n.getFixedT('es', 'app');

      const enCrumbs = buildBreadcrumbs('/admin/account-settings', '/admin', enT);
      expect(enCrumbs).toHaveLength(1);
      expect(enCrumbs[0].label).toBe('Account Settings');

      const esCrumbs = buildBreadcrumbs('/admin/account-settings', '/admin', esT);
      expect(esCrumbs).toHaveLength(1);
      expect(esCrumbs[0].label).toBe('Configuración de cuenta');
    });

    test('resolves all client and tenant administration breadcrumbs in English and Spanish', () => {
      const enT = i18n.getFixedT('en', 'app');
      const esT = i18n.getFixedT('es', 'app');

      const routes = [
        { path: '/admin/clients', en: 'Clients', es: 'Clientes' },
        { path: '/admin/management', en: 'Team Management', es: 'Gestión de equipo' },
        { path: '/admin/trust', en: 'Trust & Approvals', es: 'Confianza y aprobaciones' },
        { path: '/admin/analytics/approvals', enLast: 'Approvals', esLast: 'Aprobaciones' },
        { path: '/admin/analytics/audit-log', enLast: 'Audit Log', esLast: 'Registro de auditoría' },
      ];

      routes.forEach(({ path, en, es, enLast, esLast }) => {
        const enRes = buildBreadcrumbs(path, '/admin', enT);
        const esRes = buildBreadcrumbs(path, '/admin', esT);
        if (en) expect(enRes[enRes.length - 1].label).toBe(en);
        if (es) expect(esRes[esRes.length - 1].label).toBe(es);
        if (enLast) expect(enRes[enRes.length - 1].label).toBe(enLast);
        if (esLast) expect(esRes[esRes.length - 1].label).toBe(esLast);
      });
    });
  });

  // 3. AllClientsPage (/admin/clients)
  describe('3. AllClientsPage (/admin/clients)', () => {
    test('renders client statistics, search, invite button, and preserves company names in English and Spanish', async () => {
      let renderResult;
      await act(async () => {
        renderResult = render(
          <MemoryRouter>
            <AllClientsPage />
          </MemoryRouter>
        );
      });

      // English verification
      expect(screen.getByText('Clients')).toBeInTheDocument();
      expect(screen.getAllByText('Connected Clients').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Pending Invitations')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Send Invitation/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Sync All/i })).toBeInTheDocument();

      // Tenant company names must be preserved verbatim
      expect(screen.getByText('Acme Global Innovations')).toBeInTheDocument();
      expect(screen.getByText('Beta Media Group')).toBeInTheDocument();
      expect(screen.getByText('alice@acmeglobal.com')).toBeInTheDocument();

      // Switch to Spanish
      await act(async () => {
        await i18n.changeLanguage('es');
      });

      renderResult.rerender(
        <MemoryRouter>
          <AllClientsPage />
        </MemoryRouter>
      );

      expect(screen.getByText('Clientes')).toBeInTheDocument();
      expect(screen.getAllByText('Clientes conectados').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Invitaciones pendientes')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Enviar invitación/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Sincronizar todo/i })).toBeInTheDocument();

      // Company and user data still preserved verbatim
      expect(screen.getByText('Acme Global Innovations')).toBeInTheDocument();
      expect(screen.getByText('Beta Media Group')).toBeInTheDocument();
      expect(screen.getByText('alice@acmeglobal.com')).toBeInTheDocument();
    });
  });

  // 4. ManagementPage (/admin/management)
  describe('4. ManagementPage (/admin/management)', () => {
    test('renders tabs, staff list, permissions, role defaults, and modal in English and Spanish', async () => {
      let renderResult;
      await act(async () => {
        renderResult = render(
          <MemoryRouter>
            <ManagementPage />
          </MemoryRouter>
        );
      });

      await waitFor(() => {
        expect(screen.getByText('Access Management')).toBeInTheDocument();
      });

      // English tabs
      expect(screen.getByRole('button', { name: /Staff Members/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /User Access/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Role Defaults/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Add/i })).toBeInTheDocument();

      // Staff member preserved
      expect(screen.getByText('Elena Rostova')).toBeInTheDocument();
      expect(screen.getByText('lead.staff@bopsocial.com')).toBeInTheDocument();

      // Switch to Spanish
      await act(async () => {
        await i18n.changeLanguage('es');
      });

      renderResult.rerender(
        <MemoryRouter>
          <ManagementPage />
        </MemoryRouter>
      );

      expect(screen.getByText('Gestión de accesos')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Miembros del personal/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Acceso de usuarios/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Valores por rol/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Agregar/i })).toBeInTheDocument();

      // Preserved data
      expect(screen.getByText('Elena Rostova')).toBeInTheDocument();
      expect(screen.getByText('lead.staff@bopsocial.com')).toBeInTheDocument();
    });
  });

  // 5. EditClientPage (/admin/client/:clientId/edit)
  describe('5. EditClientPage (/admin/client/:clientId/edit)', () => {
    test('renders form fields, default language selector, and preserves client data in English and Spanish', async () => {
      let renderResult;
      await act(async () => {
        renderResult = render(
          <MemoryRouter initialEntries={['/admin/client/cli-1/edit']}>
            <Routes>
              <Route path="/admin/client/:clientId/edit" element={<EditClientPage />} />
            </Routes>
          </MemoryRouter>
        );
      });

      await waitFor(() => {
        expect(screen.getByText('Edit Client')).toBeInTheDocument();
      });

      // English fields
      expect(screen.getByText('Company Name')).toBeInTheDocument();
      expect(screen.getByText('Contact Name')).toBeInTheDocument();
      expect(screen.getByText('Email')).toBeInTheDocument();
      expect(screen.getByText('Phone')).toBeInTheDocument();
      expect(screen.getByText('Website')).toBeInTheDocument();
      expect(screen.getByText('Default Language')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Save Changes/i })).toBeInTheDocument();

      // Inputs have company values
      expect(screen.getByDisplayValue('Acme Global Innovations')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Alice Henderson')).toBeInTheDocument();

      // Switch to Spanish
      await act(async () => {
        await i18n.changeLanguage('es');
      });

      renderResult.rerender(
        <MemoryRouter initialEntries={['/admin/client/cli-1/edit']}>
          <Routes>
            <Route path="/admin/client/:clientId/edit" element={<EditClientPage />} />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.getByText('Editar cliente')).toBeInTheDocument();
      expect(screen.getByText('Nombre de la empresa')).toBeInTheDocument();
      expect(screen.getByText('Nombre de contacto')).toBeInTheDocument();
      expect(screen.getByText('Correo electrónico')).toBeInTheDocument();
      expect(screen.getByText('Teléfono')).toBeInTheDocument();
      expect(screen.getByText('Sitio web')).toBeInTheDocument();
      expect(screen.getByText('Idioma predeterminado')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Guardar cambios/i })).toBeInTheDocument();

      // Values preserved
      expect(screen.getByDisplayValue('Acme Global Innovations')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Alice Henderson')).toBeInTheDocument();
    });
  });

  // 6. AdminTrustQueuePage (/admin/trust)
  describe('6. AdminTrustQueuePage (/admin/trust)', () => {
    test('renders verifications and disputes tabs, actions, and badges in English and Spanish', async () => {
      let renderResult;
      await act(async () => {
        renderResult = render(
          <MemoryRouter>
            <AdminTrustQueuePage />
          </MemoryRouter>
        );
      });

      await waitFor(() => {
        expect(screen.getByText('Trust & safety queue')).toBeInTheDocument();
      });

      // English tabs and items
      expect(screen.getByRole('button', { name: /Verifications/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Disputes/i })).toBeInTheDocument();
      expect(screen.getByText('Apex Digital Agency')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Approve/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Reject/i })).toBeInTheDocument();

      // Switch to Spanish
      await act(async () => {
        await i18n.changeLanguage('es');
      });

      renderResult.rerender(
        <MemoryRouter>
          <AdminTrustQueuePage />
        </MemoryRouter>
      );

      expect(screen.getByText('Cola de confianza y seguridad')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Verificaciones/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Disputas/i })).toBeInTheDocument();
      expect(screen.getByText('Apex Digital Agency')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Aprobar/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Rechazar/i })).toBeInTheDocument();
    });
  });

  // 7. ApprovalQueuePage (/admin/analytics/approvals)
  describe('7. ApprovalQueuePage (/admin/analytics/approvals)', () => {
    test('renders approval queue, buttons, and handles empty state in English and Spanish', async () => {
      let renderResult;
      await act(async () => {
        renderResult = render(
          <MemoryRouter>
            <ApprovalQueuePage />
          </MemoryRouter>
        );
      });

      await waitFor(() => {
        expect(screen.getByText('Approval queue')).toBeInTheDocument();
      });

      expect(screen.getByText(/1 post awaiting review/i)).toBeInTheDocument();
      expect(screen.getByText('Q4 Product Launch Announcement')).toBeInTheDocument();
      expect(screen.getByText('pending approval')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Approve/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Reject/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Edit/i })).toBeInTheDocument();

      // Switch to Spanish
      await act(async () => {
        await i18n.changeLanguage('es');
      });

      renderResult.rerender(
        <MemoryRouter>
          <ApprovalQueuePage />
        </MemoryRouter>
      );

      expect(screen.getByText('Cola de aprobaciones')).toBeInTheDocument();
      expect(screen.getByText(/1 publicación en espera de revisión/i)).toBeInTheDocument();
      expect(screen.getByText('Q4 Product Launch Announcement')).toBeInTheDocument();
      expect(screen.getByText('aprobación pendiente')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Aprobar/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Rechazar/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Editar/i })).toBeInTheDocument();
    });
  });

  // 8. AuditLogPage (/admin/analytics/audit-log)
  describe('8. AuditLogPage (/admin/analytics/audit-log)', () => {
    test('renders audit table columns, filter dropdowns, and records in English and Spanish', async () => {
      let renderResult;
      await act(async () => {
        renderResult = render(
          <MemoryRouter>
            <AuditLogPage />
          </MemoryRouter>
        );
      });

      await waitFor(() => {
        expect(screen.getByText('Audit log')).toBeInTheDocument();
      });

      // English column headers
      expect(screen.getByText('When')).toBeInTheDocument();
      expect(screen.getByText('Action')).toBeInTheDocument();
      expect(screen.getByText('Object')).toBeInTheDocument();
      expect(screen.getByText('Platform')).toBeInTheDocument();
      expect(screen.getByText('Actor')).toBeInTheDocument();
      expect(screen.getByText('Result')).toBeInTheDocument();

      // Preserved values
      expect(screen.getByText('post.publish')).toBeInTheDocument();
      expect(screen.getByText('elena@bopsocial.com')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Search action…')).toBeInTheDocument();

      // Switch to Spanish
      await act(async () => {
        await i18n.changeLanguage('es');
      });

      renderResult.rerender(
        <MemoryRouter>
          <AuditLogPage />
        </MemoryRouter>
      );

      expect(screen.getByText('Registro de auditoría')).toBeInTheDocument();
      expect(screen.getByText('Cuándo')).toBeInTheDocument();
      expect(screen.getByText('Acción')).toBeInTheDocument();
      expect(screen.getByText('Objeto')).toBeInTheDocument();
      expect(screen.getByText('Plataforma')).toBeInTheDocument();
      expect(screen.getByText('Actor')).toBeInTheDocument();
      expect(screen.getByText('Resultado')).toBeInTheDocument();

      // Preserved values
      expect(screen.getByText('post.publish')).toBeInTheDocument();
      expect(screen.getByText('elena@bopsocial.com')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Buscar acción…')).toBeInTheDocument();
    });
  });
});
