import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ClientOnboardingPage from '../ClientOnboardingPage';
import { clientsAPI } from '../../services/api';

jest.mock('../../components/layout/PageHeader', () => () => <div data-testid="mock-header">Header</div>);
jest.mock('../../components/ui/CompetitorSection', () => () => <div data-testid="mock-competitors">Competitors</div>);
jest.mock('../../components/ui/ConnectedAccounts', () => {
  return function MockConnectedAccounts({ clientId }) {
    return <div data-testid="mock-connected-accounts" data-client-id={clientId}>ConnectedAccounts:{clientId}</div>;
  };
});

let mockUser = {
  id: 2,
  email: 'bopagencia@gmail.com',
  name: 'Bop Agencia',
  role: 'client',
  account_type: 'agency_member',
  client_id: 3,
};

jest.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: mockUser,
    refreshUser: jest.fn(),
    logout: jest.fn(),
  }),
}));

let mockCurrentClientId = 21;
jest.mock('../../stores/appStore', () => ({
  useCurrentClientId: () => mockCurrentClientId,
  useAppStore: () => jest.fn(),
}));

jest.mock('../../hooks/useData', () => ({
  useOAuthStatus: (cid) => ({ status: {}, refetch: jest.fn() }),
  useLookups: () => ({ lookups: {}, loading: false }),
}));

jest.mock('../../services/api', () => ({
  clientsAPI: {
    get: jest.fn(),
    update: jest.fn(),
    create: jest.fn(),
  },
  oauthAPI: {
    status: jest.fn().mockResolvedValue({ data: {} }),
  },
}));

describe('BS-8J.1: ClientOnboardingContext & Workspace Scoping', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    sessionStorage.clear();
    mockUser = {
      id: 2,
      email: 'bopagencia@gmail.com',
      name: 'Bop Agencia',
      role: 'client',
      account_type: 'agency_member',
      client_id: 3,
    };
    mockCurrentClientId = 21;

    clientsAPI.get.mockImplementation((id) => Promise.resolve({
      data: {
        id,
        name: id === 21 ? 'Alpha Admin' : 'Bop Admin',
        company: id === 21 ? 'Test Alpha Brands S.A.' : 'Bop Agencia',
        email: id === 21 ? 'testalpha@alphabrands.com' : 'bopagencia@gmail.com',
        website: 'https://example.com',
        competitors: [],
      },
    }));
    clientsAPI.update.mockResolvedValue({ data: { success: true } });
  });

  test('1. Agency owner on Client #21 reads Client #21 data', async () => {
    mockCurrentClientId = 21;
    render(
      <MemoryRouter>
        <ClientOnboardingPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(clientsAPI.get).toHaveBeenCalledWith(21);
    });

    const companyInput = screen.getByPlaceholderText(/Your company name/i);
    await waitFor(() => {
      expect(companyInput.value).toBe('Test Alpha Brands S.A.');
    });
  });

  test('2. Agency owner on Client #21 writes to Client #21', async () => {
    mockCurrentClientId = 21;
    render(
      <MemoryRouter>
        <ClientOnboardingPage />
      </MemoryRouter>
    );

    const companyInput = screen.getByPlaceholderText(/Your company name/i);
    await waitFor(() => {
      expect(companyInput.value).toBe('Test Alpha Brands S.A.');
    });

    const nextBtn = screen.getByRole('button', { name: /^Next$/i });
    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(clientsAPI.update).toHaveBeenCalledWith(21, expect.any(FormData));
    });
  });

  test('3. Client #3 remains unchanged when editing Client #21', async () => {
    mockCurrentClientId = 21;
    render(
      <MemoryRouter>
        <ClientOnboardingPage />
      </MemoryRouter>
    );

    const companyInput = screen.getByPlaceholderText(/Your company name/i);
    await waitFor(() => {
      expect(companyInput.value).toBe('Test Alpha Brands S.A.');
    });

    const nextBtn = screen.getByRole('button', { name: /^Next$/i });
    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(clientsAPI.update).toHaveBeenCalledWith(21, expect.any(FormData));
      expect(clientsAPI.update).not.toHaveBeenCalledWith(3, expect.any(FormData));
    });
  });

  test('4. Switching back targets Client #3', async () => {
    mockCurrentClientId = 3;
    render(
      <MemoryRouter>
        <ClientOnboardingPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(clientsAPI.get).toHaveBeenCalledWith(3);
    });

    const companyInput = screen.getByPlaceholderText(/Your company name/i);
    await waitFor(() => {
      expect(companyInput.value).toBe('Bop Agencia');
    });

    const nextBtn = screen.getByRole('button', { name: /^Next$/i });
    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(clientsAPI.update).toHaveBeenCalledWith(3, expect.any(FormData));
    });
  });

  test('5. Direct end-user still targets own client regardless of store', async () => {
    mockUser = {
      id: 99,
      email: 'enduser@external.local',
      name: 'External User',
      role: 'client',
      account_type: 'end_user',
      client_id: 42,
    };
    mockCurrentClientId = 21; // foreign store value should be ignored for end_user

    render(
      <MemoryRouter>
        <ClientOnboardingPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(clientsAPI.get).toHaveBeenCalledWith(42);
    });
  });

  test('6. OAuth component receives selected client ID for OAuth URL construction', async () => {
    mockCurrentClientId = 21;
    sessionStorage.setItem('onboarding_step_21', '5'); // Step 6 (index 5): connect accounts

    render(
      <MemoryRouter>
        <ClientOnboardingPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      const connectedAccounts = screen.getByTestId('mock-connected-accounts');
      expect(connectedAccounts).toBeInTheDocument();
      expect(connectedAccounts.getAttribute('data-client-id')).toBe('21');
    });
  });

  test('7. Prop clientId takes precedence over store or user client ID', async () => {
    mockCurrentClientId = 3;
    render(
      <MemoryRouter>
        <ClientOnboardingPage clientId={21} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(clientsAPI.get).toHaveBeenCalledWith(21);
    });
  });
});
