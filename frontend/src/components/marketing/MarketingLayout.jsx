/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Menu, X, ChevronDown,
  Github, Linkedin, Twitter, Youtube,
  BarChart3, PenSquare, Inbox, MessageCircle, Bot, Sparkles, FileText,
  Zap, Building2, Users, Star, Calendar, MessagesSquare,
  Briefcase, Stethoscope, UtensilsCrossed, Palette, ShoppingBag, GraduationCap,
} from 'lucide-react';

import { useTranslation } from 'react-i18next';
import Logo from '../ui/Logo';
import Button from '../ui/Button';
import ThemeToggle from '../ui/ThemeToggle';
import LanguageSelector from '../ui/LanguageSelector';
import SkipLink from '../ui/SkipLink';
import { prefetchRoute } from '../../utils/prefetchRoute';

/**
 * MarketingLayout — public site shell. Wraps every public/marketing page.
 *
 *  ┌─────────────────────────────────────────────────────────────┐
 *  │ Top nav (transparent on hero, solid + blur on scroll)       │
 *  │ + Product / Solutions mega-menus                            │
 *  ├─────────────────────────────────────────────────────────────┤
 *  │  page content                                               │
 *  ├─────────────────────────────────────────────────────────────┤
 *  │ 6-column footer (Product / Solutions / Resources / Company  │
 *  │                   / Legal + brand)                          │
 *  └─────────────────────────────────────────────────────────────┘
 */
