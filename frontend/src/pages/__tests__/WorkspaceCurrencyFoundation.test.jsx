/* ============================================================================
 *  Bop Social — Phase BS-2.7B: Canonical Workspace Currency & Formatter Foundation
 *  Automated Verification Test Suite
 * ============================================================================ */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n from '../../i18n/config';
import SettingsPage from '../SettingsPage';
import EditClientPage from '../EditClientPage';
import TodayDashboard from '../../components/dashboard/TodayDashboard';
import { formatCurrency, formatCompactCurrency } from '../../utils/formatters';
import { clientsAPI } from '../../services/api';
import useDashboardToday from '../../hooks/useDashboardToday';

// Mock dependencies
jest.mock('../../services/api', () => ({
  clientsAPI: {
    get: jest.fn(),
    update: jest.fn(),
  },
  connectedAccountsAPI: {
    getOAuthStatus: jest.fn(() => Promise.resolve({ data: {} })),
  },
}));

jest.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, client_id: 1, role: 'admin' },
    isAuthenticated: true,
  }),
}));

jest.mock('../../hooks/useData', () => ({
  useOAuthStatus: () => ({ status: {}, refetch: jest.fn() }),
  useLookups: () => ({ lookups: {}, loading: false }),
}));

jest.mock('../../components/ui/ConnectedAccounts', () => () => <div data-testid="mock-connected-accounts" />);
jest.mock('../../components/ui/CompetitorSection', () => () => <div data-testid="mock-competitor-section" />);

jest.mock('../../hooks/useDashboardToday');

