# ============================================================================
#  Bop Social — Backend Email & Notification Localization Tests (BS-2.6F.1)
# ============================================================================
"""
Tests verifying bilingual email and notification rendering, locale resolution
precedence, security token/URL preservation, user-content integrity, branding
eradication (no 'Social Stats'), and strict non-raising delivery without SMTP calls.
"""
import uuid
from django.core import mail
from django.contrib.auth.models import User
from django.test import TestCase

from social_stats.models import (
    Client, UserProfile, ClientInvitation, Agency, AgencyMembership,
    AgencyClientRelation, AgencyInviteFromUser, ManageRequest, ApprovalRequest,
    Notification,
)
from social_stats.locale_helpers import (
    resolve_user_language, get_email_copy, get_notification_copy,
)
from social_stats.auth_views import (
    _send_verification_email, _send_reset_email, _send_client_joined_email,
)
from social_stats.invitation_views import _send_invitation_email
from social_stats.agency_invite_views import _send_invite_email
from social_stats.manage_request_views import _send_manage_request_email
from social_stats.profile_views import (
    send_invitation_accepted_email,
    _send_account_deleted_email_to_agency,
    _send_disconnect_email_to_agency,
)
from social_stats.security.login_monitor import notify_new_login
from social_stats.security.privacy_tasks import _email_export_link
from social_stats.notification_dispatcher import dispatch
from social_stats.events.handlers.notifications import _create_notification


