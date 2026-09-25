/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
/**
 * BrandVoicePage — train + preview the client's brand voice profile.
 *
 * Workflow:
 *   1. User pastes 3-20 sample posts (one per textarea row)
 *   2. Optional: business hint + industry
 *   3. Click "Train" → calls /ai/v2/brand-voice/train/
 *   4. Profile renders: persona summary, tone, vocabulary, audience, etc.
 *   5. Test prompt input → calls /ai/v2/brand-voice/test/ to render a sample post
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Sparkles, Wand2, RefreshCw, CheckCircle, AlertTriangle, Plus, Trash2,
  Mic, Smile, Hash, Users, Ban,
} from 'lucide-react';

import PageHeader from '../../components/layout/PageHeader';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import EmptyState from '../../components/ui/EmptyState';
import Spinner from '../../components/ui/Spinner';
import { aiV2API } from '../../services/api';
import { useAuth } from '../../hooks/useAuth';
import toast from '../../components/ui/toast';

const STATUS_VARIANT = {
  pending:  { variant: 'default', label: 'Not trained yet' },
  training: { variant: 'warning', label: 'Training…' },
  ready:    { variant: 'success', label: 'Ready' },
  failed:   { variant: 'danger',  label: 'Training failed' },
};

const EMOJI_LABEL = {
  heavy: '✨ Heavy emoji', moderate: '🙂 Moderate', minimal: 'Minimal', none: 'No emojis',
};

export default function BrandVoicePage({ clientId: propClientId = null }) {
  const { t } = useTranslation('ai');
  const { user } = useAuth();
  const isAdmin = user?.role === 'superadmin' || user?.role === 'staff';
  const clientId = propClientId || user?.client_id || null;

  const [profile, setProfile] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(true);

  // Training form
  const [samples, setSamples] = useState(['', '', '']);
  const [businessHint, setBusinessHint] = useState('');
  const [industry, setIndustry] = useState('');
  const [training, setTraining] = useState(false);
  const [examplePosts, setExamplePosts] = useState([]);

  // Test prompt
  const [testTopic, setTestTopic] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  // Load profile
  useEffect(() => {
    if (!clientId) { setLoadingProfile(false); return; }
    aiV2API.brandVoiceGet({ client_id: clientId })
      .then((r) => {
        setProfile(r.data);
        if (r.data?.sample_count > 0 && r.data?.training_status === 'ready') {
          // Pre-fill samples textarea is intentionally left empty so users
          // re-paste fresh samples on retraining.
        }
      })
      .catch(() => setProfile(null))
      .finally(() => setLoadingProfile(false));
  }, [clientId]);

  function addSampleRow() {
    if (samples.length >= 20) return;
    setSamples((s) => [...s, '']);
  }
  function removeSampleRow(i) {
    setSamples((s) => s.filter((_, idx) => idx !== i));
  }
  function updateSample(i, value) {
    setSamples((s) => s.map((v, idx) => (idx === i ? value : v)));
  }

  async function handleTrain() {
    const cleaned = samples.map((s) => (s || '').trim()).filter(Boolean);
    if (cleaned.length < 3) {
      toast.error(t('brand_voice.train_card.validation_min_samples', 'Add at least 3 sample posts (or paste one per row)'));
      return;
    }
    if (!clientId) {
      toast.error(t('assistant.chat.pick_client', 'Pick a client first'));
      return;
    }
    setTraining(true);
    setExamplePosts([]);
    try {
      const r = await aiV2API.brandVoiceTrain({
        client_id:     clientId,
        sample_posts:  cleaned,
        business_hint: businessHint.trim() || undefined,
        industry:      industry.trim() || undefined,
      });
      setProfile(r.data);
      setExamplePosts(r.data?.example_posts || []);
      toast.success(t('brand_voice.train_card.success_trained', 'Brand voice trained'));
    } catch (e) {
      const msg = e?.response?.data?.error || t('brand_voice.train_card.failed_train', 'Training failed');
      toast.error(msg);
    } finally {
      setTraining(false);
    }
  }

  async function handleTest() {
    const tTopic = testTopic.trim();
    if (!tTopic) { toast.error(t('brand_voice.test_card.validation_topic', 'Add a topic to test')); return; }
    if (!clientId) { toast.error(t('assistant.chat.pick_client', 'Pick a client first')); return; }
    setTesting(true);
    setTestResult(null);
    try {
      const r = await aiV2API.brandVoiceTest({
        client_id: clientId,
        topic:     tTopic,
        platform:  'instagram',
      });
      setTestResult(r.data);
    } catch (e) {
      const msg = e?.response?.data?.error || t('brand_voice.test_card.failed_test', 'Test failed');
      toast.error(msg);
    } finally {
      setTesting(false);
    }
  }

  if (!clientId && isAdmin) {
    return (
      <div className="app-page app-page--lg">
        <PageHeader title={t('brand_voice.title', 'Brand Voice')} subtitle={t('brand_voice.pick_client_desc', 'Brand voice is per-client. Open a specific client to train its voice.')} />
        <Card padding="lg">
          <EmptyState
            icon={Mic}
            title={t('brand_voice.pick_client_title', 'Pick a client')}
            description={t('brand_voice.pick_client_desc', 'Brand voice is per-client. Open a specific client to train its voice.')}
          />
        </Card>
      </div>
    );
  }

  const statusKey = profile?.training_status || 'pending';
  const statusInfo = STATUS_VARIANT[statusKey] || STATUS_VARIANT.pending;
  const statusLabel = t(`brand_voice.status.${statusKey}`, statusInfo.label);
  const trained = profile?.training_status === 'ready';

  return (
    <div className="app-page app-page--lg">
      <PageHeader
        title={t('brand_voice.title', 'Brand Voice')}
        subtitle={t('brand_voice.subtitle', 'Train Bop Social on your past posts so every generation sounds like you')}
        actions={(
          <Badge variant={statusInfo.variant} size="md" icon={trained ? CheckCircle : Sparkles}>
            {statusLabel}
          </Badge>
        )}
      />

      <div className="brand-voice-grid" style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
        gap: 20,
      }}>
        {/* ── LEFT — training inputs ─────────────────────────────────── */}
        <Card padding="md">
          <Card.Header
            title={t('brand_voice.train_card.title', 'Train from sample posts')}
            subtitle={t('brand_voice.train_card.subtitle', 'Paste 3-20 of your most-on-brand posts. Older + recent welcome.')}
          />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {samples.map((s, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                <textarea
                  value={s}
                  onChange={(e) => updateSample(i, e.target.value)}
                  placeholder={t('brand_voice.train_card.sample_placeholder', { number: i + 1, defaultValue: `Sample post ${i + 1}…` })}
                  rows={3}
                  style={{
                    flex: 1, minHeight: 64,
                    padding: '8px 10px',
                    background: 'var(--surface-card)',
                    border: '1px solid var(--border-default)',
                    borderRadius: 'var(--radius-sm)',
                    fontFamily: 'inherit', fontSize: 13,
                    color: 'var(--text-primary)',
                    resize: 'vertical', outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
                {samples.length > 3 && (
                  <Button
                    variant="ghost" size="sm" iconOnly icon={Trash2}
                    aria-label={t('brand_voice.train_card.remove_sample', 'Remove sample')}
                    onClick={() => removeSampleRow(i)}
                  />
                )}
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
            <Button
              variant="secondary" size="sm" icon={Plus}
              onClick={addSampleRow}
              disabled={samples.length >= 20}
            >
              {t('brand_voice.train_card.add_sample', 'Add sample')}
            </Button>
            <span style={{ alignSelf: 'center', fontSize: 12, color: 'var(--text-tertiary)' }}>
              {t('brand_voice.train_card.sample_counter', { count: samples.filter((s) => (s || '').trim()).length, defaultValue: `${samples.filter((s) => (s || '').trim()).length} / 20 samples` })}
            </span>
          </div>

          <div style={{
            marginTop: 16,
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 10,
          }} className="brand-voice-meta">
            <input
              value={businessHint}
              onChange={(e) => setBusinessHint(e.target.value)}
              placeholder={t('brand_voice.train_card.business_hint_placeholder', 'Business in 1 line (optional)')}
              style={inputStyle}
            />
            <input
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              placeholder={t('brand_voice.train_card.industry_placeholder', 'Industry (optional)')}
              style={inputStyle}
            />
          </div>

          <Button
            onClick={handleTrain}
            size="lg" icon={Wand2} fullWidth loading={training}
            style={{ marginTop: 16 }}
          >
            {training ? t('brand_voice.studying', 'Bop Social is studying your voice…') : (trained ? t('brand_voice.train_card.btn_retrain', 'Re-train brand voice') : t('brand_voice.train_card.btn_train', 'Train brand voice'))}
          </Button>

          {profile?.training_status === 'failed' && profile.training_error && (
            <div role="alert" style={{
              marginTop: 12, padding: '10px 12px',
              background: 'var(--danger-bg)',
              border: '1px solid var(--danger)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--danger)',
              fontSize: 13, display: 'flex', alignItems: 'flex-start', gap: 8,
            }}>
              <AlertTriangle size={14} style={{ marginTop: 1, flexShrink: 0 }} />
              <div>
                <strong>{t('brand_voice.train_card.training_failed_prefix', 'Training failed:')}</strong> {profile.training_error}
              </div>
            </div>
          )}
        </Card>

        {/* ── RIGHT — extracted profile ─────────────────────────────── */}
        <Card padding="md">
          <Card.Header
            title={t('brand_voice.profile_card.title', 'Extracted profile')}
            subtitle={trained
              ? t('brand_voice.profile_card.subtitle_ready', { date: profile.last_trained_at ? new Date(profile.last_trained_at).toLocaleDateString() : '', defaultValue: `Last trained ${profile.last_trained_at ? new Date(profile.last_trained_at).toLocaleDateString() : ''}` })
              : t('brand_voice.profile_card.subtitle_empty', 'Train above to see your voice profile')}
          />

          {loadingProfile ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
              <Spinner size="md" />
            </div>
          ) : !trained ? (
            <EmptyState
              icon={Mic}
              title={t('brand_voice.profile_card.empty_title', 'No trained voice yet')}
              description={t('brand_voice.profile_card.empty_desc', 'Paste sample posts on the left and click Train. Your profile will appear here in seconds.')}
              compact
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {profile.voice_summary && (
                <ProfileBlock label={t('brand_voice.profile_card.persona', 'Persona')} body={profile.voice_summary} />
              )}

              {profile.tone_descriptors?.length > 0 && (
                <ChipBlock icon={Sparkles} label={t('brand_voice.profile_card.tone', 'Tone')} items={profile.tone_descriptors} />
              )}

              {profile.preferred_words?.length > 0 && (
                <ChipBlock icon={Wand2} label={t('brand_voice.profile_card.vocabulary', 'Vocabulary to favour')} items={profile.preferred_words} />
              )}

              {profile.forbidden_words?.length > 0 && (
                <ChipBlock icon={Ban} label={t('brand_voice.profile_card.avoid', 'Avoid')} items={profile.forbidden_words} accent="var(--danger)" />
              )}

              {profile.target_audience && (
                <ProfileBlock icon={Users} label={t('brand_voice.profile_card.audience', 'Target audience')} body={profile.target_audience} />
              )}

              {profile.prohibited_topics?.length > 0 && (
                <ChipBlock icon={Ban} label={t('brand_voice.profile_card.topics_avoid', 'Topics to avoid')} items={profile.prohibited_topics} accent="var(--warning)" />
              )}

              {profile.style_rules?.length > 0 && (
                <div>
                  <BlockLabel icon={Wand2} label={t('brand_voice.profile_card.style_rules', 'Style rules')} />
                  <ul style={{ margin: 0, paddingLeft: 22, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.55 }}>
                    {profile.style_rules.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
              )}

              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <SmallTag icon={Smile} text={t(`brand_voice.emoji.${profile.emoji_usage}`, EMOJI_LABEL[profile.emoji_usage] || profile.emoji_usage)} />
                {profile.hashtag_style && (
                  <SmallTag icon={Hash} text={t('brand_voice.profile_card.hashtags', { style: profile.hashtag_style, defaultValue: `Hashtags: ${profile.hashtag_style}` })} />
                )}
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* ── Validation example posts (after training) ─────────────────────── */}
      {examplePosts?.length > 0 && (
        <Card padding="md" style={{ marginTop: 20 }}>
          <Card.Header
            title={t('brand_voice.validation_examples.title', 'Validation examples')}
            subtitle={t('brand_voice.validation_examples.subtitle', 'Three short posts written in the just-trained voice — does this sound like you?')}
            action={(
              <Button variant="ghost" size="sm" icon={RefreshCw} onClick={handleTrain} loading={training}>
                {t('brand_voice.validation_examples.regenerate', 'Regenerate')}
              </Button>
            )}
          />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }} className="brand-voice-examples">
            {examplePosts.map((p, i) => (
              <div key={i} style={{
                padding: 14,
                background: 'var(--surface-sunken)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                fontSize: 13, lineHeight: 1.6,
                color: 'var(--text-primary)',
                whiteSpace: 'pre-wrap',
              }}>
                {p}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── Test the voice on a custom topic ──────────────────────────────── */}
      {trained && (
        <Card padding="md" style={{ marginTop: 20 }}>
          <Card.Header
            title={t('brand_voice.test_card.title', 'Test the voice')}
            subtitle={t('brand_voice.test_card.subtitle', 'Generate a sample post on any topic to spot-check the trained voice.')}
          />
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input
              value={testTopic}
              onChange={(e) => setTestTopic(e.target.value)}
              placeholder={t('brand_voice.test_card.placeholder', 'e.g. New summer collection, Diwali greetings…')}
              style={{ ...inputStyle, flex: '1 1 240px' }}
              onKeyDown={(e) => { if (e.key === 'Enter') handleTest(); }}
            />
            <Button onClick={handleTest} loading={testing} icon={Sparkles}>
              {t('brand_voice.test_card.btn_generate', 'Generate sample post')}
            </Button>
          </div>

          {testResult && (
            <div style={{
              marginTop: 14, padding: 14,
              background: 'var(--surface-sunken)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <Badge variant="brand" size="sm" icon={Sparkles}>
                  {testResult.voice_used ? t('brand_voice.test_card.badge_trained', 'In your trained voice') : t('brand_voice.test_card.badge_default', 'Default voice')}
                </Badge>
                <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                  {t('brand_voice.test_card.chars', { count: testResult.character_count, defaultValue: `${testResult.character_count} chars` })}
                </span>
              </div>
              <div style={{
                fontSize: 14, lineHeight: 1.6,
                color: 'var(--text-primary)',
                whiteSpace: 'pre-wrap',
              }}>
                {testResult.content}
              </div>
              {testResult.hashtags?.length > 0 && (
                <div style={{ marginTop: 10, fontSize: 13, color: 'var(--brand-primary-hover)' }}>
                  {testResult.hashtags.join(' ')}
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      <style>{`
        @media (max-width: 980px) {
          .brand-voice-grid     { grid-template-columns: 1fr !important; }
          .brand-voice-meta     { grid-template-columns: 1fr !important; }
          .brand-voice-examples { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}

function ProfileBlock({ icon: Icon, label, body }) {
  return (
    <div>
      <BlockLabel icon={Icon} label={label} />
      <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        {body}
      </p>
    </div>
  );
}

function ChipBlock({ icon, label, items, accent }) {
  return (
    <div>
      <BlockLabel icon={icon} label={label} />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
        {items.map((item, i) => (
          <span key={i} style={{
            display: 'inline-flex', alignItems: 'center',
            padding: '3px 9px',
            fontSize: 11, fontWeight: 500,
            color: accent || 'var(--text-secondary)',
            background: accent ? `${accent}1A` : 'var(--surface-sunken)',
            border: `1px solid ${accent || 'var(--border-subtle)'}`,
            borderRadius: 'var(--radius-pill)',
          }}>
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function BlockLabel({ icon: Icon, label }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6,
      fontSize: 11, fontWeight: 600,
      letterSpacing: '0.06em', textTransform: 'uppercase',
      color: 'var(--text-tertiary)',
    }}>
      {Icon ? <Icon size={11} /> : null}
      {label}
    </div>
  );
}

function SmallTag({ icon: Icon, text }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '4px 8px',
      background: 'var(--surface-card)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-pill)',
      fontSize: 11, fontWeight: 500,
      color: 'var(--text-secondary)',
    }}>
      {Icon ? <Icon size={11} /> : null}
      {text}
    </span>
  );
}

const inputStyle = {
  width: '100%', padding: '9px 12px',
  background: 'var(--surface-card)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-sm)',
  fontSize: 13, color: 'var(--text-primary)',
  fontFamily: 'inherit', outline: 'none',
  boxSizing: 'border-box',
};
