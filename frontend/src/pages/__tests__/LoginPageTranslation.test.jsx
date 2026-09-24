import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n, { changePlatformLanguage } from '../../i18n/config';
import LoginPage from '../LoginPage';
import PasswordStrength from '../../components/auth/PasswordStrength';

// Mock useAuth
jest.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    login: jest.fn(),
    loginMfa: jest.fn(),
    user: null,
    loading: false,
  }),
}));

describe('LoginPage & Auth Components Translation Closure (BS-2.1.1)', () => {
  beforeEach(async () => {
    localStorage.clear();
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