class BackendEmailNotificationI18nTests(TestCase):
    def setUp(self):
        mail.outbox = []
        # Workspace clients
        self.client_en = Client.objects.create(
            name='Acme Global', company='Acme Global',
            email='contact@acme.com', default_language='en',
        )
        self.client_es = Client.objects.create(
            name='Soluciones Sol', company='Soluciones Sol',
            email='contacto@sol.es', default_language='es',
        )
        self.client_none = Client.objects.create(
            name='Neutral Workspace', company='Neutral Workspace',
            email='neutral@example.com', default_language=None,
        )

        # Users
        self.user_es_explicit = self._create_user('es_user', explicit_lang='es', client=self.client_en)
        self.user_en_explicit = self._create_user('en_user', explicit_lang='en', client=self.client_es)
        self.user_es_tenant = self._create_user('es_tenant_user', explicit_lang=None, client=self.client_es)
        self.user_en_tenant = self._create_user('en_tenant_user', explicit_lang=None, client=self.client_en)
        self.user_neutral = self._create_user('neutral_user', explicit_lang=None, client=self.client_none)

        # Agency setup
        self.agency_user = self._create_user('agency_owner', explicit_lang='es', client=self.client_es)
        self.agency = Agency.objects.create(
            name='Agencia Creativa',
            slug='agencia-creativa',
            owner_user=self.agency_user,
        )
        AgencyMembership.objects.create(
            agency=self.agency, user=self.agency_user, role='owner', is_active=True,
        )

    def _create_user(self, prefix, explicit_lang=None, client=None):
        uid = uuid.uuid4().hex[:6]
        user = User.objects.create_user(
            username=f'{prefix}_{uid}',
            email=f'{prefix}_{uid}@example.com',
            password='ValidPassword123!',
            first_name=f'First_{prefix}',
            last_name='Last',
            is_active=True,
        )
        UserProfile.objects.create(
            user=user,
            role='client',
            client=client,
            language=explicit_lang,
        )
        return user

    # ── 1. Locale Resolution Precedence ───────────────────────────────────────
    def test_locale_resolution_precedence(self):
        """User preference overrides workspace default; workspace default applies when user unset; falls back to 'en'."""
        # 1. User explicit 'es' overrides client 'en'
        self.assertEqual(resolve_user_language(self.user_es_explicit, self.client_en), 'es')
        # 2. User explicit 'en' overrides client 'es'
        self.assertEqual(resolve_user_language(self.user_en_explicit, self.client_es), 'en')
        # 3. User unset inherits client 'es'
        self.assertEqual(resolve_user_language(self.user_es_tenant, self.client_es), 'es')
        # 4. User unset inherits client 'en'
        self.assertEqual(resolve_user_language(self.user_en_tenant, self.client_en), 'en')
        # 5. Fallback to English when both unset
        self.assertEqual(resolve_user_language(self.user_neutral, self.client_none), 'en')
        self.assertEqual(resolve_user_language(None, None), 'en')

    # ── 2. Verification & Reset Emails ────────────────────────────────────────
    def test_verification_email_bilingual_and_branding(self):
        """Verification email renders subject/body in EN/ES with Bop Social branding and no Social Stats."""
        mail.outbox = []
        token = 'tok-verify-123'
        _send_verification_email(self.user_es_tenant, token)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, 'Verifica tu cuenta de Bop Social')
        self.assertIn('Verifica tu correo electrónico', msg.alternatives[0][0])
        self.assertIn('Bop Social', msg.alternatives[0][0])
        self.assertNotIn('Social Stats', msg.alternatives[0][0])
        self.assertNotIn('SocialStats', msg.alternatives[0][0])
        self.assertIn(token, msg.body)

        mail.outbox = []
        _send_verification_email(self.user_en_tenant, token)
        self.assertEqual(len(mail.outbox), 1)
        msg_en = mail.outbox[0]
        self.assertEqual(msg_en.subject, 'Verify your Bop Social account')
        self.assertIn('Verify your email', msg_en.alternatives[0][0])
        self.assertIn('Bop Social', msg_en.alternatives[0][0])
        self.assertNotIn('Social Stats', msg_en.alternatives[0][0])
        self.assertIn(token, msg_en.body)

    def test_reset_email_bilingual_and_branding(self):
        """Password reset email renders in EN/ES with Bop Social branding."""
        mail.outbox = []
        token = 'tok-reset-456'
        _send_reset_email(self.user_es_tenant, token)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, 'Restablece tu contraseña de Bop Social')
        self.assertIn('Restablece tu contraseña', msg.alternatives[0][0])
        self.assertIn('Bop Social', msg.alternatives[0][0])
        self.assertNotIn('Social Stats', msg.alternatives[0][0])
        self.assertIn(token, msg.body)

        mail.outbox = []
        _send_reset_email(self.user_en_tenant, token)
        self.assertEqual(len(mail.outbox), 1)
        msg_en = mail.outbox[0]
        self.assertEqual(msg_en.subject, 'Reset your Bop Social password')
        self.assertIn('Reset your password', msg_en.alternatives[0][0])
        self.assertIn('Bop Social', msg_en.alternatives[0][0])
        self.assertNotIn('Social Stats', msg_en.alternatives[0][0])
        self.assertIn(token, msg_en.body)

    # ── 3. Client Joined Notification ─────────────────────────────────────────
    def test_client_joined_email_bilingual(self):
        """Agency receives localized client joined notification."""
        mail.outbox = []
        _send_client_joined_email(self.agency_user, self.user_neutral)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        # agency_user has language='es'
        self.assertIn('se unió a Bop Social', msg.subject)
        self.assertIn('¡Tu cliente se ha unido a Bop Social!', msg.alternatives[0][0])
        self.assertNotIn('Social Stats', msg.alternatives[0][0])
        self.assertNotIn('SocialStats', msg.alternatives[0][0])

    # ── 4. Agency Invitation Email ────────────────────────────────────────────
    def test_agency_invitation_email_existing_and_new_user(self):
        """Invitation email renders localized subject/body and preserves tokens."""
        # 1. Existing user invited (Spanish)
        inv_es = ClientInvitation.objects.create(
            invited_by=self.agency_user,
            client_email=self.user_es_explicit.email,
            client_user=self.user_es_explicit,
            client_record=self.client_es,
            message='Mensaje personalizado del cliente 123',
        )
        mail.outbox = []
        _send_invitation_email(inv_es, self.user_es_explicit)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn('quiere gestionar tu cuenta de Bop Social', msg.subject)
        self.assertIn('Aceptar Invitación', msg.alternatives[0][0])
        self.assertIn(str(inv_es.token), msg.body)
        self.assertIn('Mensaje personalizado del cliente 123', msg.body)
        self.assertNotIn('Social Stats', msg.alternatives[0][0])

        # 2. New user invited (English fallback)
        inv_en = ClientInvitation.objects.create(
            invited_by=self.agency_user,
            client_email='newclient@example.com',
            client_user=None,
            client_record=self.client_en,
            message='Welcome note!',
        )
        mail.outbox = []
        _send_invitation_email(inv_en, None)
        self.assertEqual(len(mail.outbox), 1)
        msg_en = mail.outbox[0]
        self.assertIn("You've been invited to Bop Social", msg_en.subject)
        self.assertIn('Create Your Account', msg_en.alternatives[0][0])
        self.assertIn(str(inv_en.token), msg_en.body)
        self.assertIn('Welcome note!', msg_en.body)
        self.assertNotIn('Social Stats', msg_en.alternatives[0][0])

    # ── 5. End-User Agency Invite & Manage Request Emails ──────────────────────
    def test_agency_invite_and_manage_request_emails(self):
        """Agency invite and manage request emails render localized and branded Bop Social."""
        # 1. Agency invite
        inv = AgencyInviteFromUser.objects.create(
            inviter_user=self.user_es_explicit,
            client=self.client_es,
            target_agency=self.agency,
            proposed_permissions={'publish': True, 'analytics': True},
            message='Por favor gestiona nuestras redes',
        )
        mail.outbox = []
        _send_invite_email(inv)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn('desea que gestiones sus redes en Bop Social', msg.subject)
        self.assertIn('Solicitud de gestión de cuenta', msg.alternatives[0][0])
        self.assertIn('Por favor gestiona nuestras redes', msg.body)
        self.assertNotIn('Social Stats', msg.alternatives[0][0])
        self.assertNotIn('SocialStats', msg.alternatives[0][0])

        # 2. Manage request
        req = ManageRequest.objects.create(
            agency=self.agency,
            target_email=self.user_es_explicit.email,
            target_user=self.user_es_explicit,
            target_client=self.client_es,
            proposed_permissions={'publish': True},
            proposed_message='Queremos ayudarte con tus campañas',
        )
        mail.outbox = []
        _send_manage_request_email(req)
        self.assertEqual(len(mail.outbox), 1)
        msg_req = mail.outbox[0]
        self.assertIn('desea gestionar tus redes sociales en Bop Social', msg_req.subject)
        self.assertIn('Invitación para gestionar cuenta', msg_req.alternatives[0][0])
        self.assertIn('Queremos ayudarte con tus campañas', msg_req.body)
        self.assertNotIn('Social Stats', msg_req.alternatives[0][0])
        self.assertNotIn('SocialStats', msg_req.alternatives[0][0])

    # ── 6. Profile & Relationship Emails ──────────────────────────────────────
    def test_profile_relationship_emails(self):
        """Connected, account deleted, and disconnect emails render bilingual with Bop Social branding."""
        # 1. Connected
        mail.outbox = []
        send_invitation_accepted_email(self.user_es_explicit, 'Agencia Creativa', 'agencia@example.com')
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn('Ya estás conectado con Agencia Creativa en Bop Social', msg.subject)
        self.assertIn('¡Ya estás conectado!', msg.alternatives[0][0])
        self.assertIn('Bop Social', msg.alternatives[0][0])
        self.assertNotIn('Social Stats', msg.alternatives[0][0])
        self.assertNotIn('SocialStats.ai', msg.alternatives[0][0])

        # 2. Account deleted
        mail.outbox = []
        _send_account_deleted_email_to_agency(self.agency_user, 'Agencia Creativa', 'Cliente Prueba', 'cli@example.com', 'Ya no lo necesito')
        self.assertEqual(len(mail.outbox), 1)
        msg_del = mail.outbox[0]
        self.assertIn('eliminó su cuenta de Bop Social', msg_del.subject)
        self.assertIn('Un cliente eliminó su cuenta', msg_del.alternatives[0][0])
        self.assertIn('Ya no lo necesito', msg_del.body)
        self.assertNotIn('Social Stats', msg_del.alternatives[0][0])

        # 3. Disconnected
        mail.outbox = []
        _send_disconnect_email_to_agency(self.agency_user, 'Agencia Creativa', 'Cliente Prueba', 'cli@example.com')
        self.assertEqual(len(mail.outbox), 1)
        msg_disc = mail.outbox[0]
        self.assertIn('se ha desconectado de tu agencia', msg_disc.subject)
        self.assertIn('Un cliente se ha desconectado', msg_disc.alternatives[0][0])
        self.assertNotIn('Social Stats', msg_disc.alternatives[0][0])

    # ── 7. Security Alerts & Data Export ──────────────────────────────────────
    def test_security_login_and_data_export(self):
        """Login alert and GDPR data export render localized in plain text with Bop Social branding."""
        # 1. Login alert
        mail.outbox = []
        ctx = {'ip': '192.168.1.100', 'browser': 'Chrome', 'os': 'Windows', 'device': 'Desktop'}
        notify_new_login(user=self.user_es_explicit, context=ctx)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn('[Bop Social] Nuevo inicio de sesión en tu cuenta', msg.subject)
        self.assertIn('Hemos detectado un nuevo inicio de sesión en tu cuenta de Bop Social', msg.body)
        self.assertIn('192.168.1.100', msg.body)
        self.assertNotIn('Social Stats', msg.body)
        self.assertNotIn('SocialStats', msg.body)

        # 2. Data export
        mail.outbox = []
        req_mock = type('Req', (), {'download_token': uuid.uuid4(), 'archive_size_bytes': 1048576})()
        _email_export_link(self.user_es_explicit, req_mock, {'files': ['posts.json', 'metrics.csv']})
        self.assertEqual(len(mail.outbox), 1)
        msg_exp = mail.outbox[0]
        self.assertIn('[Bop Social] Tu exportación de datos está lista', msg_exp.subject)
        self.assertIn('Tu exportación de datos personales de Bop Social está lista', msg_exp.body)
        self.assertIn('posts.json', msg_exp.body)
        self.assertNotIn('Social Stats', msg_exp.body)

    # ── 8. In-App Notification Localized Creation ─────────────────────────────
    def test_in_app_notification_creation_localized(self):
        """In-app notifications render in recipient language while preserving canonical event codes."""
        # 1. Event notification in Spanish
        note_es = _create_notification(
            user=self.user_es_explicit,
            client=self.client_es,
            title='Post published on instagram, facebook',
            body='Contenido del post publicado #marketing',
            data={'event_type': 'post.published', 'post_id': 101, 'link': '/admin/composer/101'},
        )
        self.assertIsNotNone(note_es)
        self.assertIn('Publicación realizada en instagram, facebook', note_es.title)
        self.assertEqual(note_es.data.get('event_type'), 'post_published')
        self.assertEqual(note_es.data.get('bus_event_type'), 'post.published')
        self.assertEqual(note_es.data.get('post_id'), 101)

        # 2. Event notification in English
        note_en = _create_notification(
            user=self.user_en_explicit,
            client=self.client_en,
            title='Post published on instagram, facebook',
            body='Published post content #marketing',
            data={'event_type': 'post.published', 'post_id': 102, 'link': '/admin/composer/102'},
        )
        self.assertIsNotNone(note_en)
        self.assertEqual(note_en.title, 'Post published on instagram, facebook')
        self.assertEqual(note_en.data.get('post_id'), 102)

    # ── 9. Tokens and URLs Preservation ───────────────────────────────────────
    def test_token_and_url_preservation_between_en_and_es(self):
        """Security tokens and destination URLs remain identical across languages."""
        token_es = uuid.uuid4().hex
        inv_es = ClientInvitation.objects.create(
            invited_by=self.agency_user,
            client_email='user_es@example.com',
            token=token_es,
        )
        mail.outbox = []
        _send_invitation_email(inv_es, self.user_es_explicit)
        body_es = mail.outbox[0].body
        self.assertIn(token_es, body_es)
        self.assertIn(f'/invitation/{token_es}', body_es)

        token_en = uuid.uuid4().hex
        inv_en = ClientInvitation.objects.create(
            invited_by=self.agency_user,
            client_email='user_en@example.com',
            token=token_en,
        )
        mail.outbox = []
        _send_invitation_email(inv_en, self.user_en_explicit)
        body_en = mail.outbox[0].body
        self.assertIn(token_en, body_en)
        self.assertIn(f'/invitation/{token_en}', body_en)
