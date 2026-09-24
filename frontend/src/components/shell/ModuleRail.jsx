/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  BarChart3, MessageCircle, Target,
  Bell, Settings, LogOut, ChevronUp,
  Briefcase, Receipt, Store,
} from 'lucide-react';

import { BrandMark } from '../ui/BrandLogo';
import AccountTypeBadge from '../ui/AccountTypeBadge';
import { useAuth } from '../../hooks/useAuth';

/**
 * 64px-wide left rail. Top = logo, middle = module switcher, bottom = secondary actions.
 *
 * Props:
 *   currentModule: 'analytics' | 'messaging' | 'ads'
 *   basePath:      '/admin' | '/dashboard'
 *   modules:       ordered list of { id, label, icon, enabled, comingSoon, badge }
 *   notifCount:    number for the bell dot
 */
export default function ModuleRail({ currentModule, basePath, modules = [], notifCount = 0 }) {
  const { t } = useTranslation('app');
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <aside
      className="ds-module-rail"
      aria-label={t('rail.brand_home', 'Module switcher')}
      style={{
        position: 'fixed',
        top: 0, left: 0, bottom: 0,
        width: 'var(--module-rail-width)',
        zIndex: 100,
        background: 'var(--surface-card)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '14px 0',
        gap: 6,
      }}
    >
      {/* Top: brand mark */}
      <button
        type="button"
        onClick={() => navigate(`${basePath}/${currentModule || 'analytics'}`)}
        aria-label={t('rail.brand_home', 'Bop Social home')}
        style={{
          width: 38, height: 38,
          borderRadius: 'var(--radius-md)',
          border: 'none',
          padding: 2,
          background: 'var(--surface-sunken)',
          boxShadow: 'var(--shadow-sm)',
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <BrandMark size={32} />
      </button>

      <Divider />

      {/* Middle: modules */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'center', marginTop: 4 }}>
        {modules.map((m) => (
          <ModuleButton
            key={m.id}
            module={m}
            active={currentModule === m.id}
            onClick={() => {
              if (!m.enabled || m.comingSoon) return;
              navigate(`${basePath}/${m.id}`);
            }}
          />
        ))}
      </div>

      {/* Bottom: secondary */}
      <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
        <RailIconBtn
          icon={Bell}
          label={t('rail.notifications', 'Notifications')}
          onClick={() => navigate(`${basePath}/analytics/alerts`)}
          dot={notifCount > 0}
        />
        <RailIconBtn
          icon={Settings}
          label={t('rail.settings', 'Settings')}
          onClick={() => navigate(`${basePath}/account-settings`)}
        />

        <UserMenu
          user={user}
          open={menuOpen}
          onOpenChange={setMenuOpen}
          onLogout={() => { logout(); navigate('/login'); }}
        />
      </div>
    </aside>
  );
}

function ModuleButton({ module: m, active, onClick }) {
  const { t } = useTranslation('app');
  const Icon = m.icon;
  const disabled = !m.enabled || m.comingSoon;

  const label = t(`modules.${m.id}.label`, m.label);
  const tooltip = m.comingSoon ? `${label} — ${t('rail.soon', 'Soon')}` : label;

  return (
    <div className="ds-rail-tip" data-tip={tooltip} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        aria-label={tooltip}
        aria-current={active ? 'page' : undefined}
        style={{
          width: 40, height: 40,
          border: 'none',
          padding: 0,
          borderRadius: 'var(--radius-md)',
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.45 : 1,
          background: active ? 'var(--brand-gradient)' : 'transparent',
          color: active ? 'var(--text-on-brand)' : 'var(--text-tertiary)',
          boxShadow: active ? '0 4px 14px var(--brand-primary-glow)' : 'none',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'var(--transition-fast)',
          position: 'relative',
        }}
        onMouseEnter={(e) => {
          if (active || disabled) return;
          e.currentTarget.style.background = 'var(--surface-hover)';
          e.currentTarget.style.color = 'var(--text-primary)';
          e.currentTarget.style.transform = 'scale(1.05)';
        }}
        onMouseLeave={(e) => {
          if (active || disabled) return;
          e.currentTarget.style.background = 'transparent';
          e.currentTarget.style.color = 'var(--text-tertiary)';
          e.currentTarget.style.transform = 'none';
        }}
      >
        <Icon size={18} strokeWidth={2} />

        {m.comingSoon && (
          <span style={{
            position: 'absolute', top: -2, right: -2,
            background: 'var(--warning)', color: '#fff',
            fontSize: 8, fontWeight: 700, padding: '1px 4px',
            borderRadius: 999, lineHeight: 1,
          }}>
            SOON
          </span>
        )}

        {!!m.badge && m.badge > 0 && (
          <span style={{
            position: 'absolute', top: 4, right: 4,
            minWidth: 16, height: 16, padding: '0 4px',
            background: 'var(--brand-primary-hover)', color: '#fff',
            fontSize: 9, fontWeight: 700, lineHeight: '16px',
            borderRadius: 999, textAlign: 'center',
          }}>
            {m.badge > 99 ? '99+' : m.badge}
          </span>
        )}
      </button>
    </div>
  );
}

