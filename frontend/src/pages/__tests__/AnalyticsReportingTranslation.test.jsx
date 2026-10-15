import React from 'react';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n, { changePlatformLanguage } from '../../i18n/config';
import AnalyticsPage from '../AnalyticsPage';
import ReportsPage from '../ReportsPage';
import ShareReportModal from '../../components/ui/ShareReportModal';
import * as useDataModule from '../../hooks/useData';
import { overviewAPI, clientsAPI, sharedReportsAPI, roiAPI } from '../../services/api';

// Mock API modules
jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {},
  overviewAPI: {
    get: jest.fn(),
  },
  clientsAPI: {
    summary: jest.fn(),
    timeseries: jest.fn(),
  },
  sharedReportsAPI: {
    list: jest.fn(),
    create: jest.fn(),
    delete: jest.fn(),
  },
  roiAPI: {
    getReports: jest.fn(),
  },
}));

// Mock useData hooks
jest.mock('../../hooks/useData', () => ({
  useClients: jest.fn(),
  useDateRange: jest.fn(),
  useLookups: jest.fn(),
}));

// Mock recharts ResponsiveContainer to render children reliably in JSDOM
jest.mock('recharts', () => {
  const OriginalRecharts = jest.requireActual('recharts');
  return {
    ...OriginalRecharts,
    ResponsiveContainer: ({ children }) => (
      <div className="recharts-responsive-container" style={{ width: 800, height: 400 }}>
        {children}
      </div>
    ),
  };
});

