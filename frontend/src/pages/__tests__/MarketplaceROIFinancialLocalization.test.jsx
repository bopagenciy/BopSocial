/* ============================================================================
 *  Bop Social — Phase BS-2.7D: Marketplace, ROI & Reporting Financial Localization
 *  Automated Verification Test Suite
 * ============================================================================ */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import i18n from '../../i18n/config';
import { CANONICAL_CURRENCIES, DEFAULT_CURRENCY } from '../../utils/currencies';
import TodayDashboard from '../../components/dashboard/TodayDashboard';
import SendManageRequestModal from '../../components/marketplace/SendManageRequestModal';
import InviteAgencyModal, { getBudgetRangeOptions } from '../../components/marketplace/InviteAgencyModal';
import AgencyProfilePage from '../marketplace/AgencyProfilePage';
import MarketplacePage from '../marketplace/MarketplacePage';
import ReportsPage from '../ReportsPage';
import AdminOverview from '../AdminOverview';
import ROICalculatorPage from '../ROICalculatorPage';
import useDashboardToday from '../../hooks/useDashboardToday';
import * as useDataModule from '../../hooks/useData';
import {
  manageRequestAPI,
  marketplaceAPI,
  reviewAPI,
  reportsAPI,
  sharedReportsAPI,
  topPostsAPI,
  goalsAPI,
  roiAPI,
} from '../../services/api';

// ── Polyfills ──────────────────────────────────────────────────────────────────
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// ── Mocks ──────────────────────────────────────────────────────────────────────
jest.mock('../../hooks/useDashboardToday');

jest.mock('../../hooks/useData', () => ({
  __esModule: true,
  useClients: jest.fn(),
  useOAuthStatus: jest.fn(() => ({ status: {}, refetch: jest.fn() })),
  useLookups: jest.fn(() => ({ lookups: { platforms: [] }, loading: false })),
  useOverview: jest.fn(),
  useDateRange: jest.fn(),
  useGoals: jest.fn(() => ({ goals: [], loading: false, createGoal: jest.fn(), deleteGoal: jest.fn(), refetch: jest.fn() })),
  useAlerts: jest.fn(() => ({ alerts: [], unreadCount: 0, loading: false, markRead: jest.fn(), markAllRead: jest.fn() })),
}));

jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {},
  manageRequestAPI: {
    send: jest.fn(() => Promise.resolve({ data: { id: 1, proposed_currency: 'EUR' } })),
    getSent: jest.fn(() => Promise.resolve({ data: [] })),
    getReceived: jest.fn(() => Promise.resolve({ data: [] })),
  },
  marketplaceAPI: {
    list: jest.fn(),
    featured: jest.fn(() => Promise.resolve({ data: { agencies: [] } })),
    categories: jest.fn(() => Promise.resolve({ data: { categories: [] } })),
    get: jest.fn(),
    getClients: jest.fn(() => Promise.resolve({
      data: [
        { id: 101, name: 'Brand Alpha', company: 'Brand Alpha Inc', currency: 'USD' },
        { id: 102, name: 'Euro Boutique', company: 'Euro Boutique SARL', currency: 'EUR' },
      ],
    })),
  },
  reviewAPI: {
    list: jest.fn(() => Promise.resolve({ data: { count: 0, avg_rating: 5, distribution: {}, rows: [] } })),
    delete: jest.fn(() => Promise.resolve({ data: {} })),
    helpful: jest.fn(() => Promise.resolve({ data: { helpful_count: 1 } })),
    respond: jest.fn(() => Promise.resolve({ data: {} })),
  },
  reportsAPI: {
    getSummary: jest.fn(() => Promise.resolve({
      data: {
        total_posts: 120,
        avg_engagement: 4.5,
        total_reach: 45000,
        network_breakdown: {},
      },
    })),
  },
  sharedReportsAPI: {
    list: jest.fn(() => Promise.resolve({ data: [] })),
    create: jest.fn(() => Promise.resolve({ data: {} })),
    delete: jest.fn(() => Promise.resolve({ data: {} })),
    update: jest.fn(() => Promise.resolve({ data: {} })),
  },
  topPostsAPI: {
    list: jest.fn(() => Promise.resolve({ data: { results: [] } })),
    run: jest.fn(() => Promise.resolve({ data: [] })),
  },
  goalsAPI: {
    create: jest.fn(() => Promise.resolve({ data: {} })),
    delete: jest.fn(() => Promise.resolve({ data: {} })),
  },
  roiAPI: {
    getSettings: jest.fn(),
    getLive: jest.fn(),
    getReports: jest.fn(),
    saveSettings: jest.fn(() => Promise.resolve({ data: {} })),
    saveReport: jest.fn(() => Promise.resolve({ data: {} })),
  },
  clientsAPI: {
    list: jest.fn(() => Promise.resolve({ data: [{ id: 101, company: 'Acme Corp', currency: 'USD' }] })),
    get: jest.fn(() => Promise.resolve({ data: { id: 101, company: 'Acme Corp', currency: 'USD' } })),
  },
}));

