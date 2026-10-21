/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Inbox, Search, Star, Archive, ArchiveRestore, CheckCircle2, X, Send,
  MessageSquare, AtSign, MessageCircle, Loader2, Filter,
  Smile, Frown, Meh, Sparkles,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';

import PageHeader from '../../components/layout/PageHeader';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import Badge from '../../components/ui/Badge';
import EmptyState from '../../components/ui/EmptyState';
import AIReplySuggestions from '../../components/ai/AIReplySuggestions';
import { useConversations, useConversation } from '../../hooks/useInbox';
import { inboxAPI } from '../../services/api';
import { useAuth } from '../../hooks/useAuth';
import { formatDate, formatTime, formatRelativeTime } from '../../utils/formatters';

const TYPE_FILTERS = [
  { id: '',         label: 'All',      icon: Inbox },
  { id: 'comment',  label: 'Comments', icon: MessageSquare },
  { id: 'dm',       label: 'DMs',      icon: MessageCircle },
  { id: 'mention',  label: 'Mentions', icon: AtSign },
  { id: 'review',   label: 'Reviews',  icon: Star },
];

const PLATFORM_PILLS = [
  { id: '',                   label: 'All',   color: 'var(--text-tertiary)' },
  { id: 'facebook',           label: 'FB',    color: '#1877F2' },
  { id: 'instagram',          label: 'IG',    color: '#E1306C' },
  { id: 'youtube',            label: 'YT',    color: '#FF0000' },
  { id: 'linkedin',           label: 'LI',    color: '#0A66C2' },
  { id: 'google_my_business', label: 'GMB',   color: '#34A853' },
];

const SENTIMENT = {
  positive: { color: 'var(--success)', icon: Smile,   label: 'Positive' },
  neutral:  { color: 'var(--text-tertiary)', icon: Meh, label: 'Neutral' },
  negative: { color: 'var(--danger)',  icon: Frown,   label: 'Negative' },
  unknown:  { color: 'var(--text-tertiary)', icon: null, label: 'Unknown' },
};

export default function UnifiedInboxPage() {
  const { t } = useTranslation('engagement');
  const [type, setType] = useState('');
  const [platform, setPlatform] = useState('');
  const [sentiment, setSentiment] = useState('');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [starredOnly, setStarredOnly] = useState(false);
  const [search, setSearch] = useState('');
  const [activeId, setActiveId] = useState(null);

  const params = {};
  if (type) params.type = type;
  if (platform) params.platform = platform;
  if (sentiment) params.sentiment = sentiment;
  if (unreadOnly) params.unread = 1;
  if (starredOnly) params.starred = 1;
  if (search) params.search = search;

  const { data: conversations, refetch: refetchList, loading } = useConversations(params);
  const { data: thread, refetch: refetchThread } = useConversation(activeId);

  // Auto-select the first conversation when the list loads
  useEffect(() => {
    if (!activeId && conversations.length > 0) {
      setActiveId(conversations[0].id);
    }
  }, [conversations, activeId]);

  // Mark-read on selection
  useEffect(() => {
    if (activeId) {
      const convo = conversations.find((c) => c.id === activeId);
      if (convo && convo.unread_count > 0) {
        inboxAPI.conversations.markRead(activeId).then(() => refetchList()).catch(() => {});
      }
    }
  // eslint-disable-next-line
  }, [activeId]);

  return (
    <div style={{ paddingBottom: 0 }}>
      <PageHeader
        title={t('inbox.title', 'Inbox')}
        subtitle={t('inbox.subtitle', 'Comments, DMs and mentions across every platform')}
      />

      <div className="inbox-grid" style={{
        display: 'grid',
        gridTemplateColumns: '240px 340px minmax(0, 1fr)',
        gap: 0,
        padding: '0 24px',
        height: 'calc(100vh - 160px)',
      }}>
        {/* ── LEFT: filters ─────────────────────────────────────────── */}
        <FiltersColumn
          type={type} setType={setType}
          platform={platform} setPlatform={setPlatform}
          sentiment={sentiment} setSentiment={setSentiment}
          unreadOnly={unreadOnly} setUnreadOnly={setUnreadOnly}
          starredOnly={starredOnly} setStarredOnly={setStarredOnly}
          search={search} setSearch={setSearch}
        />

        {/* ── MIDDLE: conversation list ─────────────────────────────── */}
        <ListColumn
          conversations={conversations}
          activeId={activeId}
          onSelect={setActiveId}
          loading={loading}
        />

        {/* ── RIGHT: thread ─────────────────────────────────────────── */}
        <ThreadColumn
          thread={thread}
          onAction={() => { refetchList(); refetchThread(); }}
        />
      </div>

      <style>{`
        @media (max-width: 1024px) {
          .inbox-grid { grid-template-columns: 1fr !important; height: auto !important; }
          .inbox-grid > div { display: none; }
          .inbox-grid > div:nth-child(2) { display: flex !important; height: 60vh; }
        }
      `}</style>
    </div>
  );
}

