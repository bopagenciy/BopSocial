# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Author    : Chandrabhan Shekhawat
#  Company   : Gigai Kripa Services
#  Website   : https://gigaikripaservices.com/
#  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
#  Released under the MIT License — see LICENSE. Keep this notice.
# ============================================================================
"""
Tests for Meta OAuth Capability-Aware Scopes & Scope Persistence (Phase BS-3C.4)
===============================================================================

Validates:
1. Facebook-only OAuth requests exact Facebook scopes.
2. Instagram scopes do NOT appear in facebook_page capability.
3. Scope persistence stores real Meta grants in PlatformCredential.scope.
4. Missing required scopes (pages_manage_posts) are detected and fail safely.
5. Existing credential updates preserve strict tenant isolation.
6. Tokens and secrets are never leaked in logs or response payloads.
7. Callback creates and updates PlatformCredential correctly.
"""
import logging
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse, parse_qs

from django.test import TestCase
from django.test import Client as HttpClient
from django.contrib.auth.models import User
from django.conf import settings

from social_stats.models import Client, PlatformCredential, UserProfile
from social_stats.meta_capabilities import (
    META_OAUTH_CAPABILITIES,
    DEFAULT_META_CAPABILITY,
    get_capability_scopes,
    get_capability_scope_string,
    validate_capability_scopes,
    normalize_scopes,
    parse_scopes,
    fetch_meta_granted_scopes,
)


