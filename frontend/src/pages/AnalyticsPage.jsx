/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  AreaChart, Area, RadarChart, Radar, PolarGrid, PolarAngleAxis,
} from 'recharts';
import { overviewAPI, clientsAPI } from '../services/api';
import { useClients, useDateRange } from '../hooks/useData';
import { TrendingUp, TrendingDown, Minus, RefreshCw, Users, Eye, MousePointer, Play, UserPlus } from 'lucide-react';
import DateRangePicker from '../components/ui/DateRangePicker';
import SocialPlatformIcon from '../components/ui/SocialPlatformIcon';
import PageHeader from '../components/layout/PageHeader';
import { formatDateRange, formatDate } from '../utils/formatters';

// ── Constants ─────────────────────────────────────────────────────────────────
const PLATFORM_META = {
  facebook:           { label: 'Facebook',           color: '#1877F2', lightBg: '#EBF5FF' },
  instagram:          { label: 'Instagram',          color: '#E1306C', lightBg: '#FFF0F5' },
  youtube:            { label: 'YouTube',            color: '#FF0000', lightBg: '#FFF5F5' },
  linkedin:           { label: 'LinkedIn',           color: '#0A66C2', lightBg: '#EEF4FF' },
  google_my_business: { label: 'Google My Business', color: '#34A853', lightBg: '#F0FFF4' },
};

const BASE_METRIC_CONFIG = {
  impressions:  { key: 'impressions',  icon: Eye,          color: '#00d7ff' },
  reach:        { key: 'reach',        icon: Users,        color: '#00d7ff' },
  clicks:       { key: 'clicks',       icon: MousePointer, color: '#0891b2' },
  video_views:  { key: 'video_views',  icon: Play,         color: '#00d7ff' },
  followers:    { key: 'followers',    icon: UserPlus,     color: '#059669' },
};

function fmt(n) {
  if (!n && n !== 0) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
  return Number(n).toLocaleString();
}

function pctChange(curr, prev) {
  if (!prev || prev === 0) return null;
  return ((curr - prev) / prev) * 100;
}

// ── Sub-components ────────────────────────────────────────────────────────────
function KPICard({ label, value, prev, icon: Icon, color, loading, vsText }) {
  const change = prev != null ? pctChange(value, prev) : null;
  return (
    <div style={{
      background: 'var(--surface-card)', borderRadius: 14, padding: '20px 22px',
      border: '1px solid var(--border-default)', flex: 1, minWidth: 160,
      boxShadow: '0 1px 6px rgba(0,0,0,0.04)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          background: color + '18',
        }}>
          <Icon size={16} color={color} />
        </div>
        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          {label}
        </span>
      </div>
      {loading ? (
        <div style={{ height: 32, background: 'var(--surface-page)', borderRadius: 6, animation: 'pulse 1.5s infinite' }} />
      ) : (
        <>
          <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1.1 }}>
            {fmt(value || 0)}
          </div>
          {change != null && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 6, fontSize: 12, fontWeight: 700,
              color: change > 0 ? '#059669' : change < 0 ? '#dc2626' : 'var(--text-secondary)' }}>
              {change > 0 ? <TrendingUp size={12} /> : change < 0 ? <TrendingDown size={12} /> : <Minus size={12} />}
              {change > 0 ? '+' : ''}{change.toFixed(1)}% {vsText || 'vs prev period'}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function SectionCard({ title, subtitle, children, style }) {
  return (
    <div style={{
      background: 'var(--surface-card)', borderRadius: 16, border: '1px solid var(--border-default)',
      boxShadow: '0 1px 8px rgba(0,0,0,0.04)', padding: '22px 26px',
      ...style,
    }}>
      {(title || subtitle) && (
        <div style={{ marginBottom: 18 }}>
          {title && <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--text-primary)' }}>{title}</div>}
          {subtitle && <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 3 }}>{subtitle}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--surface-card)', border: '1px solid var(--border-default)', borderRadius: 10,
      padding: '10px 14px', boxShadow: '0 4px 16px rgba(0,0,0,0.1)', fontSize: 12,
    }}>
      <div style={{ fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, color: p.color, marginBottom: 2 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: p.color }} />
          <span style={{ color: 'var(--text-secondary)' }}>{p.name}:</span>
          <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{fmt(p.value)}</span>
        </div>
      ))}
    </div>
  );
};

