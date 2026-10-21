/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
/**
 * WriteReviewModal — submit (or edit) a review for an agency.
 *
 * Props:
 *   open        bool
 *   onClose     () => void
 *   agency      { name, slug }
 *   existing    optional existing review object (turns the modal into an editor)
 *   onSaved     callback fired with the saved review
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Send, X, Star, Plus } from 'lucide-react';

import StarRating from './StarRating';
import { reviewAPI } from '../../services/api';
import toast from '../ui/toast';


const SERVICE_OPTIONS = [
  'content', 'analytics', 'inbox', 'campaigns', 'ads', 'strategy',
];


export default function WriteReviewModal({ open, onClose, agency, existing, onSaved }) {
  const { t } = useTranslation('agency_portal');
  const [rating,  setRating]  = useState(existing?.rating || 0);
  const [title,   setTitle]   = useState(existing?.title || '');
  const [body,    setBody]    = useState(existing?.body || '');
  const [pros,    setPros]    = useState(existing?.pros || []);
  const [cons,    setCons]    = useState(existing?.cons || []);
  const [services,setServices]= useState(existing?.services_used || []);
  const [duration,setDuration]= useState(existing?.duration_months ?? '');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setRating(existing?.rating || 0);
    setTitle(existing?.title || '');
    setBody(existing?.body || '');
    setPros(existing?.pros || []);
    setCons(existing?.cons || []);
    setServices(existing?.services_used || []);
    setDuration(existing?.duration_months ?? '');
  }, [open, existing]);

  if (!open) return null;

  function toggleService(s) {
    setServices((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]);
  }

  async function submit() {
    if (rating < 1) return toast.error(t('reviews.err_pick_star', 'Pick a star rating'));
    if (!title.trim()) return toast.error(t('reviews.err_add_title', 'Add a short title'));
    if (!body.trim()) return toast.error(t('reviews.err_add_body', 'Tell others what working with them was like'));

    setBusy(true);
    try {
      const payload = {
        rating, title: title.trim(), body: body.trim(),
        pros: pros.filter(Boolean), cons: cons.filter(Boolean),
        services_used: services,
        duration_months: duration === '' ? null : Number(duration) || null,
      };
      const r = existing
        ? await reviewAPI.update(existing.id, payload)
        : await reviewAPI.create(agency.slug, payload);
      toast.success(existing ? t('reviews.toast_updated', 'Review updated') : t('reviews.toast_created', 'Review posted'));
      onSaved?.(r.data);
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.error || t('reviews.err_save', 'Could not save review'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-label={existing ? t('reviews.edit_title', 'Edit review') : t('reviews.write_title', 'Write a review')} style={backdropStyle} onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div style={modalStyle}>
        <header style={headerStyle}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-tertiary)' }}>
              {existing ? t('reviews.edit_title', 'Edit review') : t('reviews.write_title', 'Write a review')}
            </div>
            <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-primary)' }}>
              {agency.name}
            </div>
          </div>
          <button type="button" onClick={onClose} aria-label={t('common.close', 'Close')} style={iconBtn}><X size={16} /></button>
        </header>

        <div style={{ padding: '0 24px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <Label>{t('reviews.your_rating', 'Your rating')}</Label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <StarRating value={rating} onChange={setRating} size={24} />
              <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                {rating > 0 ? t('reviews.rating_n_of_5', '{{n}} of 5', { n: rating }) : t('reviews.tap_star', 'Tap a star')}
              </span>
            </div>
          </div>

          <div>
            <Label>{t('reviews.headline', 'Headline')}</Label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t('reviews.headline_placeholder', 'e.g., Brought our reach back to life')}
              maxLength={200}
              style={inputStyle}
            />
          </div>

          <div>
            <Label>{t('reviews.experience', 'Your experience')}</Label>
            <textarea
              rows={5}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={t('reviews.experience_placeholder', 'What did they do well? What were the results? Any caveats?')}
              style={textareaStyle}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <ListEditor label={t('reviews.pros', 'Pros')} values={pros} onChange={setPros} placeholder={t('reviews.list_placeholder', 'One per line')} tone="success" t={t} />
            <ListEditor label={t('reviews.cons', 'Cons')} values={cons} onChange={setCons} placeholder={t('reviews.list_placeholder', 'One per line')} tone="warning" t={t} />
          </div>

          <div>
            <Label>{t('reviews.services_used', 'Services used')}</Label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {SERVICE_OPTIONS.map((s) => {
                const active = services.includes(s);
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => toggleService(s)}
                    style={{
                      padding: '5px 12px',
                      fontSize: 12, fontWeight: active ? 600 : 500,
                      color: active ? 'var(--brand-primary-hover)' : 'var(--text-secondary)',
                      background: active ? 'var(--brand-primary-soft)' : 'var(--surface-card)',
                      border: `1px solid ${active ? 'var(--brand-primary)' : 'var(--border-default)'}`,
                      borderRadius: 'var(--radius-pill)',
                      cursor: 'pointer', fontFamily: 'inherit',
                    }}
                  >
                    {t(`reviews.services.${s}`, s)}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <Label>{t('reviews.duration_months', 'Working relationship duration (months)')}</Label>
            <input
              type="number"
              min={0} max={120}
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              placeholder="e.g., 4"
              style={{ ...inputStyle, maxWidth: 140 }}
            />
          </div>
        </div>

        <footer style={footerStyle}>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
            {t('reviews.public_notice', 'Reviews are public. You can edit yours within 30 days.')}
          </span>
          <button type="button" onClick={submit} disabled={busy} style={btnPrimary}>
            {busy ? t('reviews.saving', 'Saving…') : <>{existing ? t('reviews.update', 'Update review') : t('reviews.submit', 'Submit review')} <Send size={13} /></>}
          </button>
        </footer>
      </div>
    </div>
  );
}


function ListEditor({ label, values, onChange, placeholder, tone, t }) {
  const [draft, setDraft] = useState('');
  function add() {
    const v = draft.trim();
    if (!v) return;
    onChange([...values, v]);
    setDraft('');
  }
  function remove(i) {
    onChange(values.filter((_, idx) => idx !== i));
  }
  const chipColor = tone === 'success' ? 'var(--success)' : 'var(--warning)';
  return (
    <div>
      <Label>{label}</Label>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {values.map((v, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 8px', background: 'var(--surface-sunken)', borderLeft: `3px solid ${chipColor}`, borderRadius: 4, fontSize: 13 }}>
            <span style={{ flex: 1, color: 'var(--text-primary)' }}>{v}</span>
            <button type="button" onClick={() => remove(i)} aria-label={t ? t('common.remove', 'Remove') : 'Remove'} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', padding: 2 }}>
              <X size={11} />
            </button>
          </div>
        ))}
        <div style={{ display: 'flex', gap: 4 }}>
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { add(); e.preventDefault(); } }}
            placeholder={placeholder}
            style={{ ...inputStyle, padding: '6px 10px', fontSize: 12, flex: 1 }}
          />
          <button type="button" onClick={add} aria-label={`Add ${label.toLowerCase()}`} style={btnGhostMini}><Plus size={12} /></button>
        </div>
      </div>
    </div>
  );
}

function Label({ children }) {
  return (
    <label style={{
      display: 'block', fontSize: 11, fontWeight: 600,
      letterSpacing: '0.04em', textTransform: 'uppercase',
      color: 'var(--text-tertiary)', marginBottom: 4,
    }}>{children}</label>
  );
}

const backdropStyle = {
  position: 'fixed', inset: 0, zIndex: 1100,
  background: 'rgba(10,14,20,0.50)',
  backdropFilter: 'blur(2px)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  padding: 20,
};

const modalStyle = {
  width: '100%', maxWidth: 560, maxHeight: '90vh',
  display: 'flex', flexDirection: 'column',
  background: 'var(--surface-elevated)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-lg)',
  boxShadow: 'var(--shadow-xl)',
  overflow: 'hidden',
};

const headerStyle = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '16px 20px 8px',
  flexShrink: 0,
};

const footerStyle = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '14px 20px',
  borderTop: '1px solid var(--border-subtle)',
  background: 'var(--surface-card)',
  gap: 10,
  flexShrink: 0,
};

const inputStyle = {
  width: '100%', padding: '10px 12px',
  background: 'var(--surface-sunken)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-sm)',
  fontSize: 13, color: 'var(--text-primary)',
  outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box',
};
const textareaStyle = { ...inputStyle, resize: 'vertical', minHeight: 100 };

const btnPrimary = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '9px 16px',
  background: 'var(--brand-primary)', color: '#fff',
  border: 'none', borderRadius: 'var(--radius-md)',
  fontSize: 13, fontWeight: 600, fontFamily: 'inherit', cursor: 'pointer',
};

const btnGhostMini = {
  width: 30, height: 30, padding: 0,
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  background: 'transparent', color: 'var(--text-secondary)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-sm)',
  cursor: 'pointer',
};

const iconBtn = {
  width: 30, height: 30, padding: 0,
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  background: 'transparent', color: 'var(--text-tertiary)',
  border: 'none', borderRadius: 'var(--radius-sm)',
  cursor: 'pointer',
};
