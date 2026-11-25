# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  BOP SOCIAL — Dedicated Agency Client Creation View (BS-8G)
# ============================================================================
import re
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from .models import Client, ClientInvitation, CLIENT_USER_ROLE_CHOICES
from .serializers import ClientSerializer
from .marketplace_models import (
    AgencyMembership,
    AgencyClientRelation,
    default_relation_permissions,
)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def agency_clients_endpoint(request):
    """
    Dedicated agency-scoped clients endpoint (BS-8G).
    GET:  List active clients connected to the authenticated user's primary agency.
    POST: Atomically provision a new agency-managed client workspace and relation.
    """
    profile = getattr(request.user, 'profile', None)
    if not profile:
        return Response({'error': 'User profile not found.'}, status=403)

    if profile.account_type != 'agency_member':
        return Response({'error': 'Only agency members can access this endpoint.'}, status=403)

    agency = profile.primary_agency
    if not agency:
        return Response({'error': 'No primary agency associated with user.'}, status=403)

    membership = AgencyMembership.objects.filter(
        agency=agency, user=request.user, is_active=True
    ).first()
    if not membership:
        return Response({'error': 'Active agency membership required.'}, status=403)

    # ── GET: List agency-managed clients ──────────────────────────────────────
    if request.method == 'GET':
        active_client_ids = list(
            AgencyClientRelation.objects.filter(
                agency=agency, status='active'
            ).values_list('client_id', flat=True)
        )
        clients = Client.objects.filter(id__in=active_client_ids).order_by('company')
        return Response(ClientSerializer(clients, many=True).data)

    # ── POST: Create new agency-managed client ────────────────────────────────
    if membership.role not in ('owner', 'admin', 'manager'):
        return Response({'error': 'Insufficient agency role to create clients.'}, status=403)

    data = request.data

    # Required fields
    company = (data.get('company') or '').strip()
    name = (data.get('name') or '').strip()
    raw_email = (data.get('email') or '').strip()

    errors = {}
    if not company:
        errors['company'] = ['Company name is required.']
    if not name:
        errors['name'] = ['Contact/Workspace name is required.']
    if not raw_email:
        errors['email'] = ['Email is required.']
    else:
        try:
            validate_email(raw_email)
        except ValidationError:
            errors['email'] = ['Enter a valid email address.']

    if errors:
        return Response({'error': 'Validation failed.', 'details': errors}, status=400)

    # Normalized email
    normalized_email = raw_email.lower()

    # Duplicate safety: prevent duplicate Client or duplicate relation
    if Client.objects.filter(email__iexact=normalized_email).exists() or AgencyClientRelation.objects.filter(
        agency=agency, client__email__iexact=normalized_email
    ).exists():
        return Response({
            'error': 'A client workspace with this email already exists.',
            'details': {'email': ['A client with this email already exists.']}
        }, status=400)

    # Optional fields
    website = (data.get('website') or '').strip()
    timezone = (data.get('timezone') or '').strip()
    default_lang = data.get('default_language') or 'es'
    if default_lang not in ('en', 'es'):
        default_lang = 'es'

    currency = data.get('currency') or 'USD'
    business_cat = (data.get('business_category') or data.get('industry') or '').strip()
    business_loc = (data.get('location_country') or '').strip()
    requires_approval = bool(data.get('requires_approval', False))

    # Atomic creation: Client + AgencyClientRelation
    with transaction.atomic():
        client = Client.objects.create(
            company=company,
            name=name,
            email=normalized_email,
            website=website,
            timezone=timezone,
            default_language=default_lang,
            currency=currency,
            business_category=business_cat,
            business_location=business_loc,
            requires_approval=requires_approval,
            ownership_type='agency_owned',
            created_via='agency_invite',
            is_active=True,
        )

        relation = AgencyClientRelation.objects.create(
            agency=agency,
            client=client,
            status='active',
            initiated_by='agency',
            initiated_by_user=request.user,
            permissions=default_relation_permissions(),
        )

    return Response({
        'client': ClientSerializer(client).data,
        'relation': {
            'id': relation.id,
            'agency_id': relation.agency_id,
            'client_id': relation.client_id,
            'status': relation.status,
            'initiated_by': relation.initiated_by,
        },
        'message': 'Client workspace created successfully.'
    }, status=201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def agency_client_invite_endpoint(request, client_id):
    """
    Agency-scoped client user invitation endpoint (BS-8J.2).
    Allows Agency Owner / Admin / Manager to invite a stakeholder user into an existing
    managed client workspace.
    """
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.account_type != 'agency_member':
        return Response({'error': 'Only agency members can invite client users.'}, status=403)

    agency = profile.primary_agency
    if not agency:
        return Response({'error': 'No primary agency associated with user.'}, status=403)

    membership = AgencyMembership.objects.filter(
        agency=agency, user=request.user, is_active=True
    ).first()
    if not membership:
        return Response({'error': 'Active agency membership required.'}, status=403)

    if membership.role not in ('owner', 'admin', 'manager'):
        return Response({'error': 'Insufficient agency role to invite client users.'}, status=403)

    client = Client.objects.filter(id=client_id).first()
    if not client:
        return Response({'error': 'Client workspace not found.'}, status=404)

    relation = AgencyClientRelation.objects.filter(agency=agency, client=client).first()
    if not relation or relation.status != 'active':
        return Response({'error': 'Active agency-client relation required.'}, status=403)

    # ── GET: List invitations for this client ─────────────────────────────────
    if request.method == 'GET':
        invitations = ClientInvitation.objects.filter(
            client_record=client,
            agency=agency,
        ).order_by('-invited_at')
        data = []
        for inv in invitations:
            is_exp = inv.is_expired
            inv_status = 'expired' if is_exp else inv.status
            data.append({
                'id': inv.id,
                'token': str(inv.token),
                'client_id': client.id,
                'client_email': inv.client_email,
                'role': inv.role,
                'status': inv_status,
                'message': inv.message,
                'invited_at': inv.invited_at.isoformat() if inv.invited_at else None,
                'expires_at': inv.expires_at.isoformat() if inv.expires_at else None,
                'responded_at': inv.responded_at.isoformat() if inv.responded_at else None,
                'accepted_at': inv.accepted_at.isoformat() if inv.accepted_at else None,
            })
        return Response(data)

    # ── POST: Create invitation ───────────────────────────────────────────────
    raw_email = request.data.get('email')
    if not raw_email or not str(raw_email).strip():
        return Response({'error': 'Email is required.', 'details': {'email': ['Email is required.']}}, status=400)

    normalized_email = str(raw_email).strip().lower()
    try:
        validate_email(normalized_email)
    except ValidationError:
        return Response({'error': 'Enter a valid email address.', 'details': {'email': ['Enter a valid email address.']}}, status=400)

    role = request.data.get('role', 'viewer')
    valid_roles = [r[0] for r in CLIENT_USER_ROLE_CHOICES]
    if role not in valid_roles:
        return Response({
            'error': f'Invalid role. Allowed roles are: {", ".join(valid_roles)}',
            'details': {'role': [f'Invalid role. Allowed: {", ".join(valid_roles)}']}
        }, status=400)

    message = request.data.get('message', '')
    if isinstance(message, str):
        message = message.strip()
    else:
        message = ''

    # Duplicate pending check
    pending_invite = ClientInvitation.objects.filter(
        client_record=client,
        client_email=normalized_email,
        status='pending',
    ).first()
    if pending_invite and not pending_invite.is_expired:
        return Response({
            'error': 'A pending invitation already exists for this email in this client workspace.',
            'details': {'email': ['A pending invitation already exists for this email.']}
        }, status=400)

    from django.contrib.auth.models import User
    existing_user = User.objects.filter(email__iexact=normalized_email).first()

    with transaction.atomic():
        invitation = ClientInvitation.objects.create(
            invited_by=request.user,
            agency=agency,
            client_record=client,
            client_email=normalized_email,
            client_user=existing_user,
            role=role,
            message=message,
            status='pending',
        )

    from .invitation_views import _send_invitation_email
    email_sent, email_error = _send_invitation_email(invitation, existing_user)

    return Response({
        'id': invitation.id,
        'token': str(invitation.token),
        'client_id': client.id,
        'client_name': client.company or client.name,
        'agency_id': agency.id,
        'agency_name': agency.name,
        'client_email': invitation.client_email,
        'role': invitation.role,
        'status': invitation.status,
        'message': invitation.message,
        'invited_at': invitation.invited_at.isoformat() if invitation.invited_at else None,
        'expires_at': invitation.expires_at.isoformat() if invitation.expires_at else None,
        'invite_url': f"/invitation/{invitation.token}",
        'email_sent': email_sent,
        'email_error': email_error,
    }, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agency_client_revoke_invitation_endpoint(request, client_id, invite_id):
    """
    Revoke a pending client invitation (BS-8J.2).
    """
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.account_type != 'agency_member':
        return Response({'error': 'Only agency members can revoke invitations.'}, status=403)

    agency = profile.primary_agency
    if not agency:
        return Response({'error': 'No primary agency associated with user.'}, status=403)

    membership = AgencyMembership.objects.filter(
        agency=agency, user=request.user, is_active=True
    ).first()
    if not membership or membership.role not in ('owner', 'admin', 'manager'):
        return Response({'error': 'Insufficient agency role to revoke invitations.'}, status=403)

    relation = AgencyClientRelation.objects.filter(agency=agency, client_id=client_id).first()
    if not relation or relation.status != 'active':
        return Response({'error': 'Active agency-client relation required.'}, status=403)

    invitation = ClientInvitation.objects.filter(
        id=invite_id, client_record_id=client_id, agency=agency
    ).first()
    if not invitation:
        return Response({'error': 'Invitation not found.'}, status=404)

    if invitation.status != 'pending':
        return Response({'error': f'Cannot revoke invitation with status "{invitation.status}".'}, status=400)

    invitation.status = 'revoked'
    invitation.save(update_fields=['status'])
    return Response({'status': 'revoked', 'message': 'Invitation has been revoked.'}, status=200)
