/* ============================================================================
 *  Bop Social — Unified Analytics & Executive Insights Workspace (BS-4E)
 *  Consumes normalized read layer APIs (/api/analytics/*) backed by
 *  SocialMetricRollup and SocialMetricSnapshot data.
 * ========================================================================== */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import {
  TrendingUp, TrendingDown, Minus, RefreshCw, Users, Eye,
  MousePointer, Play, UserPlus, AlertCircle, CheckCircle2,
  Clock, ExternalLink, ShieldCheck, HelpCircle, Info,
  Layers, BarChart2, MessageSquare, ThumbsUp, Share2,
  Bookmark, Video, Image, FileText, Smartphone,
  Zap, ChevronDown, ChevronUp, Target
} from 'lucide-react';
import { analyticsAPI } from '../../services/api';
import SocialPlatformIcon from '../ui/SocialPlatformIcon';

// ── Metric Visual Metadata ──────────────────────────────────────────────────
const METRIC_CONFIG = {
  FOLLOWERS_TOTAL:      { label: 'Total Followers',       icon: Users,        color: '#059669', isGauge: true },
  FOLLOWERS_NET_CHANGE: { label: 'Net Follower Change',   icon: UserPlus,     color: '#10b981' },
  ENGAGEMENT_TOTAL:     { label: 'Total Engagement',      icon: Layers,       color: '#6366f1' },
  REACTIONS:            { label: 'Reactions / Likes',     icon: ThumbsUp,     color: '#3b82f6' },
  COMMENTS:             { label: 'Comments',              icon: MessageSquare,color: '#8b5cf6' },
  SHARES:               { label: 'Shares',                icon: Share2,       color: '#ec4899' },
  PROFILE_VIEWS:        { label: 'Profile Views',         icon: Eye,          color: '#f59e0b' },
  VIDEO_VIEWS:          { label: 'Video Views',           icon: Play,         color: '#06b6d4' },
  REACH:                { label: 'Reach',                 icon: Users,        color: '#00d7ff', nonAggregatable: true },
};

function fmt(n) {
  if (n === null || n === undefined || isNaN(n)) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
  return Number(n).toLocaleString();
}

