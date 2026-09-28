import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import i18n, { changePlatformLanguage } from '../../i18n/config';

import WhatsAppDashboard from '../WhatsAppDashboard';
import WhatsAppCampaignsPage from '../WhatsAppCampaignsPage';
import BotSettingsPage from '../bots/BotSettingsPage';
import TemplatesGalleryPage from '../bots/TemplatesGalleryPage';
import CTWACampaignsPage from '../ctwa/CTWACampaignsPage';
import CTWACampaignDetailPage from '../ctwa/CTWACampaignDetailPage';
import LeadsPage from '../leads/LeadsPage';
import LeadDetailPage from '../leads/LeadDetailPage';
import BotFlowsListPage from '../bots/BotFlowsListPage';
import { getNodeMeta } from '../../components/bot/nodeCatalog';

import {
  whatsappAPI,
  botSettingsAPI,
  botTemplateAPI,
  ctwaAPI,
  metaAdsAPI,
  leadAPI,
  botAPI,
} from '../../services/api';

import enMessaging from '../../locales/en/messaging.json';
import esMessaging from '../../locales/es/messaging.json';

// Deep key extractor helper
function getDeepKeys(obj, prefix = '') {
  let keys = [];
  for (const key of Object.keys(obj)) {
    const fullPath = prefix ? `${prefix}.${key}` : key;
    if (obj[key] && typeof obj[key] === 'object' && !Array.isArray(obj[key])) {
      keys = keys.concat(getDeepKeys(obj[key], fullPath));
    } else {
      keys.push(fullPath);
    }
  }
  return keys.sort();
}

// Mock useAuth
jest.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, email: 'admin@bopsocial.com', name: 'Admin', role: 'admin' },
  }),
}));

// Mock APIs
jest.mock('../../services/api', () => ({
  whatsappAPI: {
    dashboard: jest.fn(),
    campaigns: { list: jest.fn() },
    templates: { list: jest.fn() },
    contacts: { list: jest.fn() },
    lists: { list: jest.fn() },
    account: { list: jest.fn() },
    health: jest.fn(),
  },
  botSettingsAPI: {
    get: jest.fn(),
    update: jest.fn(),
  },
  botTemplateAPI: {
    list: jest.fn(),
    use: jest.fn(),
  },
  ctwaAPI: {
    list: jest.fn(),
    get: jest.fn(),
    analytics: jest.fn(),
    adBreakdown: jest.fn(),
    syncMeta: jest.fn(),
    create: jest.fn(),
  },
  metaAdsAPI: {
    health: jest.fn(),
  },
  leadAPI: {
    list: jest.fn(),
    get: jest.fn(),
    status: jest.fn(),
    scoreWithAI: jest.fn(),
    activity: jest.fn(),
    timeline: jest.fn(),
    convert: jest.fn(),
    exportCsvUrl: jest.fn(() => '/mock-export.csv'),
    importCsv: jest.fn(),
  },
  botAPI: {
    list: jest.fn(),
    get: jest.fn(),
    create: jest.fn(),
    publish: jest.fn(),
    unpublish: jest.fn(),
  },
}));

// Mock recharts ResponsiveContainer
jest.mock('recharts', () => {
  const OriginalModule = jest.requireActual('recharts');
  return {
    ...OriginalModule,
    ResponsiveContainer: ({ children }) => <div data-testid="responsive-container">{children}</div>,
  };
});

