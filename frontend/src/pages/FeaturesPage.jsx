/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import {
  BarChart3, PenSquare, Inbox, Sparkles, Zap, FileText, Users, ShieldCheck,
  ArrowRight, Check,
} from 'lucide-react';

import MarketingLayout from '../components/marketing/MarketingLayout';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import Meta from '../components/Meta';

export default function FeaturesPage() {
  const { t } = useTranslation(['marketing', 'navigation']);

  const features = useMemo(() => [
    {
      id: 'analytics',
      icon: BarChart3,
      color: 'var(--module-analytics)',
      eyebrow: t('navigation:products.analytics', 'Analytics'),
      title: t('features.items.analytics.title', 'Cross-platform metrics, unified.'),
      body: t('features.items.analytics.body', 'Pull Facebook, Instagram, YouTube, LinkedIn, GMB, X, and more into a single live dashboard. Drill into any post, any platform, any window — without spreadsheets.'),
      bullets: [
        t('features.items.analytics.b1', 'Real-time follower, engagement, and reach metrics'),
        t('features.items.analytics.b2', 'Custom date ranges with on-the-fly comparisons'),
        t('features.items.analytics.b3', 'Per-platform breakdowns and aggregate views'),
        t('features.items.analytics.b4', 'White-label PDF exports for clients'),
      ],
    },
    {
      id: 'composer',
      icon: PenSquare,
      color: '#8b5cf6',
      eyebrow: t('navigation:products.composer', 'Composer'),
      title: t('features.items.composer.title', 'Write once. Publish everywhere.'),
      body: t('features.items.composer.body', 'Compose a single post and tailor it per platform inline. Attach assets from the media library, schedule into queues, or publish immediately.'),
      bullets: [
        t('features.items.composer.b1', 'Per-platform overrides without rewriting'),
        t('features.items.composer.b2', 'Smart scheduling with timezone-aware queues'),
        t('features.items.composer.b3', 'Approval gates before publish'),
        t('features.items.composer.b4', 'Built-in media library + asset transformations'),
      ],
    },
    {
      id: 'inbox',
      icon: Inbox,
      color: 'var(--module-messaging)',
      eyebrow: t('navigation:products.inbox', 'Inbox'),
      title: t('features.items.inbox.title', 'Every reply in one timeline.'),
      body: t('features.items.inbox.body', 'Comments, DMs, mentions, reviews, and WhatsApp messages — all merged into one unified inbox with sentiment tagging and AI-suggested replies.'),
      bullets: [
        t('features.items.inbox.b1', 'Cross-platform conversation threads'),
        t('features.items.inbox.b2', 'Sentiment + intent tagging out of the box'),
        t('features.items.inbox.b3', 'AI reply suggestions in your brand voice'),
        t('features.items.inbox.b4', 'Assign, snooze, and resolve workflows'),
      ],
    },
    {
      id: 'ai',
      icon: Sparkles,
      color: 'var(--module-ai)',
      eyebrow: t('navigation:products.ai_studio', 'AI'),
      title: t('features.items.ai.title', 'AI that knows your brand voice.'),
      body: t('features.items.ai.body', 'Upload sample posts to train a private brand voice profile. Generate captions, hashtags, replies, and predictions — every output carries your tone.'),
      bullets: [
        t('features.items.ai.b1', 'Caption generation in your tone'),
        t('features.items.ai.b2', 'Hashtag research with engagement scoring'),
        t('features.items.ai.b3', 'Best-time-to-post predictions'),
        t('features.items.ai.b4', 'Auto-summaries of weekly performance'),
      ],
    },
    {
      id: 'automations',
      icon: Zap,
      color: '#f59e0b',
      eyebrow: t('navigation:products.automations', 'Automations'),
      title: t('features.items.automations.title', 'Smart automations, no code.'),
      body: t('features.items.automations.body', 'Trigger actions on schedule, sentiment, or keywords. Auto-reply to FAQs, escalate negative reviews, and notify the right human at the right moment.'),
      bullets: [
        t('features.items.automations.b1', 'Visual rule builder — no code'),
        t('features.items.automations.b2', 'Trigger on schedule, keyword, or sentiment'),
        t('features.items.automations.b3', 'Built-in connectors to Slack, email, WhatsApp'),
        t('features.items.automations.b4', 'Run history with full audit trail'),
      ],
    },
    {
      id: 'reports',
      icon: FileText,
      color: '#3b82f6',
      eyebrow: t('navigation:products.reports', 'Reports'),
      title: t('features.items.reports.title', 'Polished reports clients love.'),
      body: t('features.items.reports.body', 'Generate beautiful, white-labelled performance reports in minutes. Schedule weekly or monthly delivery, share via secure links, or export to PDF.'),
      bullets: [
        t('features.items.reports.b1', 'Branded PDF and shareable web links'),
        t('features.items.reports.b2', 'Auto-scheduled delivery cadence'),
        t('features.items.reports.b3', 'Drag-and-drop section ordering'),
        t('features.items.reports.b4', 'AI-generated executive summary'),
      ],
    },
    {
      id: 'team',
      icon: Users,
      color: '#10b981',
      eyebrow: t('navigation:products.for_agencies', 'Team'),
      title: t('features.items.team.title', 'Granular collaboration controls.'),
      body: t('features.items.team.body', 'Invite teammates, assign clients, scope permissions per page or action. Approval workflows keep brand integrity tight without slowing you down.'),
      bullets: [
        t('features.items.team.b1', 'Role-based + per-user permission overrides'),
        t('features.items.team.b2', 'Multi-client workspace assignments'),
        t('features.items.team.b3', 'Approval chains with comment threads'),
        t('features.items.team.b4', 'SAML SSO on Enterprise'),
      ],
    },
    {
      id: 'security',
      icon: ShieldCheck,
      color: '#ef4444',
      eyebrow: t('navigation:legal.security', 'Security'),
      title: t('features.items.security.title', 'Enterprise-grade by default.'),
      body: t('features.items.security.body', 'Tokens encrypted at rest with Fernet. JWT auth with rotating refresh. Full audit log of every action. Built for enterprise compliance.'),
      bullets: [
        t('features.items.security.b1', 'Encryption at rest (Fernet) + in transit (TLS 1.3)'),
        t('features.items.security.b2', 'Audit log searchable across every action'),
        t('features.items.security.b3', 'GDPR + international data privacy compliance'),
        t('features.items.security.b4', 'Role-based access control + 24/7 incident response'),
      ],
    },
  ], [t]);

  const [active, setActive] = useState(features[0].id);

  // IntersectionObserver to highlight TOC entry while scrolling
  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => { if (e.isIntersecting) setActive(e.target.id); });
      },
      { rootMargin: '-40% 0px -50% 0px', threshold: 0 }
    );
    features.forEach((f) => {
      const el = document.getElementById(f.id);
      if (el) obs.observe(el);
    });
    return () => obs.disconnect();
  }, [features]);

  return (
    <MarketingLayout>
      <Meta
        title={t('features.badge', 'Features')}
        description={t('features.hero_subtitle', 'Everything you need to run a modern agency. From the first OAuth connect to the polished client report — Bop Social handles the entire growth loop.')}
      />
      {/* ── Hero ─────────────────────────────────────── */}
      <section style={{ padding: '128px 32px 64px', textAlign: 'center', position: 'relative', overflow: 'hidden' }}>
        <div
          aria-hidden
          style={{
            position: 'absolute', inset: 0,
            background: 'var(--brand-mesh)',
            opacity: 0.35, filter: 'blur(80px) saturate(140%)',
          }}
        />
        <div style={{ position: 'relative', maxWidth: 760, margin: '0 auto' }}>
          <Badge variant="brand" size="md">{t('features.badge', 'Features')}</Badge>
          <h1 style={{
            margin: '20px 0 18px',
            fontSize: 'clamp(40px, 5vw, 56px)',
            lineHeight: 1.05,
            letterSpacing: '-0.03em',
            fontWeight: 600,
            color: 'var(--text-primary)',
          }}>
            {t('features.hero_title', 'One platform. Every workflow.')}
          </h1>
          <p style={{ margin: 0, fontSize: 18, lineHeight: 1.65, color: 'var(--text-secondary)' }}>
            {t('features.hero_subtitle', 'Everything you need to run a modern agency. From the first OAuth connect to the polished client report — Bop Social handles the entire growth loop.')}
          </p>
        </div>
      </section>

      {/* ── Body: TOC + alternating feature blocks ─────────── */}
      <section style={{ padding: '32px 32px 96px' }}>
        <div
          style={{
            maxWidth: 'var(--container-2xl)',
            margin: '0 auto',
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1fr) 220px',
            gap: 64,
          }}
          className="features-grid"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 96 }}>
            {features.map((f, i) => (
              <FeatureBlock key={f.id} feature={f} flip={i % 2 === 1} />
            ))}
          </div>

          {/* Sticky TOC */}
          <aside
            style={{
              position: 'sticky',
              top: 96,
              alignSelf: 'flex-start',
              padding: 16,
              background: 'var(--surface-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              boxShadow: 'var(--shadow-xs)',
            }}
            className="features-toc"
          >
            <div style={{
              fontSize: 11, fontWeight: 600,
              letterSpacing: '0.08em', textTransform: 'uppercase',
              color: 'var(--text-tertiary)',
              padding: '4px 8px 10px',
            }}>
              {t('features.on_this_page', 'On this page')}
            </div>
            <nav style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {features.map((f) => (
                <a
                  key={f.id}
                  href={`#${f.id}`}
                  style={{
                    padding: '8px 10px',
                    fontSize: 13,
                    fontWeight: active === f.id ? 600 : 500,
                    color: active === f.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                    background: active === f.id ? 'var(--brand-primary-soft)' : 'transparent',
                    boxShadow: active === f.id ? 'inset 2px 0 0 var(--brand-primary)' : 'none',
                    borderRadius: 'var(--radius-sm)',
                    textDecoration: 'none',
                    transition: 'var(--transition-fast)',
                    display: 'flex', alignItems: 'center', gap: 8,
                  }}
                >
                  <f.icon size={13} strokeWidth={2.2} style={{ color: f.color, flexShrink: 0 }} />
                  {f.eyebrow}
                </a>
              ))}
            </nav>
          </aside>
        </div>

        <style>{`
          @media (max-width: 980px) {
            .features-grid { grid-template-columns: 1fr !important; gap: 32px !important; }
            .features-toc { display: none !important; }
          }
        `}</style>
      </section>

      {/* ── Final CTA ────────────────────────────────── */}
      <section style={{ padding: '64px 32px 120px', textAlign: 'center', background: 'var(--surface-card)', borderTop: '1px solid var(--border-subtle)' }}>
        <h2 style={{ margin: 0, fontSize: 'clamp(28px, 3.4vw, 40px)', fontWeight: 600, letterSpacing: '-0.025em', color: 'var(--text-primary)' }}>
          {t('features.see_in_workflow', 'See it in your workflow.')}
        </h2>
        <p style={{ margin: '12px auto 28px', maxWidth: 480, fontSize: 16, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          {t('features.see_in_workflow_sub', 'Free to get started. Manage every client in one place — no credit card required.')}
        </p>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
          <Button as={Link} to="/signup" size="lg" iconRight={ArrowRight}>
            {t('features.get_started', 'Get started free')}
          </Button>
        </div>
      </section>
    </MarketingLayout>
  );
}

