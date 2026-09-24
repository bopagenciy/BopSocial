/* ============================================================================
 *  Bop Social — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
/**
 * SettingsSections — Sub-sections for UserSettingsPage
 * Notifications, Appearance, Keyboard Shortcuts, API Keys, Data Privacy, Webhooks, Cross-links
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Sun, Moon, Monitor, Plus, Copy, Trash2,
  Download, AlertTriangle, Bell, Mail, Smartphone,
  Sparkles, ArrowRight, Webhook,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useTheme } from '../../hooks/useTheme';
import Button from '../../components/ui/Button';
import Switch from '../../components/ui/Switch';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import KeyboardShortcut from '../../components/ui/KeyboardShortcut';
import EmptyState from '../../components/ui/EmptyState';
import Input from '../../components/ui/Input';
import toast from '../../components/ui/toast';
import { apiKeysAPI, privacyAPI } from '../../services/api';

// ─────────────────────────────────────────────────────────────────────────
// 1. Notifications — per-channel × per-event matrix
// ─────────────────────────────────────────────────────────────────────────
const NOTIF_CHANNELS = [
  { id: 'in_app',    icon: Bell,       labelKey: 'notifications.channels.in_app', fallback: 'In-app' },
  { id: 'email',     icon: Mail,       labelKey: 'notifications.channels.email', fallback: 'Email' },
  { id: 'browser',   icon: Smartphone, labelKey: 'notifications.channels.browser', fallback: 'Browser' },
];

const NOTIF_EVENTS = [
  { id: 'mentions',         labelKey: 'notifications.events.mentions.label',       descKey: 'notifications.events.mentions.description',       fallbackLabel: 'Mentions',           fallbackDesc: 'Someone mentioned a tracked account.' },
  { id: 'alerts',           labelKey: 'notifications.events.alerts.label',         descKey: 'notifications.events.alerts.description',         fallbackLabel: 'Performance alerts', fallbackDesc: 'Engagement drops or viral posts.' },
  { id: 'reports',          labelKey: 'notifications.events.reports.label',        descKey: 'notifications.events.reports.description',        fallbackLabel: 'Scheduled reports',  fallbackDesc: 'Weekly + monthly report emails.' },
  { id: 'team',             labelKey: 'notifications.events.team.label',           descKey: 'notifications.events.team.description',           fallbackLabel: 'Team activity',      fallbackDesc: 'New members, role changes, invitations.' },
  { id: 'token_expiry',     labelKey: 'notifications.events.token_expiry.label',   descKey: 'notifications.events.token_expiry.description',   fallbackLabel: 'Token expiry',       fallbackDesc: 'OAuth tokens about to expire.' },
];

const NOTIF_KEY = 'socialstats_notif_prefs';
const NOTIF_DEFAULT = NOTIF_EVENTS.reduce((acc, e) => {
  acc[e.id] = { in_app: true, email: e.id === 'token_expiry', browser: false };
  return acc;
}, {});

export function NotificationsSection() {
  const { t } = useTranslation('settings');
  const [prefs, setPrefs] = useState(() => {
    try {
      const raw = localStorage.getItem(NOTIF_KEY);
      return raw ? { ...NOTIF_DEFAULT, ...JSON.parse(raw) } : NOTIF_DEFAULT;
    } catch { return NOTIF_DEFAULT; }
  });

  function toggle(eventId, channelId) {
    setPrefs((p) => ({
      ...p,
      [eventId]: { ...p[eventId], [channelId]: !p[eventId]?.[channelId] },
    }));
  }

  function save() {
    try {
      localStorage.setItem(NOTIF_KEY, JSON.stringify(prefs));
      toast.success(t('notifications.saved', 'Notification preferences saved'));
    } catch {
      toast.error(t('notifications.err_save', 'Could not save preferences'));
    }
  }

  return (
    <SectionContainer
      title={t('notifications.title', 'Notifications')}
      description={t('notifications.subtitle', "Choose which events you'd like to be notified about, and where.")}
      action={<Button onClick={save} size="sm">{t('notifications.save_btn', 'Save preferences')}</Button>}
    >
      <Card padding="none">
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 560 }}>
            <thead>
              <tr style={{ background: 'var(--surface-sunken)' }}>
                <th scope="col" style={notifThStyle}>{t('notifications.event_col', 'Event')}</th>
                {NOTIF_CHANNELS.map((c) => (
                  <th key={c.id} scope="col" style={{ ...notifThStyle, textAlign: 'center' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                      <c.icon size={12} /> {t(c.labelKey, c.fallback)}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {NOTIF_EVENTS.map((e, i) => (
                <tr key={e.id} style={{ borderTop: i > 0 ? '1px solid var(--border-subtle)' : 'none' }}>
                  <td style={{ padding: '14px 16px', verticalAlign: 'top' }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{t(e.labelKey, e.fallbackLabel)}</div>
                    <div style={{ marginTop: 2, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{t(e.descKey, e.fallbackDesc)}</div>
                  </td>
                  {NOTIF_CHANNELS.map((c) => {
                    const channelLabel = t(c.labelKey, c.fallback);
                    const eventLabel = t(e.labelKey, e.fallbackLabel);
                    return (
                      <td key={c.id} style={{ padding: '14px 16px', textAlign: 'center' }}>
                        <Switch
                          checked={!!prefs[e.id]?.[c.id]}
                          onChange={() => toggle(e.id, c.id)}
                          size="sm"
                          aria-label={t('notifications.switch_aria', { channel: channelLabel, event: eventLabel, defaultValue: `${channelLabel} notifications for ${eventLabel}` })}
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </SectionContainer>
  );
}

const notifThStyle = {
  textAlign: 'left',
  padding: '12px 16px',
  fontSize: 11, fontWeight: 600,
  letterSpacing: '0.06em', textTransform: 'uppercase',
  color: 'var(--text-tertiary)',
};

// ─────────────────────────────────────────────────────────────────────────
// 2. Appearance — theme + density
// ─────────────────────────────────────────────────────────────────────────
const DENSITY_KEY = 'socialstats_density';

export function AppearanceSection() {
  const { t } = useTranslation('settings');
  const { preference, setTheme } = useTheme();
  const [density, setDensity] = useState(() => {
    try { return localStorage.getItem(DENSITY_KEY) || 'comfortable'; }
    catch { return 'comfortable'; }
  });

  function changeDensity(value) {
    setDensity(value);
    try {
      localStorage.setItem(DENSITY_KEY, value);
      document.documentElement.dataset.density = value;
      toast.success(t('appearance.density_set', { value, defaultValue: `Density set to ${value}` }));
    } catch {}
  }

  return (
    <SectionContainer
      title={t('appearance.title', 'Appearance')}
      description={t('appearance.subtitle', 'Customise how Bop Social looks and feels.')}
    >
      <Card padding="md">
        <div style={{ marginBottom: 8, fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{t('appearance.theme_title', 'Theme')}</div>
        <p style={{ margin: '0 0 16px', fontSize: 13, color: 'var(--text-secondary)' }}>
          {t('appearance.theme_desc', 'Choose a light or dark theme. "System" matches your OS preference.')}
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }}>
          <ThemeCard active={preference === 'light'}  icon={Sun}     label={t('appearance.themes.light', 'Light')}   onClick={() => setTheme('light')} />
          <ThemeCard active={preference === 'dark'}   icon={Moon}    label={t('appearance.themes.dark', 'Dark')}    onClick={() => setTheme('dark')} />
          <ThemeCard active={preference === 'system'} icon={Monitor} label={t('appearance.themes.system', 'System')}  onClick={() => setTheme('system')} />
        </div>
      </Card>

      <Card padding="md" style={{ marginTop: 16 }}>
        <div style={{ marginBottom: 8, fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{t('appearance.density_title', 'Density')}</div>
        <p style={{ margin: '0 0 16px', fontSize: 13, color: 'var(--text-secondary)' }}>
          {t('appearance.density_desc', 'Show more or less content per screen. "Compact" reduces row heights and padding.')}
        </p>
        <div style={{ display: 'flex', gap: 8 }}>
          {[
            { value: 'comfortable', label: t('appearance.density.comfortable', 'Comfortable') },
            { value: 'compact',     label: t('appearance.density.compact', 'Compact') },
          ].map((d) => (
            <button
              key={d.value}
              type="button"
              onClick={() => changeDensity(d.value)}
              style={{
                padding: '8px 14px',
                minHeight: 'unset', minWidth: 'unset',
                background: density === d.value ? 'var(--brand-primary-soft)' : 'var(--surface-card)',
                color: density === d.value ? 'var(--brand-primary-hover)' : 'var(--text-secondary)',
                border: `1px solid ${density === d.value ? 'var(--brand-primary)' : 'var(--border-default)'}`,
                borderRadius: 'var(--radius-pill)',
                fontSize: 13, fontWeight: 600,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              {d.label}
            </button>
          ))}
        </div>
      </Card>
    </SectionContainer>
  );
}

function ThemeCard({ active, icon: Icon, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
        padding: 18,
        minHeight: 'unset', minWidth: 'unset',
        background: active ? 'var(--brand-primary-soft)' : 'var(--surface-card)',
        border: `1px solid ${active ? 'var(--brand-primary)' : 'var(--border-default)'}`,
        boxShadow: active ? 'var(--shadow-glow)' : 'var(--shadow-xs)',
        borderRadius: 'var(--radius-md)',
        cursor: 'pointer',
        fontFamily: 'inherit',
        color: active ? 'var(--brand-primary-hover)' : 'var(--text-secondary)',
        transition: 'var(--transition-fast)',
      }}
    >
      <Icon size={20} strokeWidth={2} />
      <span style={{ fontSize: 13, fontWeight: 600 }}>{label}</span>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// 3. Keyboard Shortcuts — list of all shortcuts
// ─────────────────────────────────────────────────────────────────────────
const SHORTCUTS = [
  { keys: 'cmd+k',         id: 'cmd_k',        category: 'global',     fallback: 'Open command palette' },
  { keys: 'cmd+/',         id: 'cmd_slash',    category: 'global',     fallback: 'Show shortcuts' },
  { keys: 'esc',           id: 'esc',          category: 'global',     fallback: 'Close modal / palette' },
  { keys: 'cmd+j',         id: 'cmd_j',        category: 'global',     fallback: 'Open AI assistant' },
  { keys: 'g+d',           id: 'g_d',          category: 'navigation', fallback: 'Go to dashboard' },
  { keys: 'g+a',           id: 'g_a',          category: 'navigation', fallback: 'Go to analytics' },
  { keys: 'g+r',           id: 'g_r',          category: 'navigation', fallback: 'Go to reports' },
  { keys: 'g+i',           id: 'g_i',          category: 'navigation', fallback: 'Go to inbox' },
  { keys: 'cmd+enter',     id: 'cmd_enter',    category: 'composer',   fallback: 'Submit composer / form' },
  { keys: 'cmd+s',         id: 'cmd_s',        category: 'composer',   fallback: 'Save draft' },
  { keys: 'cmd+shift+p',   id: 'cmd_shift_p',  category: 'composer',   fallback: 'Publish now' },
  { keys: 'r',             id: 'r',            category: 'inbox',      fallback: 'Reply' },
  { keys: 'a',             id: 'a',            category: 'inbox',      fallback: 'Archive conversation' },
  { keys: 'shift+u',       id: 'shift_u',      category: 'inbox',      fallback: 'Toggle unread' },
];

export function KeyboardShortcutsSection() {
  const { t } = useTranslation('settings');
  const grouped = SHORTCUTS.reduce((acc, s) => {
    (acc[s.category] = acc[s.category] || []).push(s);
    return acc;
  }, {});

  return (
    <SectionContainer
      title={t('shortcuts.title', 'Keyboard Shortcuts')}
      description={t('shortcuts.subtitle', 'Speed up your workflow with these keyboard shortcuts.')}
    >
      {Object.entries(grouped).map(([cat, items]) => (
        <Card key={cat} padding="none" style={{ marginBottom: 14 }}>
          <div style={{
            padding: '12px 18px',
            borderBottom: '1px solid var(--border-subtle)',
            fontSize: 11, fontWeight: 600,
            letterSpacing: '0.08em', textTransform: 'uppercase',
            color: 'var(--text-tertiary)',
            background: 'var(--surface-sunken)',
          }}>
            {t(`shortcuts.categories.${cat}`, cat)}
          </div>
          {items.map((s, i) => (
            <div
              key={s.keys}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '12px 18px',
                borderTop: i > 0 ? '1px solid var(--border-subtle)' : 'none',
              }}
            >
              <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>{t(`shortcuts.items.${s.id}`, s.fallback)}</span>
              <KeyboardShortcut keys={s.keys} size="md" />
            </div>
          ))}
        </Card>
      ))}
      <p style={{ marginTop: 12, fontSize: 12, color: 'var(--text-tertiary)' }}>
        {t('shortcuts.hint', { key: 'cmd+/', defaultValue: 'Custom keybindings coming soon. Press cmd+/ from anywhere to view this list.' })}
      </p>
    </SectionContainer>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// 4. API Keys — generate / revoke (: now wired to /api/api-keys/)
// ─────────────────────────────────────────────────────────────────────────
export function APIKeysSection() {
  const { t, i18n } = useTranslation('settings');
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState('');
  const [scopes, setScopes] = useState('');
  // The plaintext key is shown ONCE on creation. After that, only key_prefix.
  const [justCreated, setJustCreated] = useState(null);
  const [creating, setCreating] = useState(false);

  function load() {
    setLoading(true);
    apiKeysAPI.list()
      .then((r) => setKeys(r.data?.keys || []))
      .catch(() => toast.error(t('api_keys.err_create', 'Could not load API keys')))
      .finally(() => setLoading(false));
  }
  useEffect(() => { load(); }, []);

  async function generate() {
    if (!name.trim()) { toast.error(t('api_keys.err_name_required', 'Give the key a name first')); return; }
    setCreating(true);
    try {
      const payload = {
        name: name.trim(),
        scopes: scopes.split(',').map(s => s.trim()).filter(Boolean),
      };
      const r = await apiKeysAPI.create(payload);
      setJustCreated(r.data);
      setKeys((ks) => [r.data, ...ks]);
      setName('');
      setScopes('');
      toast.success(t('api_keys.created_success', 'API key created'));
    } catch (e) {
      toast.error(e?.response?.data?.error || t('api_keys.err_create', 'Could not create key'));
    } finally { setCreating(false); }
  }

  async function revoke(id) {
    if (!window.confirm(t('api_keys.confirm_revoke', 'Revoke this key? Any application using it will stop working.'))) return;
    try {
      await apiKeysAPI.revoke(id);
      toast.success(t('api_keys.revoked_success', 'Key revoked'));
      load();
    } catch { toast.error(t('api_keys.err_revoke', 'Could not revoke')); }
  }

  function copyKey(value) {
    try { navigator.clipboard.writeText(value); toast.success(t('api_keys.copied', 'Copied to clipboard')); }
    catch { toast.error(t('api_keys.err_copy', 'Could not copy')); }
  }

  return (
    <SectionContainer
      title={t('api_keys.title', 'API Keys')}
      description={t('api_keys.subtitle', 'Programmatic access for your scripts and integrations. Keys are stored as SHA-256 hashes — we never see the plaintext after creation.')}
    >
      <Card padding="md" style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
          {t('api_keys.generate_title', 'Generate a new key')}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: '2 1 220px', minWidth: 0 }}>
            <Input size="md" placeholder={t('api_keys.name_placeholder', 'e.g. "Production deploy"')}
                   value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div style={{ flex: '2 1 220px', minWidth: 0 }}>
            <Input size="md" placeholder={t('api_keys.scopes_placeholder', 'Scopes (comma-separated, e.g. read:posts, write:leads)')}
                   value={scopes} onChange={(e) => setScopes(e.target.value)} />
          </div>
          <Button onClick={generate} icon={Plus} size="md" disabled={creating}>
            {creating ? t('api_keys.creating', 'Creating…') : t('api_keys.generate_btn', 'Generate')}
          </Button>
        </div>
        <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--text-tertiary)' }}>
          {t('api_keys.hint', 'Keys are shown once at generation — copy and store them securely.')}
        </p>
      </Card>

      {justCreated && justCreated.plaintext_key && (
        <Card padding="md" style={{ marginBottom: 16, borderColor: 'var(--warning)', background: 'var(--warning-bg)' }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--warning)', marginBottom: 8,
                        display: 'flex', alignItems: 'center', gap: 6 }}>
            <AlertTriangle size={14} /> {t('api_keys.warning_title', 'Save this key now — it will not be shown again')}
          </div>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 12,
            background: 'var(--surface-sunken)', padding: '8px 12px',
            borderRadius: 'var(--radius-xs)',
            wordBreak: 'break-all', userSelect: 'all',
          }}>{justCreated.plaintext_key}</div>
          <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
            <Button size="sm" icon={Copy} onClick={() => copyKey(justCreated.plaintext_key)}>
              {t('api_keys.copy', 'Copy')}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setJustCreated(null)}>
              {t('api_keys.saved_it', "I've saved it")}
            </Button>
          </div>
        </Card>
      )}

      {loading ? (
        <Card padding="md"><div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>{t('api_keys.loading', 'Loading…')}</div></Card>
      ) : keys.length === 0 ? (
        <Card padding="none">
          <EmptyState icon={Sparkles} title={t('api_keys.empty_title', 'No API keys yet')}
                      description={t('api_keys.empty_desc', 'Generate your first key above to start integrating Bop Social with your other tools.')}
                      compact />
        </Card>
      ) : (
        <Card padding="none">
          {keys.map((k, i) => {
            const dateStr = new Date(k.created_at).toLocaleDateString(i18n.language?.startsWith('es') ? 'es-ES' : 'en-US');
            const lastUsedStr = k.last_used_at
              ? t('api_keys.last_used_at', { date: new Date(k.last_used_at).toLocaleDateString(i18n.language?.startsWith('es') ? 'es-ES' : 'en-US'), defaultValue: `Last used ${new Date(k.last_used_at).toLocaleDateString()}` })
              : t('api_keys.never_used', 'Never used');
            const callsText = k.use_count === 1
              ? t('api_keys.calls_count_one', '1 call')
              : t('api_keys.calls_count_other', { count: k.use_count, defaultValue: `${k.use_count} calls` });

            return (
              <div key={k.id} style={{
                display: 'grid', gridTemplateColumns: '1fr auto', gap: 12,
                alignItems: 'center', padding: '14px 18px',
                borderTop: i > 0 ? '1px solid var(--border-subtle)' : 'none',
                opacity: k.is_active ? 1 : 0.6,
              }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                    {k.name}
                    {!k.is_active && (
                      <Badge style={{ marginLeft: 8 }}>{k.is_expired ? t('api_keys.expired', 'Expired') : t('api_keys.revoked', 'Revoked')}</Badge>
                    )}
                  </div>
                  <div style={{ marginTop: 2, fontSize: 12, color: 'var(--text-tertiary)',
                                display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                    <span>{t('api_keys.created_at', { date: dateStr, defaultValue: `Created ${dateStr}` })}</span>
                    <span>{lastUsedStr}</span>
                    <span>{callsText}</span>
                    {k.scopes?.length > 0 && <span>{t('api_keys.scopes_label', { scopes: k.scopes.join(', '), defaultValue: `Scopes: ${k.scopes.join(', ')}` })}</span>}
                  </div>
                  <div style={{
                    marginTop: 6, fontFamily: 'var(--font-mono)', fontSize: 12,
                    color: 'var(--text-secondary)', background: 'var(--surface-sunken)',
                    padding: '4px 8px', borderRadius: 'var(--radius-xs)',
                    display: 'inline-block',
                  }}>
                    {k.key_prefix}{'•'.repeat(24)}
                  </div>
                </div>
                {k.is_active && (
                  <Button variant="ghost" size="sm" iconOnly icon={Trash2}
                          aria-label={t('api_keys.revoke_aria', 'Revoke key')} onClick={() => revoke(k.id)} />
                )}
              </div>
            );
          })}
        </Card>
      )}
    </SectionContainer>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// 5. Data & Privacy — export + delete account
// ─────────────────────────────────────────────────────────────────────────
const CONSENT_KEYS = [
  'marketing_emails',
  'product_emails',
  'cookies_analytics',
  'cookies_marketing',
  'ai_processing_optout',
  'whatsapp_marketing',
  'data_processing',
];

export function DataPrivacySection() {
  const { t, i18n } = useTranslation('settings');
  const [exports, setExports] = useState([]);
  const [exportBusy, setExportBusy] = useState(false);
  const [consents, setConsents] = useState({});
  const [processingPaused, setProcessingPaused] = useState(false);
  const [pendingDeletion, setPendingDeletion] = useState(null);
  const [loading, setLoading] = useState(true);

  function loadAll() {
    setLoading(true);
    Promise.all([
      privacyAPI.exportList().catch(() => ({ data: { requests: [] } })),
      privacyAPI.consents().catch(()  => ({ data: { consents: {} } })),
      privacyAPI.processingStatus().catch(() => ({ data: { workspaces: [] } })),
    ]).then(([ex, co, ps]) => {
      setExports(ex.data?.requests || []);
      setConsents(co.data?.consents || {});
      const ws = ps.data?.workspaces || [];
      setProcessingPaused(ws.length > 0 && ws.every(w => w.is_processing_paused));
      // Canceled deletions get filtered out client-side; "queued" is the actionable one.
      const queued = (ex.data?.requests || []).find(() => false);
      setPendingDeletion(queued || null);
    }).finally(() => setLoading(false));
  }
  useEffect(() => { loadAll(); }, []);

  async function requestExport() {
    setExportBusy(true);
    try {
      await privacyAPI.exportRequest();
      toast.success(t('data_privacy.export_queued', 'Export queued — we will email you when it is ready'));
      loadAll();
    } catch (e) {
      toast.error(e?.response?.data?.error || t('data_privacy.err_export', 'Could not queue export'));
    } finally { setExportBusy(false); }
  }

  async function toggleConsent(type, given) {
    try {
      await privacyAPI.setConsent(type, given);
      setConsents((c) => ({ ...c, [type]: given }));
    } catch { toast.error(t('data_privacy.err_consent', 'Could not save consent')); }
  }

  async function toggleProcessing(paused) {
    try {
      await privacyAPI.setProcessingPaused(paused);
      setProcessingPaused(paused);
      toast.success(paused ? t('data_privacy.processing_paused', 'Processing paused') : t('data_privacy.processing_resumed', 'Processing resumed'));
    } catch { toast.error(t('data_privacy.err_update', 'Could not update')); }
  }

  async function deleteAccount() {
    const reason = window.prompt(t('data_privacy.prompt_delete_reason', 'Tell us why (optional). Your account will be permanently deleted in 30 days unless canceled.'));
    if (reason === null) return;
    try {
      const r = await privacyAPI.deleteAccount(reason || '');
      setPendingDeletion(r.data);
      toast.success(t('data_privacy.deletion_scheduled_toast', 'Deletion scheduled — you have 30 days to cancel'));
    } catch (e) {
      toast.error(e?.response?.data?.error || t('data_privacy.err_schedule_deletion', 'Could not schedule deletion'));
    }
  }

  async function cancelDeletion() {
    try {
      await privacyAPI.cancelDeleteAccount();
      setPendingDeletion(null);
      toast.success(t('data_privacy.deletion_canceled_toast', 'Deletion canceled'));
    } catch { toast.error(t('data_privacy.err_cancel_deletion', 'Could not cancel')); }
  }

  if (loading) {
    return <SectionContainer title={t('data_privacy.title', 'Data & Privacy')} description={t('data_privacy.loading', 'Loading…')}><Card padding="md" /></SectionContainer>;
  }

  return (
    <SectionContainer
      title={t('data_privacy.title', 'Data & Privacy')}
      description={t('data_privacy.subtitle', 'Your data, your rights. Export everything, manage consents, pause processing, or delete your account.')}
    >
      {/* Export */}
      <Card padding="md" style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
          <span style={{
            display: 'inline-flex', flexShrink: 0,
            width: 40, height: 40, borderRadius: 'var(--radius-md)',
            background: 'var(--brand-primary-soft)', color: 'var(--brand-primary-hover)',
            alignItems: 'center', justifyContent: 'center',
          }}><Download size={18} strokeWidth={2.2} /></span>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 600 }}>{t('data_privacy.export_title', 'Export your data')}</div>
            <p style={{ margin: '4px 0 12px', fontSize: 13, color: 'var(--text-secondary)' }}>
              {t('data_privacy.export_desc', 'Download a ZIP with your profile, owned workspaces, consent log, and request history. Delivered via email link (expires in 7 days).')}
            </p>
            <Button size="sm" icon={Download} disabled={exportBusy} onClick={requestExport}>
              {exportBusy ? t('data_privacy.queueing', 'Queueing…') : t('data_privacy.request_export', 'Request export')}
            </Button>
            {exports.length > 0 && (
              <ul style={{ margin: '12px 0 0', padding: 0, listStyle: 'none',
                           fontSize: 12, color: 'var(--text-tertiary)' }}>
                {exports.slice(0, 3).map((e) => (
                  <li key={e.id} style={{ padding: '4px 0' }}>
                    #{e.id} · {e.status}
                    {e.completed_at && <> · {new Date(e.completed_at).toLocaleDateString(i18n.language?.startsWith('es') ? 'es-ES' : 'en-US')}</>}
                    {e.download_url && e.status === 'completed' && (
                      <> · <a href={e.download_url} target="_blank" rel="noreferrer"
                              style={{ color: 'var(--brand-primary-hover)' }}>{t('data_privacy.download', 'Download')}</a></>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </Card>

      {/* Consents */}
      <Card padding="md" style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>{t('data_privacy.consents_title', 'Your consents')}</div>
        <p style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--text-secondary)' }}>
          {t('data_privacy.consents_desc', 'Toggle communication and tracking preferences. Withdrawals take effect immediately.')}
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {CONSENT_KEYS.map((key) => (
            <div key={key} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '8px 0', borderBottom: '1px solid var(--border-subtle)',
            }}>
              <span style={{ fontSize: 13 }}>{t(`data_privacy.consent_labels.${key}`)}</span>
              <Switch checked={!!consents[key]} onChange={(v) => toggleConsent(key, v)} />
            </div>
          ))}
        </div>
      </Card>

      {/* Processing pause */}
      <Card padding="md" style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 600 }}>{t('data_privacy.pause_title', 'Pause data processing')}</div>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-secondary)' }}>
              {t('data_privacy.pause_desc', 'When paused, sync tasks skip your workspaces, AI features are disabled, and the composer goes read-only. You can still log in to view existing data.')}
            </p>
          </div>
          <Switch checked={processingPaused} onChange={toggleProcessing} />
        </div>
      </Card>

      {/* Danger zone */}
      <Card padding="md" style={{ borderColor: 'var(--danger)' }}>
        <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
          <span style={{
            display: 'inline-flex', flexShrink: 0,
            width: 40, height: 40, borderRadius: 'var(--radius-md)',
            background: 'var(--danger-bg)', color: 'var(--danger)',
            alignItems: 'center', justifyContent: 'center',
          }}><AlertTriangle size={18} strokeWidth={2.2} /></span>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--danger)' }}>{t('data_privacy.delete_account_title', 'Delete account')}</div>
            <p style={{ margin: '4px 0 12px', fontSize: 13, color: 'var(--text-secondary)' }}>
              {t('data_privacy.delete_account_desc', 'Permanently delete your account, sessions, MFA, API keys, and personal data after a 30-day grace period. Audit logs are anonymised but retained for compliance.')}
            </p>
            {pendingDeletion ? (
              <div style={{
                padding: '10px 12px',
                background: 'var(--warning-bg)', color: 'var(--warning)',
                border: '1px solid var(--warning)', borderRadius: 'var(--radius-sm)',
                fontSize: 12, marginBottom: 8,
              }}>
                {t('data_privacy.deletion_scheduled', {
                  date: new Date(pendingDeletion.grace_until).toLocaleDateString(i18n.language?.startsWith('es') ? 'es-ES' : 'en-US'),
                  defaultValue: `Deletion scheduled — completes on ${new Date(pendingDeletion.grace_until).toLocaleDateString()}`,
                })}
                {' '}<Button size="xs" variant="ghost" onClick={cancelDeletion}>{t('data_privacy.cancel_deletion', 'Cancel')}</Button>
              </div>
            ) : (
              <Button variant="danger" size="sm" icon={Trash2} onClick={deleteAccount}>
                {t('data_privacy.delete_my_account', 'Delete my account')}
              </Button>
            )}
          </div>
        </div>
      </Card>
    </SectionContainer>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// 6. Webhooks — external endpoint subscriptions (stub)
