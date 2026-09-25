import React from 'react';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n, { changePlatformLanguage } from '../../i18n/config';

import AIStudio from '../ai/AIStudio';
import BrandVoicePage from '../ai/BrandVoicePage';
import AIInsightsPage from '../ai/AIInsightsPage';
import AIUsagePage from '../ai/AIUsagePage';
import AIChatHistoryPage from '../ai/AIChatHistoryPage';
import AIAuditPage from '../ai/AIAuditPage';
import AIChatPanel from '../../components/ai/AIChatPanel';
import AIBadge from '../../components/ai/AIBadge';
import AILoading from '../../components/ai/AILoading';
import TodayBriefing from '../../components/ai/TodayBriefing';
import ChartAnnotations from '../../components/ai/ChartAnnotations';

import { useAuth } from '../../hooks/useAuth';
import { useClients, useLookups } from '../../hooks/useData';
import { aiV2API, captionAPI, hashtagAPI, postIdeasAPI } from '../../services/api';

import enAi from '../../locales/en/ai.json';
import esAi from '../../locales/es/ai.json';

// Helper for recursive key extraction
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

// Mock auth & data hooks
jest.mock('../../hooks/useAuth', () => ({
  useAuth: jest.fn(),
}));

jest.mock('../../hooks/useData', () => ({
  useClients: jest.fn(),
  useLookups: jest.fn(),
}));

// Mock API calls to ensure zero live AI inference calls
jest.mock('../../services/api', () => ({
  aiV2API: {
    brandVoiceGet: jest.fn(),
    brandVoiceTrain: jest.fn(),
    brandVoiceTest: jest.fn(),
    brandVoiceStatus: jest.fn(),
    insightsList: jest.fn(),
    insightGenerate: jest.fn(),
    insightDismiss: jest.fn(),
    usageOverview: jest.fn(),
    usageByClient: jest.fn(),
    usageByUser: jest.fn(),
    usageSummary: jest.fn(),
    audit: jest.fn(),
    chatConversations: jest.fn(),
    chatThread: jest.fn(),
    chatSend: jest.fn(),
    chatDelete: jest.fn(),
    chatArchive: jest.fn(),
    todayBriefing: jest.fn(),
    reportNarrate: jest.fn(),
  },
  captionAPI: {
    getHistory: jest.fn(),
    generate: jest.fn(),
  },
  hashtagAPI: {
    getHistory: jest.fn(),
    research: jest.fn(),
    saveSet: jest.fn(),
  },
  postIdeasAPI: {
    getHistory: jest.fn(),
    generate: jest.fn(),
    approveAll: jest.fn(),
    updateIdea: jest.fn(),
    addToCalendar: jest.fn(),
  },
}));