function FeatureBlock({ feature, flip }) {
  return (
    <motion.section
      id={feature.id}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      style={{
        scrollMarginTop: 96,
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
        gap: 48,
        alignItems: 'center',
        flexDirection: flip ? 'row-reverse' : 'row',
      }}
      className="feature-block"
    >
      {/* Visual */}
      <div style={{ order: flip ? 2 : 1 }}>
        <FeatureVisual feature={feature} />
      </div>

      {/* Copy */}
      <div style={{ order: flip ? 1 : 2 }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '4px 10px',
          fontSize: 11, fontWeight: 600,
          letterSpacing: '0.08em', textTransform: 'uppercase',
          color: '#fff',
          background: feature.color,
          borderRadius: 'var(--radius-pill)',
          marginBottom: 14,
        }}>
          <feature.icon size={11} strokeWidth={2.6} />
          {feature.eyebrow}
        </div>
        <h2 style={{
          margin: 0,
          fontSize: 'clamp(28px, 3.4vw, 36px)',
          fontWeight: 600,
          letterSpacing: '-0.02em',
          color: 'var(--text-primary)',
          lineHeight: 1.15,
        }}>
          {feature.title}
        </h2>
        <p style={{ margin: '14px 0 20px', fontSize: 15, lineHeight: 1.7, color: 'var(--text-secondary)' }}>
          {feature.body}
        </p>
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {feature.bullets.map((b) => (
            <li key={b} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14, color: 'var(--text-primary)' }}>
              <span style={{
                display: 'inline-flex',
                width: 20, height: 20, borderRadius: '50%',
                background: 'var(--success-bg)', color: 'var(--success)',
                alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}>
                <Check size={11} strokeWidth={3} />
              </span>
              {b}
            </li>
          ))}
        </ul>
      </div>

      <style>{`
        @media (max-width: 880px) {
          .feature-block { grid-template-columns: 1fr !important; gap: 24px !important; }
          .feature-block > div:first-child { order: 1 !important; }
          .feature-block > div:last-child  { order: 2 !important; }
        }
      `}</style>
    </motion.section>
  );
}