/* ── FILTERS COLUMN ────────────────────────────────────────────────────── */
function FiltersColumn({
  type, setType, platform, setPlatform, sentiment, setSentiment,
  unreadOnly, setUnreadOnly, starredOnly, setStarredOnly, search, setSearch,
}) {
  const { t } = useTranslation('engagement');
  return (
    <Card padding="none" style={{
      overflow: 'hidden', display: 'flex', flexDirection: 'column',
      borderRight: 'none', borderRadius: 'var(--radius-lg) 0 0 var(--radius-lg)',
    }}>
      <div style={{ padding: 14, borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ position: 'relative' }}>
          <Search size={14} color="var(--text-tertiary)"
                  style={{ position: 'absolute', top: 11, left: 10 }} />
          <input
            placeholder={t('inbox.search_placeholder', 'Search…')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              width: '100%', height: 36,
              padding: '0 10px 0 30px',
              background: 'var(--surface-sunken)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              fontSize: 13, outline: 'none', boxSizing: 'border-box',
              color: 'var(--text-primary)',
              minHeight: 'unset',
            }}
          />
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
        <SectionHeader>{t('inbox.filter_sections.type', 'Type')}</SectionHeader>
        {TYPE_FILTERS.map((f) => (
          <FilterRow
            key={f.id}
            icon={f.icon}
            label={t(`inbox.types.${f.id || 'all'}`, f.label)}
            active={type === f.id}
            onClick={() => setType(f.id)}
          />
        ))}

        <SectionHeader>{t('inbox.filter_sections.platform', 'Platform')}</SectionHeader>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '4px 10px 8px' }}>
          {PLATFORM_PILLS.map((p) => {
            const active = platform === p.id;
            const label = p.id === '' ? t('inbox.types.all', 'All') : p.label;
            return (
              <button
                key={p.id || 'all'}
                type="button"
                onClick={() => setPlatform(p.id)}
                style={{
                  padding: '4px 10px', borderRadius: 'var(--radius-pill)',
                  border: `1px solid ${active ? 'transparent' : 'var(--border-subtle)'}`,
                  background: active ? p.color : 'var(--surface-card)',
                  color: active ? '#fff' : 'var(--text-secondary)',
                  fontSize: 11, fontWeight: 600, cursor: 'pointer',
                  minHeight: 'unset', minWidth: 'unset',
                  transition: 'var(--transition-fast)',
                }}
              >
                {label}
              </button>
            );
          })}
        </div>

        <SectionHeader>{t('inbox.filter_sections.sentiment', 'Sentiment')}</SectionHeader>
        {[
          { id: '',         label: t('inbox.sentiments.all', 'All') },
          { id: 'positive', label: t('inbox.sentiments.positive', 'Positive'), icon: Smile,  color: 'var(--success)' },
          { id: 'neutral',  label: t('inbox.sentiments.neutral', 'Neutral'),  icon: Meh,    color: 'var(--text-tertiary)' },
          { id: 'negative', label: t('inbox.sentiments.negative', 'Negative'), icon: Frown,  color: 'var(--danger)' },
        ].map((s) => (
          <FilterRow key={s.id || 'all'} icon={s.icon} label={s.label}
                     iconColor={s.color}
                     active={sentiment === s.id} onClick={() => setSentiment(s.id)} />
        ))}

        <SectionHeader>{t('inbox.filter_sections.quick', 'Quick')}</SectionHeader>
        <FilterRow icon={Inbox} label={t('inbox.quick.unread_only', 'Unread only')}
                    active={unreadOnly} onClick={() => setUnreadOnly((v) => !v)} />
        <FilterRow icon={Star} label={t('inbox.quick.starred_only', 'Starred only')}
                    active={starredOnly} onClick={() => setStarredOnly((v) => !v)} />
      </div>
    </Card>
  );
}