describe('PHASE BS-2.3: Analytics & Reporting Internationalization', () => {
  const mockClients = [
    {
      id: 1,
      company: 'Acme Corp',
      email: 'contact@acme.test',
      is_active: true,
      created_at: '2026-01-15T10:00:00Z',
      website: 'https://acme.test',
    },
    {
      id: 2,
      company: 'Stark Industries',
      email: 'tony@stark.test',
      is_active: false,
      created_at: '2026-02-20T12:00:00Z',
      website: 'https://stark.test',
    },
  ];

  const mockOverviewEmpty = {
    by_platform: [],
  };

  const mockOverviewPopulated = {
    by_platform: [
      {
        platform: 'facebook',
        impressions: 12500,
        reach: 8400,
        clicks: 320,
        video_views: 1100,
        followers: 450,
      },
      {
        platform: 'instagram',
        impressions: 24000,
        reach: 16000,
        clicks: 780,
        video_views: 5200,
        followers: 890,
      },
    ],
  };

  const mockSharedLinks = [
    {
      id: 10,
      client: 1,
      client_name: 'Acme Corp',
      date_from: '2026-08-01',
      date_until: '2026-08-31',
      platforms: ['facebook', 'instagram'],
      view_count: 5,
      created_at: '2026-09-01T12:00:00Z',
      expires_at: '2026-10-01T12:00:00Z',
      is_expired: false,
      is_password_protected: true,
      token: 'tok-acme-10',
    },
  ];

  const now = new Date();
  const currentMonth = now.getMonth() + 1;
  const currentYear = now.getFullYear();

  const mockROIReports = [
    {
      id: 50,
      client_name: 'Acme Corp',
      month: currentMonth,
      year: currentYear,
      roi_percentage: '220.5',
      currency_symbol: '$',
      total_investment: 5000,
      estimated_revenue: 16025,
      estimated_leads: 140,
    },
  ];


  beforeEach(async () => {
    localStorage.clear();
    overviewAPI.get.mockResolvedValue({ data: mockOverviewPopulated });
    clientsAPI.summary.mockResolvedValue({ data: { impressions: 5000, reach: 3000, clicks: 120, video_views: 400, followers: 80 } });
    clientsAPI.timeseries.mockResolvedValue({ data: [] });
    sharedReportsAPI.list.mockResolvedValue({ data: mockSharedLinks });
    roiAPI.getReports.mockResolvedValue({ data: mockROIReports });

    useDataModule.useClients.mockReturnValue({ clients: mockClients, loading: false });
    useDataModule.useDateRange.mockReturnValue([
      { since: '2026-08-25', until: '2026-09-24' },
      jest.fn(),
    ]);
    useDataModule.useLookups.mockReturnValue({ lookups: { platforms: [] } });

    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  describe('AnalyticsPage Localization', () => {
    test('renders all 12 reported defects and components in English when English is active', async () => {
      await act(async () => {
        render(
          <MemoryRouter>
            <AnalyticsPage />
          </MemoryRouter>
        );
      });

      // 1. Page Title & Subtitle
      expect(screen.getByRole('heading', { level: 1, name: 'Analytics' })).toBeInTheDocument();
      expect(screen.getByText(/All clients overview —/i)).toBeInTheDocument();

      // 2. Dropdown options
      expect(screen.getByText('All Users')).toBeInTheDocument();

      // 3. Metric cards
      expect(screen.getAllByText('Impressions').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Reach').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Clicks').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Video Views').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Followers').length).toBeGreaterThanOrEqual(1);

      // 4. Section titles
      expect(screen.getByText('Performance by Platform')).toBeInTheDocument();
      expect(screen.getByText(/Aggregated across all clients —/i)).toBeInTheDocument();
      expect(screen.getByText('Platform Distribution')).toBeInTheDocument();
      expect(screen.getByText('Platform Metrics Comparison')).toBeInTheDocument();
      expect(screen.getByText('Platform Balance Radar')).toBeInTheDocument();
      expect(screen.getByText('Platform Breakdown')).toBeInTheDocument();
      expect(screen.getByText('User Overview')).toBeInTheDocument();

      // 5. Table headers & values
      expect(screen.getByRole('columnheader', { name: 'Platform' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'CTR' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'Client' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'Status' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'Website' })).toBeInTheDocument();

      // 6. User action buttons & status
      expect(screen.getByText('Active')).toBeInTheDocument();
      expect(screen.getByText('Inactive')).toBeInTheDocument();
      const viewButtons = screen.getAllByRole('button', { name: /View Analytics →/i });
      expect(viewButtons.length).toBe(2);
    });

    test('renders all 12 reported defects in Spanish when Spanish is selected', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      await act(async () => {
        render(
          <MemoryRouter>
            <AnalyticsPage />
          </MemoryRouter>
        );
      });

      // 1. Page Title & Subtitle in Spanish
      expect(screen.getByRole('heading', { level: 1, name: 'Analítica' })).toBeInTheDocument();
      expect(screen.getByText(/Resumen de todos los clientes —/i)).toBeInTheDocument();

      // 2. Dropdown options in Spanish
      expect(screen.getByText('Todos los usuarios')).toBeInTheDocument();

      // 3. Metric cards in Spanish
      expect(screen.getAllByText('Impresiones').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Alcance').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Clics').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Visualizaciones de video').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Seguidores').length).toBeGreaterThanOrEqual(1);

      // 4. Section titles in Spanish
      expect(screen.getByText('Rendimiento por plataforma')).toBeInTheDocument();
      expect(screen.getByText(/Datos consolidados de todos los clientes —/i)).toBeInTheDocument();
      expect(screen.getByText('Distribución por plataforma')).toBeInTheDocument();
      expect(screen.getByText('Comparación de métricas de plataforma')).toBeInTheDocument();
      expect(screen.getByText('Radar de equilibrio de plataformas')).toBeInTheDocument();
      expect(screen.getByText('Desglose por plataforma')).toBeInTheDocument();
      expect(screen.getByText('Resumen de usuarios')).toBeInTheDocument();

      // 5. Table headers in Spanish
      expect(screen.getByRole('columnheader', { name: 'Plataforma' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'CTR' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'Cliente' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'Estado' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'Sitio web' })).toBeInTheDocument();

      // 6. User action buttons & status in Spanish
      expect(screen.getByText('Activo')).toBeInTheDocument();
      expect(screen.getByText('Inactivo')).toBeInTheDocument();
      const viewButtons = screen.getAllByRole('button', { name: /Ver analítica →/i });
      expect(viewButtons.length).toBe(2);
    });

    test('renders client-specific view and dynamic titles in Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      await act(async () => {
        render(
          <MemoryRouter>
            <AnalyticsPage />
          </MemoryRouter>
        );
      });

      // Click "Ver analítica →" for Acme Corp
      const viewButtons = screen.getAllByRole('button', { name: /Ver analítica →/i });
      await act(async () => {
        fireEvent.click(viewButtons[0]);
      });

      // Subtitle switches to "Viendo Acme Corp — ..."
      expect(screen.getByText(/Viendo Acme Corp —/i)).toBeInTheDocument();

      // "Todas las plataformas" appears in selector
      expect(screen.getByText('Todas las plataformas')).toBeInTheDocument();

      // Section titles for single client view
      expect(screen.getByText(/Rendimiento a lo largo del tiempo — Acme Corp/i)).toBeInTheDocument();
      expect(screen.getByText('Todas las métricas a lo largo del tiempo')).toBeInTheDocument();
    });

    test('renders empty states in Spanish correctly when there is no data', async () => {
      overviewAPI.get.mockResolvedValue({ data: mockOverviewEmpty });
      useDataModule.useClients.mockReturnValue({ clients: [], loading: false });

      await act(async () => {
        await changePlatformLanguage('es');
      });

      await act(async () => {
        render(
          <MemoryRouter>
            <AnalyticsPage />
          </MemoryRouter>
        );
      });

      expect(screen.getByText('Aún no hay datos. Sincroniza tus usuarios para ver las estadísticas de las plataformas.')).toBeInTheDocument();
      expect(screen.getByText('Aún no hay datos de plataformas.')).toBeInTheDocument();
      expect(screen.getByText('No hay datos de plataforma. Sincroniza clientes para cargar la analítica.')).toBeInTheDocument();
      expect(screen.getByText('Aún no hay clientes. Agrega un cliente para comenzar.')).toBeInTheDocument();
    });
  });

  describe('ReportsPage & ShareReportModal Localization', () => {
    test('renders ReportsPage in English and Spanish', async () => {
      // English
      const { rerender } = render(
        <MemoryRouter>
          <ReportsPage />
        </MemoryRouter>
      );

      expect(screen.getByRole('heading', { level: 1, name: 'Reports' })).toBeInTheDocument();
      expect(screen.getByText('Shared Links')).toBeInTheDocument();
      expect(screen.getByText('ROI Reports')).toBeInTheDocument();
      expect(screen.getByText('Shared Report Links')).toBeInTheDocument();
      expect(screen.getByText('All clients')).toBeInTheDocument();

      // Switch to Spanish
      await act(async () => {
        await changePlatformLanguage('es');
      });

      rerender(
        <MemoryRouter>
          <ReportsPage />
        </MemoryRouter>
      );

      expect(screen.getByRole('heading', { level: 1, name: 'Informes' })).toBeInTheDocument();
      expect(screen.getByText('Enlaces compartidos')).toBeInTheDocument();
      expect(screen.getByText('Informes de ROI')).toBeInTheDocument();
      expect(screen.getByText('Enlaces de informes compartidos')).toBeInTheDocument();
      expect(screen.getByText('Todos los clientes')).toBeInTheDocument();
    });

    test('renders ROI reports table with localized badges and headers in Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      await act(async () => {
        render(
          <MemoryRouter>
            <ReportsPage />
          </MemoryRouter>
        );
      });

      // Switch tab to "Informes de ROI"
      const roiTab = screen.getByText('Informes de ROI');
      await act(async () => {
        fireEvent.click(roiTab);
      });

      // Headers in Spanish
      expect(screen.getByRole('columnheader', { name: 'Usuario' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'Mes' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'ROI %' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'Inversión' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'Ingresos' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'Clientes potenciales' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'Estado' })).toBeInTheDocument();

      // Badge in Spanish (220.5% -> Excelente)
      expect(screen.getByText('Excelente')).toBeInTheDocument();
      const monthNamesEs = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
      expect(screen.getByText(`${monthNamesEs[currentMonth - 1]} ${currentYear}`)).toBeInTheDocument();
      expect(screen.getByText(/Ver →/i)).toBeInTheDocument();
    });

    test('renders ShareReportModal in Spanish with proper form options', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      await act(async () => {
        render(
          <ShareReportModal clientId={1} onClose={jest.fn()} />
        );
      });

      expect(screen.getByRole('heading', { level: 2, name: 'Compartir informe' })).toBeInTheDocument();
      expect(screen.getByText('Rango de fechas')).toBeInTheDocument();
      expect(screen.getByText('Plataformas')).toBeInTheDocument();
      expect(screen.getByText('Vencimiento')).toBeInTheDocument();
      expect(screen.getByText('Protección con contraseña')).toBeInTheDocument();
      expect(screen.getByText('Proteger con contraseña')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Generar enlace/i })).toBeInTheDocument();

      // Expiry options in Spanish
      expect(screen.getByText('Nunca')).toBeInTheDocument();
      expect(screen.getByText('24 horas')).toBeInTheDocument();
      expect(screen.getByText('7 días')).toBeInTheDocument();
      expect(screen.getByText('30 días')).toBeInTheDocument();
    });
  });
});
