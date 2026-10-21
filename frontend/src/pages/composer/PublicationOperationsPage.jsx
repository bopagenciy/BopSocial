/* ============================================================================
 *  Social Stats — BS-3H Publication Operations & Manual Recovery Console
 * ========================================================================== */
import { useEffect, useState, useMemo } from 'react';
import {
  AlertTriangle, CheckCircle2, Clock, RefreshCw, XCircle, Eye,
  ShieldAlert, Play, Layers, Calendar, Send, HelpCircle, ArrowRight,
  Filter, ChevronRight, X, Info, ExternalLink
} from 'lucide-react';
import toast from 'react-hot-toast';

import PageHeader from '../../components/layout/PageHeader';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import EmptyState from '../../components/ui/EmptyState';
import { composerAPI } from '../../services/api';
import { formatDate } from '../../utils/formatters';

const CLASSIFICATION_CONFIG = {
  PUBLISHED_SUCCESS:      { label: 'Published',       color: 'success', icon: CheckCircle2 },
  QUEUED_FRESH:           { label: 'Queued (Fresh)',   color: 'neutral', icon: Clock },
  QUEUED_RECOVERABLE:     { label: 'Queued (Orphaned)', color: 'warning', icon: AlertTriangle },
  QUEUED_AMBIGUOUS:       { label: 'Queued (Logs)',    color: 'warning', icon: AlertTriangle },
  PUBLISHING_ACTIVE:      { label: 'Publishing',      color: 'info',    icon: RefreshCw },
  PUBLISHING_STALLED:     { label: 'Stalled (>15m)',   color: 'warning', icon: Clock },
  PARTIAL_FAILURE:        { label: 'Partial Failure', color: 'error',   icon: XCircle },
  FAILED_TERMINAL:        { label: 'Failed',          color: 'error',   icon: XCircle },
  PENDING_APPROVAL:       { label: 'Pending Approval', color: 'warning', icon: Clock },
  MANUAL_REVIEW_REQUIRED: { label: 'Needs Review',    color: 'error',   icon: ShieldAlert },
  NORMAL:                 { label: 'Normal',          color: 'neutral', icon: Info },
};

