/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { clientsAPI } from '../services/api';
import { ArrowLeft } from 'lucide-react';
import PageHeader from '../components/layout/PageHeader';

export default function EditClientPage({ clientId, onSelectClient }) {
  const { t }          = useTranslation(['management', 'common']);
  const navigate       = useNavigate();
  const [form, setForm]= useState({ company: '', name: '', email: '', phone: '', website: '', default_language: '', currency: 'USD' });
  const [errors, setErrors]   = useState({});
  const [saving, setSaving]   = useState(false);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg]         = useState('');

  useEffect(() => {
    clientsAPI.get(clientId).then(res => {
      const c = res.data;
      setForm({
        company:          c.company || '',
        name:             c.name    || '',
        email:            c.email   || '',
        phone:            c.phone   || '',
        website:          c.website || '',
        default_language: c.default_language || '',
        currency:         c.currency || 'USD',
      });
      setLoading(false);
    }).catch(() => {
      setMsg(`❌ ${t('edit_client.failed_load', 'Failed to load client.')}`);
      setLoading(false);
    });
  }, [clientId, t]);

  const handleFieldChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  };

  const validateForm = () => {
    const nextErrors = {};
    if (!form.company.trim()) nextErrors.company = t('edit_client.company_required', 'Company name is required.');
    if (!form.name.trim()) nextErrors.name = t('edit_client.contact_required', 'Contact name is required.');
    if (!form.email.trim()) nextErrors.email = t('edit_client.email_required', 'Email is required.');
    else if (!/\S+@\S+\.\S+/.test(form.email)) nextErrors.email = t('edit_client.email_invalid', 'Enter a valid email address.');
    if (form.website.trim()) {
      try {
        new URL(form.website);
      } catch {
        nextErrors.website = t('edit_client.website_invalid', 'Use a full website URL like https://example.com');
      }
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) {
      setMsg(`❌ ${t('edit_client.fix_errors', 'Please fix the highlighted fields.')}`);
      return;
    }
    setSaving(true); setMsg('');
    try {
      const payload = {
        company:          form.company,
        name:             form.name,
        email:            form.email,
        phone:            form.phone,
        website:          form.website,
        default_language: form.default_language || null,
        currency:         form.currency || 'USD',
      };
      const res = await clientsAPI.update(clientId, payload);
      onSelectClient?.(res.data);
      setMsg(`✅ ${t('edit_client.success', 'Client updated successfully.')}`);
    } catch (err) {
      setMsg('❌ ' + (err.response?.data?.error || JSON.stringify(err.response?.data) || t('edit_client.failed_update', 'Update failed')));
    } finally { setSaving(false); }
  };

  if (loading) return <div style={styles.loading}>{t('common.status.loading', 'Loading…')}</div>;

  return (
    <div style={styles.page}>
      <PageHeader
        title={t('edit_client.title', 'Edit Client')}
        subtitle={t('edit_client.subtitle', 'Update client organization details and settings')}
        actions={(
          <button onClick={() => navigate(-1)} style={styles.backBtn}>
            <span style={styles.backBtnInner}><ArrowLeft size={16} /> {t('edit_client.back', 'Back')}</span>
          </button>
        )}
      />

      <div style={styles.card}>
        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.row}>
            <label style={styles.label}>{t('edit_client.company_name', 'Company Name')} <span style={styles.requiredAsterisk}>*</span></label>
            <input
              value={form.company}
              onChange={e => handleFieldChange('company', e.target.value)}
              style={{ ...styles.input, ...(errors.company ? styles.inputError : {}) }}
              placeholder={t('edit_client.company_name_placeholder', 'Acme Corp')}
            />
            {errors.company && <div style={styles.errorText}>{errors.company}</div>}
          </div>
          <div style={styles.row}>
            <label style={styles.label}>{t('edit_client.contact_name', 'Contact Name')} <span style={styles.requiredAsterisk}>*</span></label>
            <input
              value={form.name}
              onChange={e => handleFieldChange('name', e.target.value)}
              style={{ ...styles.input, ...(errors.name ? styles.inputError : {}) }}
              placeholder={t('edit_client.contact_name_placeholder', 'John Smith')}
            />
            {errors.name && <div style={styles.errorText}>{errors.name}</div>}
          </div>
          <div style={styles.row}>
            <label style={styles.label}>{t('edit_client.email', 'Email')} <span style={styles.requiredAsterisk}>*</span></label>
            <input
              type="email"
              value={form.email}
              onChange={e => handleFieldChange('email', e.target.value)}
              style={{ ...styles.input, ...(errors.email ? styles.inputError : {}) }}
              placeholder={t('edit_client.email_placeholder', 'john@acme.com')}
            />
            {errors.email && <div style={styles.errorText}>{errors.email}</div>}
          </div>
          <div style={styles.row}>
            <label style={styles.label}>{t('edit_client.phone', 'Phone')}</label>
            <input
              value={form.phone}
              onChange={e => handleFieldChange('phone', e.target.value)}
              style={styles.input}
              placeholder={t('edit_client.phone_placeholder', '+1 555 000 0000')}
            />
          </div>
          <div style={styles.row}>
            <label style={styles.label}>{t('edit_client.website', 'Website')}</label>
            <input
              value={form.website}
              onChange={e => handleFieldChange('website', e.target.value)}
              style={{ ...styles.input, ...(errors.website ? styles.inputError : {}) }}
              placeholder={t('edit_client.website_placeholder', 'https://acme.com')}
            />
            {errors.website && <div style={styles.errorText}>{errors.website}</div>}
          </div>
          <div style={styles.row}>
            <label style={styles.label}>{t('edit_client.default_language', 'Default Language')}</label>
            <select
              value={form.default_language}
              onChange={e => handleFieldChange('default_language', e.target.value)}
              style={styles.input}
            >
              <option value="">{t('edit_client.lang_system', 'System / Browser default')}</option>
              <option value="en">{t('edit_client.lang_en', 'English')}</option>
              <option value="es">{t('edit_client.lang_es', 'Español')}</option>
            </select>
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>
              {t('edit_client.default_language_hint', 'Workspace language preference when users have not set an individual choice.')}
            </div>
          </div>
          <div style={styles.row}>
            <label style={styles.label}>{t('edit_client.currency', 'Workspace currency')}</label>
            <select
              value={form.currency || 'USD'}
              onChange={e => handleFieldChange('currency', e.target.value)}
              style={styles.input}
              data-testid="edit-client-currency-select"
            >
              <option value="USD">USD — US Dollar ($)</option>
              <option value="COP">COP — Peso colombiano ($)</option>
              <option value="EUR">EUR — Euro (€)</option>
              <option value="GBP">GBP — British Pound (£)</option>
              <option value="MXN">MXN — Peso mexicano ($)</option>
              <option value="CAD">CAD — Canadian Dollar ($)</option>
              <option value="INR">INR — Indian Rupee (₹)</option>
              <option value="BRL">BRL — Real brasileño (R$)</option>
              <option value="ARS">ARS — Peso argentino ($)</option>
              <option value="CLP">CLP — Peso chileno ($)</option>
              <option value="PEN">PEN — Sol peruano (S/)</option>
            </select>
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>
              {t('edit_client.currency_hint', 'Canonical business currency for metrics, budgets, and reporting.')}
            </div>
          </div>

          {msg && <div style={msg.startsWith('✅') ? styles.success : styles.error}>{msg}</div>}

          <div style={styles.actions}>
            <button type="button" onClick={() => navigate(-1)} style={styles.cancelBtn}>
              {t('edit_client.btn_cancel', 'Cancel')}
            </button>
            <button type="submit" disabled={saving} style={styles.saveBtn}>
              {saving ? t('edit_client.saving', 'Saving…') : t('edit_client.btn_save', 'Save Changes')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const styles = {
  page:     { padding: '28px 32px', maxWidth: 700, margin: '0 auto' },
  loading:  { padding: 60, textAlign: 'center', color: 'var(--text-tertiary)' },
  backBtn: {
    padding: '8px 16px', borderRadius: 8, border: '1.5px solid var(--border-default)',
    background: 'var(--surface-card)', color: 'var(--text-secondary)', cursor: 'pointer', fontWeight: 600, fontSize: 13,
  },
  backBtnInner: { display: 'flex', alignItems: 'center', gap: 6 },
  card: {
    background: 'var(--surface-card)', borderRadius: 14, padding: 32,
    boxShadow: '0 1px 6px rgba(0,0,0,.07)',
  },
  form:    { display: 'flex', flexDirection: 'column', gap: 20 },
  row:     { display: 'flex', flexDirection: 'column', gap: 6 },
  label:   { fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' },
  requiredAsterisk: { color: '#ef4444', marginLeft: 2, fontWeight: 800 },
  input: {
    padding: '10px 14px', borderRadius: 8, border: '1.5px solid var(--border-default)',
    fontSize: 14, outline: 'none', color: 'var(--text-primary)', background: 'var(--surface-card)',
  },
  inputError: { borderColor: '#ef4444', background: '#fef2f2' },
  errorText: { marginTop: 6, fontSize: 12, color: '#dc2626' },
  success: { padding: '10px 14px', borderRadius: 8, background: '#dcfce7', color: '#16a34a', fontSize: 13 },
  error:   { padding: '10px 14px', borderRadius: 8, background: '#fee2e2', color: '#dc2626', fontSize: 13 },
  actions: { display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 4 },
  cancelBtn: {
    padding: '10px 20px', borderRadius: 8, border: '1.5px solid var(--border-default)',
    background: 'var(--surface-card)', color: 'var(--text-secondary)', cursor: 'pointer', fontWeight: 600, fontSize: 13,
  },
  saveBtn: {
    padding: '10px 24px', borderRadius: 8, border: 'none',
    background: '#00d7ff', color: 'var(--text-primary)', cursor: 'pointer', fontWeight: 700, fontSize: 13,
  },
};
