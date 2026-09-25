/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, Search, FileText } from 'lucide-react';

import PageHeader from '../../components/layout/PageHeader';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import EmptyState from '../../components/ui/EmptyState';
import { auditAPI } from '../../services/api';
import { formatDate } from '../../utils/formatters';

const RESULT_VARIANT = {
  success: 'success',
  failed:  'danger',
  partial: 'warning',
};

export default function AuditLogPage() {
  const { t, i18n } = useTranslation(['management', 'common']);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ action: '', result: '', search: '' });

  function refetch() {
    setLoading(true);
    const params = {};
    if (filter.action) params.action = filter.action;
    if (filter.result) params.result = filter.result;
    if (filter.search) params.search = filter.search;
    auditAPI.list(params)
      .then((r) => setRows(r.data?.results || r.data || []))
      .finally(() => setLoading(false));
  }
  useEffect(() => { refetch(); /* eslint-disable-next-line */ }, [
    filter.action, filter.result, filter.search,
  ]);

  return (
    <div style={{ paddingBottom: 32 }}>
      <PageHeader
        title={t('audit_log.title', 'Audit log')}
        subtitle={t('audit_log.subtitle', 'Every write action Bop Social performed on your behalf')}
      />

      <div style={{ padding: '0 24px' }}>
        <Card padding="sm" style={{
          padding: 12, marginBottom: 12,
          display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center',
        }}>
          <div style={{ position: 'relative', flex: 1, minWidth: 220 }}>
            <Search size={14} color="var(--text-tertiary)"
                    style={{ position: 'absolute', top: 11, left: 10 }} />
            <input
              placeholder={t('audit_log.search_placeholder', 'Search action…')}
              value={filter.search}
              onChange={(e) => setFilter({ ...filter, search: e.target.value })}
              style={{ ...inputStyle, paddingLeft: 30 }}
            />
          </div>
          <select value={filter.result}
                   onChange={(e) => setFilter({ ...filter, result: e.target.value })}
                   style={inputStyle}>
            <option value="">{t('audit_log.filter_all', 'All results')}</option>
            <option value="success">{t('audit_log.filter_success', 'Success')}</option>
            <option value="partial">{t('audit_log.filter_partial', 'Partial')}</option>
            <option value="failed">{t('audit_log.filter_failed', 'Failed')}</option>
          </select>
        </Card>

        {loading && (
          <div style={{ padding: 32, textAlign: 'center' }}>
            <Loader2 size={18} className="ds-spin" color="var(--text-tertiary)" />
          </div>
        )}

        {!loading && rows.length === 0 && (
          <Card padding="none" style={{ overflow: 'hidden' }}>
            <EmptyState
              icon={FileText}
              title={t('audit_log.empty_title', 'No audit entries yet')}
              description={t('audit_log.empty_desc', "Once Bop Social publishes a post, sends a reply, or fires an automation, it'll show up here.")}
            />
          </Card>
        )}

        {!loading && rows.length > 0 && (
          <Card padding="none" style={{ overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr>
                  <th style={th}>{t('audit_log.col_when', 'When')}</th>
                  <th style={th}>{t('audit_log.col_action', 'Action')}</th>
                  <th style={th}>{t('audit_log.col_object', 'Object')}</th>
                  <th style={th}>{t('audit_log.col_platform', 'Platform')}</th>
                  <th style={th}>{t('audit_log.col_actor', 'Actor')}</th>
                  <th style={th}>{t('audit_log.col_result', 'Result')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td style={td}>{r.created_at ? formatDate(r.created_at, { dateStyle: 'short', timeStyle: 'short' }, i18n?.language) : '—'}</td>
                    <td style={td}>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontSize: 12,
                        color: 'var(--text-primary)',
                      }}>
                        {r.action}
                      </span>
                    </td>
                    <td style={td}>
                      {r.object_type
                        ? <span style={{ color: 'var(--text-secondary)' }}>
                            {r.object_type}#{r.object_id || '—'}
                          </span>
                        : <span style={{ color: 'var(--text-tertiary)' }}>—</span>}
                    </td>
                    <td style={td}>
                      {r.platform
                        ? <Badge variant="default">{r.platform}</Badge>
                        : <span style={{ color: 'var(--text-tertiary)' }}>—</span>}
                    </td>
                    <td style={td}>
                      <span style={{ color: 'var(--text-secondary)' }}>
                        {r.actor_email || t('audit_log.system_actor', 'system')}
                      </span>
                    </td>
                    <td style={td}>
                      <Badge variant={RESULT_VARIANT[r.result] || 'default'} dot>
                        {r.result ? t(`audit_log.filter_${r.result}`, r.result) : '—'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      <style>{`.ds-spin { animation: ds-spin 0.9s linear infinite; } @keyframes ds-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

const inputStyle = {
  height: 36, padding: '0 12px',
  background: 'var(--surface-card)',
  border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-md)',
  fontSize: 13, color: 'var(--text-primary)',
  outline: 'none', boxSizing: 'border-box', minHeight: 'unset',
};
const th = {
  textAlign: 'left', padding: '10px 14px', fontSize: 11,
  fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.4,
  color: 'var(--text-tertiary)',
  borderBottom: '1px solid var(--border-subtle)',
  background: 'var(--surface-sunken)',
};
const td = { padding: '10px 14px', borderBottom: '1px solid var(--border-subtle)',
              color: 'var(--text-primary)' };
