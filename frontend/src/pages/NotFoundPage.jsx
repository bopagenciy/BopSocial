/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Search, ArrowRight, Home, BookOpen } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import MarketingLayout from '../components/marketing/MarketingLayout';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Meta from '../components/Meta';

export default function NotFoundPage() {
  const { t } = useTranslation(['marketing', 'common']);
  const navigate = useNavigate();

  function handleSearch(e) {
    e.preventDefault();
    const q = new FormData(e.currentTarget).get('q');
    navigate(`/help?q=${encodeURIComponent(q || '')}`);
  }

  return (
    <MarketingLayout>
      <Meta
        title={t('metadata.not_found_title', 'Page Not Found')}
        description={t('errors.not_found_desc', "The page you're looking for doesn't exist, has moved, or was never here.")}
      />
      <section
        style={{
          padding: '160px 32px 120px',
          textAlign: 'center',
          position: 'relative',
          overflow: 'hidden',
          minHeight: 'calc(100vh - 200px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          aria-hidden
          style={{
            position: 'absolute', inset: 0,
            background: 'var(--brand-mesh)',
            opacity: 0.30, filter: 'blur(80px) saturate(140%)',
          }}
        />

        <div style={{ position: 'relative', maxWidth: 560, margin: '0 auto' }}>
          {/* Animated 404 mark */}
          <motion.div
            initial={{ scale: 0.92, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            style={{
              fontSize: 'clamp(96px, 18vw, 180px)',
              fontWeight: 700,
              letterSpacing: '-0.06em',
              lineHeight: 0.9,
              backgroundImage: 'var(--brand-gradient)',
              WebkitBackgroundClip: 'text',
              backgroundClip: 'text',
              color: 'transparent',
              marginBottom: 12,
            }}
          >
            {t('errors.not_found_code', '404')}
          </motion.div>

          <h1 style={{
            margin: 0,
            fontSize: 'clamp(28px, 3.4vw, 36px)',
            fontWeight: 600,
            letterSpacing: '-0.025em',
            color: 'var(--text-primary)',
          }}>
            {t('errors.not_found_title', 'Page not found')}
          </h1>
          <p style={{ margin: '12px auto 28px', maxWidth: 440, fontSize: 16, lineHeight: 1.65, color: 'var(--text-secondary)' }}>
            {t('errors.not_found_desc', "The page you're looking for doesn't exist, has moved, or was never here.")}
          </p>

          <form onSubmit={handleSearch} style={{ maxWidth: 420, margin: '0 auto 24px' }}>
            <Input
              name="q"
              type="search"
              size="lg"
              placeholder={t('help.search_placeholder', 'Search the help center…')}
              prefix={<Search size={16} />}
            />
          </form>

          <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Button as={Link} to="/" size="lg" icon={Home}>{t('errors.back_home', 'Go home')}</Button>
            <Button as={Link} to="/help" variant="secondary" size="lg" icon={BookOpen} iconRight={ArrowRight}>
              {t('resources.help_center', 'Help center')}
            </Button>
          </div>
        </div>
      </section>
    </MarketingLayout>
  );
}
