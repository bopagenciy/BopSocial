# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Author    : Chandrabhan Shekhawat
#  Company   : Gigai Kripa Services
#  Website   : https://gigaikripaservices.com/
#  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
#  Released under the MIT License — see LICENSE. Keep this notice.
# ============================================================================
"""
Permission enforcement layer for the two-sided marketplace.

This module provides two helpers that mutating views call BEFORE executing
the mutation:

    resolve_acting_context(request, client) -> ('owner'|'superadmin'|'agency'|'forbidden', relation_or_None)

    check_action(request, client, action_key, *, action_type=None,
                 payload=None, target_object_type='', target_object_id=None,
                 preview='') -> ('allowed'|'denied'|'approval_required', extra)

Semantics:
    - Superadmin bypasses everything.
    - Owner (UserProfile.role='client' AND profile.client_id == client.id, OR
      Client.owner_user == request.user) is always allowed for any action on
      their own workspace.
    - Otherwise the user must be an active member of an agency that has an
      *active* AgencyClientRelation against this client, and that relation
      must grant the action_key in its `permissions` dict.
    - If the relation grants the action BUT lists it under
      `requires_approval_for`, the helper creates an ApprovalRequest and
      returns ('approval_required', approval_request). The caller MUST NOT
      proceed with the mutation in that case — it should return 202 with
      {'requires_approval': True, 'approval_id': ar.id}.

Rule-of-thumb: legacy data stays unchanged. The backfill set every
permission to True for every legacy relation, so existing agency staff still
get through this gate untouched.

Note on Rule #9 of the marketplace spec: end-users can ALWAYS disconnect
their platforms even when agency-managed. Callers handling
`disconnect_platforms` should call `check_action` only when the actor is
agency-side; the owner branch passes through naturally.
"""
from __future__ import annotations

from typing import Optional

from .models import (
    AGENCY_CLIENT_PERMISSIONS,
    AgencyClientRelation,
    AgencyMembership,
    ApprovalRequest,
    Client,
)


# ─────────────────────────────────────────────────────────────────────────────
# Acting context resolution
# ─────────────────────────────────────────────────────────────────────────────
def _profile(user):
    return getattr(user, 'profile', None)


def get_client_user_role(user, client: Client) -> Optional[str]:
    """Return the explicit ClientUserRole.role for (user, client), or None."""
    if not user or not user.is_authenticated or not client:
        return None
    from .models import ClientUserRole
    return (
        ClientUserRole.objects.filter(user=user, client=client)
        .values_list('role', flat=True)
        .first()
    )


def _is_owner(user, client: Client) -> bool:
    """True if `user` owns `client` directly (or is the legacy client-role user
    pointing at it without a restricted ClientUserRole)."""
    if not user or not user.is_authenticated:
        return False
    if client.owner_user_id and client.owner_user_id == user.id:
        return True
    client_role = get_client_user_role(user, client)
    if client_role is not None:
        return client_role == 'client_admin'
    prof = _profile(user)
    if prof and prof.role == 'client' and prof.account_type != 'agency_member' and prof.client_id == client.id:
        return True
    return False


def _is_superadmin(user) -> bool:
    prof = _profile(user)
    return bool(prof and prof.role == 'superadmin')


def can_approve_for_client(user, client: Client) -> bool:
    """Canonical approval authorization policy shared across approvals and composer."""
    if not user or not user.is_authenticated or not client:
        return False
    if _is_superadmin(user):
        return True
    if client.owner_user_id and client.owner_user_id == user.id:
        return True
    client_role = get_client_user_role(user, client)
    if client_role is not None:
        return client_role in ('approver', 'client_admin')
    if _is_owner(user, client):
        return True

    prof = _profile(user)
    if not prof or prof.account_type != 'agency_member' or not prof.primary_agency_id:
        return False
    membership = AgencyMembership.objects.filter(
        agency_id=prof.primary_agency_id, user=user, is_active=True
    ).first()
    if not membership or membership.role not in ('owner', 'admin', 'manager'):
        return False
    relation = AgencyClientRelation.objects.filter(
        agency_id=prof.primary_agency_id, client=client, status='active'
    ).first()
    if not relation:
        return False
    # Agency-side approval only when client has no external owner_user
    if client.owner_user_id is not None:
        return False
    return True


