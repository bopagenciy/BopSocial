/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ArrowRight,
  Building2,
  Stethoscope,
  ShoppingBag,
  Utensils,
  Users,
  Sparkles,
  MessageCircle,
  PenSquare,
  TrendingUp,
} from 'lucide-react';

import MarketingLayout from '../components/marketing/MarketingLayout';
import MeshGradient from '../components/marketing/MeshGradient';
import ScrollReveal from '../components/marketing/ScrollReveal';
import Button from '../components/ui/Button';
import Meta from '../components/Meta';

export default function CustomersPage() {
  const { t } = useTranslation(['marketing', 'common']);

  const workflows = useMemo(() => [
    {
      industry: t('customers.workflows.real_estate.industry', 'Real estate'),
      icon: Building2,
      accent: 'var(--brand-primary)',
      headline: t('customers.workflows.real_estate.headline', 'Capture and qualify property leads via WhatsApp'),
      body: t('customers.workflows.real_estate.body', 'Run click-to-WhatsApp ads, route enquiries through a bot that asks for budget and locality, then push qualified leads to your CRM. Schedule property reels and Instagram posts from the same Composer.'),
      bullets: [
        t('customers.workflows.real_estate.b1', 'CTWA campaigns with platform-native lead forms'),
        t('customers.workflows.real_estate.b2', 'Visual bot builder for qualification flows'),
        t('customers.workflows.real_estate.b3', 'Brand-voice AI captions per listing'),
      ],
    },
    {
      industry: t('customers.workflows.healthcare.industry', 'Healthcare'),
      icon: Stethoscope,
      accent: '#8b5cf6',
      headline: t('customers.workflows.healthcare.headline', 'Cut no-shows with WhatsApp reminders + a unified inbox'),
      body: t('customers.workflows.healthcare.body', 'Send appointment reminders 24h and 2h before the slot via WhatsApp templates. Reschedule requests land in the same inbox as Instagram DMs and Google reviews — your team works from one queue.'),
      bullets: [
        t('customers.workflows.healthcare.b1', 'Approved WhatsApp template campaigns'),
        t('customers.workflows.healthcare.b2', 'Unified inbox across DMs, reviews, comments'),
        t('customers.workflows.healthcare.b3', 'Per-clinic workspaces with shared brand voice'),
      ],
    },
    {
      industry: t('customers.workflows.agencies.industry', 'Agencies'),
      icon: Users,
      accent: '#f472b6',
      headline: t('customers.workflows.agencies.headline', 'Manage many clients without losing the thread'),
      body: t('customers.workflows.agencies.body', 'A small agency can manage many client workspaces from one Bop Social tenant. Approval flows, white-label reports, and per-client brand voice mean the work scales without a proportional headcount increase.'),
      bullets: [
        t('customers.workflows.agencies.b1', 'Per-client workspace + brand voice'),
        t('customers.workflows.agencies.b2', 'Approval flows for posts and replies'),
        t('customers.workflows.agencies.b3', 'White-label reports on a schedule'),
      ],
    },
    {
      industry: t('customers.workflows.restaurants.industry', 'Restaurants'),
      icon: Utensils,
      accent: '#f59e0b',
      headline: t('customers.workflows.restaurants.headline', 'CTWA bots that take orders and bookings'),
      body: t('customers.workflows.restaurants.body', 'Run Click-to-WhatsApp ads that drop the user into a bot for menu, location, and booking. Route confirmed orders to your POS via webhook. Update Instagram and Google Business with daily specials from one Composer.'),
      bullets: [
        t('customers.workflows.restaurants.b1', 'Menu + booking bots out of the box'),
        t('customers.workflows.restaurants.b2', 'Google Business posts auto-synced'),
        t('customers.workflows.restaurants.b3', 'Per-location workspaces'),
      ],
    },
    {
      industry: t('customers.workflows.ecommerce.industry', 'E-commerce'),
      icon: ShoppingBag,
      accent: '#10b981',
      headline: t('customers.workflows.ecommerce.headline', 'Catalogue ads + WhatsApp checkout'),
      body: t('customers.workflows.ecommerce.body', 'Pull products from Shopify or Woo into Composer. Run carousel ads on Instagram and Facebook with deep links into a WhatsApp catalogue checkout. Reply to inbound messages with AI-suggested replies in your brand voice.'),
      bullets: [
        t('customers.workflows.ecommerce.b1', 'Native product tagging in Composer'),
        t('customers.workflows.ecommerce.b2', 'WhatsApp catalogue sync with inventory'),
        t('customers.workflows.ecommerce.b3', 'ROAS + conversion attribution per campaign'),
      ],
    },
  ], [t]);

  return (
    <MarketingLayout>
      <Meta
        title={t('customers.badge', 'Customers')}
        description={t('customers.hero_subtitle', "Customer stories will appear here as Bop Social launches publicly. In the meantime, here's how the product is built to be used — by industry.")}
      />

      {/* ╭───────────╮
          │  1. HERO  │
          ╰───────────╯ */}
      <section style={{
        position: 'relative',
        padding: '120px 24px 80px',
        overflow: 'hidden',
      }}>
        <MeshGradient variant="hero" />

        <div style={{ position: 'relative', maxWidth: 880, margin: '0 auto', textAlign: 'center' }}>
          <span style={{
            display: 'inline-block',
            padding: '4px 12px', marginBottom: 18,
            fontSize: 11, fontWeight: 700, letterSpacing: '0.08em',
            color: '#fff',
            background: 'rgba(255,255,255,0.12)',
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: 'var(--radius-pill)',
            textTransform: 'uppercase',
          }}>{t('customers.badge', 'Customers')}</span>

          <h1 style={{
            margin: 0,
            fontSize: 'clamp(36px, 6vw, 56px)',
            fontWeight: 700, letterSpacing: '-0.025em',
            lineHeight: 1.1,
            color: '#fff',
          }}>
            {t('customers.hero_title', 'Customer stories — coming soon')}
          </h1>

          <p style={{
            margin: '20px auto 0', maxWidth: 620,
            fontSize: 'clamp(15px, 1.6vw, 17px)',
            lineHeight: 1.55,
            color: 'rgba(255,255,255,0.78)',
          }}>
            {t('customers.hero_subtitle', "We're rolling out Bop Social to a first cohort of launch partners. Real customer stories, with named teams and real numbers, will appear here as those partners go public. Until then, here's how the product is built to be used.")}
          </p>

          <div style={{
            marginTop: 32, display: 'inline-flex', gap: 12, flexWrap: 'wrap',
            justifyContent: 'center',
          }}>
            <Button as={Link} to="/signup" size="lg"
                    style={{
                      background: 'var(--brand-gradient)',
                      color: '#1E202A',
                      border: 'none',
                      fontWeight: 600,
                    }}>
              {t('customers.launch_partner', 'Become a launch partner')} <ArrowRight size={15} />
            </Button>
            <Button as={Link} to="/contact" size="lg" variant="ghost"
                    style={{
                      color: '#fff',
                      background: 'rgba(255,255,255,0.08)',
                      border: '1px solid rgba(255,255,255,0.18)',
                    }}>
              {t('customers.talk_team', 'Talk to the team')}
            </Button>
          </div>
        </div>
      </section>

      {/* ╭──────────────────────────╮
          │  2.  EXAMPLE WORKFLOWS   │
          ╰──────────────────────────╯ */}
      <section style={{
        padding: 'clamp(64px, 10vh, 120px) 24px',
        background: 'var(--surface-page)',
      }}>
        <div style={{ maxWidth: 1180, margin: '0 auto' }}>
          <ScrollReveal>
            <div style={{ textAlign: 'center', marginBottom: 48 }}>
              <span style={{
                display: 'inline-block',
                padding: '3px 10px', marginBottom: 14,
                fontSize: 11, fontWeight: 700,
                color: 'var(--brand-primary-hover)',
                background: 'var(--brand-primary-soft)',
                borderRadius: 'var(--radius-pill)',
                letterSpacing: '0.06em', textTransform: 'uppercase',
              }}>{t('customers.example_workflows_badge', 'Example workflows · illustrative')}</span>
              <h2 style={{
                margin: 0, fontSize: 'clamp(28px, 4vw, 40px)',
                fontWeight: 700, letterSpacing: '-0.02em',
                color: 'var(--text-primary)', lineHeight: 1.15,
              }}>{t('customers.example_workflows_title', 'Built for how your team actually works')}</h2>
              <p style={{
                margin: '14px auto 0', maxWidth: 620,
                fontSize: 16, lineHeight: 1.55,
                color: 'var(--text-secondary)',
              }}>
                {t('customers.sample_disclaimer', 'These are example workflows, not real customer stories. Each describes a typical setup for that industry — the channels, AI features, and approval flows that fit.')}
              </p>
            </div>
          </ScrollReveal>

          <div style={{
            display: 'grid', gap: 16,
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          }}>
            {workflows.map((w, i) => {
              const Icon = w.icon;
              return (
                <ScrollReveal key={w.industry} delay={i * 0.05}>
                  <article style={{
                    height: '100%',
                    padding: 24,
                    background: 'var(--surface-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-lg)',
                    display: 'flex', flexDirection: 'column', gap: 14,
                  }}>
                    <div style={{
                      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                      width: 40, height: 40, borderRadius: 'var(--radius-md)',
                      background: `${w.accent}1A`,
                      color: w.accent,
                    }}>
                      <Icon size={20} strokeWidth={2} />
                    </div>

                    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em',
                                  textTransform: 'uppercase', color: 'var(--text-tertiary)' }}>
                      {w.industry}
                    </div>

                    <h3 style={{
                      margin: 0, fontSize: 17, fontWeight: 700,
                      color: 'var(--text-primary)', lineHeight: 1.3,
                      letterSpacing: '-0.01em',
                    }}>{w.headline}</h3>

                    <p style={{
                      margin: 0, fontSize: 13, lineHeight: 1.55,
                      color: 'var(--text-secondary)',
                    }}>{w.body}</p>

                    <ul style={{
                      margin: 'auto 0 0', padding: 0, listStyle: 'none',
                      display: 'flex', flexDirection: 'column', gap: 6,
                    }}>
                      {w.bullets.map((b) => (
                        <li key={b} style={{
                          display: 'flex', alignItems: 'flex-start', gap: 8,
                          fontSize: 12, color: 'var(--text-secondary)',
                        }}>
                          <span style={{
                            marginTop: 6,
                            width: 4, height: 4, borderRadius: 999,
                            flexShrink: 0,
                            background: w.accent,
                          }} />
                          {b}
                        </li>
                      ))}
                    </ul>
                  </article>
                </ScrollReveal>
              );
            })}
          </div>
        </div>
      </section>

      {/* ╭──────────────╮
          │  3. CTA      │
          ╰──────────────╯ */}
      <section style={{ padding: 'clamp(64px, 10vh, 120px) 24px' }}>
        <div style={{
          maxWidth: 720, margin: '0 auto',
          padding: '48px 32px',
          background: 'var(--surface-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-xl)',
          textAlign: 'center',
        }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            gap: 10, padding: '6px 12px', marginBottom: 16,
            fontSize: 11, fontWeight: 700, letterSpacing: '0.06em',
            color: 'var(--brand-primary-hover)',
            background: 'var(--brand-primary-soft)',
            borderRadius: 'var(--radius-pill)', textTransform: 'uppercase',
          }}>
            <Sparkles size={12} /> {t('customers.launch_partner', 'Launch partner programme')}
          </div>
          <h2 style={{
            margin: 0,
            fontSize: 'clamp(24px, 3.6vw, 32px)',
            fontWeight: 700, letterSpacing: '-0.02em',
            color: 'var(--text-primary)', lineHeight: 1.2,
          }}>
            {t('customers.cta_title', 'Be the first customer story on this page')}
          </h2>
          <p style={{
            margin: '14px auto 0', maxWidth: 520,
            fontSize: 15, lineHeight: 1.55,
            color: 'var(--text-secondary)',
          }}>
            {t('customers.cta_subtitle', "Launch-partner teams get hands-on onboarding, a direct line to the team, and a feature spot here when they're ready to share their numbers.")}
          </p>
          <div style={{
            marginTop: 28, display: 'inline-flex', gap: 12,
            justifyContent: 'center', flexWrap: 'wrap',
          }}>
            <Button as={Link} to="/signup" size="lg" variant="primary">
              {t('common:actions.start_free', 'Start free')} <ArrowRight size={15} />
            </Button>
            <Button as={Link} to="/contact" size="lg" variant="ghost">
              {t('customers.talk_team', 'Talk to the team')}
            </Button>
          </div>
        </div>
      </section>
    </MarketingLayout>
  );
}
