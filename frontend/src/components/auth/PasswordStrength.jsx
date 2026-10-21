/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
/**
 * PasswordStrength — small meter rendered under password fields.
 *
 * Score ranges 0..4 based on length, casing, digits, symbols. This is an
 * affordance, not validation — the backend remains the source of truth.
 */
import { useTranslation } from 'react-i18next';

const LEVELS = [
  { key: 'very_weak', label: 'Very weak', color: 'var(--danger)',  width: '20%' },
  { key: 'weak',      label: 'Weak',      color: 'var(--danger)',  width: '40%' },
  { key: 'fair',      label: 'Fair',      color: 'var(--warning)', width: '60%' },
  { key: 'good',      label: 'Good',      color: 'var(--info)',    width: '80%' },
  { key: 'strong',    label: 'Strong',    color: 'var(--success)', width: '100%' },
];

export function scorePassword(pw) {
  if (!pw) return 0;
  let score = 0;
  if (pw.length >= 8)  score += 1;
  if (pw.length >= 12) score += 1;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score += 1;
  if (/\d/.test(pw))   score += 1;
  if (/[^A-Za-z0-9]/.test(pw)) score += 1;
  return Math.min(4, score);
}

export default function PasswordStrength({ password = '', show = true }) {
  const { t } = useTranslation('auth');
  if (!show || !password) return null;
  const s = scorePassword(password);
  const lvl = LEVELS[s];
  const translatedLabel = t(`password_strength.${lvl.key}`, lvl.label);

  return (
    <div style={{ marginTop: 6 }}>
      <div
        style={{
          height: 4,
          width: '100%',
          background: 'var(--surface-sunken)',
          borderRadius: 999,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: lvl.width,
            background: lvl.color,
            borderRadius: 999,
            transition: 'width var(--transition-default), background var(--transition-default)',
          }}
        />
      </div>
      <div
        style={{
          marginTop: 4,
          fontSize: 11,
          color: lvl.color,
          fontWeight: 500,
        }}
      >
        {t('password_strength.label', 'Password strength:')} {translatedLabel}
      </div>
    </div>
  );
}