def can_mutate_content(user, client: Client) -> bool:
    """True if user may create/edit/delete/schedule/publish content for `client`."""
    if not user or not user.is_authenticated or not client:
        return False
    if _is_superadmin(user):
        return True
    prof = _profile(user)
    if prof and prof.role == 'staff':
        return prof.assigned_clients.filter(id=client.id).exists()
    client_role = get_client_user_role(user, client)
    if client_role is not None:
        return client_role in ('editor', 'client_admin')
    if _is_owner(user, client):
        return True
    return _resolve_relation(user, client) is not None


def can_manage_social_accounts(user, client: Client) -> bool:
    """True if user may initiate OAuth or manage social credentials for `client`."""
    if not user or not user.is_authenticated or not client:
        return False
    if _is_superadmin(user):
        return True
    prof = _profile(user)
    if prof and prof.role == 'staff':
        return prof.assigned_clients.filter(id=client.id).exists()
    client_role = get_client_user_role(user, client)
    if client_role is not None:
        return client_role == 'client_admin'
    if _is_owner(user, client):
        return True
    if not prof or prof.account_type != 'agency_member' or not prof.primary_agency_id:
        return False
    membership = AgencyMembership.objects.filter(
        agency_id=prof.primary_agency_id, user=user, is_active=True
    ).first()
    if not membership or membership.role not in ('owner', 'admin', 'manager'):
        return False
    relation = AgencyClientRelation.objects.filter(
        agency_id=prof.primary_agency_id, client=client, status='active'
    ).first()
    return bool(relation and relation.can('connect_platforms'))


def can_manage_client_workspace(user, client: Client, *, destructive: bool = False) -> bool:
    """True if user may update (destructive=False) or delete (destructive=True) `client`."""
    if not user or not user.is_authenticated or not client:
        return False
    if _is_superadmin(user):
        return True
    prof = _profile(user)
    if prof and prof.role == 'staff' and not destructive:
        return prof.assigned_clients.filter(id=client.id).exists()
    if client.owner_user_id and client.owner_user_id == user.id:
        return True
    client_role = get_client_user_role(user, client)
    if client_role is not None:
        return client_role == 'client_admin'
    if _is_owner(user, client):
        return True
    if not prof or prof.account_type != 'agency_member' or not prof.primary_agency_id:
        return False
    membership = AgencyMembership.objects.filter(
        agency_id=prof.primary_agency_id, user=user, is_active=True
    ).first()
    allowed_agency_roles = ('owner', 'admin') if destructive else ('owner', 'admin', 'manager')
    if not membership or membership.role not in allowed_agency_roles:
        return False
    relation = AgencyClientRelation.objects.filter(
        agency_id=prof.primary_agency_id, client=client, status='active'
    ).first()
    if not relation:
        return False
    if destructive and client.owner_user_id is not None:
        return False
    return True


def _resolve_relation(user, client: Client) -> Optional[AgencyClientRelation]:
    """Find the active AgencyClientRelation that lets `user` act on `client`.

    A user can act on behalf of any agency they are an active member of.
    We pick the relation for the agency they are most likely "currently
    representing" — for now: the one matching `profile.primary_agency` if set,
    else the first active relation found.
    """
    prof = _profile(user)
    if not prof:
        return None

    agency_ids = list(
        AgencyMembership.objects.filter(user=user, is_active=True)
        .values_list('agency_id', flat=True)
    )
    if not agency_ids:
        return None

    qs = AgencyClientRelation.objects.filter(
        client=client, agency_id__in=agency_ids, status='active',
    )
    if prof.primary_agency_id:
        primary = qs.filter(agency_id=prof.primary_agency_id).first()
        if primary:
            return primary
    return qs.first()


