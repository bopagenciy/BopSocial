/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
/**
 * SignupPage — /signup?invite=TOKEN
 * Email/password signup for clients. Also supports Google/Facebook social signup.
 * After submit → "check your email" success state with resend.
 */
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, AlertCircle, CheckCircle, Mail, RefreshCw, Building2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import AuthLayout from '../components/auth/AuthLayout';
import PasswordStrength from '../components/auth/PasswordStrength';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Checkbox from '../components/ui/Checkbox';
import Confetti from '../components/ui/Confetti';
import SocialPlatformIcon from '../components/ui/SocialPlatformIcon';
import { useAuth } from '../hooks/useAuth';
import { authAPI, invitationAPI } from '../services/api';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

export default function SignupPage() {
  const { t } = useTranslation(['auth', 'common']);
  const navigate = useNavigate();
  const { user } = useAuth();
  const params = new URLSearchParams(window.location.search);
  const inviteToken = params.get('invite');

  const [inv, setInv] = useState(null);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPwd, setConfirmPwd] = useState('');
  const [accepted, setAccepted] = useState(false);
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [resending, setResending] = useState(false);
  const [resentMsg, setResentMsg] = useState('');

  // Redirect already-logged-in users
  useEffect(() => {
    if (user) navigate('/dashboard', { replace: true });
  }, [user, navigate]);

  // Fetch invitation preview
  useEffect(() => {
    if (!inviteToken) return;
    invitationAPI.getByToken(inviteToken).then((res) => setInv(res.data)).catch(() => {});
    localStorage.setItem('pending_invite_token', inviteToken);
  }, [inviteToken]);

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
    if (!fullName.trim()) e.fullName = t('signup.validation.full_name_required', 'Full name is required.');
    if (!email.trim()) e.email = t('signup.validation.email_required', 'Email is required.');
    else if (!/\S+@\S+\.\S+/.test(email)) e.email = t('signup.validation.email_invalid', 'Enter a valid email address.');
    if (!password) e.password = t('signup.validation.password_required', 'Password is required.');
    else if (password.length < 8) e.password = t('signup.validation.password_length', 'Password must be at least 8 characters.');
    if (!confirmPwd) e.confirmPwd = t('signup.validation.confirm_required', 'Please confirm your password.');
    else if (password !== confirmPwd) e.confirmPwd = t('signup.validation.passwords_mismatch', 'Passwords do not match.');
    if (!accepted) e.terms = t('signup.validation.terms_required', 'You must accept the Terms of Service.');
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(ev) {
    ev.preventDefault();
    setServerError('');
    if (!validate()) return;
    setLoading(true);
    try {
      await authAPI.signup({
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        password,
        terms_accepted: true,
      });
      setDone(true);
    } catch (err) {
      const data = err?.response?.data;
      if (data?.errors) {
        const m = {};
        if (data.errors.full_name) m.fullName = data.errors.full_name;
        if (data.errors.email) m.email = data.errors.email;
        if (data.errors.password) m.password = data.errors.password;
        setErrors(m);
      } else {
        setServerError(data?.detail || t('common.something_went_wrong', 'Something went wrong. Please try again.'));
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    setResending(true);
    setResentMsg('');
    try {
      await authAPI.resendVerification(email);
      setResentMsg(t('signup.email_resent', 'A new verification email has been sent.'));
    } catch {
      setResentMsg(t('common.something_went_wrong', 'Could not resend. Please try again.'));
    } finally {
      setResending(false);
    }
  }

  function handleGoogle() {
    if (inviteToken) localStorage.setItem('pending_invite_token', inviteToken);
    window.location.href = `${API_BASE}/auth/social/google/start/`;
  }
  function handleFacebook() {
    if (inviteToken) localStorage.setItem('pending_invite_token', inviteToken);
    window.location.href = `${API_BASE}/auth/social/facebook/start/`;
  }

  // ───────────────────────────── Success state ─────────────────────────────
  if (done) {
    return (
      <>
        <Confetti />
        <AuthLayout
          heroTitle={t('signup.check_email_title', 'Check your email')}
          heroSub={t('signup.check_email_instruction', 'Click the link in the email to activate your account and continue setup.')}
        >
        <div
          style={{
            background: 'var(--surface-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-xl)',
            padding: 32,
            boxShadow: 'var(--shadow-md)',
            textAlign: 'center',
          }}
        >
          <div
            aria-hidden
            style={{
              width: 56, height: 56,
              margin: '0 auto 16px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'var(--brand-primary-soft)',
              borderRadius: '50%',
              color: 'var(--brand-primary-hover)',
            }}
          >
            <Mail size={26} strokeWidth={1.8} />
          </div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: '-0.01em', color: 'var(--text-primary)' }}>
            {t('signup.check_email_title', 'Check your email')}
          </h1>
          <p style={{ margin: '8px 0 20px', fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {t('signup.check_email_desc', 'We sent a verification link to')} <strong style={{ color: 'var(--text-primary)' }}>{email}</strong>.{' '}
            {t('signup.check_email_instruction', 'Click the link in the email to activate your account and continue setup.')}
          </p>

          {resentMsg && (
            <div
              role="status"
              style={{
                padding: '10px 12px',
                marginBottom: 14,
                background: resentMsg === t('signup.email_resent', 'A new verification email has been sent.') ? 'var(--success-bg)' : 'var(--danger-bg)',
                border: `1px solid ${resentMsg === t('signup.email_resent', 'A new verification email has been sent.') ? 'var(--success)' : 'var(--danger)'}`,
                borderRadius: 'var(--radius-md)',
                color: resentMsg === t('signup.email_resent', 'A new verification email has been sent.') ? 'var(--success)' : 'var(--danger)',
                fontSize: 13,
              }}
            >
              {resentMsg}
            </div>
          )}

          <Button
            variant="secondary"
            size="md"
            icon={RefreshCw}
            fullWidth
            loading={resending}
            onClick={handleResend}
          >
            {t('signup.resend_email', 'Resend verification email')}
          </Button>
          <div style={{ marginTop: 14, fontSize: 13, color: 'var(--text-secondary)' }}>
            {t('signup.already_have_account', 'Already have an account?')}{' '}
            <Link to="/login" style={{ color: 'var(--text-link)', fontWeight: 600, textDecoration: 'none' }}>
              {t('signup.sign_in', 'Sign in')}
            </Link>
          </div>
        </div>
        </AuthLayout>
      </>
    );
  }

  // ───────────────────────────── Form state ──────────────────────────────────
  return (
    <AuthLayout
      footer={
        <>
          {t('signup.already_have_account', 'Already have an account?')}{' '}
          <Link to="/login" style={{ color: 'var(--text-link)', fontWeight: 600, textDecoration: 'none' }}>
            {t('signup.sign_in', 'Sign in')}
          </Link>
        </>
      }
    >
      <div
        style={{
          background: 'var(--surface-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-xl)',
          padding: 32,
          boxShadow: 'var(--shadow-md)',
        }}
      >
        <header style={{ marginBottom: 22 }}>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
            {t('signup.title', 'Create your account')}
          </h1>
          <p style={{ margin: '6px 0 0', fontSize: 14, color: 'var(--text-secondary)' }}>
            {t('signup.subtitle', 'Start managing your social media channels today.')}
          </p>
        </header>

        {inv && (
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
              padding: '10px 12px',
              marginBottom: 18,
              background: 'var(--brand-primary-soft)',
              border: '1px solid var(--brand-primary-glow)',
              borderRadius: 'var(--radius-md)',
              fontSize: 13,
              color: 'var(--text-secondary)',
            }}
          >
            <Building2 size={15} style={{ color: 'var(--brand-primary-hover)', flexShrink: 0, marginTop: 1 }} />
            <span>
              {t('auth:invitation.invited_by', 'Invited by {{name}}', { name: inv.agency_name })}.{' '}
              {t('auth:invitation.signup_prompt', 'Sign up below to join their workspace.')}
            </span>
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Input
            label={t('signup.full_name_label', 'Full name')}
            autoComplete="name"
            value={fullName}
            onChange={(e) => { setFullName(e.target.value); clearField('fullName'); }}
            placeholder={t('signup.full_name_placeholder', 'Your full name')}
            error={errors.fullName}
            size="lg"
            autoFocus
          />

          <Input
            label={t('signup.email_label', 'Work email')}
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => { setEmail(e.target.value); clearField('email'); }}
            placeholder={t('signup.email_placeholder', 'you@company.com')}
            error={errors.email}
            size="lg"
          />

          <div>
            <Input
              label={t('signup.password_label', 'Password')}
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); clearField('password'); }}
              placeholder={t('signup.password_placeholder', 'At least 8 characters')}
              error={errors.password}
              size="lg"
            />
            <PasswordStrength password={password} />
          </div>

          <Input
            label={t('signup.confirm_password_label', 'Confirm password')}
            type="password"
            autoComplete="new-password"
            value={confirmPwd}
            onChange={(e) => { setConfirmPwd(e.target.value); clearField('confirmPwd'); }}
            placeholder={t('signup.confirm_password_placeholder', 'Re-enter your password')}
            error={errors.confirmPwd}
            success={!!confirmPwd && confirmPwd === password && password.length >= 8 && !errors.confirmPwd}
            size="lg"
          />

          <Checkbox
            checked={accepted}
            onChange={(e) => { setAccepted(e.target.checked); if (errors.terms) clearField('terms'); }}
            label={
              <>
                {t('signup.terms_agree', 'I agree to the')}{' '}
                <Link to="/terms" style={{ color: 'var(--text-link)', fontWeight: 500 }}>
                  {t('signup.terms_link', 'Terms of Service')}
                </Link>{' '}
                {t('common.and', 'and')}{' '}
                <Link to="/privacy" style={{ color: 'var(--text-link)', fontWeight: 500 }}>
                  {t('signup.privacy_link', 'Privacy Policy')}
                </Link>
              </>
            }
          />
          {errors.terms && (
            <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: -6 }}>{errors.terms}</div>
          )}

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
            {loading ? t('signup.submitting', 'Creating account...') : t('signup.submit_button', 'Create account')}
          </Button>
        </form>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            margin: '20px 0',
            color: 'var(--text-tertiary)',
          }}
        >
          <span style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
          <span style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            {t('common.or', 'or')}
          </span>
          <span style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <Button variant="secondary" size="lg" fullWidth onClick={handleGoogle}>
            <SocialPlatformIcon platform="google" size={16} /> Google
          </Button>
          <Button variant="secondary" size="lg" fullWidth onClick={handleFacebook}>
            <SocialPlatformIcon platform="facebook" size={16} /> Facebook
          </Button>
        </div>
      </div>
    </AuthLayout>
  );
}