// Stylised per-feature visual — small composition, no real screenshots needed
function FeatureVisual({ feature }) {
  const Icon = feature.icon;
  return (
    <div
      style={{
        position: 'relative',
        aspectRatio: '4 / 3',
        borderRadius: 'var(--radius-xl)',
        background: `linear-gradient(135deg, ${feature.color}22, transparent 80%), var(--surface-card)`,
        border: '1px solid var(--border-subtle)',
        boxShadow: 'var(--shadow-md)',
        overflow: 'hidden',
        padding: 28,
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
      }}
    >
      {/* Window chrome */}
      <div style={{ display: 'flex', gap: 6 }}>
        {['#ef4444', '#f59e0b', '#10b981'].map((c) => (
          <span key={c} style={{ width: 8, height: 8, borderRadius: '50%', background: c, opacity: 0.7 }} />
        ))}
      </div>

      {/* Header pill */}
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 8,
        padding: '8px 12px',
        background: 'var(--surface-sunken)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        alignSelf: 'flex-start',
      }}>
        <span style={{
          width: 22, height: 22,
          background: feature.color, color: '#fff',
          borderRadius: 'var(--radius-sm)',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={12} strokeWidth={2.4} />
        </span>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
          {feature.eyebrow}
        </span>
      </div>

      {/* Skeleton-y "data" rows */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10, justifyContent: 'center' }}>
        {[0.85, 0.6, 0.7, 0.5].map((w, i) => (
          <div
            key={i}
            style={{
              height: 10,
              width: `${w * 100}%`,
              borderRadius: 999,
              background: i === 0
                ? `linear-gradient(90deg, ${feature.color}, ${feature.color}66)`
                : 'var(--surface-sunken)',
              opacity: i === 0 ? 0.95 : 0.85,
            }}
          />
        ))}
      </div>

      {/* Footer chip */}
      <div
        style={{
          alignSelf: 'flex-end',
          padding: '4px 10px',
          fontSize: 10, fontWeight: 600,
          letterSpacing: '0.08em', textTransform: 'uppercase',
          color: feature.color,
          background: `${feature.color}1A`,
          borderRadius: 'var(--radius-pill)',
        }}
      >
        Live
      </div>
    </div>
  );
}
