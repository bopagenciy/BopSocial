import React from 'react';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n, { changePlatformLanguage } from '../../i18n/config';
import LoginPage from '../LoginPage';
import PasswordStrength from '../../components/auth/PasswordStrength';

const mockLogin = jest.fn();
const mockLoginMfa = jest.fn();

// Mock useAuth
jest.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    login: mockLogin,
    loginMfa: mockLoginMfa,
    user: null,
    loading: false,
  }),
}));

describe('LoginPage & Auth Components Translation Closure (BS-2.1.1 & BS-3C.3A)', () => {
  beforeEach(async () => {
    localStorage.clear();
    mockLogin.mockReset();
    mockLoginMfa.mockReset();
    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  test('renders English login page and demo notices by default', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByText('Welcome back')).toBeInTheDocument();
    expect(screen.getByText(/or continue with/i)).toBeInTheDocument();
    expect(screen.getByText(/local only/i)).toBeInTheDocument();
    expect(screen.getByText('Superadmin')).toBeInTheDocument();
    expect(screen.getByText('Agency')).toBeInTheDocument();
    expect(screen.getByText('End user')).toBeInTheDocument();
    expect(screen.getByText('Marketing OS')).toBeInTheDocument();

    // Terms notice in English
    expect(screen.getByText(/I agree to the/i)).toBeInTheDocument();
    expect(screen.getByText('Terms of Service')).toBeInTheDocument();
    expect(screen.getByText('Privacy Policy')).toBeInTheDocument();
  });

  test('renders Spanish login page and demo notices when Spanish is active', async () => {
    await act(async () => {
      await changePlatformLanguage('es');
    });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByText('Bienvenido de nuevo')).toBeInTheDocument();
    expect(screen.getByText(/o continuar con/i)).toBeInTheDocument();
    expect(screen.getByText(/solo local/i)).toBeInTheDocument();
    expect(screen.getByText('Superadministrador')).toBeInTheDocument();
    expect(screen.getByText('Agencia')).toBeInTheDocument();
    expect(screen.getByText('Usuario final')).toBeInTheDocument();
    expect(screen.getByText('Sistema Operativo de Marketing')).toBeInTheDocument();

    // Terms notice in Spanish
    expect(screen.getByText(/Acepto los/i)).toBeInTheDocument();
    expect(screen.getByText('Términos de Servicio')).toBeInTheDocument();
    expect(screen.getByText(/y la/i)).toBeInTheDocument();
    expect(screen.getByText('Política de Privacidad')).toBeInTheDocument();
  });

  test('enforces terms acceptance checkbox before login submission', async () => {
    mockLogin.mockResolvedValueOnce({ id: 1, role: 'agency' });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    const submitButton = screen.getByRole('button', { name: /Sign in/i });
    const checkbox = screen.getByRole('checkbox');

    // Initially unchecked and button is disabled
    expect(checkbox).not.toBeChecked();
    expect(submitButton).toBeDisabled();

    // Check the terms acceptance checkbox
    await act(async () => {
      fireEvent.click(checkbox);
    });

    expect(checkbox).toBeChecked();
    expect(submitButton).not.toBeDisabled();

    // Fill in email and password
    const emailInput = screen.getByPlaceholderText(/you@agency.com/i);
    const passwordInput = screen.getByPlaceholderText(/Enter your password/i);

    fireEvent.change(emailInput, { target: { value: 'pilot.operator@bopagencia.local' } });
    fireEvent.change(passwordInput, { target: { value: 'SecretPassword123!' } });

    // Submit form
    await act(async () => {
      fireEvent.click(submitButton);
    });

    expect(mockLogin).toHaveBeenCalledWith('pilot.operator@bopagencia.local', 'SecretPassword123!', true);
  });

  test('renders PasswordStrength meter in Spanish correctly', async () => {
    await act(async () => {
      await changePlatformLanguage('es');
    });

    render(<PasswordStrength password="MyStrongPassword123!" show={true} />);

    expect(screen.getByText(/Seguridad de la contraseña:/i)).toBeInTheDocument();
    expect(screen.getByText(/Fuerte/i)).toBeInTheDocument();
  });
});

