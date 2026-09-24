/* ============================================================================
 *  Bop Social — Marketing Operating System
 *  Author    : Bop Social Team
 *  Website   : https://bopsocial.com
 * ========================================================================== */
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import {
  ArrowRight, Sparkles, Building2, TrendingUp, Star, Inbox, Wand2,
  ShieldCheck, Check, Users2,
} from 'lucide-react';

import MarketingLayout from '../components/marketing/MarketingLayout';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import Meta from '../components/Meta';


export default function ForAgenciesPage() {
  const { t } = useTranslation(['marketing', 'navigation']);

  return (
    <MarketingLayout>
      <Meta
        title={t('metadata.for_agencies_title')}
        description={t('metadata.for_agencies_desc')}
      />
      <Hero t={t} />
      <ROIBand t={t} />
      <MarketplaceExposure t={t} />
      <FeatureBlocks t={t} />
      <FinalCTA t={t} />
    </MarketingLayout>
  );
}


function Hero({ t }) {
  return (
    <section style={{ position: 'relative', overflow: 'hidden', padding: '128px 32px 72px' }}>
      <div aria-hidden style={meshBg} />
      <div style={{ position: 'relative', maxWidth: 880, margin: '0 auto', textAlign: 'center' }}>
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <Badge variant="brand" icon={Building2} size="md">{t('for_agencies.badge')}</Badge>
        </motion.div>
        <motion.h1
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05 }}
          style={{
            margin: '20px 0 16px',
            fontSize: 'clamp(36px, 5.2vw, 60px)',
            lineHeight: 1.06, letterSpacing: '-0.03em',
            fontWeight: 600, color: 'var(--text-primary)',
          }}
        >
          {t('for_agencies.hero_title_pre')}
          <span style={{ backgroundImage: 'var(--brand-gradient)', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>
            {t('for_agencies.hero_title_highlight')}
          </span>
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          style={{ margin: '0 auto', maxWidth: 640, fontSize: 18, lineHeight: 1.6, color: 'var(--text-secondary)' }}
        >
          {t('for_agencies.hero_subtitle')}
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          style={{ marginTop: 28, display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}
        >
          <Button as={Link} to="/signup" size="xl" iconRight={ArrowRight}>
            {t('for_agencies.cta_start')}
          </Button>
          <Button as={Link} to="/agencies" size="xl" variant="secondary" icon={Building2}>
            {t('for_agencies.cta_marketplace')}
          </Button>
        </motion.div>
        <p style={{ marginTop: 14, fontSize: 13, color: 'var(--text-tertiary)' }}>
          {t('for_agencies.micro')}
        </p>
      </div>
    </section>
  );
}


function ROIBand({ t }) {
  const items = t('for_agencies.roi', { returnObjects: true }) || [];
  return (
    <section style={{ padding: '40px 32px', background: 'var(--surface-card)', borderTop: '1px solid var(--border-subtle)', borderBottom: '1px solid var(--border-subtle)' }}>
      <div style={{ maxWidth: 'var(--container-2xl)', margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14 }}>
        {Array.isArray(items) && items.map((it) => (
          <div key={it.label} style={{ textAlign: 'center', padding: '14px 12px' }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
              {it.stat}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 4 }}>{it.label}</div>
          </div>
        ))}
      </div>
    </section>
  );
}


