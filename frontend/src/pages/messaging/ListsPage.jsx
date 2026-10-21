/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, ListChecks, Trash2, Users2, Calendar } from 'lucide-react';

import PageHeader from '../../components/layout/PageHeader';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import EmptyState from '../../components/ui/EmptyState';
import Badge from '../../components/ui/Badge';
import { useWhatsAppLists } from '../../hooks/useWhatsApp';
import { whatsappAPI } from '../../services/api';

export default function ListsPage() {
  const { t } = useTranslation('messaging');
  const { data: lists, refetch, loading } = useWhatsAppLists();
  const [showCreate, setShowCreate] = useState(false);

  return (
    <div style={{ paddingBottom: 32 }}>
      <PageHeader
        title={t('lists.title', 'Lists')}
        subtitle={t('lists.subtitle', 'Segment your contacts into reusable audiences')}
        action={
          <Button icon={Plus} onClick={() => setShowCreate(true)}>{t('lists.new_list', 'New List')}</Button>
        }
      />

      <div style={{ padding: '0 24px' }}>
        {!loading && (lists || []).length === 0 && (
          <Card padding="none" style={{ overflow: 'hidden' }}>
            <EmptyState
              icon={ListChecks}
              title={t('lists.empty_title', 'Create your first list')}
              description={t('lists.empty_desc', 'Lists let you target specific contact segments with campaigns. Group customers by tag, location, lifecycle stage, or any other dimension.')}
              action={<Button icon={Plus} onClick={() => setShowCreate(true)}>{t('lists.new_list', 'New List')}</Button>}
            />
          </Card>
        )}

        {(lists || []).length > 0 && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 16,
          }}>
            {lists.map((l) => (
              <ListCard key={l.id} list={l} onChange={refetch} t={t} />
            ))}
          </div>
        )}
      </div>

      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); refetch(); }}
          t={t}
        />
      )}
    </div>
  );
}

function ListCard({ list, onChange, t }) {
  const contactText = list.contact_count === 1
    ? (t ? t('lists.count_contacts', { count: 1, defaultValue: '1 contact' }) : '1 contact')
    : (t ? t('lists.count_contacts_plural', { count: list.contact_count, defaultValue: `${list.contact_count} contacts` }) : `${list.contact_count} contacts`);

  return (
    <Card interactive padding="md">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 12 }}>
        <div style={{
          width: 36, height: 36,
          borderRadius: 'var(--radius-sm)',
          background: 'var(--brand-primary-glow)',
          color: 'var(--brand-primary-hover)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <ListChecks size={16} strokeWidth={2.4} />
        </div>
        <Badge variant="default">{contactText}</Badge>
      </div>
      <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
        {list.name}
      </div>
      {list.description && (
        <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 12 }}>
          {list.description}
        </div>
      )}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginTop: 12, paddingTop: 12,
        borderTop: '1px solid var(--border-subtle)',
        fontSize: 11, color: 'var(--text-tertiary)',
      }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <Calendar size={11} />
          {new Date(list.created_at).toLocaleDateString()}
        </span>
        <Button
          variant="ghost"
          size="sm"
          icon={Trash2}
          iconOnly
          aria-label={t ? t('campaigns.delete', 'Delete') : 'Delete list'}
          onClick={async (e) => {
            e.preventDefault(); e.stopPropagation();
            const msg = t ? t('lists.delete_confirm', { name: list.name, defaultValue: `Delete list "${list.name}"?` }) : `Delete "${list.name}"?`;
            if (window.confirm(msg)) {
              await whatsappAPI.lists.delete(list.id);
              onChange();
            }
          }}
        />
      </div>
    </Card>
  );
}

function CreateModal({ onClose, onCreated, t }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);

  async function save() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await whatsappAPI.lists.create({ name, description });
      onCreated();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(10,14,20,0.5)',
        backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 200,
      }}
    >
      <Card
        onClick={(e) => e.stopPropagation()}
        padding="md"
        style={{ width: 'min(440px, 92vw)' }}
      >
        <Card.Header
          title={t ? t('lists.modal.title', 'New Contact List') : 'New list'}
          subtitle={t ? t('lists.subtitle', 'Group contacts for targeted outreach') : 'Group contacts for targeted outreach'}
        />
        <Card.Body>
          <label style={field}>
            <span style={fieldLabel}>{t ? t('lists.modal.name_label', 'Name') : 'Name'}</span>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t ? t('lists.modal.name_placeholder', 'e.g. VIP Customers') : 'VIP customers'}
              style={input}
            />
          </label>
          <label style={field}>
            <span style={fieldLabel}>{t ? t('lists.modal.description_label', 'Description') : 'Description (optional)'}</span>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t ? t('lists.modal.description_placeholder', 'What segment does this list represent?') : 'What kind of contacts belong here?'}
              style={{ ...input, resize: 'vertical' }}
            />
          </label>
        </Card.Body>
        <Card.Footer>
          <Button variant="secondary" onClick={onClose}>{t ? t('lists.modal.cancel_btn', 'Cancel') : 'Cancel'}</Button>
          <Button onClick={save} loading={saving} disabled={!name.trim()}>{t ? t('lists.modal.create_btn', 'Create List') : 'Create'}</Button>
        </Card.Footer>
      </Card>
    </div>
  );
}

const field = { display: 'block', marginBottom: 12 };
const fieldLabel = {
  display: 'block', fontSize: 11, fontWeight: 600,
  color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: 0.4,
  marginBottom: 6,
};
const input = {
  width: '100%', padding: '10px 12px',
  background: 'var(--surface-card)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-md)',
  fontSize: 14, color: 'var(--text-primary)',
  outline: 'none', boxSizing: 'border-box',
};