describe('Phase BS-2.6C: AI Studio & Advanced Creation Tools Internationalization', () => {
  const mockUser = {
    id: 1,
    client_id: 10,
    first_name: 'Alex',
    role: 'superadmin',
  };

  beforeEach(() => {
    jest.clearAllMocks();

    useAuth.mockReturnValue({
      user: mockUser,
    });

    useClients.mockReturnValue({
      clients: [{ id: 10, company: 'Acme Corp' }],
    });

    useLookups.mockReturnValue({
      lookups: {},
    });

    // Default mock resolves
    aiV2API.brandVoiceGet.mockResolvedValue({
      data: {
        training_status: 'ready',
        trained: true,
        last_trained_at: '2026-09-20T10:00:00Z',
        profile: {
          persona: 'Friendly brand guide',
          tone: 'Conversational',
          target_audience: 'Modern creators',
          vocabulary: ['innovative', 'sparkle'],
          avoid: ['cheap', 'spam'],
          style_rules: ['Short sentences'],
          hashtags: 'minimal',
        },
        sample_posts: ['Sample post one', 'Sample post two', 'Sample post three'],
      },
    });

    aiV2API.usageOverview.mockResolvedValue({
      data: {
        period: 'month',
        totals: {
          cost_usd: 12.45,
          requests: 150,
          input_tokens: 45000,
          output_tokens: 12000,
          cached_requests: 30,
          errors: 0,
        },
        budget: { cap_usd: 50.0, used_usd: 12.45, remaining_usd: 37.55, percent: 24.9 },
        by_feature: [{ feature: 'caption_writer', cost_usd: 5.2, requests: 80, input_tokens: 20000, output_tokens: 5000 }],
      },
    });

    aiV2API.usageByClient.mockResolvedValue({ data: { clients: [] } });
    aiV2API.usageByUser.mockResolvedValue({ data: { users: [] } });

    aiV2API.insightsList.mockResolvedValue({
      data: {
        insights: [
          {
            id: 'ins-1',
            title: 'Instagram engagement surge',
            description: 'Post frequency drove +22% comments.',
            severity: 'high',
            confidence: 0.92,
            action_recommended: 'Schedule follow-up post tomorrow.',
            dismissed: false,
          },
        ],
      },
    });

    aiV2API.usageSummary.mockResolvedValue({
      data: {
        period: 'month',
        cost_total_usd: 12.45,
        total_requests: 150,
        input_tokens: 45000,
        output_tokens: 12000,
        cached_requests: 30,
        errors_count: 0,
        budget: { cap_usd: 50.0, used_usd: 12.45, percent: 24.9 },
        by_feature: [{ feature: 'caption_writer', cost_usd: 5.2, requests: 80, input_tokens: 20000, output_tokens: 5000 }],
        top_clients: [],
        top_users: [],
        daily_activity: [],
      },
    });

    aiV2API.audit.mockResolvedValue({
      data: {
        rows: [
          {
            id: 1,
            feature: 'caption_writer',
            status: 'success',
            model: 'gemini-1.5-flash',
            input_tokens: 300,
            output_tokens: 150,
            cost_usd: 0.0012,
            created_at: '2026-09-25T11:00:00Z',
          },
        ],
        by_feature: [{ feature: 'caption_writer', count: 1 }],
        quota: { used: 15, limit: 100, remaining: 85, percent: 15 },
      },
    });

    aiV2API.chatConversations.mockResolvedValue({
      data: {
        conversations: [
          { id: 'conv-1', title: 'Marketing campaign brainstorm', updated_at: '2026-09-25T10:00:00Z', archived: false },
        ],
      },
    });

    aiV2API.todayBriefing.mockResolvedValue({
      data: {
        items: [
          {
            id: 'brief-1',
            title: 'Audience peak active time',
            description: 'Post between 6pm and 8pm.',
            severity: 'medium',
            insight_type: 'engagement_trend',
            action_recommended: 'Queue posts for evening.',
          },
        ],
      },
    });
  });

  afterEach(async () => {
    await act(async () => {
      await changePlatformLanguage('en');
    });
  });

  test('ai.json catalog maintains 100% key parity between English and Spanish', () => {
    const enKeys = getDeepKeys(enAi);
    const esKeys = getDeepKeys(esAi);

    const missingInEs = enKeys.filter(k => !esKeys.includes(k));
    const extraInEs = esKeys.filter(k => !enKeys.includes(k));

    expect(missingInEs).toEqual([]);
    expect(extraInEs).toEqual([]);
    expect(enKeys.length).toBeGreaterThan(100);
  });

  test('AIStudio renders with translated headings and cards in EN and ES', async () => {
    await act(async () => {
      await changePlatformLanguage('en');
    });

    const { rerender } = render(
      <MemoryRouter>
        <AIStudio basePath="/admin" />
      </MemoryRouter>
    );

    expect(screen.getByText('Bop Social Studio')).toBeInTheDocument();
    expect(screen.getByText('Brand Voice')).toBeInTheDocument();
    expect(screen.getByText('AI Insights')).toBeInTheDocument();
    expect(screen.getByText('Chat History')).toBeInTheDocument();

    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <AIStudio basePath="/admin" />
      </MemoryRouter>
    );

    expect(screen.getByText('Estudio Bop Social')).toBeInTheDocument();
    expect(screen.getByText('Voz de marca')).toBeInTheDocument();
    expect(screen.getByText('Hallazgos de IA')).toBeInTheDocument();
    expect(screen.getByText('Historial de chat')).toBeInTheDocument();
  });

  test('BrandVoicePage renders in EN and ES with zero residual Social Stats branding', async () => {
    await act(async () => {
      await changePlatformLanguage('en');
    });

    const { container, rerender } = render(
      <MemoryRouter>
        <BrandVoicePage clientId={10} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Brand Voice')).toBeInTheDocument();
    });

    // Check branding
    expect(container.textContent).not.toContain('Social Stats');
    expect(container.textContent).not.toContain('SocialStats');

    // Check Spanish translation
    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <BrandVoicePage clientId={10} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Voz de marca')).toBeInTheDocument();
      expect(screen.getByText('Lista')).toBeInTheDocument();
    });

    expect(container.textContent).not.toContain('Social Stats');
    expect(container.textContent).not.toContain('SocialStats');
  });

  test('AIAuditPage renders translated quota and compliance disclaimer without residual branding', async () => {
    await act(async () => {
      await changePlatformLanguage('en');
    });

    const { container, rerender } = render(
      <MemoryRouter>
        <AIAuditPage clientId={10} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('What did Bop Social do for me?')).toBeInTheDocument();
      expect(screen.getByText("Today's AI quota")).toBeInTheDocument();
    });

    // Verify disclaimer
    expect(container.textContent).toContain('Bop Social powers every request below');
    expect(container.textContent).not.toContain('SocialStats');
    expect(container.textContent).not.toContain('Social Stats');

    // Switch to Spanish
    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <AIAuditPage clientId={10} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('¿Qué hizo Bop Social por mí?')).toBeInTheDocument();
      expect(screen.getByText('Cuota de IA de hoy')).toBeInTheDocument();
    });

    expect(container.textContent).toContain('Bop Social impulsa cada una de las solicitudes');
    expect(container.textContent).not.toContain('SocialStats');
    expect(container.textContent).not.toContain('Social Stats');
  });

  test('AIUsagePage renders metrics and table in EN and ES', async () => {
    await act(async () => {
      await changePlatformLanguage('en');
    });

    const { rerender } = render(
      <MemoryRouter>
        <AIUsagePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('AI Usage')).toBeInTheDocument();
      expect(screen.getByText('Monthly budget')).toBeInTheDocument();
    });

    // Switch to Spanish
    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <AIUsagePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Uso de IA')).toBeInTheDocument();
      expect(screen.getByText('Presupuesto mensual')).toBeInTheDocument();
    });
  });

  test('AIBadge and AILoading render localized text and Bop Social branding', async () => {
    await act(async () => {
      await changePlatformLanguage('en');
    });

    const { getByTitle, rerender } = render(
      <div>
        <AIBadge />
        <AILoading />
      </div>
    );

    expect(getByTitle('This content was generated with Bop Social assistance')).toBeInTheDocument();
    expect(screen.getByLabelText('Bop Social is thinking…')).toBeInTheDocument();

    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <div>
        <AIBadge />
        <AILoading />
      </div>
    );

    expect(getByTitle('Este contenido fue generado con la asistencia de Bop Social')).toBeInTheDocument();
    expect(screen.getByLabelText('Bop Social está pensando…')).toBeInTheDocument();
  });

  test('TodayBriefing and ChartAnnotations render correctly with translated action buttons', async () => {
    await act(async () => {
      await changePlatformLanguage('en');
    });

    const { rerender } = render(
      <MemoryRouter>
        <TodayBriefing clientId={10} />
        <ChartAnnotations clientId={10} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Today's briefing")).toBeInTheDocument();
      expect(screen.getByText('What this data means')).toBeInTheDocument();
      expect(screen.getByText('From Bop Social')).toBeInTheDocument();
    });

    await act(async () => {
      await changePlatformLanguage('es');
    });

    rerender(
      <MemoryRouter>
        <TodayBriefing clientId={10} />
        <ChartAnnotations clientId={10} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Resumen de hoy')).toBeInTheDocument();
      expect(screen.getByText('¿Qué significan estos datos?')).toBeInTheDocument();
      expect(screen.getByText('De Bop Social')).toBeInTheDocument();
    });
  });
});
