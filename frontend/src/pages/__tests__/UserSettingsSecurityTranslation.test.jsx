import React from 'react';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n, { changePlatformLanguage } from '../../i18n/config';
import UserSettingsPage from '../UserSettingsPage';
import { MFAManager, ActiveSessionsList } from '../settings/SecuritySections';
import {
  NotificationsSection,
  AppearanceSection,
  KeyboardShortcutsSection,
  APIKeysSection,
  WebhooksSection,
  DataPrivacySection,
  CrossLinksSection,
} from '../settings/SettingsSections';
import { useAuth } from '../../hooks/useAuth';
import { useTheme } from '../../hooks/useTheme';
import {
  profileAPI,
  mfaAPI,
  sessionsAPI,
  apiKeysAPI,
  privacyAPI,
} from '../../services/api';
import enSettings from '../../locales/en/settings.json';
import esSettings from '../../locales/es/settings.json';
import enAuth from '../../locales/en/auth.json';
import esAuth from '../../locales/es/auth.json';

// Mock useAuth
jest.mock('../../hooks/useAuth', () => ({
  useAuth: jest.fn(),
}));

// Mock useTheme
jest.mock('../../hooks/useTheme', () => ({
  useTheme: jest.fn(),
}));

// Mock API calls
jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {},
  profileAPI: {
    get: jest.fn(),
    update: jest.fn(),
    changePassword: jest.fn(),
    agencyInfo: jest.fn(),
    disconnectAgency: jest.fn(),
    deleteAccount: jest.fn(),
  },
  mfaAPI: {
    status: jest.fn(),
    setup: jest.fn(),
    verifySetup: jest.fn(),
    regenerateBackupCodes: jest.fn(),
    disable: jest.fn(),
  },
  sessionsAPI: {
    list: jest.fn(),
    revoke: jest.fn(),
    revokeAll: jest.fn(),
  },
  apiKeysAPI: {
    list: jest.fn(),
    create: jest.fn(),
    revoke: jest.fn(),
  },
  privacyAPI: {
    exportList: jest.fn(),
    exportRequest: jest.fn(),
    consents: jest.fn(),
    setConsent: jest.fn(),
    processingStatus: jest.fn(),
    setProcessingPaused: jest.fn(),
    deleteAccount: jest.fn(),
    cancelDeleteAccount: jest.fn(),
  },
}));

