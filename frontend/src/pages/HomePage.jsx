/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
/**
 * HomePage — Bop Social marketing site front door.
 *
 * 15-section long-scroll structure:
 *   1.  Hero (above fold)
 *   2.  Platform strip (channels we cover)
 *   3.  3 pillars — Analyze · Engage · Convert
 *   4.  Bento grid (8 features)
 *   5.  Use-case tabs (Agencies · Real Estate · Clinics · Restaurants · Creators)
 *   6.  How it works (4-step)
 *   7.  AI everywhere (animated chat demo)
 *   8.  Comparison table vs Hootsuite / Sprout / Buffer (feature parity only)
 *   9.  Agency marketplace teaser
 *   10. Capability stats band
 *   11. Final CTA (email capture)
 *   12. Footer (provided by MarketingLayout)
 *
 * Customer testimonials, fabricated case studies, and customer-count claims
 * are intentionally absent until we have real customers to feature.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import {
  ArrowRight, PlayCircle, Sparkles, Check,
  BarChart3, MessageCircle, Zap, Bot, Inbox, PenSquare,
  Briefcase, Building2, Stethoscope, UtensilsCrossed, Palette,
  TrendingUp,
} from 'lucide-react';

import MarketingLayout      from '../components/marketing/MarketingLayout';
import MeshGradient         from '../components/marketing/MeshGradient';
import AnimatedDashboardMockup from '../components/marketing/AnimatedDashboardMockup';
import FloatingUICard       from '../components/marketing/FloatingUICard';
import ParallaxTilt         from '../components/marketing/ParallaxTilt';
import ScrollReveal         from '../components/marketing/ScrollReveal';
import FeatureBento         from '../components/marketing/FeatureBento';
import AnimatedChat         from '../components/marketing/AnimatedChat';
import ComparisonTable      from '../components/marketing/ComparisonTable';
import MetricCounter        from '../components/marketing/MetricCounter';
import CTASection           from '../components/marketing/CTASection';
import {
  AIAssistantPreview, ComposerPreview, InboxPreview, BotBuilderPreview,
  AIInsightPreview, AutomationsPreview, AnalyticsPreview, ReportsPreview,
} from '../components/marketing/BentoPreviews';

import Button from '../components/ui/Button';
import Meta   from '../components/Meta';
import JsonLd, { buildOrganization, buildWebSite } from '../components/JsonLd';
import { track } from '../services/analytics';

// ─────────────────────────────────────────────────────────────────────────────
export default function HomePage() {
  const { t } = useTranslation(['marketing', 'navigation', 'common']);
  return (
    <MarketingLayout>
      <Meta
        noSuffix
        title={t('marketing:metadata.home_title', 'Bop Social — The Marketing OS for Modern Teams')}
        description={t('marketing:metadata.home_desc', 'Manage analytics, content, conversations, and campaigns for every client and organization — across multiple platforms — in one place. Built for the Bop Universe.')}
      />
      <JsonLd id="organization" data={buildOrganization()} />
      <JsonLd id="website"      data={buildWebSite()} />
      <Hero />
      <TrustStrip />
      <ThreePillars />
      <BentoSection />
      <UseCaseTabs />
      <HowItWorks />
      <AIEverywhere />
      <ComparisonSection />
      <MarketplaceTeaser />
      <StatsBand />
      <FinalCTA />
    </MarketingLayout>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Section 1 — HERO
// ─────────────────────────────────────────────────────────────────────────────
function Hero() {
  const { t } = useTranslation(['marketing', 'navigation', 'common']);
  const reduced = useReducedMotion();
  return (
    <section style={{
      position: 'relative',
      paddingTop: 'clamp(120px, 18vh, 180px)',
      paddingBottom: 'clamp(80px, 12vh, 120px)',
      overflow: 'hidden',
      isolation: 'isolate',
    }}>
      <MeshGradient variant="hero" />

      <div style={{
        position: 'relative', zIndex: 1,
        maxWidth: 1180, margin: '0 auto',
        padding: '0 24px',
        textAlign: 'center',
        color: '#fff',
      }}>
        {/* Eyebrow */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <Link to="/changelog" style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            padding: '6px 14px',
            fontSize: 12, fontWeight: 600,
            color: '#fff',
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid rgba(255,255,255,0.14)',
            borderRadius: 'var(--radius-pill)',
            textDecoration: 'none',
            backdropFilter: 'blur(10px)',
          }}>
            <Sparkles size={12} style={{ color: '#F5A623' }} />
            <span style={{ color: 'rgba(255,255,255,0.65)' }}>{t('home.eyebrow_new', 'NEW')}</span>
            {t('home.eyebrow_text', 'CTWA Bot Builder is live')}
            <ArrowRight size={11} style={{ opacity: 0.6 }} />
          </Link>
        </motion.div>

        {/* Headline */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1 }}
          style={{
            margin: '24px 0 0',
            fontSize: 'clamp(40px, 7vw, 72px)',
            fontWeight: 600, lineHeight: 1.05, letterSpacing: '-0.03em',
            color: '#fff', maxWidth: 900, marginInline: 'auto',
          }}
        >
          {t('home.hero_title_pre', 'The ')}
          <span style={{
            background: 'linear-gradient(135deg, #F5A623 0%, #F7C06D 50%, #E09612 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}>
            {t('home.hero_title_highlight', 'Marketing OS')}
          </span>
          <br />{t('home.hero_title_post', 'for modern teams')}
        </motion.h1>

        {/* Subheading */}
        <motion.p
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.25 }}
          style={{
            margin: '24px auto 0',
            fontSize: 'clamp(16px, 1.8vw, 19px)',
            color: 'rgba(255,255,255,0.72)', lineHeight: 1.55,
            maxWidth: 640,
          }}
        >
          {t('home.hero_subtitle', 'Manage analytics, content, conversations, and campaigns for every client and organization — across multiple platforms — in one place.')}
        </motion.p>

        {/* CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          style={{
            marginTop: 32, display: 'flex', gap: 12,
            justifyContent: 'center', flexWrap: 'wrap',
          }}
        >
          <Button as={Link} to="/signup" size="lg"
                  onClick={() => track('signup_click', { source: 'home_hero' })}
                  style={{
                    background: 'linear-gradient(135deg, #F5A623, #E09612)',
                    color: '#1E202A', border: 'none', fontWeight: 600,
                  }}>
            {t('home.get_started', 'Get started')} <ArrowRight size={15} />
          </Button>
          <Button as={Link} to="/customers" size="lg" variant="ghost"
                  style={{
                    color: '#fff',
                    background: 'rgba(255,255,255,0.06)',
                    border: '1px solid rgba(255,255,255,0.18)',
                  }}>
            <PlayCircle size={15} /> {t('home.watch_demo', 'Watch 90s demo')}
          </Button>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.6 }}
          style={{ marginTop: 14, fontSize: 13, color: 'rgba(255,255,255,0.5)' }}
        >
          {t('home.positioning', 'Multi-company architecture · Real-time analytics · Built for the Bop Universe')}
        </motion.p>

        {/* Hero mockup with floating cards */}
        <motion.div
          initial={{ opacity: 0, y: 40, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
          style={{ marginTop: 64, position: 'relative', maxWidth: 1080, marginInline: 'auto' }}
        >
          <ParallaxTilt max={reduced ? 0 : 4}>
            <AnimatedDashboardMockup />
          </ParallaxTilt>

          <div className="mkt-hero-floats">
            <FloatingUICard top="6%"  left="-4%"  delay={0.6} tone="cyan"   width={220}>
              <NotificationCard />
            </FloatingUICard>
            <FloatingUICard top="58%" left="-7%"  delay={0.9} tone="green"  width={220}>
              <LeadCapturedCard />
            </FloatingUICard>
            <FloatingUICard top="14%" right="-4%" delay={0.7} tone="purple" width={230}>
              <CampaignMetricCard />
            </FloatingUICard>
            <FloatingUICard top="62%" right="-6%" delay={1.0} tone="pink"   width={230}>
              <AIPopupCard />
            </FloatingUICard>
          </div>
        </motion.div>

        <style>{`
          @media (max-width: 1100px) {
            .mkt-hero-floats { display: none !important; }
          }
        `}</style>
      </div>
    </section>
  );
}

