# ============================================================================
#  Social Stats — Phase BS-2.7D: Marketplace, ROI & Reporting Financial
#                                Localization Test Suite
# ============================================================================
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from social_stats.bot_models import BotFlow, CTWACampaign, Lead
from social_stats.currencies import DEFAULT_CURRENCY, SUPPORTED_CURRENCIES
from social_stats.dashboard_views import dashboard_today
from social_stats.lead_views import LeadViewSet
from social_stats.manage_request_views import send_manage_request, accept_manage_invite
from social_stats.marketplace_models import Agency, AgencyClientRelation, ManageRequest
from social_stats.meta_capi import resolve_capi_currency
from social_stats.models import (
    AgencyMembership,
    Client,
    ROIReport,
    ROISettings,
    UserProfile,
    WhatsAppContact,
)
from social_stats.roi_views import calculate_roi, ROICalculateView


class BS27DFinancialLocalizationTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

        # Clients with different currencies
        self.client_usd = Client.objects.create(
            name='Global Corp', company='Global Corp LLC',
            email=f'client_{uuid.uuid4().hex[:8]}@example.com',
            currency='USD',
        )
        self.client_eur = Client.objects.create(
            name='Euro Tech', company='Euro Tech BV',
            email=f'client_{uuid.uuid4().hex[:8]}@example.com',
            currency='EUR',
        )
        self.client_inr = Client.objects.create(
            name='India Retail', company='India Retail Pvt',
            email=f'client_{uuid.uuid4().hex[:8]}@example.com',
            currency='INR',
        )

        # Users and profiles
        self.user_usd = User.objects.create_user(
            username=f'user_usd_{uuid.uuid4().hex[:6]}', password='password123',
            email=f'user_usd_{uuid.uuid4().hex[:6]}@example.com',
        )
        UserProfile.objects.create(user=self.user_usd, client=self.client_usd, role='client')

        self.user_eur = User.objects.create_user(
            username=f'user_eur_{uuid.uuid4().hex[:6]}', password='password123'
        )
        UserProfile.objects.create(user=self.user_eur, client=self.client_eur, role='client')

        # Agency
        self.agency_user = User.objects.create_user(
            username=f'agency_owner_{uuid.uuid4().hex[:6]}', password='password123'
        )
        self.agency = Agency.objects.create(
            name='Apex Marketing',
            slug=f'apex-marketing-{uuid.uuid4().hex[:6]}',
            owner_user=self.agency_user,
            pricing_currency='GBP',
            pricing_starting_at=Decimal('1500.00'),
        )
        UserProfile.objects.create(user=self.agency_user, client=self.client_usd, role='agency_owner')
        AgencyMembership.objects.create(agency=self.agency, user=self.agency_user, role='owner', is_active=True)

    def test_marketplace_agency_and_relation_currency_defaults(self):
        """Agency and AgencyClientRelation define valid currency fields defaulting to USD."""
        agency_default = Agency.objects.create(
            name='Default Agency',
            slug=f'default-{uuid.uuid4().hex[:6]}',
            owner_user=self.user_usd,
        )
        self.assertEqual(agency_default.pricing_currency, 'USD')

        relation = AgencyClientRelation.objects.create(
            agency=self.agency,
            client=self.client_eur,
            monthly_fee=Decimal('2500.00'),
            fee_currency='EUR',
        )
        self.assertEqual(relation.fee_currency, 'EUR')
        self.assertEqual(relation.monthly_fee, Decimal('2500.00'))

    def test_manage_request_currency_authority_hierarchy(self):
        """Test ManageRequest currency resolution hierarchy and propagation upon acceptance."""
        # 1. Explicit currency wins
        req_explicit = self.factory.post('/api/manage-request/send/', {
            'target_client_id': self.client_usd.id,
            'target_email': self.user_usd.email,
            'proposed_pricing': '3000.00',
            'proposed_currency': 'EUR',
            'proposed_message': 'Explicit currency test',
            'proposed_permissions': {'can_view_analytics': True},
        }, format='json')
        force_authenticate(req_explicit, user=self.agency_user)
        res_explicit = send_manage_request(req_explicit)
        self.assertEqual(res_explicit.status_code, 201)
        self.assertEqual(res_explicit.data['proposed_currency'], 'EUR')

        mr_id = res_explicit.data['id']
        mr = ManageRequest.objects.get(id=mr_id)
        self.assertEqual(mr.proposed_currency, 'EUR')
        self.assertEqual(mr.currency, 'EUR')

        # 2. Acceptance propagates fee_currency and monthly_fee to AgencyClientRelation
        accept_req = self.factory.post(f'/api/manage-invite/{mr.token}/accept/', {})
        force_authenticate(accept_req, user=self.user_usd)
        res_accept = accept_manage_invite(accept_req, token=mr.token)
        self.assertEqual(res_accept.status_code, 200)

        relation = AgencyClientRelation.objects.get(agency=self.agency, client=self.client_usd)
        self.assertEqual(relation.fee_currency, 'EUR')
        self.assertEqual(relation.monthly_fee, Decimal('3000.00'))

        # 3. Fallback when currency not explicitly provided:
        # client_eur without existing relation -> falls back to client.currency ('EUR')
        req_implicit = self.factory.post('/api/manage-request/send/', {
            'target_client_id': self.client_eur.id,
            'target_email': 'another_client@example.com',
            'proposed_pricing': '2000.00',
            'proposed_message': 'Implicit fallback test',
            'proposed_permissions': {'can_view_analytics': True},
        }, format='json')
        force_authenticate(req_implicit, user=self.agency_user)
        res_implicit = send_manage_request(req_implicit)
        self.assertEqual(res_implicit.status_code, 201)
        self.assertEqual(res_implicit.data['proposed_currency'], 'EUR')

    def test_roi_report_snapshot_immutability(self):
        """Saved ROIReport snapshots authoritative currency and is immutable against later updates."""
        settings = ROISettings.objects.create(
            client=self.client_eur,
            facebook_budget=Decimal('500.00'),
            agency_fee=Decimal('200.00'),
            currency='EUR',
        )

        req = self.factory.post('/api/roi/calculate/', {
            'client_id': self.client_eur.id,
            'month': 5,
            'year': 2026,
        })
        force_authenticate(req, user=self.user_eur)
        view = ROICalculateView.as_view()
        res = view(req)
        self.assertEqual(res.status_code, 200)

        report = ROIReport.objects.get(client=self.client_eur, month=5, year=2026)
        self.assertEqual(report.currency, 'EUR')

        # Mutate client and settings currency
        self.client_eur.currency = 'USD'
        self.client_eur.save()
        settings.currency = 'GBP'
        settings.save()

        # Re-fetch report and assert currency is unchanged
        report.refresh_from_db()
        self.assertEqual(report.currency, 'EUR')

    def test_lead_conversion_currency_hierarchy(self):
        """Lead conversion authoritative hierarchy: CTWA campaign > explicit param > client.currency > USD."""
        flow = BotFlow.objects.create(client=self.client_eur, name='Sales Flow')
        campaign_gbp = CTWACampaign.objects.create(
            client=self.client_eur,
            flow=flow,
            name='UK Campaign',
            ad_account_id='act_uk_123',
            campaign_id='meta_uk_123',
            currency='GBP',
        )

        contact_eur = WhatsAppContact.objects.create(
            client=self.client_eur,
            phone='+4412345678',
            name='Alice UK',
        )

        # 1. CTWA campaign currency takes precedence
        lead_ctwa = Lead.objects.create(
            client=self.client_eur,
            contact=contact_eur,
            source_flow=flow,
            source_campaign_id='meta_uk_123',
            phone='+4412345678',
            name='Alice UK',
        )
        req1 = self.factory.post(f'/api/leads/{lead_ctwa.id}/convert/', {
            'conversion_value': 120.00,
            'currency': 'USD',  # Should be overridden by CTWA campaign GBP
        })
        force_authenticate(req1, user=self.user_eur)
        view1 = LeadViewSet.as_view({'post': 'convert'})
        res1 = view1(req1, pk=lead_ctwa.id)
        self.assertEqual(res1.status_code, 200)
        lead_ctwa.refresh_from_db()
        self.assertEqual(lead_ctwa.currency, 'GBP')
        self.assertEqual(lead_ctwa.conversion_value, Decimal('120.00'))

        # 2. Explicit conversion currency when no CTWA campaign
        contact_spain = WhatsAppContact.objects.create(
            client=self.client_eur,
            phone='+3412345678',
            name='Bob Spain',
        )
        lead_explicit = Lead.objects.create(
            client=self.client_eur,
            contact=contact_spain,
            source_flow=flow,
            phone='+3412345678',
            name='Bob Spain',
        )
        req2 = self.factory.post(f'/api/leads/{lead_explicit.id}/convert/', {
            'conversion_value': 250.00,
            'currency': 'CAD',
        })
        force_authenticate(req2, user=self.user_eur)
        view2 = LeadViewSet.as_view({'post': 'convert'})
        res2 = view2(req2, pk=lead_explicit.id)
        self.assertEqual(res2.status_code, 200)
        lead_explicit.refresh_from_db()
        self.assertEqual(lead_explicit.currency, 'CAD')

        # 3. Fallback to client currency
        contact_spain2 = WhatsAppContact.objects.create(
            client=self.client_eur,
            phone='+3498765432',
            name='Carlos Spain',
        )
        lead_fallback = Lead.objects.create(
            client=self.client_eur,
            contact=contact_spain2,
            source_flow=flow,
            phone='+3498765432',
            name='Carlos Spain',
        )
        req3 = self.factory.post(f'/api/leads/{lead_fallback.id}/convert/', {
            'conversion_value': 80.00,
        })
        force_authenticate(req3, user=self.user_eur)
        view3 = LeadViewSet.as_view({'post': 'convert'})
        res3 = view3(req3, pk=lead_fallback.id)
        self.assertEqual(res3.status_code, 200)
        lead_fallback.refresh_from_db()
        self.assertEqual(lead_fallback.currency, 'EUR')

    def test_lead_csv_export_currency_column(self):
        """Lead CSV export includes machine-readable 'currency' column adjacent to 'conversion_value'."""
        flow = BotFlow.objects.create(client=self.client_usd, name='Export Flow')
        contact_usd = WhatsAppContact.objects.create(
            client=self.client_usd,
            phone='+15550001',
            name='Export Lead 1',
        )
        Lead.objects.create(
            client=self.client_usd,
            contact=contact_usd,
            source_flow=flow,
            phone='+15550001',
            name='Export Lead 1',
            status='converted',
            conversion_value=Decimal('99.50'),
            currency='USD',
        )

        req = self.factory.get('/api/leads/export.csv/')
        force_authenticate(req, user=self.user_usd)
        view = LeadViewSet.as_view({'get': 'export_csv'})
        res = view(req)
        self.assertEqual(res.status_code, 200)

        csv_content = b''.join(res.streaming_content).decode('utf-8')
        lines = [line.strip() for line in csv_content.strip().split('\n') if line.strip()]
        self.assertGreater(len(lines), 1)

        headers = lines[0].split(',')
        self.assertIn('conversion_value', headers)
        self.assertIn('currency', headers)

        idx_val = headers.index('conversion_value')
        idx_curr = headers.index('currency')
        # Check adjacent
        self.assertEqual(abs(idx_val - idx_curr), 1)

        row_data = lines[1].split(',')
        self.assertEqual(row_data[idx_curr], 'USD')
        self.assertEqual(float(row_data[idx_val]), 99.50)

    def test_dashboard_pipeline_aggregation_single_currency(self):
        """Single-currency pipeline returns total, currency, and has_mixed_currencies=False."""
        contact1 = WhatsAppContact.objects.create(client=self.client_eur, phone='+331', name='C1')
        contact2 = WhatsAppContact.objects.create(client=self.client_eur, phone='+332', name='C2')
        Lead.objects.create(
            client=self.client_eur, contact=contact1, phone='+331', status='new',
            conversion_value=Decimal('500.00'), currency='EUR',
        )
        Lead.objects.create(
            client=self.client_eur, contact=contact2, phone='+332', status='qualified',
            conversion_value=Decimal('750.00'), currency='EUR',
        )

        req = self.factory.get('/api/dashboard/today/')
        force_authenticate(req, user=self.user_eur)
        res = dashboard_today(req)
        self.assertEqual(res.status_code, 200)

        leads_data = res.data['leads']
        self.assertEqual(leads_data['has_mixed_currencies'], False)
        self.assertEqual(leads_data['pipeline_value'], 1250.0)
        self.assertEqual(leads_data['currency'], 'EUR')

    def test_dashboard_pipeline_aggregation_mixed_currency_protection(self):
        """Mixed-currency pipeline never sums across currencies, returns null total & grouped map."""
        contact1 = WhatsAppContact.objects.create(client=self.client_eur, phone='+331', name='C1')
        contact2 = WhatsAppContact.objects.create(client=self.client_eur, phone='+111', name='C2')
        # Lead in EUR
        Lead.objects.create(
            client=self.client_eur, contact=contact1, phone='+331', status='new',
            conversion_value=Decimal('500.00'), currency='EUR',
        )
        # Lead in USD
        Lead.objects.create(
            client=self.client_eur, contact=contact2, phone='+111', status='qualified',
            conversion_value=Decimal('800.00'), currency='USD',
        )

        req = self.factory.get('/api/dashboard/today/')
        force_authenticate(req, user=self.user_eur)
        res = dashboard_today(req)
        self.assertEqual(res.status_code, 200)

        leads_data = res.data['leads']
        self.assertEqual(leads_data['has_mixed_currencies'], True)
        self.assertIsNone(leads_data['pipeline_value'])
        self.assertIn('EUR', leads_data['pipeline_values_by_currency'])
        self.assertIn('USD', leads_data['pipeline_values_by_currency'])
        self.assertEqual(leads_data['pipeline_values_by_currency']['EUR'], 500.0)
        self.assertEqual(leads_data['pipeline_values_by_currency']['USD'], 800.0)

    def test_legacy_inr_preservation(self):
        """Historical INR records preserve currency and exact monetary precision."""
        contact_inr = WhatsAppContact.objects.create(
            client=self.client_inr,
            phone='+919999999999',
            name='Dev Sharma',
        )
        lead_inr = Lead.objects.create(
            client=self.client_inr,
            contact=contact_inr,
            phone='+919999999999',
            name='Dev Sharma',
            status='converted',
            conversion_value=Decimal('150000.00'),
            currency='INR',
        )
        self.assertEqual(lead_inr.currency, 'INR')
        self.assertEqual(lead_inr.conversion_value, Decimal('150000.00'))

    def test_capi_currency_resolution_compatibility(self):
        """resolve_capi_currency respects lead conversion currency, then client currency, then USD."""
        contact1 = WhatsAppContact.objects.create(client=self.client_eur, phone='+339999', name='C1')
        contact2 = WhatsAppContact.objects.create(client=self.client_eur, phone='+338888', name='C2')
        lead = Lead.objects.create(
            client=self.client_eur,
            contact=contact1,
            phone='+339999',
            status='converted',
            currency='CAD',
            conversion_value=Decimal('300.00'),
        )
        # 1. Lead has CAD
        self.assertEqual(resolve_capi_currency(lead), 'CAD')

        # 2. Lead unconverted -> falls back to client EUR
        lead_unconv = Lead.objects.create(
            client=self.client_eur,
            contact=contact2,
            phone='+338888',
            status='new',
        )
        self.assertEqual(resolve_capi_currency(lead_unconv), 'EUR')

        # 3. Custom fields override
        lead_unconv.custom_fields = {'currency': 'MXN'}
        self.assertEqual(resolve_capi_currency(lead_unconv), 'MXN')