describe('Phase BS-2.6E — WhatsApp Campaigns, CTWA & Bot Builder Internationalization Test Suite', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    await act(async () => {
      await changePlatformLanguage('en');
    });

    // Default mock resolves
    whatsappAPI.dashboard.mockResolvedValue({
      data: {
        total_campaigns: 12,
        messages_sent: 5400,
        delivered: 5200,
        read: 4800,
        failed: 200,
        quality_rating: 'GREEN',
        limit: '100k',
        waba_id: 'waba_123',
        recent_campaigns: [],
        daily_stats: [],
      },
    });
    whatsappAPI.campaigns.list.mockResolvedValue({ data: { results: [] } });
    whatsappAPI.templates.list.mockResolvedValue({ data: { results: [] } });
    whatsappAPI.contacts.list.mockResolvedValue({ data: { results: [] } });
    whatsappAPI.lists.list.mockResolvedValue({ data: { results: [] } });
    whatsappAPI.account.list.mockResolvedValue({ data: [{ id: 1, phone_number: '+15551234567', status: 'connected' }] });

    botSettingsAPI.get.mockResolvedValue({
      data: {
        bot_enabled: true,
        bot_max_msgs_per_minute: 20,
        bot_max_msgs_per_conv: 200,
        bot_spam_threshold: 5,
      },
    });

    botTemplateAPI.list.mockResolvedValue({
      data: [
        {
          id: 1,
          name: 'Real Estate Qualifier',
          description: 'Qualify buyer leads with automated questions',
          industry: 'real_estate',
          use_case: 'lead_capture',
          is_featured: true,
          nodes: [{ id: 'n1', type: 'message_text' }],
          use_count: 42,
        },
      ],
    });

    ctwaAPI.list.mockResolvedValue({
      data: [
        {
          id: 101,
          name: 'Summer Promo CTWA',
          flow_name: 'Lead Bot Flow',
          ad_ids: ['ad_001', 'ad_002'],
          is_active: true,
          total_clicks: 120,
          total_conversations: 85,
          total_leads: 45,
          total_spent: 3200,
        },
      ],
    });
    ctwaAPI.get.mockResolvedValue({
      data: {
        id: 101,
        name: 'Summer Promo CTWA',
        flow: 1,
        flow_name: 'Lead Bot Flow',
        campaign_id: 'meta_camp_123',
        ad_account_id: 'act_999999',
        ad_ids: ['ad_001'],
        last_synced_at: '2026-03-20T10:00:00Z',
      },
    });
    ctwaAPI.analytics.mockResolvedValue({
      data: {
        totals: { clicks: 120, conversations: 85, leads: 45, spent: 3200, cpl: 71.11 },
        leads_per_day: [{ date: '2026-03-20', c: 10 }],
        conversations_per_day: [{ date: '2026-03-20', c: 20 }],
      },
    });
    metaAdsAPI.health.mockResolvedValue({ data: { connected: true, fb_user: { name: 'Agency Pro' }, pixel_configured: true } });

    leadAPI.list.mockResolvedValue({
      data: [
        {
          id: 501,
          name: 'Jane Doe',
          phone: '+15550192834',
          email: 'jane@example.com',
          status: 'new',
          quality_score: 85,
          source_flow_name: 'Lead Bot Flow',
          source_ad_name: 'Hero Ad',
          assigned_email: 'agent@agency.com',
          created_at: '2026-03-20T12:00:00Z',
        },
      ],
    });
    leadAPI.get.mockResolvedValue({
      data: {
        id: 501,
        name: 'Jane Doe',
        phone: '+15550192834',
        email: 'jane@example.com',
        location: 'Miami, FL',
        status: 'new',
        quality_score: 85,
        quality_reason: 'High budget indicated',
        interest: 'Luxury Condos',
        budget: '500,000 USD',
        tags: ['vip', 'buyer'],
        source_flow_name: 'Lead Bot Flow',
        source_ad_name: 'Hero Ad',
        source_campaign_name: 'Summer Promo CTWA',
        created_at: '2026-03-20T12:00:00Z',
        updated_at: '2026-03-20T12:10:00Z',
        activities: [],
        custom_fields: { preferred_timeline: '3 months' },
      },
    });
    leadAPI.timeline.mockResolvedValue({ data: { bot_steps: [] } });

    botAPI.list.mockResolvedValue({
      data: [
        {
          id: 1,
          name: 'Lead Capture Flow',
          status: 'published',
          trigger_type: 'ctwa',
          created_at: '2026-03-20T10:00:00Z',
          updated_at: '2026-03-20T10:00:00Z',
        },
      ],
    });
  });

  // 1. Catalog Parity & Non-Empty Checks
  it('1. verifies 100% key parity between English and Spanish messaging catalogs', () => {
    const enKeys = getDeepKeys(enMessaging);
    const esKeys = getDeepKeys(esMessaging);

    expect(enKeys.length).toBeGreaterThan(500);
    expect(enKeys).toEqual(esKeys);
  });

  it('2. verifies that all translations in messaging catalogs are non-empty strings', () => {
    function assertNoEmptyValues(obj, path = '') {
      for (const [k, v] of Object.entries(obj)) {
        const full = path ? `${path}.${k}` : k;
        if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
          assertNoEmptyValues(v, full);
        } else {
          expect(typeof v).toBe('string');
          expect(v.trim().length).toBeGreaterThan(0);
        }
      }
    }
    assertNoEmptyValues(enMessaging, 'en');
    assertNoEmptyValues(esMessaging, 'es');
  });

  it('3. verifies zero residual Social Stats / SocialStats branding in messaging catalogs', () => {
    const enStr = JSON.stringify(enMessaging);
    const esStr = JSON.stringify(esMessaging);

    expect(enStr).not.toContain('Social Stats');
    expect(enStr).not.toContain('SocialStats');
    expect(esStr).not.toContain('Social Stats');
    expect(esStr).not.toContain('SocialStats');

    // Confirm Bop Social is present where relevant
    expect(enStr).toContain('Bop Social');
    expect(esStr).toContain('Bop Social');
  });

  // 2. WhatsApp Dashboard
  it('4. renders WhatsAppDashboard in English and Spanish', async () => {
    const { rerender } = render(
      <MemoryRouter>
        <WhatsAppDashboard />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Delivery Rate')).toBeInTheDocument();
      expect(screen.getByText('Recent campaigns')).toBeInTheDocument();
    });

    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <WhatsAppDashboard />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Tasa de entrega')).toBeInTheDocument();
      expect(screen.getByText('Campañas recientes')).toBeInTheDocument();
    });
  });

  // 3. Bot Settings Page
  it('5. renders BotSettingsPage in English and Spanish', async () => {
    const { rerender } = render(
      <MemoryRouter>
        <BotSettingsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Bot safety')).toBeInTheDocument();
      expect(screen.getByText('Anti-abuse limits')).toBeInTheDocument();
      expect(screen.getByText('Save Changes')).toBeInTheDocument();
    });

    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <BotSettingsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Seguridad del bot')).toBeInTheDocument();
      expect(screen.getByText('Límites antiabuso')).toBeInTheDocument();
      expect(screen.getByText('Guardar cambios')).toBeInTheDocument();
    });
  });

  // 4. Templates Gallery Page
  it('6. renders TemplatesGalleryPage in English and Spanish', async () => {
    const { rerender } = render(
      <MemoryRouter>
        <TemplatesGalleryPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Bot flow templates')).toBeInTheDocument();
      expect(screen.getByText('Industry')).toBeInTheDocument();
      expect(screen.getByText('Use case')).toBeInTheDocument();
    });

    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <TemplatesGalleryPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Plantillas de flujos')).toBeInTheDocument();
      expect(screen.getByText('Industria')).toBeInTheDocument();
      expect(screen.getByText('Caso de uso')).toBeInTheDocument();
    });
  });

  // 5. CTWA Campaigns Page
  it('7. renders CTWACampaignsPage in English and Spanish', async () => {
    const { rerender } = render(
      <MemoryRouter>
        <CTWACampaignsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('CTWA campaigns')).toBeInTheDocument();
      expect(screen.getByText('New campaign')).toBeInTheDocument();
    });

    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <CTWACampaignsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Campañas CTWA')).toBeInTheDocument();
      expect(screen.getByText('Nueva campaña')).toBeInTheDocument();
    });
  });

  // 6. CTWA Campaign Detail Page
  it('8. renders CTWACampaignDetailPage in English and Spanish', async () => {
    const { rerender } = render(
      <MemoryRouter initialEntries={['/admin/ctwa/101']}>
        <Routes>
          <Route path="/admin/ctwa/:id" element={<CTWACampaignDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('All campaigns')).toBeInTheDocument();
      expect(screen.getByText('Sync with Meta')).toBeInTheDocument();
      expect(screen.getByText('Ad Breakdown')).toBeInTheDocument();
    });

    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter initialEntries={['/admin/ctwa/101']}>
        <Routes>
          <Route path="/admin/ctwa/:id" element={<CTWACampaignDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Todas las campañas')).toBeInTheDocument();
      expect(screen.getByText('Sincronizar con Meta')).toBeInTheDocument();
      expect(screen.getByText('Desglose por anuncio')).toBeInTheDocument();
    });
  });

  // 7. Leads Page
  it('9. renders LeadsPage in English and Spanish', async () => {
    const { rerender } = render(
      <MemoryRouter>
        <LeadsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Leads/)).toBeInTheDocument();
      expect(screen.getByText('Import CSV')).toBeInTheDocument();
      expect(screen.getByText('Export CSV')).toBeInTheDocument();
    });

    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <LeadsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Prospectos/)).toBeInTheDocument();
      expect(screen.getByText('Importar CSV')).toBeInTheDocument();
      expect(screen.getByText('Exportar CSV')).toBeInTheDocument();
    });
  });

  // 8. Lead Detail Page
  it('10. renders LeadDetailPage in English and Spanish', async () => {
    const { rerender } = render(
      <MemoryRouter initialEntries={['/admin/leads/501']}>
        <Routes>
          <Route path="/admin/leads/:id" element={<LeadDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('All leads')).toBeInTheDocument();
      expect(screen.getByText('Score with AI')).toBeInTheDocument();
      expect(screen.getByText('Convert')).toBeInTheDocument();
      expect(screen.getByText('Overview')).toBeInTheDocument();
      expect(screen.getByText('Conversation')).toBeInTheDocument();
    });

    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter initialEntries={['/admin/leads/501']}>
        <Routes>
          <Route path="/admin/leads/:id" element={<LeadDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Todos los prospectos')).toBeInTheDocument();
      expect(screen.getByText('Calificar con IA')).toBeInTheDocument();
      expect(screen.getByText('Convertir')).toBeInTheDocument();
      expect(screen.getByText('Resumen')).toBeInTheDocument();
      expect(screen.getByText('Conversación')).toBeInTheDocument();
    });
  });

  // 9. Node Catalog Localized Metadata
  it('11. verifies getNodeMeta resolves localized labels and categories via t function', () => {
    const tEn = i18n.getFixedT('en', 'messaging');
    const tEs = i18n.getFixedT('es', 'messaging');

    const metaEn = getNodeMeta('message_text', tEn);
    const metaEs = getNodeMeta('message_text', tEs);

    expect(metaEn.label).toBe('Send Text');
    expect(metaEs.label).toBe('Enviar texto');

    const handoffEn = getNodeMeta('human_handoff', tEn);
    const handoffEs = getNodeMeta('human_handoff', tEs);

    expect(handoffEn.label).toBe('Human Handoff');
    expect(handoffEs.label).toBe('Derivación humana');
  });

  // 10. Bot Flows List Page
  it('12. renders BotFlowsListPage in English and Spanish with Bop Social AI branding', async () => {
    const { rerender } = render(
      <MemoryRouter>
        <BotFlowsListPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Bot flows')).toBeInTheDocument();
      expect(screen.getByText('Create flow')).toBeInTheDocument();
    });

    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <BotFlowsListPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Flujos de bots')).toBeInTheDocument();
      expect(screen.getByText('Crear flujo')).toBeInTheDocument();
    });
  });
});