function MarketplaceExposure({ t }) {
  const bullets = t('for_agencies.marketplace_bullets', { returnObjects: true }) || [];
  return (
    <section style={{ padding: '72px 32px' }}>
      <div style={{ maxWidth: 920, margin: '0 auto', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 40, alignItems: 'center' }} className="fa-grid">
        <div>
          <Badge variant="brand" icon={Star} size="md">{t('for_agencies.marketplace_badge')}</Badge>
          <h2 style={{ margin: '14px 0 10px', fontSize: 28, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
            {t('for_agencies.marketplace_title')}
          </h2>
          <p style={{ margin: '0 0 20px', fontSize: 15, color: 'var(--text-secondary)', lineHeight: 1.65 }}>
            {t('for_agencies.marketplace_subtitle')}
          </p>
          <Button as={Link} to="/agencies" variant="secondary" size="md" icon={Building2}>
            {t('for_agencies.marketplace_cta')}
          </Button>
        </div>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {Array.isArray(bullets) && bullets.map((s) => (
            <li key={s} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 14, color: 'var(--text-primary)' }}>
              <Check size={16} style={{ color: 'var(--success)', flexShrink: 0, marginTop: 2 }} />
              <span>{s}</span>
            </li>
          ))}
        </ul>
      </div>
      <style>{`@media (max-width: 880px) { .fa-grid { grid-template-columns: 1fr !important; gap: 28px !important; } }`}</style>
    </section>
  );
}


function FeatureBlocks({ t }) {
  const items = [
    { icon: TrendingUp,  title: t('for_agencies.items.analytics.title'), body: t('for_agencies.items.analytics.body') },
    { icon: Inbox,       title: t('for_agencies.items.inbox.title'),     body: t('for_agencies.items.inbox.body') },
    { icon: Wand2,       title: t('for_agencies.items.composer.title'),  body: t('for_agencies.items.composer.body') },
    { icon: Users2,      title: t('for_agencies.items.whatsapp.title'),  body: t('for_agencies.items.whatsapp.body') },
    { icon: ShieldCheck, title: t('for_agencies.items.trust.title'),     body: t('for_agencies.items.trust.body') },
    { icon: Sparkles,    title: t('for_agencies.items.ai.title'),        body: t('for_agencies.items.ai.body') },
  ];
  return (
    <section style={{ padding: '64px 32px', background: 'var(--surface-card)' }}>
      <div style={{ maxWidth: 'var(--container-2xl)', margin: '0 auto' }}>
        <h2 style={sectionH}>{t('for_agencies.features_title')}</h2>
        <p style={sectionSub}>{t('for_agencies.features_subtitle')}</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16, marginTop: 32 }}>
          {items.map((it) => (
            <article key={it.title} style={featureCard}>
              <span style={{
                width: 36, height: 36, borderRadius: 'var(--radius-md)',
                background: 'var(--brand-primary-glow)', color: 'var(--brand-primary-hover)',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: 12,
              }}>
                <it.icon size={18} strokeWidth={2.2} />
              </span>
              <h3 style={{ margin: '0 0 6px', fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>{it.title}</h3>
              <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.55 }}>{it.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}


function FinalCTA({ t }) {
  return (
    <section style={{ padding: '72px 32px', background: 'var(--surface-card)', borderTop: '1px solid var(--border-subtle)' }}>
      <div style={{ maxWidth: 720, margin: '0 auto', textAlign: 'center' }}>
        <h2 style={{ margin: 0, fontSize: 30, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
          {t('for_agencies.final_title')}
        </h2>
        <p style={{ margin: '8px 0 22px', fontSize: 15, color: 'var(--text-secondary)' }}>
          {t('for_agencies.final_subtitle')}
        </p>
        <Button as={Link} to="/signup" size="xl" iconRight={ArrowRight}>
          {t('for_agencies.final_button')}
        </Button>
      </div>
    </section>
  );
}


const sectionH = {
  margin: 0,
  fontSize: 32, fontWeight: 700,
  color: 'var(--text-primary)', letterSpacing: '-0.025em',
  textAlign: 'center',
};
const sectionSub = {
  margin: '8px auto 0', maxWidth: 580,
  fontSize: 15, color: 'var(--text-secondary)',
  textAlign: 'center', lineHeight: 1.6,
};
const featureCard = {
  padding: 20,
  background: 'var(--surface-page)',
  border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--radius-lg)',
};
const meshBg = {
  position: 'absolute', inset: 0,
  background: 'var(--brand-mesh)',
  opacity: 0.45, filter: 'blur(80px) saturate(140%)', zIndex: 0,
};
