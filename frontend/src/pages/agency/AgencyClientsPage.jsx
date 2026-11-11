/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  BOP SOCIAL — Agency Client Management (BS-8F)
 * ========================================================================== */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Users, Building2, Plus, Search, CheckCircle,
  ExternalLink, ArrowRight, ShieldCheck, X, AlertCircle
} from 'lucide-react';
import { useClients } from '../../hooks/useData';
import { useAppStore, useCurrentClient } from '../../stores/appStore';
import PageHeader from '../../components/layout/PageHeader';

export default function AgencyClientsPage() {
  const { t } = useTranslation(['management', 'common', 'agency_portal']);
  const navigate = useNavigate();
  const { clients, loading } = useClients();
  const currentClient = useCurrentClient();
  const setCurrentClient = useAppStore((s) => s.setCurrentClient);

  const [search, setSearch] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);

  const filteredClients = (clients || []).filter((c) =>
    !search ||
    (c.company || '').toLowerCase().includes(search.toLowerCase()) ||
    (c.name || '').toLowerCase().includes(search.toLowerCase())
  );

  const handleSelectAndGo = (client) => {
    setCurrentClient(client);
    navigate('/dashboard/analytics');
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
            onClick={() => setShowAddModal(true)}
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

      {/* Add Client Modal Placeholder */}
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
            maxWidth: 480,
            padding: 24,
            position: 'relative',
          }}>
            <button
              type="button"
              onClick={() => setShowAddModal(false)}
              aria-label="Cerrar"
              style={{
                position: 'absolute',
                top: 16,
                right: 16,
                border: 'none',
                background: 'transparent',
                color: 'var(--text-tertiary)',
                cursor: 'pointer',
              }}
            >
              <X size={18} />
            </button>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
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
                  Alta de workspace en Agencia #2
                </span>
              </div>
            </div>

            <div style={{
              background: 'var(--surface-sunken)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: 14,
              fontSize: 13,
              color: 'var(--text-secondary)',
              lineHeight: 1.5,
              display: 'flex',
              gap: 10,
            }}>
              <AlertCircle size={18} style={{ color: 'var(--brand-primary)', flexShrink: 0, marginTop: 2 }} />
              <div>
                <strong>Aprovisionamiento preparado:</strong> El flujo de creación e invitación de clientes dedicados se habilitará en la siguiente fase (BS-8G).
                En esta fase, la base de datos canónica se mantiene intacta.
              </div>
            </div>

            <div style={{ marginTop: 20, display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-default)',
                  background: 'transparent',
                  color: 'var(--text-primary)',
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
