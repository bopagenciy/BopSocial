/* ============================================================================
 *  Bop Social — Marketing Operating System
 *  Author    : Bop Social Team
 *  Website   : https://bopsocial.com
 * ========================================================================== */
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ShieldCheck, Lock, Server, FileCheck, Eye, AlertTriangle, ArrowRight, Award } from 'lucide-react';
import MarketingLayout from '../components/marketing/MarketingLayout';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import Meta from '../components/Meta';

const COMMITMENTS = [
  { id: 'encryption',     icon: Lock,      color: '#3b82f6', defaultTitle: 'Encryption everywhere',   defaultBody: 'TLS 1.3 in transit. AES-256-GCM (Fernet) at rest for OAuth tokens, API keys, and customer secrets. Keys rotated quarterly.' },
  { id: 'infrastructure', icon: Server,    color: '#10b981', defaultTitle: 'Hardened infrastructure', defaultBody: 'AWS multi-AZ deployments. Per-environment isolation. WAF + DDoS mitigation. Automated patching + vulnerability scans daily.' },
  { id: 'audit',          icon: Eye,       color: '#8b5cf6', defaultTitle: 'Audit log, always-on',     defaultBody: 'Every action — auth, OAuth connect, publish, role change — is logged with actor, timestamp, IP, and result. Searchable for 1 year on Growth, custom on Enterprise.' },
  { id: 'compliance',     icon: FileCheck, color: '#f59e0b', defaultTitle: 'Compliance-ready',        defaultBody: 'GDPR + India DPDP compliant by design. SOC 2 Type II in progress (target Q3 2026). HIPAA, ISO 27001 on Enterprise contracts.' },
];

const CERTIFICATIONS = [
  { id: 'gdpr', defaultName: 'GDPR',          defaultStatus: 'Compliant',   defaultDesc: 'EU/EEA data protection.' },
  { id: 'dpdp', defaultName: 'India DPDP',    defaultStatus: 'Compliant',   defaultDesc: 'Indian Data Protection Act 2023.' },
  { id: 'soc2', defaultName: 'SOC 2 Type II', defaultStatus: 'In progress', defaultDesc: 'Audit underway, expected Q3 2026.' },
  { id: 'iso',  defaultName: 'ISO 27001',     defaultStatus: 'Roadmap',     defaultDesc: 'Targeted for 2027.' },
];

