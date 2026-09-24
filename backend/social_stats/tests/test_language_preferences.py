# ============================================================================
#  Bop Social — Internationalization & Preference Precedence Tests
# ============================================================================
import uuid
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from social_stats.models import Client, UserProfile


def _client_factory(name='Client Org', default_lang=None):
    return Client.objects.create(
        name=name,
        company=name,
        email=f'{uuid.uuid4().hex[:8]}@example.com',
        default_language=default_lang,
    )


def _user_factory(client=None, explicit_language=None, role='client'):
    username = f'user_{uuid.uuid4().hex[:8]}'
    email = f'{username}@example.com'
    u = User.objects.create_user(
        username=username,
        email=email,
        password='ValidPassword123!',
        first_name='Test',
        last_name='User',
        is_active=True,
    )
    profile = UserProfile.objects.create(
        user=u,
        role=role,
        client=client,
        language=explicit_language,
    )
    return u, profile


class LanguagePreferencePrecedenceTests(TestCase):
    """
    Tests verifying BS-2.0 / BS-2.1 language preference precedence:
    1. Explicit User Preference ('en' or 'es')
    2. Tenant / Company Default ('en' or 'es')
    3. Unset / None (triggers client-side browser/fallback resolution)
    """

    def setUp(self):
        self.api = APIClient()

    def test_distinguish_unset_from_explicit_preference(self):
        """Newly created and unset profiles have language=None, distinct from explicit 'en'."""
        _, profile_unset = _user_factory(explicit_language=None)
        self.assertIsNone(profile_unset.language)

        _, profile_en = _user_factory(explicit_language='en')
        self.assertEqual(profile_en.language, 'en')

        _, profile_es = _user_factory(explicit_language='es')
        self.assertEqual(profile_es.language, 'es')

    def test_tenant_default_applies_when_user_preference_unset(self):
        """When user preference is None, /api/auth/me/ returns tenant default language."""
        client_spanish = _client_factory('Spanish Workspace', default_lang='es')
        user, _ = _user_factory(client=client_spanish, explicit_language=None)

        self.api.force_authenticate(user=user)
        res = self.api.get('/api/auth/me/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data.get('language'), 'es')
        self.assertEqual(res.data.get('tenant_language'), 'es')
        self.assertIsNone(res.data.get('user_language'))
        self.assertFalse(res.data.get('has_explicit_language'))

    def test_explicit_user_preference_overrides_tenant_default(self):
        """Explicit English user preference overrides Spanish tenant default."""
        client_spanish = _client_factory('Spanish Workspace', default_lang='es')
        user, _ = _user_factory(client=client_spanish, explicit_language='en')

        self.api.force_authenticate(user=user)
        res = self.api.get('/api/auth/me/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data.get('language'), 'en')
        self.assertEqual(res.data.get('user_language'), 'en')
        self.assertEqual(res.data.get('tenant_language'), 'es')
        self.assertTrue(res.data.get('has_explicit_language'))

    def test_explicit_spanish_user_preference_overrides_tenant_english(self):
        """Explicit Spanish user preference overrides English tenant default."""
        client_english = _client_factory('English Workspace', default_lang='en')
        user, _ = _user_factory(client=client_english, explicit_language='es')

        self.api.force_authenticate(user=user)
        res = self.api.get('/api/auth/me/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data.get('language'), 'es')
        self.assertEqual(res.data.get('user_language'), 'es')
        self.assertEqual(res.data.get('tenant_language'), 'en')
        self.assertTrue(res.data.get('has_explicit_language'))

    def test_user_profile_patch_persists_explicit_language(self):
        """PATCH /api/profile/ can set explicit 'es', change to 'en', or clear to None."""
        client = _client_factory('Tenant Org', default_lang='es')
        user, profile = _user_factory(client=client, explicit_language=None)

        self.api.force_authenticate(user=user)

        # 1. Initially effective language is tenant default 'es', but user_language is None
        res1 = self.api.get('/api/profile/')
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.data.get('language'), 'es')
        self.assertIsNone(res1.data.get('user_language'))

        # 2. User explicitly selects 'en'
        patch_res = self.api.patch('/api/profile/', {'first_name': 'Test', 'language': 'en'}, format='json')
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.data.get('language'), 'en')
        self.assertEqual(patch_res.data.get('user_language'), 'en')

        profile.refresh_from_db()
        self.assertEqual(profile.language, 'en')

        # 3. User unsets preference (clears to tenant default)
        patch_res2 = self.api.patch('/api/profile/', {'first_name': 'Test', 'language': ''}, format='json')
        self.assertEqual(patch_res2.status_code, 200)
        self.assertEqual(patch_res2.data.get('language'), 'es')
        self.assertIsNone(patch_res2.data.get('user_language'))

        profile.refresh_from_db()
        self.assertIsNone(profile.language)

    def test_cross_tenant_language_isolation(self):
        """Tenant A default language does not affect Tenant B users."""
        tenant_a = _client_factory('Tenant A', default_lang='es')
        tenant_b = _client_factory('Tenant B', default_lang='en')

        user_a, _ = _user_factory(client=tenant_a, explicit_language=None)
        user_b, _ = _user_factory(client=tenant_b, explicit_language=None)

        self.api.force_authenticate(user=user_a)
        res_a = self.api.get('/api/auth/me/')
        self.assertEqual(res_a.data.get('language'), 'es')

        self.api.force_authenticate(user=user_b)
        res_b = self.api.get('/api/auth/me/')
        self.assertEqual(res_b.data.get('language'), 'en')

    def test_cross_user_language_isolation(self):
        """In the same tenant, User 1 preference does not bleed into User 2."""
        tenant = _client_factory('Shared Tenant', default_lang=None)
        user1, _ = _user_factory(client=tenant, explicit_language='es')
        user2, _ = _user_factory(client=tenant, explicit_language='en')
        user3, _ = _user_factory(client=tenant, explicit_language=None)

        self.api.force_authenticate(user=user1)
        self.assertEqual(self.api.get('/api/auth/me/').data.get('language'), 'es')

        self.api.force_authenticate(user=user2)
        self.assertEqual(self.api.get('/api/auth/me/').data.get('language'), 'en')

        self.api.force_authenticate(user=user3)
        self.assertIsNone(self.api.get('/api/auth/me/').data.get('language'))
