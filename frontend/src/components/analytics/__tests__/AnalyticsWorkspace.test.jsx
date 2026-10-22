import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import AnalyticsWorkspace from '../AnalyticsWorkspace';
import * as api from '../../../services/api';

// Mock API module
jest.mock('../../../services/api', () => ({
  analyticsAPI: {
    summary: jest.fn(),
    trends: jest.fn(),
    topPosts: jest.fn(),
  },
}));

// Mock recharts ResponsiveContainer and charts to avoid DOM measurement issues in Jest
jest.mock('recharts', () => {
  const OriginalModule = jest.requireActual('recharts');
  return {
    ...OriginalModule,
    ResponsiveContainer: ({ children }) => <div className="recharts-responsive-container">{children}</div>,
  };
});

const mockSummaryResponse = {
  data: {
    client_id: 3,
    platform: 'all',
    period: 'day',
    date_range: { start: '2026-09-21', end: '2026-10-21' },
    capabilities: {
      facebook: {
        platform: 'facebook',
        display_name: 'Facebook Page',
        status: 'FULL',
        notes: 'Full Page insights active',
      },
      instagram: {
        platform: 'instagram',
        display_name: 'Instagram (Basic Mode)',
        status: 'PARTIAL',
        notes: 'Basic mode active without manage_insights',
        permission_guidance: 'Advanced Instagram insights require additional Meta permissions.',
      },
    },
    metrics: {
      FOLLOWERS_TOTAL: {
        metric_key: 'FOLLOWERS_TOTAL',
        display_name: 'Total Followers',
        value: 12500,
        is_available: true,
        unavailable_reason: null,
      },
      REACTIONS: {
        metric_key: 'REACTIONS',
        display_name: 'Reactions / Likes',
        value: 340,
        is_available: true,
        unavailable_reason: null,
      },
      COMMENTS: {
        metric_key: 'COMMENTS',
        display_name: 'Comments',
        value: 52,
        is_available: true,
        unavailable_reason: null,
      },
      REACH: {
        metric_key: 'REACH',
        display_name: 'Reach',
        value: null,
        is_available: false,
        unavailable_reason: 'Unavailable for aggregated period',
        caveat: 'Unique daily audiences cannot be safely summed across days.',
      },
      VIDEO_VIEWS: {
        metric_key: 'VIDEO_VIEWS',
        display_name: 'Video Views',
        value: null,
        is_available: false,
        unavailable_reason: 'Not available with current Instagram permissions',
      },
    },
    data_health: [
      {
        platform: 'facebook',
        display_name: 'Facebook Page',
        capability_mode: 'FULL',
        freshness_status: 'Fresh',
        last_synced_at: '2026-10-21T19:30:00Z',
        age_seconds: 180,
      },
      {
        platform: 'instagram',
        display_name: 'Instagram Professional',
        capability_mode: 'PARTIAL',
        freshness_status: 'Fresh',
        last_synced_at: '2026-10-21T19:30:00Z',
        age_seconds: 180,
        permission_guidance: 'Advanced Instagram insights require additional Meta permissions.',
      },
    ],
  },
};

const mockTopPostsResponse = {
  data: {
    client_id: 3,
    platform: 'all',
    ranking_metric: 'REACTIONS',
    count: 2,
    posts: [
      {
        object_id: 'fb_post_bop_12',
        platform: 'facebook',
        ranking_metric: 'REACTIONS',
        ranking_value: 95,
        is_bop_authored: true,
        source_label: 'Published by Bop Social',
        unified_post_id: 12,
        caption: 'Bop Social Official Launch Post',
        permalink: 'https://facebook.com/posts/fb_post_bop_12',
        media_type: 'image',
        published_at: '2026-10-21T18:00:00Z',
        metrics: { REACTIONS: 95, COMMENTS: 12, SHARES: 8 },
      },
      {
        object_id: 'ig_post_org_44',
        platform: 'instagram',
        ranking_metric: 'REACTIONS',
        ranking_value: 80,
        is_bop_authored: false,
        source_label: 'Organic / External',
        unified_post_id: null,
        caption: 'Organic community photo from feed',
        permalink: 'https://instagram.com/p/ig_post_org_44',
        media_type: 'image',
        published_at: '2026-10-20T14:30:00Z',
        metrics: { REACTIONS: 80, COMMENTS: 5 },
      },
    ],
  },
};

describe('AnalyticsWorkspace UI Suite (BS-4E)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api.analyticsAPI.summary.mockResolvedValue(mockSummaryResponse);
    api.analyticsAPI.trends.mockResolvedValue({ data: { is_available: true, datapoints: [] } });
    api.analyticsAPI.topPosts.mockResolvedValue(mockTopPostsResponse);
  });

  const renderComponent = () =>
    render(
      <BrowserRouter>
        <AnalyticsWorkspace clientId={3} clientName="Alpha Agency" />
      </BrowserRouter>
    );

  test('01: renders executive KPI summary cards with available numeric values', async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByText('Total Followers')).toBeInTheDocument();
      expect(screen.getByText('12.5K')).toBeInTheDocument();
      expect(screen.getByText('340')).toBeInTheDocument();
    });
  });

  test('02: unavailable metrics render explicit Unavailable state, never zero', async () => {
    renderComponent();
    await waitFor(() => {
      // REACH should NOT display 0
      expect(screen.queryByText(/^0$/)).not.toBeInTheDocument();
      // Must display Unavailable label and reason
      const unavailLabels = screen.getAllByText('Unavailable');
      expect(unavailLabels.length).toBeGreaterThan(0);
      expect(screen.getByText(/Unique daily audiences cannot be safely summed across days/)).toBeInTheDocument();
    });
  });

  test('03: displays Instagram partial mode badge and notice', async () => {
    renderComponent();
    await waitFor(() => {
      expect(screen.getByText(/Instagram Partial Mode:/)).toBeInTheDocument();
      expect(screen.getByText(/instagram_manage_insights/)).toBeInTheDocument();
    });
  });

  test('04: switches to Content Performance tab and renders deduplicated posts with Bop and Organic labels', async () => {
    renderComponent();
    const contentTab = screen.getByText('3. Content Performance');
    fireEvent.click(contentTab);

    await waitFor(() => {
      expect(screen.getByText('Top Performing Content Objects')).toBeInTheDocument();
      expect(screen.getByText('Published by Bop Social')).toBeInTheDocument();
      expect(screen.getByText('Organic / External')).toBeInTheDocument();
      expect(screen.getByText('Bop Social Official Launch Post')).toBeInTheDocument();
      expect(screen.getByText('Organic community photo from feed')).toBeInTheDocument();
    });
  });

  test('05: switches to Platform Breakdown tab and displays Facebook Full vs Instagram Partial', async () => {
    renderComponent();
    const platformTab = screen.getByText('4. Platform Breakdown');
    fireEvent.click(platformTab);

    await waitFor(() => {
      expect(screen.getByText('Full Analytics')).toBeInTheDocument();
      expect(screen.getByText('Partial Analytics')).toBeInTheDocument();
      expect(screen.getByText(/Operating in/)).toBeInTheDocument();
    });
  });

  test('06: switches to Data Health & Freshness tab and renders telemetry status', async () => {
    renderComponent();
    const healthTab = screen.getByText('5. Data Health & Freshness');
    fireEvent.click(healthTab);

    await waitFor(() => {
      expect(screen.getByText('Data Health & Telemetry Status')).toBeInTheDocument();
      const freshBadges = screen.getAllByText('Fresh');
      expect(freshBadges.length).toBeGreaterThanOrEqual(2);
    });
  });
});