describe('Phase BS-2.7B: Canonical Workspace Currency & Formatter Foundation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    i18n.changeLanguage('en');
  });

  // ── 1. Formatter: USD, COP, EUR & Zero-Decimal ─────────────────────────────
  it('1. formats USD, COP, EUR correctly in English and Spanish', () => {
    // USD
    expect(formatCurrency(1250, 'USD', 'en')).toBe('$1,250.00');
    expect(formatCurrency(1250, 'USD', 'es')).toMatch(/1.*250,00/);

    // COP (Colombian Peso)
    const copEn = formatCurrency(500000, 'COP', 'en');
    const copEs = formatCurrency(500000, 'COP', 'es');
    expect(copEn).toMatch(/500,000/);
    expect(copEs).toMatch(/500[.\s]000/);

    // EUR
    expect(formatCurrency(3400, 'EUR', 'en')).toBe('€3,400.00');
    expect(formatCurrency(3400, 'EUR', 'es')).toMatch(/3.*400,00\s?€/);

    // Zero-decimal currency (CLP)
    const clp = formatCurrency(25000, 'CLP', 'en');
    expect(clp).toMatch(/25,000/);
    expect(clp).not.toContain('.00');
  });

  // ── 2. Compact Formatter ───────────────────────────────────────────────────
  it('2. formats compact currency for KPI tiles across currencies and languages', () => {
    // English compact USD
    const usdCompactEn = formatCompactCurrency(1200000, 'USD', 'en');
    expect(usdCompactEn).toMatch(/\$1\.2M|\$1\.20M/);

    // Spanish compact COP
    const copCompactEs = formatCompactCurrency(50000000, 'COP', 'es');
    expect(copCompactEs).toMatch(/50\s?M/);

    // Null/undefined inputs return placeholder
    expect(formatCompactCurrency(null, 'USD', 'en')).toBe('—');
    expect(formatCompactCurrency(undefined, 'USD', 'en')).toBe('—');

    // Unknown currency fallback
    const fallback = formatCompactCurrency(10000, 'XYZ', 'en');
    expect(fallback).toContain('XYZ');
    expect(fallback).toContain('10K');
  });

  // ── 3. Today Dashboard No Longer Hardcodes Rupee ───────────────────────────
  it('3. renders TodayDashboard pipeline value with workspace currency without ₹ hardcoding', () => {
    // Mock dashboard today payload with COP workspace currency
    useDashboardToday.mockReturnValue({
      data: {
        client_id: 1,
        client_name: 'Bogota Brands',
        client_currency: 'COP',
        leads: {
          new_today: 12,
          qualified: 8,
          converted_today: 3,
          pipeline_value: 4500000,
          currency: 'COP',
        },
        posts: { published_today: 2, scheduled: 5, queued: 1 },
        inbox: { unread: 4, priority: 1, replied_today: 10 },
        campaigns: { running: 2, sent_today: 150 },
        engagement_chart: [],
        recent_activity: [],
        pending_approvals: [],
      },
      isLoading: false,
      isError: false,
    });

    const { container } = render(
      <MemoryRouter>
        <TodayDashboard />
      </MemoryRouter>
    );

    // Must NOT contain the Indian Rupee symbol anywhere in the rendered dashboard
    expect(container.textContent).not.toContain('₹');

    // Must contain the formatted pipeline value with COP notation (e.g. COP 4.5M or $4.5M)
    expect(container.textContent).toMatch(/Pipeline/);
    expect(container.textContent).toMatch(/4\.5M|4,5\s?M/);
  });

  it('4. renders TodayDashboard pipeline value with USD currency in Spanish UI', () => {
    i18n.changeLanguage('es');

    useDashboardToday.mockReturnValue({
      data: {
        client_id: 2,
        client_name: 'Miami Corp',
        client_currency: 'USD',
        leads: {
          new_today: 5,
          qualified: 2,
          converted_today: 1,
          pipeline_value: 250000,
          currency: 'USD',
        },
        posts: { published_today: 1, scheduled: 2, queued: 0 },
        inbox: { unread: 0, priority: 0, replied_today: 2 },
        campaigns: { running: 1, sent_today: 20 },
        engagement_chart: [],
        recent_activity: [],
        pending_approvals: [],
      },
      isLoading: false,
      isError: false,
    });

    const { container } = render(
      <MemoryRouter>
        <TodayDashboard />
      </MemoryRouter>
    );

    expect(container.textContent).not.toContain('₹');
    expect(container.textContent).toMatch(/Pipeline/);
    expect(container.textContent).toMatch(/250\s?K|250K|250\s?mil/i);
  });

  // ── 4. SettingsPage Currency Selector ──────────────────────────────────────
  it('5. renders workspace currency selector in SettingsPage with supported ISO codes', async () => {
    clientsAPI.get.mockResolvedValue({
      data: {
        id: 1,
        company: 'Alpha Corp',
        currency: 'EUR',
        default_language: 'en',
      },
    });

    render(
      <MemoryRouter>
        <SettingsPage clientId={1} />
      </MemoryRouter>
    );

    // Click the "Business Profile" tab where currency configuration resides
    const profileTab = await screen.findByRole('button', { name: /business profile/i });
    fireEvent.click(profileTab);

    await waitFor(() => {
      const select = screen.getByTestId('workspace-currency-select');
      expect(select).toBeInTheDocument();
      expect(select.value).toBe('EUR');
    });

    // Verify presence of options
    const select = screen.getByTestId('workspace-currency-select');
    const options = Array.from(select.querySelectorAll('option')).map((o) => o.value);
    expect(options).toEqual(
      expect.arrayContaining(['USD', 'COP', 'EUR', 'GBP', 'MXN', 'CAD', 'INR', 'BRL', 'ARS', 'CLP', 'PEN'])
    );
  });

  // ── 5. EditClientPage Currency Selector ────────────────────────────────────
  it('6. allows updating workspace currency in EditClientPage', async () => {
    clientsAPI.get.mockResolvedValue({
      data: {
        id: 2,
        company: 'Beta LLC',
        name: 'Beta Admin',
        email: 'beta@example.com',
        phone: '1234567890',
        website: 'https://beta.com',
        default_language: 'es',
        currency: 'COP',
      },
    });
    clientsAPI.update.mockResolvedValue({
      data: { id: 2, company: 'Beta LLC', currency: 'USD' },
    });

    render(
      <MemoryRouter>
        <EditClientPage clientId={2} />
      </MemoryRouter>
    );

    await waitFor(() => {
      const select = screen.getByTestId('edit-client-currency-select');
      expect(select).toBeInTheDocument();
      expect(select.value).toBe('COP');
    });

    const select = screen.getByTestId('edit-client-currency-select');
    fireEvent.change(select, { target: { value: 'USD' } });
    expect(select.value).toBe('USD');
  });

  // ── 6. Language & Currency Independence in UI ──────────────────────────────
  it('7. preserves workspace currency selection when switching UI language', async () => {
    clientsAPI.get.mockResolvedValue({
      data: {
        id: 3,
        company: 'Global Retail',
        currency: 'COP',
        default_language: 'en',
      },
    });

    const { rerender } = render(
      <MemoryRouter>
        <SettingsPage clientId={3} />
      </MemoryRouter>
    );

    // Navigate to Business Profile
    const profileTabEn = await screen.findByRole('button', { name: /business profile/i });
    fireEvent.click(profileTabEn);

    await waitFor(() => {
      expect(screen.getByTestId('workspace-currency-select').value).toBe('COP');
    });

    // Switch language to Spanish
    i18n.changeLanguage('es');

    rerender(
      <MemoryRouter>
        <SettingsPage clientId={3} />
      </MemoryRouter>
    );

    // Selected currency must still be COP
    await waitFor(() => {
      expect(screen.getByTestId('workspace-currency-select').value).toBe('COP');
    });
  });
});
