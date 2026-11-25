import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import ComposerPage from '../composer/ComposerPage';
import InvitationPage from '../InvitationPage';
import { composerAPI, invitationAPI } from '../../services/api';

let mockCurrentClient = { id: 21, company: 'Test Alpha Brands S.A.' };
let mockUser = { id: 12, email: 'bopagencia@gmail.com', role: 'client', account_type: 'agency_member' };
const mockRefreshAuth = jest.fn().mockResolvedValue({});
const mockLogout = jest.fn();

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
    user: mockUser,
    refreshAuth: mockRefreshAuth,
    logout: mockLogout,
  }),
}));

jest.mock('../../stores/appStore', () => ({
  useCurrentClient: () => mockCurrentClient,
}));

jest.mock('../../hooks/useComposer', () => ({
  useComposerPost: () => ({ data: null, loading: false, refetch: jest.fn() }),
}));

jest.mock('../../components/ai/AIWriteButton', () => (props) => (
  <div data-testid="ai-write-btn" data-client-id={props.clientId || ''} />
));

jest.mock('../../services/api', () => ({
  composerAPI: {
    posts: {
      create: jest.fn().mockResolvedValue({ data: { id: 501, client: 21 } }),
      update: jest.fn().mockResolvedValue({ data: { id: 501, client: 21 } }),
      schedule: jest.fn().mockResolvedValue({ data: {} }),
      publishNow: jest.fn().mockResolvedValue({ data: { status: 'pending_approval' } }),
    },
    media: {
      upload: jest.fn().mockResolvedValue({ data: { id: 77, mime_type: 'image/png' } }),
    },
    preflight: jest.fn().mockResolvedValue({ data: { ok: true, platforms: {} } }),
  },
  captionAPI: { generate: jest.fn().mockResolvedValue({ data: { captions: {} } }) },
  hashtagAPI: { generate: jest.fn().mockResolvedValue({ data: { hashtags: [] } }) },
  invitationAPI: {
    getByToken: jest.fn(),
    accept: jest.fn(),
    respond: jest.fn(),
  },
}));

describe('BS-9C Commercial Workflows (Frontend)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCurrentClient = { id: 21, company: 'Test Alpha Brands S.A.' };
    mockUser = { id: 12, email: 'bopagencia@gmail.com', role: 'client', account_type: 'agency_member' };
  });

  test('ComposerPage binds activeClientId on draft save and AIWriteButton', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/analytics/composer']}>
        <Routes>
          <Route path="/admin/analytics/composer" element={<ComposerPage />} />
          <Route path="/admin/analytics/composer/:id" element={<ComposerPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByTestId('ai-write-btn')).toHaveAttribute('data-client-id', '21');

    const textarea = document.querySelector('textarea');
    fireEvent.change(textarea, { target: { value: 'Hello Alpha Brands' } });

    const saveBtn = screen.getByRole('button', { name: /save_draft|save draft/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(composerAPI.posts.create).toHaveBeenCalledWith(
        expect.objectContaining({
          client: 21,
          content: 'Hello Alpha Brands',
        })
      );
    });
  });

  test('InvitationPage allows unauthenticated new user to set password and accept', async () => {
    mockUser = null;
    invitationAPI.getByToken.mockResolvedValue({
      data: {
        token: 'tok-123',
        agency_name: 'Bop Agencia',
        agency_email: 'bopagencia@gmail.com',
        client_name: 'Test Alpha Brands S.A.',
        client_email: 'new.approver@alphabrands.test',
        role: 'approver',
        status: 'pending',
        is_expired: false,
        user_exists: false,
      },
    });
    invitationAPI.accept.mockResolvedValue({
      data: { status: 'accepted', access: 'jwt-a', refresh: 'jwt-r' },
    });

    render(
      <MemoryRouter initialEntries={['/invitation/tok-123']}>
        <Routes>
          <Route path="/invitation/:token" element={<InvitationPage />} />
          <Route path="/u" element={<div>Client Portal</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Test Alpha Brands S.A./i)).toBeInTheDocument();
    });

    const inputs = document.querySelectorAll('input');
    fireEvent.change(inputs[0], { target: { value: 'Jane Approver' } });
    fireEvent.change(inputs[1], { target: { value: 'StrongPass123!' } });
    fireEvent.change(inputs[2], { target: { value: 'StrongPass123!' } });

    fireEvent.click(screen.getByRole('button', { name: /create account & accept/i }));

    await waitFor(() => {
      expect(invitationAPI.accept).toHaveBeenCalledWith('tok-123', {
        full_name: 'Jane Approver',
        password: 'StrongPass123!',
      });
      expect(mockRefreshAuth).toHaveBeenCalledWith('jwt-a', 'jwt-r');
    });
  });
});