function formatRelativeAge(seconds) {
  if (!seconds && seconds !== 0) return 'Unknown';
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86400)}d ago`;
}

// ── KPI Card Component ──────────────────────────────────────────────────────
function MetricKPICard({ metricKey, data, loading }) {
  const meta = METRIC_CONFIG[metricKey] || { label: metricKey, icon: BarChart2, color: '#6366f1' };
  const Icon = meta.icon;
  const isAvailable = data ? data.is_available : false;
  const val = data?.value;
  const reason = data?.unavailable_reason;
  const warning = data?.comparability_warning || data?.caveat;

  return (
    <div style={{
      background: 'var(--surface-card)',
      borderRadius: 14,
      padding: '20px 22px',
      border: '1px solid var(--border-default)',
      flex: '1 1 200px',
      minWidth: 200,
      maxWidth: 'calc(33.333% - 14px)',
      boxShadow: '0 1px 6px rgba(0,0,0,0.04)',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      position: 'relative',
    }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10, display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              background: meta.color + '18',
            }}>
              <Icon size={18} color={meta.color} />
            </div>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {meta.label}
            </span>
          </div>
          {warning && (
            <div title={warning} style={{ cursor: 'help' }}>
              <HelpCircle size={15} color="#f59e0b" />
            </div>
          )}
        </div>

        {loading ? (
          <div style={{ height: 36, background: 'var(--surface-page)', borderRadius: 6, animation: 'pulse 1.5s infinite' }} />
        ) : isAvailable && val !== null ? (
          <div>
            <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1.1 }}>
              {fmt(val)}
            </div>
            {meta.isGauge && (
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 4 }}>
                Latest snapshot observation
              </div>
            )}
          </div>
        ) : (
          <div style={{
            background: 'var(--surface-page)',
            borderRadius: 8,
            padding: '8px 12px',
            border: '1px dashed var(--border-default)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#f59e0b', fontSize: 12, fontWeight: 700 }}>
              <AlertCircle size={14} />
              <span>Unavailable</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 4, lineHeight: 1.3 }}>
              {reason || 'Not available for current scope'}
            </div>
          </div>
        )}
      </div>

      {warning && (
        <div style={{
          marginTop: 10,
          paddingTop: 8,
          borderTop: '1px solid var(--border-subtle)',
          fontSize: 10.5,
          color: 'var(--text-tertiary)',
          lineHeight: 1.25,
        }}>
          ⚠️ {warning}
        </div>
      )}


    </div>
  );
}

// ── Main Analytics Workspace ────────────────────────────────────────────────
export default function AnalyticsWorkspace({ clientId, clientName, allClients = [] }) {
  const [searchParams, setSearchParams] = useSearchParams();

  // URL state persistence
  const initialPlatform = searchParams.get('platform') || 'all';
  const initialPeriod = searchParams.get('period') || 'day';
  const initialDays = parseInt(searchParams.get('days') || '30', 10);
  const initialTab = searchParams.get('tab') || 'overview';

  const [activeTab, setActiveTab] = useState(initialTab);
  const [platform, setPlatform] = useState(initialPlatform);
  const [period, setPeriod] = useState(initialPeriod);
  const [days, setDays] = useState(initialDays);
  const [activeMetric, setActiveMetric] = useState('REACTIONS');
  const [rankingMetric, setRankingMetric] = useState('REACTIONS');

  // Sync state to URL params
  useEffect(() => {
    const params = new URLSearchParams(searchParams);
    params.set('platform', platform);
    params.set('period', period);
    params.set('days', String(days));
    params.set('tab', activeTab);
    setSearchParams(params, { replace: true });
  }, [platform, period, days, activeTab, setSearchParams]);

  // Compute date range
  const dateRange = useMemo(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - days);
    return {
      start_date: start.toISOString().slice(0, 10),
      end_date: end.toISOString().slice(0, 10),
    };
  }, [days]);

  // Data states
  const [summaryData, setSummaryData] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState(null);

  const [trendsData, setTrendsData] = useState([]);
  const [trendsMeta, setTrendsMeta] = useState(null);
  const [trendsLoading, setTrendsLoading] = useState(false);

  const [topPosts, setTopPosts] = useState([]);
  const [topPostsLoading, setTopPostsLoading] = useState(false);

  // Business Intelligence & Signals State
  const [insightsData, setInsightsData] = useState(null);
  const [summaryBI, setSummaryBI] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsError, setInsightsError] = useState(null);
  const [expandedEvidence, setExpandedEvidence] = useState({});

  // Fetch Summary
  const fetchSummary = useCallback(() => {
    if (!clientId) return;
    setSummaryLoading(true);
    setSummaryError(null);
    analyticsAPI.summary({
      client_id: clientId,
      platform,
      period,
      start_date: dateRange.start_date,
      end_date: dateRange.end_date,
    })
      .then(res => setSummaryData(res.data))
      .catch(err => {
        const msg = err.response?.data?.error || 'Failed to load analytics summary';
        setSummaryError(msg);
      })
      .finally(() => setSummaryLoading(false));
  }, [clientId, platform, period, dateRange.start_date, dateRange.end_date]);

  // Fetch Trends
  const fetchTrends = useCallback(() => {
    if (!clientId) return;
    setTrendsLoading(true);
    analyticsAPI.trends({
      client_id: clientId,
      metric: activeMetric,
      platform,
      period,
      start_date: dateRange.start_date,
      end_date: dateRange.end_date,
    })
      .then(res => {
        setTrendsData(res.data?.datapoints || []);
        setTrendsMeta(res.data);
      })
      .catch(() => {
        setTrendsData([]);
        setTrendsMeta(null);
      })
      .finally(() => setTrendsLoading(false));
  }, [clientId, activeMetric, platform, period, dateRange.start_date, dateRange.end_date]);

  // Fetch Top Posts
  const fetchTopPosts = useCallback(() => {
    if (!clientId) return;
    setTopPostsLoading(true);
    analyticsAPI.topPosts({
      client_id: clientId,
      platform,
      metric: rankingMetric,
      limit: 20,
      start_date: dateRange.start_date,
      end_date: dateRange.end_date,
    })
      .then(res => setTopPosts(res.data?.posts || []))
      .catch(() => setTopPosts([]))
      .finally(() => setTopPostsLoading(false));
  }, [clientId, platform, rankingMetric, dateRange.start_date, dateRange.end_date]);

  // Fetch Business Intelligence Signals & Executive Summary
  const fetchInsights = useCallback(() => {
    if (!clientId) return;
    setInsightsLoading(true);
    setInsightsError(null);
    Promise.all([
      analyticsAPI.insights({
        client_id: clientId,
        platform,
        start_date: dateRange.start_date,
        end_date: dateRange.end_date,
      }),
      analyticsAPI.executiveSummary({
        client_id: clientId,
        platform,
        start_date: dateRange.start_date,
        end_date: dateRange.end_date,
      }),
    ])
      .then(([insRes, sumRes]) => {
        setInsightsData(insRes.data);
        setSummaryBI(sumRes.data);
      })
      .catch(err => {
        const msg = err.response?.data?.error || 'Failed to load business intelligence signals';
        setInsightsError(msg);
      })
      .finally(() => setInsightsLoading(false));
  }, [clientId, platform, dateRange.start_date, dateRange.end_date]);

  // Effects
  useEffect(() => { fetchSummary(); }, [fetchSummary]);
  useEffect(() => {
    if (activeTab === 'trends') fetchTrends();
  }, [activeTab, fetchTrends]);
  useEffect(() => {
    if (activeTab === 'content') fetchTopPosts();
  }, [activeTab, fetchTopPosts]);
  useEffect(() => {
    if (activeTab === 'intelligence') fetchInsights();
  }, [activeTab, fetchInsights]);

  // Refresh all active data
  const handleRefresh = () => {
    fetchSummary();
    if (activeTab === 'trends') fetchTrends();
    if (activeTab === 'content') fetchTopPosts();
    if (activeTab === 'intelligence') fetchInsights();
  };

  const isInstagramDegraded = summaryData?.capabilities?.instagram?.status === 'PARTIAL';

  return (
    <div style={{ padding: '24px 32px', background: 'var(--surface-page)', minHeight: '100vh', color: 'var(--text-primary)' }}>
      {/* ── Top Header & Global Filter Bar ───────────────────────────────── */}
      <div style={{
        background: 'var(--surface-card)',
        borderRadius: 16,
        padding: '20px 24px',
        border: '1px solid var(--border-default)',
        marginBottom: 24,
        boxShadow: '0 2px 10px rgba(0,0,0,0.03)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>
              Analytics & Executive Insights
            </h1>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '4px 0 0' }}>
              {clientName ? `Client: ${clientName}` : 'Normalized Social Analytics Workspace'}
            </p>
          </div>

          {/* Controls Bar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            {/* Platform Selector */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-tertiary)' }}>Platform:</span>
              <select
                value={platform}
                onChange={e => setPlatform(e.target.value)}
                style={controlSelectStyle}
              >
                <option value="all">All Platforms</option>
                <option value="facebook">Facebook</option>
                <option value="instagram">Instagram</option>
              </select>
            </div>

            {/* Date Presets */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-tertiary)' }}>Range:</span>
              <div style={{ display: 'flex', background: 'var(--surface-sunken)', borderRadius: 8, padding: 3 }}>
                {[7, 30, 90].map(d => (
                  <button
                    key={d}
                    onClick={() => setDays(d)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 6,
                      border: 'none',
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: 'pointer',
                      background: days === d ? 'var(--surface-card)' : 'transparent',
                      color: days === d ? 'var(--text-primary)' : 'var(--text-secondary)',
                      boxShadow: days === d ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                    }}
                  >
                    {d}d
                  </button>
                ))}
              </div>
            </div>

            {/* Period Selector */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-tertiary)' }}>Bucket:</span>
              <select
                value={period}
                onChange={e => setPeriod(e.target.value)}
                style={controlSelectStyle}
              >
                <option value="day">Day</option>
                <option value="week">Week</option>
                <option value="month">Month</option>
              </select>
            </div>

            {/* Refresh Button */}
            <button
              onClick={handleRefresh}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '8px 14px', borderRadius: 8,
                border: '1px solid var(--border-default)',
                background: 'var(--surface-card)', color: 'var(--text-secondary)',
                cursor: 'pointer', fontSize: 12, fontWeight: 700,
              }}
              title="Refresh Data"
            >
              <RefreshCw size={14} className={summaryLoading ? 'animate-spin' : ''} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Global Warnings / Context Banners */}
        {platform === 'all' && (
          <div style={{
            marginTop: 16,
            padding: '10px 14px',
            background: 'rgba(59, 130, 246, 0.08)',
            border: '1px solid rgba(59, 130, 246, 0.2)',
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            fontSize: 12,
            color: 'var(--text-secondary)',
          }}>
            <Info size={16} color="#3b82f6" />
            <span>
              <strong>Cross-Platform Mode:</strong> Only metrics with strictly comparable semantics are aggregated. Provider-specific nuances (such as Video Views and Clicks) are preserved with caveats.
            </span>
          </div>
        )}

        {isInstagramDegraded && (platform === 'all' || platform === 'instagram') && (
          <div style={{
            marginTop: 10,
            padding: '10px 14px',
            background: 'rgba(245, 158, 11, 0.08)',
            border: '1px solid rgba(245, 158, 11, 0.25)',
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            fontSize: 12,
            color: 'var(--text-secondary)',
          }}>
            <AlertCircle size={16} color="#f59e0b" />
            <span>
              <strong>Instagram Partial Mode:</strong> Basic media counters (Reactions, Comments, Total Followers) are active. Advanced metrics (Reach, Saves, Profile Views) require <code>instagram_manage_insights</code> permissions.
            </span>
          </div>
        )}
      </div>

      {/* ── Section Navigation Tabs ───────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24, borderBottom: '1px solid var(--border-default)', paddingBottom: 8 }}>
        {[
          { id: 'overview',     label: '1. Overview', icon: Layers },
          { id: 'trends',       label: '2. Trends', icon: BarChart2 },
          { id: 'content',      label: '3. Content Performance', icon: FileText },
          { id: 'platform',     label: '4. Platform Breakdown', icon: Smartphone },
          { id: 'health',       label: '5. Data Health & Freshness', icon: ShieldCheck },
          { id: 'intelligence', label: '6. Executive Insights & BI', icon: Zap },
        ].map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '10px 18px',
                borderRadius: 10,
                border: 'none',
                background: isActive ? 'var(--surface-card)' : 'transparent',
                color: isActive ? '#00d7ff' : 'var(--text-secondary)',
                fontWeight: isActive ? 800 : 600,
                fontSize: 13,
                cursor: 'pointer',
                boxShadow: isActive ? '0 1px 4px rgba(0,0,0,0.06)' : 'none',
                borderBottom: isActive ? '2px solid #00d7ff' : '2px solid transparent',
              }}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* ── Error Banner ──────────────────────────────────────────────────── */}
      {summaryError && (
        <div style={{
          padding: '14px 18px',
          background: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid #ef4444',
          borderRadius: 10,
          marginBottom: 20,
          color: '#ef4444',
          fontSize: 13,
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <AlertCircle size={18} />
          <span>{summaryError}</span>
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 1: OVERVIEW                                                       */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'overview' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ fontSize: 16, fontWeight: 800, margin: 0 }}>Executive KPI Summary</h2>
            <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
              Window: {dateRange.start_date} to {dateRange.end_date} (Bucket: {period})
            </span>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginBottom: 28 }}>
            {[
              'FOLLOWERS_TOTAL',
              'FOLLOWERS_NET_CHANGE',
              'ENGAGEMENT_TOTAL',
              'REACTIONS',
              'COMMENTS',
              'SHARES',
              'PROFILE_VIEWS',
              'VIDEO_VIEWS',
              'REACH',
            ].map(k => (
              <MetricKPICard
                key={k}
                metricKey={k}
                data={summaryData?.metrics?.[k]}
                loading={summaryLoading}
              />
            ))}
          </div>

          {/* Quick Health Summary Pill */}
          <div style={{
            background: 'var(--surface-card)',
            borderRadius: 12,
            padding: '16px 20px',
            border: '1px solid var(--border-default)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 12,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <ShieldCheck size={18} color="#059669" />
              <span style={{ fontSize: 13, fontWeight: 700 }}>Telemetry Status:</span>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                Tenant isolated, normalized against Metric Registry v1.
              </span>
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              {(summaryData?.data_health || []).map(h => (
                <div key={h.platform} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                  <SocialPlatformIcon platform={h.platform} size={14} />
                  <span style={{ fontWeight: 600 }}>{h.display_name}:</span>
                  <span style={{
                    padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 700,
                    background: h.capability_mode === 'FULL' ? 'rgba(5, 150, 105, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                    color: h.capability_mode === 'FULL' ? '#059669' : '#d97706',
                  }}>
                    {h.capability_mode}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 2: TRENDS                                                         */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'trends' && (
        <div style={{
          background: 'var(--surface-card)',
          borderRadius: 16,
          padding: '24px 28px',
          border: '1px solid var(--border-default)',
          boxShadow: '0 2px 10px rgba(0,0,0,0.03)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16, marginBottom: 20 }}>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 800, margin: 0 }}>
                Chronological Timeseries Trends
              </h2>
              <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: '4px 0 0' }}>
                Observed rollup datapoints over selected date window.
              </p>
            </div>

            {/* Metric Selection Pills */}
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {[
                'REACTIONS',
                'COMMENTS',
                'SHARES',
                'ENGAGEMENT_TOTAL',
                'FOLLOWERS_TOTAL',
                'REACH',
              ].map(m => {
                const conf = METRIC_CONFIG[m] || { label: m, color: '#6366f1' };
                const isSelected = activeMetric === m;
                return (
                  <button
                    key={m}
                    onClick={() => setActiveMetric(m)}
                    style={{
                      padding: '5px 12px',
                      borderRadius: 20,
                      border: '1px solid',
                      borderColor: isSelected ? conf.color : 'var(--border-default)',
                      background: isSelected ? conf.color : 'var(--surface-sunken)',
                      color: isSelected ? '#fff' : 'var(--text-secondary)',
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {conf.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Metric Specific Caveats */}
          {activeMetric === 'FOLLOWERS_TOTAL' && (
            <div style={{ padding: '8px 12px', background: 'rgba(5, 150, 105, 0.08)', borderRadius: 8, marginBottom: 16, fontSize: 12, color: '#059669' }}>
              💡 <strong>Gauge Semantics:</strong> Follower count represents the observed total at snapshot time. Points are non-cumulative.
            </div>
          )}

          {activeMetric === 'REACH' && period !== 'day' && (
            <div style={{ padding: '8px 12px', background: 'rgba(239, 68, 68, 0.08)', borderRadius: 8, marginBottom: 16, fontSize: 12, color: '#ef4444' }}>
              ⚠️ <strong>Aggregation Safety:</strong> Reach cannot be safely summed across days into weekly or monthly buckets due to unique daily audience overlap. Switch to 'Day' bucket to view daily reach.
            </div>
          )}

          {/* Chart Rendering */}
          {trendsLoading ? (
            <div style={{ height: 320, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)' }}>
              Loading timeseries data...
            </div>
          ) : trendsMeta && !trendsMeta.is_available ? (
            <div style={{
              height: 280, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              border: '1px dashed var(--border-default)', borderRadius: 12, padding: 24, textAlign: 'center',
            }}>
              <AlertCircle size={32} color="#f59e0b" style={{ marginBottom: 12 }} />
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                {trendsMeta.unavailable_reason || 'Metric Unavailable'}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 6, maxWidth: 440 }}>
                {trendsMeta.permission_guidance || 'This metric is not supported under the active platform configuration.'}
              </div>
            </div>
          ) : trendsData.length === 0 ? (
            <div style={{
              height: 280, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              border: '1px dashed var(--border-default)', borderRadius: 12, color: 'var(--text-tertiary)',
            }}>
              <BarChart2 size={32} style={{ marginBottom: 8, opacity: 0.5 }} />
              <div>No rollup datapoints recorded for {activeMetric} in this window.</div>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <AreaChart data={trendsData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                <defs>
                  <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={METRIC_CONFIG[activeMetric]?.color || '#00d7ff'} stopOpacity={0.25} />
                    <stop offset="95%" stopColor={METRIC_CONFIG[activeMetric]?.color || '#00d7ff'} stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                <XAxis dataKey="period_start" tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} />
                <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} width={55} />
                <Tooltip
                  formatter={(val) => [val !== null ? fmt(val) : 'Unavailable', METRIC_CONFIG[activeMetric]?.label || activeMetric]}
                  labelFormatter={(lbl) => `Period: ${lbl}`}
                  contentStyle={{
                    background: 'var(--surface-card)',
                    border: '1px solid var(--border-default)',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="metric_value"
                  stroke={METRIC_CONFIG[activeMetric]?.color || '#00d7ff'}
                  strokeWidth={2.5}
                  fill="url(#trendGrad)"
                  dot={trendsData.length <= 31 ? { r: 3 } : false}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 3: CONTENT PERFORMANCE                                            */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'content' && (
        <div style={{
          background: 'var(--surface-card)',
          borderRadius: 16,
          padding: '24px 28px',
          border: '1px solid var(--border-default)',
          boxShadow: '0 2px 10px rgba(0,0,0,0.03)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16, marginBottom: 20 }}>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 800, margin: 0 }}>
                Top Performing Content Objects
              </h2>
              <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: '4px 0 0' }}>
                Strictly deduplicated unique content objects ranked by normalized metric observations.
              </p>
            </div>

            {/* Rank metric selector */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-tertiary)' }}>Rank by:</span>
              <select
                value={rankingMetric}
                onChange={e => setRankingMetric(e.target.value)}
                style={controlSelectStyle}
              >
                <option value="REACTIONS">Reactions / Likes</option>
                <option value="COMMENTS">Comments</option>
                <option value="SHARES">Shares</option>
              </select>
            </div>
          </div>

          {topPostsLoading ? (
            <div style={{ height: 240, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)' }}>
              Loading top content objects...
            </div>
          ) : topPosts.length === 0 ? (
            <div style={{
              height: 200, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              border: '1px dashed var(--border-default)', borderRadius: 12, color: 'var(--text-tertiary)',
            }}>
              <FileText size={32} style={{ marginBottom: 8, opacity: 0.5 }} />
              <div>No content performance observations found for current filter.</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {topPosts.map((post, idx) => (
                <div
                  key={`${post.platform}-${post.object_id}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '16px 20px',
                    borderRadius: 12,
                    background: 'var(--surface-sunken)',
                    border: '1px solid var(--border-default)',
                    flexWrap: 'wrap',
                    gap: 16,
                  }}
                >
                  {/* Left: Rank, Platform, Type & Identity */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 260, flex: '1 1 300px' }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: 8,
                      background: idx < 3 ? '#00d7ff22' : 'var(--surface-card)',
                      color: idx < 3 ? '#00d7ff' : 'var(--text-tertiary)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontWeight: 800, fontSize: 13,
                    }}>
                      #{idx + 1}
                    </div>

                    <div style={{
                      width: 34, height: 34, borderRadius: 8,
                      background: 'var(--surface-card)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <SocialPlatformIcon platform={post.platform} size={18} />
                    </div>

                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        {/* Source Label */}
                        <span style={{
                          padding: '2px 8px', borderRadius: 10, fontSize: 10.5, fontWeight: 800,
                          background: post.is_bop_authored ? 'rgba(99, 102, 241, 0.15)' : 'rgba(107, 114, 128, 0.15)',
                          color: post.is_bop_authored ? '#6366f1' : 'var(--text-secondary)',
                        }}>
                          {post.source_label}
                        </span>

                        {/* Media Type */}
                        <span style={{
                          padding: '2px 7px', borderRadius: 10, fontSize: 10, fontWeight: 700,
                          background: 'var(--surface-card)', color: 'var(--text-tertiary)',
                          textTransform: 'uppercase',
                        }}>
                          {post.media_type}
                        </span>

                        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                          ID: {post.object_id.slice(-8)}
                        </span>
                      </div>

                      {/* Caption Snippet */}
                      <div style={{
                        fontSize: 13, fontWeight: 600, color: 'var(--text-primary)',
                        marginTop: 4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 420,
                      }}>
                        {post.caption || '(No caption recorded)'}
                      </div>
                    </div>
                  </div>

                  {/* Right: Metrics & Permalink */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <div style={{ display: 'flex', gap: 14 }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: 14, fontWeight: 800, color: '#3b82f6' }}>
                          {fmt(post.metrics?.REACTIONS ?? 0)}
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                          Likes
                        </div>
                      </div>

                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: 14, fontWeight: 800, color: '#8b5cf6' }}>
                          {fmt(post.metrics?.COMMENTS ?? 0)}
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                          Comments
                        </div>
                      </div>

                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: 14, fontWeight: 800, color: '#ec4899' }}>
                          {fmt(post.metrics?.SHARES ?? 0)}
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                          Shares
                        </div>
                      </div>
                    </div>

                    {post.permalink && (
                      <a
                        href={post.permalink}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          width: 32, height: 32, borderRadius: 8,
                          background: 'var(--surface-card)', border: '1px solid var(--border-default)',
                          color: 'var(--text-secondary)',
                        }}
                        title="View Post on Platform"
                      >
                        <ExternalLink size={14} />
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 4: PLATFORM BREAKDOWN                                             */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'platform' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 20 }}>
          {/* Facebook Card */}
          <div style={{
            background: 'var(--surface-card)',
            borderRadius: 16,
            padding: '24px 26px',
            border: '1px solid var(--border-default)',
            boxShadow: '0 2px 10px rgba(0,0,0,0.03)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 40, height: 40, borderRadius: 10,
                  background: 'rgba(24, 119, 242, 0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <SocialPlatformIcon platform="facebook" size={22} />
                </div>
                <div>
                  <h3 style={{ fontSize: 16, fontWeight: 800, margin: 0 }}>Facebook Page</h3>
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Page Insights & Post Metrics</span>
                </div>
              </div>

              <span style={{
                padding: '4px 10px', borderRadius: 12, fontSize: 11, fontWeight: 800,
                background: 'rgba(5, 150, 105, 0.15)', color: '#059669',
              }}>
                Full Analytics
              </span>
            </div>

            <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 18 }}>
              Comprehensive Page level and Post level insights supported via Meta Graph API v21.0. Daily reach observations and cross-post engagement are fully queryable.
            </div>

            <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: 8 }}>
                Supported Capabilities
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                <li>Account Timeseries & Profile Follower Total</li>
                <li>Post Reactions, Comments, Shares, and Clicks</li>
                <li>Single-day Unique Reach Observations</li>
                <li>Video Views & Retention Rollups</li>
              </ul>
            </div>
          </div>

          {/* Instagram Card */}
          <div style={{
            background: 'var(--surface-card)',
            borderRadius: 16,
            padding: '24px 26px',
            border: '1px solid var(--border-default)',
            boxShadow: '0 2px 10px rgba(0,0,0,0.03)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 40, height: 40, borderRadius: 10,
                  background: 'rgba(225, 48, 108, 0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <SocialPlatformIcon platform="instagram" size={22} />
                </div>
                <div>
                  <h3 style={{ fontSize: 16, fontWeight: 800, margin: 0 }}>Instagram Professional</h3>
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Connected Professional Account</span>
                </div>
              </div>

              <span style={{
                padding: '4px 10px', borderRadius: 12, fontSize: 11, fontWeight: 800,
                background: 'rgba(245, 158, 11, 0.15)', color: '#d97706',
              }}>
                Partial Analytics
              </span>
            </div>

            <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 18 }}>
              Operating in <strong>Basic Media Mode</strong>. Direct media counters (Likes, Comments, Total Followers) are active and verified.
            </div>

            <div style={{
              padding: '12px 14px', borderRadius: 10,
              background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.2)',
              marginBottom: 16, fontSize: 12, color: 'var(--text-secondary)',
            }}>
              <div style={{ fontWeight: 700, color: '#d97706', marginBottom: 4 }}>
                ℹ️ Permission Notice
              </div>
              Advanced Instagram insights (Account reach, impressions, stories, saves) require additional Meta permission (<code>instagram_manage_insights</code>).
            </div>

            <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: 8 }}>
                Current Status
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                <li>✅ Total Followers count active</li>
                <li>✅ Media Reactions & Comments active</li>
                <li>⚠️ Reach / Impressions unavailable under basic scopes</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 5: DATA HEALTH & FRESHNESS                                        */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'health' && (
        <div style={{
          background: 'var(--surface-card)',
          borderRadius: 16,
          padding: '24px 28px',
          border: '1px solid var(--border-default)',
          boxShadow: '0 2px 10px rgba(0,0,0,0.03)',
        }}>
          <h2 style={{ fontSize: 16, fontWeight: 800, margin: '0 0 6px' }}>
            Data Health & Telemetry Status
          </h2>
          <p style={{ fontSize: 12, color: 'var(--text-tertiary)', margin: '0 0 20px' }}>
            Audited synchronization cadence, snapshot recency, and credential degradation states.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
            {(summaryData?.data_health || []).map(health => (
              <div
                key={health.platform}
                style={{
                  background: 'var(--surface-sunken)',
                  borderRadius: 12,
                  padding: '18px 20px',
                  border: '1px solid var(--border-default)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <SocialPlatformIcon platform={health.platform} size={18} />
                    <span style={{ fontSize: 14, fontWeight: 700 }}>{health.display_name}</span>
                  </div>
                  <span style={{
                    padding: '3px 9px', borderRadius: 12, fontSize: 11, fontWeight: 800,
                    background: health.freshness_status === 'Fresh' ? 'rgba(5, 150, 105, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                    color: health.freshness_status === 'Fresh' ? '#059669' : '#ef4444',
                  }}>
                    {health.freshness_status}
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)' }}>
                    <span>Capability Mode:</span>
                    <strong style={{ color: health.capability_mode === 'FULL' ? '#059669' : '#d97706' }}>
                      {health.capability_mode}
                    </strong>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)' }}>
                    <span>Last Synced:</span>
                    <span>{health.last_synced_at ? health.last_synced_at.slice(0, 19).replace('T', ' ') + ' UTC' : 'None'}</span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)' }}>
                    <span>Data Age:</span>
                    <span>{formatRelativeAge(health.age_seconds)}</span>
                  </div>

                  {health.permission_guidance && (
                    <div style={{
                      marginTop: 8, padding: '8px 10px', borderRadius: 8,
                      background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.2)',
                      fontSize: 11, color: 'var(--text-secondary)',
                    }}>
                      {health.permission_guidance}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════ */}
      {/* TAB 6: EXECUTIVE INSIGHTS & BUSINESS INTELLIGENCE                     */}
      {/* ═════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'intelligence' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Executive Overview Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
            {/* Engagement Direction */}
            <div style={{
              background: 'var(--surface-card)', borderRadius: 14, padding: '18px 20px',
              border: '1px solid var(--border-default)', boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                  Engagement Trend
                </span>
                <span style={{
                  padding: '2px 8px', borderRadius: 12, fontSize: 10.5, fontWeight: 800,
                  background: summaryBI?.engagement_direction?.direction === 'UP' ? 'rgba(5, 150, 105, 0.15)' : (summaryBI?.engagement_direction?.direction === 'DOWN' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(100, 116, 139, 0.15)'),
                  color: summaryBI?.engagement_direction?.direction === 'UP' ? '#059669' : (summaryBI?.engagement_direction?.direction === 'DOWN' ? '#ef4444' : '#64748b'),
                }}>
                  {summaryBI?.engagement_direction?.direction || 'NEUTRAL'}
                </span>
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 4 }}>
                {summaryBI?.engagement_direction?.relative_delta != null ? `${(summaryBI.engagement_direction.relative_delta * 100).toFixed(1)}%` : '—'}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                {summaryBI?.engagement_direction?.explanation || 'Stable trend over period'}
              </div>
            </div>

            {/* Follower Direction */}
            <div style={{
              background: 'var(--surface-card)', borderRadius: 14, padding: '18px 20px',
              border: '1px solid var(--border-default)', boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                  Audience Direction
                </span>
                <span style={{
                  padding: '2px 8px', borderRadius: 12, fontSize: 10.5, fontWeight: 800,
                  background: summaryBI?.follower_direction?.direction === 'UP' ? 'rgba(5, 150, 105, 0.15)' : (summaryBI?.follower_direction?.direction === 'DOWN' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(100, 116, 139, 0.15)'),
                  color: summaryBI?.follower_direction?.direction === 'UP' ? '#059669' : (summaryBI?.follower_direction?.direction === 'DOWN' ? '#ef4444' : '#64748b'),
                }}>
                  {summaryBI?.follower_direction?.direction || 'NEUTRAL'}
                </span>
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 4 }}>
                {summaryBI?.follower_direction?.net_change != null ? `+${summaryBI.follower_direction.net_change}` : '—'}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                {summaryBI?.follower_direction?.explanation || 'Follower counts steady'}
              </div>
            </div>

            {/* Winning Formats Card */}
            <div style={{
              background: 'var(--surface-card)', borderRadius: 14, padding: '18px 20px',
              border: '1px solid var(--border-default)', boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                  Winning Format
                </span>
                <span style={{
                  padding: '2px 8px', borderRadius: 12, fontSize: 10.5, fontWeight: 800,
                  background: summaryBI?.winning_formats?.length > 0 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(100, 116, 139, 0.15)',
                  color: summaryBI?.winning_formats?.length > 0 ? '#10b981' : '#64748b',
                }}>
                  {summaryBI?.winning_formats?.length > 0 ? `${summaryBI.winning_formats[0].confidence} confidence` : 'Low sample'}
                </span>
              </div>
              <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 4 }}>
                {summaryBI?.winning_formats?.length > 0 ? `${summaryBI.winning_formats[0].format.toUpperCase()} (+${summaryBI.winning_formats[0].relative_delta_pct}%)` : 'Not enough comparable historical data yet'}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                {summaryBI?.winning_formats?.length > 0 ? `n=${summaryBI.winning_formats[0].sample_size} posts observed vs cohort median` : 'Publish more distinct formats to unlock format intelligence.'}
              </div>
            </div>

            {/* Posting Time Card */}
            <div style={{
              background: 'var(--surface-card)', borderRadius: 14, padding: '18px 20px',
              border: '1px solid var(--border-default)', boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                  Posting Time
                </span>
                <span style={{
                  padding: '2px 8px', borderRadius: 12, fontSize: 10.5, fontWeight: 800,
                  background: summaryBI?.posting_time_insights?.has_sufficient_data ? 'rgba(59, 130, 246, 0.15)' : 'rgba(100, 116, 139, 0.15)',
                  color: summaryBI?.posting_time_insights?.has_sufficient_data ? '#3b82f6' : '#64748b',
                }}>
                  {summaryBI?.posting_time_insights?.has_sufficient_data ? 'Supported' : 'Insufficient data'}
                </span>
              </div>
              <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 4 }}>
                {summaryBI?.posting_time_insights?.has_sufficient_data ? `${summaryBI.posting_time_insights.recommendations[0].bucket.toUpperCase()} (+${summaryBI.posting_time_insights.recommendations[0].relative_delta_pct}%)` : 'Not enough data yet'}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                {summaryBI?.posting_time_insights?.has_sufficient_data ? `Client timezone: ${clientName || 'Local'}` : 'Requires at least 5 posts across multiple time buckets to determine optimal hours.'}
              </div>
            </div>
          </div>

          {/* Key Business Signals Container */}
          <div style={{
            background: 'var(--surface-card)', borderRadius: 16, padding: '24px 28px',
            border: '1px solid var(--border-default)', boxShadow: '0 2px 10px rgba(0,0,0,0.03)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div>
                <h2 style={{ fontSize: 16, fontWeight: 800, margin: 0 }}>Deterministic Business Signals</h2>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '4px 0 0' }}>
                  Defensible, machine-readable performance conclusions derived strictly from statistical medians and verified cohorts.
                </p>
              </div>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-tertiary)' }}>
                {insightsData?.signals?.length || 0} signals identified
              </div>
            </div>

            {insightsLoading ? (
              <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-tertiary)' }}>
                Computing deterministic baselines and confidence tiers...
              </div>
            ) : (!insightsData?.signals || insightsData.signals.length === 0) ? (
              <div style={{
                padding: '40px 20px', textAlign: 'center', background: 'var(--surface-sunken)',
                borderRadius: 12, border: '1px dashed var(--border-default)',
              }}>
                <div style={{ fontSize: 24, marginBottom: 8 }}>📊</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                  Not enough comparable historical data yet
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', maxWidth: 480, margin: '0 auto' }}>
                  Signals require at least 3 comparable observations per cohort. As you publish more content, outperformance, momentum, and format baselines will activate automatically.
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {insightsData.signals.map(sig => {
                  const isExpanded = !!expandedEvidence[sig.signal_identity];
                  const relPct = sig.relative_delta != null ? `${(sig.relative_delta * 100).toFixed(1)}%` : null;

                  return (
                    <div
                      key={sig.signal_identity}
                      style={{
                        background: 'var(--surface-sunken)',
                        borderRadius: 12,
                        padding: '16px 20px',
                        border: '1px solid var(--border-default)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 10,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 10 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                          <SocialPlatformIcon platform={sig.platform} size={16} />
                          <span style={{ fontSize: 13, fontWeight: 800 }}>
                            {sig.signal_type.replace(/_/g, ' ')}
                          </span>
                          {/* Severity Badge */}
                          <span style={{
                            padding: '2px 8px', borderRadius: 12, fontSize: 10.5, fontWeight: 800,
                            background: sig.severity === 'POSITIVE' ? 'rgba(5, 150, 105, 0.15)' : (sig.severity === 'CRITICAL' ? 'rgba(239, 68, 68, 0.2)' : (sig.severity === 'WARNING' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(100, 116, 139, 0.15)')),
                            color: sig.severity === 'POSITIVE' ? '#059669' : (sig.severity === 'CRITICAL' ? '#dc2626' : (sig.severity === 'WARNING' ? '#d97706' : '#64748b')),
                          }}>
                            {sig.severity}
                          </span>
                          {/* Confidence Badge */}
                          <span style={{
                            padding: '2px 8px', borderRadius: 12, fontSize: 10.5, fontWeight: 700,
                            background: sig.confidence_level === 'HIGH' ? 'rgba(59, 130, 246, 0.15)' : (sig.confidence_level === 'MEDIUM' ? 'rgba(139, 92, 246, 0.15)' : 'rgba(100, 116, 139, 0.15)'),
                            color: sig.confidence_level === 'HIGH' ? '#2563eb' : (sig.confidence_level === 'MEDIUM' ? '#7c3aed' : '#64748b'),
                          }}>
                            {sig.confidence_level === 'HIGH' ? 'High confidence' : (sig.confidence_level === 'MEDIUM' ? 'Medium confidence' : 'Low confidence')}
                          </span>
                          {/* Source Attribution Tag */}
                          {sig.evidence?.source_label && (
                            <span style={{
                              padding: '2px 8px', borderRadius: 12, fontSize: 10.5, fontWeight: 600,
                              background: sig.evidence?.is_bop_authored ? 'rgba(0, 215, 255, 0.12)' : 'rgba(148, 163, 184, 0.15)',
                              color: sig.evidence?.is_bop_authored ? '#0891b2' : '#64748b',
                            }}>
                              {sig.evidence.source_label}
                            </span>
                          )}
                        </div>

                        {relPct && (
                          <div style={{
                            fontSize: 14, fontWeight: 800,
                            color: sig.direction === 'UP' ? '#059669' : (sig.direction === 'DOWN' ? '#ef4444' : 'var(--text-secondary)'),
                          }}>
                            {sig.direction === 'UP' ? '▲ ' : (sig.direction === 'DOWN' ? '▼ ' : '')}{relPct} vs baseline
                          </div>
                        )}
                      </div>

                      {/* Explanation Sentence */}
                      <div style={{ fontSize: 12.5, color: 'var(--text-primary)', lineHeight: 1.45 }}>
                        {sig.explanation}
                      </div>

                      {/* Evidence Accordion Toggle */}
                      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
                        <button
                          onClick={() => setExpandedEvidence(prev => ({ ...prev, [sig.signal_identity]: !prev[sig.signal_identity] }))}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 4,
                            background: 'transparent', border: 'none', cursor: 'pointer',
                            fontSize: 11.5, fontWeight: 700, color: '#00d7ff',
                          }}
                        >
                          <span>{isExpanded ? 'Hide calculation evidence' : 'Why am I seeing this?'}</span>
                          {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>
                      </div>

                      {/* Expanded Evidence Drawer */}
                      {isExpanded && (
                        <div style={{
                          marginTop: 8, padding: '12px 14px', borderRadius: 8,
                          background: 'var(--surface-card)', border: '1px solid var(--border-default)',
                          fontSize: 11.5, color: 'var(--text-secondary)',
                          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10,
                        }}>
                          <div>
                            <strong>Observed Value:</strong> {sig.observed_value != null ? sig.observed_value : 'N/A'}
                          </div>
                          <div>
                            <strong>Baseline (Median):</strong> {sig.baseline_value != null ? sig.baseline_value : 'N/A'}
                          </div>
                          <div>
                            <strong>Sample Size:</strong> n = {sig.sample_size}
                          </div>
                          <div>
                            <strong>Cohort Method:</strong> {sig.evidence?.baseline_method || 'cohort median'}
                          </div>
                          <div>
                            <strong>Comparison Window:</strong> {sig.period_start} to {sig.period_end}
                          </div>
                          <div>
                            <strong>Data Freshness:</strong> {sig.evidence?.freshness || 'FRESH'}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const controlSelectStyle = {
  padding: '6px 10px',
  borderRadius: 8,
  border: '1px solid var(--border-default)',
  background: 'var(--surface-sunken)',
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--text-primary)',
  cursor: 'pointer',
  outline: 'none',
};
