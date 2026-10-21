/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Command } from 'cmdk';
import {
  LayoutDashboard, LineChart, FileText, Search, Send, Inbox, Users2,
  FileType, MessageCircle, Settings, Plus, Upload, Lightbulb, Wand2,
  TrendingUp, AlertCircle, CalendarDays,
  Sparkles, BookOpen, Activity, ShieldCheck, ExternalLink,
  MessageSquare, UserSquare,
} from 'lucide-react';

import { useClients } from '../../hooks/useData';
import useUnifiedSearch from '../../hooks/useUnifiedSearch';

const RECENTS_KEY = 'cmdk:recents';
const RECENTS_MAX = 6;

/**
 * Cmd+K command palette. Aggregates pages + clients + quick actions.
 *
 * Props:
 *   open, onOpenChange   — controlled
 *   basePath             — '/admin' or '/dashboard'
 */
export default function CommandPalette({ open, onOpenChange, basePath }) {
  const { t } = useTranslation('app');
  const navigate = useNavigate();
  const [recents, setRecents] = useState(() => readRecents());
  const [inputValue, setInputValue] = useState('');
  const { clients } = useClients();

  const { results: searchResults, isFetching: searchFetching, debouncedQuery } =
    useUnifiedSearch(inputValue);

  // Cmd+K toggle
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        onOpenChange(!open);
      }
      if (e.key === 'Escape') onOpenChange(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onOpenChange]);

  // Reset the input when the palette closes — opening fresh next time.
  useEffect(() => {
    if (!open) setInputValue('');
  }, [open]);

  const pages = useMemo(() => buildPages(basePath, t), [basePath, t]);
  const actions = useMemo(() => buildActions(basePath, t), [basePath, t]);
  const links = useMemo(() => buildLinks(t), [t]);

  function pick(id, fn) {
    fn();
    addRecent(id);
    setRecents(readRecents());
    onOpenChange(false);
  }

  // Show the cross-feature search section only when the user has actually
  // typed enough — avoids an empty "Search results" header on first open.
  const hasSearchQuery = (debouncedQuery || '').trim().length >= 2;
  const hasSearchHits  = hasSearchQuery && (searchResults.total > 0);

  if (!open) return null;

  return (
    <div
      className="ds-cmdk-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onClick={() => onOpenChange(false)}
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(10, 14, 20, 0.5)',
        backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)',
        zIndex: 500,
        display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
        paddingTop: '15vh',
      }}
    >
      <Command
        label="Command Menu"
        loop
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(640px, 92vw)',
          background: 'var(--surface-elevated)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-lg)',
          overflow: 'hidden',
          color: 'var(--text-primary)',
        }}
      >
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '14px 16px',
          borderBottom: '1px solid var(--border-subtle)',
        }}>
          <Search size={16} color="var(--text-tertiary)" />
          <Command.Input
            autoFocus
            value={inputValue}
            onValueChange={setInputValue}
            placeholder={t('command_palette.placeholder', 'Search pages, posts, leads, conversations…')}
            style={{
              flex: 1, border: 'none', outline: 'none',
              background: 'transparent',
              fontSize: 15, fontFamily: 'var(--font-sans)',
              color: 'var(--text-primary)',
            }}
          />
          {searchFetching && (
            <span
              aria-label={t('command_palette.searching', 'Searching…')}
              style={{ fontSize: 11, color: 'var(--text-tertiary)' }}
            >
              {t('command_palette.searching', 'Searching…')}
            </span>
          )}
        </div>

        <Command.List style={{ maxHeight: 420, overflowY: 'auto', padding: '8px 8px 12px' }}>
          <Command.Empty style={{
            padding: '32px 16px', textAlign: 'center',
            color: 'var(--text-tertiary)', fontSize: 13,
          }}>
            {t('command_palette.no_results', 'No results found.')}
          </Command.Empty>

          {/* Cross-feature search results render before static navigation
              so the user sees their actual content first. */}
          {hasSearchHits && (
            <SearchResultGroups
              results={searchResults}
              onPick={(id, link) => pick(id, () => navigate(link))}
            />
          )}

          {recents.length > 0 && !hasSearchQuery && (
            <Group heading={t('command_palette.recent', 'Recent')}>
              {recents.map((r) => {
                const item = [...pages, ...actions].find((p) => p.id === r);
                if (!item) return null;
                return (
                  <Item key={item.id} item={item} onSelect={() => pick(item.id, item.run)} />
                );
              })}
            </Group>
          )}

          <Group heading={t('command_palette.pages', 'Pages')}>
            {pages.map((p) => (
              <Item key={p.id} item={p} onSelect={() => pick(p.id, () => navigate(p.path))} />
            ))}
          </Group>

          <Group heading={t('command_palette.quick_actions', 'Quick actions')}>
            {actions.map((a) => (
              <Item key={a.id} item={a} onSelect={() => pick(a.id, a.run)} />
            ))}
          </Group>

          {(clients || []).length > 0 && (
            <Group heading={t('command_palette.clients', 'Clients')}>
              {(clients || []).slice(0, 8).map((c) => (
                <Item
                  key={`client-${c.id}`}
                  item={{
                    id: `client-${c.id}`,
                    label: c.company,
                    hint: t('command_palette.switch_to_client', 'Switch to client'),
                    icon: Users2,
                  }}
                  onSelect={() => pick(`client-${c.id}`, () => navigate(`/admin/client/${c.id}`))}
                />
              ))}
            </Group>
          )}

          <Group heading={t('command_palette.help_resources', 'Help & resources')}>
            {links.map((l) => (
              <Item
                key={l.id}
                item={l}
                onSelect={() => pick(l.id, () => window.open(l.path, '_blank', 'noopener'))}
              />
            ))}
          </Group>
        </Command.List>

        <div style={{
          padding: '8px 14px',
          borderTop: '1px solid var(--border-subtle)',
          background: 'var(--surface-sunken)',
          fontSize: 11, color: 'var(--text-tertiary)',
          display: 'flex', justifyContent: 'space-between',
        }}>
          <span>{t('command_palette.nav_hint', '↑↓ to navigate · ↵ to select')}</span>
          <span>{t('command_palette.close_hint', 'esc to close')}</span>
        </div>
      </Command>
    </div>
  );
}

