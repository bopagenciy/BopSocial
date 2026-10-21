/* ============================================================================
 *  Bop Social — Interaction & Engagement Translation Verification Tests (BS-2.5)
 *  Verifies English and Spanish internationalization for:
 *  - UnifiedInboxPage
 *  - ReviewsPage
 *  - AutomationsPage
 *  - AIReplySuggestions
 *  - WhatsAppInboxPage
 *  - Customer Content & Reviewer Integrity (never modifying user messages)
 *  - BS-2.4 Residual Closures (AIWriteButton & Calendar formatMonthYear)
 * ========================================================================== */
import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n, { changePlatformLanguage } from '../../i18n/config';
import UnifiedInboxPage from '../inbox/UnifiedInboxPage';
import ReviewsPage from '../inbox/ReviewsPage';
import AutomationsPage from '../automations/AutomationsPage';
import AIReplySuggestions from '../../components/ai/AIReplySuggestions';
import WhatsAppInboxPage from '../WhatsAppInboxPage';
import AIWriteButton from '../../components/ai/AIWriteButton';
import { formatMonthYear } from '../../utils/formatters';
import { automationsAPI, aiV2API, inboxAPI, whatsappAPI } from '../../services/api';

// Mock API modules
jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {},
  inboxAPI: {
    conversations: {
      markRead: jest.fn(),
      reply: jest.fn(),
      star: jest.fn(),
      unstar: jest.fn(),
      archive: jest.fn(),
      unarchive: jest.fn(),
      resolve: jest.fn(),
      reopen: jest.fn(),
    },
    reviews: {
      reply: jest.fn(),
      flag: jest.fn(),
    },
  },
  automationsAPI: {
    list: jest.fn(),
    templates: jest.fn(),
    toggle: jest.fn(),
    delete: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
  },
  aiV2API: {
    replySuggest: jest.fn(),
  },
  whatsappAPI: {
    send: jest.fn(),
  },
}));

// Mock useInbox hooks directly so components render synchronously with data
jest.mock('../../hooks/useInbox', () => ({
  useConversations: () => ({
    data: [
      {
        id: 101,
        contact_name: 'Customer Alice',
        contact_handle: 'alice_in_wonderland',
        platform: 'instagram',
        type: 'comment',
        sentiment: 'positive',
        unread_count: 2,
        is_starred: true,
        is_archived: false,
        is_resolved: false,
        last_message_preview: 'I absolutely love your new product release!',
        last_message_at: '2026-09-24T10:00:00Z',
      },
    ],
    loading: false,
    refetch: jest.fn(),
  }),
  useConversation: () => ({
    data: {
      id: 101,
      contact_name: 'Customer Alice',
      contact_handle: 'alice_in_wonderland',
      platform: 'instagram',
      type: 'comment',
      sentiment: 'positive',
      unread_count: 0,
      is_starred: true,
      is_archived: false,
      is_resolved: false,
      messages: [
        {
          id: 5001,
          direction: 'inbound',
          author_name: 'Customer Alice',
          content: 'Hello, can you help me with my order #12345?',
          sentiment: 'positive',
          created_at: '2026-09-24T10:00:00Z',
          ai_suggested_reply: 'Hi Alice! We would love to help you with order #12345.',
        },
      ],
    },
    loading: false,
    refetch: jest.fn(),
  }),
  useReviews: () => ({
    data: [
      {
        id: 201,
        reviewer_name: 'Carlos Mendoza',
        reviewer_avatar_url: null,
        rating: 5,
        sentiment: 'positive',
        status: 'new',
        comment: 'Excelente servicio al cliente y entrega rápida!',
        created_at_platform: '2026-09-20T12:00:00Z',
        reply_text: null,
      },
    ],
    loading: false,
    refetch: jest.fn(),
  }),
  useInboxStats: () => ({
    data: null,
    loading: false,
    refetch: jest.fn(),
  }),
}));

