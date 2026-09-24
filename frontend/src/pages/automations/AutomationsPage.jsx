/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useEffect, useMemo, useState } from 'react';
import {
  Plus, Zap, Play, Pause, Trash2, ChevronRight, X, Sparkles,
  MessageSquare, MessageCircle, Star, AtSign, AlertCircle,
  Send, Bell, UserPlus, Tag, Webhook, Loader2,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';

import PageHeader from '../../components/layout/PageHeader';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import Badge from '../../components/ui/Badge';
import EmptyState from '../../components/ui/EmptyState';
import { automationsAPI } from '../../services/api';
import { formatDate, formatTime } from '../../utils/formatters';

const TRIGGER_OPTIONS = [
  { id: 'new_comment',         label: 'New comment',           icon: MessageSquare,
    desc: 'Fires whenever a new inbound comment arrives' },
  { id: 'new_dm',              label: 'New direct message',    icon: MessageCircle,
    desc: 'Fires on inbound DMs' },
  { id: 'new_review',          label: 'New review',            icon: Star,
    desc: 'Fires on a new Google Business review' },
  { id: 'keyword_mention',     label: 'Keyword mention',       icon: AtSign,
    desc: 'Fires when an inbound message contains certain keywords' },
  { id: 'negative_sentiment',  label: 'Negative sentiment',    icon: AlertCircle,
    desc: 'Fires when inbound sentiment is flagged negative' },
];

const ACTION_OPTIONS = [
  { id: 'auto_reply',     label: 'Auto-reply',          icon: Send,
    desc: 'Posts a fixed text reply' },
  { id: 'ai_smart_reply', label: 'AI smart-reply',      icon: Sparkles,
    desc: 'Lets Bop Social write a short reply matching your brand voice' },
  { id: 'notify',         label: 'Send notification',   icon: Bell,
    desc: 'Creates an in-app notification' },
  { id: 'assign',         label: 'Assign to user',      icon: UserPlus,
    desc: 'Assigns the conversation to a specific user' },
  { id: 'add_tag',        label: 'Add tag',             icon: Tag,
    desc: 'Tags the conversation for later filtering' },
  { id: 'webhook',        label: 'Call webhook',        icon: Webhook,
    desc: 'POSTs the event payload to your URL' },
];

export default function AutomationsPage() {
  const { t } = useTranslation('engagement');
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showBuilder, setShowBuilder] = useState(false);
  const [editing, setEditing] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const res = await automationsAPI.list();
      setRules(res.data?.results || res.data || []);
    } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function toggle(rule) {
    try { await automationsAPI.toggle(rule.id); load(); }
    catch { toast.error(t('automations.toasts.toggle_failed', 'Toggle failed')); }
  }
  async function destroy(rule) {
    if (!window.confirm(t('automations.delete_confirm', 'Delete "{{name}}"?', { name: rule.name }))) return;
    try {
      await automationsAPI.delete(rule.id);
      load();
      toast.success(t('automations.toasts.deleted', 'Deleted'));
    } catch {
      toast.error(t('automations.toasts.delete_failed', 'Delete failed'));
    }
  }

  return (
    <div style={{ paddingBottom: 32 }}>
      <PageHeader
        title={t('automations.title', 'Automations')}
        subtitle={t('automations.subtitle', 'If this happens, do that — across every connected platform')}
        action={<Button icon={Plus} onClick={() => { setEditing(null); setShowBuilder(true); }}>
          {t('automations.new_rule', 'New Rule')}
        </Button>}
      />

      <div style={{
        display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 320px',
        gap: 16, padding: '0 24px',
      }} className="automations-grid">
        <div>
          {loading && (
            <div style={{ padding: 32, textAlign: 'center' }}>
              <Loader2 size={18} className="ds-spin" color="var(--text-tertiary)" />
            </div>
          )}
          {!loading && rules.length === 0 && (
            <Card padding="none" style={{ overflow: 'hidden' }}>
              <EmptyState
                icon={Zap}
                title={t('automations.empty_title', 'No automations yet')}
                description={t('automations.empty_desc', 'Automations save you from staring at the inbox. Pick a template on the right or build one from scratch.')}
                action={<Button icon={Plus} onClick={() => { setEditing(null); setShowBuilder(true); }}>
                  {t('automations.build_rule', 'Build a rule')}
                </Button>}
              />
            </Card>
          )}
          {rules.map((rule) => (
            <RuleRow key={rule.id} rule={rule}
                     onToggle={() => toggle(rule)}
                     onEdit={() => { setEditing(rule); setShowBuilder(true); }}
                     onDelete={() => destroy(rule)} />
          ))}
        </div>

        <TemplatesSidebar onPick={(tpl) => { setEditing(tpl); setShowBuilder(true); }} />
      </div>

      {showBuilder && (
        <RuleBuilder
          initial={editing}
          onClose={() => setShowBuilder(false)}
          onSaved={() => { setShowBuilder(false); load(); }}
        />
      )}

      <style>{`
        .ds-spin { animation: ds-spin 0.9s linear infinite; }
        @keyframes ds-spin { to { transform: rotate(360deg); } }
        @media (max-width: 1024px) {
          .automations-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}

/* ── Rule row ──────────────────────────────────────────────────────────── */
function RuleRow({ rule, onToggle, onEdit, onDelete }) {
  const { t } = useTranslation('engagement');
  const trigger = TRIGGER_OPTIONS.find((tOption) => tOption.id === rule.trigger_type);
  const action  = ACTION_OPTIONS.find((aOption) => aOption.id === rule.action_type);
  const TIcon = trigger?.icon || Zap;
  const AIcon = action?.icon  || Send;

  const triggerLabel = trigger ? t(`automations.triggers.${trigger.id}.label`, trigger.label) : rule.trigger_type;
  const actionLabel = action ? t(`automations.actions.${action.id}.label`, action.label) : rule.action_type;

  return (
    <Card padding="md" style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
              {rule.name}
            </span>
            <Badge variant={rule.is_active ? 'success' : 'default'} dot>
              {rule.is_active ? t('automations.active', 'Active') : t('automations.paused', 'Paused')}
            </Badge>
            {rule.run_count > 0 && (
              <Badge>{t('automations.fired_badge', 'fired {{count}}×', { count: rule.run_count })}</Badge>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
                        fontSize: 12, color: 'var(--text-secondary)' }}>
            <Pill icon={TIcon} label={triggerLabel} />
            <ChevronRight size={12} color="var(--text-tertiary)" />
            <Pill icon={AIcon} label={actionLabel} accent />
          </div>

          {rule.last_run_at && (
            <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-tertiary)' }}>
              {t('automations.last_fired', 'Last fired {{date}}', { date: `${formatDate(rule.last_run_at)} ${formatTime(rule.last_run_at)}` })}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 4 }}>
          <Button variant="ghost" size="sm"
                  icon={rule.is_active ? Pause : Play}
                  onClick={onToggle}
                  iconOnly aria-label={rule.is_active ? t('automations.btn_pause', 'Pause') : t('automations.btn_resume', 'Resume')} />
          <Button variant="ghost" size="sm" onClick={onEdit}>{t('automations.btn_edit', 'Edit')}</Button>
          <Button variant="ghost" size="sm" icon={Trash2} onClick={onDelete}
                  iconOnly aria-label={t('automations.btn_delete', 'Delete')} />
        </div>
      </div>
    </Card>
  );
}

function Pill({ icon: Icon, label, accent }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '4px 10px', borderRadius: 'var(--radius-pill)',
      background: accent ? 'var(--brand-primary-glow)' : 'var(--surface-sunken)',
      color: accent ? 'var(--brand-primary-hover)' : 'var(--text-secondary)',
      border: '1px solid var(--border-subtle)',
      fontSize: 11, fontWeight: 600,
    }}>
      <Icon size={11} />
      {label}
    </span>
  );
}

/* ── Templates sidebar ─────────────────────────────────────────────────── */
function TemplatesSidebar({ onPick }) {
  const { t } = useTranslation('engagement');
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    automationsAPI.templates()
      .then((res) => setTemplates(res.data?.templates || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <Card padding="none" style={{ overflow: 'hidden', alignSelf: 'flex-start',
                                   position: 'sticky', top: 'calc(var(--topbar-height) + 16px)' }}>
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)',
                    display: 'flex', alignItems: 'center', gap: 8 }}>
        <Sparkles size={14} color="var(--brand-primary-hover)" />
        <strong style={{ fontSize: 14, color: 'var(--text-primary)' }}>{t('automations.templates_title', 'Templates')}</strong>
      </div>
      <div style={{ maxHeight: 'calc(100vh - 280px)', overflowY: 'auto' }}>
        {loading && <div style={{ padding: 16, color: 'var(--text-tertiary)', fontSize: 12 }}>{t('automations.loading', 'Loading…')}</div>}
        {templates.map((tItem, i) => (
          <button
            key={i} type="button"
            onClick={() => onPick(tItem)}
            style={{
              display: 'block', width: '100%', textAlign: 'left',
              padding: '12px 16px',
              background: 'transparent',
              border: 'none', borderBottom: '1px solid var(--border-subtle)',
              cursor: 'pointer', minHeight: 'unset', minWidth: 'unset',
              transition: 'var(--transition-fast)',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--surface-hover)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
          >
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
              {tItem.name}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
              {tItem.description}
            </div>
          </button>
        ))}
      </div>
    </Card>
  );
}

/* ── Rule builder modal ────────────────────────────────────────────────── */
function RuleBuilder({ initial, onClose, onSaved }) {
  const { t } = useTranslation('engagement');
  const isExisting = !!initial?.id;

  const [form, setForm] = useState(() => ({
    name:             initial?.name             || '',
    trigger_type:     initial?.trigger_type     || 'new_comment',
    trigger_filters:  initial?.trigger_filters  || {},
    action_type:      initial?.action_type      || 'notify',
    action_config:    initial?.action_config    || {},
    is_active:        initial?.is_active ?? true,
  }));
  const [saving, setSaving] = useState(false);

  const trigger = useMemo(() => TRIGGER_OPTIONS.find((tOption) => tOption.id === form.trigger_type), [form.trigger_type]);
  const action  = useMemo(() => ACTION_OPTIONS.find((aOption) => aOption.id === form.action_type),    [form.action_type]);

  async function save() {
    if (!form.name.trim()) { toast.error(t('automations.toasts.name_required', 'Name is required')); return; }
    setSaving(true);
    try {
      if (isExisting) await automationsAPI.update(initial.id, form);
      else            await automationsAPI.create(form);
      toast.success(isExisting ? t('automations.toasts.updated', 'Updated') : t('automations.toasts.created', 'Created'));
      onSaved();
    } catch (e) {
      toast.error(e.response?.data?.detail || t('automations.toasts.save_failed', 'Save failed'));
    } finally { setSaving(false); }
  }

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(10,14,20,0.5)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 16,
    }}>
      <Card onClick={(e) => e.stopPropagation()} padding="none" style={{
        width: 'min(620px, 100%)',
        maxHeight: 'calc(100vh - 32px)', overflow: 'hidden',
        display: 'flex', flexDirection: 'column',
      }}>
        <header style={modalHeader}>
          <div>
            <strong style={{ fontSize: 16 }}>
              {isExisting ? t('automations.modal.edit_rule', 'Edit rule') : (initial ? t('automations.modal.customise_template', 'Customise template') : t('automations.modal.new_rule', 'New rule'))}
            </strong>
            {initial && !isExisting && (
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
                {t('automations.modal.prefilled_from', 'Pre-filled from "{{name}}" template', { name: initial.name })}
              </div>
            )}
          </div>
          <button type="button" onClick={onClose} aria-label={t('automations.modal.close', 'Close')} style={iconBtnStyle}>
            <X size={14} />
          </button>
        </header>

        <div style={{ padding: 16, overflowY: 'auto', flex: 1 }}>
          <Field label={t('automations.modal.rule_name_label', 'Rule name')}>
            <input value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder={t('automations.modal.rule_name_placeholder', 'e.g. Auto-thank for 5-star reviews')}
                    style={inputStyle} autoFocus />
          </Field>

          <SectionLabel>{t('automations.modal.section_trigger', '1. Trigger')}</SectionLabel>
          <select value={form.trigger_type}
                   onChange={(e) => setForm({ ...form, trigger_type: e.target.value, trigger_filters: {} })}
                   style={inputStyle}>
            {TRIGGER_OPTIONS.map((tOption) => (
              <option key={tOption.id} value={tOption.id}>{t(`automations.triggers.${tOption.id}.label`, tOption.label)}</option>
            ))}
          </select>
          {trigger && (
            <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-tertiary)' }}>{t(`automations.triggers.${trigger.id}.desc`, trigger.desc)}</div>
          )}

          <TriggerFilters
            type={form.trigger_type}
            value={form.trigger_filters}
            onChange={(f) => setForm({ ...form, trigger_filters: f })}
          />

          <SectionLabel>{t('automations.modal.section_action', '2. Action')}</SectionLabel>
          <select value={form.action_type}
                   onChange={(e) => setForm({ ...form, action_type: e.target.value, action_config: {} })}
                   style={inputStyle}>
            {ACTION_OPTIONS.map((aOption) => (
              <option key={aOption.id} value={aOption.id}>{t(`automations.actions.${aOption.id}.label`, aOption.label)}</option>
            ))}
          </select>
          {action && (
            <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-tertiary)' }}>{t(`automations.actions.${action.id}.desc`, action.desc)}</div>
          )}

          <ActionConfig
            type={form.action_type}
            value={form.action_config}
            onChange={(c) => setForm({ ...form, action_config: c })}
          />

          <label style={{ display: 'flex', alignItems: 'center', gap: 8,
                          marginTop: 16, fontSize: 13, color: 'var(--text-primary)', cursor: 'pointer' }}>
            <input type="checkbox" checked={form.is_active}
                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            {t('automations.modal.enabled_label', 'Enabled — fire immediately on save')}
          </label>
        </div>

        <footer style={modalFooter}>
          <Button variant="secondary" onClick={onClose}>{t('automations.modal.btn_cancel', 'Cancel')}</Button>
          <Button onClick={save} loading={saving}>
            {isExisting ? t('automations.modal.btn_save_changes', 'Save changes') : t('automations.modal.btn_create_rule', 'Create rule')}
          </Button>
        </footer>
      </Card>
    </div>
  );
}

/* ── Trigger-specific filter inputs ────────────────────────────────────── */
function TriggerFilters({ type, value, onChange }) {
  const { t } = useTranslation('engagement');
  const set = (k, v) => onChange({ ...value, [k]: v });

  if (type === 'keyword_mention') {
    const kws = (value.keywords || []).join(', ');
    return (
      <Field label={t('automations.config.keywords_label', 'Keywords (comma-separated)')}>
        <input value={kws}
                onChange={(e) => set('keywords', e.target.value.split(',').map((x) => x.trim()).filter(Boolean))}
                placeholder={t('automations.config.keywords_placeholder', 'urgent, asap, refund')}
                style={inputStyle} />
      </Field>
    );
  }
  if (type === 'new_review') {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 12 }}>
        <Field label={t('automations.config.min_rating', 'Min rating')}>
          <input type="number" min={1} max={5}
                  value={value.min_rating ?? ''}
                  onChange={(e) => set('min_rating', e.target.value ? Number(e.target.value) : undefined)}
                  placeholder="1" style={inputStyle} />
        </Field>
        <Field label={t('automations.config.max_rating', 'Max rating')}>
          <input type="number" min={1} max={5}
                  value={value.max_rating ?? ''}
                  onChange={(e) => set('max_rating', e.target.value ? Number(e.target.value) : undefined)}
                  placeholder="5" style={inputStyle} />
        </Field>
      </div>
    );
  }
  // For other triggers, optionally restrict to specific platforms
  const allPlatforms = ['facebook', 'instagram', 'youtube', 'linkedin', 'google_my_business'];
  const selected = value.platforms || [];
  return (
    <div style={{ marginTop: 12 }}>
      <SectionLabel small>{t('automations.config.restrict_platforms', 'Restrict to platforms (optional)')}</SectionLabel>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {allPlatforms.map((p) => {
          const on = selected.includes(p);
          return (
            <button
              key={p} type="button"
              onClick={() => set('platforms', on ? selected.filter((x) => x !== p) : [...selected, p])}
              style={pillStyle(on)}
            >
              {p}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ── Action-specific config inputs ─────────────────────────────────────── */
function ActionConfig({ type, value, onChange }) {
  const { t } = useTranslation('engagement');
  const set = (k, v) => onChange({ ...value, [k]: v });

  if (type === 'auto_reply') {
    return (
      <Field label={t('automations.config.reply_template_label', 'Reply template (use {author_name}, {platform}, {content})')}>
        <textarea value={value.template || ''}
                   onChange={(e) => set('template', e.target.value)}
                   rows={3}
                   placeholder={t('automations.config.reply_template_placeholder', 'Thanks {author_name}! Glad you liked the post.')}
                   style={{ ...inputStyle, height: 'auto', resize: 'vertical' }} />
      </Field>
    );
  }
  if (type === 'ai_smart_reply') {
    return (
      <div style={{ ...infoBoxStyle, marginTop: 12 }}>
        <Sparkles size={14} color="var(--brand-primary-hover)" />
        <span>{t('automations.config.ai_smart_reply_desc', 'Bop Social writes a short on-brand reply using the trained brand voice.')}</span>
      </div>
    );
  }
  if (type === 'notify') {
    return (
      <>
        <Field label={t('automations.config.notif_title_label', 'Notification title')}>
          <input value={value.title || ''}
                  onChange={(e) => set('title', e.target.value)}
                  placeholder={t('automations.config.notif_title_placeholder', 'Heads up — needs attention')}
                  style={inputStyle} />
        </Field>
        <Field label={t('automations.config.notif_body_label', 'Body (use {author_name}, {platform}, {content})')}>
          <textarea value={value.body || ''}
                     onChange={(e) => set('body', e.target.value)}
                     rows={3}
                     placeholder={t('automations.config.notif_body_placeholder', '{author_name} on {platform}: {content}')}
                     style={{ ...inputStyle, height: 'auto', resize: 'vertical' }} />
        </Field>
      </>
    );
  }
  if (type === 'assign') {
    return (
      <Field label={t('automations.config.assign_user_label', 'User ID to assign to')}>
        <input type="number" value={value.user_id || ''}
                onChange={(e) => set('user_id', e.target.value ? Number(e.target.value) : undefined)}
                placeholder="42" style={inputStyle} />
      </Field>
    );
  }
  if (type === 'add_tag') {
    return (
      <Field label={t('automations.config.tag_label', 'Tag to apply')}>
        <input value={value.tag || ''}
                onChange={(e) => set('tag', e.target.value)}
                placeholder={t('automations.config.tag_placeholder', 'priority')}
                style={inputStyle} />
      </Field>
    );
  }
  if (type === 'webhook') {
    return (
      <Field label={t('automations.config.webhook_url_label', 'Webhook URL')}>
        <input value={value.url || ''}
                onChange={(e) => set('url', e.target.value)}
                placeholder={t('automations.config.webhook_url_placeholder', 'https://your-app.example.com/webhook')}
                style={inputStyle} />
      </Field>
    );
  }
  return null;
}

/* ── Layout helpers ────────────────────────────────────────────────────── */
function Field({ label, children }) {
  return (
    <label style={{ display: 'block', marginTop: 12 }}>
      <span style={{
        display: 'block', fontSize: 11, fontWeight: 600,
        color: 'var(--text-tertiary)',
        textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 6,
      }}>
        {label}
      </span>
      {children}
    </label>
  );
}

function SectionLabel({ children, small }) {
  return (
    <div style={{
      marginTop: small ? 12 : 20, marginBottom: 8,
      fontSize: small ? 11 : 12, fontWeight: 700,
      color: 'var(--text-tertiary)',
      textTransform: 'uppercase', letterSpacing: 0.6,
    }}>
      {children}
    </div>
  );
}

function pillStyle(on) {
  return {
    padding: '4px 10px', borderRadius: 'var(--radius-pill)',
    border: `1px solid ${on ? 'transparent' : 'var(--border-subtle)'}`,
    background: on ? 'var(--brand-primary-glow)' : 'var(--surface-card)',
    color: on ? 'var(--brand-primary-hover)' : 'var(--text-secondary)',
    fontSize: 11, fontWeight: 600, cursor: 'pointer',
    minHeight: 'unset', minWidth: 'unset',
  };
}

const inputStyle = {
  width: '100%', padding: '9px 12px',
  background: 'var(--surface-card)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-md)',
  fontSize: 13, color: 'var(--text-primary)',
  outline: 'none', boxSizing: 'border-box', minHeight: 'unset',
  fontFamily: 'inherit',
};

const iconBtnStyle = {
  width: 28, height: 28, borderRadius: 'var(--radius-sm)',
  background: 'transparent', border: 'none', cursor: 'pointer',
  color: 'var(--text-tertiary)',
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  minHeight: 'unset', minWidth: 'unset',
};

const modalHeader = {
  padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)',
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
};

const modalFooter = {
  padding: 12, borderTop: '1px solid var(--border-subtle)',
  display: 'flex', justifyContent: 'flex-end', gap: 8,
};

const infoBoxStyle = {
  display: 'flex', alignItems: 'center', gap: 8,
  padding: '10px 12px', borderRadius: 'var(--radius-md)',
  background: 'var(--brand-primary-glow)', color: 'var(--text-primary)',
  fontSize: 12, lineHeight: 1.5,
};
