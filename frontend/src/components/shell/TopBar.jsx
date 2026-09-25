/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useEffect, useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Search, Sparkles, ChevronRight } from 'lucide-react';

import ThemeToggle from '../ui/ThemeToggle';
import LanguageSelector from '../ui/LanguageSelector';
import NotificationBell from '../ui/NotificationBell';

/**
 * 56px-tall top bar.
 * Left: breadcrumb (Module / Feature / Detail)
 * Center: command-palette trigger (⌘K)
 * Right: theme toggle, language selector, notifications, what's new pill, user menu (user menu lives in rail)
 */
export default function TopBar({
  basePath,
  module,
  onOpenPalette,
  onOpenMobileMenu,
}) {
  const { t } = useTranslation('app');
  const navigate = useNavigate();
  const location = useLocation();
  const crumbs = buildBreadcrumbs(location.pathname, basePath, t);
  const isMac = typeof navigator !== 'undefined' && /mac/i.test(navigator.platform);

  return (
    <header
      style={{
        position: 'fixed',
        top: 0,
        left: 'calc(var(--module-rail-width) + var(--feature-sidebar-width))',
        right: 0,
        height: 'var(--topbar-height)',
        zIndex: 80,
        background: 'var(--surface-card)',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '0 20px',
      }}
      className="ds-topbar"
    >
      {/* Breadcrumb */}
      <nav aria-label={t('topbar.breadcrumb_home', 'Breadcrumb')} style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, flex: '0 1 auto' }}>
        {crumbs.map((c, i) => (
          <span key={c.label} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            {i > 0 && <ChevronRight size={12} color="var(--text-tertiary)" />}
            {i === crumbs.length - 1 ? (
              <span style={{
                fontSize: 13, fontWeight: 600,
                color: 'var(--text-primary)',
                whiteSpace: 'nowrap',
                maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
                {c.label}
              </span>
            ) : c.to ? (
              <Link to={c.to} style={{
                fontSize: 13, color: 'var(--text-tertiary)',
                textDecoration: 'none', whiteSpace: 'nowrap',
              }}>
                {c.label}
              </Link>
            ) : (
              <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>{c.label}</span>
            )}
          </span>
        ))}
      </nav>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Command palette trigger — flex-shrinks at narrow widths so the
          notification bell + theme toggle + What's-New pill stay visible. */}
      <button
        type="button"
        onClick={onOpenPalette}
        aria-label={t('topbar.search_aria', 'Open command palette (Cmd+K)')}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          flex: '0 1 280px',
          minWidth: 180,
          height: 34,
          padding: '0 12px',
          background: 'var(--surface-sunken)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--text-tertiary)',
          fontSize: 13, fontWeight: 500,
          cursor: 'pointer',
          transition: 'var(--transition-fast)',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--border-default)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border-subtle)'; }}
        className="ds-topbar-search"
      >
        <Search size={14} />
        <span style={{ flex: 1, textAlign: 'left' }}>{t('topbar.search_placeholder', 'Search anything…')}</span>
        <kbd style={{
          fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 500,
          padding: '2px 6px',
          background: 'var(--surface-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-sm)',
          color: 'var(--text-tertiary)',
        }}>
          {isMac ? '⌘' : 'Ctrl'}K
        </kbd>
      </button>

      <ThemeToggle size="sm" />

      <LanguageSelector size="sm" />

      <NotificationBellWrapper />

      <Link
        to="/changelog"
        target="_blank"
        rel="noopener noreferrer"
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          padding: '4px 10px',
          background: 'var(--brand-primary-glow)',
          color: 'var(--brand-primary-hover)',
          border: '1px solid transparent',
          borderRadius: 999,
          fontSize: 11, fontWeight: 600,
          textDecoration: 'none',
          letterSpacing: 0.2,
          transition: 'var(--transition-fast)',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--brand-primary-soft)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--brand-primary-glow)'; }}
        aria-label={t('topbar.whats_new', "What's new")}
        className="ds-whats-new"
      >
        <Sparkles size={11} />
        {t('topbar.new', 'New')}
      </Link>
    </header>
  );
}

/**
 * Bridges existing NotificationBell which expects no props.
 * Wraps it so failures (no token, no perms) don't kill the topbar.
 */
function NotificationBellWrapper() {
  try {
    return <NotificationBell />;
  } catch {
    return null;
  }
}

export function buildBreadcrumbs(pathname, basePath, t) {
  // Strip basePath
  const rest = pathname.startsWith(basePath) ? pathname.slice(basePath.length) : pathname;
  const parts = rest.split('/').filter(Boolean);
  if (parts.length === 0) return [{ label: t ? t('topbar.breadcrumb_home', 'Home') : 'Home' }];

  const out = [];
  let acc = basePath;
  for (let i = 0; i < parts.length; i++) {
    acc += `/${parts[i]}`;
    const rawSeg = parts[i];
    const key = rawSeg.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    const translated = t ? (
      t(`breadcrumbs.${key}`, '') ||
      t(`sidebar.items.${key}`, '') ||
      t(`modules.${key}.label`, '') ||
      t(`rail.${key}`, '') ||
      t(`mobile_nav.${key}`, '')
    ) : '';
    out.push({
      label: translated || humanize(rawSeg),
      to: i < parts.length - 1 ? acc : undefined,
    });
  }
  return out;
}

export function humanize(seg) {
  // Strip query, IDs that look numeric, then capitalize-ish
  if (/^\d+$/.test(seg)) return `#${seg}`;
  return seg
    .replace(/-|_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
