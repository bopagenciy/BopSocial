/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useEffect, useState } from 'react';
import {
  Plus, Layers, Pause, Play, Trash2, Clock, Edit2, X, GripVertical,
  CheckCircle2, AlertCircle, ArrowUp, ArrowDown, Image as ImageIcon,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import toast from 'react-hot-toast';

import PageHeader from '../../components/layout/PageHeader';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import Badge from '../../components/ui/Badge';
import { usePostQueues } from '../../hooks/useComposer';
import { composerAPI } from '../../services/api';
import { formatDate } from '../../utils/formatters';

const STRATEGIES = [
  { id: 'sequential',  label: 'Sequential' },
  { id: 'random',      label: 'Random' },
  { id: 'round_robin', label: 'Round-robin' },
];

export default function QueueManagerPage() {
  const { t } = useTranslation('content');
  const { data: queues, refetch, loading } = usePostQueues();
  const [activeId, setActiveId] = useState(null);
  const [showCreate, setShowCreate] = useState(false);

  // Auto-select first queue once available
  useEffect(() => {
    if (!activeId && queues.length > 0) setActiveId(queues[0].id);
  }, [queues, activeId]);

  return (
    <div style={{ paddingBottom: 32 }}>
      <PageHeader
        title={t('queues.title')}
        subtitle={t('queues.subtitle')}
        action={<Button icon={Plus} onClick={() => setShowCreate(true)}>{t('queues.new_queue')}</Button>}
      />

      <div style={{
        display: 'grid', gridTemplateColumns: '320px minmax(0, 1fr)',
        gap: 16, padding: '0 24px',
      }} className="queue-grid">
        {/* Left: queue list */}
        <Card padding="none" style={{ overflow: 'hidden' }}>
          {loading && <div style={{ padding: 16, color: 'var(--text-tertiary)' }}>{t('queues.loading')}</div>}
          {!loading && queues.length === 0 && (
            <EmptyState
              icon={Layers}
              title={t('queues.empty_title')}
              description={t('queues.empty_desc')}
              action={<Button icon={Plus} onClick={() => setShowCreate(true)}>{t('queues.create_queue')}</Button>}
            />
          )}
          {queues.map((q) => (
            <QueueRow key={q.id} queue={q} active={activeId === q.id}
                      onClick={() => setActiveId(q.id)} onChange={refetch} />
          ))}
        </Card>

        {/* Right: queue items */}
        <Card padding="none" style={{ overflow: 'hidden' }}>
          {activeId
            ? <QueueDetail queueId={activeId} onChanged={refetch} />
            : <EmptyState icon={Layers} title={t('queues.select_queue')} />}
        </Card>
      </div>

      {showCreate && (
        <CreateQueueModal
          onClose={() => setShowCreate(false)}
          onCreated={(q) => { setShowCreate(false); refetch(); setActiveId(q.id); }}
        />
      )}

      <style>{`
        @media (max-width: 900px) {
          .queue-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}

/* ── Queue list row ───────────────────────────────────────────────────── */
function QueueRow({ queue, active, onClick, onChange }) {
  const { t } = useTranslation('content');
  async function toggle() {
    try {
      if (queue.is_active) await composerAPI.queues.pause(queue.id);
      else                  await composerAPI.queues.resume(queue.id);
      onChange();
    } catch { toast.error(t('queues.failed')); }
  }
  async function destroy(e) {
    e.stopPropagation();
    if (!window.confirm(t('queues.delete_confirm', { name: queue.name }))) return;
    try { await composerAPI.queues.delete(queue.id); onChange(); }
    catch { toast.error(t('queues.delete_failed')); }
  }

  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: 'block', width: '100%', textAlign: 'left',
        padding: '12px 14px',
        background: active ? 'var(--brand-primary-glow)' : 'transparent',
        border: 'none', borderBottom: '1px solid var(--border-subtle)',
        cursor: 'pointer', minHeight: 'unset', minWidth: 'unset',
        transition: 'var(--transition-fast)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
            {queue.name}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
            {queue.schedule_rule || t('queues.no_rule')}
          </div>
          <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
            <Badge variant={queue.is_active ? 'success' : 'default'} dot>
              {queue.is_active ? t('queues.active') : t('queues.paused')}
            </Badge>
            <Badge>{queue.waiting_count} {t('queues.waiting')}</Badge>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <span
            role="button"
            onClick={(e) => { e.stopPropagation(); toggle(); }}
            aria-label={queue.is_active ? t('queues.pause') : t('queues.resume')}
            style={iconBtnStyle}
          >
            {queue.is_active ? <Pause size={12} /> : <Play size={12} />}
          </span>
          <span
            role="button"
            onClick={destroy}
            aria-label={t('queues.delete_queue')}
            style={{ ...iconBtnStyle, color: 'var(--danger)' }}
          >
            <Trash2 size={12} />
          </span>
        </div>
      </div>
    </button>
  );
}

/* ── Queue detail (items list) ────────────────────────────────────────── */
function QueueDetail({ queueId, onChanged }) {
  const { t } = useTranslation('content');
  const [queue, setQueue] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await composerAPI.queues.get(queueId);
      setQueue(res.data);
      if (res.data.items && Array.isArray(res.data.items)) {
        setItems(res.data.items);
      } else {
        const itemRes = await composerAPI.queues.items(queueId);
        setItems(itemRes.data || []);
      }
    } catch (e) {
      toast.error(t('queues.failed'));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [queueId]);

  async function addItem(content) {
    try {
      await composerAPI.queues.addItems(queueId, [{ content }]);
      toast.success(t('queues.item_added'));
      load(); onChanged?.();
    } catch (e) { toast.error(t('queues.item_add_failed')); }
  }

  async function approveItem(itemId) {
    try {
      await composerAPI.queues.approveItem(queueId, itemId);
      toast.success('Item approved');
      load(); onChanged?.();
    } catch (e) {
      toast.error('Failed to approve item');
    }
  }

  async function revokeItem(itemId) {
    try {
      await composerAPI.queues.revokeItem(queueId, itemId);
      toast.success('Approval revoked');
      load(); onChanged?.();
    } catch (e) {
      toast.error('Failed to revoke approval');
    }
  }

  async function moveItem(index, delta) {
    const targetIdx = index + delta;
    if (targetIdx < 0 || targetIdx >= items.length) return;
    const reordered = [...items];
    const [moved] = reordered.splice(index, 1);
    reordered.splice(targetIdx, 0, moved);
    setItems(reordered);
    try {
      await composerAPI.queues.reorder(queueId, reordered.map((i) => i.id));
      onChanged?.();
    } catch {
      toast.error('Failed to reorder items');
      load();
    }
  }

  if (loading || !queue) {
    return <div style={{ padding: 16, color: 'var(--text-tertiary)' }}>{t('queues.loading')}</div>;
  }

  return (
    <div>
      <div style={{
        padding: '14px 16px',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
      }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
            {queue.name}
          </div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            fontSize: 12, color: 'var(--text-tertiary)', marginTop: 4,
          }}>
            <Clock size={12} />
            <span style={{ fontFamily: 'var(--font-mono)' }}>{queue.schedule_rule || '—'}</span>
            <span>·</span>
            <span>{t(`queues.strategies.${queue.queue_strategy}`, queue.queue_strategy)}</span>
            <span>·</span>
            <span>{(queue.platforms || []).join(', ') || 'no platforms'}</span>
          </div>
        </div>
        <Button icon={Plus} size="sm" onClick={() => setShowAdd(true)}>{t('queues.add_item')}</Button>
      </div>

      <div style={{ padding: 16 }}>
        <div style={{
          display: 'flex', gap: 12, fontSize: 12, color: 'var(--text-secondary)',
          marginBottom: 16,
        }}>
          <span><strong>{queue.items_count}</strong> {t('queues.total_items', { count: queue.items_count })}</span>
          <span><strong>{queue.waiting_count}</strong> {t('queues.items_waiting', { count: queue.waiting_count })}</span>
          {queue.last_dispatched_at && (
            <span>{t('queues.last_fired', { time: formatDate(queue.last_dispatched_at, { dateStyle: 'short', timeStyle: 'short' }) })}</span>
          )}
        </div>

        {/* Queued Items List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {items.length === 0 ? (
            <div style={{
              padding: 24, textAlign: 'center',
              color: 'var(--text-tertiary)', fontSize: 13,
              background: 'var(--surface-sunken)', borderRadius: 'var(--radius-md)',
            }}>
              No items in queue. Add content above to start recurring publication.
            </div>
          ) : (
            items.map((item, idx) => (
              <div
                key={item.id}
                style={{
                  display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12,
                  padding: '12px 14px',
                  background: 'var(--surface-sunken)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{
                    fontSize: 13, color: 'var(--text-primary)',
                    whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginBottom: 6,
                  }}>
                    {item.content || <em style={{ color: 'var(--text-tertiary)' }}>(No text content)</em>}
                  </div>
                  {item.hashtags && item.hashtags.length > 0 && (
                    <div style={{ fontSize: 11, color: 'var(--brand-primary)', marginBottom: 6 }}>
                      {item.hashtags.map((h) => h.startsWith('#') ? h : `#${h}`).join(' ')}
                    </div>
                  )}
                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, fontSize: 11 }}>
                    <Badge variant={item.status === 'used' ? 'default' : item.status === 'waiting' ? 'info' : 'danger'}>
                      {item.status}
                    </Badge>

                    {item.media_urls && item.media_urls.length > 0 && (
                      <Badge variant="default">
                        <ImageIcon size={10} style={{ marginRight: 4 }} />
                        {item.media_urls.length} media
                      </Badge>
                    )}

                    {item.is_approved ? (
                      <Badge variant="success">
                        <CheckCircle2 size={10} style={{ marginRight: 4 }} />
                        Approved
                      </Badge>
                    ) : item.status === 'waiting' ? (
                      <Badge variant="warning">
                        <AlertCircle size={10} style={{ marginRight: 4 }} />
                        Pending Approval
                      </Badge>
                    ) : null}

                    {item.unified_post && (
                      <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                        Post #{item.unified_post}
                      </span>
                    )}
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
                  {item.status === 'waiting' && !item.is_approved && (
                    <Button size="xs" variant="primary" onClick={() => approveItem(item.id)}>
                      Approve
                    </Button>
                  )}
                  {item.status === 'waiting' && item.is_approved && (
                    <Button size="xs" variant="secondary" onClick={() => revokeItem(item.id)}>
                      Revoke
                    </Button>
                  )}
                  <button
                    type="button"
                    disabled={idx === 0}
                    onClick={() => moveItem(idx, -1)}
                    style={{ ...iconBtnStyle, opacity: idx === 0 ? 0.3 : 1 }}
                    title="Move up"
                  >
                    <ArrowUp size={12} />
                  </button>
                  <button
                    type="button"
                    disabled={idx === items.length - 1}
                    onClick={() => moveItem(idx, 1)}
                    style={{ ...iconBtnStyle, opacity: idx === items.length - 1 ? 0.3 : 1 }}
                    title="Move down"
                  >
                    <ArrowDown size={12} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {showAdd && (
        <AddItemModal onClose={() => setShowAdd(false)}
                      onSave={(content) => { addItem(content); setShowAdd(false); }} />
      )}
    </div>
  );
}