/**
 *
 * Each input bucket (posts / leads / conversations / contacts) becomes a
 * group; each hit becomes an Item that navigates to the backend-provided
 * `deep_link`. We let cmdk auto-hide empty groups so we don't need to
 * conditionally skip categories — passing the full payload is enough.
 */
function SearchResultGroups({ results, onPick }) {
  const { t } = useTranslation('app');
  return (
    <>
      {(results.posts || []).length > 0 && (
        <Group heading={t('command_palette.posts', 'Posts')}>
          {results.posts.map((p) => (
            <Item
              key={`s-post-${p.id}`}
              item={{
                id:    `s-post-${p.id}`,
                label: p.title || p.preview || 'Untitled post',
                hint:  `Post · ${p.status || 'draft'}`,
                icon:  FileType,
              }}
              onSelect={() => onPick(`s-post-${p.id}`, p.deep_link)}
            />
          ))}
        </Group>
      )}
      {(results.leads || []).length > 0 && (
        <Group heading={t('command_palette.leads', 'Leads')}>
          {results.leads.map((l) => (
            <Item
              key={`s-lead-${l.id}`}
              item={{
                id:    `s-lead-${l.id}`,
                label: l.name || l.phone || 'Lead',
                hint:  `Lead · ${l.status || 'new'}` + (l.email ? ` · ${l.email}` : ''),
                icon:  UserSquare,
              }}
              onSelect={() => onPick(`s-lead-${l.id}`, l.deep_link)}
            />
          ))}
        </Group>
      )}
      {(results.conversations || []).length > 0 && (
        <Group heading={t('command_palette.conversations', 'Conversations')}>
          {results.conversations.map((c) => (
            <Item
              key={`s-conv-${c.id}`}
              item={{
                id:    `s-conv-${c.id}`,
                label: c.contact || '(unknown)',
                hint:  `${c.platform || 'inbox'} · ${(c.preview || '').slice(0, 80)}`,
                icon:  MessageSquare,
              }}
              onSelect={() => onPick(`s-conv-${c.id}`, c.deep_link)}
            />
          ))}
        </Group>
      )}
      {(results.contacts || []).length > 0 && (
        <Group heading={t('command_palette.contacts', 'Contacts')}>
          {results.contacts.map((ct) => (
            <Item
              key={`s-contact-${ct.id}`}
              item={{
                id:    `s-contact-${ct.id}`,
                label: ct.name || ct.phone || 'Contact',
                hint:  ct.phone || '',
                icon:  Users2,
              }}
              onSelect={() => onPick(`s-contact-${ct.id}`, ct.deep_link)}
            />
          ))}
        </Group>
      )}
    </>
  );
}