export default function SecurityPage() {
  const { t } = useTranslation(['marketing', 'navigation']);

  return (
    <MarketingLayout>
      <Meta
        title={t('metadata.security_title')}
        description={t('metadata.security_desc')}
      />
      {/* Hero */}
      <section style={{ padding: '128px 32px 56px', textAlign: 'center', position: 'relative', overflow: 'hidden' }}>
        <div
          aria-hidden
          style={{
            position: 'absolute', inset: 0,
            background: 'var(--brand-mesh)',
            opacity: 0.30, filter: 'blur(80px) saturate(140%)',
          }}
        />
        <div style={{ position: 'relative', maxWidth: 760, margin: '0 auto' }}>
          <Badge variant="brand" size="md" icon={ShieldCheck}>{t('security.badge')}</Badge>
          <h1 style={{
            margin: '20px 0 18px',
            fontSize: 'clamp(40px, 5vw, 56px)',
            lineHeight: 1.05,
            letterSpacing: '-0.03em',
            fontWeight: 600,
            color: 'var(--text-primary)',
          }}>
            {t('security.hero_title')}
          </h1>
          <p style={{ margin: 0, fontSize: 18, lineHeight: 1.65, color: 'var(--text-secondary)' }}>
            {t('security.hero_subtitle')}
          </p>
        </div>
      </section>

      {/* Commitments grid */}
      <section style={{ padding: '32px 32px 96px' }}>
        <div
          style={{
            maxWidth: 'var(--container-xl)',
            margin: '0 auto',
            display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
            gap: 20,
          }}
          className="security-grid"
        >
          {COMMITMENTS.map((c) => (
            <article
              key={c.id}
              style={{
                padding: 28,
                background: 'var(--surface-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-xl)',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <span style={{
                display: 'inline-flex',
                width: 40, height: 40,
                borderRadius: 'var(--radius-md)',
                background: c.color, color: '#fff',
                alignItems: 'center', justifyContent: 'center',
                marginBottom: 14,
              }}>
                <c.icon size={18} strokeWidth={2.2} />
              </span>
              <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em', color: 'var(--text-primary)' }}>
                {t(`security.commitments.${c.id}.title`, c.defaultTitle)}
              </h3>
              <p style={{ margin: '8px 0 0', fontSize: 14, lineHeight: 1.65, color: 'var(--text-secondary)' }}>
                {t(`security.commitments.${c.id}.body`, c.defaultBody)}
              </p>
            </article>
          ))}
        </div>
        <style>{`
          @media (max-width: 880px) { .security-grid { grid-template-columns: 1fr !important; } }
        `}</style>
      </section>

      {/* Certifications */}
      <section style={{ padding: '64px 32px', background: 'var(--surface-card)', borderTop: '1px solid var(--border-subtle)', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ maxWidth: 'var(--container-xl)', margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: 32 }}>
            <h2 style={{ margin: 0, fontSize: 'clamp(28px, 3.4vw, 36px)', fontWeight: 600, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
              {t('security.certifications_title')}
            </h2>
            <p style={{ margin: '12px auto 0', maxWidth: 560, fontSize: 15, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {t('security.certifications_subtitle')}
            </p>
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
              gap: 16,
            }}
            className="security-cert-grid"
          >
            {CERTIFICATIONS.map((cert) => {
              const name = t(`security.certifications.${cert.id}.name`, cert.defaultName);
              const status = t(`security.certifications.${cert.id}.status`, cert.defaultStatus);
              const desc = t(`security.certifications.${cert.id}.description`, cert.defaultDesc);
              return (
                <div
                  key={cert.id}
                  style={{
                    padding: 20,
                    background: 'var(--surface-page)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-lg)',
                  }}
                >
                  <span style={{
                    display: 'inline-flex',
                    width: 36, height: 36,
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--brand-primary-soft)',
                    color: 'var(--brand-primary-hover)',
                    alignItems: 'center', justifyContent: 'center',
                    marginBottom: 12,
                  }}>
                    <Award size={16} strokeWidth={2.2} />
                  </span>
                  <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
                    {name}
                  </div>
                  <div style={{ marginTop: 4 }}>
                    <Badge
                      size="sm"
                      variant={status === 'Compliant' || status === 'En cumplimiento' ? 'success' : status === 'In progress' || status === 'En progreso' ? 'warning' : 'default'}
                    >
                      {status}
                    </Badge>
                  </div>
                  <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    {desc}
                  </p>
                </div>
              );
            })}
          </div>
          <style>{`
            @media (max-width: 980px) { .security-cert-grid { grid-template-columns: 1fr 1fr !important; } }
            @media (max-width: 480px) { .security-cert-grid { grid-template-columns: 1fr !important; } }
          `}</style>
        </div>
      </section>

      {/* Bug bounty + reporting */}
      <section style={{ padding: '96px 32px' }}>
        <div
          style={{
            maxWidth: 800, margin: '0 auto',
            padding: 40,
            background: 'var(--surface-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-2xl)',
            boxShadow: 'var(--shadow-md)',
            display: 'flex', gap: 24, alignItems: 'flex-start',
          }}
          className="security-bounty"
        >
          <span
            style={{
              flexShrink: 0,
              width: 56, height: 56,
              borderRadius: 'var(--radius-lg)',
              background: 'var(--danger-bg)',
              color: 'var(--danger)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <AlertTriangle size={26} strokeWidth={1.8} />
          </span>
          <div style={{ minWidth: 0, flex: 1 }}>
            <h3 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: '-0.015em', color: 'var(--text-primary)' }}>
              {t('security.vulnerability_title')}
            </h3>
            <p style={{ margin: '8px 0 16px', fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.65 }}>
              {t('security.vulnerability_body', {
                defaultValue: "We run a private vulnerability disclosure program with competitive rewards for verified critical issues. Email security@bopsocial.com with reproduction steps and impact assessment. We acknowledge within 24 hours and triage within 72.",
              })}
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Button as="a" href="mailto:security@bopsocial.com" size="md" iconRight={ArrowRight}>
                {t('security.report_button')}
              </Button>
              <Button as={Link} to="/status" variant="secondary" size="md">
                {t('security.status_button')}
              </Button>
            </div>
          </div>
          <style>{`
            @media (max-width: 640px) { .security-bounty { flex-direction: column !important; } }
          `}</style>
        </div>
      </section>

      {/* Bottom links */}
      <section style={{ padding: '0 32px 120px', textAlign: 'center' }}>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-tertiary)' }}>
          {t('security.footer_looking')}{' '}
          <Link to="/privacy" style={{ color: 'var(--text-link)', fontWeight: 500 }}>{t('security.footer_privacy')}</Link>,{' '}
          <Link to="/gdpr"    style={{ color: 'var(--text-link)', fontWeight: 500 }}>{t('security.footer_gdpr')}</Link>,{' '}
          {t('common.or', 'or')} <Link to="/dpdp" style={{ color: 'var(--text-link)', fontWeight: 500 }}>{t('security.footer_dpdp')}</Link>?
        </p>
      </section>
    </MarketingLayout>
  );
}