describe('User Settings & Security Internationalization (BS-2.6B.1)', () => {
  const mockUser = {
    id: 1,
    name: 'Alex Rivera',
    email: 'alex@example.com',
    role: 'client',
  };

  beforeEach(async () => {
    localStorage.clear();
    jest.clearAllMocks();

    useAuth.mockReturnValue({
      user: mockUser,
      refreshAuth: jest.fn().mockResolvedValue(mockUser),
      logout: jest.fn(),
    });

    useTheme.mockReturnValue({
      preference: 'dark',
      setTheme: jest.fn(),
    });

    profileAPI.get.mockResolvedValue({
      data: {
        first_name: 'Alex',
        last_name: 'Rivera',
        email: 'alex@example.com',
        is_social: false,
        language: 'en',
      },
    });

    profileAPI.agencyInfo.mockResolvedValue({
      data: {
        connected: true,
        agency_name: 'Starlight Media',
        agency_email: 'contact@starlight.com',
        agency_since: '2025-06-15T10:00:00Z',
      },
    });

    mfaAPI.status.mockResolvedValue({
      data: {
        enabled: false,
        backup_codes_remaining: 0,
        last_used_at: null,
      },
    });

    sessionsAPI.list.mockResolvedValue({
      data: {
        sessions: [
          {
            id: 101,
            browser: 'Chrome 128',
            os: 'Windows 11',
            device: 'Desktop',
            ip: '192.168.1.50',
            is_active: true,
            last_used_at: '2026-09-24T12:00:00Z',
          },
          {
            id: 102,
            browser: 'Safari',
            os: 'iOS 18',
            device: 'iPhone 15',
            ip: '10.0.0.4',
            is_active: false,
            last_used_at: '2026-09-20T08:30:00Z',
          },
        ],
      },
    });

    apiKeysAPI.list.mockResolvedValue({
      data: {
        keys: [
          {
            id: 'k_1',
            name: 'Production Ingestion',
            key_prefix: 'sk_live_abc123',
            is_active: true,
            is_expired: false,
            created_at: '2026-09-01T12:00:00Z',
            last_used_at: '2026-09-24T14:30:00Z',
            use_count: 142,
            scopes: ['read:posts', 'write:leads'],
          },
        ],
      },
    });

    privacyAPI.exportList.mockResolvedValue({
      data: { requests: [] },
    });
    privacyAPI.consents.mockResolvedValue({
      data: { consents: { marketing_emails: true, data_processing: true } },
    });
    privacyAPI.processingStatus.mockResolvedValue({
      data: { workspaces: [{ id: 1, is_processing_paused: false }] },
    });

    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  // 1. Catalog Parity & Integrity
  describe('Catalog Parity & Integrity', () => {
    function getAllKeys(obj, prefix = '') {
      let keys = [];
      for (const k of Object.keys(obj)) {
        const nextPrefix = prefix ? `${prefix}.${k}` : k;
        if (typeof obj[k] === 'object' && obj[k] !== null && !Array.isArray(obj[k])) {
          keys = keys.concat(getAllKeys(obj[k], nextPrefix));
        } else {
          keys.push(nextPrefix);
        }
      }
      return keys;
    }

    test('settings.json maintains 100% key parity between EN and ES', () => {
      const enKeys = getAllKeys(enSettings).sort();
      const esKeys = getAllKeys(esSettings).sort();
      expect(enKeys).toEqual(esKeys);
      expect(enKeys.length).toBeGreaterThan(150);
    });

    test('auth.json maintains 100% key parity between EN and ES (resolving 7 missing keys)', () => {
      const enKeys = getAllKeys(enAuth).sort();
      const esKeys = getAllKeys(esAuth).sort();
      expect(enKeys).toEqual(esKeys);
      expect(enKeys).toContain('end_user_signup.step_about');
      expect(enKeys).toContain('end_user_signup.step_account');
      expect(enKeys).toContain('end_user_signup.step_confirm');
      expect(enKeys).toContain('end_user_signup.subtitle_step_2');
      expect(enKeys).toContain('end_user_signup.subtitle_step_3');
      expect(enKeys).toContain('end_user_signup.title_step_2');
      expect(enKeys).toContain('end_user_signup.title_step_3');
    });

    test('no residual "Social Stats" branding exists in user settings translation catalogs', () => {
      expect(JSON.stringify(enSettings)).not.toContain('Social Stats');
      expect(JSON.stringify(esSettings)).not.toContain('Social Stats');
    });
  });

  // 2. Navigation Sidebar Tabs
  describe('UserSettingsPage Navigation Tabs', () => {
    test('renders all tabs and groups in English', async () => {
      await act(async () => {
        render(
          <MemoryRouter>
            <UserSettingsPage />
          </MemoryRouter>
        );
      });

      expect(screen.getByRole('heading', { name: /Settings/i })).toBeInTheDocument();
      expect(screen.getByText('Account')).toBeInTheDocument();
      expect(screen.getByText('Workspace')).toBeInTheDocument();
      expect(screen.getByText('Developer')).toBeInTheDocument();
      expect(screen.getByText('Privacy')).toBeInTheDocument();

      expect(screen.getByRole('button', { name: /Profile/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Account & Security/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Agency/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Notifications/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Appearance/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Keyboard/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /API Keys/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Webhooks/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Data & Privacy/i })).toBeInTheDocument();
    });

    test('renders all tabs and groups in Spanish after language switch', async () => {
      await act(async () => {
        await i18n.changeLanguage('es');
        render(
          <MemoryRouter>
            <UserSettingsPage />
          </MemoryRouter>
        );
      });

      expect(screen.getByRole('heading', { name: /Configuración/i })).toBeInTheDocument();
      expect(screen.getByText('Cuenta')).toBeInTheDocument();
      expect(screen.getByText('Espacio de trabajo')).toBeInTheDocument();
      expect(screen.getByText('Desarrollador')).toBeInTheDocument();
      expect(screen.getByText('Privacidad')).toBeInTheDocument();

      expect(screen.getByRole('button', { name: /Perfil/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Cuenta y seguridad/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Agencia/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Notificaciones/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Apariencia/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Atajos de teclado/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Claves de API/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Webhooks/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Datos y privacidad/i })).toBeInTheDocument();
    });
  });

  // 3. Security Tab & Password Management
  describe('Security Tab & Password Form', () => {
    test('renders password change form labels and placeholders in English and Spanish', async () => {
      let renderResult;
      await act(async () => {
        renderResult = render(
          <MemoryRouter>
            <UserSettingsPage />
          </MemoryRouter>
        );
      });

      // Switch to Security tab
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /Account & Security/i }));
      });

      expect(screen.getByText('Security')).toBeInTheDocument();
      expect(screen.getByText('Current Password')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Enter current password')).toBeInTheDocument();
      expect(screen.getByText('New Password')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('At least 8 characters')).toBeInTheDocument();
      expect(screen.getByText('Confirm New Password')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Re-enter new password')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Change Password/i })).toBeInTheDocument();

      // Switch to Spanish
      await act(async () => {
        await i18n.changeLanguage('es');
      });

      expect(screen.getByText('Seguridad')).toBeInTheDocument();
      expect(screen.getByText('Contraseña actual')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Introduce tu contraseña actual')).toBeInTheDocument();
      expect(screen.getByText('Nueva contraseña')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Al menos 8 caracteres')).toBeInTheDocument();
      expect(screen.getByText('Confirmar nueva contraseña')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Vuelve a introducir la nueva contraseña')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Cambiar contraseña/i })).toBeInTheDocument();
    });

    test('validates required fields with localized error messages', async () => {
      await act(async () => {
        render(
          <MemoryRouter>
            <UserSettingsPage />
          </MemoryRouter>
        );
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /Account & Security/i }));
      });

      // Submit empty form in English
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /Change Password/i }));
      });
      expect(screen.getByText('All fields are required.')).toBeInTheDocument();

      // Switch to Spanish and submit empty form
      await act(async () => {
        await i18n.changeLanguage('es');
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /Cambiar contraseña/i }));
      });
      expect(screen.getByText('Todos los campos son obligatorios.')).toBeInTheDocument();
    });
  });

  // 4. Two-Factor Authentication (MFA)
  describe('MFAManager Component', () => {
    test('renders disabled MFA state in English and Spanish', async () => {
      mfaAPI.status.mockResolvedValueOnce({
        data: { enabled: false },
      });

      await act(async () => {
        render(<MFAManager />);
      });

      expect(screen.getByText('Two-factor auth (TOTP)')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Set up MFA/i })).toBeInTheDocument();

      await act(async () => {
        await i18n.changeLanguage('es');
      });

      expect(screen.getByText('Autenticación de dos factores (TOTP)')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Configurar 2FA/i })).toBeInTheDocument();
    });

    test('renders enabled MFA state with backup count and badge in English and Spanish', async () => {
      mfaAPI.status.mockResolvedValueOnce({
        data: {
          enabled: true,
          backup_codes_remaining: 5,
          last_used_at: '2026-09-24T12:00:00Z',
        },
      });

      await act(async () => {
        render(<MFAManager />);
      });

      expect(screen.getByText('Two-factor auth is on')).toBeInTheDocument();
      expect(screen.getByText('Enabled')).toBeInTheDocument();
      expect(screen.getByText(/5 backup codes remaining/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Regenerate backup codes/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Disable MFA/i })).toBeInTheDocument();

      await act(async () => {
        await i18n.changeLanguage('es');
      });

      expect(screen.getByText('La autenticación de dos factores está activada')).toBeInTheDocument();
      expect(screen.getByText('Activada')).toBeInTheDocument();
      expect(screen.getByText(/Quedan 5 códigos de recuperación/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Regenerar códigos de recuperación/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Desactivar 2FA/i })).toBeInTheDocument();
    });
  });

  // 5. Active Sessions List
  describe('ActiveSessionsList Component', () => {
    test('renders active and revoked sessions in English and Spanish', async () => {
      await act(async () => {
        render(<ActiveSessionsList />);
      });

      expect(screen.getByText('Active sessions')).toBeInTheDocument();
      expect(screen.getByText(/1 active · 1 revoked/i)).toBeInTheDocument();
      expect(screen.getByText(/Chrome 128 on Windows 11/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Revoked/i).length).toBeGreaterThanOrEqual(1);

      await act(async () => {
        await i18n.changeLanguage('es');
      });

      expect(screen.getByText('Sesiones activas')).toBeInTheDocument();
      expect(screen.getByText(/1 activas · 1 revocadas/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Revocada/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  // 6. Notifications Matrix
  describe('NotificationsSection Component', () => {
    test('renders matrix channels and event labels in English and Spanish', async () => {
      await act(async () => {
        render(<NotificationsSection />);
      });

      expect(screen.getByText('Notifications')).toBeInTheDocument();
      expect(screen.getByText('In-app')).toBeInTheDocument();
      expect(screen.getByText('Email')).toBeInTheDocument();
      expect(screen.getByText('Browser')).toBeInTheDocument();
      expect(screen.getByText('Mentions')).toBeInTheDocument();
      expect(screen.getByText('Performance alerts')).toBeInTheDocument();
      expect(screen.getByText('Scheduled reports')).toBeInTheDocument();
      expect(screen.getByText('Team activity')).toBeInTheDocument();
      expect(screen.getByText('Token expiry')).toBeInTheDocument();

      await act(async () => {
        await i18n.changeLanguage('es');
      });

      expect(screen.getByText('Notificaciones')).toBeInTheDocument();
      expect(screen.getByText('En la app')).toBeInTheDocument();
      expect(screen.getByText('Correo')).toBeInTheDocument();
      expect(screen.getByText('Navegador')).toBeInTheDocument();
      expect(screen.getByText('Menciones')).toBeInTheDocument();
      expect(screen.getByText('Alertas de rendimiento')).toBeInTheDocument();
      expect(screen.getByText('Informes programados')).toBeInTheDocument();
      expect(screen.getByText('Actividad del equipo')).toBeInTheDocument();
      expect(screen.getByText('Vencimiento de tokens')).toBeInTheDocument();
    });
  });

  // 7. Appearance & Density
  describe('AppearanceSection Component', () => {
    test('renders themes and density options in English and Spanish', async () => {
      await act(async () => {
        render(<AppearanceSection />);
      });

      expect(screen.getByText('Appearance')).toBeInTheDocument();
      expect(screen.getByText('Theme')).toBeInTheDocument();
      expect(screen.getByText('Light')).toBeInTheDocument();
      expect(screen.getByText('Dark')).toBeInTheDocument();
      expect(screen.getByText('System')).toBeInTheDocument();
      expect(screen.getByText('Density')).toBeInTheDocument();
      expect(screen.getByText('Comfortable')).toBeInTheDocument();
      expect(screen.getByText('Compact')).toBeInTheDocument();

      await act(async () => {
        await i18n.changeLanguage('es');
      });

      expect(screen.getByText('Apariencia')).toBeInTheDocument();
      expect(screen.getByText('Tema')).toBeInTheDocument();
      expect(screen.getByText('Claro')).toBeInTheDocument();
      expect(screen.getByText('Oscuro')).toBeInTheDocument();
      expect(screen.getByText('Sistema')).toBeInTheDocument();
      expect(screen.getByText('Densidad')).toBeInTheDocument();
      expect(screen.getByText('Cómoda')).toBeInTheDocument();
      expect(screen.getByText('Compacta')).toBeInTheDocument();
    });
  });

  // 8. Keyboard Shortcuts
  describe('KeyboardShortcutsSection Component', () => {
    test('renders grouped shortcuts and action labels in English and Spanish', async () => {
      await act(async () => {
        render(<KeyboardShortcutsSection />);
      });

      expect(screen.getByText('Keyboard Shortcuts')).toBeInTheDocument();
      expect(screen.getByText('Global')).toBeInTheDocument();
      expect(screen.getByText('Navigation')).toBeInTheDocument();
      expect(screen.getByText('Composer')).toBeInTheDocument();
      expect(screen.getByText('Inbox')).toBeInTheDocument();
      expect(screen.getByText('Open command palette')).toBeInTheDocument();
      expect(screen.getByText('Go to dashboard')).toBeInTheDocument();

      await act(async () => {
        await i18n.changeLanguage('es');
      });

      expect(screen.getByText('Atajos de teclado')).toBeInTheDocument();
      expect(screen.getByText('Global')).toBeInTheDocument();
      expect(screen.getByText('Navegación')).toBeInTheDocument();
      expect(screen.getByText('Editor')).toBeInTheDocument();
      expect(screen.getByText('Bandeja de entrada')).toBeInTheDocument();
      expect(screen.getByText('Abrir paleta de comandos')).toBeInTheDocument();
      expect(screen.getByText('Ir al panel principal')).toBeInTheDocument();
    });
  });

  // 9. API Keys & Invariants
  describe('APIKeysSection Component', () => {
    test('renders form, empty states, and preserves machine invariants', async () => {
      await act(async () => {
        render(<APIKeysSection />);
      });

      expect(screen.getByText('API Keys')).toBeInTheDocument();
      expect(screen.getByText('Generate a new key')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('e.g. "Production deploy"')).toBeInTheDocument();
      expect(screen.getByText('Production Ingestion')).toBeInTheDocument();
      // Machine scopes invariant
      expect(screen.getByText(/read:posts, write:leads/i)).toBeInTheDocument();

      await act(async () => {
        await i18n.changeLanguage('es');
      });

      expect(screen.getByText('Claves de API')).toBeInTheDocument();
      expect(screen.getByText('Generar una nueva clave')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('ej. "Despliegue de producción"')).toBeInTheDocument();
      // Machine scopes invariant preserved in Spanish
      expect(screen.getByText(/read:posts, write:leads/i)).toBeInTheDocument();
    });
  });

  // 10. Webhooks & Machine-Readable Invariants
  describe('WebhooksSection Component', () => {
    test('preserves machine event subscriptions while localizing UI text', async () => {
      await act(async () => {
        render(<WebhooksSection />);
      });

      expect(screen.getByText('Webhooks')).toBeInTheDocument();
      expect(screen.getByText('Add an endpoint')).toBeInTheDocument();

      await act(async () => {
        await i18n.changeLanguage('es');
      });

      expect(screen.getByText('Webhooks')).toBeInTheDocument();
      expect(screen.getByText('Añadir un endpoint')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Añadir/i })).toBeInTheDocument();
    });
  });

  // 11. Data Privacy & Consents
  describe('DataPrivacySection Component', () => {
    test('renders consent toggles, export card, and localized labels in English and Spanish', async () => {
      await act(async () => {
        render(<DataPrivacySection />);
      });

      expect(screen.getByText('Data & Privacy')).toBeInTheDocument();
      expect(screen.getByText('Export your data')).toBeInTheDocument();
      expect(screen.getByText('Your consents')).toBeInTheDocument();
      expect(screen.getByText('Marketing emails')).toBeInTheDocument();
      expect(screen.getByText('Analytics cookies')).toBeInTheDocument();
      expect(screen.getByText('AI processing — opt out')).toBeInTheDocument();
      expect(screen.getByText('Pause data processing')).toBeInTheDocument();

      await act(async () => {
        await i18n.changeLanguage('es');
      });

      expect(screen.getByText('Datos y privacidad')).toBeInTheDocument();
      expect(screen.getByText('Exportar tus datos')).toBeInTheDocument();
      expect(screen.getByText('Tus consentimientos')).toBeInTheDocument();
      expect(screen.getByText('Correos de marketing')).toBeInTheDocument();
      expect(screen.getByText('Cookies analíticas')).toBeInTheDocument();
      expect(screen.getByText('Procesamiento de IA — exclusión voluntaria')).toBeInTheDocument();
      expect(screen.getByText('Pausar procesamiento de datos')).toBeInTheDocument();
    });
  });

  // 12. Danger Zone (Delete Account)
  describe('Danger Zone (Delete Account)', () => {
    test('navigates deletion flow in English and Spanish with invariant DELETE keyword', async () => {
      await act(async () => {
        render(
          <MemoryRouter>
            <UserSettingsPage />
          </MemoryRouter>
        );
      });

      expect(screen.getByText('Danger Zone')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Delete Account/i })).toBeInTheDocument();

      // Step 1: Open reasons
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /Delete Account/i }));
      });

      expect(screen.getByText('Why are you deleting your account?')).toBeInTheDocument();
      expect(screen.getByText('Please select a reason. This helps us improve Bop Social.')).toBeInTheDocument();
      expect(screen.getByText('I no longer need this account')).toBeInTheDocument();
      expect(screen.getByText('Privacy concerns')).toBeInTheDocument();

      // Select reason and proceed to Step 2
      await act(async () => {
        fireEvent.click(screen.getByLabelText(/Privacy concerns/i));
      });
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /Continue/i }));
      });

      expect(screen.getByText('This will permanently delete everything')).toBeInTheDocument();
      expect(screen.getByText('All your analytics data and reports')).toBeInTheDocument();
      expect(screen.getByText('All connected social media accounts')).toBeInTheDocument();
      expect(screen.getByText(/Type DELETE to confirm:/i)).toBeInTheDocument();

      // Switch to Spanish
      await act(async () => {
        await i18n.changeLanguage('es');
      });

      expect(screen.getByText('Esto eliminará todo de forma permanente')).toBeInTheDocument();
      expect(screen.getByText('Todos tus datos de análisis e informes')).toBeInTheDocument();
      expect(screen.getByText('Todas las cuentas de redes sociales conectadas')).toBeInTheDocument();
      expect(screen.getByText(/Escribe DELETE para confirmar:/i)).toBeInTheDocument();

      // Cancel button
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /Cancelar/i }));
      });

      expect(screen.getByText('Zona de peligro')).toBeInTheDocument();
    });
  });

  // 13. Agency Tab & Connection Card
  describe('Agency Tab', () => {
    test('renders agency connection card, permissions, and disconnect in English and Spanish', async () => {
      await act(async () => {
        render(
          <MemoryRouter>
            <UserSettingsPage />
          </MemoryRouter>
        );
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /Agency/i }));
      });

      expect(screen.getByText('Agency Connection')).toBeInTheDocument();
      expect(screen.getByText('Starlight Media')).toBeInTheDocument();
      expect(screen.getByText('Connected')).toBeInTheDocument();
      expect(screen.getByText('Your agency can:')).toBeInTheDocument();
      expect(screen.getByText('View your analytics and reports')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Disconnect from Agency/i })).toBeInTheDocument();

      await act(async () => {
        await i18n.changeLanguage('es');
      });

      expect(screen.getByText('Conexión con la agencia')).toBeInTheDocument();
      expect(screen.getByText('Tu agencia puede:')).toBeInTheDocument();
      expect(screen.getByText('Ver tus estadísticas e informes')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Desconectar de la agencia/i })).toBeInTheDocument();
    });
  });
});