function Group({ heading, children }) {
  // cmdk hides empty groups automatically.
  return (
    <Command.Group
      heading={
        <span style={{
          display: 'inline-block', padding: '8px 8px 4px',
          fontSize: 11, fontWeight: 600,
          letterSpacing: 0.6, textTransform: 'uppercase',
          color: 'var(--text-tertiary)',
        }}>
          {heading}
        </span>
      }
    >
      {children}
    </Command.Group>
  );
}

function Item({ item, onSelect }) {
  const Icon = item.icon || Search;
  return (
    <Command.Item
      value={`${item.label} ${item.hint || ''} ${item.keywords || ''}`}
      onSelect={onSelect}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '8px 10px',
        margin: '1px 0',
        borderRadius: 'var(--radius-sm)',
        fontSize: 13,
        color: 'var(--text-primary)',
        cursor: 'pointer',
      }}
    >
      <span style={{
        width: 28, height: 28, borderRadius: 'var(--radius-sm)',
        background: 'var(--surface-sunken)',
        color: 'var(--text-secondary)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon size={14} strokeWidth={2} />
      </span>
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={{ display: 'block', fontWeight: 500 }}>{item.label}</span>
        {item.hint && (
          <span style={{ display: 'block', fontSize: 11, color: 'var(--text-tertiary)' }}>
            {item.hint}
          </span>
        )}
      </span>
    </Command.Item>
  );
}

function buildPages(basePath, t) {
  const tr = (k, d) => t ? t(k, d) : d;
  return [
    // Analytics
    { id: 'analytics-dashboard', label: tr('sidebar.items.dashboard', 'Dashboard'), hint: 'Analytics overview', icon: LayoutDashboard, path: `${basePath}/analytics/dashboard` },
    { id: 'analytics-analytics', label: tr('sidebar.items.analytics', 'Analytics'), hint: 'Deep metrics', icon: LineChart, path: `${basePath}/analytics/analytics` },
    { id: 'analytics-reports', label: tr('sidebar.items.reports', 'Reports'), hint: 'PDF reports', icon: FileText, path: `${basePath}/analytics/reports` },
    { id: 'analytics-calendar', label: tr('sidebar.items.calendar', 'Content Calendar'), hint: 'Plan & schedule', icon: CalendarDays, path: `${basePath}/analytics/calendar` },
    { id: 'analytics-roi', label: tr('sidebar.items.roi_calculator', 'ROI Calculator'), hint: 'Revenue forecasting', icon: TrendingUp, path: `${basePath}/analytics/roi` },
    { id: 'analytics-alerts', label: tr('sidebar.items.alerts', 'Alerts'), hint: 'Anomaly notifications', icon: AlertCircle, path: `${basePath}/analytics/alerts` },
    { id: 'analytics-caption', label: tr('sidebar.items.caption_writer', 'Caption Writer'), hint: 'AI-powered captions', icon: Wand2, path: `${basePath}/analytics/caption-writer` },
    { id: 'analytics-ideas', label: tr('sidebar.items.post_ideas', 'Post Ideas'), hint: 'AI content brainstorm', icon: Lightbulb, path: `${basePath}/analytics/post-ideas` },
    // Messaging
    { id: 'messaging-dashboard', label: tr('modules.messaging.label', 'Messaging dashboard'), hint: 'WhatsApp overview', icon: MessageCircle, path: `${basePath}/messaging` },
    { id: 'messaging-inbox', label: tr('sidebar.items.inbox', 'Inbox'), hint: 'Conversations', icon: Inbox, path: `${basePath}/messaging/inbox` },
    { id: 'messaging-campaigns', label: tr('sidebar.items.campaigns', 'Campaigns'), hint: 'Broadcast outreach', icon: Send, path: `${basePath}/messaging/campaigns` },
    { id: 'messaging-templates', label: tr('sidebar.items.templates', 'Templates'), hint: 'Approved templates', icon: FileType, path: `${basePath}/messaging/templates` },
    { id: 'messaging-contacts', label: tr('sidebar.items.contacts', 'Contacts'), hint: 'Audience', icon: Users2, path: `${basePath}/messaging/contacts` },
    { id: 'messaging-account', label: tr('sidebar.items.account', 'Pinbot account'), hint: 'WhatsApp setup', icon: Settings, path: `${basePath}/messaging/account` },
  ];
}

