from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from social_stats.models import UserProfile


class LoginDiagnosisTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = 'SuperSecretPass123!'
        self.superadmin = User.objects.create_user(
            username='bopsoluciones@gmail.com',
            email='bopsoluciones@gmail.com',
            password=self.password,
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        self.profile = UserProfile.objects.create(
            user=self.superadmin,
            role='superadmin',
            account_type='legacy',
            terms_accepted=False,
        )

    def test_login_success_with_exact_credentials(self):
        resp = self.client.post(
            '/api/auth/login/',
            {
                'username': 'bopsoluciones@gmail.com',
                'password': self.password,
                'terms_accepted': True,
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

        # Profile terms should be updated
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.terms_accepted)

    def test_login_success_with_case_insensitivity_and_whitespace(self):
        resp = self.client.post(
            '/api/auth/login/',
            {
                'username': '  BopSoluciones@Gmail.Com  ',
                'password': self.password,
                'terms_accepted': True,
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.data)

    def test_login_success_with_email_field(self):
        resp = self.client.post(
            '/api/auth/login/',
            {
                'email': 'bopsoluciones@gmail.com',
                'password': self.password,
                'terms_accepted': True,
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.data)

    def test_login_rejected_with_invalid_password(self):
        resp = self.client.post(
            '/api/auth/login/',
            {
                'username': 'bopsoluciones@gmail.com',
                'password': 'WrongPassword123!',
                'terms_accepted': True,
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(resp.status_code, 401)
        self.assertIn('detail', resp.data)

    def test_login_rejected_without_terms(self):
        resp = self.client.post(
            '/api/auth/login/',
            {
                'username': 'bopsoluciones@gmail.com',
                'password': self.password,
                'terms_accepted': False,
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('terms', resp.data.get('detail', '').lower())

    def test_login_rejected_when_inactive(self):
        self.superadmin.is_active = False
        self.superadmin.save(update_fields=['is_active'])

        resp = self.client.post(
            '/api/auth/login/',
            {
                'username': 'bopsoluciones@gmail.com',
                'password': self.password,
                'terms_accepted': True,
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(resp.status_code, 401)

    def test_axes_records_login_failure_on_invalid_credentials(self):
        from axes.models import AccessAttempt
        AccessAttempt.objects.filter(username='bopsoluciones@gmail.com').delete()

        resp = self.client.post(
            '/api/auth/login/',
            {
                'username': '  BopSoluciones@Gmail.Com  ',
                'password': 'BadPassword123!',
                'terms_accepted': True,
            },
            format='json',
            HTTP_HOST='localhost',
        )
        self.assertEqual(resp.status_code, 401)
        self.assertTrue(
            AccessAttempt.objects.filter(username='bopsoluciones@gmail.com').exists()
        )
