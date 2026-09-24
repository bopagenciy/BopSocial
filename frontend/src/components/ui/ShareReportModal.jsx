/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { QRCodeSVG } from 'qrcode.react';
import { Link2, Copy, Check, X, Lock, Calendar, Layers, Clock, Share2, Trash2, Eye } from 'lucide-react';
import { sharedReportsAPI } from '../../services/api';
import { PLATFORMS } from '../../services/platforms';
import SocialPlatformIcon from './SocialPlatformIcon';
import { formatDate, formatDateRange } from '../../utils/formatters';

const ALL_PLATFORMS = Object.keys(PLATFORMS);

function buildShareUrl(report) {
  if (!report) return '';
  if (report.share_url) return report.share_url;
  if (report.token) return `${window.location.origin}/report/${report.token}`;
  return '';
}

function getApiError(error, fallback) {
  const data = error?.response?.data;
  if (!data) return fallback;
  if (typeof data === 'string') {
    // Don't show raw HTML error pages
    if (data.trim().startsWith('<')) return fallback;
    return data;
  }
  if (data.detail) return data.detail;
  if (data.error) return data.error;
  const firstValue = Object.values(data)[0];
  if (Array.isArray(firstValue)) return firstValue[0];
  if (typeof firstValue === 'string') return firstValue;
  return fallback;
}

function expiryToDatetime(val) {
  if (!val) return null;
  const now = new Date();
  if (val === '24h') now.setHours(now.getHours() + 24);
  if (val === '7d')  now.setDate(now.getDate() + 7);
  if (val === '30d') now.setDate(now.getDate() + 30);
  return now.toISOString();
}