/* ── Modals ───────────────────────────────────────────────────────────── */
function CreateQueueModal({ onClose, onCreated }) {
  const { t } = useTranslation('content');
  const [form, setForm] = useState({
    name: '',
    schedule_rule: '0 10 * * 1-5',
    queue_strategy: 'sequential',
    platforms: ['facebook', 'instagram'],
  });
  const [saving, setSaving] = useState(false);

  async function save() {
    if (!form.name.trim()) { toast.error(t('queues.name_required')); return; }
    setSaving(true);
    try {
      const res = await composerAPI.queues.create(form);
      onCreated(res.data);
      toast.success(t('queues.queue_created'));
    } catch (e) {
      toast.error(e.response?.data?.detail || t('queues.failed'));
    } finally { setSaving(false); }
  }

  return (
    <Backdrop onClose={onClose}>
      <Card padding="none" style={{ width: 'min(480px, 92vw)' }}>
        <div style={modalHeader}>
          <h3 style={{ margin: 0, fontSize: 16 }}>{t('queues.modal_new_queue')}</h3>
          <button onClick={onClose} style={iconBtnStyle} aria-label="Close"><X size={14} /></button>
        </div>
        <div style={{ padding: 16 }}>
          <div style={{
            padding: '10px 12px',
            background: 'var(--surface-sunken)',
            borderRadius: 'var(--radius-md)',
            fontSize: 12,
            color: 'var(--text-secondary)',
            marginBottom: 14,
            lineHeight: 1.5,
            border: '1px solid var(--border-subtle)',
          }}>
            <strong>Policy D Notice:</strong> Queue items must be explicitly approved before autonomous recurring publication if your tenant requires approval.
          </div>
          <Field label={t('queues.field_name')}>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                   placeholder={t('queues.name_placeholder')} style={inputStyle} autoFocus />
          </Field>
          <Field label={t('queues.field_schedule')}>
            <input value={form.schedule_rule}
                   onChange={(e) => setForm({ ...form, schedule_rule: e.target.value })}
                   placeholder="0 10 * * 1-5"
                   style={{ ...inputStyle, fontFamily: 'var(--font-mono)' }} />
            <span style={helpStyle}>{t('queues.schedule_help')}</span>
          </Field>
          <Field label={t('queues.field_strategy')}>
            <select value={form.queue_strategy}
                    onChange={(e) => setForm({ ...form, queue_strategy: e.target.value })}
                    style={inputStyle}>
              {STRATEGIES.map((s) => <option key={s.id} value={s.id}>{t(`queues.strategies.${s.id}`, s.label)}</option>)}
            </select>
          </Field>
          <Field label={t('queues.field_platforms')}>
            <input value={(form.platforms || []).join(', ')}
                   onChange={(e) => setForm({ ...form, platforms: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) })}
                   placeholder="facebook, instagram"
                   style={inputStyle} />
          </Field>
        </div>
        <div style={modalFooter}>
          <Button variant="secondary" onClick={onClose}>{t('queues.cancel')}</Button>
          <Button onClick={save} loading={saving}>{t('queues.create')}</Button>
        </div>
      </Card>
    </Backdrop>
  );
}