jest.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, client_id: 101, role: 'admin' },
    isAuthenticated: true,
  }),
}));

describe('Phase BS-2.7D: Marketplace, ROI & Reporting Financial Localization Suite', () => {
  const curMonth = new Date().getMonth() + 1;
  const curYear = new Date().getFullYear();

  beforeEach(async () => {
    jest.clearAllMocks();
    useDataModule.useClients.mockReturnValue({
      clients: [{ id: 101, company: 'Acme Corp', currency: 'USD' }],
      loading: false,
    });
    useDataModule.useLookups.mockReturnValue({
      lookups: { platforms: [] },
      loading: false,
    });
    useDataModule.useOverview.mockReturnValue({
      data: {
        total_clients: 2,
        by_platform: [],
        recent_syncs: [],
        period: { since: '2026-08-25', until: '2026-09-24' },
      },
      loading: false,
    });
    useDataModule.useDateRange.mockReturnValue([
      { since: '2026-08-25', until: '2026-09-24' },
      jest.fn(),
    ]);
    useDataModule.useGoals.mockReturnValue({
      goals: [],
      loading: false,
      createGoal: jest.fn(),
      deleteGoal: jest.fn(),
      refetch: jest.fn(),
    });
    useDataModule.useAlerts.mockReturnValue({
      alerts: [],
      unreadCount: 0,
      loading: false,
      markRead: jest.fn(),
      markAllRead: jest.fn(),
    });

    sharedReportsAPI.list.mockResolvedValue({ data: [] });
    topPostsAPI.list.mockResolvedValue({ data: { results: [] } });
    topPostsAPI.run.mockResolvedValue({ data: [] });
    reviewAPI.list.mockResolvedValue({ data: { count: 0, avg_rating: 5, distribution: {}, rows: [] } });

    roiAPI.getReports.mockResolvedValue({
      data: [
        { id: 1, month: curMonth, year: curYear, total_investment: 3000, estimated_revenue: 9000, roi_percentage: 200, currency: 'EUR' },
        { id: 2, month: curMonth, year: curYear, total_investment: 2000, estimated_revenue: 7000, roi_percentage: 250, currency: 'GBP' },
      ],
    });
    roiAPI.getSettings.mockResolvedValue({
      data: {
        facebook_budget: 500,
        instagram_budget: 300,
        youtube_budget: 0,
        linkedin_budget: 0,
        gmb_budget: 0,
        agency_fee: 200,
        avg_sale_value: 100,
        conversion_rate: 2.5,
        lead_to_sale_rate: 20,
        monthly_revenue_goal: 5000,
        monthly_leads_goal: 50,
        currency: 'EUR',
        currency_symbol: '€',
      },
    });
    roiAPI.getLive.mockResolvedValue({
      data: {
        total_investment: 1000,
        estimated_revenue: 3500,
        roi_percentage: 250,
        per_dollar_earned: 3.5,
        cost_per_click: 0.8,
        cost_per_lead: 25.0,
        cost_per_sale: 100.0,
        total_clicks: 1250,
        total_website_clicks: 800,
        estimated_leads: 40,
        estimated_sales: 8,
        platform_breakdown: [
          { platform: 'facebook', budget: 500, clicks: 650, leads: 22, sales: 5, revenue: 2000, roi_percentage: 300 },
          { platform: 'instagram', budget: 300, clicks: 400, leads: 15, sales: 3, revenue: 1500, roi_percentage: 400 },
        ],
        goals: {
          revenue_goal: 5000,
          revenue_progress: 70,
          leads_goal: 50,
          leads_progress: 80,
        },
        has_data: true,
      },
    });
    marketplaceAPI.list.mockResolvedValue({
      data: {
        agencies: [
          {
            id: 10,
            slug: 'alpha-creative',
            name: 'Alpha Creative Agency',
            tagline: 'Leading Social Agency',
            pricing_starting_at: '2500.00',
            pricing_currency: 'EUR',
            rating: '4.9',
            review_count: 12,
            verified: true,
            skills: ['Instagram Growth', 'Meta Ads'],
          },
          {
            id: 11,
            slug: 'london-digital',
            name: 'London Digital Group',
            tagline: 'Global Scaling Partners',
            pricing_starting_at: '1800.00',
            pricing_currency: 'GBP',
            rating: '4.8',
            review_count: 8,
            verified: true,
            skills: ['Content Strategy'],
          },
        ],
        count: 2,
      },
    });
    marketplaceAPI.get.mockResolvedValue({
      data: {
        id: 10,
        slug: 'alpha-creative',
        name: 'Alpha Creative Agency',
        tagline: 'Leading Social Agency',
        description: 'Elite digital marketing agency',
        pricing_starting_at: '2500.00',
        pricing_currency: 'EUR',
        rating: '4.9',
        avg_rating: 4.9,
        review_count: 12,
        verified: true,
        skills: ['Instagram Growth', 'Meta Ads'],
        team_size: '10-20',
        founded_year: 2020,
      },
    });

    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  // 1. Canonical currency constants
  it('1. exports canonical 11 currencies with USD as default', () => {
    expect(DEFAULT_CURRENCY).toBe('USD');
    expect(CANONICAL_CURRENCIES.length).toBe(11);
    const codes = CANONICAL_CURRENCIES.map(c => c.code);
    ['USD', 'COP', 'EUR', 'GBP', 'MXN', 'CAD', 'INR', 'BRL', 'ARS', 'CLP', 'PEN'].forEach(c => {
      expect(codes).toContain(c);
    });
  });

  // 2. Marketplace Page agency pricing display
  it('2. renders marketplace agencies with their authoritative pricing currency', async () => {
    render(
      <MemoryRouter>
        <MarketplacePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Alpha Creative Agency')).toBeInTheDocument();
    });

    // EUR 2500 starting price
    const eurStarting = screen.getByText((content) => content.includes('2,500') || content.includes('2.500'));
    expect(eurStarting).toBeInTheDocument();
    expect(eurStarting.textContent).toMatch(/€|EUR/);

    // GBP 1800 starting price
    const gbpStarting = screen.getByText((content) => content.includes('1,800') || content.includes('1.800'));
    expect(gbpStarting).toBeInTheDocument();
    expect(gbpStarting.textContent).toMatch(/£|GBP/);
  });

  // 3. Agency Profile Page pricing display
  it('3. renders agency profile starting price with localized currency', async () => {
    render(
      <MemoryRouter initialEntries={['/marketplace/agency/alpha-creative']}>
        <Routes>
          <Route path="/marketplace/agency/:slug" element={<AgencyProfilePage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Alpha Creative Agency')).toBeInTheDocument();
    });

    const priceText = screen.getByText((content) => content.includes('2,500') || content.includes('2.500'));
    expect(priceText).toBeInTheDocument();
    expect(priceText.textContent).toMatch(/€|EUR/);
  });

  // 4. SendManageRequestModal allows currency selection and passes proposed_currency
  it('4. SendManageRequestModal submits proposed_currency in payload', async () => {
    const onSent = jest.fn();
    render(
      <MemoryRouter>
        <SendManageRequestModal
          open={true}
          onClose={jest.fn()}
          onSent={onSent}
        />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Invite a client to manage')).toBeInTheDocument();
    });

    // Step 1: Target email
    const emailInput = screen.getByPlaceholderText('client@business.com');
    fireEvent.change(emailInput, { target: { value: 'client@example.com' } });

    // Click Next to Step 2
    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    // Step 2: Permissions -> Click Next to Step 3
    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    // Step 3: Terms & Pricing
    const pricingInput = screen.getByPlaceholderText('e.g., 5000');
    fireEvent.change(pricingInput, { target: { value: '3000' } });

    const currencySelect = screen.getByDisplayValue('USD');
    fireEvent.change(currencySelect, { target: { value: 'GBP' } });

    // Click Next to Step 4
    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    // Step 4: Click Send invitation
    const sendBtn = screen.getByRole('button', { name: /send invitation/i });
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(manageRequestAPI.send).toHaveBeenCalledWith(
        expect.objectContaining({
          target_email: 'client@example.com',
          proposed_pricing: 3000,
          proposed_currency: 'GBP',
        })
      );
    });
  });

  // 5. InviteAgencyModal localized budget thresholds without hardcoded ₹ or $
  it('5. InviteAgencyModal renders localized budget ranges according to currency', async () => {
    // Check helper getBudgetRangeOptions directly
    const optionsEUR = getBudgetRangeOptions('EUR', 'en');
    optionsEUR.forEach(opt => {
      expect(opt.label).not.toContain('₹');
      if (opt.value !== 'Open / discuss') {
        expect(opt.label).toMatch(/€|EUR/);
      }
    });

    const optionsUSD = getBudgetRangeOptions('USD', 'en');
    optionsUSD.forEach(opt => {
      expect(opt.label).not.toContain('₹');
      if (opt.value !== 'Open / discuss') {
        expect(opt.label).toMatch(/\$|USD/);
      }
    });

    render(
      <MemoryRouter>
        <InviteAgencyModal
          open={true}
          targetAgency={{ id: 10, name: 'Alpha Creative Agency' }}
          onClose={jest.fn()}
          onSent={jest.fn()}
        />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Alpha Creative Agency')).toBeInTheDocument();
    });
  });

  // 6. ROICalculatorPage formats values according to selected/authoritative currency
  it('6. ROICalculatorPage displays and updates according to authoritative currency', async () => {
    render(
      <MemoryRouter>
        <ROICalculatorPage clientId={101} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Currency|Moneda/i)).toHaveValue('EUR');
    });

    // Est. Revenue and Total Invested should be formatted with EUR
    const totalInvestedElements = screen.getAllByText((content, element) =>
      element?.textContent?.includes('1,000') || element?.textContent?.includes('1.000')
    );
    expect(totalInvestedElements.length).toBeGreaterThan(0);
    expect(totalInvestedElements[0].textContent).toMatch(/€|EUR/);
  });

  // 7. Changing UI language does NOT alter currency
  it('7. changing language between en and es preserves currency code', async () => {
    render(
      <MemoryRouter>
        <ROICalculatorPage clientId={101} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Currency|Moneda/i)).toHaveValue('EUR');
    });

    // Change language to Spanish
    await act(async () => {
      await i18n.changeLanguage('es');
    });

    // Currency select must STILL be EUR
    expect(screen.getByLabelText(/Currency|Moneda/i)).toHaveValue('EUR');
  });

  // 8. TodayDashboard LeadsTile: single currency pipeline
  it('8. TodayDashboard LeadsTile displays single-currency pipeline total', () => {
    useDashboardToday.mockReturnValue({
      data: {
        client_id: 101,
        leads: {
          new_today: 5,
          qualified: 12,
          converted_today: 3,
          pipeline_value: 45000,
          currency: 'EUR',
          has_mixed_currencies: false,
        },
        client_currency: 'EUR',
      },
      isLoading: false,
      isError: false,
      refetch: jest.fn(),
    });

    render(
      <MemoryRouter>
        <TodayDashboard />
      </MemoryRouter>
    );

    expect(screen.getByText(/Pipeline/)).toBeInTheDocument();
    expect(screen.getByText(/45K|45.000|45,000/)).toBeInTheDocument();
  });

  // 9. TodayDashboard LeadsTile: mixed-currency pipeline protection
  it('9. TodayDashboard LeadsTile shows "Pipeline: Multiple currencies" when mixed currencies exist', () => {
    useDashboardToday.mockReturnValue({
      data: {
        client_id: 101,
        leads: {
          new_today: 8,
          qualified: 15,
          converted_today: 4,
          pipeline_value: null,
          has_mixed_currencies: true,
          pipeline_values_by_currency: {
            EUR: 25000,
            USD: 18000,
          },
        },
        client_currency: 'EUR',
      },
      isLoading: false,
      isError: false,
      refetch: jest.fn(),
    });

    render(
      <MemoryRouter>
        <TodayDashboard />
      </MemoryRouter>
    );

    expect(screen.getByText('Pipeline: Multiple currencies')).toBeInTheDocument();
  });

  // 10. ReportsPage renders reports using their snapshotted currency
  it('10. ReportsPage renders reports using each row snapshotted currency', async () => {
    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>
    );

    // Switch to ROI Reports tab
    const roiTab = screen.getByRole('button', { name: /roi reports/i });
    fireEvent.click(roiTab);

    // Row 1: EUR 3000
    await waitFor(() => {
      const eurMatch = screen.getByText((content) => content.includes('3,000') || content.includes('3.000'));
      expect(eurMatch).toBeInTheDocument();
      expect(eurMatch.textContent).toMatch(/€|EUR/);
    });

    // Row 2: GBP 2000
    const gbpMatch = screen.getByText((content) => content.includes('2,000') || content.includes('2.000'));
    expect(gbpMatch).toBeInTheDocument();
    expect(gbpMatch.textContent).toMatch(/£|GBP/);
  });

  // 11. AdminOverview renders reports using each row snapshotted currency
  it('11. AdminOverview renders reports using each row snapshotted currency', async () => {
    render(
      <MemoryRouter>
        <AdminOverview />
      </MemoryRouter>
    );

    await waitFor(() => {
      const eurReport = screen.getAllByText((content) => content.includes('3,000') || content.includes('3.000'));
      expect(eurReport.length).toBeGreaterThan(0);
      expect(eurReport[0].textContent).toMatch(/€|EUR/);
    });
  });
});
