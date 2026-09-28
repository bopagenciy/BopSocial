# ============================================================================
#  Social Stats — Phase BS-2.7C: CTWA & Meta Ads Multi-Currency Test Suite
# ============================================================================
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from social_stats.bot_models import BotFlow, CTWACampaign, Lead
from social_stats.bot_serializers import CTWACampaignSerializer
from social_stats.bot_views import CTWACampaignViewSet
from social_stats.currencies import CURRENCY_CHOICES, SUPPORTED_CURRENCIES
from social_stats.meta_ads_views import sync_campaign_spend, fetch_per_ad_insights
from social_stats.meta_capi import push_lead_event, resolve_capi_currency
from social_stats.models import Client, PlatformCredential, UserProfile


class CTWAMetaMultiCurrencyTests(TestCase):
    def setUp(self):
        # Create client with COP currency
        self.client_cop = Client.objects.create(
            name='Bogota Tech',
            company='Bogota Tech SAS',
            email=f'client_{uuid.uuid4().hex[:8]}@example.com',
            currency='COP',
            meta_pixel_id='pixel_cop_123',
        )
        # Create client with USD currency
        self.client_usd = Client.objects.create(
            name='Miami Brands',
            company='Miami Brands LLC',
            email=f'client_{uuid.uuid4().hex[:8]}@example.com',
            currency='USD',
            meta_pixel_id='pixel_usd_456',
        )
        # Create client with EUR currency
        self.client_eur = Client.objects.create(
            name='Madrid Retail',
            company='Madrid Retail SL',
            email=f'client_{uuid.uuid4().hex[:8]}@example.com',
            currency='EUR',
            meta_pixel_id='pixel_eur_789',
        )

        # Users and profiles
        self.user_cop = User.objects.create_user(
            username=f'user_cop_{uuid.uuid4().hex[:6]}', password='password123'
        )
        UserProfile.objects.create(
            user=self.user_cop, client=self.client_cop, role='client'
        )

        self.user_usd = User.objects.create_user(
            username=f'user_usd_{uuid.uuid4().hex[:6]}', password='password123'
        )
        UserProfile.objects.create(
            user=self.user_usd, client=self.client_usd, role='client'
        )

        # Flows
        self.flow_cop = BotFlow.objects.create(client=self.client_cop, name='Flow COP')
        self.flow_usd = BotFlow.objects.create(client=self.client_usd, name='Flow USD')
        self.flow_eur = BotFlow.objects.create(client=self.client_eur, name='Flow EUR')

        # Credentials
        PlatformCredential.objects.create(
            client=self.client_cop,
            platform='facebook',
            access_token='fake_fb_token_cop',
            is_active=True,
        )
        PlatformCredential.objects.create(
            client=self.client_usd,
            platform='facebook',
            access_token='fake_fb_token_usd',
            is_active=True,
        )

        self.factory = APIRequestFactory()

    # ── 1. Model & Migration Defaults ──────────────────────────────────────────
    def test_ctwa_campaign_currency_defaults_to_usd_or_client(self):
        camp = CTWACampaign.objects.create(
            client=self.client_cop,
            flow=self.flow_cop,
            name='Default Test Campaign',
            ad_account_id='act_111',
            campaign_id='camp_111',
        )
        # Database column default is 'USD' unless explicitly assigned
        self.assertIn(camp.currency, SUPPORTED_CURRENCIES)
        self.assertEqual(camp.currency, 'USD')

    def test_ctwa_campaign_explicit_currency_persists(self):
        camp = CTWACampaign.objects.create(
            client=self.client_cop,
            flow=self.flow_cop,
            name='COP Campaign',
            ad_account_id='act_222',
            campaign_id='camp_222',
            currency='COP',
        )
        camp.refresh_from_db()
        self.assertEqual(camp.currency, 'COP')

    # ── 2. Serializer Normalization & Validation ──────────────────────────────
    def test_serializer_normalizes_lowercase_currency(self):
        data = {
            'name': 'API Campaign',
            'flow': self.flow_cop.id,
            'ad_account_id': 'act_333',
            'campaign_id': 'camp_333',
            'currency': 'cop',
        }
        serializer = CTWACampaignSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['currency'], 'COP')

    def test_serializer_rejects_invalid_currency(self):
        data = {
            'name': 'Bad Currency Campaign',
            'flow': self.flow_cop.id,
            'ad_account_id': 'act_444',
            'campaign_id': 'camp_444',
            'currency': 'INVALID',
        }
        serializer = CTWACampaignSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('currency', serializer.errors)

    # ── 3. ViewSet Currency Authority Hierarchy ───────────────────────────────
    def test_viewset_create_preserves_meta_account_currency(self):
        view = CTWACampaignViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/ctwa-campaigns/', {
            'name': 'Meta Account EUR Campaign',
            'flow': self.flow_cop.id,
            'ad_account_id': 'act_eur_99',
            'campaign_id': 'camp_eur_99',
            'currency': 'EUR',
        })
        force_authenticate(req, user=self.user_cop)
        resp = view(req)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['currency'], 'EUR')

        camp = CTWACampaign.objects.get(id=resp.data['id'])
        self.assertEqual(camp.currency, 'EUR')

    def test_viewset_create_falls_back_to_client_currency_when_omitted(self):
        view = CTWACampaignViewSet.as_view({'post': 'create'})
        req = self.factory.post('/api/ctwa-campaigns/', {
            'name': 'Omitted Currency Campaign',
            'flow': self.flow_cop.id,
            'ad_account_id': 'act_cop_88',
            'campaign_id': 'camp_cop_88',
        })
        force_authenticate(req, user=self.user_cop)
        resp = view(req)
        self.assertEqual(resp.status_code, 201)
        # Should fallback to client_cop.currency which is 'COP'
        self.assertEqual(resp.data['currency'], 'COP')

    # ── 4. Client Currency Change Does NOT Alter Historical Campaigns ──────────
    def test_client_currency_change_does_not_rewrite_historical_campaign(self):
        camp = CTWACampaign.objects.create(
            client=self.client_cop,
            flow=self.flow_cop,
            name='Historical COP Campaign',
            ad_account_id='act_cop_hist',
            campaign_id='camp_cop_hist',
            currency='COP',
        )
        # Mutate client workspace currency
        self.client_cop.currency = 'EUR'
        self.client_cop.save()

        camp.refresh_from_db()
        # Campaign currency must remain strictly 'COP'
        self.assertEqual(camp.currency, 'COP')

    # ── 5. Analytics Endpoint Currency Metadata ───────────────────────────────
    def test_analytics_endpoint_includes_campaign_currency(self):
        camp = CTWACampaign.objects.create(
            client=self.client_cop,
            flow=self.flow_cop,
            name='Analytics Test Camp',
            ad_account_id='act_cop_analytics',
            campaign_id='camp_cop_analytics',
            currency='COP',
            total_spent=Decimal('250000.00'),
            total_leads=10,
        )
        view = CTWACampaignViewSet.as_view({'get': 'analytics'})
        req = self.factory.get(f'/api/ctwa-campaigns/{camp.id}/analytics/')
        force_authenticate(req, user=self.user_cop)
        resp = view(req, pk=camp.id)

        self.assertEqual(resp.status_code, 200)
        self.assertIn('totals', resp.data)
        self.assertEqual(resp.data['totals']['currency'], 'COP')
        self.assertEqual(resp.data['totals']['spent'], 250000.0)
        self.assertEqual(resp.data['totals']['cpl'], 25000.0)

    # ── 6. Spend Sync & Per-Ad Insights Currency ──────────────────────────────
    @patch('social_stats.meta_ads_views._graph')
    def test_sync_campaign_spend_preserves_currency_and_raw_numeric(self, mock_graph):
        mock_graph.return_value = (True, {
            'data': [{'spend': '450.75', 'clicks': '35'}]
        })
        camp = CTWACampaign.objects.create(
            client=self.client_cop,
            flow=self.flow_cop,
            name='Sync Test Camp',
            ad_account_id='act_cop_sync',
            campaign_id='camp_cop_sync',
            currency='COP',
        )

        res = sync_campaign_spend(camp)
        self.assertTrue(res['ok'])
        self.assertEqual(res['currency'], 'COP')
        self.assertEqual(res['total_spent'], 450.75)
        self.assertEqual(res['total_clicks'], 35)

        camp.refresh_from_db()
        self.assertEqual(camp.total_spent, Decimal('450.75'))
        self.assertEqual(camp.currency, 'COP')

    @patch('social_stats.meta_ads_views._graph')
    def test_fetch_per_ad_insights_includes_currency(self, mock_graph):
        mock_graph.return_value = (True, {
            'data': [
                {'ad_id': 'ad_1', 'ad_name': 'Ad One', 'spend': '100.00', 'clicks': '10', 'ctr': '2.5', 'cpc': '10.0'},
                {'ad_id': 'ad_2', 'ad_name': 'Ad Two', 'spend': '200.00', 'clicks': '20', 'ctr': '3.0', 'cpc': '10.0'},
            ]
        })
        camp = CTWACampaign.objects.create(
            client=self.client_usd,
            flow=self.flow_usd,
            name='Per Ad USD Camp',
            ad_account_id='act_usd_ads',
            campaign_id='camp_usd_ads',
            currency='USD',
        )

        res = fetch_per_ad_insights(camp)
        self.assertTrue(res['ok'])
        self.assertEqual(res['currency'], 'USD')
        self.assertEqual(len(res['ads']), 2)
        for ad in res['ads']:
            self.assertEqual(ad['currency'], 'USD')

    # ── 7. Meta CAPI Multi-Currency Correction ────────────────────────────────
    @patch('social_stats.meta_capi.requests.post')
    def test_meta_capi_currency_cop_campaign(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"events_received": 1, "fbtrace_id": "trace_cop"}'
        mock_resp.json.return_value = {'events_received': 1, 'fbtrace_id': 'trace_cop'}
        mock_post.return_value = mock_resp

        # Create campaign with COP
        camp_cop = CTWACampaign.objects.create(
            client=self.client_cop,
            flow=self.flow_cop,
            name='CAPI COP Camp',
            ad_account_id='act_capi_cop',
            campaign_id='123456789_cop',
            currency='COP',
        )

        # Create contact and lead
        from social_stats.models import WhatsAppContact
        contact = WhatsAppContact.objects.create(
            client=self.client_cop, phone='+573001234567', name='Juan Perez'
        )
        lead = Lead.objects.create(
            client=self.client_cop,
            contact=contact,
            phone='+573001234567',
            email='juan@example.com',
            source_campaign_id='123456789_cop',
            conversion_value=Decimal('500000.00'),
        )

        res = push_lead_event(lead)
        self.assertTrue(res['sent'])

        # Verify posted CAPI payload
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs['json']
        event = payload['data'][0]
        custom_data = event['custom_data']

        self.assertEqual(custom_data['currency'], 'COP')
        self.assertEqual(custom_data['value'], 500000.00)
        self.assertNotEqual(custom_data['currency'], 'INR')

    @patch('social_stats.meta_capi.requests.post')
    def test_meta_capi_currency_usd_campaign(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"events_received": 1}'
        mock_resp.json.return_value = {'events_received': 1}
        mock_post.return_value = mock_resp

        camp_usd = CTWACampaign.objects.create(
            client=self.client_usd,
            flow=self.flow_usd,
            name='CAPI USD Camp',
            ad_account_id='act_capi_usd',
            campaign_id='987654321_usd',
            currency='USD',
        )

        from social_stats.models import WhatsAppContact
        contact = WhatsAppContact.objects.create(
            client=self.client_usd, phone='+13055551234', name='John Smith'
        )
        lead = Lead.objects.create(
            client=self.client_usd,
            contact=contact,
            phone='+13055551234',
            email='john@example.com',
            source_campaign_id='987654321_usd',
            conversion_value=Decimal('150.00'),
        )

        res = push_lead_event(lead)
        self.assertTrue(res['sent'])

        call_kwargs = mock_post.call_args[1]
        custom_data = call_kwargs['json']['data'][0]['custom_data']
        self.assertEqual(custom_data['currency'], 'USD')
        self.assertEqual(custom_data['value'], 150.00)

    @patch('social_stats.meta_capi.requests.post')
    def test_meta_capi_currency_eur_campaign(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"events_received": 1}'
        mock_resp.json.return_value = {'events_received': 1}
        mock_post.return_value = mock_resp

        # Set credential for client_eur
        PlatformCredential.objects.create(
            client=self.client_eur,
            platform='facebook',
            access_token='fake_fb_token_eur',
            is_active=True,
        )

        camp_eur = CTWACampaign.objects.create(
            client=self.client_eur,
            flow=self.flow_eur,
            name='CAPI EUR Camp',
            ad_account_id='act_capi_eur',
            campaign_id='555555555_eur',
            currency='EUR',
        )

        from social_stats.models import WhatsAppContact
        contact = WhatsAppContact.objects.create(
            client=self.client_eur, phone='+34600123456', name='Carlos Garcia'
        )
        lead = Lead.objects.create(
            client=self.client_eur,
            contact=contact,
            phone='+34600123456',
            email='carlos@example.es',
            source_campaign_id='555555555_eur',
            conversion_value=Decimal('3500.00'),
        )

        res = push_lead_event(lead)
        self.assertTrue(res['sent'])

        call_kwargs = mock_post.call_args[1]
        custom_data = call_kwargs['json']['data'][0]['custom_data']
        self.assertEqual(custom_data['currency'], 'EUR')
        self.assertEqual(custom_data['value'], 3500.00)

    def test_meta_capi_currency_resolution_hierarchy(self):
        # 1. Fallback to client currency when no campaign exists
        lead_no_camp = MagicMock()
        lead_no_camp.source_campaign_id = None
        lead_no_camp.custom_fields = {}
        lead_no_camp.client = self.client_cop
        self.assertEqual(resolve_capi_currency(lead_no_camp), 'COP')

        # 2. Explicit lead currency in custom_fields overrides client
        lead_custom = MagicMock()
        lead_custom.source_campaign_id = None
        lead_custom.custom_fields = {'currency': 'MXN'}
        lead_custom.client = self.client_cop
        self.assertEqual(resolve_capi_currency(lead_custom), 'MXN')

        # 3. Fallback to USD when client has no currency
        lead_no_client = MagicMock()
        lead_no_client.source_campaign_id = None
        lead_no_client.custom_fields = {}
        lead_no_client.client = None
        self.assertEqual(resolve_capi_currency(lead_no_client), 'USD')

    # ── 8. Tenant Isolation ───────────────────────────────────────────────────
    def test_tenant_isolation_ctwa_campaigns(self):
        camp_cop = CTWACampaign.objects.create(
            client=self.client_cop,
            flow=self.flow_cop,
            name='COP Tenant Camp',
            ad_account_id='act_cop_iso',
            campaign_id='camp_cop_iso',
            currency='COP',
        )
        camp_usd = CTWACampaign.objects.create(
            client=self.client_usd,
            flow=self.flow_usd,
            name='USD Tenant Camp',
            ad_account_id='act_usd_iso',
            campaign_id='camp_usd_iso',
            currency='USD',
        )

        view = CTWACampaignViewSet.as_view({'get': 'list'})

        # Request as user_cop
        req_cop = self.factory.get('/api/ctwa-campaigns/')
        force_authenticate(req_cop, user=self.user_cop)
        resp_cop = view(req_cop)
        cop_ids = [c['id'] for c in resp_cop.data.get('results', resp_cop.data)]
        self.assertIn(camp_cop.id, cop_ids)
        self.assertNotIn(camp_usd.id, cop_ids)

        # Request as user_usd
        req_usd = self.factory.get('/api/ctwa-campaigns/')
        force_authenticate(req_usd, user=self.user_usd)
        resp_usd = view(req_usd)
        usd_ids = [c['id'] for c in resp_usd.data.get('results', resp_usd.data)]
        self.assertIn(camp_usd.id, usd_ids)
        self.assertNotIn(camp_cop.id, usd_ids)
