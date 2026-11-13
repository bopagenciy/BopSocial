import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AgencyClientsPage from '../AgencyClientsPage';
import { agencyClientAPI } from '../../../services/api';

jest.mock('../../../services/api', () => ({
  agencyClientAPI: {
    create: jest.fn(),
    list: jest.fn(),
  },
}));

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

const mockRefetch = jest.fn();
const mockClients = [
  { id: 3, name: 'Bop Agencia', company: 'Bop Agencia' },
];

jest.mock('../../../hooks/useData', () => ({
  useClients: () => ({
    clients: mockClients,
    loading: false,
    refetch: mockRefetch,
  }),
}));

const mockSetCurrentClient = jest.fn();
jest.mock('../../../stores/appStore', () => ({
  useAppStore: () => mockSetCurrentClient,
  useCurrentClient: () => mockClients[0],
}));

describe('BS-8G: Agency-Scoped Client Creation Frontend', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('Form renders required and optional fields without exposing server-controlled internals', () => {
    render(
      <MemoryRouter>
        <AgencyClientsPage />
      </MemoryRouter>
    );

    // Open creation modal
    fireEvent.click(screen.getByTestId('add-client-button'));
    expect(screen.getByTestId('add-client-modal')).toBeInTheDocument();

    // Required fields
    expect(screen.getByLabelText(/Empresa \/ Marca \*/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Nombre del Workspace \/ Contacto \*/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email de contacto \*/i)).toBeInTheDocument();

    // Optional fields
    expect(screen.getByLabelText(/Sitio web/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Idioma predeterminado/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Moneda/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Zona horaria/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Industria \/ Categoría/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/País \/ Ubicación/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Requiere aprobación previa/i)).toBeInTheDocument();

    // Strict security check: server-controlled internals MUST NOT exist in inputs
    expect(document.querySelector('input[name="agency_id"]')).toBeNull();
    expect(document.querySelector('input[name="agency"]')).toBeNull();
    expect(document.querySelector('input[name="ownership_type"]')).toBeNull();
    expect(document.querySelector('input[name="created_via"]')).toBeNull();
    expect(document.querySelector('input[name="bop_organization_id"]')).toBeNull();
    expect(document.querySelector('input[name="status"]')).toBeNull();
  });

  test('Validates required fields client-side before calling API', async () => {
    render(
      <MemoryRouter>
        <AgencyClientsPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByTestId('add-client-button'));
    const submitBtn = screen.getByTestId('submit-create-client-btn');

    // Submit empty
    fireEvent.click(submitBtn);

    expect(agencyClientAPI.create).not.toHaveBeenCalled();
    expect(screen.getByText(/El nombre de la empresa es obligatorio/i)).toBeInTheDocument();
  });

  test('Successful client creation calls API, closes modal, and refreshes list', async () => {
    agencyClientAPI.create.mockResolvedValueOnce({
      status: 201,
      data: {
        client: {
          id: 42,
          company: 'Test Alpha Brands S.A.',
          name: 'Test Alpha Brands',
          email: 'test.alpha@bopagencia.test',
        },
        relation: {
          id: 15,
          agency_id: 2,
          client_id: 42,
          status: 'active',
        },
      },
    });

    render(
      <MemoryRouter>
        <AgencyClientsPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByTestId('add-client-button'));

    // Fill form
    fireEvent.change(screen.getByLabelText(/Empresa \/ Marca \*/i), {
      target: { value: 'Test Alpha Brands S.A.' },
    });
    fireEvent.change(screen.getByLabelText(/Nombre del Workspace \/ Contacto \*/i), {
      target: { value: 'Test Alpha Brands' },
    });
    fireEvent.change(screen.getByLabelText(/Email de contacto \*/i), {
      target: { value: 'test.alpha@bopagencia.test' },
    });
    fireEvent.click(screen.getByLabelText(/Requiere aprobación previa/i));

    fireEvent.click(screen.getByTestId('submit-create-client-btn'));

    await waitFor(() => {
      expect(agencyClientAPI.create).toHaveBeenCalledWith(
        expect.objectContaining({
          company: 'Test Alpha Brands S.A.',
          name: 'Test Alpha Brands',
          email: 'test.alpha@bopagencia.test',
          default_language: 'es',
          currency: 'USD',
          requires_approval: true,
        })
      );
    });

    // Modal closed
    await waitFor(() => {
      expect(screen.queryByTestId('add-client-modal')).not.toBeInTheDocument();
    });

    // Refetch called
    expect(mockRefetch).toHaveBeenCalled();

    // Success feedback displayed
    expect(screen.getByTestId('agency-client-feedback')).toHaveTextContent(
      'Cliente "Test Alpha Brands S.A." creado con éxito.'
    );
  });

  test('Displays API duplicate validation error when creation fails', async () => {
    agencyClientAPI.create.mockRejectedValueOnce({
      response: {
        status: 400,
        data: {
          error: 'A client workspace with this email already exists.',
          details: {
            email: ['A client with this email already exists.'],
          },
        },
      },
    });

    render(
      <MemoryRouter>
        <AgencyClientsPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByTestId('add-client-button'));

    fireEvent.change(screen.getByLabelText(/Empresa \/ Marca \*/i), {
      target: { value: 'Dup Brand' },
    });
    fireEvent.change(screen.getByLabelText(/Nombre del Workspace \/ Contacto \*/i), {
      target: { value: 'Dup Contact' },
    });
    fireEvent.change(screen.getByLabelText(/Email de contacto \*/i), {
      target: { value: 'dup@brand.local' },
    });

    fireEvent.click(screen.getByTestId('submit-create-client-btn'));

    await waitFor(() => {
      expect(screen.getByText(/A client with this email already exists/i)).toBeInTheDocument();
    });

    // Modal remains open on error
    expect(screen.getByTestId('add-client-modal')).toBeInTheDocument();
  });
});