function buildActions(basePath, t) {
  const tr = (k, d) => t ? t(k, d) : d;
  return [
    {
      id: 'action-new-campaign',
      label: tr('command_palette.actions.send_message', 'Send a message'),
      hint: tr('command_palette.actions.send_message_hint', 'Open inbox to compose'),
      icon: Send,
      run: () => location.assign(`${basePath}/messaging/inbox`),
    },
    {
      id: 'action-create-campaign',
      label: tr('command_palette.actions.create_campaign', 'Create a campaign'),
      hint: tr('command_palette.actions.create_campaign_hint', 'New broadcast'),
      icon: Plus,
      run: () => location.assign(`${basePath}/messaging/campaigns?new=1`),
    },
    {
      id: 'action-upload-contacts',
      label: tr('command_palette.actions.upload_contacts', 'Upload contacts'),
      hint: tr('command_palette.actions.upload_contacts_hint', 'Import a CSV'),
      icon: Upload,
      run: () => location.assign(`${basePath}/messaging/contacts?import=1`),
    },
    {
      id: 'action-new-template',
      label: tr('command_palette.actions.new_template', 'Create a template'),
      hint: tr('command_palette.actions.new_template_hint', 'WhatsApp template'),
      icon: FileType,
      run: () => location.assign(`${basePath}/messaging/templates?new=1`),
    },
  ];
}

function buildLinks(t) {
  const tr = (k, d) => t ? t(k, d) : d;
  return [
    { id: 'link-changelog', label: tr('command_palette.links.changelog', "What's new"), hint: tr('command_palette.links.changelog_hint', 'Recent product updates'), icon: Sparkles, path: '/changelog' },
    { id: 'link-help', label: tr('command_palette.links.help', 'Help center'), hint: tr('command_palette.links.help_hint', 'Guides + troubleshooting'), icon: BookOpen, path: '/help' },
    { id: 'link-status', label: tr('command_palette.links.status', 'System status'), hint: tr('command_palette.links.status_hint', 'Live uptime + incidents'), icon: Activity, path: '/status' },
    { id: 'link-security', label: tr('command_palette.links.security', 'Security & compliance'), hint: tr('command_palette.links.security_hint', 'GDPR, DPDP, certifications'), icon: ShieldCheck, path: '/security' },
    { id: 'link-contact', label: tr('command_palette.links.contact', 'Contact support'), hint: tr('command_palette.links.contact_hint', 'Send us a message'), icon: ExternalLink, path: '/contact' },
  ];
}

function readRecents() {
  try {
    const raw = localStorage.getItem(RECENTS_KEY);
    return raw ? JSON.parse(raw).slice(0, RECENTS_MAX) : [];
  } catch {
    return [];
  }
}

function addRecent(id) {
  try {
    const list = readRecents().filter((x) => x !== id);
    list.unshift(id);
    localStorage.setItem(RECENTS_KEY, JSON.stringify(list.slice(0, RECENTS_MAX)));
  } catch {}
}
