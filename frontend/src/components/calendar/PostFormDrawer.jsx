/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useState, useEffect } from 'react';
import { isBefore } from 'date-fns';
import { X, AlertCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { PLATFORMS, PLATFORM_LIST } from '../../services/platforms';
import { useSuggestedTimes } from '../../hooks/useCalendar';
import { formatDate } from '../../utils/formatters';
import SocialPlatformIcon from '../ui/SocialPlatformIcon';

const CHAR_LIMITS = {
  facebook:          63206,
  instagram:         2200,
  linkedin:          3000,
  youtube:           5000,
  google_my_business:1500,
};

const POST_TYPES = [
  { value: 'image',    label: 'Image'    },
  { value: 'video',    label: 'Video'    },
  { value: 'reel',     label: 'Reel'     },
  { value: 'story',    label: 'Story'    },
  { value: 'carousel', label: 'Carousel' },
  { value: 'text',     label: 'Text'     },
  { value: 'article',  label: 'Article'  },
  { value: 'short',    label: 'Short'    },
];

const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

function getMinScheduleValue() {
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

function CharCounter({ text, limit }) {
  const count = (text || '').length;
  const pct   = count / limit;
  const color = pct > 0.95 ? '#EF4444' : pct > 0.80 ? '#F59E0B' : '#10B981';
  return (
    <div style={{ fontSize: 11, color, textAlign: 'right', marginTop: 2 }}>
      {count.toLocaleString()} / {limit.toLocaleString()}
    </div>
  );
}

function SuggestRow({ clientId, platform }) {
  const { t } = useTranslation('content');
  const { suggestions, source } = useSuggestedTimes(clientId, platform);
  if (!suggestions.length) return null;
  return (
    <div style={{
      background: '#EFF6FF', border: '1px solid #BFDBFE',
      borderRadius: 8, padding: '8px 12px', marginTop: 6, fontSize: 12,
    }}>
      <span style={{ color: '#2563EB', fontWeight: 600 }}>💡 {t('calendar.form.best_times_for', { platform: PLATFORMS[platform]?.label || platform })} </span>
      <span style={{ color: '#1e40af' }}>
        {suggestions.slice(0, 4).map(s => s.note || `${t(`calendar.weekdays.${DAY_KEYS[s.day_of_week]}`)} ${s.hour}:${String(s.minute||0).padStart(2,'0')}`).join(', ')}
      </span>
      {source === 'industry' && <span style={{ color: '#64748B' }}> ({t('calendar.form.industry', 'industry')})</span>}
    </div>
  );
}

export default function PostFormDrawer({ date, post, isOpen, onClose, onSave, clientId, readOnly }) {
  const { t } = useTranslation('content');
  const isEdit = !!post;

  const [platform,    setPlatform]    = useState(post?.platform    || 'instagram');
  const [postType,    setPostType]    = useState(post?.post_type   || 'image');
  const [title,       setTitle]       = useState(post?.title       || '');
  const [caption,     setCaption]     = useState(post?.caption     || '');
  const [hashtags,    setHashtags]    = useState(post?.hashtags    || '');
  const [mediaUrl,    setMediaUrl]    = useState(post?.media_url   || '');
  const [postUrl,     setPostUrl]     = useState(post?.post_url    || '');
  const [status,      setStatus]      = useState(post?.status === 'scheduled' ? 'scheduled' : 'draft');
  const [scheduledAt, setScheduledAt] = useState('');
  const [notes,       setNotes]       = useState(post?.notes       || '');
  const [saving,      setSaving]      = useState(false);
  const [errors,      setErrors]      = useState({});
  const [error,       setError]       = useState('');

  useEffect(() => {
    if (!isOpen) return;
    if (post) {
      setPlatform(post.platform || 'instagram');
      setPostType(post.post_type || 'image');
      setTitle(post.title || '');
      setCaption(post.caption || '');
      setHashtags(post.hashtags || '');
      setMediaUrl(post.media_url || '');
      setPostUrl(post.post_url || '');
      setStatus(post.status === 'scheduled' ? 'scheduled' : 'draft');
      setNotes(post.notes || '');
      if (post.scheduled_at) {
        // Convert to local datetime-local input format
        const d = new Date(post.scheduled_at);
        const pad = n => String(n).padStart(2, '0');
        setScheduledAt(
          `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
        );
      }
    } else {
      // New post — pre-fill date
      setPlatform('instagram');
      setPostType('image');
      setTitle('');
      setCaption('');
      setHashtags('');
      setMediaUrl('');
      setPostUrl('');
      setStatus('draft');
      setNotes('');
      if (date) {
        const d = date instanceof Date ? date : new Date(date);
        const pad = n => String(n).padStart(2, '0');
        setScheduledAt(
          `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T10:00`
        );
      } else {
        setScheduledAt('');
      }
    }
    setError('');
    setErrors({});
    setSaving(false);
  }, [isOpen, post, date]);

  const charLimit = CHAR_LIMITS[platform] || 2200;
  const hashCount = hashtags.trim().split(/\s+/).filter(t => t.startsWith('#')).length;

  const clearFieldError = (field) => {
    setErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  };

  const validateForm = (finalStatus) => {
    const nextErrors = {};
    if (!platform) {
      nextErrors.platform = t('calendar.form.validation.platform_required', 'Please select a platform.');
    }
    if (!caption.trim() && !title.trim()) {
      nextErrors.caption = t('calendar.form.validation.caption_required', 'Caption is required. Add a caption or at least an internal title.');
    }
    if (finalStatus === 'scheduled' && !scheduledAt) {
      nextErrors.scheduledAt = t('calendar.form.validation.datetime_required', 'Please pick a date and time to schedule this post.');
    }
    if (finalStatus === 'scheduled' && scheduledAt && isBefore(new Date(scheduledAt), new Date())) {
      nextErrors.scheduledAt = t('calendar.form.validation.future_datetime', 'The scheduled time must be in the future.');
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  async function handleSave(forcedStatus) {
    setError('');
    const finalStatus = forcedStatus || status;

    // Auto-reveal the datetime picker when "Schedule Post" is clicked
    if (finalStatus === 'scheduled') {
      setStatus('scheduled');
    }

    if (!validateForm(finalStatus)) {
      // Build a specific summary of what's missing
      const missing = [];
      if (!platform) missing.push(t('calendar.form.platform', 'Platform'));
      if (!caption.trim() && !title.trim()) missing.push(t('calendar.form.caption', 'Caption'));
      if (finalStatus === 'scheduled' && !scheduledAt) missing.push(t('calendar.form.schedule_datetime', 'Scheduled Date & Time'));
      if (finalStatus === 'scheduled' && scheduledAt && isBefore(new Date(scheduledAt), new Date())) {
        missing.push(`${t('calendar.form.schedule_datetime', 'Scheduled Date & Time')} (${t('calendar.form.validation.future_datetime', 'must be in the future')})`);
      }
      setError(
        missing.length > 0
          ? t('calendar.form.validation.missing_fields', {
              plural: missing.length > 1 ? 's' : '',
              fields: missing.join(', '),
              defaultValue: `Required field(s) missing: ${missing.join(', ')}.`
            })
          : t('calendar.form.validation.fix_highlighted', 'Please fix the highlighted fields before saving.')
      );
      return;
    }

    setSaving(true);
    const payload = {
      platform, post_type: postType,
      title, caption, hashtags,
      media_url: mediaUrl, post_url: postUrl,
      status: finalStatus,
      notes,
    };
    if (finalStatus === 'scheduled' && scheduledAt) {
      payload.scheduled_at = new Date(scheduledAt).toISOString();
    }
    if (!isEdit && clientId) {
      payload.client = clientId;
    }

    const result = await onSave(payload, post?.id);
    setSaving(false);
    if (result?.success === false) {
      setError(result.error || t('calendar.form.validation.save_failed', 'Save failed.'));
    }
  }

  const plat = PLATFORMS[platform] || { color: '#64748B', label: platform };

  return (
    <>
      {/* Overlay */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'var(--overlay-backdrop)', zIndex: 1000,
          opacity: isOpen ? 1 : 0,
          transition: 'opacity 0.25s',
          pointerEvents: isOpen ? 'auto' : 'none',
        }}
      />

      {/* Drawer */}
      <div style={{
        position:  'fixed', top: 0, right: 0, bottom: 0,
        width:     460,
        background:'#fff',
        boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
        zIndex:    1001,
        transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
        transition:'transform 0.25s ease-out',
        display:   'flex', flexDirection: 'column',
        overflowY: 'auto',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px', borderBottom: '1px solid #E2E8F0',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          position: 'sticky', top: 0, background: '#fff', zIndex: 1,
        }}>
          <div style={{ fontWeight: 700, fontSize: 16, color: '#0f172a' }}>
            {isEdit ? t('calendar.form.edit_post', 'Edit Post') : t('calendar.form.schedule_button', 'Schedule Post')}
          </div>
          {date && !isEdit && (
            <div style={{ fontSize: 12, color: '#64748B' }}>
              {formatDate(date instanceof Date ? date : new Date(date), { weekday: 'long', month: 'long', day: 'numeric' })}
            </div>
          )}
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748B' }}>
            <X size={20} />
          </button>
        </div>

        {/* Form */}
        <div style={{ padding: '20px', flex: 1 }}>
          {/* Platform selector */}
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>{t('calendar.form.platform', 'Platform')} <span style={requiredAsteriskStyle}>*</span></label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {PLATFORM_LIST.map(key => {
                const p = PLATFORMS[key];
                const active = platform === key;
                return (
                  <button
                    key={key}
                    onClick={() => setPlatform(key)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 5,
                      padding: '6px 12px', borderRadius: 8,
                      background: active ? p.color : '#F1F5F9',
                      color:      active ? '#fff'   : '#475569',
                      border:     errors.platform
                        ? '1px solid #ef4444'
                        : (active ? `1px solid ${p.color}` : '1px solid #E2E8F0'),
                      cursor:     'pointer', fontSize: 12, fontWeight: 600,
                      transition: 'all 0.15s',
                    }}
                  >
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                      <SocialPlatformIcon platform={key} size={14} />
                      {p.label.split(' ')[0]}
                    </span>
                  </button>
                );
              })}
            </div>
            {errors.platform && <div style={fieldErrorStyle}>{errors.platform}</div>}
          </div>

          {/* Post Type */}
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>{t('calendar.form.post_type', 'Post Type')}</label>
            <select
              value={postType}
              onChange={e => setPostType(e.target.value)}
              style={inputStyle}
            >
              {POST_TYPES.map(typeItem => (
                <option key={typeItem.value} value={typeItem.value}>
                  {t(`calendar.form.post_types.${typeItem.value}`, typeItem.label)}
                </option>
              ))}
            </select>
          </div>

          {/* Title */}
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>{t('calendar.form.title', 'Internal Title')}</label>
            <input
              type="text"
              value={title}
              onChange={e => {
                setTitle(e.target.value);
                clearFieldError('caption');
              }}
              placeholder={t('calendar.form.title_placeholder', 'Agency reference label')}
              style={inputStyle}
            />
          </div>

          {/* Caption */}
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>{t('calendar.form.caption', 'Caption')} <span style={requiredAsteriskStyle}>*</span></label>
            <textarea
              value={caption}
              onChange={e => {
                setCaption(e.target.value);
                clearFieldError('caption');
              }}
              placeholder={t('calendar.form.caption_placeholder', { platform: plat.label, defaultValue: `Write your ${plat.label} caption…` })}
              rows={5}
              style={{ ...inputStyle, ...(errors.caption ? inputErrorStyle : {}), resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.5 }}
            />
            {errors.caption && <div style={fieldErrorStyle}>{errors.caption}</div>}
            <CharCounter text={caption} limit={charLimit} />
          </div>

          {/* Hashtags */}
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>
              {t('calendar.form.hashtags', 'Hashtags')}
              {hashCount > 0 && (
                <span style={{ marginLeft: 8, fontWeight: 400, color: '#64748B' }}>
                  {t('calendar.hashtags_count', { count: hashCount, defaultValue: `${hashCount} hashtags` })}
                </span>
              )}
            </label>
            <input
              type="text"
              value={hashtags}
              onChange={e => setHashtags(e.target.value)}
              placeholder={t('calendar.form.hashtags_placeholder', '#socialmedia #marketing')}
              style={inputStyle}
            />
          </div>

          {/* Media URL */}
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>{t('calendar.form.media_url', 'Media URL (optional)')}</label>
            <input
              type="url"
              value={mediaUrl}
              onChange={e => setMediaUrl(e.target.value)}
              placeholder="https://…"
              style={inputStyle}
            />
          </div>

          {/* Post URL */}
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>{t('calendar.form.post_url', 'Post URL (optional)')}</label>
            <input
              type="url"
              value={postUrl}
              onChange={e => setPostUrl(e.target.value)}
              placeholder="https://…"
              style={inputStyle}
            />
          </div>

          {/* Status */}
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>{t('calendar.form.status', 'Status')}</label>
            <div style={{ display: 'flex', gap: 8 }}>
              {['draft', 'scheduled'].map(s => (
                <button
                  key={s}
                  onClick={() => setStatus(s)}
                  style={{
                    flex: 1, padding: '8px', borderRadius: 8,
                    background: status === s ? (s === 'scheduled' ? '#2563EB' : '#F1F5F9') : '#F8FAFC',
                    color:      status === s ? (s === 'scheduled' ? '#fff'   : '#374151') : '#94A3B8',
                    border:     status === s ? `1px solid ${s === 'scheduled' ? '#2563EB' : '#CBD5E1'}` : '1px solid #E2E8F0',
                    cursor: 'pointer', fontSize: 13, fontWeight: 600,
                  }}
                >
                  {t(`status.${s}`, s)}
                </button>
              ))}
            </div>
          </div>

          {/* DateTime picker */}
          {status === 'scheduled' && (
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>{t('calendar.form.schedule_datetime', 'Scheduled Date & Time')} <span style={requiredAsteriskStyle}>*</span></label>
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={e => {
                  setScheduledAt(e.target.value);
                  clearFieldError('scheduledAt');
                }}
                min={getMinScheduleValue()}
                style={{ ...inputStyle, ...(errors.scheduledAt ? inputErrorStyle : {}) }}
              />
              {errors.scheduledAt && <div style={fieldErrorStyle}>{errors.scheduledAt}</div>}
              {clientId && (
                <SuggestRow clientId={clientId} platform={platform} />
              )}
            </div>
          )}

          {/* Agency notes */}
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>{t('calendar.form.notes', 'Internal Notes (not shown to user)')}</label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder={t('calendar.form.notes_placeholder', 'e.g. Waiting on final image from designer')}
              rows={2}
              style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }}
            />
          </div>

          {/* Error */}
          {error && (
            <div style={{
              display: 'flex', alignItems: 'flex-start', gap: 10,
              background: '#FEF2F2', border: '1px solid #FECACA',
              borderRadius: 8, padding: '12px 14px',
              color: '#B91C1C', fontSize: 13, marginBottom: 12, lineHeight: 1.5,
            }}>
              <AlertCircle size={16} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        {!readOnly && (
          <div style={{
            padding: '14px 20px', borderTop: '1px solid #E2E8F0',
            display: 'flex', gap: 8,
            position: 'sticky', bottom: 0, background: '#fff', zIndex: 1,
          }}>
            <button
              onClick={() => handleSave('draft')}
              disabled={saving}
              style={{
                flex: 1, padding: '10px', borderRadius: 8,
                background: '#F1F5F9', border: '1px solid #E2E8F0',
                color: '#374151', cursor: 'pointer', fontSize: 13, fontWeight: 600,
                opacity: saving ? 0.6 : 1,
              }}
            >
              {t('calendar.form.save_as_draft', 'Save as Draft')}
            </button>
            <button
              onClick={() => handleSave('scheduled')}
              disabled={saving}
              style={{
                flex: 1, padding: '10px', borderRadius: 8,
                background: '#2563EB', color: '#fff',
                border: 'none', cursor: saving ? 'not-allowed' : 'pointer',
                fontSize: 13, fontWeight: 600,
                opacity: saving ? 0.6 : 1,
              }}
            >
              {saving ? t('calendar.form.saving', 'Saving…') : (isEdit ? t('calendar.form.update_button', 'Update Post') : t('calendar.form.schedule_button', 'Schedule Post'))}
            </button>
          </div>
        )}
      </div>
    </>
  );
}

const labelStyle = {
  display: 'block', fontSize: 12, fontWeight: 600,
  color: '#374151', marginBottom: 6,
};

const requiredAsteriskStyle = {
  color: '#ef4444', marginLeft: 2, fontWeight: 800,
};

const inputStyle = {
  width: '100%', padding: '9px 11px', borderRadius: 8,
  border: '1px solid #D1D5DB', fontSize: 13,
  boxSizing: 'border-box', background: '#fff',
  outline: 'none', color: '#1e293b',
};

const inputErrorStyle = {
  borderColor: '#ef4444',
  background: '#fef2f2',
};

const fieldErrorStyle = {
  marginTop: 6,
  fontSize: 12,
  color: '#dc2626',
};