class MetaOAuthCapabilitiesTests(TestCase):
    def setUp(self):
        self.http = HttpClient()
        self.user = User.objects.create_user(
            username='meta.pilot@bopagencia.local',
            email='meta.pilot@bopagencia.local',
            password='Password123!Secure',
        )
        self.client_a = Client.objects.create(
            name='Bop Agencia Pilot',
            company='Bop Agencia',
            email='pilot@bopagencia.local',
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='superadmin',
            client=self.client_a,
        )

    # ── Test 1: Facebook-only OAuth requests exact Facebook scopes ──────────
    def test_facebook_only_oauth_requests_exact_facebook_scopes(self):
        """Facebook-only OAuth must request exactly the baseline Facebook scopes in dialog URL."""
        res = self.http.get(f'/api/oauth/facebook/start/{self.client_a.id}/')
        self.assertEqual(res.status_code, 302)

        redirect_url = res['Location']
        parsed = urlparse(redirect_url)
        params = parse_qs(parsed.query)

        self.assertIn('scope', params)
        requested_scopes = params['scope'][0].split(',')

        expected_facebook_scopes = [
            'pages_show_list',
            'pages_read_engagement',
            'pages_manage_metadata',
            'pages_manage_posts',
            'read_insights',
        ]
        self.assertEqual(requested_scopes, expected_facebook_scopes)

    # ── Test 2: Instagram scopes NO aparecen en facebook_page ───────────────
    def test_instagram_scopes_not_in_facebook_page(self):
        """Instagram scopes must never appear in facebook_page capability or default flow."""
        fb_scopes = get_capability_scopes('facebook_page')
        ig_exclusive = [
            'instagram_basic',
            'instagram_content_publishing',
            'instagram_content_publish',
            'instagram_manage_insights',
        ]
        for ig_scope in ig_exclusive:
            self.assertNotIn(ig_scope, fb_scopes)

        # Verify decoupled instagram_professional capability exists separately
        self.assertIn('instagram_professional', META_OAUTH_CAPABILITIES)
        ig_scopes = get_capability_scopes('instagram_professional')
        self.assertIn('instagram_basic', ig_scopes)
        self.assertIn('instagram_content_publishing', ig_scopes)
        self.assertNotIn('instagram_content_publish', ig_scopes)
        self.assertIn('pages_show_list', ig_scopes)
        self.assertIn('business_management', ig_scopes)
        self.assertIn('instagram_manage_insights', ig_scopes)
        self.assertIn('pages_read_engagement', ig_scopes)

    # ── Test 3: Scope persistence guarda grants reales ──────────────────────
    def test_scope_persistence_saves_real_meta_grants(self):
        """Callback must persist real granted scopes into PlatformCredential.scope."""
        # 1. Start OAuth to set state in session
        start_res = self.http.get(f'/api/oauth/facebook/start/{self.client_a.id}/')
        self.assertEqual(start_res.status_code, 302)
        state = self.http.session['oauth_state']

        # 2. Mock Graph API responses
        mock_short_resp = MagicMock()
        mock_short_resp.status_code = 200
        mock_short_resp.json.return_value = {'access_token': 'short_token_xyz'}

        mock_long_resp = MagicMock()
        mock_long_resp.status_code = 200
        mock_long_resp.json.return_value = {
            'access_token': 'long_token_abc',
            'expires_in': 5184000,
        }

        mock_accounts_resp = MagicMock()
        mock_accounts_resp.status_code = 200
        mock_accounts_resp.json.return_value = {
            'data': [{
                'id': '657647337668646',
                'name': 'Bo Projects',
                'access_token': 'page_token_bo_projects',
            }]
        }

        mock_debug_resp = MagicMock()
        mock_debug_resp.status_code = 200
        mock_debug_resp.json.return_value = {
            'data': {
                'scopes': [
                    'pages_show_list',
                    'pages_read_engagement',
                    'pages_manage_metadata',
                    'pages_manage_posts',
                    'read_insights',
                ],
                'granular_scopes': [{
                    'scope': 'pages_manage_posts',
                    'target_ids': ['657647337668646'],
                }],
            }
        }

        mock_perms_resp = MagicMock()
        mock_perms_resp.status_code = 200
        mock_perms_resp.json.return_value = {
            'data': [
                {'permission': 'pages_show_list', 'status': 'granted'},
                {'permission': 'pages_read_engagement', 'status': 'granted'},
                {'permission': 'pages_manage_metadata', 'status': 'granted'},
                {'permission': 'pages_manage_posts', 'status': 'granted'},
                {'permission': 'read_insights', 'status': 'granted'},
            ]
        }

        def mock_get(url, *args, **kwargs):
            if 'oauth/access_token' in url:
                params = kwargs.get('params', {})
                if params.get('grant_type') == 'fb_exchange_token':
                    return mock_long_resp
                return mock_short_resp
            if 'me/accounts' in url:
                return mock_accounts_resp
            if 'debug_token' in url:
                return mock_debug_resp
            if 'me/permissions' in url:
                return mock_perms_resp
            return MagicMock(status_code=404, json=lambda: {})

        with patch('social_stats.oauth_views.requests.get', side_effect=mock_get), \
             patch('social_stats.meta_capabilities.requests.get', side_effect=mock_get):
            cb_res = self.http.get(f'/api/oauth/facebook/callback/?code=test_code_123&state={state}')

        self.assertEqual(cb_res.status_code, 302)
        self.assertIn('connected=facebook', cb_res['Location'])

        cred = PlatformCredential.objects.get(client=self.client_a, platform='facebook')
        self.assertEqual(cred.page_id, '657647337668646')
        self.assertEqual(cred.page_name, 'Bo Projects')
        self.assertTrue(cred.is_active)
        self.assertEqual(cred.auth_method, 'oauth')

        # Verify real scope persistence
        expected_persisted = 'pages_manage_metadata,pages_manage_posts,pages_read_engagement,pages_show_list,read_insights'
        self.assertEqual(cred.scope, expected_persisted)
        self.assertTrue(cred.has_scope('pages_manage_posts'))
        self.assertTrue(cred.has_scope('pages_show_list'))
        self.assertFalse(cred.has_scope('instagram_basic'))
        self.assertEqual(len(cred.get_scopes()), 5)

    # ── Test 4: Missing pages_manage_posts se detecta ────────────────────────
    def test_missing_pages_manage_posts_detected(self):
        """Missing pages_manage_posts must be flagged by validator and fail connect flow."""
        # 1. Test validator directly
        insufficient_grants = ['pages_show_list', 'pages_read_engagement', 'read_insights']
        val = validate_capability_scopes('facebook_page', insufficient_grants)
        self.assertFalse(val['is_valid'])
        self.assertIn('pages_manage_posts', val['missing_required_scopes'])

        # 2. Test callback flow with missing required scope
        start_res = self.http.get(f'/api/oauth/facebook/start/{self.client_a.id}/')
        state = self.http.session['oauth_state']

        mock_short_resp = MagicMock(status_code=200, json=lambda: {'access_token': 'short_tok'})
        mock_long_resp = MagicMock(status_code=200, json=lambda: {'access_token': 'long_tok', 'expires_in': 3600})
        mock_accounts_resp = MagicMock(status_code=200, json=lambda: {'data': [{'id': '101', 'name': 'P', 'access_token': 'pt'}]})
        mock_perms_resp = MagicMock(status_code=200, json=lambda: {'data': [
            {'permission': 'pages_show_list', 'status': 'granted'},
            {'permission': 'pages_read_engagement', 'status': 'granted'},
            # pages_manage_posts is missing/declined
        ]})

        def mock_get(url, *args, **kwargs):
            if 'oauth/access_token' in url:
                params = kwargs.get('params', {})
                if params.get('grant_type') == 'fb_exchange_token':
                    return mock_long_resp
                return mock_short_resp
            if 'me/accounts' in url:
                return mock_accounts_resp
            if 'me/permissions' in url:
                return mock_perms_resp
            if 'debug_token' in url:
                return MagicMock(status_code=200, json=lambda: {'data': {'scopes': ['pages_show_list', 'pages_read_engagement']}})
            return MagicMock(status_code=404, json=lambda: {})

        with patch('social_stats.oauth_views.requests.get', side_effect=mock_get), \
             patch('social_stats.meta_capabilities.requests.get', side_effect=mock_get):
            cb_res = self.http.get(f'/api/oauth/facebook/callback/?code=test_code_456&state={state}')

        self.assertEqual(cb_res.status_code, 302)
        self.assertIn('error=facebook_missing_permissions', cb_res['Location'])

        # Ensure no credential created with missing required scopes
        self.assertFalse(PlatformCredential.objects.filter(client=self.client_a, platform='facebook').exists())

    # ── Test 5: Existing credential update preserva tenant isolation ─────────
    def test_existing_credential_update_preserves_tenant_isolation(self):
        """Updating client A's credential must never leak or overwrite client B's credential."""
        client_b = Client.objects.create(
            name='Other Client B',
            company='Client B Inc',
            email='clientb@other.local',
        )

        cred_b = PlatformCredential.objects.create(
            client=client_b,
            platform='facebook',
            page_id='999888777',
            page_name='Client B Page',
            access_token='token_b_existing',
            scope='pages_show_list',
            is_active=True,
            auth_method='oauth',
        )

        # Connect client A
        start_res = self.http.get(f'/api/oauth/facebook/start/{self.client_a.id}/')
        state = self.http.session['oauth_state']

        mock_short_resp = MagicMock(status_code=200, json=lambda: {'access_token': 'short_a'})
        mock_long_resp = MagicMock(status_code=200, json=lambda: {'access_token': 'long_a', 'expires_in': 3600})
        mock_accounts_resp = MagicMock(status_code=200, json=lambda: {'data': [{'id': '111222', 'name': 'Client A Page', 'access_token': 'page_a'}]})
        mock_perms_resp = MagicMock(status_code=200, json=lambda: {'data': [
            {'permission': 'pages_show_list', 'status': 'granted'},
            {'permission': 'pages_manage_posts', 'status': 'granted'},
        ]})

        def mock_get(url, *args, **kwargs):
            if 'oauth/access_token' in url:
                params = kwargs.get('params', {})
                if params.get('grant_type') == 'fb_exchange_token':
                    return mock_long_resp
                return mock_short_resp
            if 'me/accounts' in url:
                return mock_accounts_resp
            if 'me/permissions' in url:
                return mock_perms_resp
            return MagicMock(status_code=404, json=lambda: {})

        with patch('social_stats.oauth_views.requests.get', side_effect=mock_get), \
             patch('social_stats.meta_capabilities.requests.get', side_effect=mock_get):
            cb_res = self.http.get(f'/api/oauth/facebook/callback/?code=code_a&state={state}')

        self.assertEqual(cb_res.status_code, 302)

        # Verify Client A created
        cred_a = PlatformCredential.objects.get(client=self.client_a, platform='facebook')
        self.assertEqual(cred_a.page_id, '111222')
        self.assertEqual(cred_a.page_name, 'Client A Page')

        # Verify Client B is totally untouched
        cred_b_after = PlatformCredential.objects.get(id=cred_b.id)
        self.assertEqual(cred_b_after.client_id, client_b.id)
        self.assertEqual(cred_b_after.page_id, '999888777')
        self.assertEqual(cred_b_after.page_name, 'Client B Page')
        self.assertEqual(cred_b_after.scope, 'pages_show_list')

    # ── Test 6: Token/secret nunca aparece en logs/responses ─────────────────
    def test_token_and_secret_never_appear_in_logs_or_responses(self):
        """Tokens and app secrets must never appear in log output or debug endpoint responses."""
        secret_token = 'SUPER_SECRET_TOKEN_DO_NOT_LOG_98765'
        secret_key = 'VERY_SECRET_APP_SECRET_43210'

        # 1. Test oauth_debug endpoint (must not reveal secret value or prefix)
        from rest_framework.test import APIClient
        api = APIClient()
        api.force_authenticate(user=self.user)
        with patch.object(settings, 'META_APP_SECRET', secret_key):
            debug_res = api.get('/api/oauth/debug/')
            self.assertEqual(debug_res.status_code, 200)
            data = debug_res.json()
            self.assertNotIn(secret_key, str(data))
            self.assertNotIn(secret_key[:6], str(data))
            self.assertTrue(data.get('meta_app_secret_set'))

        # 2. Test logging safety during start and callback error
        logger_name = 'social_stats.oauth_views'
        with self.assertLogs(logger=logger_name, level='INFO') as log_capture:
            # Start
            self.http.get(f'/api/oauth/facebook/start/{self.client_a.id}/')
            state = self.http.session['oauth_state']

            # Callback with simulated error containing token-like payload
            with patch('social_stats.oauth_views.requests.get') as mock_get:
                mock_get.return_value.status_code = 400
                mock_get.return_value.json.return_value = {
                    'error': {'type': 'OAuthException', 'code': 190, 'error_subcode': 460}
                }
                self.http.get(f'/api/oauth/facebook/callback/?code=AUTH_CODE_SECRET_ABC&state={state}')

            all_logs = ' '.join(log_capture.output)
            self.assertNotIn('AUTH_CODE_SECRET_ABC', all_logs)
            self.assertNotIn(secret_token, all_logs)
            self.assertNotIn(secret_key, all_logs)

    # ── Test 7: Callback sigue creando/actualizando PlatformCredential correctamente ─
    def test_callback_creates_and_updates_platform_credential_correctly(self):
        """Callback handles initial creation and subsequent update preserving auth_method='oauth'."""
        # 1. Initial creation
        self.http.get(f'/api/oauth/facebook/start/{self.client_a.id}/')
        state1 = self.http.session['oauth_state']

        mock_get_v1 = MagicMock()
        mock_get_v1.side_effect = lambda url, *args, **kwargs: MagicMock(
            status_code=200,
            json=lambda: (
                {'access_token': 'short_1'} if 'oauth/access_token' in url and 'fb_exchange_token' not in kwargs.get('params', {})
                else {'access_token': 'long_1', 'expires_in': 5184000} if 'oauth/access_token' in url
                else {'data': [{'id': 'page_100', 'name': 'First Version', 'access_token': 'page_tok_1'}]} if 'me/accounts' in url
                else {'data': [{'permission': 'pages_show_list', 'status': 'granted'}, {'permission': 'pages_manage_posts', 'status': 'granted'}]} if 'me/permissions' in url
                else {'data': {'scopes': ['pages_show_list', 'pages_manage_posts']}}
            )
        )

        with patch('social_stats.oauth_views.requests.get', mock_get_v1), \
             patch('social_stats.meta_capabilities.requests.get', mock_get_v1):
            res1 = self.http.get(f'/api/oauth/facebook/callback/?code=c1&state={state1}')
        self.assertEqual(res1.status_code, 302)

        cred = PlatformCredential.objects.get(client=self.client_a, platform='facebook')
        self.assertEqual(cred.page_id, 'page_100')
        self.assertEqual(cred.page_name, 'First Version')
        self.assertEqual(cred.auth_method, 'oauth')
        self.assertTrue(cred.is_active)
        self.assertEqual(cred.scope, 'pages_manage_posts,pages_show_list')

        # 2. Subsequent update
        self.http.get(f'/api/oauth/facebook/start/{self.client_a.id}/')
        state2 = self.http.session['oauth_state']

        mock_get_v2 = MagicMock()
        mock_get_v2.side_effect = lambda url, *args, **kwargs: MagicMock(
            status_code=200,
            json=lambda: (
                {'access_token': 'short_2'} if 'oauth/access_token' in url and 'fb_exchange_token' not in kwargs.get('params', {})
                else {'access_token': 'long_2', 'expires_in': 5184000} if 'oauth/access_token' in url
                else {'data': [{'id': 'page_100', 'name': 'Updated Name', 'access_token': 'page_tok_2'}]} if 'me/accounts' in url
                else {'data': [
                    {'permission': 'pages_show_list', 'status': 'granted'},
                    {'permission': 'pages_manage_posts', 'status': 'granted'},
                    {'permission': 'read_insights', 'status': 'granted'},
                ]} if 'me/permissions' in url
                else {'data': {'scopes': ['pages_show_list', 'pages_manage_posts', 'read_insights']}}
            )
        )

        with patch('social_stats.oauth_views.requests.get', mock_get_v2), \
             patch('social_stats.meta_capabilities.requests.get', mock_get_v2):
            res2 = self.http.get(f'/api/oauth/facebook/callback/?code=c2&state={state2}')
        self.assertEqual(res2.status_code, 302)

        cred.refresh_from_db()
        self.assertEqual(cred.page_id, 'page_100')
        self.assertEqual(cred.page_name, 'Updated Name')
        self.assertEqual(cred.scope, 'pages_manage_posts,pages_show_list,read_insights')
        self.assertEqual(PlatformCredential.objects.filter(client=self.client_a, platform='facebook').count(), 1)

    # ── Additional: Instagram decoupled in facebook_page capability ──────────
    def test_instagram_not_connected_in_facebook_only_capability(self):
        """Even if Facebook page returns a linked IG account, facebook_page capability must not connect it."""
        self.http.get(f'/api/oauth/facebook/start/{self.client_a.id}/')
        state = self.http.session['oauth_state']

        mock_get = MagicMock()
        mock_get.side_effect = lambda url, *args, **kwargs: MagicMock(
            status_code=200,
            json=lambda: (
                {'access_token': 'short'} if 'oauth/access_token' in url and 'fb_exchange_token' not in kwargs.get('params', {})
                else {'access_token': 'long', 'expires_in': 3600} if 'oauth/access_token' in url
                else {'data': [{'id': 'page_999', 'name': 'Page With IG', 'access_token': 'tok'}]} if 'me/accounts' in url
                else {'instagram_business_account': {'id': 'ig_account_555'}} if 'page_999' in url
                else {'data': [{'permission': 'pages_show_list', 'status': 'granted'}, {'permission': 'pages_manage_posts', 'status': 'granted'}]} if 'me/permissions' in url
                else {'data': {'scopes': ['pages_show_list', 'pages_manage_posts']}}
            )
        )

        with patch('social_stats.oauth_views.requests.get', mock_get), \
             patch('social_stats.meta_capabilities.requests.get', mock_get):
            res = self.http.get(f'/api/oauth/facebook/callback/?code=c_ig&state={state}')

        self.assertEqual(res.status_code, 302)
        self.assertIn('connected=facebook', res['Location'])
        self.assertNotIn('instagram', res['Location'])
        self.assertTrue(PlatformCredential.objects.filter(client=self.client_a, platform='facebook').exists())
        self.assertFalse(PlatformCredential.objects.filter(client=self.client_a, platform='instagram').exists())

    # ── Unit tests for helpers in meta_capabilities.py ───────────────────────
    def test_normalize_and_parse_scopes(self):
        """Scope normalization must trim, lowercase, deduplicate, and sort."""
        self.assertEqual(normalize_scopes(''), '')
        self.assertEqual(normalize_scopes([]), '')
        self.assertEqual(
            normalize_scopes(' pages_manage_posts , pages_show_list, pages_manage_posts '),
            'pages_manage_posts,pages_show_list'
        )
        self.assertEqual(
            normalize_scopes(['READ_INSIGHTS', 'pages_show_list', 'read_insights']),
            'pages_show_list,read_insights'
        )
        self.assertEqual(
            parse_scopes('pages_show_list,pages_manage_posts'),
            ['pages_manage_posts', 'pages_show_list']
        )

    def test_validate_capability_scopes_unknown_capability_fallback(self):
        """Unknown capability must safely fall back to default capability."""
        val = validate_capability_scopes(
            'unknown_future_cap',
            ['pages_show_list', 'pages_manage_posts', 'read_insights']
        )
        self.assertTrue(val['is_valid'])
        self.assertEqual(val['capability'], DEFAULT_META_CAPABILITY)
        self.assertEqual(val['missing_required_scopes'], [])

    def test_fetch_meta_granted_scopes_debug_token_priority(self):
        """fetch_meta_granted_scopes must read from debug_token if available."""
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            'data': {
                'scopes': ['pages_show_list', 'pages_manage_posts'],
                'granular_scopes': [{'scope': 'pages_read_engagement'}],
            }
        }
        with patch('social_stats.meta_capabilities.requests.get', return_value=mock_resp):
            scopes = fetch_meta_granted_scopes(
                user_token='user_tok',
                page_token='page_tok',
                app_id='app_id',
                app_secret='app_sec',
            )
        self.assertEqual(scopes, ['pages_manage_posts', 'pages_read_engagement', 'pages_show_list'])

    def test_fetch_meta_granted_scopes_permissions_fallback(self):
        """fetch_meta_granted_scopes must fall back to /me/permissions when debug_token is unavailable."""
        mock_perms_resp = MagicMock(status_code=200)
        mock_perms_resp.json.return_value = {
            'data': [
                {'permission': 'pages_show_list', 'status': 'granted'},
                {'permission': 'pages_manage_posts', 'status': 'granted'},
                {'permission': 'pages_read_engagement', 'status': 'declined'},
            ]
        }
        # debug_token returns 400, /me/permissions returns 200
        def side_effect(url, *args, **kwargs):
            if 'debug_token' in url:
                return MagicMock(status_code=400, json=lambda: {'error': 'unsupported'})
            return mock_perms_resp

        with patch('social_stats.meta_capabilities.requests.get', side_effect=side_effect):
            scopes = fetch_meta_granted_scopes(
                user_token='user_tok',
                app_id='app_id',
                app_secret='app_sec',
            )
        self.assertEqual(scopes, ['pages_manage_posts', 'pages_show_list'])

    # ── Unit tests for modern Instagram scopes and alias validation ──────────
    def test_instagram_modern_scope_set_requests(self):
        """instagram_professional must request modern instagram_content_publishing and business_management."""
        ig_scopes = get_capability_scopes('instagram_professional')
        self.assertIn('instagram_basic', ig_scopes)
        self.assertIn('instagram_content_publishing', ig_scopes)
        self.assertNotIn('instagram_content_publish', ig_scopes)
        self.assertIn('pages_show_list', ig_scopes)
        self.assertIn('business_management', ig_scopes)
        self.assertIn('instagram_manage_insights', ig_scopes)
        self.assertIn('pages_read_engagement', ig_scopes)

    def test_instagram_validation_modern_grant_pass(self):
        """Modern grant set with instagram_content_publishing must validate PASS."""
        granted = [
            'instagram_basic',
            'instagram_content_publishing',
            'pages_show_list',
            'business_management',
        ]
        res = validate_capability_scopes('instagram_professional', granted)
        self.assertTrue(res['is_valid'])
        self.assertEqual(res['missing_required_scopes'], [])

    def test_instagram_validation_legacy_grant_pass_via_alias(self):
        """Legacy grant set with instagram_content_publish must validate PASS via alias equivalence."""
        granted = [
            'instagram_basic',
            'instagram_content_publish',
            'pages_show_list',
            'business_management',
        ]
        res = validate_capability_scopes('instagram_professional', granted)
        self.assertTrue(res['is_valid'])
        self.assertEqual(res['missing_required_scopes'], [])

    def test_instagram_validation_missing_publish_fails(self):
        """Absence of both publish scopes must validate FAIL."""
        granted = [
            'instagram_basic',
            'pages_show_list',
            'business_management',
        ]
        res = validate_capability_scopes('instagram_professional', granted)
        self.assertFalse(res['is_valid'])
        self.assertIn('instagram_content_publishing', res['missing_required_scopes'])

    def test_instagram_validation_missing_business_management_fails(self):
        """Absence of business_management must validate FAIL."""
        granted = [
            'instagram_basic',
            'instagram_content_publishing',
            'pages_show_list',
        ]
        res = validate_capability_scopes('instagram_professional', granted)
        self.assertFalse(res['is_valid'])
        self.assertIn('business_management', res['missing_required_scopes'])

    def test_instagram_validation_missing_pages_show_list_fails(self):
        """Absence of pages_show_list must validate FAIL."""
        granted = [
            'instagram_basic',
            'instagram_content_publishing',
            'business_management',
        ]
        res = validate_capability_scopes('instagram_professional', granted)
        self.assertFalse(res['is_valid'])
        self.assertIn('pages_show_list', res['missing_required_scopes'])

    def test_instagram_validation_missing_basic_fails(self):
        """Absence of instagram_basic must validate FAIL."""
        granted = [
            'instagram_content_publishing',
            'pages_show_list',
            'business_management',
        ]
        res = validate_capability_scopes('instagram_professional', granted)
        self.assertFalse(res['is_valid'])
        self.assertIn('instagram_basic', res['missing_required_scopes'])

    def test_scope_persistence_preserves_real_grant_without_replacement(self):
        """Real Meta grants must be stored without replacing them with aliases."""
        val_modern = validate_capability_scopes(
            'instagram_professional',
            ['instagram_basic', 'instagram_content_publishing', 'pages_show_list', 'business_management']
        )
        self.assertIn('instagram_content_publishing', val_modern['granted_scopes'])
        self.assertNotIn('instagram_content_publish', val_modern['granted_scopes'])
        self.assertEqual(
            normalize_scopes(val_modern['granted_scopes']),
            'business_management,instagram_basic,instagram_content_publishing,pages_show_list'
        )

        val_legacy = validate_capability_scopes(
            'instagram_professional',
            ['instagram_basic', 'instagram_content_publish', 'pages_show_list', 'business_management']
        )
        self.assertIn('instagram_content_publish', val_legacy['granted_scopes'])
        self.assertNotIn('instagram_content_publishing', val_legacy['granted_scopes'])
        self.assertEqual(
            normalize_scopes(val_legacy['granted_scopes']),
            'business_management,instagram_basic,instagram_content_publish,pages_show_list'
        )

