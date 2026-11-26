import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

import DraftsPage from '../composer/DraftsPage';
import ComposerPage from '../composer/ComposerPage';
import { composerAPI } from '../../services/api';

let mockClient = { id: 3, company: 'Bop Agencia' };
let mockExistingPost = null;

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn() },
}));

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (k, d) => (typeof d === 'string' ? d : k),
    i18n: { language: 'es', changeLanguage: jest.fn() },
  }),
  Trans: ({ children }) => <>{children}</>,
  initReactI18next: { type: '3rdParty', init: jest.fn() },
}));

jest.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 12, email: 'bopagencia@gmail.com', role: 'client', account_type: 'agency_member' },
  }),
}));

jest.mock('../../stores/appStore', () => ({
  useCurrentClient: () => mockClient,
}));

jest.mock('../../hooks/useComposer', () => ({
  useComposerPost: () => ({ data: mockExistingPost, loading: false, refetch: jest.fn() }),
}));

jest.mock('../../components/ai/AIWriteButton', () => () => <div data-testid="ai-write-btn" />);

jest.mock('../../services/api', () => ({
  composerAPI: {
    posts: {
      list: jest.fn(),
      create: jest.fn(),
      update: jest.fn(),
      delete: jest.fn(),
      publishNow: jest.fn(),
      schedule: jest.fn(),
    },
    media: {
      list: jest.fn().mockResolvedValue({ data: { results: [] } }),
      upload: jest.fn(),
    },
    preflight: jest.fn(),
  },
  captionAPI: { generate: jest.fn() },
  hashtagAPI: { generate: jest.fn() },
}));

function LocationDisplay() {
  const loc = useLocation();
  return <div data-testid="current-path">{loc.pathname}</div>;
}

describe('BS-10D.2 Draft Management & Composer Redirect', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockClient = { id: 3, company: 'Bop Agencia' };
    mockExistingPost = null;
  });

  test('DraftsPage lists workspace drafts with thumbnail and opens editor on Edit', async () => {
    composerAPI.posts.list.mockResolvedValueOnce({
      data: {
        results: [
          {
            id: 16,
            client: 3,
            title: 'BOP-001 | Captación de clientes',
            content: '¿Cuántos clientes está perdiendo tu negocio?',
            media_type: 'image',
            thumbnail_url: '/api/media/serve/10/?thumb=1&token=abc',
            target_platforms: ['facebook', 'instagram'],
            status: 'draft',
            updated_at: '2026-11-25T21:42:25Z',
          },
        ],
      },
    });

    render(
      <MemoryRouter initialEntries={['/dashboard/analytics/drafts']}>
        <Routes>
          <Route path="/dashboard/analytics/drafts" element={<DraftsPage />} />
          <Route path="/dashboard/analytics/composer/:id" element={<LocationDisplay />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('BOP-001 | Captación de clientes')).toBeInTheDocument();
    expect(screen.getByText('facebook')).toBeInTheDocument();
    expect(screen.getByText('instagram')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Editar').closest('button'));
    expect(await screen.findByTestId('current-path')).toHaveTextContent('/dashboard/analytics/composer/16');
  });

  test('Save Draft in /dashboard/analytics/composer stays in /dashboard/analytics/composer/<id> and reopens media', async () => {
    composerAPI.posts.create.mockResolvedValueOnce({ data: { id: 16, client: 3, status: 'draft' } });

    render(
      <MemoryRouter initialEntries={['/dashboard/analytics/composer']}>
        <Routes>
          <Route
            path="/dashboard/analytics/composer"
            element={
              <>
                <ComposerPage />
                <LocationDisplay />
              </>
            }
          />
          <Route
            path="/dashboard/analytics/composer/:id"
            element={
              <>
                <ComposerPage />
                <LocationDisplay />
              </>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    const textarea = await screen.findByPlaceholderText('composer.content_placeholder');
    fireEvent.change(textarea, { target: { value: 'Contenido de borrador comercial' } });

    fireEvent.click(screen.getByText('composer.save_draft').closest('button'));

    await waitFor(() => {
      expect(composerAPI.posts.create).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId('current-path')).toHaveTextContent('/dashboard/analytics/composer/16');
    });
  });

  test('Reopening existing draft hydrates resolved_media_assets into Composer preview', async () => {
    mockExistingPost = {
      id: 16,
      client: 3,
      title: 'BOP-001',
      content: 'Caption con #BopAgencia',
      media_type: 'image',
      target_platforms: ['facebook', 'instagram'],
      media_urls: ['asset:10'],
      resolved_media_assets: [
        {
          id: 10,
          file_url: '/api/media/serve/10/?token=xyz',
          thumbnail_url: '/api/media/serve/10/?thumb=1&token=xyz',
          mime_type: 'image/png',
          alt_text: 'Bob Promo',
        },
      ],
    };

    render(
      <MemoryRouter initialEntries={['/dashboard/analytics/composer/16']}>
        <Routes>
          <Route path="/dashboard/analytics/composer/:id" element={<ComposerPage />} />
        </Routes>
      </MemoryRouter>,
    );

    const imgs = await screen.findAllByAltText('Bob Promo');
    expect(imgs.length).toBeGreaterThan(0);
    expect(imgs[0].getAttribute('src')).toBe('/api/media/serve/10/?thumb=1&token=xyz');
  });
});