function AddItemModal({ onClose, onSave }) {
  const { t } = useTranslation('content');
  const [content, setContent] = useState('');
  return (
    <Backdrop onClose={onClose}>
      <Card padding="none" style={{ width: 'min(520px, 92vw)' }}>
        <div style={modalHeader}>
          <h3 style={{ margin: 0, fontSize: 16 }}>{t('queues.modal_add_item')}</h3>
          <button onClick={onClose} style={iconBtnStyle} aria-label="Close"><X size={14} /></button>
        </div>
        <div style={{ padding: 16 }}>
          <Field label={t('queues.field_post_content')}>
            <textarea value={content} onChange={(e) => setContent(e.target.value)}
                      rows={6} placeholder={t('queues.post_content_placeholder')}
                      style={{ ...inputStyle, height: 'auto', padding: '10px 12px', resize: 'vertical' }} />
          </Field>
        </div>
        <div style={modalFooter}>
          <Button variant="secondary" onClick={onClose}>{t('queues.cancel')}</Button>
          <Button onClick={() => onSave(content)} disabled={!content.trim()}>{t('queues.add')}</Button>
        </div>
      </Card>
    </Backdrop>
  );
}

/* ── Layout helpers ───────────────────────────────────────────────────── */
function Backdrop({ onClose, children }) {
  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(10,14,20,0.5)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div onClick={(e) => e.stopPropagation()}>{children}</div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label style={{ display: 'block', marginBottom: 12 }}>
      <span style={fieldLabel}>{label}</span>
      {children}
    </label>
  );
}

const inputStyle = {
  width: '100%', height: 36, padding: '0 12px',
  background: 'var(--surface-card)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-md)',
  fontSize: 13, color: 'var(--text-primary)',
  outline: 'none', boxSizing: 'border-box', minHeight: 'unset',
};

const fieldLabel = {
  display: 'block', fontSize: 11, fontWeight: 600,
  color: 'var(--text-tertiary)', textTransform: 'uppercase',
  letterSpacing: 0.4, marginBottom: 6,
};

const helpStyle = {
  display: 'block', marginTop: 4, fontSize: 11, color: 'var(--text-tertiary)',
};

const code = {
  background: 'var(--surface-sunken)', padding: '0 6px', borderRadius: 4,
  fontFamily: 'var(--font-mono)', fontSize: 11,
};

const iconBtnStyle = {
  width: 28, height: 28, borderRadius: 'var(--radius-sm)',
  background: 'transparent', border: 'none', cursor: 'pointer',
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  color: 'var(--text-tertiary)',
  minHeight: 'unset', minWidth: 'unset',
};

const modalHeader = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)',
};

const modalFooter = {
  display: 'flex', justifyContent: 'flex-end', gap: 8,
  padding: '12px 16px', borderTop: '1px solid var(--border-subtle)',
};