function SectionHeader({ children }) {
  return (
    <div style={{
      padding: '12px 12px 6px',
      fontSize: 11, fontWeight: 600,
      color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: 0.6,
    }}>
      {children}
    </div>
  );
}

function FilterRow({ icon: Icon, label, active, onClick, iconColor }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 8,
        width: '100%', padding: '8px 12px',
        background: active ? 'var(--brand-primary-glow)' : 'transparent',
        border: 'none', borderRadius: 'var(--radius-sm)',
        color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
        fontSize: 13, fontWeight: active ? 600 : 500,
        cursor: 'pointer', textAlign: 'left',
        minHeight: 'unset', minWidth: 'unset',
        transition: 'var(--transition-fast)',
      }}
    >
      {Icon && <Icon size={14} color={iconColor || (active ? 'var(--text-primary)' : 'var(--text-tertiary)')} />}
      <span style={{ flex: 1 }}>{label}</span>
    </button>
  );
}

/* ── LIST COLUMN ───────────────────────────────────────────────────────── */
function ListColumn({ conversations, activeId, onSelect, loading }) {
  const { t } = useTranslation('engagement');
  return (
    <Card padding="none" style={{
      overflow: 'hidden', display: 'flex', flexDirection: 'column',
      borderRadius: 0, borderLeft: 'none', borderRight: 'none',
    }}>
      <div style={{
        padding: 14, borderBottom: '1px solid var(--border-subtle)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-tertiary)',
                       textTransform: 'uppercase', letterSpacing: 0.4 }}>
          {conversations.length === 1
            ? t('inbox.conversations_count_one', '1 conversation', { count: 1 })
            : t('inbox.conversations_count_other', '{{count}} conversations', { count: conversations.length })}
        </span>
      </div>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loading && (
          <div style={{ padding: 32, textAlign: 'center' }}>
            <Loader2 size={18} className="ds-spin" color="var(--text-tertiary)" />
          </div>
        )}
        {!loading && conversations.length === 0 && (
          <EmptyState
            icon={Inbox}
            title={t('inbox.empty_title', 'Inbox zero')}
            description={t('inbox.empty_desc', "You're all caught up. New comments and messages will appear here as they arrive.")}
          />
        )}
        {conversations.map((c) => (
          <ConversationRow
            key={c.id}
            conv={c}
            active={c.id === activeId}
            onClick={() => onSelect(c.id)}
          />
        ))}
      </div>
      <style>{`.ds-spin { animation: ds-spin 0.9s linear infinite; } @keyframes ds-spin { to { transform: rotate(360deg); } }`}</style>
    </Card>
  );
}

