import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import toast from 'react-hot-toast';

import ComposerPage, { extractComposerHashtags } from '../composer/ComposerPage';
import { hashtagAPI } from '../../services/api';

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    error: jest.fn(),
    success: jest.fn(),
  },
}));

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (k, d) => (typeof d === 'string' ? d : k),
    i18n: { language: 'en', changeLanguage: jest.fn() },
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
  useCurrentClient: () => ({ id: 3, company: 'Bop Agencia' }),
}));

jest.mock('../../hooks/useComposer', () => ({
  useComposerPost: () => ({ data: null, loading: false, refetch: jest.fn() }),
}));

jest.mock('../../components/ai/AIWriteButton', () => () => <div data-testid="ai-write-btn" />);

jest.mock('../../services/api', () => ({
  composerAPI: {
    posts: { create: jest.fn(), update: jest.fn(), publishNow: jest.fn(), schedule: jest.fn(), preflight: jest.fn() },
    media: { list: jest.fn().mockResolvedValue({ data: { results: [] } }), upload: jest.fn() },
  },
  captionAPI: { generate: jest.fn() },
  hashtagAPI: { generate: jest.fn() },
}));

describe('BS-10C.2 / BS-10C.2A Composer hashtag contract & event-handler', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('extracts hashtags from actual groups + prose recommended_set schema without prose words', () => {
    const actualBackendResponse = {
      hashtags: {
        strategy: 'Combine global + local tags',
        groups: {
          mega: {
            tags: [{ tag: '#marketingdigital' }, { tag: 'emprendedores' }],
          },
          branded: {
            tags: [{ tag: '##BopAgencia' }],
          },
        },
        recommended_set: {
          caption: '¿Cuántos clientes estás perdiendo hoy? #marketingdigital #negocioscali #inteligenciaartificial',
          first_comment: '#empresascali #BopAgencia',
        },
      },
      cached: false,
      id: 2,
    };

    const extracted = extractComposerHashtags(actualBackendResponse, 'Texto previo #BopAgencia', 8);
    expect(extracted).toEqual([
      '#marketingdigital',
      '#negocioscali',
      '#inteligenciaartificial',
      '#empresascali',
      '#emprendedores',
    ]);
  });

  test('clicking Add Hashtags in ComposerPage updates post content and shows no error toast', async () => {
    hashtagAPI.generate.mockResolvedValueOnce({
      data: {
        hashtags: {
          groups: {
            medium: { tags: [{ tag: '#agencia' }, { tag: '#automatizacion' }] },
          },
          recommended_set: {
            caption: 'Impulsa tu marca en Cali. #marketingdigital #negocioscali',
          },
        },
        cached: false,
        id: 10,
      },
    });

    render(
      <MemoryRouter initialEntries={['/dashboard/analytics/composer']}>
        <Routes>
          <Route path="/dashboard/analytics/composer" element={<ComposerPage />} />
        </Routes>
      </MemoryRouter>,
    );

    const textarea = await screen.findByPlaceholderText('composer.content_placeholder');
    fireEvent.change(textarea, { target: { value: 'Publicación de prueba para Bop Agencia' } });

    const addHashtagsBtn = screen.getByText('composer.ai_hashtags').closest('button');
    fireEvent.click(addHashtagsBtn);

    await waitFor(() => {
      expect(hashtagAPI.generate).toHaveBeenCalledWith(
        expect.objectContaining({ client_id: 3 }),
      );
    });

    await waitFor(() => {
      expect(textarea.value).toContain('Publicación de prueba para Bop Agencia');
      expect(textarea.value).toContain('#marketingdigital #negocioscali #agencia #automatizacion');
    });
    expect(toast.error).not.toHaveBeenCalled();
  });
});
