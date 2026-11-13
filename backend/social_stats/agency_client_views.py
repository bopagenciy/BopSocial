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

from .models import Client
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
