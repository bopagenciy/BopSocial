import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import FeatureSidebar from '../FeatureSidebar';
import AgencyClientsPage from '../../../pages/agency/AgencyClientsPage';

// Track auth user in mock
let mockUser = {
  id: 2,
  email: 'bopagencia@gmail.com',
  name: 'Bop Agencia',
  role: 'client',
  account_type: 'agency_member',
  client_id: 3,
};

jest.mock('../../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: mockUser,
    logout: jest.fn(),
    can: () => true,
  }),
}));

const mockClients = [
  { id: 3, name: 'Bop Agencia', company: 'Bop Agencia' },
  { id: 10, name: 'Beta Corp', company: 'Beta Corp' },
];

jest.mock('../../../hooks/useData', () => ({
  useClients: () => ({
    clients: mockClients,
    loading: false,
    refetch: jest.fn(),
  }),
}));

let mockCurrentClient = mockClients[0];
const mockSetCurrentClient = jest.fn((c) => { mockCurrentClient = c; });

jest.mock('../../../stores/appStore', () => ({
  useAppStore: (selector) => {
    const state = {
      setCurrentClient: mockSetCurrentClient,
      currentClient: mockCurrentClient,
      currentClientId: mockCurrentClient?.id ?? null,
      badgeCounts: {},
    };
    return typeof selector === 'function' ? selector(state) : state;
  },
  useCurrentClient: () => mockCurrentClient,
  useCurrentClientId: () => mockCurrentClient?.id ?? null,
  useBadgeCount: () => 0,
}));

describe('BS-8F: Agency Owner Multi-Client Access & Shell Validation', () => {
  beforeEach(() => {
    mockUser = {
      id: 2,
      email: 'bopagencia@gmail.com',
      name: 'Bop Agencia',
      role: 'client',
      account_type: 'agency_member',
      client_id: 3,
    };
    mockCurrentClient = mockClients[0];
    mockSetCurrentClient.mockClear();
  });

  test('Agency member sees ClientSwitcher and Clientes navigation in sidebar', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard/analytics']}>
        <FeatureSidebar module="analytics" basePath="/dashboard" isAdmin={false} />
      </MemoryRouter>
    );

    // Switcher button is rendered
    const switcherBtn = screen.getByTestId('client-switcher-button');
    expect(switcherBtn).toBeInTheDocument();
    expect(switcherBtn).toHaveTextContent('Bop Agencia');

    // Clientes navigation is visible in Agencia section
    const clientesNav = screen.getByRole('link', { name: /clientes/i });
    expect(clientesNav).toBeInTheDocument();
    expect(clientesNav).toHaveAttribute('href', '/agency/clients');
  });

  test('Client switcher lists only own agency clients and excludes All Clients', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard/analytics']}>
        <FeatureSidebar module="analytics" basePath="/dashboard" isAdmin={false} />
      </MemoryRouter>
    );

    const switcherBtn = screen.getByTestId('client-switcher-button');
    fireEvent.click(switcherBtn);

    // Dropdown is open
    const dropdown = screen.getByTestId('client-switcher-dropdown');
    expect(dropdown).toBeInTheDocument();

    // Verify own clients are present
    expect(screen.getByRole('option', { name: 'Bop Agencia' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Beta Corp' })).toBeInTheDocument();

    // Verify "All clients" / "Todos los clientes" is NOT shown for agency members
    expect(screen.queryByRole('option', { name: /all clients/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /todos los clientes/i })).not.toBeInTheDocument();
  });

  test('Selecting client in switcher calls setCurrentClient', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard/analytics']}>
        <FeatureSidebar module="analytics" basePath="/dashboard" isAdmin={false} />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByTestId('client-switcher-button'));
    fireEvent.click(screen.getByRole('option', { name: 'Beta Corp' }));

    expect(mockSetCurrentClient).toHaveBeenCalledWith(mockClients[1]);
  });

  test('AgencyClientsPage lists managed clients and triggers add client modal', () => {
    render(
      <MemoryRouter initialEntries={['/agency/clients']}>
        <AgencyClientsPage />
      </MemoryRouter>
    );

    // Header and client cards
    expect(screen.getByRole('heading', { name: /clientes/i })).toBeInTheDocument();
    expect(screen.getByTestId('client-card-3')).toHaveTextContent('Bop Agencia');
    expect(screen.getByTestId('client-card-10')).toHaveTextContent('Beta Corp');

    // Add client trigger
    const addBtn = screen.getByTestId('add-client-button');
    expect(addBtn).toBeInTheDocument();

    // Click trigger opens modal placeholder
    fireEvent.click(addBtn);
    expect(screen.getByTestId('add-client-modal')).toBeInTheDocument();
    expect(screen.getByText(/Añadir nuevo cliente/i)).toBeInTheDocument();
  });

  test('End user (non-agency) does NOT see ClientSwitcher', () => {
    mockUser = {
      id: 5,
      email: 'user@test.local',
      role: 'client',
      account_type: 'end_user',
      client_id: 99,
    };

    render(
      <MemoryRouter initialEntries={['/dashboard/analytics']}>
        <FeatureSidebar module="analytics" basePath="/dashboard" isAdmin={false} />
      </MemoryRouter>
    );

    expect(screen.queryByTestId('client-switcher-button')).not.toBeInTheDocument();
  });
});
