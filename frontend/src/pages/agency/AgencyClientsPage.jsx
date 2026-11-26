/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  BOP SOCIAL — Agency Client Management & Creation (BS-8F / BS-8G)
 * ========================================================================== */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Users, Building2, Plus, Search, CheckCircle,
  ExternalLink, ArrowRight, ShieldCheck, X, AlertCircle, Loader2,
  UserPlus, Clock
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { useClients } from '../../hooks/useData';
import { useAppStore, useCurrentClient } from '../../stores/appStore';
import { agencyClientAPI, relationAPI } from '../../services/api';
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
  const { user } = useAuth();
  const { clients, loading, refetch } = useClients();
  const currentClient = useCurrentClient();
  const setCurrentClient = useAppStore((s) => s.setCurrentClient);

  const userRole = user?.agency_role || user?.agencyMembership?.role;
  const canInvite = user?.role === 'superadmin' || (
    user?.account_type === 'agency_member' &&
    (userRole ? ['owner', 'admin', 'manager'].includes(userRole) : true)
  );

  const [search, setSearch] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [formData, setFormData] = useState(INITIAL_FORM);
  const [formErrors, setFormErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState(null);

  // Invitation state (BS-8J.2)
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [selectedClientForInvite, setSelectedClientForInvite] = useState(null);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('approver');
  const [inviteMessage, setInviteMessage] = useState('');
  const [inviteErrors, setInviteErrors] = useState({});
  const [inviteSubmitting, setInviteSubmitting] = useState(false);
  const [pendingInvitesMap, setPendingInvitesMap] = useState({});

  // Publishing authorization state (BS-10F.2)
  const [relationsByClientId, setRelationsByClientId] = useState({});
  const [permModalClient, setPermModalClient] = useState(null);
  const [permPublishEnabled, setPermPublishEnabled] = useState(false);
  const [permSaving, setPermSaving] = useState(false);

  useEffect(() => {
    let active = true;
    if (typeof relationAPI?.list !== 'function') return;
    relationAPI.list()
      .then((res) => {
        if (!active) return;
        const map = {};
        for (const r of (res?.data?.relations || [])) {
          if (r?.client?.id) map[r.client.id] = r;
        }
        setRelationsByClientId(map);
      })
      .catch(() => {});
    return () => { active = false; };
  }, [clients]);

  const handleOpenPermModal = (client) => {
    const rel = relationsByClientId[client.id];
    if (!rel) return;
    setPermModalClient(client);
    setPermPublishEnabled(Boolean(rel.permissions?.publish_posts));
  };

  const handleSavePublishPerm = async () => {
    if (!permModalClient) return;
    const rel = relationsByClientId[permModalClient.id];
    if (!rel) return;
    setPermSaving(true);
    try {
      const res = await relationAPI.updatePerms(rel.id, {
        permissions: { publish_posts: permPublishEnabled },
      });
      setRelationsByClientId((prev) => ({
        ...prev,
        [permModalClient.id]: {
          ...rel,
          permissions: res?.data?.permissions || { ...rel.permissions, publish_posts: permPublishEnabled },
        },
      }));
      setFeedback({
        type: 'success',
        message: permPublishEnabled
          ? `Publicación externa habilitada para "${permModalClient.company || permModalClient.name}".`
          : `Publicación externa deshabilitada para "${permModalClient.company || permModalClient.name}".`,
      });
      setPermModalClient(null);
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err?.response?.data?.error || 'No se pudieron actualizar los permisos de publicación.',
      });
    } finally {
      setPermSaving(false);
    }
  };

  const handleOpenInviteModal = (client) => {
    setSelectedClientForInvite(client);
    setInviteEmail('');
    setInviteRole('approver');
    setInviteMessage('');
    setInviteErrors({});
    setShowInviteModal(true);
  };

  const handleCloseInviteModal = () => {
    if (!inviteSubmitting) {
      setShowInviteModal(false);
      setSelectedClientForInvite(null);
      setInviteErrors({});
    }
  };

  const handleInviteSubmit = async (e) => {
    e.preventDefault();
    if (!selectedClientForInvite) return;

    const errors = {};
    const trimmedEmail = inviteEmail.trim();
    if (!trimmedEmail) {
      errors.email = 'El email es obligatorio.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      errors.email = 'Ingresa un formato de email válido.';
    }
    if (!['approver', 'client_admin', 'editor', 'viewer'].includes(inviteRole)) {
      errors.role = 'Rol no válido.';
    }

    if (Object.keys(errors).length > 0) {
      setInviteErrors(errors);
      return;
    }

    setInviteSubmitting(true);
    setInviteErrors({});

    try {
      const payload = {
        email: trimmedEmail.toLowerCase(),
        role: inviteRole,
        message: inviteMessage.trim(),
      };
      const res = await agencyClientAPI.invite(selectedClientForInvite.id, payload);

      setPendingInvitesMap((prev) => ({
        ...prev,
        [selectedClientForInvite.id]: [
          ...(prev[selectedClientForInvite.id] || []),
          {
            id: res.data.id,
            email: res.data.client_email || trimmedEmail.toLowerCase(),
            client_email: res.data.client_email || trimmedEmail.toLowerCase(),
            role: res.data.role || inviteRole,
            status: res.data.status || 'pending',
          },
        ],
      }));

      setShowInviteModal(false);
      setSelectedClientForInvite(null);
      setFeedback({
        type: 'success',
        message: `Invitación enviada con éxito a ${trimmedEmail} (${inviteRole}).`,
      });
    } catch (err) {
      const respData = err.response?.data;
      if (respData?.details && typeof respData.details === 'object') {
        const apiErrors = {};
        for (const [k, v] of Object.entries(respData.details)) {
          apiErrors[k] = Array.isArray(v) ? v.join(' ') : String(v);
        }
        setInviteErrors(apiErrors);
      } else {
        setInviteErrors({
          general: respData?.error || 'Error al enviar la invitación. Intenta nuevamente.',
        });
      }
    } finally {
      setInviteSubmitting(false);
    }
  };

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

                {/* Pending Invitations list (BS-8J.2) */}
                {pendingInvitesMap[c.id] && pendingInvitesMap[c.id].length > 0 && (
                  <div
                    data-testid={`pending-invites-${c.id}`}
                    style={{
                      padding: '8px 12px',
                      background: 'rgba(234, 179, 8, 0.08)',
                      borderRadius: 'var(--radius-sm, 6px)',
                      border: '1px solid rgba(234, 179, 8, 0.25)',
                      fontSize: 12,
                      color: 'var(--text-secondary, #64748b)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 4,
                    }}
                  >
                    <div style={{ fontWeight: 600, color: '#ca8a04', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Clock size={12} /> Invitaciones pendientes:
                    </div>
                    {pendingInvitesMap[c.id].map((inv, idx) => (
                      <div key={inv.id || idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span>{inv.client_email || inv.email}</span>
                        <span style={{ fontSize: 11, background: '#fef08a', color: '#854d0e', padding: '1px 6px', borderRadius: 999, fontWeight: 600 }}>
                          {inv.role}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingTop: 12,
                  borderTop: '1px solid var(--border-subtle)',
                  fontSize: 12,
                  gap: 8,
                  flexWrap: 'wrap',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ color: 'var(--text-tertiary)' }}>
                      {isSelected ? '● Espacio actual' : 'Disponible'}
                    </span>
                    {canInvite && (
                      <button
                        type="button"
                        data-testid={`invite-client-btn-${c.id}`}
                        onClick={() => handleOpenInviteModal(c)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 5,
                          background: 'rgba(0, 215, 255, 0.08)',
                          color: 'var(--brand-primary, #00b8d9)',
                          border: '1px solid rgba(0, 215, 255, 0.25)',
                          fontWeight: 600,
                          cursor: 'pointer',
                          padding: '3px 8px',
                          borderRadius: 'var(--radius-sm, 6px)',
                          fontSize: 11,
                        }}
                      >
                        <UserPlus size={12} />
                        <span>Invitar usuario</span>
                      </button>
                    )}
                    {relationsByClientId[c.id]?.can_manage_permissions && (
                      <button
                        type="button"
                        data-testid={`publish-perms-btn-${c.id}`}
                        onClick={() => handleOpenPermModal(c)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 5,
                          background: relationsByClientId[c.id]?.permissions?.publish_posts
                            ? 'rgba(16, 185, 129, 0.12)'
                            : 'rgba(245, 158, 11, 0.12)',
                          color: relationsByClientId[c.id]?.permissions?.publish_posts ? '#059669' : '#B45309',
                          border: relationsByClientId[c.id]?.permissions?.publish_posts
                            ? '1px solid rgba(16, 185, 129, 0.3)'
                            : '1px solid rgba(245, 158, 11, 0.3)',
                          fontWeight: 600,
                          cursor: 'pointer',
                          padding: '3px 8px',
                          borderRadius: 'var(--radius-sm, 6px)',
                          fontSize: 11,
                        }}
                      >
                        <ShieldCheck size={12} />
                        <span>
                          {relationsByClientId[c.id]?.permissions?.publish_posts
                            ? 'Publicación: Activa'
                            : 'Publicación: Pausada'}
                        </span>
                      </button>
                    )}
                  </div>
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
      {/* Invite Client User Modal (BS-8J.2) */}
      {showInviteModal && selectedClientForInvite && (
        <div
          role="dialog"
          aria-modal="true"
          data-testid="invite-user-modal"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1000,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
          }}
        >
          <div
            style={{
              background: 'var(--surface-card, #ffffff)',
              borderRadius: 'var(--radius-xl, 16px)',
              border: '1px solid var(--border-subtle, #e2e8f0)',
              width: '100%',
              maxWidth: 480,
              boxShadow: 'var(--shadow-xl, 0 20px 25px -5px rgba(0, 0, 0, 0.1))',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {/* Modal Header */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '18px 24px',
              borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
            }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                  Invitar usuario
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-secondary, #64748b)', marginTop: 2 }}>
                  Espacio: {selectedClientForInvite.company || selectedClientForInvite.name}
                </div>
              </div>
              <button
                type="button"
                onClick={handleCloseInviteModal}
                disabled={inviteSubmitting}
                data-testid="close-invite-modal-btn"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-tertiary, #94a3b8)',
                  cursor: 'pointer',
                  padding: 4,
                  borderRadius: 6,
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body / Form */}
            <form onSubmit={handleInviteSubmit} style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
              {inviteErrors.general && (
                <div style={{
                  padding: '10px 14px',
                  background: '#fef2f2',
                  border: '1px solid #fecaca',
                  borderRadius: 8,
                  color: '#dc2626',
                  fontSize: 13,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}>
                  <AlertCircle size={16} />
                  <span>{inviteErrors.general}</span>
                </div>
              )}

              <div>
                <label
                  htmlFor="invite-email"
                  style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary, #334155)', marginBottom: 6 }}
                >
                  Email del usuario *
                </label>
                <input
                  id="invite-email"
                  type="email"
                  data-testid="invite-email-input"
                  value={inviteEmail}
                  onChange={(e) => {
                    setInviteEmail(e.target.value);
                    if (inviteErrors.email) setInviteErrors((prev) => ({ ...prev, email: null }));
                  }}
                  placeholder="stakeholder@alphabrands.com"
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: 8,
                    border: inviteErrors.email ? '1px solid #ef4444' : '1px solid var(--border-default, #cbd5e1)',
                    background: 'var(--surface-card, #ffffff)',
                    fontSize: 13,
                    color: 'var(--text-primary, #0f172a)',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                  required
                />
                {inviteErrors.email && (
                  <div style={{ color: '#ef4444', fontSize: 12, marginTop: 4 }}>
                    {inviteErrors.email}
                  </div>
                )}
              </div>

              <div>
                <label
                  htmlFor="invite-role"
                  style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary, #334155)', marginBottom: 6 }}
                >
                  Rol en el workspace *
                </label>
                <select
                  id="invite-role"
                  data-testid="invite-role-select"
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: 8,
                    border: '1px solid var(--border-default, #cbd5e1)',
                    background: 'var(--surface-card, #ffffff)',
                    fontSize: 13,
                    color: 'var(--text-primary, #0f172a)',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                >
                  <option value="approver">Aprobador (approver)</option>
                  <option value="client_admin">Administrador de Cliente (client_admin)</option>
                  <option value="editor">Editor (editor)</option>
                  <option value="viewer">Visualizador (viewer)</option>
                </select>
                {inviteErrors.role && (
                  <div style={{ color: '#ef4444', fontSize: 12, marginTop: 4 }}>
                    {inviteErrors.role}
                  </div>
                )}
              </div>

              <div>
                <label
                  htmlFor="invite-message"
                  style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary, #334155)', marginBottom: 6 }}
                >
                  Mensaje opcional
                </label>
                <textarea
                  id="invite-message"
                  data-testid="invite-message-input"
                  value={inviteMessage}
                  onChange={(e) => setInviteMessage(e.target.value)}
                  placeholder="Hola, te invitamos a revisar y colaborar en el contenido de este workspace..."
                  rows={3}
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: 8,
                    border: '1px solid var(--border-default, #cbd5e1)',
                    background: 'var(--surface-card, #ffffff)',
                    fontSize: 13,
                    color: 'var(--text-primary, #0f172a)',
                    outline: 'none',
                    resize: 'vertical',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              {/* Modal Footer */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: 10,
                marginTop: 8,
                paddingTop: 16,
                borderTop: '1px solid var(--border-subtle, #e2e8f0)',
              }}>
                <button
                  type="button"
                  onClick={handleCloseInviteModal}
                  disabled={inviteSubmitting}
                  style={{
                    padding: '8px 16px',
                    borderRadius: 8,
                    border: '1px solid var(--border-default, #cbd5e1)',
                    background: 'transparent',
                    color: 'var(--text-secondary, #64748b)',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  data-testid="submit-invite-btn"
                  disabled={inviteSubmitting}
                  style={{
                    padding: '8px 18px',
                    borderRadius: 8,
                    border: 'none',
                    background: 'var(--brand-primary, #00b8d9)',
                    color: '#ffffff',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  {inviteSubmitting ? <Loader2 size={15} className="animate-spin" /> : 'Enviar invitación'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Publishing Permissions Modal (BS-10F.2) */}
      {permModalClient && (
        <div
          role="dialog"
          aria-modal="true"
          data-testid="publish-perms-modal"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
          }}
        >
          <div style={{
            width: '100%',
            maxWidth: 440,
            background: 'var(--surface-card, #ffffff)',
            borderRadius: 16,
            padding: 24,
            boxShadow: '0 20px 40px rgba(0,0,0,0.2)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
                Autorización de publicación
              </h3>
              <button
                type="button"
                onClick={() => !permSaving && setPermModalClient(null)}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-tertiary)' }}
              >
                <X size={18} />
              </button>
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 0, marginBottom: 16 }}>
              Workspace: <strong>{permModalClient.company || permModalClient.name}</strong>
            </p>
            <label style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
              padding: 12,
              borderRadius: 10,
              border: '1px solid var(--border-default, #cbd5e1)',
              cursor: 'pointer',
              marginBottom: 18,
            }}>
              <input
                type="checkbox"
                data-testid="toggle-publish-posts-checkbox"
                checked={permPublishEnabled}
                onChange={(e) => setPermPublishEnabled(e.target.checked)}
                style={{ marginTop: 2 }}
              />
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                  Habilitar publicación externa (`publish_posts`)
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                  Permite que el programador y los workers ejecuten publicaciones aprobadas en Meta y redes conectadas.
                </div>
              </div>
            </label>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                onClick={() => setPermModalClient(null)}
                disabled={permSaving}
                style={{
                  padding: '8px 16px',
                  borderRadius: 8,
                  border: '1px solid var(--border-default, #cbd5e1)',
                  background: 'transparent',
                  color: 'var(--text-secondary, #64748b)',
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                data-testid="save-publish-perms-btn"
                onClick={handleSavePublishPerm}
                disabled={permSaving}
                style={{
                  padding: '8px 18px',
                  borderRadius: 8,
                  border: 'none',
                  background: 'var(--brand-primary, #00b8d9)',
                  color: '#ffffff',
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {permSaving ? 'Guardando…' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
