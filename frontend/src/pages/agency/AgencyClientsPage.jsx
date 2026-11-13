/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  BOP SOCIAL — Agency Client Management & Creation (BS-8F / BS-8G)
 * ========================================================================== */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Users, Building2, Plus, Search, CheckCircle,
  ExternalLink, ArrowRight, ShieldCheck, X, AlertCircle, Loader2
} from 'lucide-react';
import { useClients } from '../../hooks/useData';
import { useAppStore, useCurrentClient } from '../../stores/appStore';
import { agencyClientAPI } from '../../services/api';
import PageHeader from '../../components/layout/PageHeader';

const INITIAL_FORM = {
  company: '',
  name: '',
  email: '',
  website: '',
  timezone: 'UTC',
  default_language: 'es',
  currency: 'USD',
  business_category: '',
  location_country: '',
  requires_approval: false,
};

export default function AgencyClientsPage() {
  const { t } = useTranslation(['management', 'common', 'agency_portal']);
  const navigate = useNavigate();
  const { clients, loading, refetch } = useClients();
  const currentClient = useCurrentClient();
  const setCurrentClient = useAppStore((s) => s.setCurrentClient);

  const [search, setSearch] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [formData, setFormData] = useState(INITIAL_FORM);
  const [formErrors, setFormErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const filteredClients = (clients || []).filter((c) =>
    !search ||
    (c.company || '').toLowerCase().includes(search.toLowerCase()) ||
    (c.name || '').toLowerCase().includes(search.toLowerCase())
  );

  const handleSelectAndGo = (client) => {
    setCurrentClient(client);
    navigate('/dashboard/analytics');
  };

  const handleOpenModal = () => {
    setFormData(INITIAL_FORM);
    setFormErrors({});
    setFeedback(null);
    setShowAddModal(true);
  };

  const handleCloseModal = () => {
    if (!submitting) {
      setShowAddModal(false);
      setFormErrors({});
    }
  };

  const handleFieldChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (formErrors[field]) {
      setFormErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
  };

  const handleFormSubmit = async (e) => {
    e.preventDefault();
    const errors = {};

    if (!formData.company.trim()) {
      errors.company = 'El nombre de la empresa es obligatorio.';
    }
    if (!formData.name.trim()) {
      errors.name = 'El nombre del contacto/workspace es obligatorio.';
    }
    if (!formData.email.trim()) {
      errors.email = 'El email es obligatorio.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email.trim())) {
      errors.email = 'Ingresa un formato de email válido.';
    }

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    setSubmitting(true);
    setFormErrors({});

    try {
      const payload = {
        company: formData.company.trim(),
        name: formData.name.trim(),
        email: formData.email.trim(),
        website: formData.website.trim(),
        timezone: formData.timezone.trim() || 'UTC',
        default_language: formData.default_language || 'es',
        currency: formData.currency || 'USD',
        business_category: formData.business_category.trim(),
        location_country: formData.location_country.trim(),
        requires_approval: Boolean(formData.requires_approval),
      };

      const res = await agencyClientAPI.create(payload);
      setShowAddModal(false);
      setFormData(INITIAL_FORM);
      setFeedback({
        type: 'success',
        message: `Cliente "${res.data.client.company || res.data.client.name}" creado con éxito.`,
      });

      if (refetch) await refetch();
      window.dispatchEvent(new CustomEvent('clients:refetch'));
    } catch (err) {
      const respData = err.response?.data;
      if (respData?.details && typeof respData.details === 'object') {
        const apiErrors = {};
        for (const [k, v] of Object.entries(respData.details)) {
          apiErrors[k] = Array.isArray(v) ? v.join(' ') : String(v);
        }
        setFormErrors(apiErrors);
      } else {
        setFormErrors({
          general: respData?.error || 'Error al crear el cliente. Intenta nuevamente.',
        });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: '28px 36px', maxWidth: 1200, margin: '0 auto' }}>
      <PageHeader
        title={t('agency_clients.title', 'Clientes')}
        subtitle={t('agency_clients.subtitle', 'Espacios de trabajo y marcas gestionadas por tu agencia')}
        badge="Agency"
        actions={
          <button
            type="button"
            onClick={handleOpenModal}
            data-testid="add-client-button"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '9px 16px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: 'var(--brand-primary)',
              color: '#fff',
              fontWeight: 600,
              fontSize: 13,
              cursor: 'pointer',
              boxShadow: 'var(--shadow-sm)',
              transition: 'var(--transition-fast)',
            }}
          >
            <Plus size={16} strokeWidth={2.4} />
            <span>{t('agency_clients.add_client', 'Añadir cliente')}</span>
          </button>
        }
      />

      {feedback && (
        <div
          data-testid="agency-client-feedback"
          style={{
            margin: '16px 0',
            padding: '12px 16px',
            borderRadius: 'var(--radius-md)',
            background: feedback.type === 'success' ? '#f0fdf4' : '#fef2f2',
            border: `1px solid ${feedback.type === 'success' ? '#bbf7d0' : '#fecaca'}`,
            color: feedback.type === 'success' ? '#166534' : '#991b1b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: 13,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <CheckCircle size={16} />
            <span>{feedback.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setFeedback(null)}
            style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'inherit' }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Toolbar / Search */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        margin: '24px 0 16px',
        gap: 16,
      }}>
        <div style={{ position: 'relative', width: 320, maxWidth: '100%' }}>
          <Search
            size={14}
            color="var(--text-tertiary)"
            style={{ position: 'absolute', top: 11, left: 12 }}
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('agency_clients.search_placeholder', 'Buscar clientes por nombre…')}
            style={{
              width: '100%',
              padding: '8px 12px 8px 34px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-default)',
              background: 'var(--surface-card)',
              fontSize: 13,
              color: 'var(--text-primary)',
              outline: 'none',
            }}
          />
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          {filteredClients.length} {filteredClients.length === 1 ? 'cliente activo' : 'clientes activos'}
        </div>
      </div>

      {/* Clients Grid / List */}
      {loading ? (
        <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-tertiary)' }}>
          Cargando clientes…
        </div>
      ) : filteredClients.length === 0 ? (
        <div style={{
          padding: 48,
          textAlign: 'center',
          background: 'var(--surface-card)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--border-subtle)',
        }}>
          <Users size={36} color="var(--text-tertiary)" style={{ marginBottom: 12 }} />
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
            No se encontraron clientes
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            {search ? 'Intenta con otro término de búsqueda' : 'No hay clientes conectados a esta agencia.'}
          </div>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
          gap: 16,
        }}>
          {filteredClients.map((c) => {
            const isSelected = currentClient?.id === c.id;
            return (
              <div
                key={c.id}
                data-testid={`client-card-${c.id}`}
                style={{
                  background: 'var(--surface-card)',
                  borderRadius: 'var(--radius-lg)',
                  border: isSelected ? '2px solid var(--brand-primary)' : '1px solid var(--border-subtle)',
                  padding: 20,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 14,
                  boxShadow: 'var(--shadow-sm)',
                  transition: 'var(--transition-fast)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{
                    width: 42,
                    height: 42,
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--brand-primary-glow)',
                    color: 'var(--brand-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 700,
                    fontSize: 16,
                  }}>
                    {c.company ? c.company.slice(0, 2).toUpperCase() : <Building2 size={20} />}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 15,
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {c.company || c.name}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>
                      Workspace #{c.id}
                    </div>
                  </div>
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    padding: '3px 8px',
                    borderRadius: 999,
                    fontSize: 11,
                    fontWeight: 600,
                    background: '#dcfce7',
                    color: '#16a34a',
                  }}>
                    <CheckCircle size={11} />
                    Activo
                  </span>
                </div>

                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingTop: 12,
                  borderTop: '1px solid var(--border-subtle)',
                  fontSize: 12,
                }}>
                  <span style={{ color: 'var(--text-tertiary)' }}>
                    {isSelected ? '● Espacio actual' : 'Disponible'}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleSelectAndGo(c)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      background: isSelected ? 'var(--brand-primary-glow)' : 'transparent',
                      color: 'var(--brand-primary)',
                      border: 'none',
                      fontWeight: 600,
                      cursor: 'pointer',
                      padding: '4px 8px',
                      borderRadius: 'var(--radius-sm)',
                    }}
                  >
                    <span>{isSelected ? 'Ver dashboard' : 'Gestionar workspace'}</span>
                    <ArrowRight size={13} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add Client Modal */}
      {showAddModal && (
        <div
          role="dialog"
          aria-modal="true"
          data-testid="add-client-modal"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
        >
          <div style={{
            background: 'var(--surface-elevated)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--border-default)',
            boxShadow: 'var(--shadow-xl)',
            width: '100%',
            maxWidth: 540,
            maxHeight: '90vh',
            overflowY: 'auto',
            padding: 24,
            position: 'relative',
          }}>
            <button
              type="button"
              onClick={handleCloseModal}
              disabled={submitting}
              aria-label="Cerrar"
              style={{
                position: 'absolute',
                top: 16,
                right: 16,
                border: 'none',
                background: 'transparent',
                color: 'var(--text-tertiary)',
                cursor: submitting ? 'not-allowed' : 'pointer',
              }}
            >
              <X size={18} />
            </button>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
              <div style={{
                width: 40,
                height: 40,
                borderRadius: 'var(--radius-md)',
                background: 'var(--brand-primary-glow)',
                color: 'var(--brand-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <Building2 size={20} />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
                  Añadir nuevo cliente
                </h3>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  Crear espacio de trabajo gestionado por tu agencia
                </span>
              </div>
            </div>

            {formErrors.general && (
              <div style={{
                marginBottom: 16,
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
                background: '#fef2f2',
                border: '1px solid #fecaca',
                color: '#991b1b',
                fontSize: 13,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}>
                <AlertCircle size={16} />
                <span>{formErrors.general}</span>
              </div>
            )}

            <form onSubmit={handleFormSubmit}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {/* Company Name */}
                <div>
                  <label
                    htmlFor="client-company-input"
                    style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}
                  >
                    Empresa / Marca *
                  </label>
                  <input
                    id="client-company-input"
                    name="company"
                    type="text"
                    required
                    placeholder="ej. Test Alpha Brands S.A."
                    value={formData.company}
                    onChange={(e) => handleFieldChange('company', e.target.value)}
                    disabled={submitting}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: 'var(--radius-md)',
                      border: formErrors.company ? '1px solid var(--danger, #ef4444)' : '1px solid var(--border-default)',
                      background: 'var(--surface-card)',
                      fontSize: 13,
                      color: 'var(--text-primary)',
                      outline: 'none',
                    }}
                  />
                  {formErrors.company && (
                    <span style={{ fontSize: 11, color: '#ef4444', marginTop: 3, display: 'block' }}>
                      {formErrors.company}
                    </span>
                  )}
                </div>

                {/* Workspace / Contact Name */}
                <div>
                  <label
                    htmlFor="client-name-input"
                    style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}
                  >
                    Nombre del Workspace / Contacto *
                  </label>
                  <input
                    id="client-name-input"
                    name="name"
                    type="text"
                    required
                    placeholder="ej. Test Alpha Brands"
                    value={formData.name}
                    onChange={(e) => handleFieldChange('name', e.target.value)}
                    disabled={submitting}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: 'var(--radius-md)',
                      border: formErrors.name ? '1px solid var(--danger, #ef4444)' : '1px solid var(--border-default)',
                      background: 'var(--surface-card)',
                      fontSize: 13,
                      color: 'var(--text-primary)',
                      outline: 'none',
                    }}
                  />
                  {formErrors.name && (
                    <span style={{ fontSize: 11, color: '#ef4444', marginTop: 3, display: 'block' }}>
                      {formErrors.name}
                    </span>
                  )}
                </div>

                {/* Email */}
                <div>
                  <label
                    htmlFor="client-email-input"
                    style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}
                  >
                    Email de contacto *
                  </label>
                  <input
                    id="client-email-input"
                    name="email"
                    type="email"
                    required
                    placeholder="ej. contacto@alphabrands.com"
                    value={formData.email}
                    onChange={(e) => handleFieldChange('email', e.target.value)}
                    disabled={submitting}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: 'var(--radius-md)',
                      border: formErrors.email ? '1px solid var(--danger, #ef4444)' : '1px solid var(--border-default)',
                      background: 'var(--surface-card)',
                      fontSize: 13,
                      color: 'var(--text-primary)',
                      outline: 'none',
                    }}
                  />
                  {formErrors.email && (
                    <span style={{ fontSize: 11, color: '#ef4444', marginTop: 3, display: 'block' }}>
                      {formErrors.email}
                    </span>
                  )}
                </div>

                {/* Grid for Language & Currency */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label
                      htmlFor="client-lang-select"
                      style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}
                    >
                      Idioma predeterminado
                    </label>
                    <select
                      id="client-lang-select"
                      name="default_language"
                      value={formData.default_language}
                      onChange={(e) => handleFieldChange('default_language', e.target.value)}
                      disabled={submitting}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-default)',
                        background: 'var(--surface-card)',
                        fontSize: 13,
                        color: 'var(--text-primary)',
                        outline: 'none',
                      }}
                    >
                      <option value="es">Español (es)</option>
                      <option value="en">Inglés (en)</option>
                    </select>
                  </div>

                  <div>
                    <label
                      htmlFor="client-currency-input"
                      style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}
                    >
                      Moneda
                    </label>
                    <input
                      id="client-currency-input"
                      name="currency"
                      type="text"
                      placeholder="USD"
                      value={formData.currency}
                      onChange={(e) => handleFieldChange('currency', e.target.value)}
                      disabled={submitting}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-default)',
                        background: 'var(--surface-card)',
                        fontSize: 13,
                        color: 'var(--text-primary)',
                        outline: 'none',
                      }}
                    />
                  </div>
                </div>

                {/* Grid for Website & Timezone */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label
                      htmlFor="client-website-input"
                      style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}
                    >
                      Sitio web
                    </label>
                    <input
                      id="client-website-input"
                      name="website"
                      type="text"
                      placeholder="https://ejemplo.com"
                      value={formData.website}
                      onChange={(e) => handleFieldChange('website', e.target.value)}
                      disabled={submitting}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-default)',
                        background: 'var(--surface-card)',
                        fontSize: 13,
                        color: 'var(--text-primary)',
                        outline: 'none',
                      }}
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="client-timezone-input"
                      style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}
                    >
                      Zona horaria
                    </label>
                    <input
                      id="client-timezone-input"
                      name="timezone"
                      type="text"
                      placeholder="UTC"
                      value={formData.timezone}
                      onChange={(e) => handleFieldChange('timezone', e.target.value)}
                      disabled={submitting}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-default)',
                        background: 'var(--surface-card)',
                        fontSize: 13,
                        color: 'var(--text-primary)',
                        outline: 'none',
                      }}
                    />
                  </div>
                </div>

                {/* Grid for Industry & Country */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label
                      htmlFor="client-industry-input"
                      style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}
                    >
                      Industria / Categoría
                    </label>
                    <input
                      id="client-industry-input"
                      name="business_category"
                      type="text"
                      placeholder="ej. Retail, Moda"
                      value={formData.business_category}
                      onChange={(e) => handleFieldChange('business_category', e.target.value)}
                      disabled={submitting}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-default)',
                        background: 'var(--surface-card)',
                        fontSize: 13,
                        color: 'var(--text-primary)',
                        outline: 'none',
                      }}
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="client-country-input"
                      style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}
                    >
                      País / Ubicación
                    </label>
                    <input
                      id="client-country-input"
                      name="location_country"
                      type="text"
                      placeholder="ej. ES, MX, US"
                      value={formData.location_country}
                      onChange={(e) => handleFieldChange('location_country', e.target.value)}
                      disabled={submitting}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-default)',
                        background: 'var(--surface-card)',
                        fontSize: 13,
                        color: 'var(--text-primary)',
                        outline: 'none',
                      }}
                    />
                  </div>
                </div>

                {/* Requires Approval Checkbox */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--surface-sunken)',
                  border: '1px solid var(--border-subtle)',
                  marginTop: 4,
                }}>
                  <input
                    id="client-approval-checkbox"
                    name="requires_approval"
                    type="checkbox"
                    checked={formData.requires_approval}
                    onChange={(e) => handleFieldChange('requires_approval', e.target.checked)}
                    disabled={submitting}
                    style={{ width: 16, height: 16, cursor: submitting ? 'not-allowed' : 'pointer' }}
                  />
                  <label
                    htmlFor="client-approval-checkbox"
                    style={{ fontSize: 12, color: 'var(--text-primary)', cursor: submitting ? 'not-allowed' : 'pointer', fontWeight: 500 }}
                  >
                    Requiere aprobación previa para publicar posts
                  </label>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                <button
                  type="button"
                  onClick={handleCloseModal}
                  disabled={submitting}
                  style={{
                    padding: '8px 16px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-default)',
                    background: 'transparent',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                    fontWeight: 500,
                    cursor: submitting ? 'not-allowed' : 'pointer',
                  }}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  data-testid="submit-create-client-btn"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '8px 18px',
                    borderRadius: 'var(--radius-md)',
                    border: 'none',
                    background: 'var(--brand-primary)',
                    color: '#fff',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: submitting ? 'not-allowed' : 'pointer',
                    boxShadow: 'var(--shadow-sm)',
                    opacity: submitting ? 0.8 : 1,
                  }}
                >
                  {submitting ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      <span>Creando…</span>
                    </>
                  ) : (
                    <span>Crear cliente</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