export default function MarketingLayout({ children }) {
  return (
    <div style={{ background: 'var(--surface-page)', color: 'var(--text-primary)' }}>
      <SkipLink targetId="marketing-main" />
      <MarketingNav />
      <main id="marketing-main" tabIndex={-1} style={{ outline: 'none' }}>
        {children}
      </main>
      <MarketingFooter />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Nav data
// ─────────────────────────────────────────────────────────────────────────────
const PRODUCT_MENU = [
  { label: 'Analytics',     labelKey: 'products.analytics',     to: '/product/analytics',         icon: BarChart3,    desc: 'Cross-platform metrics', descKey: 'products.analytics_desc' },
  { label: 'Composer',      labelKey: 'products.composer',      to: '/product/composer',          icon: PenSquare,    desc: 'Write once, publish 5x', descKey: 'products.composer_desc' },
  { label: 'Inbox',         labelKey: 'products.inbox',         to: '/product/inbox',             icon: Inbox,        desc: 'Every conversation, one place', descKey: 'products.inbox_desc' },
  { label: 'WhatsApp',      labelKey: 'products.whatsapp',      to: '/product/whatsapp',          icon: MessageCircle,desc: 'Campaigns + two-way chat', descKey: 'products.whatsapp_desc' },
  { label: 'Bot Builder',   labelKey: 'products.bot_builder',   to: '/product/bot-builder',       icon: Bot,          desc: 'Visual CTWA flow editor', descKey: 'products.bot_builder_desc' },
  { label: 'AI Studio',     labelKey: 'products.ai_studio',     to: '/product/ai',                icon: Sparkles,     desc: 'Bop Social in every corner', descKey: 'products.ai_studio_desc' },
  { label: 'AI Assistant',  labelKey: 'products.ai_assistant',  to: '/product/ai-assistant',      icon: MessagesSquare, desc: 'Cmd+J — talk to your data', descKey: 'products.ai_assistant_desc' },
  { label: 'Reports',       labelKey: 'products.reports',       to: '/product/reports',           icon: FileText,     desc: 'Reports that write themselves', descKey: 'products.reports_desc' },
  { label: 'Automations',   labelKey: 'products.automations',   to: '/product/automations',       icon: Zap,          desc: 'IF this, do that', descKey: 'products.automations_desc' },
  { label: 'Marketplace',   labelKey: 'products.marketplace',   to: '/product/marketplace-product', icon: Star,       desc: 'Two-sided marketplace', descKey: 'products.marketplace_desc' },
];

const SOLUTIONS_BY_ROLE = [
  { label: 'For Agencies',   labelKey: 'solutions.agencies',   to: '/solutions/agencies',   icon: Briefcase, desc: 'Manage 100+ clients', descKey: 'solutions.agencies_desc' },
  { label: 'For Businesses', labelKey: 'solutions.businesses', to: '/solutions/businesses', icon: Building2, desc: 'Take back control', descKey: 'solutions.businesses_desc' },
  { label: 'For Creators',   labelKey: 'solutions.creators',   to: '/solutions/creators',   icon: Palette,   desc: 'Track your creator economy', descKey: 'solutions.creators_desc' },
];

const SOLUTIONS_BY_INDUSTRY = [
  { label: 'Real Estate', labelKey: 'solutions.real_estate', to: '/solutions/real-estate', icon: Building2,        desc: 'Sell more properties', descKey: 'solutions.real_estate_desc' },
  { label: 'Healthcare',  labelKey: 'solutions.healthcare',  to: '/solutions/clinics',     icon: Stethoscope,      desc: 'Engage patients', descKey: 'solutions.healthcare_desc' },
  { label: 'Restaurants', labelKey: 'solutions.restaurants', to: '/solutions/restaurants', icon: UtensilsCrossed,  desc: 'Fill more tables', descKey: 'solutions.restaurants_desc' },
  { label: 'E-commerce',  labelKey: 'solutions.ecommerce',   to: '/solutions/ecommerce',   icon: ShoppingBag,      desc: 'Drive sales from social', descKey: 'solutions.ecommerce_desc' },
  { label: 'Education',   labelKey: 'solutions.education',   to: '/solutions/education',   icon: GraduationCap,    desc: 'Reach more students', descKey: 'solutions.education_desc' },
];

const SIMPLE_LINKS = [
  { label: 'Customers', labelKey: 'nav.customers', to: '/customers' },
  { label: 'Resources', labelKey: 'nav.resources', to: null,
    menu: { single: [
      { label: 'Blog',          labelKey: 'resources.blog',         to: '/blog',         icon: FileText,       desc: 'Marketing tips + product updates', descKey: 'resources.blog_desc' },
      { label: 'Help Center',   labelKey: 'resources.help_center',   to: '/help',         icon: Users,          desc: 'Guides + how-tos', descKey: 'resources.help_center_desc' },
      { label: 'Changelog',     labelKey: 'resources.changelog',     to: '/changelog',    icon: Calendar,       desc: 'What shipped this week', descKey: 'resources.changelog_desc' },
      { label: 'Status',        labelKey: 'resources.status',        to: '/status',       icon: Zap,            desc: 'System uptime', descKey: 'resources.status_desc' },
      { label: 'Integrations',  labelKey: 'resources.integrations',  to: '/integrations', icon: Sparkles,       desc: 'Connect your stack', descKey: 'resources.integrations_desc' },
      { label: 'Contact',       labelKey: 'resources.contact',       to: '/contact',      icon: MessagesSquare, desc: 'Sales + support', descKey: 'resources.contact_desc' },
    ]},
  },
  { label: 'About', labelKey: 'nav.about', to: '/about' },
];

// ─────────────────────────────────────────────────────────────────────────────
// Nav
// ─────────────────────────────────────────────────────────────────────────────
function MarketingNav() {
  const { t } = useTranslation('navigation');
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [openMenu, setOpenMenu] = useState(null);  // 'product' | 'solutions' | 'resources'
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth < 1024 : false);
  const location = useLocation();
  const headerRef = useRef(null);

  // Grace period for the mega-menu hover. Without it the menu closes
  // instantly when the pointer briefly leaves the trigger to reach the
  // panel — the cursor's natural diagonal path crosses non-menu space.
  const closeTimerRef = useRef(null);
  const cancelClose = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };
  const scheduleClose = () => {
    cancelClose();
    closeTimerRef.current = setTimeout(() => setOpenMenu(null), 140);
  };
  useEffect(() => () => cancelClose(), []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    const onResize = () => {
      const mobile = window.innerWidth < 1024;
      setIsMobile(mobile);
      if (!mobile) setMobileOpen(false);
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // Close mega-menu on navigation
  useEffect(() => {
    setOpenMenu(null);
    setMobileOpen(false);
  }, [location.pathname]);

  // Escape key closes open menu
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setOpenMenu(null);
        setMobileOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Close mega-menu on outside click
  useEffect(() => {
    if (!openMenu) return;
    const onClickOutside = (e) => {
      if (headerRef.current && !headerRef.current.contains(e.target)) {
        setOpenMenu(null);
      }
    };
    document.addEventListener('pointerdown', onClickOutside);
    return () => document.removeEventListener('pointerdown', onClickOutside);
  }, [openMenu]);

  // Lock scroll when mobile drawer is open
  useEffect(() => {
    if (mobileOpen) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => { document.body.style.overflow = prev; };
    }
  }, [mobileOpen]);

  const isHomePage = location.pathname === '/';
  const isDarkHeroNav = isHomePage && !scrolled && !openMenu;

  return (
    <header
      ref={headerRef}
      style={{
        position: 'fixed',
        top: 0, left: 0, right: 0,
        zIndex: 'var(--z-sticky)',
        background: openMenu ? 'var(--surface-card)' : (isDarkHeroNav ? 'transparent' : 'var(--surface-overlay)'),
        backdropFilter: openMenu ? 'none' : (isDarkHeroNav ? 'none' : 'blur(14px) saturate(180%)'),
        WebkitBackdropFilter: openMenu ? 'none' : (isDarkHeroNav ? 'none' : 'blur(14px) saturate(180%)'),
        borderBottom: openMenu || !isDarkHeroNav ? '1px solid var(--border-subtle)' : '1px solid transparent',
        transition: 'background var(--transition-default), border-color var(--transition-default), backdrop-filter var(--transition-default)',
      }}
      onMouseLeave={scheduleClose}
      onMouseEnter={cancelClose}
    >
      <div
        style={{
          maxWidth: 'var(--container-2xl)',
          margin: '0 auto',
          padding: isMobile ? '12px 20px' : '14px 32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 24,
        }}
      >
        <Link
          to="/"
          style={{ display: 'inline-flex', alignItems: 'center' }}
          aria-label="Bop Social home"
          onMouseEnter={() => { cancelClose(); setOpenMenu(null); }}
        >
          <Logo variant="horizontal" height={isMobile ? 32 : 38} inverted={isDarkHeroNav} />
        </Link>

        {/* Desktop nav */}
        {!isMobile && (
          <nav style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <MegaTrigger label={t('nav.product', 'Product')}
                         active={openMenu === 'product'}
                         darkHero={isDarkHeroNav}
                         onEnter={() => { cancelClose(); setOpenMenu('product'); }}
                         onToggle={() => {
                           cancelClose();
                           setOpenMenu((prev) => (prev === 'product' ? null : 'product'));
                         }} />
            <MegaTrigger label={t('nav.solutions', 'Solutions')}
                         active={openMenu === 'solutions'}
                         darkHero={isDarkHeroNav}
                         onEnter={() => { cancelClose(); setOpenMenu('solutions'); }}
                         onToggle={() => {
                           cancelClose();
                           setOpenMenu((prev) => (prev === 'solutions' ? null : 'solutions'));
                         }} />
            {SIMPLE_LINKS.map((l) => l.to ? (
              <NavLink key={l.label} to={l.to}
                       active={location.pathname === l.to}
                       darkHero={isDarkHeroNav}
                       onMouseEnter={() => { cancelClose(); setOpenMenu(null); }}>
                {l.labelKey ? t(l.labelKey, l.label) : l.label}
              </NavLink>
            ) : (
              <MegaTrigger key={l.label} label={l.labelKey ? t(l.labelKey, l.label) : l.label}
                           active={openMenu === l.label.toLowerCase()}
                           darkHero={isDarkHeroNav}
                           onEnter={() => { cancelClose(); setOpenMenu(l.label.toLowerCase()); }}
                           onToggle={() => {
                             cancelClose();
                             const key = l.label.toLowerCase();
                             setOpenMenu((prev) => (prev === key ? null : key));
                           }} />
            ))}
          </nav>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <LanguageSelector size="sm" darkHero={isDarkHeroNav} />
          <ThemeToggle size="sm" />
          {!isMobile && (
            <>
              <Button as={Link} to="/login" variant="ghost" size="sm"
                      onMouseEnter={() => { cancelClose(); setOpenMenu(null); }}
                      style={{ color: isDarkHeroNav ? '#FFFFFF' : 'var(--text-primary)' }}>
                {t('nav.sign_in', 'Sign in')}
              </Button>
              <Button as={Link} to="/signup" size="sm" variant="primary"
                      onMouseEnter={() => { cancelClose(); setOpenMenu(null); }}>
                {t('nav.get_started', 'Get started')}
              </Button>
            </>
          )}
          {isMobile && (
            <button
              type="button"
              aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={mobileOpen}
              onClick={() => setMobileOpen((v) => !v)}
              style={{
                width: 36, height: 36,
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                border: '1px solid var(--border-default)',
                borderRadius: 'var(--radius-md)',
                background: 'var(--surface-card)',
                color: 'var(--text-secondary)',
                cursor: 'pointer', padding: 0,
              }}
            >
              {mobileOpen ? <X size={16} /> : <Menu size={16} />}
            </button>
          )}
        </div>
      </div>

      {/* Mega-menu panels (desktop only) */}
      {!isMobile && openMenu === 'product' && (
        <MegaPanel onMouseEnter={cancelClose} onMouseLeave={scheduleClose}>
          <MegaGrid columns={2}>
            {PRODUCT_MENU.map((item) => (
              <MegaItem key={item.to} {...item} />
            ))}
          </MegaGrid>
        </MegaPanel>
      )}
      {!isMobile && openMenu === 'solutions' && (
        <MegaPanel onMouseEnter={cancelClose} onMouseLeave={scheduleClose}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32 }}>
            <div>
              <MegaHeader>{t('sections.by_role', 'By role')}</MegaHeader>
              <MegaGrid columns={1}>
                {SOLUTIONS_BY_ROLE.map((item) => <MegaItem key={item.to} {...item} />)}
              </MegaGrid>
            </div>
            <div>
              <MegaHeader>{t('sections.by_industry', 'By industry')}</MegaHeader>
              <MegaGrid columns={1}>
                {SOLUTIONS_BY_INDUSTRY.map((item) => <MegaItem key={item.to} {...item} />)}
              </MegaGrid>
            </div>
          </div>
        </MegaPanel>
      )}
      {!isMobile && openMenu === 'resources' && (
        <MegaPanel onMouseEnter={cancelClose} onMouseLeave={scheduleClose}>
          <MegaGrid columns={2}>
            {SIMPLE_LINKS.find((l) => l.label === 'Resources').menu.single.map((item) => (
              <MegaItem key={item.to} {...item} />
            ))}
          </MegaGrid>
        </MegaPanel>
      )}

      {/* Mobile drawer */}
      {isMobile && mobileOpen && (
        <MobileDrawer location={location} onClose={() => setMobileOpen(false)} />
      )}
    </header>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Nav primitives
// ─────────────────────────────────────────────────────────────────────────────
function NavLink({ to, active, children, onMouseEnter, darkHero = false }) {
  const normalColor = darkHero ? 'rgba(255, 255, 255, 0.88)' : (active ? 'var(--text-primary)' : 'var(--text-secondary)');
  const hoverBg = darkHero ? 'rgba(255, 255, 255, 0.12)' : 'var(--surface-hover)';
  const hoverColor = darkHero ? '#FFFFFF' : 'var(--text-primary)';
  const activeBg = darkHero ? 'rgba(255, 255, 255, 0.14)' : 'var(--surface-hover)';
  return (
    <Link
      to={to}
      onMouseEnter={(e) => { prefetchRoute(to); onMouseEnter?.(e); }}
      onTouchStart={() => prefetchRoute(to)}
      onFocus={() => prefetchRoute(to)}
      style={{
        padding: '8px 12px',
        fontSize: 14,
        fontWeight: active ? 600 : 500,
        color: active ? (darkHero ? '#FFFFFF' : 'var(--text-primary)') : normalColor,
        background: active ? activeBg : 'transparent',
        textDecoration: 'none',
        borderRadius: 'var(--radius-md)',
        transition: 'var(--transition-fast)',
      }}
      onMouseOver={(e) => {
        e.currentTarget.style.color = hoverColor;
        e.currentTarget.style.background = hoverBg;
      }}
      onMouseOut={(e) => {
        e.currentTarget.style.color = active ? (darkHero ? '#FFFFFF' : 'var(--text-primary)') : normalColor;
        e.currentTarget.style.background = active ? activeBg : 'transparent';
      }}
    >
      {children}
    </Link>
  );
}

function MegaTrigger({ label, active, onEnter, onToggle, darkHero = false }) {
  const normalColor = darkHero ? 'rgba(255, 255, 255, 0.88)' : (active ? 'var(--text-primary)' : 'var(--text-secondary)');
  const activeBg = darkHero ? 'rgba(255, 255, 255, 0.14)' : 'var(--surface-hover)';
  return (
    <button
      type="button"
      onMouseEnter={onEnter}
      onFocus={onEnter}
      onClick={onToggle || onEnter}
      aria-expanded={active}
      aria-haspopup="true"
      style={{
        padding: '8px 12px',
        fontSize: 14, fontWeight: 500,
        color: active ? (darkHero ? '#FFFFFF' : 'var(--text-primary)') : normalColor,
        background: active ? activeBg : 'transparent',
        border: 'none',
        borderRadius: 'var(--radius-md)',
        cursor: 'pointer',
        display: 'inline-flex', alignItems: 'center', gap: 4,
        transition: 'var(--transition-fast)',
        fontFamily: 'inherit',
      }}
      onMouseOver={(e) => {
        if (!active) {
          e.currentTarget.style.color = darkHero ? '#FFFFFF' : 'var(--text-primary)';
          e.currentTarget.style.background = darkHero ? 'rgba(255, 255, 255, 0.12)' : 'var(--surface-hover)';
        }
      }}
      onMouseOut={(e) => {
        if (!active) {
          e.currentTarget.style.color = normalColor;
          e.currentTarget.style.background = 'transparent';
        }
      }}
    >
      {label}
      <ChevronDown size={14} style={{
        transform: active ? 'rotate(180deg)' : 'rotate(0)',
        transition: 'transform 160ms var(--ease-out)',
      }} />
    </button>
  );
}

function MegaPanel({ children, onMouseLeave, onMouseEnter }) {
  return (
    <div
      role="menu"
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      style={{
        position: 'absolute',
        top: '100%',
        left: 0,
        right: 0,
        background: 'var(--surface-card)',
        borderTop: '1px solid var(--border-subtle)',
        borderBottom: '1px solid var(--border-default)',
        boxShadow: '0 24px 48px -12px rgba(0, 0, 0, 0.28), 0 4px 16px rgba(0, 0, 0, 0.08)',
        zIndex: 1000,
        animation: 'mkt-mega-fade 180ms var(--ease-out)',
      }}
    >
      <div
        style={{
          maxWidth: 'var(--container-2xl)',
          margin: '0 auto',
          padding: '24px 32px 32px',
        }}
      >
        {children}
      </div>
      <style>{`
        @keyframes mkt-mega-fade {
          from { opacity: 0; transform: translateY(-4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

function MegaGrid({ children, columns = 2 }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
      gap: 6,
    }}>
      {children}
    </div>
  );
}

function MegaHeader({ children }) {
  return (
    <h3 style={{
      margin: '0 0 12px',
      fontSize: 11, fontWeight: 600,
      letterSpacing: '0.08em', textTransform: 'uppercase',
      color: 'var(--text-tertiary)',
    }}>{children}</h3>
  );
}

function MegaItem({ to, label, desc, labelKey, descKey, icon: Icon }) {
  const { t } = useTranslation('navigation');
  const displayLabel = labelKey ? t(labelKey, label) : label;
  const displayDesc = descKey ? t(descKey, desc) : desc;
  return (
    <Link
      to={to}
      role="menuitem"
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 12,
        padding: '10px 12px',
        borderRadius: 'var(--radius-md)',
        textDecoration: 'none',
        color: 'var(--text-primary)',
        transition: 'var(--transition-fast)',
        outline: 'none',
      }}
      onMouseOver={(e) => { e.currentTarget.style.background = 'var(--surface-hover)'; }}
      onMouseOut={(e)  => { e.currentTarget.style.background = 'transparent'; }}
      onFocus={(e)     => { e.currentTarget.style.background = 'var(--surface-hover)'; }}
      onBlur={(e)      => { e.currentTarget.style.background = 'transparent'; }}
    >
      {Icon && (
        <span style={{
          width: 32, height: 32, flexShrink: 0,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          borderRadius: 'var(--radius-sm)',
          background: 'var(--brand-primary-soft)',
          color: 'var(--brand-primary-hover)',
        }}>
          <Icon size={16} strokeWidth={2.2} />
        </span>
      )}
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.3 }}>{displayLabel}</div>
        {displayDesc && (
          <div style={{ marginTop: 2, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
            {displayDesc}
          </div>
        )}
      </div>
    </Link>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Mobile drawer
// ─────────────────────────────────────────────────────────────────────────────
function MobileDrawer({ location, onClose }) {
  const { t } = useTranslation('navigation');
  const [openSection, setOpenSection] = useState(null);
  const drawerRef = useRef(null);

  useEffect(() => {
    drawerRef.current?.focus();
  }, []);

  return (
    <div
      ref={drawerRef}
      role="dialog"
      aria-modal="true"
      aria-label="Navigation"
      tabIndex={-1}
      style={{
        position: 'fixed',
        top: 60, left: 0, right: 0, bottom: 0,
        background: 'var(--surface-page)',
        zIndex: 'var(--z-overlay)',
        padding: 16,
        overflowY: 'auto',
        animation: 'mkt-drawer-slide 220ms var(--ease-out)',
      }}
    >
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 14px 14px', borderBottom: '1px solid var(--border-subtle)',
        marginBottom: 8,
      }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)' }}>
          {t('languages.select_language', 'Language')}
        </span>
        <LanguageSelector size="sm" />
      </div>

      <Accordion title={t('nav.product', 'Product')}
                 open={openSection === 'product'}
                 onToggle={() => setOpenSection((s) => s === 'product' ? null : 'product')}>
        {PRODUCT_MENU.map((item) => (
          <DrawerItem key={item.to} {...item} active={location.pathname === item.to} />
        ))}
      </Accordion>
      <Accordion title={t('nav.solutions', 'Solutions')}
                 open={openSection === 'solutions'}
                 onToggle={() => setOpenSection((s) => s === 'solutions' ? null : 'solutions')}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em',
                      textTransform: 'uppercase', color: 'var(--text-tertiary)',
                      padding: '8px 14px 4px' }}>{t('sections.by_role', 'By role')}</div>
        {SOLUTIONS_BY_ROLE.map((item) => (
          <DrawerItem key={item.to} {...item} active={location.pathname === item.to} />
        ))}
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em',
                      textTransform: 'uppercase', color: 'var(--text-tertiary)',
                      padding: '12px 14px 4px' }}>{t('sections.by_industry', 'By industry')}</div>
        {SOLUTIONS_BY_INDUSTRY.map((item) => (
          <DrawerItem key={item.to} {...item} active={location.pathname === item.to} />
        ))}
      </Accordion>
      {SIMPLE_LINKS.map((l) =>
        l.to ? (
          <Link
            key={l.label}
            to={l.to}
            style={{
              display: 'block',
              padding: '14px 16px',
              fontSize: 16, fontWeight: 500,
              color: 'var(--text-primary)', textDecoration: 'none',
              borderRadius: 'var(--radius-md)',
              background: location.pathname === l.to ? 'var(--surface-hover)' : 'transparent',
            }}
          >{l.labelKey ? t(l.labelKey, l.label) : l.label}</Link>
        ) : (
          <Accordion key={l.label} title={l.labelKey ? t(l.labelKey, l.label) : l.label}
                     open={openSection === l.label.toLowerCase()}
                     onToggle={() => setOpenSection((s) => s === l.label.toLowerCase() ? null : l.label.toLowerCase())}>
            {l.menu.single.map((item) => (
              <DrawerItem key={item.to} {...item} active={location.pathname === item.to} />
            ))}
          </Accordion>
        )
      )}
      <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border-subtle)',
                    display: 'grid', gap: 8 }}>
        <Button as={Link} to="/login" variant="secondary" size="lg" fullWidth>{t('nav.sign_in', 'Sign in')}</Button>
        <Button as={Link} to="/signup" size="lg" fullWidth>{t('nav.get_started_free', 'Get started free')}</Button>
      </div>
      <style>{`
        @keyframes mkt-drawer-slide {
          from { opacity: 0; transform: translateY(-8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

function Accordion({ title, open, onToggle, children }) {
  return (
    <div style={{ borderBottom: '1px solid var(--border-subtle)' }}>
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        style={{
          width: '100%',
          padding: '14px 16px',
          fontSize: 16, fontWeight: 500,
          color: 'var(--text-primary)',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          fontFamily: 'inherit',
        }}
      >
        {title}
        <ChevronDown size={16} style={{
          transform: open ? 'rotate(180deg)' : 'rotate(0)',
          transition: 'transform 160ms var(--ease-out)',
          color: 'var(--text-tertiary)',
        }} />
      </button>
      {open && <div style={{ padding: '4px 0 12px' }}>{children}</div>}
    </div>
  );
}

function DrawerItem({ to, label, desc, labelKey, descKey, icon: Icon, active }) {
  const { t } = useTranslation('navigation');
  const displayLabel = labelKey ? t(labelKey, label) : label;
  const displayDesc = descKey ? t(descKey, desc) : desc;
  return (
    <Link
      to={to}
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 10,
        padding: '10px 16px',
        textDecoration: 'none',
        color: 'var(--text-primary)',
        background: active ? 'var(--surface-hover)' : 'transparent',
      }}
    >
      {Icon && (
        <span style={{
          width: 28, height: 28, flexShrink: 0,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          borderRadius: 'var(--radius-sm)',
          background: 'var(--brand-primary-soft)',
          color: 'var(--brand-primary-hover)',
        }}>
          <Icon size={14} strokeWidth={2.2} />
        </span>
      )}
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 500 }}>{displayLabel}</div>
        {displayDesc && (
          <div style={{ marginTop: 1, fontSize: 12, color: 'var(--text-secondary)' }}>{displayDesc}</div>
        )}
      </div>
    </Link>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Footer — 6-column grid
// ─────────────────────────────────────────────────────────────────────────────
function MarketingFooter() {
  const { t } = useTranslation('navigation');
  const year = new Date().getFullYear();

  const COLUMNS = [
    {
      title: t('footer.product', 'Product'),
      links: [
        { label: t('products.analytics', 'Analytics'),     to: '/product/analytics' },
        { label: t('products.composer', 'Composer'),      to: '/product/composer' },
        { label: t('products.inbox', 'Inbox'),         to: '/product/inbox' },
        { label: t('products.whatsapp', 'WhatsApp'),      to: '/product/whatsapp' },
        { label: t('products.bot_builder', 'Bot Builder'),   to: '/product/bot-builder' },
        { label: t('products.ai_studio', 'AI Studio'),     to: '/product/ai' },
        { label: t('products.reports', 'Reports'),       to: '/product/reports' },
        { label: t('products.automations', 'Automations'),   to: '/product/automations' },
        { label: t('products.marketplace', 'Marketplace'),   to: '/product/marketplace-product' },
      ],
    },
    {
      title: t('footer.solutions', 'Solutions'),
      links: [
        { label: t('solutions.agencies', 'For Agencies'),   to: '/solutions/agencies' },
        { label: t('solutions.businesses', 'For Businesses'), to: '/solutions/businesses' },
        { label: t('solutions.real_estate', 'Real Estate'),    to: '/solutions/real-estate' },
        { label: t('solutions.healthcare', 'Healthcare'),     to: '/solutions/clinics' },
        { label: t('solutions.restaurants', 'Restaurants'),    to: '/solutions/restaurants' },
        { label: t('solutions.creators', 'Creators'),       to: '/solutions/creators' },
        { label: t('solutions.ecommerce', 'E-commerce'),     to: '/solutions/ecommerce' },
      ],
    },
    {
      title: t('footer.resources', 'Resources'),
      links: [
        { label: t('nav.customers', 'Customers'),     to: '/customers' },
        { label: t('resources.blog', 'Blog'),          to: '/blog' },
        { label: t('resources.help_center', 'Help Center'),   to: '/help' },
        { label: t('resources.changelog', 'Changelog'),     to: '/changelog' },
        { label: t('resources.status', 'Status'),        to: '/status' },
        { label: t('resources.integrations', 'Integrations'),  to: '/integrations' },
      ],
    },
    {
      title: t('footer.company', 'Company'),
      links: [
        { label: t('nav.about', 'About'),     to: '/about' },
        { label: t('nav.customers', 'Customers'), to: '/customers' },
        { label: t('resources.contact', 'Contact'),   to: '/contact' },
        { label: t('footer.press', 'Press'),     to: '/about#press' },
        { label: t('footer.careers', 'Careers'),   to: '/about#careers' },
      ],
    },
    {
      title: t('footer.legal', 'Legal'),
      links: [
        { label: t('footer.privacy', 'Privacy'),         to: '/privacy' },
        { label: t('footer.terms', 'Terms'),           to: '/terms' },
        { label: t('footer.cookies', 'Cookies'),         to: '/cookies' },
        { label: t('footer.gdpr', 'GDPR'),            to: '/gdpr' },
        { label: t('footer.dpdp', 'DPDP'),            to: '/dpdp' },
        { label: t('footer.security', 'Security'),        to: '/security' },
      ],
    },
  ];

  return (
    <footer
      style={{
        marginTop: 80,
        background: 'var(--surface-card)',
        borderTop: '1px solid var(--border-subtle)',
      }}
    >
      <div
        style={{
          maxWidth: 'var(--container-2xl)',
          margin: '0 auto',
          padding: '64px 32px 32px',
        }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1.6fr) repeat(5, minmax(0, 1fr))',
            gap: 40,
          }}
          className="mkt-footer-grid"
        >
          {/* Brand column */}
          <div>
            <Logo variant="horizontal" height={28} />
            <p style={{
              margin: '14px 0 16px',
              fontSize: 13, lineHeight: 1.6,
              color: 'var(--text-secondary)',
              maxWidth: 280,
            }}>
              {t('footer.tagline', 'The AI marketing OS for modern agencies. Analytics, content, conversations, and ads — for every client, in one place.')}
            </p>
            <div style={{ display: 'flex', gap: 6 }}>
              <SocialIconLink href="https://github.com/bopagenciy/BopSocial"   label="GitHub"   icon={Github} />
              <SocialIconLink href="https://linkedin.com/company/bopsocial"   label="LinkedIn" icon={Linkedin} />
              <SocialIconLink href="https://twitter.com/bopsocial"            label="Twitter"  icon={Twitter} />
              <SocialIconLink href="https://youtube.com/@bopsocial"           label="YouTube"  icon={Youtube} />
            </div>
            {/* Geographic framing intentionally omitted from the global footer.
                Office and contact information lives on /contact and /dpdp. */}
          </div>

          {COLUMNS.map((col) => (
            <div key={col.title}>
              <h3 style={{
                margin: '0 0 12px',
                fontSize: 11, fontWeight: 600,
                letterSpacing: '0.08em', textTransform: 'uppercase',
                color: 'var(--text-tertiary)',
              }}>{col.title}</h3>
              <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {col.links.map((l) => (
                  <li key={l.to + l.label}>
                    <Link
                      to={l.to}
                      style={{
                        fontSize: 13,
                        color: 'var(--text-secondary)',
                        textDecoration: 'none',
                        transition: 'var(--transition-fast)',
                      }}
                      onMouseOver={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; }}
                      onMouseOut={(e)  => { e.currentTarget.style.color = 'var(--text-secondary)'; }}
                    >{l.label}</Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div style={{
          marginTop: 48,
          paddingTop: 24,
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center', justifyContent: 'space-between',
          gap: 16, flexWrap: 'wrap',
          fontSize: 12, color: 'var(--text-tertiary)',
        }}>
          <span>© {year} Bop Social. {t('footer.all_rights_reserved', 'All rights reserved.')}</span>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <Link to="/status" style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              color: 'var(--text-tertiary)', textDecoration: 'none',
            }}>
              <span aria-hidden style={{
                width: 8, height: 8, borderRadius: '50%',
                background: 'var(--success)',
                boxShadow: '0 0 8px rgba(16,185,129,0.6)',
              }} />
              {t('footer.systems_operational', 'All systems operational')}
            </Link>
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              color: 'var(--text-tertiary)',
            }}>
              <Sparkles size={11} /> {t('footer.built_for_universe', 'Built for the Bop Universe')}
            </span>
          </div>
        </div>

        <style>{`
          @media (max-width: 1100px) {
            .mkt-footer-grid {
              grid-template-columns: 1fr 1fr 1fr !important;
            }
            .mkt-footer-grid > div:first-child { grid-column: 1 / -1; }
          }
          @media (max-width: 640px) {
            .mkt-footer-grid { grid-template-columns: 1fr 1fr !important; }
          }
        `}</style>
      </div>
    </footer>
  );
}

function SocialIconLink({ href, label, icon: Icon }) {
  return (
    <a
      href={href} target="_blank" rel="noopener noreferrer" aria-label={label}
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: 32, height: 32,
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-subtle)',
        color: 'var(--text-tertiary)',
        background: 'var(--surface-card)',
        transition: 'var(--transition-fast)',
        textDecoration: 'none',
      }}
      onMouseOver={(e) => {
        e.currentTarget.style.color = 'var(--brand-primary-hover)';
        e.currentTarget.style.borderColor = 'var(--brand-primary-glow)';
      }}
      onMouseOut={(e) => {
        e.currentTarget.style.color = 'var(--text-tertiary)';
        e.currentTarget.style.borderColor = 'var(--border-subtle)';
      }}
    >
      <Icon size={14} strokeWidth={2} />
    </a>
  );
}
