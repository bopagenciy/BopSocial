import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import FeatureSidebar from '../../components/shell/FeatureSidebar';
import ApprovalQueuePage from '../admin/ApprovalQueuePage';
import { composerAPI, notificationsAPI } from '../../services/api';

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
    user: {
      id: 12,
      email: 'bopagencia@gmail.com',
      role: 'client',
      account_type: 'agency_member',
      client_id: 3,
    },
    can: (perm) => ['composer.view', 'calendar.view', 'composer.approve'].includes(perm),
  }),
}));

jest.mock('../../hooks/useData', () => ({
  useClients: () => ({ clients: [{ id: 3, company: 'Bop Agencia' }] }),
}));

jest.mock('../../stores/appStore', () => ({
  useCurrentClient: () => ({ id: 3, company: 'Bop Agencia' }),
  useAppStore: (sel) => sel({
    setCurrentClient: jest.fn(),
    badgeCounts: { pending_approvals: 1, unread_inbox: 0, unread_notifications: 0 },
  }),
  useBadgeCount: (key) => (key === 'pending_approvals' ? 1 : 0),
}));

jest.mock('../../services/api', () => ({
  notificationsAPI: {
    approvalQueue: jest.fn(),
  },
  composerAPI: {
    posts: {
      approve: jest.fn(),
      cancel: jest.fn(),
    },
  },
}));

describe('BS-10E.4 Commercial Approval Workflow UI', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    notificationsAPI.approvalQueue.mockResolvedValue({
      data: {
        count: 1,
        queue: [
          {
            id: 16,
            client: 3,
            title: 'BOP-001 | Captación de clientes',
            content: 'Contenido comercial pendiente',
            media_type: 'image',
            thumbnail_url: '/api/media/serve/10/?thumb=1&token=sig123',
            target_platforms: ['facebook', 'instagram'],
            status: 'pending_approval',
            scheduled_at: '2026-11-27T15:00:00Z',
            created_at: '2026-11-25T21:42:25Z',
          },
        ],
      },
    });
    composerAPI.posts.approve.mockResolvedValue({ data: { id: 16, status: 'scheduled' } });
  });

  test('FeatureSidebar exposes Approvals link under Publish with pending badge', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard/analytics/approvals']}>
        <FeatureSidebar module="analytics" basePath="/dashboard" isAdmin={false} />
      </MemoryRouter>
    );

    const link = screen.getByRole('link', { name: /Approvals/i });
    expect(link).toHaveAttribute('href', '/dashboard/analytics/approvals');
    expect(link).toHaveTextContent('1');
  });

  test('ApprovalQueuePage displays pending post, both platforms, authorized image, and approve action', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard/analytics/approvals']}>
        <ApprovalQueuePage />
      </MemoryRouter>
    );

    expect(await screen.findByText('BOP-001 | Captación de clientes')).toBeInTheDocument();
    expect(screen.getByText('facebook')).toBeInTheDocument();
    expect(screen.getByText('instagram')).toBeInTheDocument();
    const img = screen.getByRole('img', { name: 'BOP-001 | Captación de clientes' });
    expect(img).toHaveAttribute('src', '/api/media/serve/10/?thumb=1&token=sig123');

    const editLink = screen.getByRole('link', { name: /Edit/i });
    expect(editLink).toHaveAttribute('href', '/dashboard/analytics/composer/16');

    fireEvent.click(screen.getByRole('button', { name: /Approve/i }));
    await waitFor(() => {
      expect(composerAPI.posts.approve).toHaveBeenCalledWith(16);
    });
  });
});