function RailIconBtn({ icon: Icon, label, onClick, dot }) {
  return (
    <div className="ds-rail-tip" data-tip={label} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={onClick}
        aria-label={label}
        style={{
          width: 36, height: 36,
          padding: 0, border: 'none', borderRadius: 'var(--radius-md)',
          background: 'transparent',
          color: 'var(--text-tertiary)',
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'var(--transition-fast)',
          position: 'relative',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'var(--surface-hover)';
          e.currentTarget.style.color = 'var(--text-primary)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'transparent';
          e.currentTarget.style.color = 'var(--text-tertiary)';
        }}
      >
        <Icon size={16} strokeWidth={2} />
        {dot && (
          <span aria-hidden style={{
            position: 'absolute', top: 8, right: 8,
            width: 6, height: 6, background: 'var(--danger)',
            borderRadius: '50%',
          }} />
        )}
      </button>
    </div>
  );
}

function UserMenu({ user, open, onOpenChange, onLogout }) {
  const { t } = useTranslation('app');
  const navigate = useNavigate();
  const isAgency = user?.account_type === 'agency_member';
  const isEndUser = user?.account_type === 'end_user';

  // Close on outside click / escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') onOpenChange(false); };
    const onClick = (e) => {
      if (!e.target.closest('.ds-user-menu-anchor')) onOpenChange(false);
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('mousedown', onClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('mousedown', onClick);
    };
  }, [open, onOpenChange]);

  const initial = ((user?.name || user?.email || 'U').trim()[0] || 'U').toUpperCase();
  const hue = hashHue(user?.email || user?.name || '');

  return (
    <div className="ds-user-menu-anchor" style={{ position: 'relative', marginTop: 4 }}>
      <button
        type="button"
        onClick={() => onOpenChange(!open)}
        aria-label={t('rail.account_menu', 'Account menu')}
        aria-haspopup="menu"
        aria-expanded={open}
        style={{
          width: 36, height: 36, padding: 0,
          borderRadius: 999, border: '1px solid var(--border-subtle)',
          background: `linear-gradient(135deg, hsl(${hue},65%,55%), hsl(${(hue+50)%360},65%,45%))`,
          color: '#fff', fontWeight: 700, fontSize: 13,
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'var(--transition-fast)',
        }}
      >
        {initial}
      </button>

      {open && (
        <div
          role="menu"
          style={{
            position: 'absolute',
            left: 'calc(100% + 12px)',
            bottom: 0,
            background: 'var(--surface-elevated)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-lg)',
            minWidth: 200,
            padding: 6,
            zIndex: 200,
          }}
        >
          <div style={{ padding: '8px 10px 10px', borderBottom: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              {user?.name || user?.email}
            </div>
            <div style={{ marginTop: 6 }}>
              <AccountTypeBadge type={user?.account_type} role={user?.role} size="sm" />
            </div>
          </div>
          {isAgency && (
            <>
              <MenuRow icon={Briefcase} label={t('rail.manage_agency', 'Manage agency')} onClick={() => {
                onOpenChange(false); navigate('/agency');
              }} />
              <MenuRow icon={Store} label={t('rail.marketplace_profile', 'Marketplace profile')} onClick={() => {
                onOpenChange(false); navigate('/agency/marketplace-profile');
              }} />
            </>
          )}
          {isEndUser && (
            <MenuRow icon={Briefcase} label={t('rail.my_agency', 'My agency')} onClick={() => {
              onOpenChange(false); navigate('/u/agency');
            }} />
          )}
          <MenuRow icon={Settings} label={t('rail.account_settings', 'Account settings')} onClick={() => {
            onOpenChange(false);
            navigate(user?.role === 'client' ? '/dashboard/account-settings' : '/admin/account-settings');
          }} />
          <MenuRow icon={LogOut} label={t('rail.sign_out', 'Sign out')} danger onClick={onLogout} />
        </div>
      )}
    </div>
  );
}

function MenuRow({ icon: Icon, label, onClick, danger }) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        width: '100%', padding: '8px 10px',
        background: 'transparent', border: 'none',
        borderRadius: 'var(--radius-sm)',
        color: danger ? 'var(--danger)' : 'var(--text-primary)',
        fontSize: 13, fontWeight: 500,
        cursor: 'pointer', textAlign: 'left',
        transition: 'var(--transition-fast)',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--surface-hover)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
    >
      <Icon size={14} strokeWidth={2} />
      {label}
    </button>
  );
}

function Divider() {
  return (
    <div style={{
      width: 32, height: 1,
      background: 'var(--border-subtle)',
      margin: '8px 0',
    }} />
  );
}

function hashHue(s) {
  let h = 0;
  for (let i = 0; i < (s || '').length; i++) h = s.charCodeAt(i) + ((h << 5) - h);
  return Math.abs(h) % 360;
}