export default function PublicationOperationsPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterTab, setFilterTab] = useState('all'); // all, attention, queued, publishing, failed
  const [platformFilter, setPlatformFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [selectedPost, setSelectedPost] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailData, setDetailData] = useState(null);
  const [recoveringId, setRecoveringId] = useState(null);
  const [activeTab, setActiveTab] = useState('overview'); // overview, timeline

  const fetchOperations = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filterTab === 'attention') params.attention_required = 'true';
      if (filterTab === 'queued') params.status = 'queued';
      if (filterTab === 'publishing') params.status = 'publishing';
      if (filterTab === 'failed') params.status = 'failed';
      if (platformFilter !== 'all') params.platform = platformFilter;
      if (sourceFilter !== 'all') params.source_type = sourceFilter;

      const res = await composerAPI.operations.list(params);
      setItems(res.data?.results || []);
    } catch (err) {
      toast.error('Failed to load publication operations');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOperations();
  }, [filterTab, platformFilter, sourceFilter]);

  const openDetail = async (post) => {
    setSelectedPost(post);
    setDetailLoading(true);
    setDetailData(null);
    try {
      const res = await composerAPI.operations.get(post.id);
      setDetailData(res.data);
    } catch (err) {
      toast.error('Failed to load publication details');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleRecover = async (post) => {
    if (!window.confirm(`Are you sure you want to recover and redispatch Publication #${post.id}? This will safely enqueue it without duplicating platform posts.`)) {
      return;
    }
    setRecoveringId(post.id);
    try {
      const res = await composerAPI.operations.recover(post.id);
      toast.success(res.data?.detail || 'Publication recovered successfully');
      fetchOperations();
      if (selectedPost && selectedPost.id === post.id) {
        openDetail(post);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Recovery failed');
    } finally {
      setRecoveringId(null);
    }
  };

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto' }}>
      <PageHeader
        title="Publication Operations & Orphan Console"
        subtitle="Operational health, orphan visibility, multi-platform status, and controlled safe recovery."
        action={
          <Button icon={RefreshCw} onClick={fetchOperations} loading={loading} variant="secondary">
            Refresh
          </Button>
        }
      />

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, borderBottom: '1px solid var(--border)', paddingBottom: 12 }}>
        {[
          { id: 'all', label: 'All Publications' },
          { id: 'attention', label: '⚠️ Attention Required', alert: true },
          { id: 'queued', label: 'Queued' },
          { id: 'publishing', label: 'In Flight' },
          { id: 'failed', label: 'Failed / Partial' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setFilterTab(tab.id)}
            style={{
              padding: '8px 16px',
              borderRadius: 6,
              border: 'none',
              background: filterTab === tab.id ? 'var(--primary)' : 'transparent',
              color: filterTab === tab.id ? '#fff' : 'var(--text-secondary)',
              fontWeight: 500,
              fontSize: 13,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Filter Row */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-secondary)' }}>
          <Filter size={15} />
          <span>Filters:</span>
        </div>
        <select
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
          style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--surface)', fontSize: 13 }}
        >
          <option value="all">All Platforms</option>
          <option value="facebook">Facebook</option>
          <option value="instagram">Instagram</option>
        </select>

        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--surface)', fontSize: 13 }}
        >
          <option value="all">All Sources</option>
          <option value="POST_QUEUE">Recurring Queue</option>
          <option value="SCHEDULED">Scheduled</option>
          <option value="DIRECT">Direct / Composer</option>
        </select>
      </div>

      {/* Publications Table */}
      <Card style={{ overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-tertiary)' }}>
            <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 12px' }} />
            <div>Loading publication operations...</div>
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={CheckCircle2}
            title="No publications matching filter"
            description="All monitored publication pipelines are operating normally."
          />
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: 'var(--surface-hover)', borderBottom: '1px solid var(--border)', textAlign: 'left', color: 'var(--text-secondary)' }}>
                <th style={{ padding: '12px 16px' }}>Post ID</th>
                <th style={{ padding: '12px 16px' }}>Client</th>
                <th style={{ padding: '12px 16px' }}>Content</th>
                <th style={{ padding: '12px 16px' }}>Source</th>
                <th style={{ padding: '12px 16px' }}>Platforms & Outcome</th>
                <th style={{ padding: '12px 16px' }}>Operational Status</th>
                <th style={{ padding: '12px 16px' }}>Effective Age</th>
                <th style={{ padding: '12px 16px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((post) => {
                const classConf = CLASSIFICATION_CONFIG[post.classification?.classification] || CLASSIFICATION_CONFIG.NORMAL;
                const Icon = classConf.icon;
                return (
                  <tr
                    key={post.id}
                    style={{
                      borderBottom: '1px solid var(--border)',
                      background: post.classification?.attention_required ? 'rgba(239, 68, 68, 0.03)' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '12px 16px', fontWeight: 600 }}>#{post.id}</td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ fontWeight: 500 }}>{post.client?.company || post.client?.name}</div>
                    </td>
                    <td style={{ padding: '12px 16px', maxWidth: 260 }}>
                      <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {post.content_preview || <em>(No content)</em>}
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12 }}>
                        {post.source?.type === 'POST_QUEUE' && <Layers size={13} style={{ color: 'var(--primary)' }} />}
                        {post.source?.type === 'SCHEDULED' && <Calendar size={13} style={{ color: 'var(--text-secondary)' }} />}
                        {post.source?.type === 'DIRECT' && <Send size={13} style={{ color: 'var(--text-secondary)' }} />}
                        <span>{post.source?.description || post.source?.type}</span>
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {(post.platform_progress || []).map((p) => {
                          let badgeColor = 'neutral';
                          if (p.status === 'success') badgeColor = 'success';
                          else if (p.status === 'failed') badgeColor = 'error';
                          else if (p.status === 'publishing') badgeColor = 'warning';
                          return (
                            <span
                              key={p.platform}
                              style={{
                                fontSize: 11,
                                padding: '2px 8px',
                                borderRadius: 4,
                                border: '1px solid var(--border)',
                                background: p.status === 'success' ? '#ecfdf5' : p.status === 'failed' ? '#fef2f2' : 'var(--surface)',
                                color: p.status === 'success' ? '#047857' : p.status === 'failed' ? '#b91c1c' : 'var(--text-secondary)',
                                fontWeight: 500,
                              }}
                            >
                              {p.platform}: {p.status}
                            </span>
                          );
                        })}
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 5,
                            padding: '3px 8px',
                            borderRadius: 4,
                            fontSize: 12,
                            fontWeight: 500,
                            background: post.classification?.severity === 'CRITICAL' ? '#fee2e2' : post.classification?.severity === 'WARNING' ? '#fef3c7' : post.classification?.severity === 'ERROR' ? '#fee2e2' : '#f3f4f6',
                            color: post.classification?.severity === 'CRITICAL' ? '#991b1b' : post.classification?.severity === 'WARNING' ? '#92400e' : post.classification?.severity === 'ERROR' ? '#991b1b' : '#374151',
                          }}
                        >
                          <Icon size={12} />
                          {classConf.label}
                        </span>
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontSize: 12 }}>
                      {post.effective_age_seconds ? `${Math.round(post.effective_age_seconds / 60)}m` : '0m'}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', alignItems: 'center' }}>
                        {post.classification?.can_recover && (
                          <Button
                            size="sm"
                            variant="primary"
                            icon={Play}
                            loading={recoveringId === post.id}
                            onClick={() => handleRecover(post)}
                          >
                            Recover
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="secondary"
                          icon={Eye}
                          onClick={() => openDetail(post)}
                        >
                          Review
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

      {/* Review & Diagnosis Drawer */}
      {selectedPost && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex',
            justifyContent: 'flex-end',
            zIndex: 1000,
          }}
          onClick={() => setSelectedPost(null)}
        >
          <div
            style={{
              width: 580,
              background: 'var(--surface)',
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '-4px 0 24px rgba(0,0,0,0.15)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drawer Header */}
            <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 18 }}>Publication #{selectedPost.id}</h3>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                  Client: {selectedPost.client?.company || selectedPost.client?.name}
                </div>
              </div>
              <button
                onClick={() => setSelectedPost(null)}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-secondary)' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Drawer Tabs */}
            <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', padding: '0 24px' }}>
              <button
                onClick={() => setActiveTab('overview')}
                style={{
                  padding: '12px 16px',
                  border: 'none',
                  background: 'transparent',
                  borderBottom: activeTab === 'overview' ? '2px solid var(--primary)' : '2px solid transparent',
                  color: activeTab === 'overview' ? 'var(--primary)' : 'var(--text-secondary)',
                  fontWeight: 600,
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                Overview & Diagnosis
              </button>
              <button
                onClick={() => setActiveTab('timeline')}
                style={{
                  padding: '12px 16px',
                  border: 'none',
                  background: 'transparent',
                  borderBottom: activeTab === 'timeline' ? '2px solid var(--primary)' : '2px solid transparent',
                  color: activeTab === 'timeline' ? 'var(--primary)' : 'var(--text-secondary)',
                  fontWeight: 600,
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                Operational Timeline
              </button>
            </div>

            {/* Drawer Body */}
            <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
              {detailLoading ? (
                <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-secondary)' }}>
                  <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 12px' }} />
                  <div>Loading publication diagnosis...</div>
                </div>
              ) : !detailData ? (
                <div>Failed to load diagnosis.</div>
              ) : activeTab === 'overview' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                  {/* Operator Guidance Banner */}
                  <div
                    style={{
                      padding: 16,
                      borderRadius: 8,
                      background: detailData.classification?.severity === 'CRITICAL' ? '#fee2e2' : detailData.classification?.severity === 'WARNING' ? '#fef3c7' : '#eff6ff',
                      border: '1px solid ' + (detailData.classification?.severity === 'CRITICAL' ? '#fca5a5' : detailData.classification?.severity === 'WARNING' ? '#fcd34d' : '#bfdbfe'),
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, color: '#1f2937' }}>
                      <Info size={15} />
                      Operator Guidance
                    </div>
                    <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.5 }}>
                      {detailData.operator_guidance}
                    </div>
                  </div>

                  {/* Classification Card */}
                  <Card style={{ padding: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 8 }}>
                      Operational Diagnosis
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <span style={{ fontWeight: 600, fontSize: 15 }}>{detailData.classification?.classification}</span>
                      <Badge color={detailData.classification?.can_recover ? 'warning' : 'neutral'}>
                        {detailData.classification?.can_recover ? 'Eligible for Safe Recovery' : 'Manual Review Required'}
                      </Badge>
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                      {detailData.classification?.attention_reason}
                    </div>
                  </Card>

                  {/* Provenance & Approval */}
                  <Card style={{ padding: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 12 }}>
                      Provenance & Governance
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 13 }}>
                      <div>
                        <div style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Source Type</div>
                        <div style={{ fontWeight: 500, marginTop: 2 }}>{detailData.source?.type}</div>
                      </div>
                      <div>
                        <div style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Queue / Cron Details</div>
                        <div style={{ fontWeight: 500, marginTop: 2 }}>{detailData.source?.queue_name || 'N/A'}</div>
                      </div>
                      <div>
                        <div style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Requires Approval</div>
                        <div style={{ fontWeight: 500, marginTop: 2 }}>{detailData.approval?.requires_approval ? 'Yes' : 'No'}</div>
                      </div>
                      <div>
                        <div style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Approval Status</div>
                        <div style={{ fontWeight: 500, marginTop: 2 }}>
                          {detailData.approval?.is_approved ? `Approved by ${detailData.approval.approved_by}` : 'Pending / None'}
                        </div>
                      </div>
                    </div>
                  </Card>

                  {/* Platform Progress Breakdown */}
                  <Card style={{ padding: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 12 }}>
                      Platform Target Breakdown
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {(detailData.platform_progress || []).map((p) => (
                        <div key={p.platform} style={{ padding: 12, borderRadius: 6, border: '1px solid var(--border)', background: 'var(--surface-hover)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{p.platform}</span>
                            <span style={{ fontSize: 12, fontWeight: 600, color: p.status === 'success' ? '#059669' : p.status === 'failed' ? '#dc2626' : 'var(--text-secondary)' }}>
                              {p.status}
                            </span>
                          </div>
                          {p.platform_post_id && (
                            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                              Provider ID: <code>{p.platform_post_id}</code>
                            </div>
                          )}
                          {p.error_message && (
                            <div style={{ fontSize: 12, color: '#dc2626', marginTop: 4 }}>
                              Error: {p.error_message}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </Card>
                </div>
              ) : (
                /* Timeline Tab */
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {(detailData.timeline || []).map((event, idx) => (
                    <div key={idx} style={{ display: 'flex', gap: 12 }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <div
                          style={{
                            width: 10,
                            height: 10,
                            borderRadius: '50%',
                            background: event.severity === 'success' ? '#10b981' : event.severity === 'error' ? '#ef4444' : event.severity === 'warning' ? '#f59e0b' : '#6b7280',
                            marginTop: 5,
                          }}
                        />
                        {idx < detailData.timeline.length - 1 && (
                          <div style={{ width: 2, flex: 1, background: 'var(--border)', margin: '4px 0' }} />
                        )}
                      </div>
                      <div style={{ flex: 1, paddingBottom: 16 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                          <span style={{ fontWeight: 600, fontSize: 13 }}>{event.event_type}</span>
                          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                            {formatDate(event.timestamp, { dateStyle: 'short', timeStyle: 'medium' })}
                          </span>
                        </div>
                        <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
                          {event.description}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Drawer Footer */}
            <div style={{ padding: '16px 24px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Button variant="secondary" onClick={() => setSelectedPost(null)}>
                Close
              </Button>
              {detailData?.classification?.can_recover && (
                <Button
                  variant="primary"
                  icon={Play}
                  loading={recoveringId === detailData.id}
                  onClick={() => handleRecover(detailData)}
                >
                  Recover Publication
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
