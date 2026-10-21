/* ============================================================================
 *  Bop Social — Content & Publishing Translation Verification Tests (BS-2.4)
 *  Verifies English and Spanish internationalization for:
 *  - ComposerPage
 *  - CalendarPage (Grid, PostDrawer, PostFormDrawer)
 *  - QueueManagerPage
 *  - MediaLibraryPage
 *  - MyPostsPage
 *  - VideoStudioPage
 *  - Customer Content Integrity & Machine-Readable Status Translations
 * ========================================================================== */
import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n, { changePlatformLanguage } from '../../i18n/config';
import ComposerPage from '../composer/ComposerPage';
import CalendarPage from '../CalendarPage';
import CalendarGrid from '../../components/calendar/CalendarGrid';
import PostDrawer from '../../components/calendar/PostDrawer';
import PostFormDrawer from '../../components/calendar/PostFormDrawer';
import QueueManagerPage from '../composer/QueueManagerPage';
import MediaLibraryPage from '../composer/MediaLibraryPage';
import MyPostsPage from '../MyPostsPage';
import VideoStudioPage from '../video/VideoStudioPage';

// Mock API modules
jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {},
  composerAPI: {
    posts: {
      list: jest.fn().mockResolvedValue({ data: [] }),
      get: jest.fn().mockResolvedValue({ data: null }),
      create: jest.fn().mockResolvedValue({ data: { id: 1 } }),
      update: jest.fn().mockResolvedValue({ data: { id: 1 } }),
      delete: jest.fn().mockResolvedValue({ data: { success: true } }),
    },
    media: {
      list: jest.fn().mockResolvedValue({ data: [] }),
      upload: jest.fn().mockResolvedValue({ data: {} }),
      delete: jest.fn().mockResolvedValue({ data: { success: true } }),
    },
    queues: {
      list: jest.fn().mockResolvedValue({ data: [] }),
      get: jest.fn().mockResolvedValue({ data: null }),
      create: jest.fn().mockResolvedValue({ data: { id: 1 } }),
      delete: jest.fn().mockResolvedValue({ data: { success: true } }),
      pause: jest.fn().mockResolvedValue({ data: { success: true } }),
      resume: jest.fn().mockResolvedValue({ data: { success: true } }),
      addItem: jest.fn().mockResolvedValue({ data: {} }),
    },
  },
  captionAPI: {
    generate: jest.fn(),
  },
  hashtagAPI: {
    suggest: jest.fn(),
  },
  videoAPI: {
    upload: jest.fn(),
    importFromUrl: jest.fn(),
    trim: jest.fn(),
    resize: jest.fn(),
    extractThumbnail: jest.fn(),
    addCaptions: jest.fn(),
    youtubeUpload: jest.fn(),
  },
  clientsAPI: {
    list: jest.fn().mockResolvedValue({ data: [] }),
  },
}));

// Mock hooks
jest.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, email: 'agency@demo.local', role: 'agency', client_id: 1, company: 'Demo Agency' },
  }),
}));

jest.mock('../../hooks/useData', () => ({
  useClients: () => ({
    clients: [{ id: 1, company: 'Demo Client', name: 'Demo Client' }],
    loading: false,
  }),
  useDateRange: () => [{ start: '2026-01-01', end: '2026-01-31' }, jest.fn()],
  useOAuthStatus: () => ({
    status: { instagram: { status: 'active' }, facebook: { status: 'active' } },
  }),
  useLookups: () => ({
    lookups: {
      platforms: [
        { key: 'instagram', label: 'Instagram' },
        { key: 'facebook', label: 'Facebook' },
      ],
    },
  }),
  usePosts: () => ({
    posts: [
      {
        id: 99,
        platform: 'instagram',
        post_type: 'image',
        title: 'Customer Defined Title 123',
        caption: 'Untranslated Customer Caption with #hashtag and @mention',
        post_url: 'https://instagram.com/p/123',
        published_at: '2026-02-15T10:00:00Z',
        impressions: 1500,
        likes: 120,
        comments: 14,
        video_views: 0,
      },
    ],
    total: 1,
    hasMore: false,
    loading: false,
    loadingMore: false,
    loadMore: jest.fn(),
  }),
}));