// Mock useWhatsApp
jest.mock('../../hooks/useWhatsApp', () => ({
  useWhatsAppInbox: () => ({
    data: [
      {
        contact: { id: 10, name: 'Valeria WhatsApp', phone: '+1234567890' },
        last_message: { preview: 'Hola, tengo una pregunta sobre el producto', timestamp: '2026-09-24T10:00:00Z', direction: 'inbound' },
        within_24h: true,
        unread_count: 1,
      },
    ],
    loading: false,
    refetch: jest.fn(),
  }),
  useWhatsAppThread: () => ({
    data: {
      contact: { id: 10, name: 'Valeria WhatsApp', phone: '+1234567890', within_24h_window: true },
      messages: [
        {
          id: 1,
          payload: { body: 'Hola, tengo una pregunta sobre el producto' },
          direction: 'inbound',
          created_at: '2026-09-24T10:00:00Z',
        },
      ],
    },
    loading: false,
    refetch: jest.fn(),
  }),
}));

// Mock useAuth
jest.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, email: 'agency@demo.local', role: 'agency', client_id: 1, company: 'Demo Agency' },
  }),
}));

describe('Phase BS-2.5: Interaction & Engagement Translation', () => {
  beforeEach(async () => {
    automationsAPI.list.mockResolvedValue({
      data: [
        {
          id: 301,
          name: 'Auto-thank 5 stars',
          is_active: true,
          run_count: 14,
          trigger_type: 'new_review',
          action_type: 'auto_reply',
          last_run_at: '2026-09-24T09:30:00Z',
        },
      ],
    });
    automationsAPI.templates.mockResolvedValue({
      data: {
        templates: [
          {
            name: 'Auto-thank for 5-star reviews',
            description: 'Posts a friendly thank-you reply on every new 5★ Google review.',
            trigger_type: 'new_review',
            trigger_filters: { min_rating: 5, max_rating: 5 },
            action_type: 'auto_reply',
            action_config: { template: 'Thank you so much for the kind words, {reviewer_name}! 🙏' },
          },
          {
            name: 'Alert me on negative sentiment',
            description: 'Sends an in-app notification whenever a comment or DM is flagged negative.',
            trigger_type: 'negative_sentiment',
            trigger_filters: {},
            action_type: 'notify',
            action_config: { title: 'Heads up — negative sentiment detected', body: '{author_name} on {platform}: "{content}"' },
          },
          {
            name: 'AI smart-reply to comments',
            description: 'Automatically writes an on-brand reply to every new comment using Claude.',
            trigger_type: 'new_comment',
            trigger_filters: {},
            action_type: 'ai_smart_reply',
            action_config: {},
          },
          {
            name: 'Tag urgent keywords',
            description: 'Tags conversations whose content mentions "urgent", "asap", or "broken".',
            trigger_type: 'keyword_mention',
            trigger_filters: { keywords: ['urgent', 'asap', 'broken'] },
            action_type: 'add_tag',
            action_config: { tag: 'priority' },
          },
          {
            name: 'Webhook on new DM',
            description: 'POSTs a JSON payload to your webhook URL whenever a new direct message arrives.',
            trigger_type: 'new_dm',
            trigger_filters: {},
            action_type: 'webhook',
            action_config: { url: 'https://your-webhook.example/incoming' },
          },
          {
            name: 'Assign 1-2★ reviews to support lead',
            description: 'Routes low-rating reviews to a specific user (configure user_id).',
            trigger_type: 'new_review',
            trigger_filters: { min_rating: 1, max_rating: 2 },
            action_type: 'notify',
            action_config: { title: '1-2★ review needs attention', body: '{reviewer_name}: "{content}"' },
          },
        ],
      },
    });
    aiV2API.replySuggest.mockResolvedValue({
      data: {
        suggestions: [
          { text: 'Thanks for reaching out! We are on it.', tone: 'friendly', recommended: true },
          { text: 'Thank you for your inquiry regarding order #12345.', tone: 'professional' },
        ],
        summary: 'Customer asking for order assistance',
      },
    });

    inboxAPI.conversations.markRead.mockResolvedValue({ data: {} });
    inboxAPI.conversations.reply.mockResolvedValue({ data: {} });
    inboxAPI.conversations.star.mockResolvedValue({ data: {} });
    inboxAPI.conversations.unstar.mockResolvedValue({ data: {} });
    inboxAPI.conversations.archive.mockResolvedValue({ data: {} });
    inboxAPI.conversations.unarchive.mockResolvedValue({ data: {} });
    inboxAPI.conversations.resolve.mockResolvedValue({ data: {} });
    inboxAPI.conversations.reopen.mockResolvedValue({ data: {} });
    inboxAPI.reviews.reply.mockResolvedValue({ data: {} });
    inboxAPI.reviews.flag.mockResolvedValue({ data: {} });
    whatsappAPI.send.mockResolvedValue({ data: { success: true } });

    await act(async () => {
      await changePlatformLanguage('en');
    });
  });

  afterAll(async () => {
    await act(async () => {
      await changePlatformLanguage('en');
    });
  });

  describe('BS-2.4 Residual Closures', () => {
    test('Calendar month formatting produces lowercase preposition in Spanish (Septiembre de 2026)', () => {
      const enMonth = formatMonthYear('2026-09-15', 'en');
      const esMonth = formatMonthYear('2026-09-15', 'es');

      expect(enMonth).toBe('September 2026');
      expect(esMonth).toBe('Septiembre de 2026');
      expect(esMonth).not.toBe('Septiembre De 2026');
    });

    test('AIWriteButton renders localized label in English and Spanish', async () => {
      const { rerender } = render(<AIWriteButton onGenerate={jest.fn()} />);
      expect(screen.getByText('Write with AI')).toBeInTheDocument();

      await act(async () => {
        await changePlatformLanguage('es');
      });
      rerender(<AIWriteButton onGenerate={jest.fn()} />);
      expect(screen.getByText('Escribir con IA')).toBeInTheDocument();
    });
  });

  describe('UnifiedInboxPage', () => {
    test('renders filters, sections, and preserves customer message in English', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      await act(async () => {
        render(
          <MemoryRouter>
            <UnifiedInboxPage />
          </MemoryRouter>
        );
      });

      expect(screen.getByText('Inbox')).toBeInTheDocument();
      expect(screen.getByText('Comments, DMs and mentions across every platform')).toBeInTheDocument();
      expect(screen.getByText('Type')).toBeInTheDocument();
      expect(screen.getByText('Sentiment')).toBeInTheDocument();
      expect(screen.getAllByText('Comments').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('DMs')).toBeInTheDocument();
      expect(screen.getByText('Mentions')).toBeInTheDocument();
      expect(screen.getByText('Reviews')).toBeInTheDocument();
      expect(screen.getByText('Unread only')).toBeInTheDocument();
      expect(screen.getByText('Starred only')).toBeInTheDocument();

      // Customer message content integrity
      expect(screen.getAllByText('Customer Alice').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Hello, can you help me with my order #12345?')).toBeInTheDocument();
    });

    test('renders filters, sections, and preserves customer message in Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      await act(async () => {
        render(
          <MemoryRouter>
            <UnifiedInboxPage />
          </MemoryRouter>
        );
      });

      expect(screen.getByText('Bandeja de entrada')).toBeInTheDocument();
      expect(screen.getByText('Comentarios, mensajes directos y menciones en todas las plataformas')).toBeInTheDocument();
      expect(screen.getByText('Tipo')).toBeInTheDocument();
      expect(screen.getByText('Sentimiento')).toBeInTheDocument();
      expect(screen.getAllByText('Comentarios').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Mensajes directos')).toBeInTheDocument();
      expect(screen.getByText('Menciones')).toBeInTheDocument();
      expect(screen.getByText('Reseñas')).toBeInTheDocument();
      expect(screen.getByText('Solo no leídos')).toBeInTheDocument();
      expect(screen.getByText('Solo destacados')).toBeInTheDocument();

      // Customer message content MUST remain completely uncorrupted in Spanish
      expect(screen.getAllByText('Customer Alice').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Hello, can you help me with my order #12345?')).toBeInTheDocument();
    });
  });

  describe('ReviewsPage', () => {
    test('renders review filters and controls in English', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      await act(async () => {
        render(
          <MemoryRouter>
            <ReviewsPage />
          </MemoryRouter>
        );
      });

      expect(screen.getByText('Reviews')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
      expect(screen.getByText('Rating')).toBeInTheDocument();
      expect(screen.getAllByText('New').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Replied').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Flagged').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Carlos Mendoza')).toBeInTheDocument();
      expect(screen.getByText('Excelente servicio al cliente y entrega rápida!')).toBeInTheDocument();
      expect(screen.getByText('Reply')).toBeInTheDocument();
      expect(screen.getByText('Flag')).toBeInTheDocument();
    });

    test('renders review filters and controls in Spanish while preserving customer review', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      await act(async () => {
        render(
          <MemoryRouter>
            <ReviewsPage />
          </MemoryRouter>
        );
      });

      expect(screen.getByText('Reseñas')).toBeInTheDocument();
      expect(screen.getByText('Estado')).toBeInTheDocument();
      expect(screen.getByText('Calificación')).toBeInTheDocument();
      expect(screen.getAllByText('Nueva').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Respondida').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Marcada').length).toBeGreaterThanOrEqual(1);
      // Verbatim customer name and review text
      expect(screen.getByText('Carlos Mendoza')).toBeInTheDocument();
      expect(screen.getByText('Excelente servicio al cliente y entrega rápida!')).toBeInTheDocument();
      expect(screen.getByText('Responder')).toBeInTheDocument();
      expect(screen.getByText('Marcar')).toBeInTheDocument();
    });
  });

  describe('AutomationsPage', () => {
    test('renders automations list and controls in English', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      await act(async () => {
        render(
          <MemoryRouter>
            <AutomationsPage />
          </MemoryRouter>
        );
      });

      expect(screen.getByText('Automations')).toBeInTheDocument();
      expect(screen.getByText('If this happens, do that — across every connected platform')).toBeInTheDocument();
      expect(screen.getByText('New Rule')).toBeInTheDocument();
      expect(screen.getByText('Auto-thank 5 stars')).toBeInTheDocument();
      expect(screen.getByText('Active')).toBeInTheDocument();
      expect(screen.getByText('fired 14×')).toBeInTheDocument();
      expect(screen.getByText('Edit')).toBeInTheDocument();
      expect(screen.getByText('Templates')).toBeInTheDocument();

      // System-controlled templates in English
      expect(screen.getByText('Auto-thank for 5-star reviews')).toBeInTheDocument();
      expect(screen.getByText('Posts a friendly thank-you reply on every new 5★ Google review.')).toBeInTheDocument();
      expect(screen.getByText('Alert me on negative sentiment')).toBeInTheDocument();
      expect(screen.getByText('AI smart-reply to comments')).toBeInTheDocument();
      expect(screen.getByText('Tag urgent keywords')).toBeInTheDocument();
      expect(screen.getByText('Webhook on new DM')).toBeInTheDocument();
      expect(screen.getByText('Assign 1-2★ reviews to support lead')).toBeInTheDocument();
    });

    test('renders automations list and controls in Spanish with localized templates', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      await act(async () => {
        render(
          <MemoryRouter>
            <AutomationsPage />
          </MemoryRouter>
        );
      });

      expect(screen.getByText('Automatizaciones')).toBeInTheDocument();
      expect(screen.getByText('Si ocurre esto, haz aquello — en todas las plataformas conectadas')).toBeInTheDocument();
      expect(screen.getByText('Nueva regla')).toBeInTheDocument();
      expect(screen.getByText('Auto-thank 5 stars')).toBeInTheDocument();
      expect(screen.getByText('Activa')).toBeInTheDocument();
      expect(screen.getByText('ejecutada 14×')).toBeInTheDocument();
      expect(screen.getByText('Editar')).toBeInTheDocument();
      expect(screen.getByText('Plantillas')).toBeInTheDocument();

      // System-controlled templates in Spanish (BS-2.5.1 closure)
      expect(screen.getByText('Agradecimiento automático por reseñas de 5 estrellas')).toBeInTheDocument();
      expect(screen.getByText('Publica una respuesta amistosa de agradecimiento en cada nueva reseña de 5★ de Google.')).toBeInTheDocument();
      expect(screen.getByText('Avisarme ante sentimiento negativo')).toBeInTheDocument();
      expect(screen.getByText('Respuesta inteligente con IA a comentarios')).toBeInTheDocument();
      expect(screen.getByText('Etiquetar palabras clave urgentes')).toBeInTheDocument();
      expect(screen.getByText('Webhook ante nuevo mensaje directo')).toBeInTheDocument();
      expect(screen.getByText('Asignar reseñas de 1-2★ al líder de soporte')).toBeInTheDocument();
    });

    test('clicking a template in Spanish opens modal prefilled in Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      await act(async () => {
        render(
          <MemoryRouter>
            <AutomationsPage />
          </MemoryRouter>
        );
      });

      // Click on the 5-star review template
      const tplButton = screen.getByText('Agradecimiento automático por reseñas de 5 estrellas');
      await act(async () => {
        tplButton.click();
      });

      expect(screen.getByText('Personalizar plantilla')).toBeInTheDocument();
      expect(screen.getByText('Rellenado a partir de la plantilla "Agradecimiento automático por reseñas de 5 estrellas"')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Agradecimiento automático por reseñas de 5 estrellas')).toBeInTheDocument();
      expect(screen.getByDisplayValue('¡Muchas gracias por tus amables palabras, {reviewer_name}! 🙏')).toBeInTheDocument();
    });
  });

  describe('AIReplySuggestions', () => {
    test('renders suggested replies header and tone badges in English and Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      render(
        <AIReplySuggestions
          clientId={1}
          messageId={5001}
          senderName="Alice"
          autoLoad={true}
        />
      );

      // Await debounce and promise resolution
      await act(async () => {
        await new Promise((r) => setTimeout(r, 350));
      });

      expect(screen.getByText('Suggested replies')).toBeInTheDocument();
      expect(screen.getByText('· Recommended')).toBeInTheDocument();
      expect(screen.getByText('Friendly')).toBeInTheDocument();
      expect(screen.getByText('Professional')).toBeInTheDocument();

      await act(async () => {
        await changePlatformLanguage('es');
      });

      // Rerender in Spanish
      render(
        <AIReplySuggestions
          clientId={1}
          messageId={5001}
          senderName="Alice"
          autoLoad={true}
        />
      );

      await act(async () => {
        await new Promise((r) => setTimeout(r, 350));
      });

      expect(screen.getAllByText('Respuestas sugeridas')[0]).toBeInTheDocument();
      expect(screen.getAllByText('· Recomendada')[0]).toBeInTheDocument();
      expect(screen.getAllByText('Amigable')[0]).toBeInTheDocument();
      expect(screen.getAllByText('Profesional')[0]).toBeInTheDocument();
    });
  });

  describe('WhatsAppInboxPage', () => {
    test('renders WhatsApp inbox header and window badge in English and Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      const { unmount } = render(
        <MemoryRouter>
          <WhatsAppInboxPage />
        </MemoryRouter>
      );

      expect(screen.getByText('Inbox')).toBeInTheDocument();
      expect(screen.getByText('WhatsApp conversations')).toBeInTheDocument();
      expect(screen.getByText('Conversations (1)')).toBeInTheDocument();
      expect(screen.getAllByText('Valeria WhatsApp').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('24h window open')).toBeInTheDocument();
      expect(screen.getAllByText('Hola, tengo una pregunta sobre el producto').length).toBeGreaterThanOrEqual(1);

      unmount();

      await act(async () => {
        await changePlatformLanguage('es');
      });

      render(
        <MemoryRouter>
          <WhatsAppInboxPage />
        </MemoryRouter>
      );

      expect(screen.getByText('Bandeja de entrada')).toBeInTheDocument();
      expect(screen.getByText('Conversaciones de WhatsApp')).toBeInTheDocument();
      expect(screen.getByText('Conversaciones (1)')).toBeInTheDocument();
      expect(screen.getAllByText('Valeria WhatsApp').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Ventana de 24 h abierta')).toBeInTheDocument();
      expect(screen.getAllByText('Hola, tengo una pregunta sobre el producto').length).toBeGreaterThanOrEqual(1);
    });
  });
});
