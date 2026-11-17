import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AgencyClientsPage from '../AgencyClientsPage';
import { agencyClientAPI } from '../../../services/api';

jest.mock('../../../services/api', () => ({
  agencyClientAPI: {
    create: jest.fn(),
    list: jest.fn(),
    invite: jest.fn(),
    listInvitations: jest.fn(),
  },
}));

let mockUser = {
  id: 2,
  email: 'bopagencia@gmail.com',
  name: 'Bop Agencia',
  role: 'client',
  account_type: 'agency_member',
  agency_role: 'owner',
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
  { id: 21, name: 'Alpha Brands Workspace', company: 'Test Alpha Brands S.A.' },
];

jest.mock('../../../hooks/useData', () => ({
  useClients: () => ({
    clients: mockClients,
    loading: false,
    refetch: jest.fn(),
  }),
}));

jest.mock('../../../stores/appStore', () => ({
  useAppStore: () => jest.fn(),
  useCurrentClient: () => mockClients[0],
}));

describe('BS-8J.2: Agency Client User Invitation Frontend', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUser = {
      id: 2,
      email: 'bopagencia@gmail.com',
      name: 'Bop Agencia',
      role: 'client',
      account_type: 'agency_member',
      agency_role: 'owner',
      client_id: 3,
    };
  });

  test('1. Invite button visible to owner, admin, and manager', () => {
    // Owner
    mockUser.agency_role = 'owner';
    const { unmount } = render(
      <MemoryRouter>
        <AgencyClientsPage />
      </MemoryRouter>
    );
    expect(screen.getByTestId('invite-client-btn-21')).toBeInTheDocument();
    unmount();

    // Admin
    mockUser.agency_role = 'admin';
    const { unmount: unmountAdmin } = render(
      <MemoryRouter>
        <AgencyClientsPage />
      </MemoryRouter>
    );
    expect(screen.getByTestId('invite-client-btn-21')).toBeInTheDocument();
    unmountAdmin();

    // Manager
    mockUser.agency_role = 'manager';
    const { unmount: unmountMgr } = render(
      <MemoryRouter>
        <AgencyClientsPage />
      </MemoryRouter>
    );
    expect(screen.getByTestId('invite-client-btn-21')).toBeInTheDocument();
    unmountMgr();
  });

  test('2. Invite button hidden for unauthorized users (member or end_user)', () => {
    // Member
    mockUser.agency_role = 'member';
    const { unmount } = render(
      <MemoryRouter>
        <AgencyClientsPage />
      </MemoryRouter>
    );
    expect(screen.queryByTestId('invite-client-btn-21')).not.toBeInTheDocument();
    unmount();

    // End user
    mockUser.account_type = 'end_user';
    mockUser.agency_role = null;
    const { unmount: unmountEnd } = render(
      <MemoryRouter>
        <AgencyClientsPage />
      </MemoryRouter>
    );
    expect(screen.queryByTestId('invite-client-btn-21')).not.toBeInTheDocument();
    unmountEnd();
  });

  test('3. Role selector allows choosing client-scoped roles', () => {
    mockUser.agency_role = 'owner';
    render(
      <MemoryRouter>
        <AgencyClientsPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByTestId('invite-client-btn-21'));
    expect(screen.getByTestId('invite-user-modal')).toBeInTheDocument();

    const roleSelect = screen.getByTestId('invite-role-select');
    expect(roleSelect).toBeInTheDocument();

    // Test selection options
    fireEvent.change(roleSelect, { target: { value: 'client_admin' } });
    expect(roleSelect.value).toBe('client_admin');

    fireEvent.change(roleSelect, { target: { value: 'approver' } });
    expect(roleSelect.value).toBe('approver');

    fireEvent.change(roleSelect, { target: { value: 'editor' } });
    expect(roleSelect.value).toBe('editor');

    fireEvent.change(roleSelect, { target: { value: 'viewer' } });
    expect(roleSelect.value).toBe('viewer');
  });

  test('4. Valid submission calls API and creates pending invite state', async () => {
    agencyClientAPI.invite.mockResolvedValueOnce({
      data: {
        id: 101,
        token: 'mock-uuid-token-1234',
        client_id: 21,
        client_email: 'stakeholder@alphabrands.test',
        role: 'approver',
        status: 'pending',
      },
    });

    render(
      <MemoryRouter>
        <AgencyClientsPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByTestId('invite-client-btn-21'));

    fireEvent.change(screen.getByTestId('invite-email-input'), {
      target: { value: 'stakeholder@alphabrands.test' },
    });
    fireEvent.change(screen.getByTestId('invite-role-select'), {
      target: { value: 'approver' },
    });
    fireEvent.change(screen.getByTestId('invite-message-input'), {
      target: { value: 'Welcome to the team!' },
    });

    fireEvent.click(screen.getByTestId('submit-invite-btn'));

    await waitFor(() => {
      expect(agencyClientAPI.invite).toHaveBeenCalledWith(21, {
        email: 'stakeholder@alphabrands.test',
        role: 'approver',
        message: 'Welcome to the team!',
      });
    });

    // Modal closes
    await waitFor(() => {
      expect(screen.queryByTestId('invite-user-modal')).not.toBeInTheDocument();
    });

    // Pending invite rendered on card
    expect(screen.getByTestId('pending-invites-21')).toBeInTheDocument();
    expect(screen.getByText('stakeholder@alphabrands.test')).toBeInTheDocument();
    expect(screen.getByText('approver')).toBeInTheDocument();
  });

  test('5. Validation errors are handled cleanly', async () => {
    render(
      <MemoryRouter>
        <AgencyClientsPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByTestId('invite-client-btn-21'));

    // Submit with empty email
    fireEvent.click(screen.getByTestId('submit-invite-btn'));
    expect(screen.getByText(/El email es obligatorio/i)).toBeInTheDocument();
    expect(agencyClientAPI.invite).not.toHaveBeenCalled();

    // Submit with invalid email format
    fireEvent.change(screen.getByTestId('invite-email-input'), {
      target: { value: 'invalid-email-format' },
    });
    fireEvent.click(screen.getByTestId('submit-invite-btn'));
    expect(screen.getByText(/Ingresa un formato de email válido/i)).toBeInTheDocument();

    // API error response
    agencyClientAPI.invite.mockRejectedValueOnce({
      response: {
        data: {
          error: 'A pending invitation already exists for this email.',
        },
      },
    });

    fireEvent.change(screen.getByTestId('invite-email-input'), {
      target: { value: 'duplicate@alphabrands.test' },
    });
    fireEvent.click(screen.getByTestId('submit-invite-btn'));

    await waitFor(() => {
      expect(screen.getByText(/A pending invitation already exists for this email/i)).toBeInTheDocument();
    });
  });

  test('6. No plaintext secret or password rendered in UI', () => {
    render(
      <MemoryRouter>
        <AgencyClientsPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByTestId('invite-client-btn-21'));
    const modal = screen.getByTestId('invite-user-modal');

    // Ensure no password inputs or secrets in modal
    expect(modal.querySelector('input[type="password"]')).toBeNull();
    expect(modal.textContent).not.toMatch(/password|contraseña|hash|secret/i);
    // Ensure no internal DB tenant IDs like "ID: 21" or "Tenant #21" in modal header
    expect(screen.getByText(/Espacio: Test Alpha Brands S.A./i)).toBeInTheDocument();
    expect(modal.textContent).not.toMatch(/Tenant #/i);
  });
});
