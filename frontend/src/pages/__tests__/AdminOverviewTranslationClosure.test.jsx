import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n, { changePlatformLanguage } from '../../i18n/config';
import AdminOverview from '../AdminOverview';
import * as useDataModule from '../../hooks/useData';
import { goalsAPI, topPostsAPI, sharedReportsAPI, roiAPI } from '../../services/api';

// Mock API calls made in AdminOverview subcomponents
jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {},
  goalsAPI: {
    create: jest.fn(),
    delete: jest.fn(),
  },
  topPostsAPI: {
    list: jest.fn(),
    run: jest.fn(),
  },
  sharedReportsAPI: {
    list: jest.fn(),
    delete: jest.fn(),
  },
  roiAPI: {
    getReports: jest.fn(),
  },
}));

// Mock useData hooks
jest.mock('../../hooks/useData', () => ({
  useOverview: jest.fn(),
  useDateRange: jest.fn(),
  useClients: jest.fn(),
  useGoals: jest.fn(),
  useAlerts: jest.fn(),
  useLookups: jest.fn(),
}));

describe('AdminOverview Translation & Date Formatting Closure (BS-2.2.1)', () => {
  const emptyOverview = {
    total_clients: 0,
    by_platform: [],
    recent_syncs: [],
    period: {
      since: '2026-08-25',
      until: '2026-09-24',
    },
  };

  const populatedOverview = {
    total_clients: 3,
    by_platform: [
      {
        platform: 'youtube',
        impressions: 15400,
        reach: 8900,
        clicks: 340,
        followers: 120,
        video_views: 4500,
      },
    ],
    recent_syncs: [
      {
        id: 101,
        client_name: 'Demo Agency',
        platform: 'youtube',
        status: 'success',
        records_synced: 42,
        started_at: '2026-09-24T08:00:00Z',
      },
    ],
    period: {
      since: '2026-08-25',
      until: '2026-09-24',
    },
  };

  beforeEach(async () => {
    localStorage.clear();
    roiAPI.getReports.mockResolvedValue({ data: [] });
    topPostsAPI.list.mockResolvedValue({ data: [] });
    topPostsAPI.run.mockResolvedValue({ data: [] });
    sharedReportsAPI.list.mockResolvedValue({ data: [] });

    useDataModule.useDateRange.mockReturnValue([
      { since: '2026-08-25', until: '2026-09-24' },
      jest.fn(),
    ]);
    useDataModule.useClients.mockReturnValue({ clients: [], loading: false, refetch: jest.fn() });
    useDataModule.useGoals.mockReturnValue({ goals: [], refetch: jest.fn() });
    useDataModule.useAlerts.mockReturnValue({ alerts: [], unreadCount: 0, markRead: jest.fn(), markAllRead: jest.fn() });
    useDataModule.useLookups.mockReturnValue({ lookups: { platforms: [] } });

    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  test('renders all reported defect states in English when English is active', async () => {
    useDataModule.useOverview.mockReturnValue({ data: emptyOverview, loading: false });

    await act(async () => {
      render(
        <MemoryRouter>
          <AdminOverview />
        </MemoryRouter>
      );
    });

    // 1. "No data yet"
    expect(screen.getByText('No data yet')).toBeInTheDocument();

    // 2. "Waiting for synced performance data"
    expect(screen.getByText('Waiting for synced performance data')).toBeInTheDocument();

    // 3. "0 active platforms in this window"
    expect(screen.getByText('0 active platforms in this window')).toBeInTheDocument();

    // 4. "0 clicks from 0 impressions"
    expect(screen.getByText('0 clicks from 0 impressions')).toBeInTheDocument();

    // 5. "No recent syncs" (appears in SignalCard and summary bar)
    const noSyncElements = screen.getAllByText('No recent syncs');
    expect(noSyncElements.length).toBeGreaterThanOrEqual(1);

    // 6. Localized date range in English
    expect(screen.getByText(/Aug 25.*Sep 24, 2026/)).toBeInTheDocument();
  });

  test('renders all reported defect states in Spanish when Spanish is selected', async () => {
    await act(async () => {
      await changePlatformLanguage('es');
    });

    useDataModule.useOverview.mockReturnValue({ data: emptyOverview, loading: false });

    await act(async () => {
      render(
        <MemoryRouter>
          <AdminOverview />
        </MemoryRouter>
      );
    });

    // 1. "No data yet" -> "Sin datos todavía"
    expect(screen.getByText('Sin datos todavía')).toBeInTheDocument();

    // 2. "Waiting for synced performance data" -> "Esperando datos de rendimiento sincronizados"
    expect(screen.getByText('Esperando datos de rendimiento sincronizados')).toBeInTheDocument();

    // 3. "0 active platforms in this window" -> "0 plataformas activas en este período"
    expect(screen.getByText('0 plataformas activas en este período')).toBeInTheDocument();

    // 4. "0 clicks from 0 impressions" -> "0 clics de 0 impresiones"
    expect(screen.getByText('0 clics de 0 impresiones')).toBeInTheDocument();

    // 5. "No recent syncs" -> "Sin sincronizaciones recientes"
    const noSyncElements = screen.getAllByText('Sin sincronizaciones recientes');
    expect(noSyncElements.length).toBeGreaterThanOrEqual(1);

    // 6. Localized date range in Spanish
    expect(screen.getByText(/25 ago.*24 sept 2026/)).toBeInTheDocument();
  });

  test('dynamically updates text when language is switched without page reload', async () => {
    useDataModule.useOverview.mockReturnValue({ data: emptyOverview, loading: false });

    const { rerender } = render(
      <MemoryRouter>
        <AdminOverview />
      </MemoryRouter>
    );

    expect(screen.getByText('No data yet')).toBeInTheDocument();
    expect(screen.getByText('Waiting for synced performance data')).toBeInTheDocument();

    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <AdminOverview />
      </MemoryRouter>
    );

    expect(screen.getByText('Sin datos todavía')).toBeInTheDocument();
    expect(screen.getByText('Esperando datos de rendimiento sincronizados')).toBeInTheDocument();
  });

  test('handles populated overview data and preserves metrics across locales', async () => {
    useDataModule.useOverview.mockReturnValue({ data: populatedOverview, loading: false });

    // English
    const { rerender } = render(
      <MemoryRouter>
        <AdminOverview />
      </MemoryRouter>
    );

    // Singular 1 platform in English
    expect(screen.getByText('1 active platform in this window')).toBeInTheDocument();
    expect(screen.getByText(/340 clicks from 15\.4k impressions/i)).toBeInTheDocument();
    expect(screen.getByText(/15\.4k impressions · 8\.9k reach/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Demo Agency · success/i).length).toBeGreaterThanOrEqual(1);

    // Switch to Spanish
    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <AdminOverview />
      </MemoryRouter>
    );

    // Singular 1 platform in Spanish
    expect(screen.getByText('1 plataforma activa en este período')).toBeInTheDocument();
    expect(screen.getByText(/340 clics de 15\.4k impresiones/i)).toBeInTheDocument();
    expect(screen.getByText(/15\.4k impresiones · 8\.9k alcance/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Demo Agency · éxito/i).length).toBeGreaterThanOrEqual(1);
  });
});
