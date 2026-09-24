/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
/**
 * ResetPasswordPage — handles two flows:
 *   /forgot-password           → request reset link (email → success state)
 *   /reset-password?token=UUID → confirm new password
 */
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, AlertCircle, CheckCircle, Mail } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import AuthLayout from '../components/auth/AuthLayout';
import PasswordStrength from '../components/auth/PasswordStrength';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import { authAPI } from '../services/api';

export default function ResetPasswordPage() {
  const token = new URLSearchParams(window.location.search).get('token');
  return token ? <ResetForm token={token} /> : <ForgotForm />;
}

// ─── Forgot password (request reset link) ────────────────────────────────
function ForgotForm() {
  const { t } = useTranslation('auth');
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!email.trim()) { setError(t('forgot_password.validation.email_required', 'Email is required.')); return; }
    setError('');
    setLoading(true);
    try {
      await authAPI.passwordResetRequest(email.trim().toLowerCase());
      setDone(true);
    } catch {
      setError(t('common.something_went_wrong', 'Something went wrong. Please try again.'));
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <AuthLayout
        heroTitle={t('forgot_password.check_email_title', 'Check your inbox')}
        heroSub={t('forgot_password.check_email_desc', 'If {{email}} is registered, a password reset link is on its way.', { email })}
      >
        <div style={{ ...cardStyle, textAlign: 'center' }}>
          <div aria-hidden style={iconBubbleStyle}>
            <Mail size={26} strokeWidth={1.8} />
          </div>
          <h1 style={titleStyle}>{t('forgot_password.check_email_title', 'Check your inbox')}</h1>
          <p style={{ ...subStyle, margin: '8px 0 20px' }}>
            {t('forgot_password.check_email_desc', 'If {{email}} is registered, a password reset link is on its way.', { email })}
          </p>
          <Button as={Link} to="/login" variant="secondary" size="md" fullWidth>
            {t('forgot_password.back_to_login', 'Back to sign in')}
          </Button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      footer={
        <>
          <Link to="/login" style={{ color: 'var(--text-link)', fontWeight: 600, textDecoration: 'none' }}>
            {t('forgot_password.back_to_login', 'Back to sign in')}
          </Link>
        </>
      }
    >
      <div style={cardStyle}>
        <header style={{ marginBottom: 22 }}>
          <h1 style={titleStyle}>{t('forgot_password.title', 'Reset your password')}</h1>
          <p style={subStyle}>{t('forgot_password.subtitle', "Enter your email — we'll send a secure link to reset your password.")}</p>
        </header>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Input
            label={t('forgot_password.email_label', 'Email address')}
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => { setEmail(e.target.value); setError(''); }}
            placeholder={t('forgot_password.email_placeholder', 'you@company.com')}
            error={error}
            size="lg"
            autoFocus
          />
          <Button type="submit" size="lg" iconRight={ArrowRight} fullWidth loading={loading}>
            {loading ? t('forgot_password.submitting', 'Sending link...') : t('forgot_password.submit_button', 'Send reset link')}
          </Button>
        </form>
      </div>
    </AuthLayout>
  );
}

// ─── Reset password (confirm new password) ───────────────────────────────
function ResetForm({ token }) {
  const { t } = useTranslation('auth');
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [serverError, setServerError] = useState('');

  function clearField(field) {
    setErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }

  function validate() {
    const e = {};
    if (!password) e.password = t('reset_password.validation.password_required', 'Password is required.');
    else if (password.length < 8) e.password = t('reset_password.validation.password_length', 'Password must be at least 8 characters.');
    if (!confirm) e.confirm = t('reset_password.validation.confirm_required', 'Please confirm your password.');
    else if (password !== confirm) e.confirm = t('reset_password.validation.passwords_mismatch', 'Passwords do not match.');
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(ev) {
    ev.preventDefault();
    setServerError('');
    if (!validate()) return;
    setLoading(true);
    try {
      await authAPI.passwordResetConfirm(token, password);
      setDone(true);
      setTimeout(() => navigate('/login', { replace: true }), 2200);
    } catch (err) {
      const data = err?.response?.data;
      if (data?.errors?.password) setErrors((p) => ({ ...p, password: data.errors.password }));
      else setServerError(data?.error || t('verify_email.failed_default', 'This reset link is invalid or has expired.'));
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <AuthLayout
        heroTitle={t('reset_password.success_title', 'Password updated!')}
        heroSub={t('reset_password.success_subtitle', 'Your password has been changed successfully. Redirecting to sign in...')}
      >
        <div style={{ ...cardStyle, textAlign: 'center' }}>
          <div aria-hidden style={{ ...iconBubbleStyle, background: 'var(--success-bg)', color: 'var(--success)' }}>
            <CheckCircle size={26} strokeWidth={1.8} />
          </div>
          <h1 style={titleStyle}>{t('reset_password.success_title', 'Password updated!')}</h1>
          <p style={subStyle}>{t('reset_password.success_subtitle', 'Your password has been changed successfully. Redirecting to sign in...')}</p>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      footer={
        <Link to="/login" style={{ color: 'var(--text-link)', fontWeight: 600, textDecoration: 'none' }}>
          {t('forgot_password.back_to_login', 'Back to sign in')}
        </Link>
      }
    >
      <div style={cardStyle}>
        <header style={{ marginBottom: 22 }}>
          <h1 style={titleStyle}>{t('reset_password.title', 'Set new password')}</h1>
          <p style={subStyle}>{t('reset_password.subtitle', 'Choose a strong password with at least 8 characters.')}</p>
        </header>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <Input
              label={t('reset_password.new_password_label', 'New password')}
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); clearField('password'); }}
              placeholder={t('reset_password.new_password_placeholder', 'At least 8 characters')}
              error={errors.password}
              size="lg"
              autoFocus
            />
            <PasswordStrength password={password} />
          </div>

          <Input
            label={t('reset_password.confirm_password_label', 'Confirm new password')}
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => { setConfirm(e.target.value); clearField('confirm'); }}
            placeholder={t('reset_password.confirm_password_placeholder', 'Re-enter your new password')}
            error={errors.confirm}
            success={!!confirm && confirm === password && password.length >= 8 && !errors.confirm}
            size="lg"
          />

          {serverError && (
            <div
              role="alert"
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 8,
                padding: '10px 12px',
                background: 'var(--danger-bg)',
                border: '1px solid var(--danger)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--danger)',
                fontSize: 13,
              }}
            >
              <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{serverError}</span>
            </div>
          )}

          <Button type="submit" size="lg" iconRight={ArrowRight} fullWidth loading={loading}>
            {loading ? t('reset_password.submitting', 'Updating...') : t('reset_password.submit_button', 'Update password')}
          </Button>
        </form>
      </div>
    </AuthLayout>
  );
}

// ── shared styles ────────────────────────────────────────────────────────
const cardStyle = {
  background: 'var(--surface-card)',
  border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--radius-xl)',
  padding: 32,
  boxShadow: 'var(--shadow-md)',
  textAlign: 'left',
};

const iconBubbleStyle = {
  width: 56,
  height: 56,
  margin: '0 auto 16px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'var(--brand-primary-soft)',
  borderRadius: '50%',
  color: 'var(--brand-primary-hover)',
};

const titleStyle = {
  margin: 0,
  fontSize: 22,
  fontWeight: 600,
  letterSpacing: '-0.02em',
  color: 'var(--text-primary)',
};

const subStyle = {
  margin: '6px 0 0',
  fontSize: 14,
  color: 'var(--text-secondary)',
  lineHeight: 1.6,
};