// ─────────────────────────────────────────────────────────────────────────
const WEBHOOK_KEY = 'socialstats_webhook_endpoints';
const WEBHOOK_EVENTS = [
  'composer.post_published',
  'composer.post_failed',
  'inbox.new_message',
  'credential.token_expired',
  'goal.milestone_hit',
];

export function WebhooksSection() {
  const { t } = useTranslation('settings');
  const [endpoints, setEndpoints] = useState(() => {
    try { return JSON.parse(localStorage.getItem(WEBHOOK_KEY) || '[]'); }
    catch { return []; }
  });
  const [url, setUrl] = useState('');

  function save(next) {
    setEndpoints(next);
    try { localStorage.setItem(WEBHOOK_KEY, JSON.stringify(next)); } catch {}
  }

  function add() {
    if (!/^https:\/\//.test(url)) { toast.error(t('webhooks.err_https', 'Endpoint must use HTTPS')); return; }
    save([{ id: `wh_${Date.now()}`, url: url.trim(), events: WEBHOOK_EVENTS, active: true }, ...endpoints]);
    setUrl('');
    toast.success(t('webhooks.endpoint_added', 'Endpoint added'));
  }

  function remove(id) {
    save(endpoints.filter((e) => e.id !== id));
    toast.success(t('webhooks.endpoint_removed', 'Endpoint removed'));
  }

  return (
    <SectionContainer
      title={t('webhooks.title', 'Webhooks')}
      description={t('webhooks.subtitle', 'Receive HTTP POST notifications when events happen in your workspace.')}
    >
      <Card padding="md" style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
          {t('webhooks.add_title', 'Add an endpoint')}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 280px', minWidth: 0 }}>
            <Input
              size="md"
              type="url"
              placeholder={t('webhooks.placeholder', 'https://your-server.com/webhooks/bopsocial')}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </div>
          <Button onClick={add} icon={Plus} size="md">{t('webhooks.add_btn', 'Add')}</Button>
        </div>
      </Card>

      {endpoints.length === 0 ? (
        <Card padding="none">
          <EmptyState
            icon={Webhook}
            title={t('webhooks.empty_title', 'No webhook endpoints')}
            description={t('webhooks.empty_desc', 'Add an HTTPS endpoint above to start receiving events.')}
            compact
          />
        </Card>
      ) : (
        <Card padding="none">
          {endpoints.map((e, i) => {
            const countText = e.events.length === 1
              ? t('webhooks.events_subscribed_one', '1 event subscribed')
              : t('webhooks.events_subscribed_other', { count: e.events.length, defaultValue: `${e.events.length} events subscribed` });

            return (
              <div
                key={e.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '14px 18px',
                  borderTop: i > 0 ? '1px solid var(--border-subtle)' : 'none',
                }}
              >
                <span style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 13,
                    color: 'var(--text-primary)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {e.url}
                  </div>
                  <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-tertiary)' }}>
                    {countText}
                  </div>
                </span>
                <Badge variant={e.active ? 'success' : 'default'} size="sm" dot>
                  {e.active ? t('webhooks.status_active', 'Active') : t('webhooks.status_paused', 'Paused')}
                </Badge>
                <Button variant="ghost" size="sm" iconOnly icon={Trash2} aria-label={t('webhooks.remove_aria', 'Remove')} onClick={() => remove(e.id)} />
              </div>
            );
          })}
        </Card>
      )}
    </SectionContainer>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// 7. Cross-link cards — for sections that live as separate pages
// ─────────────────────────────────────────────────────────────────────────
export function CrossLinksSection({ user }) {
  const { t } = useTranslation('settings');
  const isStaff = user?.role === 'superadmin' || user?.role === 'staff';
  const base = isStaff ? '/admin' : '/dashboard';

  const LINKS = [
    { to: `${base}/management`, id: 'team', staffOnly: true, fallbackLabel: 'Team & permissions', fallbackDesc: 'Invite teammates, assign roles, override permissions.' },
    { to: `${base}/clients`,    id: 'workspaces', staffOnly: true, fallbackLabel: 'Workspaces (clients)', fallbackDesc: 'Manage every client account in your agency.' },
    { to: `${base}/analytics/audit-log`, id: 'audit_log', staffOnly: true, fallbackLabel: 'Audit log', fallbackDesc: 'Search every action across your account.' },
    { to: '/help',              id: 'help_center', staffOnly: false, fallbackLabel: 'Help center', fallbackDesc: 'Setup guides, troubleshooting, FAQs.' },
  ].filter((l) => !l.staffOnly || isStaff);

  return (
    <SectionContainer
      title={t('more.title', 'More settings')}
      description={t('more.subtitle', 'Some areas live as their own pages. Jump to them here.')}
    >
      <div style={{ display: 'grid', gap: 10 }}>
        {LINKS.map((l) => (
          <Link
            key={l.to}
            to={l.to}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
              padding: 16,
              background: 'var(--surface-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              boxShadow: 'var(--shadow-xs)',
              textDecoration: 'none',
              transition: 'var(--transition-fast)',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--border-default)'; e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = 'var(--shadow-sm)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border-subtle)'; e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'var(--shadow-xs)'; }}
          >
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{t(`more.links.${l.id}.label`, l.fallbackLabel)}</div>
              <div style={{ marginTop: 2, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{t(`more.links.${l.id}.desc`, l.fallbackDesc)}</div>
            </div>
            <ArrowRight size={14} style={{ color: 'var(--text-tertiary)', flexShrink: 0 }} />
          </Link>
        ))}
      </div>
    </SectionContainer>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Shared section container
// ─────────────────────────────────────────────────────────────────────────
function SectionContainer({ title, description, action, children }) {
  return (
    <div className="settings-section">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 4, flexWrap: 'wrap' }}>
        <h2 style={{
          margin: 0,
          fontSize: 20, fontWeight: 600,
          letterSpacing: '-0.015em',
          color: 'var(--text-primary)',
        }}>
          {title}
        </h2>
        {action}
      </div>
      <p style={{ margin: '4px 0 24px', fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.55 }}>
        {description}
      </p>
      {children}

      <style>{`
        .settings-section { padding: 32px 36px; }
        @media (max-width: 768px) {
          .settings-section { padding: 22px 18px; }
        }
      `}</style>
    </div>
  );
}
