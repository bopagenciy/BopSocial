/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
/**
 * LeadDetailPage — full lead view with tabs.
 *
 * Tabs: Overview / Activity / Conversation / Custom Fields.
 * Right rail: status pills, assigned-to, "Convert" / "Score with AI" /
 * "Add note" / "Send WhatsApp" quick actions.
 */
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, Star, Sparkles, MessageSquare, CheckCircle2, Trash2,
  User, Bot, Clock, Phone, Mail, MapPin, Building2,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { leadAPI } from '../../services/api';
import toast from '../../components/ui/toast';
import { formatCurrency } from '../../utils/formatters';

const STATUS_KEYS = [
  { key: 'new',       color: 'var(--brand-primary)' },
  { key: 'contacted', color: 'var(--info)' },
  { key: 'qualified', color: 'var(--warning)' },
  { key: 'converted', color: 'var(--success)' },
  { key: 'lost',      color: 'var(--text-tertiary)' },
  { key: 'spam',      color: 'var(--danger)' },
];

export default function LeadDetailPage() {
  const { t } = useTranslation('messaging');
  const { id } = useParams();
  const navigate = useNavigate();
  const [lead,    setLead]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab,     setTab]     = useState('overview');
  const [scoring, setScoring] = useState(false);
  const [convertOpen, setConvertOpen] = useState(false);

  const statuses = useMemo(() => STATUS_KEYS.map((s) => ({
    ...s,
    label: t(`leads.statuses.${s.key}`, s.key),
  })), [t]);

  function load() {
    setLoading(true);
    leadAPI.get(id)
      .then((r) => setLead(r.data))
      .catch(() => toast.error(t('leads.detail.load_error')))
      .finally(() => setLoading(false));
  }
  useEffect(load, [id]); // eslint-disable-line

  async function changeStatus(status) {
    try {
      const r = await leadAPI.status(id, { status });
      setLead(r.data);
      toast.success(t('leads.detail.status_updated', { status: t(`leads.statuses.${status}`, status) }));
    } catch { toast.error(t('leads.detail.update_error')); }
  }

  async function scoreWithAI() {
    setScoring(true);
    try {
      await leadAPI.scoreWithAI(id);
      toast.success(t('leads.detail.scored_success'));
      load();
    } catch (e) { toast.error(e?.response?.data?.error || t('leads.detail.scoring_error')); }
    finally { setScoring(false); }
  }

  async function addNote(content) {
    if (!content.trim()) return;
    try {
      await leadAPI.activity(id, { activity_type: 'note', content });
      toast.success(t('leads.detail.note_added'));
      load();
    } catch { toast.error(t('leads.detail.note_error')); }
  }

  if (loading || !lead) {
    return <div style={{ padding: 32, color: 'var(--text-tertiary)' }}>{t('leads.loading', 'Loading…')}</div>;
  }

  const currentStatus = STATUS_KEYS.find((s) => s.key === lead.status) || STATUS_KEYS[0];
  const customFieldKeys = Object.keys(lead.custom_fields || {});

  return (
    <div style={{ maxWidth: 1080, margin: '0 auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Link to="/admin/leads" style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        fontSize: 13, color: 'var(--text-secondary)', textDecoration: 'none', alignSelf: 'flex-start',
      }}>
        <ArrowLeft size={14} /> {t('leads.detail.back')}
      </Link>

      {/* Hero */}
      <header style={{
        padding: 18,
        background: 'var(--surface-card)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        display: 'flex', alignItems: 'flex-start', gap: 14, flexWrap: 'wrap',
      }}>
        <span style={{
          width: 48, height: 48, flexShrink: 0,
          background: 'var(--brand-primary-glow)', color: 'var(--brand-primary-hover)',
          borderRadius: 'var(--radius-md)',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <User size={22} strokeWidth={2.2} />
        </span>
        <div style={{ flex: 1, minWidth: 200 }}>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
            {lead.name || <em style={{ color: 'var(--text-tertiary)' }}>{t('leads.table.no_name')}</em>}
          </h1>
          <div style={{ marginTop: 6, display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 13, color: 'var(--text-secondary)' }}>
            {lead.phone && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><Phone size={12} /> {lead.phone}</span>}
            {lead.email && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><Mail size={12} /> {lead.email}</span>}
            {lead.location && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><MapPin size={12} /> {lead.location}</span>}
          </div>
        </div>

        {/* Status + score + actions */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
          <select value={lead.status}
                  onChange={(e) => changeStatus(e.target.value)}
                  style={{
                    padding: '6px 10px',
                    background: 'transparent', color: currentStatus.color,
                    border: `1px solid ${currentStatus.color}`, borderRadius: 'var(--radius-pill)',
                    fontSize: 12, fontWeight: 600, fontFamily: 'inherit', cursor: 'pointer',
                  }}>
            {statuses.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
          <ScoreBadge score={lead.quality_score} reason={lead.quality_reason} />
        </div>
      </header>

      {/* Quick action bar */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button type="button" onClick={scoreWithAI} disabled={scoring} style={btnGhost}>
          <Sparkles size={13} /> {scoring ? t('leads.detail.scoring') : t('leads.detail.score_ai')}
        </button>
        <button type="button" onClick={() => setConvertOpen(true)} disabled={lead.status === 'converted'} style={btnPrimary}>
          <CheckCircle2 size={13} /> {t('leads.detail.convert')}
        </button>
      </div>

      {/* Tabs */}
      <nav style={{ display: 'flex', gap: 6, borderBottom: '1px solid var(--border-subtle)' }}>
        {['overview', 'activity', 'conversation', 'custom'].map((k) => (
          <button key={k} type="button" onClick={() => setTab(k)} style={{
            padding: '10px 16px',
            background: 'transparent',
            color: tab === k ? 'var(--text-primary)' : 'var(--text-tertiary)',
            border: 'none',
            borderBottom: `2px solid ${tab === k ? 'var(--brand-primary)' : 'transparent'}`,
            fontSize: 13, fontWeight: tab === k ? 600 : 500, fontFamily: 'inherit',
            cursor: 'pointer', marginBottom: -1,
          }}>
            {k === 'overview' ? t('leads.detail.overview_tab') :
             k === 'activity' ? t('leads.detail.activity_tab_count', { count: lead.activities?.length || 0 }) :
             k === 'conversation' ? t('leads.detail.conversation_tab') :
             t('leads.detail.custom_fields_tab_count', { count: customFieldKeys.length })}
          </button>
        ))}
      </nav>

      {tab === 'overview'     && <Overview lead={lead} />}
      {tab === 'activity'     && <Activity lead={lead} onAddNote={addNote} />}
      {tab === 'conversation' && <ConversationTab lead={lead} />}
      {tab === 'custom'       && <CustomTab lead={lead} />}

      {convertOpen && (
        <ConvertModal lead={lead} onClose={() => setConvertOpen(false)}
                      onConverted={() => { setConvertOpen(false); load(); }} />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Tab: Overview
// ─────────────────────────────────────────────────────────
function Overview({ lead }) {
  const { t, i18n } = useTranslation('messaging');
  const currency = lead.currency || lead.conversion_currency || 'USD';
  const rows = [
    [t('leads.fields.interest'), lead.interest],
    [t('leads.fields.budget'),   lead.budget],
    [t('leads.fields.location'), lead.location],
    [t('leads.fields.tags'),     (lead.tags || []).join(', ')],
    [],
    [t('leads.fields.source_flow'),     lead.source_flow_name],
    [t('leads.fields.source_ad'),       lead.source_ad_name || lead.source_ad_id],
    [t('leads.fields.source_campaign'), lead.source_campaign_name || lead.source_campaign_id],
    [],
    [t('leads.fields.created'),  lead.created_at && new Date(lead.created_at).toLocaleString()],
    [t('leads.fields.updated'),  lead.updated_at && new Date(lead.updated_at).toLocaleString()],
    [t('leads.fields.converted_at'), lead.converted_at && new Date(lead.converted_at).toLocaleString()],
    [t('leads.fields.conversion_value'), lead.conversion_value && formatCurrency(Number(lead.conversion_value), currency, i18n?.language)],
  ];
  return (
    <section style={card}>
      {rows.map((r, i) => r.length === 0 ? (
        <div key={i} style={{ height: 8 }} />
      ) : (
        <Row key={i} k={r[0]} v={r[1]} />
      ))}
    </section>
  );
}

function Row({ k, v }) {
  if (!v) return null;
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '160px 1fr', gap: 16,
      padding: '7px 0', borderBottom: '1px solid var(--border-subtle)',
      fontSize: 13,
    }}>
      <span style={{ color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em', fontSize: 11, fontWeight: 600 }}>{k}</span>
      <span style={{ color: 'var(--text-primary)', wordBreak: 'break-word' }}>{v}</span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Tab: Activity (timeline + add note)
// ─────────────────────────────────────────────────────────
function Activity({ lead, onAddNote }) {
  const { t } = useTranslation('messaging');
  const [draft, setDraft] = useState('');
  const acts = lead.activities || [];
  return (
    <section>
      <div style={{ ...card, marginBottom: 12 }}>
        <textarea value={draft} onChange={(e) => setDraft(e.target.value)}
                  rows={2} placeholder={t('leads.detail.note_placeholder')}
                  style={{
                    width: '100%', padding: 10,
                    background: 'var(--surface-sunken)',
                    border: '1px solid var(--border-default)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: 13, color: 'var(--text-primary)',
                    outline: 'none', fontFamily: 'inherit',
                    boxSizing: 'border-box', resize: 'vertical',
                  }} />
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
          <button type="button" onClick={() => { onAddNote(draft); setDraft(''); }}
                  disabled={!draft.trim()} style={btnPrimary}>
            {t('leads.detail.add_note')}
          </button>
        </div>
      </div>

      {acts.length === 0 ? (
        <div style={{ ...card, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
          {t('leads.detail.no_activity')}
        </div>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {acts.map((a) => (
            <li key={a.id} style={{ ...card, padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={pill}>{a.activity_type}</span>
                {a.actor_email && <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{a.actor_email}</span>}
                <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-tertiary)', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                  <Clock size={10} /> {new Date(a.created_at).toLocaleString()}
                </span>
              </div>
              {a.content && <div style={{ fontSize: 13, color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>{a.content}</div>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ─────────────────────────────────────────────────────────
// Tab: Conversation (calls /timeline/ for bot_steps)
// ─────────────────────────────────────────────────────────
function ConversationTab({ lead }) {
  const { t } = useTranslation('messaging');
  const [steps, setSteps] = useState(null);
  useEffect(() => {
    leadAPI.timeline(lead.id)
      .then((r) => setSteps(r.data?.bot_steps || []))
      .catch(() => setSteps([]));
  }, [lead.id]);

  if (steps === null) {
    return <div style={{ ...card, color: 'var(--text-tertiary)' }}>{t('leads.detail.loading_conv')}</div>;
  }
  if (steps.length === 0) {
    return <div style={{ ...card, color: 'var(--text-tertiary)', textAlign: 'center', fontSize: 13 }}>
      {t('leads.detail.no_conv')}
    </div>;
  }
  // The timeline returns newest-first; render oldest-first for chat readability
  const ordered = [...steps].reverse();
  return (
    <section style={{ ...card, padding: 14 }}>
      {ordered.map((s) => {
        const isUser = s.direction === 'user_to_bot';
        const isSystem = s.direction === 'system';
        const text = (s.payload?.text || s.payload?.body || s.payload?.caption || '').toString();
        if (isSystem) {
          return (
            <div key={s.id} style={{ textAlign: 'center', margin: '6px 0', fontSize: 11 }}>
              <span style={pill}>{s.node_type}</span>
            </div>
          );
        }
        return (
          <div key={s.id} style={{ display: 'flex', flexDirection: isUser ? 'row-reverse' : 'row', gap: 6, marginBottom: 8 }}>
            <span style={{
              width: 24, height: 24, flexShrink: 0,
              background: isUser ? 'var(--surface-card)' : 'var(--brand-gradient)',
              color: isUser ? 'var(--text-secondary)' : '#fff',
              borderRadius: '50%',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {isUser ? <User size={12} /> : <Bot size={12} />}
            </span>
            <div style={{
              maxWidth: '75%', padding: '8px 12px',
              fontSize: 13, lineHeight: 1.45,
              background: isUser ? 'var(--surface-sunken)' : '#dcf8c6',
              color: isUser ? 'var(--text-primary)' : '#1f2c34',
              borderRadius: isUser ? '8px 8px 2px 8px' : '8px 8px 8px 2px',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              {text || <em>({s.node_type})</em>}
            </div>
          </div>
        );
      })}
    </section>
  );
}

// ─────────────────────────────────────────────────────────
// Tab: Custom Fields
// ─────────────────────────────────────────────────────────
function CustomTab({ lead }) {
  const { t } = useTranslation('messaging');
  const entries = Object.entries(lead.custom_fields || {});
  if (entries.length === 0) {
    return <div style={{ ...card, color: 'var(--text-tertiary)', textAlign: 'center', fontSize: 13 }}>
      {t('leads.detail.no_custom_fields')}
    </div>;
  }
  return (
    <section style={card}>
      {entries.map(([k, v]) => (
        <Row key={k} k={k} v={typeof v === 'object' ? JSON.stringify(v) : String(v)} />
      ))}
    </section>
  );
}

function ScoreBadge({ score, reason }) {
  if (score == null) return null;
  const color =
    score >= 80 ? 'var(--success)' :
    score >= 60 ? 'var(--warning)' :
    score >= 40 ? 'var(--text-secondary)' :
                  'var(--text-tertiary)';
  return (
    <div style={{ textAlign: 'right' }}>
      <span title={reason || ''} style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        padding: '4px 10px',
        fontSize: 13, fontWeight: 700,
        color, border: `1px solid ${color}`, background: 'transparent',
        borderRadius: 'var(--radius-pill)',
        fontVariantNumeric: 'tabular-nums',
      }}>
        <Star size={11} fill="currentColor" /> {score}/100
      </span>
      {reason && (
        <div style={{
          marginTop: 4, maxWidth: 240, fontSize: 11,
          color: 'var(--text-tertiary)', lineHeight: 1.4, textAlign: 'right',
        }}>
          {reason}
        </div>
      )}
    </div>
  );
}

function ConvertModal({ lead, onClose, onConverted }) {
  const { t, i18n } = useTranslation('messaging');
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const currency = lead.currency || lead.conversion_currency || 'USD';
  async function go() {
    setBusy(true);
    try {
      await leadAPI.convert(lead.id, Number(value || 0));
      const formattedVal = formatCurrency(Number(value || 0), currency, i18n?.language);
      toast.success(t('leads.convert_modal.success', { value: formattedVal }));
      onConverted();
    } catch (e) { toast.error(e?.response?.data?.error || t('leads.convert_modal.error')); }
    finally { setBusy(false); }
  }
  return (
    <div style={backdrop} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={modal}>
        <header style={{ padding: '14px 18px' }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>{t('leads.convert_modal.title')}</h2>
        </header>
        <div style={{ padding: '0 18px 14px' }}>
          <p style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--text-secondary)' }}>
            {t('leads.convert_modal.text', { name: lead.name || lead.phone })}
          </p>
          <label style={lbl}>{t('leads.convert_modal.value_label')}</label>
          <input type="number" value={value} onChange={(e) => setValue(e.target.value)}
                 placeholder="50000" autoFocus
                 style={{ ...inputStyle, width: '100%' }} />
        </div>
        <footer style={{ padding: '12px 18px', borderTop: '1px solid var(--border-subtle)', display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button type="button" onClick={onClose} style={btnGhost}>{t('leads.convert_modal.cancel')}</button>
          <button type="button" onClick={go} disabled={busy} style={btnPrimary}>
            <CheckCircle2 size={13} /> {busy ? t('leads.convert_modal.converting') : t('leads.convert_modal.convert_btn')}
          </button>
        </footer>
      </div>
    </div>
  );
}

const card = {
  padding: 16,
  background: 'var(--surface-card)',
  border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--radius-md)',
};
const pill = {
  padding: '2px 8px',
  fontSize: 10, fontWeight: 600,
  letterSpacing: '0.04em', textTransform: 'uppercase',
  color: 'var(--text-tertiary)',
  background: 'var(--surface-sunken)',
  border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--radius-pill)',
};
const inputStyle = {
  padding: '8px 10px',
  background: 'var(--surface-sunken)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-sm)',
  fontSize: 13, color: 'var(--text-primary)',
  outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box',
};
const btnPrimary = { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px', background: 'var(--brand-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', fontSize: 12, fontWeight: 600, fontFamily: 'inherit', cursor: 'pointer' };
const btnGhost = { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 12px', background: 'var(--surface-card)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', fontSize: 12, fontWeight: 600, fontFamily: 'inherit', cursor: 'pointer' };
const lbl = { display: 'block', fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: 4 };
const backdrop = { position: 'fixed', inset: 0, zIndex: 1100, background: 'rgba(10,14,20,0.50)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 };
const modal   = { width: '100%', maxWidth: 460, background: 'var(--surface-elevated)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-xl)' };
