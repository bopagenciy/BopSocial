import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import CalendarPage from '../CalendarPage';
import { calendarAPI } from '../../services/api';

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
    user: { id: 5, email: 'pilot.operator@bopagencia.local', role: 'client', client_id: 3 },
  }),
}));

jest.mock('../../hooks/useData', () => ({
  useClients: () => ({ clients: [{ id: 3, company: 'Bop Agencia' }] }),
}));

jest.mock('../../services/api', () => ({
  calendarAPI: {
    getPosts: jest.fn(),
    getNotes: jest.fn().mockResolvedValue({ data: {} }),
    getStats: jest.fn().mockResolvedValue({ data: null }),
    getUpcoming: jest.fn().mockResolvedValue({ data: [] }),
    createPost: jest.fn(),
    updatePost: jest.fn(),
    deletePost: jest.fn(),
    reschedule: jest.fn(),
  },
}));

const now = new Date();
const yyyy = now.getFullYear();
const mm = String(now.getMonth() + 1).padStart(2, '0');
const dateKey = `${yyyy}-${mm}-27`;

const multiplatformPost = {
  id: 'unified-16',
  unified_post_id: 16,
  source: 'unified',
  client: 3,
  platform: 'facebook',
  target_platforms: ['facebook', 'instagram'],
  post_type: 'image',
  status: 'pending_approval',
  title: 'BOP-001 | Captación de clientes',
  caption: 'Gestión profesional de redes sociales',
  media_url: '/api/media/serve/10/?token=sig123',
  media_urls: ['/api/media/serve/10/?token=sig123'],
  scheduled_at: `${dateKey}T15:00:00Z`,
};

describe('BS-10E.3 Calendar interaction, multiplatform filtering, and detail panel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    calendarAPI.getNotes.mockResolvedValue({ data: {} });
    calendarAPI.getStats.mockResolvedValue({ data: null });
    calendarAPI.getUpcoming.mockResolvedValue({ data: [] });
    calendarAPI.getPosts.mockImplementation(async (params = {}) => {
      const p = params.platform;
      if (!p || p === 'all' || multiplatformPost.target_platforms.includes(p)) {
        return { data: { [dateKey]: [multiplatformPost] } };
      }
      return { data: {} };
    });
  });

  test('platform filter buttons are clickable, filter multiplatform posts, and detail panel shows both platforms and media', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard/analytics/calendar']}>
        <CalendarPage clientId={3} />
      </MemoryRouter>
    );

    // Initial load shows the multiplatform post pill
    expect(await screen.findByText(/BOP-001/)).toBeInTheDocument();

    // Click Instagram filter -> backend receives platform=instagram and post remains visible
    const igBtn = screen.getAllByRole('button', { name: /Instagram/i })[0];
    fireEvent.click(igBtn);
    await waitFor(() => {
      expect(calendarAPI.getPosts).toHaveBeenCalledWith(
        expect.objectContaining({ client_id: 3, platform: 'instagram' })
      );
    });
    expect(await screen.findByText(/BOP-001/)).toBeInTheDocument();

    // Click LinkedIn filter -> post is excluded
    const liBtn = screen.getAllByRole('button', { name: /LinkedIn/i })[0];
    fireEvent.click(liBtn);
    await waitFor(() => {
      expect(calendarAPI.getPosts).toHaveBeenCalledWith(
        expect.objectContaining({ client_id: 3, platform: 'linkedin' })
      );
    });
    await waitFor(() => {
      expect(screen.queryByText(/BOP-001/)).not.toBeInTheDocument();
    });

    // Click All Platforms -> post reappears and clicking it opens PostDrawer with both platforms & image
    const allBtn = screen.getByRole('button', { name: /All/i });
    fireEvent.click(allBtn);
    const pill = await screen.findByText(/BOP-001/);
    fireEvent.click(pill);

    expect(await screen.findByText(/Facebook · Instagram/i)).toBeInTheDocument();
    expect(screen.getByText('Gestión profesional de redes sociales')).toBeInTheDocument();
    const img = screen.getByRole('img', { name: /BOP-001/i });
    expect(img).toHaveAttribute('src', '/api/media/serve/10/?token=sig123');
    expect(screen.getByRole('button', { name: /calendar\.drawer\.edit/i })).toBeInTheDocument();
  });
});