export default function ShareReportModal({ clientId, onClose }) {
  const { t, i18n } = useTranslation('reports');
  const today      = new Date().toISOString().slice(0, 10);
  const monthStart = today.slice(0, 8) + '01';

  const [dateFrom,    setDateFrom]    = useState(monthStart);
  const [dateUntil,   setDateUntil]   = useState(today);
  const [platforms,   setPlatforms]   = useState(ALL_PLATFORMS);
  const [expiry,      setExpiry]      = useState('');
  const [usePassword, setUsePassword] = useState(false);
  const [password,    setPassword]    = useState('');
  const [creating,    setCreating]    = useState(false);
  const [error,       setError]       = useState('');
  const [shareUrl,    setShareUrl]    = useState('');
  const [copied,      setCopied]      = useState(false);

  const expiryOptions = useMemo(() => [
    { label: t('modal.expiry_never'), value: '' },
    { label: t('modal.expiry_24h'),   value: '24h' },
    { label: t('modal.expiry_7d'),    value: '7d' },
    { label: t('modal.expiry_30d'),   value: '30d' },
  ], [t]);

  // Existing links for this client
  const [links,      setLinks]      = useState([]);
  const [linksLoading, setLinksLoading] = useState(true);

  useEffect(() => {
    setLinksLoading(true);
    sharedReportsAPI.list({ client: clientId })
      .then(res => setLinks(res.data.results || res.data))
      .catch(() => {})
      .finally(() => setLinksLoading(false));
  }, [clientId]);

  function togglePlatform(p) {
    setPlatforms(prev =>
      prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]
    );
  }

  async function handleCreate() {
    if (!dateFrom || !dateUntil) { setError(t('modal.errors.date_range')); return; }
    if (platforms.length === 0)  { setError(t('modal.errors.platforms')); return; }
    if (usePassword && !password.trim()) { setError(t('modal.errors.password')); return; }
    setError('');
    setCreating(true);
    try {
      const payload = {
        client:     clientId,
        date_from:  dateFrom,
        date_until: dateUntil,
        platforms,
        expires_at: expiryToDatetime(expiry),
        password:   usePassword ? password : '',
      };
      const res = await sharedReportsAPI.create(payload);
      const created = res.data;
      const nextUrl = buildShareUrl(created);
      setShareUrl(nextUrl);
      setLinks(prev => [created, ...prev]);
    } catch (e) {
      setError(getApiError(e, t('modal.errors.create_failed')));
    } finally {
      setCreating(false);
    }
  }

  function copyUrl(url) {
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  async function deleteLink(id) {
    await sharedReportsAPI.delete(id);
    setLinks(prev => prev.filter(l => l.id !== id));
    if (shareUrl && links.find(l => l.id === id)?.share_url === shareUrl) {
      setShareUrl('');
    }
  }

  return (
    <div style={overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={modal}>
        {/* Header */}
        <div style={modalHeader}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Share2 size={18} style={{ color: '#6366f1' }} />
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
              {t('modal.title')}
            </h2>
          </div>
          <button onClick={onClose} style={closeBtn}><X size={18} /></button>
        </div>

        <div style={body}>
          {/* ── Create New Link ─────────────────────────── */}
          <section style={section}>
            <h3 style={sectionTitle}><Calendar size={14} /> {t('modal.date_range')}</h3>
            <div style={{ display: 'flex', gap: 10 }}>
              <input type="date" value={dateFrom}  onChange={e => setDateFrom(e.target.value)}  style={inputStyle} />
              <span style={{ alignSelf: 'center', color: 'var(--text-tertiary)' }}>→</span>
              <input type="date" value={dateUntil} onChange={e => setDateUntil(e.target.value)} style={inputStyle} />
            </div>
          </section>

          <section style={section}>
            <h3 style={sectionTitle}><Layers size={14} /> {t('modal.platforms')}</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {ALL_PLATFORMS.map(p => {
                const pl  = PLATFORMS[p];
                const sel = platforms.includes(p);
                return (
                  <button
                    key={p}
                    onClick={() => togglePlatform(p)}
                    style={{
                      ...platformChip,
                      background: sel ? (pl?.bg || '#f0f4ff')  : '#f8fafc',
                      color:      sel ? (pl?.color || '#6366f1') : '#64748b',
                      borderColor: sel ? (pl?.color || '#6366f1') : '#e5e7eb',
                    }}
                  >
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                      <SocialPlatformIcon platform={p} size={14} />
                      {pl?.label || p}
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          <section style={section}>
            <h3 style={sectionTitle}><Clock size={14} /> {t('modal.expiry')}</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              {expiryOptions.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setExpiry(opt.value)}
                  style={{
                    ...expiryChip,
                    background:  expiry === opt.value ? '#6366f1' : '#f8fafc',
                    color:       expiry === opt.value ? '#fff'     : '#64748b',
                    borderColor: expiry === opt.value ? '#6366f1'  : '#e5e7eb',
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </section>

          <section style={section}>
            <h3 style={sectionTitle}><Lock size={14} /> {t('modal.password_protection')}</h3>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13 }}>
              <input
                type="checkbox"
                checked={usePassword}
                onChange={e => setUsePassword(e.target.checked)}
                style={{ accentColor: '#6366f1' }}
              />
              {t('modal.protect_with_password')}
            </label>
            {usePassword && (
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder={t('modal.enter_password')}
                style={{ ...inputStyle, marginTop: 8 }}
              />
            )}
          </section>

          {error && <p style={{ color: '#dc2626', fontSize: 13, margin: '0 0 12px' }}>{error}</p>}

          <button onClick={handleCreate} disabled={creating} style={createBtn}>
            <Link2 size={15} />
            {creating ? t('modal.creating') : t('modal.generate_link')}
          </button>

          {/* ── Generated URL + QR ──────────────────────── */}
          {shareUrl && (
            <div style={urlBox}>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 10 }}>
                {t('modal.url_hint')}
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 14 }}>
                <input readOnly value={shareUrl} style={{ ...inputStyle, flex: 1, fontSize: 12 }} />
                <button onClick={() => copyUrl(shareUrl)} style={copyBtn}>
                  {copied ? <Check size={15} style={{ color: '#16a34a' }} /> : <Copy size={15} />}
                  {copied ? t('modal.copied') : t('modal.copy')}
                </button>
                <a href={shareUrl} target="_blank" rel="noreferrer" style={openBtn}>
                  <Eye size={15} />
                  {t('modal.open')}
                </a>
              </div>
              <div style={{ display: 'flex', justifyContent: 'center' }}>
                <QRCodeSVG value={shareUrl} size={140} />
              </div>
            </div>
          )}
        </div>

        {/* ── Existing Links ───────────────────────────── */}
        {!linksLoading && links.length > 0 && (
          <div style={existingSection}>
            <h3 style={{ ...sectionTitle, marginBottom: 10 }}>
              <Link2 size={14} /> {t('modal.existing_links')}
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {links.map(link => (
                <div key={link.id} style={linkRow}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                      {formatDateRange(link.date_from, link.date_until, { dateStyle: 'medium' }, i18n?.language)}
                      {link.is_password_protected && (
                        <Lock size={10} style={{ marginLeft: 6, color: 'var(--text-tertiary)', verticalAlign: 'middle' }} />
                      )}
                      {link.is_expired && (
                        <span style={{ marginLeft: 6, fontSize: 10, color: '#dc2626', fontWeight: 700 }}>{t('shared_links.expired')}</span>
                      )}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)', display: 'flex', gap: 10 }}>
                      <span>
                        <Eye size={10} style={{ verticalAlign: 'middle' }} />{' '}
                        {t(link.view_count === 1 ? 'shared_links.views_count_one' : 'shared_links.views_count_other', { count: link.view_count })}
                      </span>
                      {link.expires_at && <span>{t('shared_links.expires_at', { date: formatDate(link.expires_at, { dateStyle: 'medium' }, i18n?.language) })}</span>}
                    </div>
                  </div>
                  <a href={buildShareUrl(link)} target="_blank" rel="noreferrer" style={iconBtn} title={t('shared_links.open_report')}>
                    <Eye size={14} />
                  </a>
                  <button onClick={() => copyUrl(buildShareUrl(link))} style={iconBtn} title={t('shared_links.copy_link')}>
                    <Copy size={14} />
                  </button>
                  <button onClick={() => deleteLink(link.id)} style={{ ...iconBtn, color: '#ef4444' }} title={t('shared_links.deactivate')}>
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────
const overlay = {
  position: 'fixed', inset: 0, background: 'var(--overlay-backdrop)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 1000, padding: 16,
};
const modal = {
  background: 'var(--surface-card)', borderRadius: 16, width: '100%', maxWidth: 520,
  maxHeight: '90vh', overflow: 'hidden', display: 'flex', flexDirection: 'column',
  boxShadow: 'var(--shadow-xl)',
};
const modalHeader = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  padding: '18px 20px', borderBottom: '1px solid var(--border-subtle)',
};
const closeBtn = {
  background: 'none', border: 'none', cursor: 'pointer',
  color: 'var(--text-tertiary)', padding: 4, display: 'flex',
};
const body = {
  padding: '18px 20px', overflowY: 'auto', flex: 1,
};
const section     = { marginBottom: 18 };
const sectionTitle = {
  display: 'flex', alignItems: 'center', gap: 6,
  fontSize: 12, fontWeight: 700, color: 'var(--text-tertiary)',
  textTransform: 'uppercase', letterSpacing: .5, marginBottom: 8,
};
const inputStyle = {
  padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border-default)',
  fontSize: 13, color: 'var(--text-primary)', outline: 'none', background: 'var(--surface-sunken)',
  width: '100%', boxSizing: 'border-box',
};
const platformChip = {
  padding: '5px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600,
  border: '1.5px solid', cursor: 'pointer', transition: 'all .15s',
};
const expiryChip = {
  padding: '5px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600,
  border: '1.5px solid', cursor: 'pointer', transition: 'all .15s',
};
const createBtn = {
  display: 'flex', alignItems: 'center', gap: 8, width: '100%',
  justifyContent: 'center', padding: '10px 0',
  background: '#6366f1', color: '#fff', border: 'none',
  borderRadius: 10, fontSize: 14, fontWeight: 700, cursor: 'pointer',
  marginBottom: 16,
};
const urlBox = {
  background: 'var(--surface-sunken)', borderRadius: 12, padding: 16,
  border: '1px solid var(--border-default)', marginBottom: 8,
};
const copyBtn = {
  display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px',
  background: 'var(--surface-sunken)', border: '1px solid var(--border-default)', borderRadius: 8,
  fontSize: 13, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap', color: '#374151',
};
const openBtn = {
  display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px',
  background: '#6366f1', border: '1px solid #6366f1', borderRadius: 8,
  fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', color: '#fff', textDecoration: 'none',
};
const existingSection = {
  padding: '16px 20px', borderTop: '1px solid var(--border-subtle)', background: 'var(--surface-page)',
};
const linkRow = {
  display: 'flex', alignItems: 'center', gap: 8,
  background: 'var(--surface-card)', borderRadius: 10, padding: '10px 12px',
  border: '1px solid var(--border-default)',
};
const iconBtn = {
  background: 'none', border: 'none', cursor: 'pointer',
  color: 'var(--text-tertiary)', padding: 4, display: 'flex', flexShrink: 0, textDecoration: 'none',
};
