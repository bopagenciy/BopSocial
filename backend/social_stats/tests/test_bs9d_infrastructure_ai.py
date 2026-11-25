"""
BOP SOCIAL — PHASE BS-9D
COMMERCIAL INFRASTRUCTURE & DEPLOYMENT READINESS TESTS

Uses mocked Ollama/Anthropic providers and mocked email backend only.
"""
import json
from unittest.mock import patch, MagicMock

import requests as req_lib
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from social_stats.models import Client, UserProfile, ClientInvitation, AIInsight
from social_stats.marketplace_models import Agency, AgencyMembership, AgencyClientRelation, default_relation_permissions
from social_stats.sentiment import classify as classify_sentiment
from social_stats.tasks import generate_ai_insights
from social_stats.invitation_views import _send_invitation_email


class BS9DInfrastructureAITests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.owner = User.objects.create_user(
            username='infra.owner@bs9d.test',
            email='infra.owner@bs9d.test',
            password='TestPassword123!',
        )
        self.agency = Agency.objects.create(
            name='BS9D Agency',
            slug='bs9d-agency',
            owner_user=self.owner,
        )
        UserProfile.objects.create(
            user=self.owner,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency,
        )
        AgencyMembership.objects.create(
            agency=self.agency,
            user=self.owner,
            role='owner',
            is_active=True,
        )
        self.client_ws = Client.objects.create(
            name='BS9D Brand',
            company='BS9D Brand S.A.',
            email='brand@bs9d.test',
            is_active=True,
        )
        AgencyClientRelation.objects.create(
            agency=self.agency,
            client=self.client_ws,
            status='active',
            initiated_by='agency',
            initiated_by_user=self.owner,
            permissions=default_relation_permissions(),
        )

    @override_settings(
        AI_CONTENT_PROVIDER='ollama',
        OLLAMA_HOST='http://mock-ollama:11434',
        OLLAMA_MODEL='qwen3.5:9b',
        ANTHROPIC_API_KEY='',
    )
    @patch('requests.post')
    def test_01_ollama_powers_captions_hashtags_sentiment_and_insights(self, mock_post):
        self.api.force_authenticate(user=self.owner)

        # 1. Captions via mocked Ollama
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'response': json.dumps({'facebook': 'Hello from Ollama!', 'instagram': 'IG caption'})},
        )
        res_cap = self.api.post(
            '/api/ai/caption/',
            {'client_id': self.client_ws.id, 'topic': 'Product launch', 'platforms': ['facebook', 'instagram']},
            format='json',
        )
        self.assertEqual(res_cap.status_code, 200)
        self.assertEqual(res_cap.data['captions']['facebook'], 'Hello from Ollama!')

        # 2. Hashtags via mocked Ollama
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'response': json.dumps({'suggested': ['#launch', '#bopsocial']})},
        )
        res_hash = self.api.post(
            '/api/ai/hashtags/',
            {'client_id': self.client_ws.id, 'niche': 'SaaS', 'post_topic': 'Product launch', 'platform': 'instagram'},
            format='json',
        )
        self.assertEqual(res_hash.status_code, 200)

        # 3. Sentiment via mocked Ollama
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'response': 'positive'},
        )
        self.assertEqual(classify_sentiment('Love this product!'), 'positive')

        # 4. Insights task via mocked Ollama
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'response': 'Great engagement this month.'},
        )
        generate_ai_insights(self.client_ws.id, 11, 2026)
        insight = AIInsight.objects.filter(client=self.client_ws, month=11, year=2026).first()
        self.assertIsNotNone(insight)
        self.assertEqual(insight.content, 'Great engagement this month.')

    @override_settings(
        AI_CONTENT_PROVIDER='ollama',
        OLLAMA_HOST='http://mock-ollama:11434',
        ANTHROPIC_API_KEY='sk-ant-should-never-be-called',
    )
    @patch('requests.post', side_effect=req_lib.Timeout('timed out'))
    def test_02_ollama_timeout_never_falls_back_to_paid_anthropic(self, mock_post):
        self.api.force_authenticate(user=self.owner)
        res = self.api.post(
            '/api/ai/caption/',
            {'client_id': self.client_ws.id, 'topic': 'Timeout check', 'platforms': ['facebook']},
            format='json',
        )
        self.assertEqual(res.status_code, 504)
        mock_post.assert_called_once()

    @override_settings(
        AI_CONTENT_PROVIDER='',
        ANTHROPIC_API_KEY='',
    )
    def test_03_unconfigured_ai_returns_503_and_unknown_sentiment(self):
        self.api.force_authenticate(user=self.owner)
        res = self.api.post(
            '/api/ai/caption/',
            {'client_id': self.client_ws.id, 'topic': 'No provider', 'platforms': ['facebook']},
            format='json',
        )
        self.assertEqual(res.status_code, 503)
        self.assertEqual(classify_sentiment('Hello world'), 'unknown')

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        FRONTEND_URL='https://app.bopsocial.example',
        DEFAULT_FROM_EMAIL='Bop Social <noreply@bopsocial.example>',
    )
    def test_04_transactional_invitation_email_uses_public_frontend_url(self):
        inv = ClientInvitation.objects.create(
            invited_by=self.owner,
            agency=self.agency,
            client_record=self.client_ws,
            client_email='stakeholder@bs9d.test',
            role='approver',
            status='pending',
        )
        sent, err = _send_invitation_email(inv, None)
        self.assertTrue(sent)
        self.assertIsNone(err)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('https://app.bopsocial.example', mail.outbox[0].body)
        self.assertNotIn('password', mail.outbox[0].body.lower().replace('set your password', ''))
