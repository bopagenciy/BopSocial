/* ============================================================================
 *  Bop Social — Phase BS-2.7C: CTWA & Meta Ads Multi-Currency Test Suite
 * ============================================================================ */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import i18n from '../../../i18n/config';

import CTWACampaignsPage from '../CTWACampaignsPage';
import CTWACampaignDetailPage from '../CTWACampaignDetailPage';
import { ctwaAPI, botAPI, metaAdsAPI } from '../../../services/api';
import enMessaging from '../../../locales/en/messaging.json';
import esMessaging from '../../../locales/es/messaging.json';

// Mock API services
jest.mock('../../../services/api', () => ({
  ctwaAPI: {
    list: jest.fn(),
    get: jest.fn(),
    create: jest.fn(),
    analytics: jest.fn(),
    syncMeta: jest.fn(),
    adBreakdown: jest.fn(),
  },
  botAPI: {
    list: jest.fn(),
  },
  metaAdsAPI: {
    health: jest.fn(),
    accounts: jest.fn(),
  },
}));

jest.mock('../../../components/ui/toast', () => ({
  error: jest.fn(),
  success: jest.fn(),
}));

describe('Phase BS-2.7C: CTWA & Meta Ads Multi-Currency Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    i18n.changeLanguage('en');

    metaAdsAPI.health.mockResolvedValue({
      data: { connected: true, fb_user: { name: 'Ad Manager' } },
    });
    metaAdsAPI.accounts.mockResolvedValue({
      data: {
        connected: true,
        accounts: [
          { id: 'act_101', name: 'US Main Account', currency: 'USD' },
          { id: 'act_202', name: 'Colombia Ads', currency: 'COP' },
        ],
      },
    });
    botAPI.list.mockResolvedValue({
      data: [{ id: 1, name: 'Lead Gen Flow', is_active: true }],
    });
  });

  // ── 1. USD Campaign Formatting ──────────────────────────────────────────────
  it('1. formats USD campaign spend and CPL accurately', async () => {
    ctwaAPI.list.mockResolvedValue({
      data: [
        {
          id: 1,
          name: 'Miami Real Estate',
          flow: 1,
          flow_name: 'Lead Gen Flow',
          currency: 'USD',
          total_clicks: 120,
          total_conversations: 40,
          total_leads: 10,
          total_spent: 350.0,
          is_active: true,
          ad_ids: ['ad_1', 'ad_2'],
        },
      ],
    });

    const { container } = render(
      <MemoryRouter>
        <CTWACampaignsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Miami Real Estate')).toBeInTheDocument();
    });

    // Check no ₹ exists
    expect(container.textContent).not.toContain('₹');

    // Single USD currency spend roll-up & card spend
    expect(screen.getByTestId('ctwa-single-currency-spent').textContent).toMatch(/\$350/);
    expect(container.textContent).toMatch(/\$35\.00|\$35/); // CPL 350/10 = 35
  });

  // ── 2. COP Campaign Formatting ──────────────────────────────────────────────
  it('2. formats COP campaign spend without Rupee residuals', async () => {
    ctwaAPI.list.mockResolvedValue({
      data: [
        {
          id: 2,
          name: 'Bogota Fitness',
          flow: 1,
          flow_name: 'Lead Gen Flow',
          currency: 'COP',
          total_clicks: 500,
          total_conversations: 200,
          total_leads: 50,
          total_spent: 500000.0,
          is_active: true,
          ad_ids: ['ad_cop_1'],
        },
      ],
    });

    const { container } = render(
      <MemoryRouter>
        <CTWACampaignsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Bogota Fitness')).toBeInTheDocument();
    });

    expect(container.textContent).not.toContain('₹');
    // Compact notation for 500K COP
    expect(container.textContent).toMatch(/500\s?K|500\.000|500,000/);
  });

  // ── 3. EUR Campaign Formatting on Detail Page ──────────────────────────────
  it('3. formats EUR campaign and per-ad breakdown with Euro symbol', async () => {
    ctwaAPI.get.mockResolvedValue({
      data: {
        id: 3,
        name: 'Madrid Luxury Villas',
        flow: 1,
        flow_name: 'Lead Gen Flow',
        currency: 'EUR',
        total_clicks: 80,
        total_conversations: 25,
        total_leads: 5,
        total_spent: 1250.0,
        is_active: true,
        ad_ids: ['ad_eur_1'],
      },
    });

    ctwaAPI.analytics.mockResolvedValue({
      data: {
        totals: {
          clicks: 80,
          conversations: 25,
          leads: 5,
          spent: 1250.0,
          cpl: 250.0,
          currency: 'EUR',
        },
        leads_per_day: [],
        conversations_per_day: [],
      },
    });

    ctwaAPI.adBreakdown.mockResolvedValue({
      data: {
        ok: true,
        currency: 'EUR',
        ads: [
          {
            ad_id: 'ad_eur_1',
            ad_name: 'Villa Ad Madrid',
            spend: 1250.0,
            clicks: 80,
            impressions: 1200,
            ctr: 6.67,
            cpc: 15.63,
            currency: 'EUR',
          },
        ],
      },
    });

    const { container } = render(
      <MemoryRouter initialEntries={['/admin/ctwa/3']}>
        <Routes>
          <Route path="/admin/ctwa/:id" element={<CTWACampaignDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Madrid Luxury Villas')).toBeInTheDocument();
    });

    // Zero Rupee in EUR campaign detail
    expect(container.textContent).not.toContain('₹');

    // EUR formatting on KPI cards
    expect(container.textContent).toMatch(/€1,250\.00|1[.\s]250,00\s?€/);

    // Fetch and check ad breakdown
    const fetchBtn = screen.getByRole('button', { name: /fetch ad breakdown|cargar métricas/i });
    fireEvent.click(fetchBtn);

    await waitFor(() => {
      expect(screen.getByText('Villa Ad Madrid')).toBeInTheDocument();
    });

    expect(container.textContent).not.toContain('₹');
    expect(container.textContent).toMatch(/€15\.63|15,63\s?€/);
  });

  // ── 4. Mixed-Currency Total Roll-Up Protection ─────────────────────────────
  it('4. displays separate totals and suppresses combined CPL when currencies are mixed', async () => {
    ctwaAPI.list.mockResolvedValue({
      data: [
        {
          id: 10,
          name: 'US Campaign',
          flow: 1,
          flow_name: 'Flow',
          currency: 'USD',
          total_clicks: 100,
          total_conversations: 30,
          total_leads: 10,
          total_spent: 100.0,
          is_active: true,
        },
        {
          id: 20,
          name: 'Colombia Campaign',
          flow: 1,
          flow_name: 'Flow',
          currency: 'COP',
          total_clicks: 200,
          total_conversations: 80,
          total_leads: 20,
          total_spent: 500000.0,
          is_active: true,
        },
      ],
    });

    const { container } = render(
      <MemoryRouter>
        <CTWACampaignsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('US Campaign')).toBeInTheDocument();
      expect(screen.getByText('Colombia Campaign')).toBeInTheDocument();
    });

    // CRITICAL: NEVER display 500,100 as a single aggregated currency!
    expect(container.textContent).not.toContain('500,100');
    expect(container.textContent).not.toContain('500100');
    expect(container.textContent).not.toContain('₹');

    // Both distinct currency totals must be rendered in the mixed spend tile
    const mixedSpentTile = screen.getByTestId('ctwa-mixed-currency-spent');
    expect(mixedSpentTile).toBeInTheDocument();
    expect(mixedSpentTile.textContent).toMatch(/\$100/);
    expect(mixedSpentTile.textContent).toMatch(/500\s?K|500\.000|500,000/);

    // Mixed CPL notice must be shown instead of a meaningless combined average
    const mixedCplNotice = screen.getByTestId('ctwa-mixed-cpl-notice');
    expect(mixedCplNotice).toBeInTheDocument();
    expect(mixedCplNotice.textContent).toMatch(/Mixed currencies|Monedas múltiples/i);
  });

  // ── 5. Individual Campaign Values Remain Visible ───────────────────────────
  it('5. preserves individual campaign values even when roll-up is mixed', async () => {
    ctwaAPI.list.mockResolvedValue({
      data: [
        {
          id: 101,
          name: 'Europe Expansion',
          flow: 1,
          flow_name: 'Flow',
          currency: 'EUR',
          total_clicks: 50,
          total_conversations: 20,
          total_leads: 5,
          total_spent: 800.0,
          is_active: true,
        },
        {
          id: 102,
          name: 'Brazil Expansion',
          flow: 1,
          flow_name: 'Flow',
          currency: 'BRL',
          total_clicks: 80,
          total_conversations: 30,
          total_leads: 8,
          total_spent: 2400.0,
          is_active: true,
        },
      ],
    });

    render(
      <MemoryRouter>
        <CTWACampaignsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Europe Expansion')).toBeInTheDocument();
      expect(screen.getByText('Brazil Expansion')).toBeInTheDocument();
    });

    // Individual cards maintain their distinct metrics
    expect(screen.getAllByText(/€800|800\s?€/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/2\.4K|2,4K|2[.,\s]400/i).length).toBeGreaterThanOrEqual(1);
  });

  // ── 6. UI Language Switch Preserves Campaign Currencies ─────────────────────
  it('6. preserves campaign currency across English and Spanish UI toggles', async () => {
    ctwaAPI.list.mockResolvedValue({
      data: [
        {
          id: 201,
          name: 'Global Campaign COP',
          flow: 1,
          flow_name: 'Flow',
          currency: 'COP',
          total_clicks: 10,
          total_conversations: 5,
          total_leads: 2,
          total_spent: 100000.0,
          is_active: true,
        },
      ],
    });

    const { rerender, container } = render(
      <MemoryRouter>
        <CTWACampaignsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Global Campaign COP')).toBeInTheDocument();
    });
    expect(container.textContent).toMatch(/100\s?K|100\.000/);

    // Switch UI to Spanish
    i18n.changeLanguage('es');

    rerender(
      <MemoryRouter>
        <CTWACampaignsPage />
      </MemoryRouter>
    );

    // Campaign currency is still COP (formatted in Spanish locale)
    expect(container.textContent).toMatch(/100\s?K|100\s?mil|100\.000/i);
    expect(container.textContent).not.toContain('₹');
  });

  // ── 7. Messaging Catalog Parity & Rupee Eradication ─────────────────────────
  it('7. verifies messaging catalog parity and absence of hardcoded Rupee in CTWA keys', () => {
    // Both locales must define the new mixed-currency keys
    expect(enMessaging.ctwa.stats.multiple_currencies).toBeDefined();
    expect(esMessaging.ctwa.stats.multiple_currencies).toBeDefined();
    expect(enMessaging.ctwa.stats.mixed_cpl_notice).toBeDefined();
    expect(esMessaging.ctwa.stats.mixed_cpl_notice).toBeDefined();

    // Check no ₹ in ctwa strings
    expect(enMessaging.ctwa.detail.synced_success).not.toContain('₹');
    expect(esMessaging.ctwa.detail.synced_success).not.toContain('₹');
    expect(enMessaging.ctwa.card.spent).not.toContain('₹');
    expect(esMessaging.ctwa.card.spent).not.toContain('₹');
  });
});
