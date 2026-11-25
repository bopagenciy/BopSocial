import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from social_stats.marketplace_models import Agency, AgencyClientRelation, AgencyMembership
from social_stats.models import Client, ClientUserRole, UserProfile


@override_settings(
    AI_CONTENT_PROVIDER='ollama',
    OLLAMA_HOST='http://host.docker.internal:11434',
    OLLAMA_MODEL='qwen3.5:9b',
    ANTHROPIC_API_KEY='',
)
class ComposerOllamaIntegrationTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='agency_owner_10c',
            email='agency_owner_10c@test.local',
            password='Password123!',
        )
        self.agency = Agency.objects.create(
            name='Agency 10C',
            slug='agency-10c',
            owner_user=self.owner,
        )
        AgencyMembership.objects.create(
            agency=self.agency,
            user=self.owner,
            role='owner',
            is_active=True,
        )
        UserProfile.objects.create(
            user=self.owner,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency,
        )
        self.client_obj = Client.objects.create(
            name='Bop Pilot 10C',
            company='Bop Pilot 10C',
            email='pilot10c@test.local',
            brand_description='Agencia digital enfocada en crecimiento.',
            brand_tone='professional',
            target_audience='PYMEs en Latinoamérica',
            default_language='es',
        )
        AgencyClientRelation.objects.create(
            agency=self.agency,
            client=self.client_obj,
            status='active',
            permissions={'draft_posts': True, 'manage_brand_voice': True},
        )

        self.foreign_user = User.objects.create_user(
            username='foreign_10c',
            email='foreign_10c@test.local',
            password='Password123!',
        )
        self.foreign_client = Client.objects.create(
            name='Foreign 10C',
            company='Foreign 10C',
            email='foreign10c@test.local',
        )
        UserProfile.objects.create(
            user=self.foreign_user,
            role='client',
            account_type='end_user',
            client=self.foreign_client,
        )
        ClientUserRole.objects.create(
            user=self.foreign_user,
            client=self.foreign_client,
            role='owner',
        )

        self.api = APIClient()

    def test_v2_compose_uses_ollama_without_anthropic_key(self):
        self.api.force_authenticate(user=self.owner)
        fake_json = json.dumps({
            'variants': [
                {
                    'platform': 'instagram',
                    'content': 'Impulsa tu negocio hoy con estrategias digitales reales.',
                    'hashtags': ['#MarketingDigital', '#BopAgencia'],
                    'suggested_media_type': 'image',
                    'character_count': 56,
                    'score': 90,
                }
            ]
        })
        with patch('social_stats.ai_helpers.generate_text_completion', return_value=fake_json) as mock_gen:
            res = self.api.post(
                '/api/ai/v2/compose/',
                {
                    'client_id': self.client_obj.id,
                    'topic': 'Lanzamiento de campaña digital',
                    'platforms': ['instagram'],
                    'tone': 'professional',
                    'length': 'short',
                    'language': 'Spanish',
                },
                format='json',
                HTTP_X_CLIENT_ID=str(self.client_obj.id),
            )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(len(res.data['variants']), 1)
        self.assertIn('Impulsa tu negocio', res.data['variants'][0]['content'])
        mock_gen.assert_called_once()
        # Verify requested language, tone, length, and topic were included
        sys_arg, prompt_arg = mock_gen.call_args[0]
        self.assertIn('Spanish', sys_arg)
        self.assertIn('TONE: professional', prompt_arg)
        self.assertIn('LENGTH: short', prompt_arg)
        self.assertIn('Lanzamiento de campaña digital', prompt_arg)

    def test_v2_hashtag_research_and_legacy_text_endpoints_use_ollama(self):
        self.api.force_authenticate(user=self.owner)
        fake_hashtags = json.dumps({
            'hashtags': [{'tag': '#BopAgencia', 'tier': 'niche', 'reason': 'Brand'}]
        })
        with patch('social_stats.ai_helpers.generate_text_completion', return_value=fake_hashtags):
            res_hr = self.api.post(
                '/api/ai/v2/hashtag-research/',
                {'client_id': self.client_obj.id, 'content': 'Agencia digital', 'platform': 'instagram'},
                format='json',
                HTTP_X_CLIENT_ID=str(self.client_obj.id),
            )
        self.assertEqual(res_hr.status_code, 200, res_hr.data)

        fake_captions = json.dumps({'captions': ['Texto profesional generado con Ollama.']})
        with patch('social_stats.ai_helpers.generate_text_completion', return_value=fake_captions):
            res_cap = self.api.post(
                '/api/ai/caption/',
                {'client_id': self.client_obj.id, 'topic': 'Servicios digitales', 'platforms': ['instagram']},
                format='json',
                HTTP_X_CLIENT_ID=str(self.client_obj.id),
            )
        self.assertEqual(res_cap.status_code, 200, res_cap.data)

    def test_ollama_failure_does_not_fallback_to_anthropic_and_foreign_client_rejected(self):
        self.api.force_authenticate(user=self.owner)
        from social_stats.ai_helpers import AIProviderError
        with patch('social_stats.ai_helpers.generate_text_completion', side_effect=AIProviderError('Ollama down')):
            res = self.api.post(
                '/api/ai/v2/compose/',
                {'client_id': self.client_obj.id, 'topic': 'Test sin fallback', 'platforms': ['instagram']},
                format='json',
                HTTP_X_CLIENT_ID=str(self.client_obj.id),
            )
        self.assertEqual(res.status_code, 503)

        self.api.force_authenticate(user=self.foreign_user)
        res_foreign = self.api.post(
            '/api/ai/v2/compose/',
            {'client_id': self.client_obj.id, 'topic': 'Acceso indebido', 'platforms': ['instagram']},
            format='json',
        )
        self.assertEqual(res_foreign.status_code, 403)