// ── Floating-card contents ──────────────────────────────────────────────────
function NotificationCard() {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={floatIconStyle('rgba(245,166,35,0.15)', '#F5A623')}>
          <Inbox size={11} />
        </span>
        <span style={floatLabel}>NEW MESSAGE · IG</span>
      </div>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>Priya Sharma</div>
      <div style={{ marginTop: 2, fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
        Is the 3BHK still available? Can I visit on Saturday?
      </div>
    </div>
  );
}

function CampaignMetricCard() {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={floatIconStyle('rgba(139,92,246,0.15)', '#a78bfa')}>
          <BarChart3 size={11} />
        </span>
        <span style={floatLabel}>WEEKLY REACH</span>
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
        248,392
      </div>
      <div style={{ marginTop: 2, fontSize: 11, color: 'var(--success)', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
        <TrendingUp size={11} /> +23% vs last week
      </div>
    </div>
  );
}

function LeadCapturedCard() {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={floatIconStyle('rgba(16,185,129,0.15)', '#34d399')}>
          <Check size={12} strokeWidth={3} />
        </span>
        <span style={floatLabel}>LEAD CAPTURED</span>
      </div>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>Rahul Verma</div>
      <div style={{ marginTop: 2, fontSize: 11, color: 'var(--text-secondary)' }}>
        Source: <strong style={{ color: '#34d399' }}>CTWA · Diwali campaign</strong>
      </div>
    </div>
  );
}

function AIPopupCard() {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={floatIconStyle('rgba(236,72,153,0.15)', '#f472b6')}>
          <Sparkles size={11} />
        </span>
        <span style={floatLabel}>AI SUGGESTION</span>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5 }}>
        Try posting Reels on Tue 7pm — your audience is 2.4× more active.
      </div>
    </div>
  );
}

const floatLabel = {
  fontSize: 9, fontWeight: 700,
  color: 'var(--text-tertiary)',
  letterSpacing: '0.06em', textTransform: 'uppercase',
};
const floatIconStyle = (bg, color) => ({
  width: 22, height: 22,
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  background: bg, color, borderRadius: 'var(--radius-sm)',
});

