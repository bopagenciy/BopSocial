/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
/**
 * HandoffQueuePage
 *
 * Per-user inbox of CTWA bot conversations that have been handed off to a
 * human. The toggle exposes any unassigned handoffs in the workspace so a
 * teammate can grab one when no one is explicitly tagged.
 *
 * Auto-refreshes every 8s — the queue is meant to feel "live" but we don't
 * want to hammer the API.
 */
import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  UserPlus, RefreshCw, Inbox, ChevronRight, Sparkles, Bot,
} from 'lucide-react';

import { botConversationAPI } from '../../services/api';
import toast from '../../components/ui/toast';


export default function HandoffQueuePage() {
  const { t } = useTranslation('messaging');
  const [items, setItems]                   = useState([]);
  const [loading, setLoading]               = useState(true);
  const [includeUnassigned, setUnassigned]  = useState(false);

  const load = useCallback((silent = false) => {
    if (!silent) setLoading(true);
    botConversationAPI.handoffQueue({
      include_unassigned: includeUnassigned ? '1' : '0',
    })
      .then((r) => setItems(r.data?.results || []))
      .catch(() => { if (!silent) toast.error('Could not load handoff queue'); })
      .finally(() => setLoading(false));
  }, [includeUnassigned]);

  useEffect(() => { load(false); }, [load]);

  // Live-refresh every 8s (silent — no spinner)
  useEffect(() => {
    const t = setInterval(() => load(true), 8000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <div style={{ maxWidth: 980, margin: '0 auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <header style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <span style={{
          width: 40, height: 40,
          background: 'var(--brand-primary-glow)', color: 'var(--brand-primary-hover)',
          borderRadius: 'var(--radius-md)',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <UserPlus size={20} strokeWidth={2.2} />
        </span>
        <div style={{ flex: 1 }}>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
            {t('handoff.title', 'Handoff queue')}
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-secondary)' }}>
            {t('handoff.subtitle', 'Conversations where the bot escalated to a human. Auto-refreshes every 8s.')}
          </p>
        </div>
        <label style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '6px 12px', fontSize: 12, fontWeight: 600,
          color: includeUnassigned ? 'var(--brand-primary-hover)' : 'var(--text-secondary)',
          background: includeUnassigned ? 'var(--brand-primary-soft)' : 'var(--surface-card)',
          border: `1px solid ${includeUnassigned ? 'var(--brand-primary)' : 'var(--border-default)'}`,
          borderRadius: 'var(--radius-pill)', cursor: 'pointer',
        }}>
          <input type="checkbox" checked={includeUnassigned}
                 onChange={(e) => setUnassigned(e.target.checked)}
                 style={{ accentColor: 'var(--brand-primary)' }} />
          {t('handoff.show_unassigned', 'Show unassigned')}
        </label>
        <button type="button" onClick={() => load(false)} aria-label={t('ctwa.refresh', 'Refresh')} style={iconBtn}>
          <RefreshCw size={13} />
        </button>
      </header>

      {loading ? (
        <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-tertiary)' }}>{t('campaigns.loading', 'Loading…')}</div>
      ) : items.length === 0 ? (
        <Empty includeUnassigned={includeUnassigned} t={t} />
      ) : (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.map((c) => <Row key={c.id} conv={c} t={t} />)}
        </ul>
      )}
    </div>
  );
}


function Row({ conv, t }) {
  const handoffAt = conv.handed_off_at
    ? new Date(conv.handed_off_at)
    : conv.ended_at
      ? new Date(conv.ended_at)
      : null;
  const minsAgo = handoffAt ? Math.max(1, Math.round((Date.now() - handoffAt.getTime()) / 60000)) : null;

  return (
    <li>
      <Link to={`/admin/conversations/${conv.id}`} style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: 14,
        background: 'var(--surface-card)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        textDecoration: 'none', color: 'var(--text-primary)',
      }}>
        <span style={{
          width: 40, height: 40, flexShrink: 0,
          background: 'var(--brand-gradient)', color: '#fff',
          borderRadius: '50%',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {(conv.contact_name || conv.contact_phone || '?').charAt(0).toUpperCase()}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {conv.contact_name || conv.contact_phone || `Contact #${conv.contact}`}
          </div>
          <div style={{ marginTop: 3, fontSize: 12, color: 'var(--text-secondary)', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
              <Bot size={11} /> {conv.flow_name || `Flow #${conv.flow}`}
            </span>
            {conv.lead && (
              <span style={{ color: 'var(--success)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                <Sparkles size={11} /> {t('conversations.detail.lead_badge', 'Lead captured')}
              </span>
            )}
            {!conv.handed_off_to_user && (
              <span style={{ color: 'var(--warning)', fontWeight: 600 }}>{t('handoff.unassigned', 'Unassigned')}</span>
            )}
          </div>
        </div>
        {minsAgo && (
          <span style={{
            padding: '3px 10px',
            fontSize: 11, fontWeight: 600,
            color: minsAgo <= 5 ? 'var(--success)' : minsAgo <= 30 ? 'var(--warning)' : 'var(--text-tertiary)',
            background: 'var(--surface-sunken)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-pill)',
            fontVariantNumeric: 'tabular-nums',
          }}>
            {minsAgo < 60 ? `${minsAgo}m ago` : `${Math.round(minsAgo / 60)}h ago`}
          </span>
        )}
        <ChevronRight size={16} style={{ color: 'var(--text-tertiary)' }} />
      </Link>
    </li>
  );
}


function Empty({ includeUnassigned, t }) {
  return (
    <div style={{
      padding: 36, textAlign: 'center',
      background: 'var(--surface-card)',
      border: '1px dashed var(--border-default)',
      borderRadius: 'var(--radius-lg)',
    }}>
      <Inbox size={32} strokeWidth={1.5} style={{ opacity: 0.4 }} />
      <h2 style={{ margin: '12px 0 6px', fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
        {t('handoff.empty_title', 'Queue is clear')}
      </h2>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)' }}>
        {includeUnassigned
          ? t('handoff.empty_desc', 'No conversations currently waiting for human assistance.')
          : t('handoff.empty_desc', 'No conversations are assigned to you. Toggle "Show unassigned" to see open handoffs.')}
      </p>
    </div>
  );
}


const iconBtn = {
  width: 30, height: 30, padding: 0,
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  background: 'transparent', color: 'var(--text-secondary)',
  border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)',
  cursor: 'pointer',
};