def resolve_acting_context(request, client: Client):
    """Return (role, relation_or_None).

    role is one of 'superadmin', 'owner', 'agency', 'forbidden'.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return ('forbidden', None)
    if _is_superadmin(user):
        return ('superadmin', None)
    if _is_owner(user, client):
        return ('owner', None)
    if get_client_user_role(user, client) == 'editor':
        return ('client_editor', None)
    relation = _resolve_relation(user, client)
    if relation:
        return ('agency', relation)
    return ('forbidden', None)


# ─────────────────────────────────────────────────────────────────────────────
# Action check (the call sites use this)
# ─────────────────────────────────────────────────────────────────────────────
def check_action(
    request,
    client: Client,
    action_key: str,
    *,
    action_type: Optional[str] = None,
    payload: Optional[dict] = None,
    target_object_type: str = '',
    target_object_id: Optional[int] = None,
    preview: str = '',
):
    """Check whether the request may perform `action_key` on `client`.

    Returns one of:
        ('allowed',           {'role': 'superadmin'|'owner'|'agency', 'relation': r|None})
        ('denied',            {'reason': str})
        ('approval_required', {'approval': ApprovalRequest, 'relation': r})

    `action_key` must be a key in AGENCY_CLIENT_PERMISSIONS.

    `action_type` (free-form string like 'publish_post', 'send_campaign')
    is recorded on the ApprovalRequest when one is created. If omitted,
    the action_key is used.
    """
    if action_key not in AGENCY_CLIENT_PERMISSIONS:
        return ('denied', {'reason': f'unknown action: {action_key}'})

    role, relation = resolve_acting_context(request, client)

    if role in ('superadmin', 'owner', 'client_editor'):
        return ('allowed', {'role': role, 'relation': None})

    if role == 'forbidden':
        return ('denied', {'reason': 'no active agency relation for this workspace'})

    # role == 'agency'
    if not relation.can(action_key):
        return ('denied', {
            'reason': f'agency does not have permission "{action_key}" on this workspace',
        })

    if relation.needs_approval(action_key):
        ar = ApprovalRequest.objects.create(
            relation=relation,
            client=client,
            requested_by=request.user,
            action_type=(action_type or action_key),
            payload=payload or {},
            preview=preview,
            target_object_type=target_object_type,
            target_object_id=target_object_id,
        )
        from django.conf import settings
        from .locale_helpers import resolve_user_language, get_notification_copy
        from .notification_dispatcher import dispatch as dispatch_notification
        from .models import ClientUserRole
        frontend = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')

        recipients = []
        seen_ids = set()
        if client.owner_user_id:
            recipients.append(client.owner_user)
            seen_ids.add(client.owner_user_id)
        for cur in ClientUserRole.objects.filter(
            client=client, role__in=('approver', 'client_admin')
        ).select_related('user'):
            if cur.user_id not in seen_ids:
                recipients.append(cur.user)
                seen_ids.add(cur.user_id)

        for recipient in recipients:
            recip_lang = resolve_user_language(recipient, client)
            notif_copy = get_notification_copy('approval_requested', lang=recip_lang, agency_name=relation.agency.name)
            body_text = preview or (f'Desean realizar: {action_type or action_key}' if recip_lang == 'es' else f'They want to: {action_type or action_key}')
            dispatch_notification(
                recipient,
                event_type='approval_requested',
                title=notif_copy['title'],
                body=body_text[:300],
                cta_url=f'{frontend}/u/approvals',
                cta_label=notif_copy['cta_label'],
                data={
                    'kind':         'approval_requested',
                    'approval_id':  ar.id,
                    'agency_name':  relation.agency.name,
                    'action_type':  action_type or action_key,
                    'expires_at':   ar.expires_at.isoformat() if ar.expires_at else None,
                },
            )
        return ('approval_required', {'approval': ar, 'relation': relation})

    return ('allowed', {'role': 'agency', 'relation': relation})


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: turn a check result into a DRF Response
# ─────────────────────────────────────────────────────────────────────────────
def deny_response(reason: str, status_code: int = 403):
    from rest_framework.response import Response
    return Response({'error': reason}, status=status_code)


def approval_pending_response(approval: ApprovalRequest):
    """Standard 202 envelope when an action is intercepted for approval."""
    from rest_framework.response import Response
    return Response(
        {
            'requires_approval': True,
            'approval_id':       approval.id,
            'action_type':       approval.action_type,
            'expires_at':        approval.expires_at.isoformat(),
            'message':           f'Submitted to {approval.client.company} for approval.',
        },
        status=202,
    )
