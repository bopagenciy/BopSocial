import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { FileText, PenSquare, Trash2, Edit3, Plus, Loader2, Image as ImageIcon } from 'lucide-react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';

import PageHeader from '../../components/layout/PageHeader';
import Button from '../../components/ui/Button';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import { composerAPI } from '../../services/api';
import { useAuth } from '../../hooks/useAuth';
import { useCurrentClient } from '../../stores/appStore';
import { formatDate } from '../../utils/formatters';

export default function DraftsPage() {
  const { t } = useTranslation('content');
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const currentClient = useCurrentClient();

  const isMultiWorkspace =
    user?.account_type === 'agency_member' || user?.role === 'superadmin' || user?.role === 'staff';
  const activeClientId = currentClient?.id || (!isMultiWorkspace ? user?.client_id : null) || null;
  const activeClientRef = useRef(activeClientId);
  activeClientRef.current = activeClientId;

  const basePath = location.pathname.startsWith('/admin') ? '/admin/analytics' : '/dashboard/analytics';

  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState(null);

  const loadDrafts = useCallback(async () => {
    const reqClientId = activeClientRef.current;
    if (!reqClientId) {
      setDrafts([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await composerAPI.posts.list({ client_id: reqClientId, status: 'draft' });
      if (activeClientRef.current !== reqClientId) return;
      const items = res.data?.results || res.data || [];
      setDrafts(Array.isArray(items) ? items : []);
    } catch (e) {
      if (activeClientRef.current !== reqClientId) return;
      toast.error(e.response?.data?.detail || 'Error al cargar los borradores.');
      setDrafts([]);
    } finally {
      if (activeClientRef.current === reqClientId) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    setDrafts([]);
    loadDrafts();
  }, [activeClientId, loadDrafts]);

  async function onDeleteDraft(draft) {
    if (!activeClientId) return;
    const confirmed = window.confirm(
      t('drafts.delete_confirm', '¿Eliminar este borrador permanentemente? Esta acción no se puede deshacer.'),
    );
    if (!confirmed) return;

    const reqClientId = activeClientId;
    setDeletingId(draft.id);
    try {
      const res = await composerAPI.posts.delete(draft.id);
      if (activeClientRef.current !== reqClientId) return;
      if (res?.status === 202) {
        toast.success(res.data?.detail || t('drafts.delete_approval_pending', 'Solicitud de eliminación enviada para aprobación.'));
      } else {
        setDrafts((cur) => cur.filter((d) => d.id !== draft.id));
        toast.success(t('drafts.deleted', 'Borrador eliminado.'));
      }
    } catch (e) {
      if (activeClientRef.current !== reqClientId) return;
      toast.error(
        e.response?.data?.detail ||
          t('drafts.delete_failed', 'No tienes permisos para eliminar este borrador.'),
      );
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div style={{ paddingBottom: 40 }}>
      <PageHeader
        title={t('drafts.title', 'Borradores')}
        subtitle={t('drafts.subtitle', 'Retoma, edita o programa tus publicaciones guardadas en este espacio de trabajo.')}
        action={
          <Button
            variant="primary"
            icon={Plus}
            onClick={() => navigate(`${basePath}/composer`)}
          >
            {t('drafts.new_post', 'Nueva publicación')}
          </Button>
        }
      />

      {!activeClientId ? (
        <Card padding="lg">
          <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
            {t('composer.select_client_required', 'Selecciona un espacio de trabajo primero.')}
          </p>
        </Card>
      ) : loading ? (
        <div style={{ padding: 48, display: 'flex', justifyContent: 'center' }}>
          <Loader2 size={22} className="ds-spin" color="var(--text-tertiary)" />
          <style>{`.ds-spin { animation: ds-spin 0.9s linear infinite; } @keyframes ds-spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      ) : drafts.length === 0 ? (
        <Card padding="lg">
          <div style={{ textAlign: 'center', padding: '24px 12px' }}>
            <FileText size={32} color="var(--text-tertiary)" style={{ marginBottom: 12 }} />
            <h3 style={{ margin: '0 0 6px', fontSize: 16 }}>
              {t('drafts.empty_title', 'No hay borradores guardados')}
            </h3>
            <p style={{ margin: '0 0 16px', color: 'var(--text-secondary)', fontSize: 13 }}>
              {t('drafts.empty_desc', 'Guarda una publicación como borrador en el Compositor para retomarla más tarde.')}
            </p>
            <Button variant="primary" icon={PenSquare} onClick={() => navigate(`${basePath}/composer`)}>
              {t('drafts.open_composer', 'Ir al Compositor')}
            </Button>
          </div>
        </Card>
      ) : (
        <div style={{ display: 'grid', gap: 12 }}>
          {drafts.map((draft) => {
            const displayTitle = draft.title?.trim() || (draft.content || '').slice(0, 72) || `Borrador #${draft.id}`;
            const snippet = (draft.content || '').slice(0, 140);
            const platforms = Array.isArray(draft.target_platforms) ? draft.target_platforms : [];
            return (
              <Card key={draft.id} padding="md">
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                  <div
                    style={{
                      width: 68,
                      height: 68,
                      borderRadius: 10,
                      background: 'var(--surface-sunken)',
                      border: '1px solid var(--border-subtle)',
                      overflow: 'hidden',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    {draft.thumbnail_url ? (
                      <img
                        src={draft.thumbnail_url}
                        alt={displayTitle}
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      />
                    ) : (
                      <ImageIcon size={22} color="var(--text-tertiary)" />
                    )}
                  </div>

                  <div style={{ flex: 1, minWidth: 220 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                      <strong style={{ fontSize: 14, color: 'var(--text-primary)' }}>{displayTitle}</strong>
                      <Badge variant="neutral">{t('drafts.status_draft', 'Borrador')}</Badge>
                    </div>
                    {snippet && (
                      <p style={{ margin: '0 0 8px', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                        {snippet}
                        {(draft.content || '').length > 140 ? '…' : ''}
                      </p>
                    )}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 12, color: 'var(--text-tertiary)' }}>
                      {platforms.map((p) => (
                        <Badge key={p} variant="info">
                          {p}
                        </Badge>
                      ))}
                      <span>
                        {t('drafts.updated_at', 'Actualizado')}: {formatDate(draft.updated_at || draft.created_at)}
                      </span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Button
                      variant="primary"
                      size="sm"
                      icon={Edit3}
                      onClick={() => navigate(`${basePath}/composer/${draft.id}`)}
                    >
                      {t('drafts.edit', 'Editar')}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={Trash2}
                      loading={deletingId === draft.id}
                      onClick={() => onDeleteDraft(draft)}
                      aria-label={t('drafts.delete', 'Eliminar borrador')}
                    >
                      {t('drafts.delete_short', 'Eliminar')}
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