// ─────────────────────────────────────────────────────────────────────────────
// Section 2 — PLATFORM STRIP
// Customer-logo carousel intentionally omitted until we have real customers.
// ─────────────────────────────────────────────────────────────────────────────
function TrustStrip() {
  const { t } = useTranslation('marketing');
  const platforms = ['Facebook', 'Instagram', 'YouTube', 'LinkedIn', 'Google Business', 'WhatsApp Business'];
  return (
    <section style={{
      padding: '40px 24px 32px',
      background: 'var(--surface-card)',
      borderTop: '1px solid var(--border-subtle)',
      borderBottom: '1px solid var(--border-subtle)',
    }}>
      <div style={{ maxWidth: 1180, margin: '0 auto', textAlign: 'center' }}>
        <p style={{
          margin: '0 0 18px',
          fontSize: 11, fontWeight: 700,
          letterSpacing: '0.08em', textTransform: 'uppercase',
          color: 'var(--text-tertiary)',
        }}>
          {t('home.channels_headline', 'One platform, every channel that matters')}
        </p>
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: '20px 32px',
          justifyContent: 'center', alignItems: 'center',
        }}>
          {platforms.map((label) => (
            <span key={label} style={{
              fontSize: 14, fontWeight: 600,
              color: 'var(--text-secondary)',
              letterSpacing: '0.01em',
            }}>{label}</span>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Section 3 — THREE PILLARS
// ─────────────────────────────────────────────────────────────────────────────
function ThreePillars() {
  const { t } = useTranslation('marketing');
  const pillars = [
    { icon: BarChart3, tone: '#F5A623', toneSoft: 'rgba(245,166,35,0.12)',
      label: t('home.pillar_analyze_label', 'ANALYZE'),
      title: t('home.pillar_analyze_title', 'Track everything'),
      blurb: t('home.pillar_analyze_blurb', 'Reach, engagement, and revenue across multiple platforms in one dashboard.'),
      preview: <AnalyticsPreview /> },
    { icon: MessageCircle, tone: '#a78bfa', toneSoft: 'rgba(139,92,246,0.10)',
      label: t('home.pillar_engage_label', 'ENGAGE'),
      title: t('home.pillar_engage_title', 'Reply in one place'),
      blurb: t('home.pillar_engage_blurb', 'Every DM, comment, and review across platforms — sorted, AI-prioritised, replyable.'),
      preview: <InboxPreview /> },
    { icon: Bot, tone: '#34d399', toneSoft: 'rgba(16,185,129,0.10)',
      label: t('home.pillar_convert_label', 'CONVERT'),
      title: t('home.pillar_convert_title', 'Capture more leads'),
      blurb: t('home.pillar_convert_blurb', 'Run conversational campaigns with AI bots that qualify customers 24/7 and route them to your CRM.'),
      preview: <BotBuilderPreview /> },
  ];
  return (
    <section style={{ padding: 'clamp(64px, 10vh, 120px) 24px', background: 'var(--surface-page)' }}>
      <div style={{ maxWidth: 1180, margin: '0 auto' }}>
        <ScrollReveal>
          <SectionHeading
            eyebrow={t('home.pillars_eyebrow', 'Three Pillars')}
            title={t('home.pillars_title', 'Analyze. Engage. Convert.')}
            subtitle={t('home.pillars_desc', 'Everything your team needs to turn social presence into measurable revenue.')}
          />
        </ScrollReveal>

        <div style={{
          marginTop: 48,
          display: 'grid',
          gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
          gap: 16,
        }} className="mkt-pillars-grid">
          {pillars.map((p, i) => (
            <ScrollReveal key={p.title} delay={0.1 * i}>
              <div style={{
                padding: 24, height: '100%',
                background: 'var(--surface-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-lg)',
                display: 'flex', flexDirection: 'column', gap: 18,
              }}>
                <div>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    width: 36, height: 36,
                    background: p.toneSoft, color: p.tone,
                    borderRadius: 'var(--radius-md)', marginBottom: 12,
                  }}>
                    <p.icon size={18} strokeWidth={2.2} />
                  </span>
                  <span style={{
                    display: 'block', marginBottom: 4,
                    fontSize: 11, fontWeight: 700, color: p.tone,
                    letterSpacing: '0.08em', textTransform: 'uppercase',
                  }}>{p.label}</span>
                  <h3 style={{
                    margin: 0, fontSize: 20, fontWeight: 700,
                    color: 'var(--text-primary)', letterSpacing: '-0.01em',
                  }}>{p.title}</h3>
                  <p style={{
                    margin: '8px 0 0',
                    fontSize: 14, lineHeight: 1.55,
                    color: 'var(--text-secondary)',
                  }}>{p.blurb}</p>
                </div>
                <div style={{ marginTop: 'auto', minHeight: 140 }}>{p.preview}</div>
              </div>
            </ScrollReveal>
          ))}
        </div>
        <style>{`
          @media (max-width: 900px) { .mkt-pillars-grid { grid-template-columns: 1fr !important; } }
        `}</style>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Section 4 — BENTO GRID
// ─────────────────────────────────────────────────────────────────────────────
function BentoSection() {
  const { t } = useTranslation(['marketing', 'navigation']);
  const items = [
    { id: 'ai-assistant', title: t('navigation:products.ai_assistant', 'AI Assistant'),
      description: t('navigation:products.ai_assistant_desc', 'Talk to your marketing data. Cmd+J anywhere.'),
      to: '/product/ai-assistant', tone: 'cyan', accentBg: true,
      icon: Sparkles, span: { col: 2, row: 1 },
      preview: <AIAssistantPreview /> },
    { id: 'composer', title: t('navigation:products.composer', 'Composer'),
      description: t('navigation:products.composer_desc', 'Write once, publish 5x.'),
      to: '/product/composer', tone: 'purple', icon: PenSquare,
      preview: <ComposerPreview /> },
    { id: 'inbox', title: t('navigation:products.inbox', 'Unified Inbox'),
      description: t('navigation:products.inbox_desc', 'Every conversation in one place.'),
      to: '/product/inbox', tone: 'green', icon: Inbox,
      preview: <InboxPreview /> },
    { id: 'bot-builder', title: t('navigation:products.bot_builder', 'Bot Builder'),
      description: t('navigation:products.bot_builder_desc', 'Visual flow editor for CTWA ads.'),
      to: '/product/bot-builder', tone: 'pink', icon: Bot,
      preview: <BotBuilderPreview /> },
    { id: 'ai-insights', title: t('navigation:products.ai_studio', 'AI Insights'),
      description: t('navigation:products.ai_studio_desc', 'Spot trends + drops before they hurt.'),
      to: '/product/ai', tone: 'amber', icon: TrendingUp,
      preview: <AIInsightPreview /> },
    { id: 'automations', title: t('navigation:products.automations', 'Automations'),
      description: t('navigation:products.automations_desc', 'IF this happens, do that.'),
      to: '/product/automations', tone: 'cyan', accentBg: true,
      icon: Zap, span: { col: 2, row: 1 },
      preview: <AutomationsPreview /> },
    { id: 'analytics', title: t('navigation:products.analytics', 'Analytics'),
      description: t('navigation:products.analytics_desc', 'Cross-platform metrics, demystified.'),
      to: '/product/analytics', tone: 'cyan', icon: BarChart3,
      preview: <AnalyticsPreview /> },
    { id: 'reports', title: t('navigation:products.reports', 'Reports'),
      description: t('navigation:products.reports_desc', 'Reports that write themselves.'),
      to: '/product/reports', tone: 'purple', icon: BarChart3,
      preview: <ReportsPreview /> },
  ];
  return (
    <section style={{
      padding: 'clamp(64px, 10vh, 120px) 24px',
      background: 'var(--surface-card)',
      borderTop: '1px solid var(--border-subtle)',
      borderBottom: '1px solid var(--border-subtle)',
    }}>
      <div style={{ maxWidth: 1180, margin: '0 auto' }}>
        <ScrollReveal>
          <SectionHeading
            eyebrow={t('home.bento_eyebrow', 'Capabilities')}
            title={t('home.bento_title', "Everything you need. Nothing you don't.")}
            subtitle={t('home.bento_subtitle', 'Hover any tile to see it move. Click for the deep dive.')}
          />
        </ScrollReveal>
        <div style={{ marginTop: 48 }}>
          <ScrollReveal>
            <FeatureBento items={items} columns={4} />
          </ScrollReveal>
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Section 5 — USE CASE TABS
// ─────────────────────────────────────────────────────────────────────────────
function UseCaseTabs() {
  const { t } = useTranslation(['marketing', 'navigation']);
  const tabs = [
    { id: 'agencies', label: t('navigation:solutions.agencies', 'Agencies'), icon: Briefcase,
      headline: t('home.use_case_agencies_headline', 'Manage 100+ clients without losing your mind.'),
      bullets: [
        t('home.use_case_agencies_bullet_1', 'Multi-client workspaces with one-click switcher'),
        t('home.use_case_agencies_bullet_2', 'Team collaboration with role permissions'),
        t('home.use_case_agencies_bullet_3', 'White-label client portals + branded reports'),
        t('home.use_case_agencies_bullet_4', 'Approval workflows for every action'),
        t('home.use_case_agencies_bullet_5', "AI assistant tuned to each client's brand voice"),
      ],
      cta: { label: t('home.read_case_study', 'Read agency case study'), to: '/customers' } },
    { id: 'real-estate', label: t('navigation:solutions.real_estate', 'Real Estate'), icon: Building2,
      headline: t('home.use_case_real_estate_headline', 'Sell more properties on social media.'),
      bullets: [
        t('home.use_case_real_estate_bullet_1', 'Property listing carousels for Instagram + Facebook'),
        t('home.use_case_real_estate_bullet_2', 'Site-visit reminders via WhatsApp'),
        t('home.use_case_real_estate_bullet_3', 'Lead capture from CTWA ads — directly to CRM'),
        t('home.use_case_real_estate_bullet_4', 'AI-written property descriptions'),
        t('home.use_case_real_estate_bullet_5', 'Open-house promo automation'),
      ],
      cta: { label: t('home.real_estate_playbook', 'Real estate playbook'), to: '/solutions/real-estate' } },
    { id: 'clinics', label: t('navigation:solutions.clinics', 'Healthcare'), icon: Stethoscope,
      headline: t('home.use_case_healthcare_headline', 'Engage patients across every platform.'),
      bullets: [
        t('home.use_case_healthcare_bullet_1', 'Appointment reminders via WhatsApp Business'),
        t('home.use_case_healthcare_bullet_2', 'Lab-report delivery with end-to-end audit trail'),
        t('home.use_case_healthcare_bullet_3', 'Pre-built health-awareness content calendar'),
        t('home.use_case_healthcare_bullet_4', 'HIPAA-aligned content checker'),
        t('home.use_case_healthcare_bullet_5', 'Review management with AI-suggested replies'),
      ],
      cta: { label: t('home.healthcare_playbook', 'Healthcare playbook'), to: '/solutions/clinics' } },
    { id: 'restaurants', label: t('navigation:solutions.restaurants', 'Restaurants'), icon: UtensilsCrossed,
      headline: t('home.use_case_restaurants_headline', 'Fill more tables with social.'),
      bullets: [
        t('home.use_case_restaurants_bullet_1', 'Reservation bots that integrate with your POS'),
        t('home.use_case_restaurants_bullet_2', 'Daily-specials posting on auto-pilot'),
        t('home.use_case_restaurants_bullet_3', 'Review management for Zomato + Google'),
        t('home.use_case_restaurants_bullet_4', 'Influencer outreach + tracking'),
        t('home.use_case_restaurants_bullet_5', 'Festival campaigns ready to go'),
      ],
      cta: { label: t('home.restaurant_playbook', 'Restaurant playbook'), to: '/solutions/restaurants' } },
    { id: 'creators', label: t('navigation:solutions.creators', 'Creators'), icon: Palette,
      headline: t('home.use_case_creators_headline', 'Track your creator economy.'),
      bullets: [
        t('home.use_case_creators_bullet_1', 'YouTube + Instagram + LinkedIn analytics in one view'),
        t('home.use_case_creators_bullet_2', 'Brand-deal tracking + invoicing'),
        t('home.use_case_creators_bullet_3', 'Audience insights — what your fans actually want'),
        t('home.use_case_creators_bullet_4', 'Posting optimization with AI predictions'),
        t('home.use_case_creators_bullet_5', 'Content calendar tuned to your schedule'),
      ],
      cta: { label: t('home.creator_playbook', 'Creator playbook'), to: '/solutions/creators' } },
  ];
  const [active, setActive] = useState(tabs[0].id);
  const current = tabs.find((t) => t.id === active) || tabs[0];

  return (
    <section style={{ padding: 'clamp(64px, 10vh, 120px) 24px', background: 'var(--surface-page)' }}>
      <div style={{ maxWidth: 1080, margin: '0 auto' }}>
        <ScrollReveal>
          <SectionHeading
            eyebrow={t('home.use_cases_eyebrow', 'Made for every kind of marketer')}
            title={t('home.use_cases_title', 'Whoever you are, Bop Social fits')}
          />
        </ScrollReveal>

        <ScrollReveal delay={0.1}>
          <div role="tablist" style={{
            marginTop: 36, display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'center',
          }}>
            {tabs.map((tab) => (
              <button
                key={tab.id} role="tab" aria-selected={active === tab.id}
                onClick={() => setActive(tab.id)}
                style={{
                  padding: '10px 16px',
                  fontSize: 13, fontWeight: 600,
                  color: active === tab.id ? '#1E202A' : 'var(--text-secondary)',
                  background: active === tab.id
                    ? 'linear-gradient(135deg, #F5A623, #E09612)' : 'var(--surface-card)',
                  border: '1px solid',
                  borderColor: active === tab.id ? 'transparent' : 'var(--border-default)',
                  borderRadius: 'var(--radius-pill)',
                  cursor: 'pointer',
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  fontFamily: 'inherit', transition: 'var(--transition-fast)',
                }}
              >
                <tab.icon size={13} />
                {tab.label}
              </button>
            ))}
          </div>

          <motion.div
            key={current.id}
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            style={{
              marginTop: 32, padding: 32,
              background: 'var(--surface-card)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-xl)',
              display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 36,
              alignItems: 'center',
            }}
            className="mkt-usecase-grid"
          >
            <div>
              <h3 style={{
                margin: 0, fontSize: 24, fontWeight: 700,
                color: 'var(--text-primary)', letterSpacing: '-0.01em', lineHeight: 1.25,
              }}>{current.headline}</h3>
              <ul style={{ margin: '20px 0 0', padding: 0, listStyle: 'none' }}>
                {current.bullets.map((b) => (
                  <li key={b} style={{
                    display: 'flex', alignItems: 'flex-start', gap: 10,
                    padding: '8px 0',
                    fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.55,
                  }}>
                    <Check size={14} style={{ color: '#F5A623', flexShrink: 0, marginTop: 4 }} strokeWidth={2.5} />
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
              <div style={{ marginTop: 20 }}>
                <Button as={Link} to={current.cta.to} size="md" variant="ghost"
                        style={{ color: 'var(--brand-primary-hover)', padding: 0 }}>
                  {current.cta.label} <ArrowRight size={14} />
                </Button>
              </div>
            </div>

            <div style={{
              minHeight: 280, borderRadius: 'var(--radius-lg)', overflow: 'hidden',
              border: '1px solid var(--border-subtle)',
            }}>
              <AnimatedDashboardMockup />
            </div>
          </motion.div>
          <style>{`
            @media (max-width: 880px) { .mkt-usecase-grid { grid-template-columns: 1fr !important; } }
          `}</style>
        </ScrollReveal>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Section 6 — HOW IT WORKS
// ─────────────────────────────────────────────────────────────────────────────
function HowItWorks() {
  const { t } = useTranslation('marketing');
  const steps = [
    { n: 1, title: t('home.step_1_title', 'Sign up free'),     blurb: t('home.step_1_blurb', 'Email + password. 5-second flow. No credit card.') },
    { n: 2, title: t('home.step_2_title', 'Connect accounts'), blurb: t('home.step_2_blurb', 'Paste tokens or OAuth — Meta + Google + LinkedIn supported.') },
    { n: 3, title: t('home.step_3_title', 'Create with AI'),   blurb: t('home.step_3_blurb', 'Generate posts, replies, and reports tuned to your brand voice.') },
    { n: 4, title: t('home.step_4_title', 'Track results'),    blurb: t('home.step_4_blurb', 'Cross-platform analytics + AI-narrated PDF reports for clients.') },
  ];
  return (
    <section style={{
      padding: 'clamp(64px, 10vh, 120px) 24px',
      background: 'var(--surface-card)',
      borderTop: '1px solid var(--border-subtle)',
      borderBottom: '1px solid var(--border-subtle)',
    }}>
      <div style={{ maxWidth: 1080, margin: '0 auto' }}>
        <ScrollReveal>
          <SectionHeading
            eyebrow={t('home.how_it_works_eyebrow', 'From zero to live')}
            title={t('home.how_it_works_title', 'Get up and running in 4 steps')}
          />
        </ScrollReveal>

        <div style={{
          marginTop: 48, position: 'relative',
          display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 16,
        }} className="mkt-steps-grid">
          <div aria-hidden style={{
            position: 'absolute', top: 26, left: '12.5%', right: '12.5%',
            height: 2, background: 'linear-gradient(90deg, #F5A623, #E09612)',
            opacity: 0.35, zIndex: 0,
          }} className="mkt-steps-connector" />
          {steps.map((s, i) => (
            <ScrollReveal key={s.n} delay={i * 0.1}>
              <div style={{ position: 'relative', zIndex: 1, textAlign: 'center' }}>
                <div style={{
                  width: 52, height: 52, margin: '0 auto 16px',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  background: 'var(--surface-page)',
                  border: '2px solid #F5A623', borderRadius: '50%',
                  fontSize: 18, fontWeight: 700, color: 'var(--text-primary)',
                  boxShadow: '0 0 0 6px var(--surface-card), 0 12px 32px rgba(245, 166, 35, 0.22)',
                }}>{s.n}</div>
                <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>{s.title}</h3>
                <p style={{
                  margin: '6px 0 0',
                  fontSize: 13, lineHeight: 1.55,
                  color: 'var(--text-secondary)',
                  maxWidth: 220, marginInline: 'auto',
                }}>{s.blurb}</p>
              </div>
            </ScrollReveal>
          ))}
        </div>
        <style>{`
          @media (max-width: 800px) {
            .mkt-steps-grid { grid-template-columns: 1fr !important; gap: 28px !important; }
            .mkt-steps-connector { display: none !important; }
          }
        `}</style>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Section 7 — AI EVERYWHERE
// ─────────────────────────────────────────────────────────────────────────────
function AIEverywhere() {
  const { t } = useTranslation('marketing');
  const features = [
    t('home.ai_feature_1', 'Brand voice tuned to your business'),
    t('home.ai_feature_2', 'Generates posts, replies, and reports'),
    t('home.ai_feature_3', 'Predicts best posting times'),
    t('home.ai_feature_4', 'Detects PR crises before they spread'),
    t('home.ai_feature_5', 'Captures leads with conversational ads'),
  ];
  return (
    <section style={{ padding: 'clamp(64px, 10vh, 120px) 24px', background: 'var(--surface-page)' }}>
      <div style={{ maxWidth: 1080, margin: '0 auto' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 56, alignItems: 'center' }} className="mkt-ai-grid">
          <ScrollReveal>
            <span style={{
              display: 'inline-block',
              padding: '4px 10px', marginBottom: 16,
              fontSize: 11, fontWeight: 700,
              color: '#F5A623', background: 'rgba(245,166,35,0.12)',
              borderRadius: 'var(--radius-pill)', letterSpacing: '0.06em',
            }}>{t('home.ai_badge', 'POWERED BY BOP INTELLIGENCE')}</span>
            <h2 style={{
              margin: 0, fontSize: 'clamp(28px, 4vw, 40px)',
              fontWeight: 700, letterSpacing: '-0.02em',
              color: 'var(--text-primary)', lineHeight: 1.15,
            }}>{t('home.ai_title', 'AI in every corner')}</h2>
            <p style={{
              margin: '14px 0 0',
              fontSize: 16, lineHeight: 1.6,
              color: 'var(--text-secondary)', maxWidth: 480,
            }}>
              {t('home.ai_desc', 'Bop Social is engineered with native AI intelligence across analytics, post scheduling, and workspace reporting.')}
            </p>
            <ul style={{ margin: '24px 0 0', padding: 0, listStyle: 'none' }}>
              {features.map((f) => (
                <li key={f} style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '8px 0',
                  fontSize: 14, color: 'var(--text-secondary)',
                }}>
                  <Sparkles size={14} style={{ color: '#F5A623', flexShrink: 0 }} />
                  {f}
                </li>
              ))}
            </ul>
            <div style={{ marginTop: 24 }}>
              <Button as={Link} to="/product/ai" size="md">
                {t('home.ai_button', 'Explore AI features')} <ArrowRight size={14} />
              </Button>
            </div>
          </ScrollReveal>

          <ScrollReveal delay={0.15}>
            <AnimatedChat
              userMessage={t('home.chat_user', 'How are we doing on Instagram this week?')}
              assistantReply={t('home.chat_assistant', "Your reach grew 23% vs last week — mostly driven by your Reel about the Acme Heights property tour (had 3.2× normal saves). I'd suggest posting 2 more Reels this week. Want me to draft the captions?")}
              speedMs={16}
            />
          </ScrollReveal>
        </div>
        <style>{`
          @media (max-width: 880px) { .mkt-ai-grid { grid-template-columns: 1fr !important; gap: 32px !important; } }
        `}</style>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Section 8 — COMPARISON
// ─────────────────────────────────────────────────────────────────────────────
function ComparisonSection() {
  const { t } = useTranslation('marketing');
  const columns = ['Bop Social', 'Hootsuite', 'Sprout Social', 'Buffer'];
  const rows = [
    { feature: t('home.comp_analytics', 'Multi-platform analytics'),     cells: ['yes',          'yes',     'yes',     'partial'] },
    { feature: t('home.comp_ai', 'Deep AI assistant'),            cells: ['Bop Social',   'partial', 'partial', 'no'] },
    { feature: t('home.comp_whatsapp', 'WhatsApp Business API'),        cells: ['yes',          'no',      'no',      'no'] },
    { feature: t('home.comp_ctwa', 'Click-to-WhatsApp bots'),       cells: ['yes',          'no',      'no',      'no'] },
    { feature: t('home.comp_bot_builder', 'Visual bot builder'),           cells: ['yes',          'no',      'no',      'no'] },
    { feature: t('home.comp_crm', 'Lead-capture CRM'),             cells: ['yes',          'no',      'partial', 'no'] },
    { feature: t('home.comp_multitenant', 'Multi-tenant client workspaces'), cells: ['yes',        'partial', 'partial', 'no'] },
    { feature: t('home.comp_audit', 'Activity audit trail'),         cells: ['yes',          'partial', 'yes',     'no'] },
    { feature: t('home.comp_universe', 'Built for Bop Universe'),       cells: ['yes',          'no',      'no',      'no'] },
  ];
  return (
    <section style={{
      padding: 'clamp(64px, 10vh, 120px) 24px',
      background: 'var(--surface-card)',
      borderTop: '1px solid var(--border-subtle)',
      borderBottom: '1px solid var(--border-subtle)',
    }}>
      <div style={{ maxWidth: 1080, margin: '0 auto' }}>
        <ScrollReveal>
          <SectionHeading
            eyebrow={t('home.comparison_eyebrow', 'Honest comparison')}
            title={t('home.comparison_title', 'How Bop Social stacks up')}
            subtitle={t('home.comparison_subtitle', 'Built for multi-company agencies and enterprises serious about AI, messaging, and multi-tenant workflows.')}
          />
        </ScrollReveal>
        <ScrollReveal delay={0.1}>
          <div style={{ marginTop: 36 }}>
            <ComparisonTable columns={columns} rows={rows} highlightIndex={0} />
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Section 11 — MARKETPLACE TEASER
// ─────────────────────────────────────────────────────────────────────────────
function MarketplaceTeaser() {
  const { t } = useTranslation('marketing');
  const steps = [
    { title: t('home.mkt_step_1_title', 'Browse verified agencies'),  body: t('home.mkt_step_1_body', 'Search by industry, language, budget, and platform.') },
    { title: t('home.mkt_step_2_title', 'Match by fit'),              body: t('home.mkt_step_2_body', 'See pricing ranges, specialities, and example workflows up front.') },
    { title: t('home.mkt_step_3_title', 'Manage from one inbox'),     body: t('home.mkt_step_3_body', 'Approvals, scheduled posts, and reporting flow through Bop Social.') },
  ];
  return (
    <section style={{ padding: 'clamp(64px, 10vh, 120px) 24px', background: 'var(--surface-page)' }}>
      <div style={{ maxWidth: 1180, margin: '0 auto' }}>
        <ScrollReveal>
          <SectionHeading
            eyebrow={t('home.marketplace_eyebrow', 'Built-in marketplace')}
            title={t('home.marketplace_title', 'Need an agency to help?')}
            subtitle={t('home.marketplace_desc', 'A two-sided marketplace where verified agencies match with businesses by industry and budget. Onboarding the first cohort of agencies now.')}
            cta={{ to: '/agencies', label: t('home.marketplace_cta', 'Browse the marketplace') }}
          />
        </ScrollReveal>

        <div style={{
          marginTop: 36,
          display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 14,
        }} className="mkt-marketplace-grid">
          {steps.map((s, i) => (
            <ScrollReveal key={s.title} delay={i * 0.07}>
              <div style={{
                height: '100%',
                padding: 22,
                background: 'var(--surface-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-lg)',
              }}>
                <div style={{
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  width: 28, height: 28, borderRadius: 'var(--radius-pill)',
                  background: 'var(--brand-primary-soft)',
                  color: 'var(--brand-primary-hover)',
                  fontSize: 13, fontWeight: 700,
                }}>{i + 1}</div>
                <h3 style={{
                  margin: '14px 0 6px',
                  fontSize: 16, fontWeight: 700,
                  color: 'var(--text-primary)',
                  letterSpacing: '-0.01em',
                }}>{s.title}</h3>
                <p style={{
                  margin: 0, fontSize: 13, lineHeight: 1.55,
                  color: 'var(--text-secondary)',
                }}>{s.body}</p>
              </div>
            </ScrollReveal>
          ))}
        </div>
        <style>{`
          @media (max-width: 1024px) { .mkt-marketplace-grid { grid-template-columns: 1fr 1fr !important; } }
          @media (max-width: 600px)  { .mkt-marketplace-grid { grid-template-columns: 1fr !important; } }
        `}</style>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Section 12 — STATS BAND
// ─────────────────────────────────────────────────────────────────────────────
function StatsBand() {
  const { t } = useTranslation('marketing');
  const stats = [
    { value: 5,    suffix: '',   label: t('home.stats_platforms', 'platforms integrated') },
    { value: 14,   suffix: '+',  label: t('home.stats_languages', 'languages supported') },
    { value: 99.9, suffix: '%',  label: t('home.stats_uptime', 'uptime target'), decimals: 1 },
    { value: 100,  suffix: '%',  label: t('home.stats_clients', 'multi-tenant architecture') },
  ];
  return (
    <section style={{ position: 'relative', overflow: 'hidden' }}>
      <div style={{
        padding: 'clamp(48px, 8vh, 88px) 24px',
        background: 'linear-gradient(135deg, #1E202A 0%, #2D3142 50%, #1E202A 100%)',
        borderTop: '1px solid rgba(245, 166, 35, 0.25)',
        borderBottom: '1px solid rgba(245, 166, 35, 0.25)',
        color: '#fff',
      }}>
        <div style={{ maxWidth: 1080, margin: '0 auto' }}>
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
            gap: 24, textAlign: 'center',
          }} className="mkt-stats-grid">
            {stats.map((s) => (
              <div key={s.label}>
                <div style={{
                  fontSize: 'clamp(28px, 5vw, 48px)',
                  fontWeight: 700, letterSpacing: '-0.02em',
                  lineHeight: 1.05, color: '#F5A623',
                }}>
                  <MetricCounter value={s.value} suffix={s.suffix}
                                 decimals={s.decimals || 0} duration={1.6} />
                </div>
                <div style={{
                  marginTop: 8, fontSize: 13, fontWeight: 600,
                  color: 'rgba(255,255,255,0.78)',
                  letterSpacing: '0.04em', textTransform: 'uppercase',
                }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
        <style>{`
          @media (max-width: 720px) {
            .mkt-stats-grid { grid-template-columns: 1fr 1fr !important; gap: 32px !important; }
          }
        `}</style>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Section 14 — FINAL CTA
// ─────────────────────────────────────────────────────────────────────────────
function FinalCTA() {
  const { t } = useTranslation('marketing');
  return (
    <section style={{ padding: 'clamp(64px, 10vh, 120px) 24px', background: 'var(--surface-page)' }}>
      <CTASection
        title={t('home.cta_title', 'Ready to elevate your marketing operations?')}
        subtitle={t('home.cta_subtitle', 'Unified social management, real-time analytics, and native AI workflows.')}
        primary={{ to: '/signup', label: t('home.cta_button', 'Get started') }}
        showEmail
        microCopy={t('home.cta_micro', 'Enterprise ready · Multi-tenant architecture · Built for the Bop Universe')}
        variant="cta"
      />
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Reusable section heading
// ─────────────────────────────────────────────────────────────────────────────
function SectionHeading({ eyebrow, title, subtitle, cta }) {
  return (
    <div style={{ textAlign: 'center', maxWidth: 720, marginInline: 'auto' }}>
      {eyebrow && (
        <span style={{
          display: 'inline-block',
          padding: '4px 12px', marginBottom: 14,
          fontSize: 11, fontWeight: 700,
          color: 'var(--brand-primary-hover)',
          background: 'var(--brand-primary-soft)',
          borderRadius: 'var(--radius-pill)',
          letterSpacing: '0.06em', textTransform: 'uppercase',
        }}>{eyebrow}</span>
      )}
      <h2 style={{
        margin: 0,
        fontSize: 'clamp(28px, 4vw, 44px)',
        fontWeight: 700, color: 'var(--text-primary)',
        letterSpacing: '-0.02em', lineHeight: 1.15,
      }}>{title}</h2>
      {subtitle && (
        <p style={{
          margin: '14px auto 0',
          fontSize: 'clamp(15px, 1.5vw, 17px)',
          lineHeight: 1.6,
          color: 'var(--text-secondary)', maxWidth: 600,
        }}>{subtitle}</p>
      )}
      {cta && (
        <div style={{ marginTop: 16 }}>
          <Button as={Link} to={cta.to} size="md" variant="ghost"
                  style={{ color: 'var(--brand-primary-hover)', padding: 0 }}>
            {cta.label} <ArrowRight size={14} />
          </Button>
        </div>
      )}
    </div>
  );
}