jest.mock('../../hooks/useCalendar', () => ({
  useCalendarPosts: () => ({ posts: [], loading: false, refetch: jest.fn() }),
  useCalendarStats: () => ({ stats: {}, loading: false }),
  useCalendarNotes: () => ({ notes: [], addNote: jest.fn(), deleteNote: jest.fn() }),
  useCreatePost: () => ({ createPost: jest.fn(), updating: false }),
  useUpcomingPosts: () => ({ posts: [], loading: false }),
  useSuggestedTimes: () => ({ suggestions: [], source: 'history' }),
}));

jest.mock('../../hooks/useComposer', () => ({
  useComposerPosts: () => ({ data: [], loading: false, refetch: jest.fn() }),
  useComposerPost: () => ({ data: null, loading: false, refetch: jest.fn() }),
  useMediaAssets: () => ({ data: [], loading: false, refetch: jest.fn() }),
  usePostQueues: () => ({ data: [], loading: false, refetch: jest.fn() }),
  usePostQueue: () => ({ data: null, loading: false, refetch: jest.fn() }),
}));

describe('PHASE BS-2.4: Content & Publishing Internationalization', () => {
  beforeEach(async () => {
    await act(async () => {
      await changePlatformLanguage('en');
    });
  });

  afterEach(async () => {
    await act(async () => {
      await changePlatformLanguage('en');
    });
  });

  describe('1. ComposerPage Translation', () => {
    test('renders English strings and preserves brand name and platform names', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      render(
        <MemoryRouter>
          <ComposerPage />
        </MemoryRouter>
      );

      expect(screen.getByText('New Post')).toBeInTheDocument();
      expect(screen.getByText('Compose once. Publish everywhere.')).toBeInTheDocument();
      expect(screen.getByText('Publish Now')).toBeInTheDocument();
      expect(screen.getByText('Save Draft')).toBeInTheDocument();

      // Platform names remain as proper nouns
      expect(screen.getAllByRole('button', { name: /Instagram/i }).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByRole('button', { name: /Facebook/i }).length).toBeGreaterThanOrEqual(1);
    });

    test('renders Spanish translations with brand and platform preservation', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      render(
        <MemoryRouter>
          <ComposerPage />
        </MemoryRouter>
      );

      expect(screen.getByText('Nueva publicación')).toBeInTheDocument();
      expect(screen.getByText('Redacta una vez. Publica en todas partes.')).toBeInTheDocument();
      expect(screen.getByText('Publicar ahora')).toBeInTheDocument();
      expect(screen.getByText('Guardar borrador')).toBeInTheDocument();

      // Platform names remain untranslated in Spanish
      expect(screen.getAllByRole('button', { name: /Instagram/i }).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByRole('button', { name: /Facebook/i }).length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('2. Calendar & Drawers Translation', () => {
    test('renders Calendar weekday headers and view toggles in English and Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      const { rerender } = render(
        <MemoryRouter>
          <CalendarGrid
            month={new Date(2026, 2, 1)}
            posts={[]}
            onDateClick={jest.fn()}
            onPostClick={jest.fn()}
          />
        </MemoryRouter>
      );

      expect(screen.getByText('Mon')).toBeInTheDocument();
      expect(screen.getByText('Sun')).toBeInTheDocument();

      await act(async () => {
        await changePlatformLanguage('es');
      });

      rerender(
        <MemoryRouter>
          <CalendarGrid
            month={new Date(2026, 2, 1)}
            posts={[]}
            onDateClick={jest.fn()}
            onPostClick={jest.fn()}
          />
        </MemoryRouter>
      );

      expect(screen.getByText('Lun')).toBeInTheDocument();
      expect(screen.getByText('Dom')).toBeInTheDocument();
    });

    test('renders PostDrawer performance metrics and action buttons in English and Spanish', async () => {
      const mockPost = {
        id: 42,
        platform: 'instagram',
        caption: 'Customer special offer caption',
        scheduled_at: '2026-04-10T14:00:00Z',
        status: 'published',
        impressions: 3400,
        reach: 2800,
        likes: 195,
        comments: 23,
      };

      await act(async () => {
        await changePlatformLanguage('en');
      });

      const { rerender } = render(
        <MemoryRouter>
          <PostDrawer
            post={mockPost}
            isOpen={true}
            onClose={jest.fn()}
            onEdit={jest.fn()}
            onDelete={jest.fn()}
            onReschedule={jest.fn()}
          />
        </MemoryRouter>
      );

      expect(screen.getByText('Published')).toBeInTheDocument();
      expect(screen.getByText('Performance')).toBeInTheDocument();
      expect(screen.getByText('Impressions')).toBeInTheDocument();
      expect(screen.getByText('Reach')).toBeInTheDocument();
      expect(screen.getByText('Customer special offer caption')).toBeInTheDocument();

      await act(async () => {
        await changePlatformLanguage('es');
      });

      rerender(
        <MemoryRouter>
          <PostDrawer
            post={mockPost}
            isOpen={true}
            onClose={jest.fn()}
            onEdit={jest.fn()}
            onDelete={jest.fn()}
            onReschedule={jest.fn()}
          />
        </MemoryRouter>
      );

      expect(screen.getByText('Publicado')).toBeInTheDocument();
      expect(screen.getByText('Rendimiento')).toBeInTheDocument();
      expect(screen.getByText('Impresiones')).toBeInTheDocument();
      expect(screen.getByText('Alcance')).toBeInTheDocument();
      // Customer content strictly preserved
      expect(screen.getByText('Customer special offer caption')).toBeInTheDocument();
    });

    test('renders PostFormDrawer buttons and labels in English and Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      const { rerender } = render(
        <MemoryRouter>
          <PostFormDrawer
            isOpen={true}
            onClose={jest.fn()}
            onSave={jest.fn()}
            date={new Date(2026, 3, 15)}
          />
        </MemoryRouter>
      );

      expect(screen.getByText('Title')).toBeInTheDocument();
      expect(screen.getByText('Save as Draft')).toBeInTheDocument();

      await act(async () => {
        await changePlatformLanguage('es');
      });

      rerender(
        <MemoryRouter>
          <PostFormDrawer
            isOpen={true}
            onClose={jest.fn()}
            onSave={jest.fn()}
            date={new Date(2026, 3, 15)}
          />
        </MemoryRouter>
      );

      expect(screen.getByText('Título')).toBeInTheDocument();
      expect(screen.getByText('Guardar como borrador')).toBeInTheDocument();
    });
  });

  describe('3. QueueManagerPage Translation', () => {
    test('renders QueueManagerPage in English and Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      const { rerender } = render(
        <MemoryRouter>
          <QueueManagerPage />
        </MemoryRouter>
      );

      expect(screen.getByText('Queues')).toBeInTheDocument();
      expect(screen.getByText('New Queue')).toBeInTheDocument();

      await act(async () => {
        await changePlatformLanguage('es');
      });

      rerender(
        <MemoryRouter>
          <QueueManagerPage />
        </MemoryRouter>
      );

      expect(screen.getByText('Colas')).toBeInTheDocument();
      expect(screen.getByText('Nueva cola')).toBeInTheDocument();
    });
  });

  describe('4. MediaLibraryPage Translation', () => {
    test('renders MediaLibraryPage in English and Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      const { rerender } = render(
        <MemoryRouter>
          <MediaLibraryPage />
        </MemoryRouter>
      );

      expect(screen.getByText('Media Library')).toBeInTheDocument();
      expect(screen.getAllByText('Upload').length).toBeGreaterThanOrEqual(1);

      await act(async () => {
        await changePlatformLanguage('es');
      });

      rerender(
        <MemoryRouter>
          <MediaLibraryPage />
        </MemoryRouter>
      );

      expect(screen.getByText('Biblioteca multimedia')).toBeInTheDocument();
      expect(screen.getAllByText('Subir').length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('5. MyPostsPage Translation & Customer Content Integrity', () => {
    test('renders MyPostsPage with English labels and untranslated customer content', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      render(
        <MemoryRouter>
          <MyPostsPage />
        </MemoryRouter>
      );

      expect(screen.getByText('My Posts')).toBeInTheDocument();
      expect(screen.getByText('Showing:')).toBeInTheDocument();
      expect(screen.getByText('Platforms:')).toBeInTheDocument();
      expect(screen.getByText('View Post')).toBeInTheDocument();

      // Invariant: Customer caption is never mutated
      expect(screen.getByText('Untranslated Customer Caption with #hashtag and @mention')).toBeInTheDocument();
    });

    test('renders MyPostsPage with Spanish labels while preserving customer text verbatim', async () => {
      await act(async () => {
        await changePlatformLanguage('es');
      });

      render(
        <MemoryRouter>
          <MyPostsPage />
        </MemoryRouter>
      );

      expect(screen.getByText('Mis publicaciones')).toBeInTheDocument();
      expect(screen.getByText('Mostrando:')).toBeInTheDocument();
      expect(screen.getByText('Plataformas:')).toBeInTheDocument();
      expect(screen.getByText('Ver publicación')).toBeInTheDocument();

      // Customer content MUST NOT be translated or modified
      expect(screen.getByText('Untranslated Customer Caption with #hashtag and @mention')).toBeInTheDocument();
    });
  });

  describe('6. VideoStudioPage Translation', () => {
    test('renders VideoStudioPage tabs and tools in English and Spanish', async () => {
      await act(async () => {
        await changePlatformLanguage('en');
      });

      const { rerender } = render(
        <MemoryRouter>
          <VideoStudioPage />
        </MemoryRouter>
      );

      expect(screen.getByText('Video Studio')).toBeInTheDocument();
      expect(screen.getByText('Trim')).toBeInTheDocument();
      expect(screen.getByText('Resize')).toBeInTheDocument();
      expect(screen.getByText('Thumbnail')).toBeInTheDocument();
      expect(screen.getByText('Captions')).toBeInTheDocument();
      expect(screen.getByText('Publish')).toBeInTheDocument();
      expect(screen.getByText('Load a video first')).toBeInTheDocument();

      await act(async () => {
        await changePlatformLanguage('es');
      });

      rerender(
        <MemoryRouter>
          <VideoStudioPage />
        </MemoryRouter>
      );

      expect(screen.getByText('Estudio de vídeo')).toBeInTheDocument();
      expect(screen.getByText('Recortar')).toBeInTheDocument();
      expect(screen.getByText('Redimensionar')).toBeInTheDocument();
      expect(screen.getByText('Miniatura')).toBeInTheDocument();
      expect(screen.getByText('Subtítulos')).toBeInTheDocument();
      expect(screen.getByText('Publicar')).toBeInTheDocument();
      expect(screen.getByText('Carga un vídeo primero')).toBeInTheDocument();
    });
  });

  describe('7. Machine-Readable Status Translations', () => {
    test('translates status values accurately without altering backend canonical keys', () => {
      const statuses = [
        { code: 'draft', en: 'Draft', es: 'Borrador' },
        { code: 'scheduled', en: 'Scheduled', es: 'Programado' },
        { code: 'publishing', en: 'Publishing', es: 'Publicando' },
        { code: 'published', en: 'Published', es: 'Publicado' },
        { code: 'failed', en: 'Failed', es: 'Fallido' },
        { code: 'queued', en: 'Queued', es: 'En cola' },
        { code: 'cancelled', en: 'Cancelled', es: 'Cancelado' },
      ];

      i18n.changeLanguage('en');
      statuses.forEach((s) => {
        expect(i18n.t(`content:status.${s.code}`)).toBe(s.en);
      });

      i18n.changeLanguage('es');
      statuses.forEach((s) => {
        expect(i18n.t(`content:status.${s.code}`)).toBe(s.es);
      });
    });
  });
});