// ── Main Component ────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
  const { t, i18n } = useTranslation('analytics');
  const { clients } = useClients();
  const [selectedClientId, setSelectedClientId] = useState('all');
  const [selectedPlatform, setSelectedPlatform] = useState('all');
  const [range, setRange]               = useDateRange(30);
  const [activeMetric, setActiveMetric] = useState('impressions');

  const METRIC_META = useMemo(() => ({
    impressions:  { label: t('metrics.impressions'),  icon: BASE_METRIC_CONFIG.impressions.icon,  color: BASE_METRIC_CONFIG.impressions.color },
    reach:        { label: t('metrics.reach'),        icon: BASE_METRIC_CONFIG.reach.icon,        color: BASE_METRIC_CONFIG.reach.color },
    clicks:       { label: t('metrics.clicks'),       icon: BASE_METRIC_CONFIG.clicks.icon,       color: BASE_METRIC_CONFIG.clicks.color },
    video_views:  { label: t('metrics.video_views'),  icon: BASE_METRIC_CONFIG.video_views.icon,  color: BASE_METRIC_CONFIG.video_views.color },
    followers:    { label: t('metrics.followers'),    icon: BASE_METRIC_CONFIG.followers.icon,    color: BASE_METRIC_CONFIG.followers.color },
  }), [t]);

  // Overview data (all clients, all platforms, date range)
  const [overview, setOverview]           = useState(null);
  const [overviewLoading, setOverviewLoading] = useState(true);

  // Per-client data
  const [summary, setSummary]           = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [timeseries, setTimeseries]     = useState([]);
  const [timeseriesLoading, setTimeseriesLoading] = useState(false);
  const [prevSummary, setPrevSummary]   = useState(null);

  // Compute previous period of same duration for comparison
  const daysDiff = Math.max(1, Math.round(
    (new Date(range.until) - new Date(range.since)) / 86400000
  ));
  const prevRange = {
    since: new Date(new Date(range.since) - daysDiff * 86400000).toISOString().slice(0, 10),
    until: range.since,
  };

  // ── Fetch overview ──────────────────────────────────────────────────────────
  const fetchOverview = useCallback(() => {
    setOverviewLoading(true);
    overviewAPI.get(range)
      .then(res => setOverview(res.data))
      .catch(() => setOverview(null))
      .finally(() => setOverviewLoading(false));
  }, [range.since, range.until]);

  useEffect(() => { fetchOverview(); }, [fetchOverview]);

  // ── Fetch per-client summary + timeseries ───────────────────────────────────
  useEffect(() => {
    if (!selectedClientId || selectedClientId === 'all') {
      setSummary(null);
      setTimeseries([]);
      return;
    }
    const id = selectedClientId;
    const platform = selectedPlatform !== 'all' ? selectedPlatform : undefined;

    // Current period
    setSummaryLoading(true);
    clientsAPI.summary(id, { ...range, ...(platform ? { platform } : {}) })
      .then(res => setSummary(res.data))
      .catch(() => setSummary(null))
      .finally(() => setSummaryLoading(false));

    // Previous period for comparison
    clientsAPI.summary(id, {
      since: prevRange.since, until: prevRange.until,
      ...(platform ? { platform } : {}),
    })
      .then(res => setPrevSummary(res.data))
      .catch(() => setPrevSummary(null));

    // Timeseries
    setTimeseriesLoading(true);
    clientsAPI.timeseries(id, { ...range, ...(platform ? { platform } : {}) })
      .then(res => setTimeseries(res.data?.results || res.data || []))
      .catch(() => setTimeseries([]))
      .finally(() => setTimeseriesLoading(false));
  }, [selectedClientId, selectedPlatform, range.since, range.until]);

  // ── Derived data ────────────────────────────────────────────────────────────
  const platformData = (overview?.by_platform || []).map(p => ({
    ...p,
    label: PLATFORM_META[p.platform]?.label || p.platform,
    color: PLATFORM_META[p.platform]?.color || '#00d7ff',
  }));

  // Aggregate totals from overview platform data
  const totals = platformData.reduce((acc, p) => {
    acc.impressions  = (acc.impressions  || 0) + (p.impressions  || 0);
    acc.reach        = (acc.reach        || 0) + (p.reach        || 0);
    acc.clicks       = (acc.clicks       || 0) + (p.clicks       || 0);
    acc.video_views  = (acc.video_views  || 0) + (p.video_views  || 0);
    acc.followers    = (acc.followers    || 0) + (p.followers    || 0);
    return acc;
  }, {});

  // Use per-client summary when one is selected
  const kpiSource = summary || totals;

  // Format timeseries for recharts
  const chartData = timeseries.map(d => ({
    date:        d.date ? d.date.slice(5) : d.date,
    impressions: d.impressions || 0,
    reach:       d.reach       || 0,
    clicks:      d.clicks      || 0,
    video_views: d.video_views || 0,
    likes:       d.likes       || 0,
    followers:   d.followers   || 0,
  }));

  // Pie chart data from platforms
  const pieData = platformData
    .filter(p => (p[activeMetric] || 0) > 0)
    .map(p => ({ name: p.label, value: p[activeMetric] || 0, color: p.color }));

  // Platform radar data
  const radarData = Object.keys(METRIC_META).map(metric => {
    const entry = { metric: METRIC_META[metric].label };
    platformData.forEach(p => {
      entry[p.label] = p[metric] || 0;
    });
    return entry;
  });

  // Top clients table (per platform, sorted by impressions)
  const topClients = clients.slice(0, 10).map(c => ({ ...c }));

  const isClientSelected = selectedClientId && selectedClientId !== 'all';
  const selectedClientName = clients.find(c => String(c.id) === String(selectedClientId))?.company;

  const formattedRange = useMemo(() => {
    return formatDateRange(range.since, range.until, { dateStyle: 'medium' }, i18n?.language);
  }, [range.since, range.until, i18n?.language]);

  return (
    <div style={{ padding: '32px 36px', background: 'var(--surface-page)', minHeight: '100vh' }}>
      <PageHeader
        title={t('title')}
        subtitle={isClientSelected
          ? t('subtitle_client', { client: selectedClientName, dateRange: formattedRange })
          : t('subtitle_all', { dateRange: formattedRange })}
        actions={(
          <div className="analytics-controls" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <DateRangePicker range={range} onChange={setRange} />
            <select
              value={selectedClientId}
              onChange={e => setSelectedClientId(e.target.value)}
              style={selectStyle}
            >
              <option value="all">{t('all_users')}</option>
              {clients.map(c => <option key={c.id} value={c.id}>{c.company}</option>)}
            </select>
            {isClientSelected && (
              <select
                value={selectedPlatform}
                onChange={e => setSelectedPlatform(e.target.value)}
                style={selectStyle}
              >
                <option value="all">{t('all_platforms')}</option>
                {Object.entries(PLATFORM_META).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            )}
            <button
              onClick={fetchOverview}
              style={{ ...btnSecondary, padding: '8px 12px' }}
              title={t('refresh')}
            >
              <RefreshCw size={14} />
            </button>
          </div>
        )}
      />

      {/* ── KPI Cards ──────────────────────────────────────────────────────── */}
      <div className="analytics-kpi-grid" style={{ display: 'flex', gap: 14, marginBottom: 24, flexWrap: 'wrap' }}>
        {Object.entries(METRIC_META).map(([key, meta]) => (
          <KPICard
            key={key}
            label={meta.label}
            value={kpiSource?.[key]}
            prev={prevSummary?.[key]}
            icon={meta.icon}
            color={meta.color}
            loading={isClientSelected ? summaryLoading : overviewLoading}
            vsText={t('vs_prev_period')}
          />
        ))}
      </div>

      {/* ── Row 1: Timeseries (client) or Platform Bars (all) ─────────────── */}
      {isClientSelected ? (
        <SectionCard
          title={t('sections.performance_over_time', { client: selectedClientName })}
          subtitle={t('sections.performance_over_time_sub')}
          style={{ marginBottom: 24 }}
        >
          {/* Metric selector */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 18, flexWrap: 'wrap' }}>
            {Object.entries(METRIC_META).map(([key, meta]) => (
              <button
                key={key}
                onClick={() => setActiveMetric(key)}
                style={{
                  padding: '5px 14px', borderRadius: 20, border: '1.5px solid',
                  cursor: 'pointer', fontSize: 12, fontWeight: 700, transition: 'all 0.15s',
                  background:  activeMetric === key ? meta.color : 'var(--surface-sunken)',
                  borderColor: activeMetric === key ? meta.color : 'var(--border-default)',
                  color:       activeMetric === key ? '#fff' : 'var(--text-secondary)',
                }}
              >
                {meta.label}
              </button>
            ))}
          </div>

          {timeseriesLoading ? (
            <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)' }}>
              {t('loading_chart')}
            </div>
          ) : chartData.length === 0 ? (
            <EmptyChart message={t('empty.no_data_period')} />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <defs>
                  <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={METRIC_META[activeMetric].color} stopOpacity={0.18} />
                    <stop offset="95%" stopColor={METRIC_META[activeMetric].color} stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-sunken)" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} />
                <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} width={52} />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone"
                  dataKey={activeMetric}
                  name={METRIC_META[activeMetric].label}
                  stroke={METRIC_META[activeMetric].color}
                  strokeWidth={2.5}
                  fill="url(#areaGrad)"
                  dot={false}
                  activeDot={{ r: 5, strokeWidth: 0 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </SectionCard>
      ) : (
        <SectionCard
          title={t('sections.performance_by_platform')}
          subtitle={t('sections.performance_by_platform_sub', { dateRange: formattedRange })}
          style={{ marginBottom: 24 }}
        >
          {overviewLoading ? (
            <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)' }}>
              {t('loading_chart')}
            </div>
          ) : platformData.length === 0 ? (
            <EmptyChart message={t('empty.no_data_sync_users')} />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={platformData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-sunken)" />
                <XAxis dataKey="label" tick={{ fontSize: 12, fill: 'var(--text-tertiary)' }} />
                <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} width={52} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="impressions" name={t('metrics.impressions')} radius={[4,4,0,0]}>
                  {platformData.map((p, i) => <Cell key={i} fill={p.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </SectionCard>
      )}

      {/* ── Row 2: Two-column ─────────────────────────────────────────────── */}
      <div className="analytics-two-col" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>

        {/* Platform distribution pie */}
        <SectionCard
          title={t('sections.platform_distribution')}
          subtitle={t('sections.platform_distribution_sub', { metric: METRIC_META[activeMetric]?.label || t('metrics.impressions') })}
        >
          {/* Metric pills */}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
            {Object.entries(METRIC_META).map(([key, meta]) => (
              <button
                key={key}
                onClick={() => setActiveMetric(key)}
                style={{
                  padding: '3px 10px', borderRadius: 20, border: '1px solid',
                  cursor: 'pointer', fontSize: 11, fontWeight: 700,
                  background:  activeMetric === key ? meta.color : 'var(--surface-sunken)',
                  borderColor: activeMetric === key ? meta.color : 'var(--border-default)',
                  color:       activeMetric === key ? '#fff' : 'var(--text-tertiary)',
                }}
              >
                {meta.label}
              </button>
            ))}
          </div>

          {overviewLoading || pieData.length === 0 ? (
            <EmptyChart height={200} message={overviewLoading ? t('loading') : t('empty.no_platform_data')} />
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => fmt(v)} />
                <Legend
                  iconType="circle"
                  iconSize={9}
                  wrapperStyle={{ fontSize: 12 }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </SectionCard>

        {/* Multi-metric bar comparison */}
        <SectionCard
          title={t('sections.platform_metrics_comparison')}
          subtitle={t('sections.platform_metrics_comparison_sub')}
        >
          {overviewLoading || platformData.length === 0 ? (
            <EmptyChart height={240} message={overviewLoading ? t('loading') : t('empty.no_data_yet')} />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={platformData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }} barGap={2}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-sunken)" />
                <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} />
                <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 10, fill: 'var(--text-tertiary)' }} width={48} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="reach"       name={t('metrics.reach')}       fill="#00d7ff" radius={[3,3,0,0]} />
                <Bar dataKey="clicks"      name={t('metrics.clicks')}      fill="#0891b2" radius={[3,3,0,0]} />
                <Bar dataKey="video_views" name={t('metrics.video_views')} fill="#00d7ff" radius={[3,3,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </SectionCard>
      </div>

      {/* ── Row 3: Multi-metric timeseries (client) or Radar (all) ────────── */}
      {isClientSelected ? (
        <SectionCard
          title={t('sections.all_metrics_over_time')}
          subtitle={t('sections.all_metrics_over_time_sub')}
          style={{ marginBottom: 24 }}
        >
          {timeseriesLoading || chartData.length === 0 ? (
            <EmptyChart height={260} message={timeseriesLoading ? t('loading') : t('empty.no_timeseries_data')} />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-sunken)" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} />
                <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} width={52} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="impressions"  name={t('metrics.impressions')}  stroke="#00d7ff" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="reach"        name={t('metrics.reach')}        stroke="#00d7ff" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="clicks"       name={t('metrics.clicks')}       stroke="#0891b2" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="video_views"  name={t('metrics.video_views')}  stroke="#00d7ff" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </SectionCard>
      ) : (
        <SectionCard
          title={t('sections.platform_balance_radar')}
          subtitle={t('sections.platform_balance_radar_sub')}
          style={{ marginBottom: 24 }}
        >
          {overviewLoading || platformData.length === 0 ? (
            <EmptyChart height={260} message={overviewLoading ? t('loading') : t('empty.no_data_yet')} />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <RadarChart cx="50%" cy="50%" outerRadius={90} data={radarData}>
                <PolarGrid stroke="var(--border-default)" />
                <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} />
                <Tooltip formatter={(v) => fmt(v)} />
                {platformData.map((p, i) => (
                  <Radar
                    key={p.platform}
                    name={p.label}
                    dataKey={p.label}
                    stroke={p.color}
                    fill={p.color}
                    fillOpacity={0.1}
                    strokeWidth={2}
                  />
                ))}
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </RadarChart>
            </ResponsiveContainer>
          )}
        </SectionCard>
      )}

      {/* ── Row 4: Platform breakdown table ───────────────────────────────── */}
      <SectionCard
        title={t('sections.platform_breakdown')}
        subtitle={t('sections.platform_breakdown_sub')}
        style={{ marginBottom: 24 }}
      >
        {overviewLoading ? (
          <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-tertiary)' }}>{t('loading')}</div>
        ) : platformData.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-tertiary)' }}>
            {t('empty.no_platform_data_table')}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: 'var(--surface-page)' }}>
                  {[
                    t('table.platform'),
                    t('table.impressions'),
                    t('table.reach'),
                    t('table.clicks'),
                    t('table.video_views'),
                    t('table.followers'),
                    t('table.ctr')
                  ].map(h => (
                    <th key={h} style={{
                      padding: '10px 16px', textAlign: 'left', fontWeight: 700,
                      color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-default)', whiteSpace: 'nowrap',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {platformData.map((p, i) => {
                  const ctr = p.impressions > 0 ? ((p.clicks / p.impressions) * 100).toFixed(2) : '0.00';
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid var(--surface-sunken)' }}>
                      <td style={{ padding: '13px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div style={{
                            width: 32, height: 32, borderRadius: 8, display: 'flex',
                            alignItems: 'center', justifyContent: 'center',
                            background: PLATFORM_META[p.platform]?.lightBg || '#e6fbff',
                          }}>
                            <SocialPlatformIcon platform={p.platform} size={16} />
                          </div>
                          <div>
                            <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{p.label}</div>
                          </div>
                        </div>
                      </td>
                      <td style={{ padding: '13px 16px', fontWeight: 700, color: '#00d7ff' }}>{fmt(p.impressions)}</td>
                      <td style={{ padding: '13px 16px', color: '#00d7ff', fontWeight: 600 }}>{fmt(p.reach)}</td>
                      <td style={{ padding: '13px 16px' }}>{fmt(p.clicks)}</td>
                      <td style={{ padding: '13px 16px' }}>{fmt(p.video_views)}</td>
                      <td style={{ padding: '13px 16px' }}>{fmt(p.followers)}</td>
                      <td style={{ padding: '13px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{
                            height: 6, width: 80, background: 'var(--border-default)', borderRadius: 3, overflow: 'hidden',
                          }}>
                            <div style={{
                              height: '100%', borderRadius: 3,
                              width: `${Math.min(parseFloat(ctr) * 20, 100)}%`,
                              background: p.color,
                            }} />
                          </div>
                          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>{ctr}%</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      {/* ── Row 5: Users overview table (only when "All Users") ───────── */}
      {!isClientSelected && (
        <SectionCard
          title={t('sections.user_overview')}
          subtitle={t('sections.user_overview_sub')}
        >
          {clients.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-tertiary)' }}>
              {t('empty.no_clients')}
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: 'var(--surface-page)' }}>
                    {[
                      t('table.client'),
                      t('table.status'),
                      t('table.created'),
                      t('table.website'),
                      ''
                    ].map(h => (
                      <th key={h} style={{
                        padding: '10px 16px', textAlign: 'left', fontWeight: 700,
                        color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-default)',
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {clients.map((c, i) => (
                    <tr key={c.id} style={{ borderBottom: '1px solid var(--surface-sunken)' }}>
                      <td style={{ padding: '13px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div style={{
                            width: 34, height: 34, borderRadius: 10, background: '#e6fbff',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 13, fontWeight: 800, color: '#00d7ff',
                          }}>
                            {(c.company || 'C')[0].toUpperCase()}
                          </div>
                          <div>
                            <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{c.company}</div>
                            <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{c.email}</div>
                          </div>
                        </div>
                      </td>
                      <td style={{ padding: '13px 16px' }}>
                        <span style={{
                          display: 'inline-flex', padding: '3px 10px', borderRadius: 20,
                          fontSize: 11, fontWeight: 700,
                          background: c.is_active ? '#d1fae5' : '#fee2e2',
                          color:      c.is_active ? '#059669' : '#dc2626',
                        }}>
                          {c.is_active ? t('table.active') : t('table.inactive')}
                        </span>
                      </td>
                      <td style={{ padding: '13px 16px', color: 'var(--text-secondary)' }}>
                        {c.created_at ? formatDate(c.created_at, { dateStyle: 'medium' }, i18n?.language) : '—'}
                      </td>
                      <td style={{ padding: '13px 16px' }}>
                        {c.website ? (
                          <a href={c.website} target="_blank" rel="noreferrer"
                            style={{ color: '#00d7ff', fontSize: 12, textDecoration: 'none' }}>
                            {c.website.replace(/^https?:\/\//, '')}
                          </a>
                        ) : <span style={{ color: 'var(--text-quaternary)' }}>—</span>}
                      </td>
                      <td style={{ padding: '13px 16px' }}>
                        <button
                          onClick={() => setSelectedClientId(String(c.id))}
                          style={{
                            padding: '5px 14px', borderRadius: 8, border: '1.5px solid #00d7ff',
                            background: 'var(--surface-card)', color: '#00d7ff', fontSize: 12, fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          {t('table.view_analytics')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      )}
    </div>
  );
}

function EmptyChart({ height = 200, message }) {
  return (
    <div style={{
      height, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      color: 'var(--text-tertiary)', fontSize: 13, gap: 8,
    }}>
      <div style={{ fontSize: 32 }}>📊</div>
      <div>{message}</div>
    </div>
  );
}

const selectStyle = {
  padding: '8px 12px', borderRadius: 10, border: '1.5px solid var(--border-default)',
  background: 'var(--surface-card)', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)',
  cursor: 'pointer', outline: 'none',
};

const btnSecondary = {
  display: 'flex', alignItems: 'center', gap: 6,
  borderRadius: 10, border: '1.5px solid var(--border-default)',
  background: 'var(--surface-card)', color: 'var(--text-secondary)', fontSize: 13, fontWeight: 700,
  cursor: 'pointer',
};
