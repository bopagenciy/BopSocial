/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, RefreshCw, Trash2, FileType, Loader2, AlertCircle, Send } from 'lucide-react';

import PageHeader from '../components/layout/PageHeader';
import { useWhatsAppTemplates } from '../hooks/useWhatsApp';
import { whatsappAPI } from '../services/api';
import { safeHtml } from '../utils/sanitize';

const COLORS = {
  primary: '#00CCF5', primaryD: '#00A8D8',
  border: 'var(--border-default)', text: 'var(--text-primary)', muted: 'var(--text-secondary)',
  success: '#10b981', danger: '#dc2626',
};

const STATUS_BADGE = {
  draft:    { bg: 'var(--surface-sunken)', color: 'var(--text-secondary)' },
  pending:  { bg: '#fef3c7', color: '#a16207' },
  approved: { bg: '#dcfce7', color: '#15803d' },
  rejected: { bg: '#fee2e2', color: '#b91c1c' },
  paused:   { bg: '#fef3c7', color: '#a16207' },
};

export default function WhatsAppTemplatesPage() {
  const { t } = useTranslation('messaging');
  const { data, refetch, loading } = useWhatsAppTemplates();
  const [showDrawer, setShowDrawer] = useState(false);

  const count = data?.length || 0;
  const subtitle = count === 1
    ? t('templates.subtitle', { count, defaultValue: '1 template' })
    : t('templates.subtitle_plural', { count, defaultValue: `${count} templates` });

  return (
    <div style={{ paddingBottom: 32 }}>
      <PageHeader
        title={t('templates.title', 'Templates')}
        subtitle={subtitle}
        action={
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => refetch()} style={btnSecondary}><RefreshCw size={14} /> {t('templates.refresh', 'Refresh')}</button>
            <button onClick={() => setShowDrawer(true)} style={btnPrimary}><Plus size={14} /> {t('templates.new_template', 'New Template')}</button>
          </div>
        }
      />

      <div style={{ padding: '0 16px' }}>
        {loading && <div style={emptyState}><Loader2 size={14} className="spin" /> {t('templates.loading', 'Loading…')}</div>}
        {!loading && (data || []).length === 0 && (
          <div style={emptyState}>
            <FileType size={32} color={COLORS.muted} style={{ marginBottom: 8 }} />
            <div style={{ fontWeight: 600, color: COLORS.text }}>{t('templates.empty_title', 'No templates yet')}</div>
            <div style={{ fontSize: 13, color: COLORS.muted, marginBottom: 12 }}>
              {t('templates.empty_desc', 'Templates are required for outbound messages outside the 24h window.')}
            </div>
            <button onClick={() => setShowDrawer(true)} style={btnPrimary}>
              <Plus size={14} /> {t('templates.create_first', 'Create your first template')}
            </button>
          </div>
        )}

        <div style={grid}>
          {(data || []).map((tpl) => (
            <TemplateCard key={tpl.id} tpl={tpl} onChange={refetch} t={t} />
          ))}
        </div>
      </div>

      {showDrawer && (
        <CreateTemplateDrawer
          onClose={() => setShowDrawer(false)}
          onCreated={() => { setShowDrawer(false); refetch(); }}
        />
      )}

      <style>{`.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function TemplateCard({ tpl, onChange, t }) {
  const status = STATUS_BADGE[tpl.status] || STATUS_BADGE.draft;
  const statusLabel = t ? t(`statuses.${tpl.status}`, tpl.status) : tpl.status;
  return (
    <div style={card}>
      <div style={{ padding: 14, borderBottom: `1px solid ${COLORS.border}` }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontFamily: 'monospace', fontSize: 13, fontWeight: 700, color: COLORS.text, wordBreak: 'break-all' }}>{tpl.name}</div>
            <div style={{ fontSize: 11, color: COLORS.muted, marginTop: 4 }}>
              {tpl.category} · {tpl.language} · {tpl.template_type}
            </div>
          </div>
          <span style={{ ...badge, background: status.bg, color: status.color }}>{statusLabel}</span>
        </div>
      </div>
      <div style={{ padding: 14 }}>
        <div style={preview}
             dangerouslySetInnerHTML={safeHtml(tpl.preview)} />
        {tpl.rejection_reason && (
          <div style={{ ...errorBox, marginTop: 10 }}>
            <AlertCircle size={14} /> {tpl.rejection_reason}
          </div>
        )}
        <div style={{ display: 'flex', gap: 6, marginTop: 12, flexWrap: 'wrap' }}>
          {tpl.status !== 'approved' && (
            <button
              onClick={async () => { await whatsappAPI.templates.submit(tpl.id); onChange(); }}
              style={btnSecondary}
            >
              <Send size={12} /> {t ? t('campaigns.wizard.send_now', 'Resubmit') : 'Resubmit'}
            </button>
          )}
          <button
            onClick={async () => { await whatsappAPI.templates.sync(tpl.id); onChange(); }}
            style={btnSecondary}
          >
            <RefreshCw size={12} /> {t ? t('templates.refresh', 'Sync') : 'Sync'}
          </button>
          <button
            onClick={async () => {
              const msg = t ? t('templates.delete_confirm', 'Delete template? This cannot be undone.') : 'Delete template?';
              if (window.confirm(msg)) {
                await whatsappAPI.templates.delete(tpl.id);
                onChange();
              }
            }}
            style={{ ...btnSecondary, color: COLORS.danger, borderColor: '#fecaca' }}
          >
            <Trash2 size={12} /> {t ? t('campaigns.delete', 'Delete') : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  );
}

function CreateTemplateDrawer({ onClose, onCreated }) {
  const { t } = useTranslation('messaging');
  const [form, setForm] = useState({
    name: '', category: 'utility', language: 'en_US',
    template_type: 'text', body: '', footer: '',
  });
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const renderedPreview = useMemo(() => {
    let body = form.body || '';
    body = body.replace(/\{\{(\d+)\}\}/g, (_, n) => `[Sample ${n}]`);
    return body;
  }, [form.body]);

  function setName(v) {
    // Slug-like: lowercase, underscores
    const slug = v.toLowerCase().replace(/[^a-z0-9_]/g, '_').replace(/_+/g, '_');
    setForm({ ...form, name: slug });
  }

  async function save() {
    if (!form.name.trim() || !form.body.trim()) {
      setError(t('templates.drawer.name_label', 'Name') + ' & ' + t('templates.drawer.body_label', 'Body') + ' required.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await whatsappAPI.templates.create(form);
      onCreated();
    } catch (e) {
      setError(e.response?.data?.detail || JSON.stringify(e.response?.data) || e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={drawerBackdrop} onClick={onClose}>
      <div style={drawerBox} onClick={(e) => e.stopPropagation()}>
        <header style={{
          padding: 16, borderBottom: `1px solid ${COLORS.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <h3 style={{ margin: 0, fontSize: 16, color: COLORS.text }}>{t('templates.drawer.title', 'New Template')}</h3>
          <button onClick={onClose} style={iconBtn}>×</button>
        </header>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 320px', gap: 16, padding: 16, overflow: 'auto', flex: 1 }}>
          {/* Form */}
          <div>
            <Field
              label={t('templates.drawer.name_label', 'Name (slug)')}
              value={form.name}
              onChange={setName}
              placeholder={t('templates.drawer.name_placeholder', 'order_confirmation')}
              helper={t('templates.drawer.name_hint', 'Lowercase, no spaces')}
            />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              <SelectField
                label={t('templates.drawer.category_label', 'Category')}
                value={form.category}
                onChange={(v) => setForm({ ...form, category: v })}
                options={['utility', 'marketing', 'authentication']}
              />
              <SelectField
                label={t('templates.drawer.language_label', 'Language')}
                value={form.language}
                onChange={(v) => setForm({ ...form, language: v })}
                options={['en_US', 'en', 'en_GB', 'es', 'pt_BR', 'fr', 'de', 'hi', 'ar']}
              />
              <SelectField
                label={t('templates.drawer.header_type_label', 'Type')}
                value={form.template_type}
                onChange={(v) => setForm({ ...form, template_type: v })}
                options={['text', 'image', 'video', 'document']}
              />
            </div>

            <label style={{ display: 'block', marginTop: 8 }}>
              <span style={fieldLabel}>
                {t('templates.drawer.body_label', 'Body')} ({t('templates.drawer.body_hint', 'use {{1}} for variables')})
              </span>
              <textarea
                rows={8}
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
                placeholder={t('templates.drawer.body_placeholder', 'Hi {{1}}, your order #{{2}} is on the way!')}
                style={{ ...input, fontFamily: 'monospace' }}
              />
            </label>

            <Field
              label={t('templates.drawer.footer_label', 'Footer (optional)')}
              value={form.footer}
              onChange={(v) => setForm({ ...form, footer: v })}
              placeholder={t('templates.drawer.footer_placeholder', 'Reply STOP to unsubscribe')}
            />

            {error && <div style={{ ...errorBox, marginTop: 10 }}><AlertCircle size={14} /> {String(error)}</div>}
          </div>

          {/* Live preview */}
          <div style={{ position: 'sticky', top: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: COLORS.muted, marginBottom: 8, textTransform: 'uppercase' }}>
              {t('bot_templates.preview.title', 'Preview')}
            </div>
            <div style={whatsappBubble}>
              <div style={{ whiteSpace: 'pre-wrap' }}>{renderedPreview || 'Start typing your template body…'}</div>
              {form.footer && <div style={{ marginTop: 8, fontSize: 11, color: '#667781' }}>{form.footer}</div>}
            </div>
          </div>
        </div>

        <footer style={{
          padding: 16, borderTop: `1px solid ${COLORS.border}`,
          display: 'flex', justifyContent: 'flex-end', gap: 8,
        }}>
          <button onClick={onClose} style={btnSecondary}>{t('templates.drawer.cancel_btn', 'Cancel')}</button>
          <button onClick={save} disabled={saving} style={btnPrimary}>
            {saving ? t('templates.drawer.submitting', 'Submitting…') : t('templates.drawer.submit_btn', 'Submit for Approval')}
          </button>
        </footer>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, placeholder, helper }) {
  return (
    <label style={{ display: 'block', marginBottom: 10 }}>
      <span style={fieldLabel}>{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} style={input} />
      {helper && <span style={{ fontSize: 11, color: COLORS.muted }}>{helper}</span>}
    </label>
  );
}
function SelectField({ label, value, onChange, options }) {
  return (
    <label style={{ display: 'block', marginBottom: 10 }}>
      <span style={fieldLabel}>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} style={input}>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

const card = { background: 'var(--surface-card)', border: `1px solid ${COLORS.border}`, borderRadius: 12, overflow: 'hidden' };
const grid = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
  gap: 12,
};
const preview = {
  whiteSpace: 'pre-wrap', fontSize: 13, color: COLORS.text,
  background: 'var(--surface-sunken)', padding: 12, borderRadius: 8,
  border: `1px solid ${COLORS.border}`, minHeight: 60,
};
const emptyState = {
  padding: 40, textAlign: 'center', background: 'var(--surface-card)',
  border: `1px solid ${COLORS.border}`, borderRadius: 12,
  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
};
const badge = { display: 'inline-flex', padding: '3px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600 };
const input = {
  width: '100%', padding: '9px 12px', borderRadius: 8,
  border: `1px solid ${COLORS.border}`, fontSize: 13, outline: 'none', boxSizing: 'border-box',
};
const fieldLabel = {
  display: 'block', fontSize: 12, fontWeight: 600,
  color: COLORS.muted, textTransform: 'uppercase', letterSpacing: '0.04em',
  marginBottom: 4,
};
const code = {
  background: 'var(--surface-sunken)', padding: '0px 6px', borderRadius: 4,
  fontSize: 12, fontFamily: 'monospace',
};
const btnPrimary = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '8px 14px', borderRadius: 8, border: 'none',
  background: 'linear-gradient(135deg, #00CCF5, #00A8D8)', color: '#fff',
  fontWeight: 600, fontSize: 13, cursor: 'pointer',
};
const btnSecondary = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '7px 12px', borderRadius: 8, border: `1px solid ${COLORS.border}`,
  background: 'var(--surface-card)', color: COLORS.text, fontWeight: 600, fontSize: 12, cursor: 'pointer',
};
const iconBtn = {
  background: 'transparent', border: 'none', padding: 4, cursor: 'pointer',
  fontSize: 22, lineHeight: 1, color: COLORS.muted,
};
const errorBox = {
  display: 'flex', alignItems: 'center', gap: 8,
  padding: '8px 12px', borderRadius: 8,
  background: '#fef2f2', color: COLORS.danger,
  border: '1px solid #fecaca', fontSize: 12,
};
const drawerBackdrop = {
  position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)',
  display: 'flex', justifyContent: 'flex-end', zIndex: 100,
};
const drawerBox = {
  background: 'var(--surface-card)', width: '100%', maxWidth: 920, height: '100%',
  display: 'flex', flexDirection: 'column',
  boxShadow: '-12px 0 40px rgba(0,0,0,0.15)',
};
const whatsappBubble = {
  background: '#dcf8c6', borderRadius: 12,
  padding: 12, fontSize: 13, color: 'var(--text-primary)',
  boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
};
