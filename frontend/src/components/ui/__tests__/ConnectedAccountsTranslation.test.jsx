import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import i18n from '../../../i18n/config';
import ConnectedAccounts from '../ConnectedAccounts';
import FacebookConnectModal from '../../FacebookConnectModal';
import { oauthAPI } from '../../../services/api';
import enConnections from '../../../locales/en/connections.json';
import esConnections from '../../../locales/es/connections.json';

// Mock oauthAPI to ensure provider API calls are strictly mocked
jest.mock('../../../services/api', () => ({
  oauthAPI: {
    googleUrl: jest.fn((clientId, p) => `https://mock.google.com/oauth/${clientId}/${p}`),
    linkedinUrl: jest.fn((clientId) => `https://mock.linkedin.com/oauth/${clientId}`),
    facebookUrl: jest.fn((clientId) => `https://mock.facebook.com/oauth/${clientId}`),
    disconnect: jest.fn().mockResolvedValue({ success: true }),
  },
}));

describe('Phase BS-2.6A — Social Connections Translation Suite', () => {
  const mockStatus = {
    facebook: {
      status: 'active',
      account_name: 'BopSocialPage',
      expires_at: '2026-12-31T23:59:59Z',
    },
    instagram: {
      status: 'active',
      account_name: 'bopsocial_ig',
      expires_at: '2026-12-31T23:59:59Z',
    },
    youtube: {
      status: 'expired',
      account_name: 'BopSocialChannel',
      expires_at: '2026-06-01T12:00:00Z',
    },
    google_my_business: {
      status: 'not_connected',
    },
    linkedin: {
      status: 'not_connected',
    },
  };

  beforeEach(async () => {
    jest.clearAllMocks();
    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  test('1. ConnectedAccounts renders in English', () => {
    render(<ConnectedAccounts clientId="client_123" status={mockStatus} onRefresh={jest.fn()} />);

    expect(screen.getByRole('heading', { level: 2, name: /connected accounts/i })).toBeInTheDocument();
    expect(screen.getByText(/connect your social media accounts to start syncing stats automatically/i)).toBeInTheDocument();
    expect(screen.getByText(/how it works:/i)).toBeInTheDocument();
    expect(screen.getByText(/facebook & instagram share one login/i)).toBeInTheDocument();
  });

  test('2. ConnectedAccounts renders in Spanish', async () => {
    await act(async () => {
      await i18n.changeLanguage('es');
    });

    render(<ConnectedAccounts clientId="client_123" status={mockStatus} onRefresh={jest.fn()} />);

    expect(screen.getByRole('heading', { level: 2, name: /cuentas conectadas/i })).toBeInTheDocument();
    expect(screen.getByText(/conecta tus cuentas de redes sociales para comenzar a sincronizar/i)).toBeInTheDocument();
    expect(screen.getByText(/cómo funciona:/i)).toBeInTheDocument();
    expect(screen.getByText(/facebook e instagram comparten un mismo inicio de sesión/i)).toBeInTheDocument();
  });

  test('3. Active status label translation (English and Spanish)', async () => {
    const { unmount } = render(<ConnectedAccounts clientId="client_123" status={mockStatus} onRefresh={jest.fn()} />);
    expect(screen.getAllByText(/● Active/i).length).toBeGreaterThan(0);
    unmount();

    await act(async () => {
      await i18n.changeLanguage('es');
    });

    render(<ConnectedAccounts clientId="client_123" status={mockStatus} onRefresh={jest.fn()} />);
    expect(screen.getAllByText(/● Activo/i).length).toBeGreaterThan(0);
  });

  test('4. Expired status label translation (English and Spanish)', async () => {
    const { unmount } = render(<ConnectedAccounts clientId="client_123" status={mockStatus} onRefresh={jest.fn()} />);
    expect(screen.getByText(/⚠ Expired/i)).toBeInTheDocument();
    unmount();

    await act(async () => {
      await i18n.changeLanguage('es');
    });

    render(<ConnectedAccounts clientId="client_123" status={mockStatus} onRefresh={jest.fn()} />);
    expect(screen.getByText(/⚠ Vencido/i)).toBeInTheDocument();
  });

  test('5. Not connected status label translation (English and Spanish)', async () => {
    const { unmount } = render(<ConnectedAccounts clientId="client_123" status={mockStatus} onRefresh={jest.fn()} />);
    expect(screen.getAllByText(/○ Not connected/i).length).toBeGreaterThan(0);
    unmount();

    await act(async () => {
      await i18n.changeLanguage('es');
    });

    render(<ConnectedAccounts clientId="client_123" status={mockStatus} onRefresh={jest.fn()} />);
    expect(screen.getAllByText(/○ No conectado/i).length).toBeGreaterThan(0);
  });

  test('6. Token expiration date formatting with locale support', async () => {
    const { unmount } = render(<ConnectedAccounts clientId="client_123" status={mockStatus} onRefresh={jest.fn()} />);
    expect(screen.getAllByText(/token expires:/i).length).toBeGreaterThan(0);
    unmount();

    await act(async () => {
      await i18n.changeLanguage('es');
    });

    render(<ConnectedAccounts clientId="client_123" status={mockStatus} onRefresh={jest.fn()} />);
    expect(screen.getAllByText(/el token vence:/i).length).toBeGreaterThan(0);
  });

  test('7. Human-readable permission descriptions and labels in FacebookConnectModal', async () => {
    render(<FacebookConnectModal open={true} onClose={jest.fn()} onContinue={jest.fn()} />);

    expect(screen.getByText('Access your Facebook Pages list')).toBeInTheDocument();
    expect(screen.getByText("We'll show the Pages you manage so you can choose which one to connect.")).toBeInTheDocument();
    expect(screen.getByText('Read Page engagement data')).toBeInTheDocument();
    expect(screen.getByText('Read Instagram insights')).toBeInTheDocument();
  });

  test('8. FacebookConnectModal English rendering', () => {
    render(<FacebookConnectModal open={true} onClose={jest.fn()} onContinue={jest.fn()} />);

    expect(screen.getByRole('heading', { level: 2, name: /connect your facebook & instagram/i })).toBeInTheDocument();
    expect(screen.getByText(/required permissions/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /continue with facebook login/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel and close dialog/i })).toBeInTheDocument();
    expect(screen.getByText(/by continuing, you agree to our/i)).toBeInTheDocument();
  });

  test('9. FacebookConnectModal Spanish rendering', async () => {
    await act(async () => {
      await i18n.changeLanguage('es');
    });

    render(<FacebookConnectModal open={true} onClose={jest.fn()} onContinue={jest.fn()} />);

    expect(screen.getByRole('heading', { level: 2, name: /conecta tu facebook e instagram/i })).toBeInTheDocument();
    expect(screen.getByText(/permisos requeridos/i)).toBeInTheDocument();
    expect(screen.getByText('Acceder a tu lista de Páginas de Facebook')).toBeInTheDocument();
    expect(screen.getByText(/mostraremos las páginas que administras/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /continuar con el inicio de sesión de facebook/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancelar y cerrar diálogo/i })).toBeInTheDocument();
    expect(screen.getByText(/al continuar, aceptas nuestros/i)).toBeInTheDocument();
  });

  test('10. Language switching without losing modal state or unchecking permissions', async () => {
    const { rerender } = render(<FacebookConnectModal open={true} onClose={jest.fn()} onContinue={jest.fn()} />);

    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes.length).toBe(3);
    checkboxes.forEach((cb) => expect(cb).toBeChecked());

    await act(async () => {
      await i18n.changeLanguage('es');
    });

    rerender(<FacebookConnectModal open={true} onClose={jest.fn()} onContinue={jest.fn()} />);

    const rerenderedBoxes = screen.getAllByRole('checkbox');
    expect(rerenderedBoxes.length).toBe(3);
    rerenderedBoxes.forEach((cb) => expect(cb).toBeChecked());
    expect(screen.getByRole('heading', { level: 2, name: /conecta tu facebook e instagram/i })).toBeInTheDocument();
  });

  test('11. OAuth technical scope values remain unchanged', () => {
    render(<FacebookConnectModal open={true} onClose={jest.fn()} onContinue={jest.fn()} />);

    // Machine-readable scopes must appear in <code> tags unmodified
    expect(screen.getByText('pages_show_list')).toBeInTheDocument();
    expect(screen.getByText('pages_read_engagement')).toBeInTheDocument();
    expect(screen.getByText('instagram_manage_insights')).toBeInTheDocument();
  });

  test('12. Disconnect confirmation remains active and uses translated prompt', async () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockImplementation(() => false);

    render(<ConnectedAccounts clientId="client_123" status={mockStatus} onRefresh={jest.fn()} />);

    const disconnectBtn = screen.getAllByRole('button', { name: /disconnect/i })[0];
    fireEvent.click(disconnectBtn);

    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('Disconnect Facebook? Sync will stop.'));
    expect(oauthAPI.disconnect).not.toHaveBeenCalled();

    confirmSpy.mockRestore();
  });

  test('13. User-visible Social Stats branding is removed and replaced by Bop Social', () => {
    const { container } = render(<ConnectedAccounts clientId="client_123" status={mockStatus} onRefresh={jest.fn()} />);

    // Ensure no user-visible "Social Stats" string is rendered
    expect(container.textContent).not.toContain('Social Stats');
    expect(screen.queryByText(/social stats/i)).not.toBeInTheDocument();
  });

  test('14. English/Spanish key parity across connections namespace', () => {
    const getKeys = (obj, prefix = '') => {
      let keys = new Set();
      for (const [k, v] of Object.entries(obj)) {
        const full = prefix ? `${prefix}.${k}` : k;
        if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
          keys = new Set([...keys, ...getKeys(v, full)]);
        } else {
          keys.add(full);
        }
      }
      return keys;
    };

    const enKeys = getKeys(enConnections);
    const esKeys = getKeys(esConnections);

    expect(enKeys).toEqual(esKeys);
    expect(enKeys.size).toBe(50);
  });

  test('15. Provider API calls are strictly mocked and continue handler receives scope', () => {
    const onContinueMock = jest.fn();
    render(<FacebookConnectModal open={true} onClose={jest.fn()} onContinue={onContinueMock} />);

    const continueBtn = screen.getByRole('button', { name: /continue with facebook login/i });
    fireEvent.click(continueBtn);

    expect(onContinueMock).toHaveBeenCalledTimes(1);
    expect(onContinueMock).toHaveBeenCalledWith(
      'pages_show_list,pages_read_engagement,instagram_manage_insights',
      expect.objectContaining({
        pages_show_list: true,
        pages_read_engagement: true,
        instagram_manage_insights: true,
      })
    );
  });
});