function ConversationRow({ conv, active, onClick }) {
  const { t } = useTranslation('engagement');
  const platform = PLATFORM_PILLS.find((p) => p.id === conv.platform);
  const sent = SENTIMENT[conv.sentiment] || SENTIMENT.unknown;
  const initial = (conv.contact_name || conv.contact_handle || '?')[0].toUpperCase();

  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 10,
        width: '100%', padding: '12px 14px',
        background: active ? 'var(--brand-primary-glow)' : 'transparent',
        border: 'none', borderBottom: '1px solid var(--border-subtle)',
        cursor: 'pointer', textAlign: 'left',
        minHeight: 'unset', minWidth: 'unset',
        transition: 'var(--transition-fast)',
      }}
    >
      <div style={{ position: 'relative', flexShrink: 0 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 999,
          background: `linear-gradient(135deg, ${platform?.color || 'var(--text-tertiary)'}, ${shade(platform?.color || 'var(--text-tertiary)', -15)})`,
          color: '#fff', fontWeight: 700, fontSize: 14,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {initial}
        </div>
        <div style={{
          position: 'absolute', bottom: -2, right: -2,
          width: 14, height: 14, borderRadius: 999,
          background: 'var(--surface-card)', border: '2px solid var(--surface-card)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 8, fontWeight: 700, color: platform?.color,
        }}>
          {(platform?.label || '?').slice(0, 2)}
        </div>
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
          <span style={{
            fontSize: 13, fontWeight: 600,
            color: 'var(--text-primary)',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            flex: 1,
          }}>
            {conv.contact_name || conv.contact_handle || t('inbox.unknown_contact', 'Unknown')}
          </span>
          {conv.is_starred && <Star size={11} color="var(--warning)" fill="var(--warning)" />}
          {conv.unread_count > 0 && (
            <span style={{
              minWidth: 18, height: 18, padding: '0 5px',
              background: 'var(--brand-primary-hover)', color: '#fff',
              borderRadius: 999, fontSize: 10, fontWeight: 700,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {conv.unread_count}
            </span>
          )}
        </div>
        <div style={{
          fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4,
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          marginBottom: 4,
        }}>
          {conv.last_message_preview || ''}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {sent.icon && <sent.icon size={11} color={sent.color} />}
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
            {fmtTime(conv.last_message_at)}
          </span>
        </div>
      </div>
    </button>
  );
}

/* ── THREAD COLUMN ─────────────────────────────────────────────────────── */
function ThreadColumn({ thread, onAction }) {
  const { t } = useTranslation('engagement');
  const { user } = useAuth();
  const scrollRef = useRef();
  const [replyText, setReplyText] = useState('');
  const [sending, setSending] = useState(false);

  // Auto-scroll to the bottom on thread change
  useEffect(() => {
    if (scrollRef.current && thread?.messages?.length) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [thread?.id, thread?.messages?.length]);

  if (!thread) {
    return (
      <Card padding="none" style={{
        overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center',
        borderRadius: '0 var(--radius-lg) var(--radius-lg) 0', borderLeft: 'none',
      }}>
        <EmptyState
          icon={MessageSquare}
          title={t('inbox.select_conversation_title', 'Select a conversation')}
          description={t('inbox.select_conversation_desc', 'Pick a conversation from the list to read it and reply.')}
        />
      </Card>
    );
  }

  const platform = PLATFORM_PILLS.find((p) => p.id === thread.platform);

  async function send() {
    const text = replyText.trim();
    if (!text) return;
    setSending(true);
    try {
      await inboxAPI.conversations.reply(thread.id, text);
      setReplyText('');
      onAction?.();
      toast.success(t('inbox.reply_sent', 'Reply sent'));
    } catch (e) {
      const code = e.response?.data?.code;
      if (code === 'token_expired') {
        toast.error(t('inbox.token_expired', '{{platform}} token expired — please reconnect.', { platform: thread.platform }));
      } else {
        toast.error(e.response?.data?.detail || t('inbox.reply_failed', 'Reply failed'));
      }
    } finally {
      setSending(false);
    }
  }

  async function toggleStar() {
    if (thread.is_starred) await inboxAPI.conversations.unstar(thread.id);
    else                    await inboxAPI.conversations.star(thread.id);
    onAction?.();
  }
  async function toggleArchive() {
    if (thread.is_archived) await inboxAPI.conversations.unarchive(thread.id);
    else                     await inboxAPI.conversations.archive(thread.id);
    onAction?.();
  }
  async function toggleResolve() {
    if (thread.is_resolved) await inboxAPI.conversations.reopen(thread.id);
    else                     await inboxAPI.conversations.resolve(thread.id);
    onAction?.();
  }

  // Last inbound message — used to show AI suggested reply if available
  const lastInbound = (thread.messages || [])
    .filter((m) => m.direction === 'inbound')
    .slice(-1)[0];

  return (
    <Card padding="none" style={{
      overflow: 'hidden', display: 'flex', flexDirection: 'column',
      borderRadius: '0 var(--radius-lg) var(--radius-lg) 0', borderLeft: 'none',
    }}>
      {/* Thread header */}
      <div style={{
        padding: 14, borderBottom: '1px solid var(--border-subtle)',
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <div style={{
          width: 36, height: 36, borderRadius: 999,
          background: `linear-gradient(135deg, ${platform?.color || 'var(--text-tertiary)'}, ${shade(platform?.color || 'var(--text-tertiary)', -15)})`,
          color: '#fff', fontWeight: 700, fontSize: 13,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {(thread.contact_name || thread.contact_handle || '?')[0].toUpperCase()}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
            {thread.contact_name || thread.contact_handle || t('inbox.unknown_contact', 'Unknown')}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
            <span style={{ color: platform?.color, fontWeight: 600 }}>{platform?.label}</span>
            <span>·</span>
            <span>{t(`inbox.types.${thread.type}`, thread.type)}</span>
            {thread.contact_handle && (
              <>
                <span>·</span>
                <span>@{thread.contact_handle}</span>
              </>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <ActionIcon
            icon={Star}
            active={thread.is_starred}
            onClick={toggleStar}
            ariaLabel={thread.is_starred ? t('inbox.unstar', 'Unstar') : t('inbox.star', 'Star')}
          />
          <ActionIcon
            icon={thread.is_archived ? ArchiveRestore : Archive}
            active={thread.is_archived}
            onClick={toggleArchive}
            ariaLabel={thread.is_archived ? t('inbox.unarchive', 'Restore') : t('inbox.archive', 'Archive')}
          />
          <ActionIcon
            icon={CheckCircle2}
            active={thread.is_resolved}
            onClick={toggleResolve}
            ariaLabel={thread.is_resolved ? t('inbox.reopen', 'Reopen') : t('inbox.resolve', 'Resolve')}
          />
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} style={{
        flex: 1, overflowY: 'auto', padding: 16,
        background: 'var(--surface-sunken)',
        display: 'flex', flexDirection: 'column', gap: 8,
      }}>
        {(thread.messages || []).map((m) => <Bubble key={m.id} msg={m} />)}
      </div>

      {/* Reply box */}
      <div style={{ padding: 12, borderTop: '1px solid var(--border-subtle)', background: 'var(--surface-card)' }}>
        {/* Suggested reply variants for the latest inbound message */}
        {lastInbound && !thread.is_resolved && (
          <AIReplySuggestions
            clientId={user?.client_id || thread.client}
            messageId={lastInbound.id}
            platform={thread.platform}
            senderName={thread.contact_name || ''}
            onPick={(text) => setReplyText(text)}
            autoLoad={false}
          />
        )}
        {lastInbound?.ai_suggested_reply && (
          <button
            type="button"
            onClick={() => setReplyText(lastInbound.ai_suggested_reply)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 10px',
              background: 'var(--brand-primary-glow)',
              color: 'var(--brand-primary-hover)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-pill)',
              fontSize: 11, fontWeight: 600,
              cursor: 'pointer', marginBottom: 8,
              minHeight: 'unset', minWidth: 'unset',
            }}
          >
            <Sparkles size={11} />
            {t('inbox.ai_suggests', 'AI suggests: {{preview}}…', { preview: lastInbound.ai_suggested_reply.slice(0, 60) })}
          </button>
        )}
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <textarea
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); send(); }
            }}
            placeholder={thread.is_resolved ? t('inbox.resolved_placeholder', 'Conversation resolved — reopen to reply') : t('inbox.reply_placeholder', 'Type a reply… (⌘↵ to send)')}
            disabled={thread.is_resolved}
            rows={2}
            style={{
              flex: 1, resize: 'vertical',
              padding: '10px 12px',
              background: 'var(--surface-sunken)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              fontSize: 13, fontFamily: 'inherit',
              color: 'var(--text-primary)',
              outline: 'none', boxSizing: 'border-box',
              minHeight: 'unset',
            }}
          />
          <Button
            icon={Send}
            onClick={send}
            loading={sending}
            disabled={!replyText.trim() || thread.is_resolved}
          >
            {t('inbox.send_reply', 'Send')}
          </Button>
        </div>
      </div>
    </Card>
  );
}

function ActionIcon({ icon: Icon, active, onClick, ariaLabel }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      title={ariaLabel}
      style={{
        width: 32, height: 32, borderRadius: 'var(--radius-sm)',
        background: active ? 'var(--brand-primary-glow)' : 'transparent',
        color: active ? 'var(--brand-primary-hover)' : 'var(--text-tertiary)',
        border: 'none', cursor: 'pointer',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        minHeight: 'unset', minWidth: 'unset',
        transition: 'var(--transition-fast)',
      }}
    >
      <Icon size={14} />
    </button>
  );
}

function Bubble({ msg }) {
  const { t } = useTranslation('engagement');
  const isOut = msg.direction === 'outbound';
  const sent = SENTIMENT[msg.sentiment] || SENTIMENT.unknown;
  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      alignItems: isOut ? 'flex-end' : 'flex-start',
      gap: 2,
    }}>
      <div style={{
        maxWidth: '75%',
        padding: '10px 14px',
        borderRadius: 16,
        background: isOut
          ? 'linear-gradient(135deg, #00CCF5, #00A8D8)'
          : 'var(--surface-card)',
        color: isOut ? '#fff' : 'var(--text-primary)',
        fontSize: 13, lineHeight: 1.5,
        boxShadow: isOut ? '0 2px 6px rgba(0,168,216,0.15)' : 'var(--shadow-sm)',
        border: isOut ? 'none' : '1px solid var(--border-subtle)',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>
        {!isOut && msg.author_name && (
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 4 }}>
            {msg.author_name}
          </div>
        )}
        {msg.content || <em style={{ opacity: 0.7 }}>{t('inbox.no_content', '[no content]')}</em>}
      </div>
      <div style={{
        display: 'flex', gap: 6, alignItems: 'center',
        fontSize: 10, color: 'var(--text-tertiary)',
        padding: '0 6px',
      }}>
        <span>{fmtDateTime(msg.sent_at || msg.created_at)}</span>
        {!isOut && sent.icon && (
          <>
            <span>·</span>
            <sent.icon size={10} color={sent.color} />
          </>
        )}
      </div>
    </div>
  );
}

/* ── helpers ───────────────────────────────────────────────────────────── */
function fmtTime(iso) {
  if (!iso) return '';
  return formatRelativeTime(iso);
}

function fmtDateTime(iso) {
  if (!iso) return '';
  const dateStr = formatDate(iso, { month: 'short', day: 'numeric' });
  const timeStr = formatTime(iso, { hour: '2-digit', minute: '2-digit' });
  return `${dateStr} ${timeStr}`;
}

function shade(hex, pct) {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) return hex;
  let n = parseInt(m[1], 16);
  let r = (n >> 16) + Math.round(255 * pct / 100);
  let g = ((n >> 8) & 0xff) + Math.round(255 * pct / 100);
  let b = (n & 0xff) + Math.round(255 * pct / 100);
  r = Math.max(0, Math.min(255, r));
  g = Math.max(0, Math.min(255, g));
  b = Math.max(0, Math.min(255, b));
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
}

