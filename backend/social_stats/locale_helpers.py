# ============================================================================
#  Bop Social — Backend Internationalization & Email Localization Helpers
# ============================================================================
"""
Unified backend locale resolution and bilingual (EN / ES) copy generation
for transactional emails, security alerts, and system notifications.

Invariants:
  - Hierarchy: User preference -> Client/Workspace default -> English fallback ('en').
  - Branding: 'Bop Social' (never 'Social Stats').
  - Tokens, URLs, IDs, customer-authored content, and machine-readable event codes
    are strictly preserved without translation.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def resolve_user_language(user: Any = None, client: Any = None) -> str:
    """
    Resolve the effective language ('en' or 'es') for a notification/email recipient.

    Hierarchy:
      1. User's explicit language preference: user.profile.language
      2. Explicit workspace/client default language: client.default_language
      3. User's assigned workspace default language: user.profile.client.default_language
      4. Fallback: 'en'
    """
    if user is not None:
        profile = getattr(user, 'profile', None)
        if profile is not None:
            user_lang = getattr(profile, 'language', None)
            if user_lang in ('en', 'es'):
                return user_lang

    if client is not None:
        client_lang = getattr(client, 'default_language', None)
        if client_lang in ('en', 'es'):
            return client_lang

    if user is not None:
        profile = getattr(user, 'profile', None)
        if profile is not None:
            user_client = getattr(profile, 'client', None)
            if user_client is not None:
                client_lang = getattr(user_client, 'default_language', None)
                if client_lang in ('en', 'es'):
                    return client_lang

    return 'en'


# ── Bilingual Copy Dictionaries ──────────────────────────────────────────────

EMAIL_COPY = {
    'client_joined': {
        'en': {
            'subject': '{client_name} joined Bop Social — send a dashboard access request',
            'title': 'Your client joined Bop Social! 🎉',
            'greeting': 'Hi <strong style="color:#0f172a;">{agency_name}</strong>, great news! <strong style="color:#0f172a;">{client_name}</strong> ({client_email}) has just verified their email and joined Bop Social.',
            'badge': 'Client Joined',
            'body': 'You can now go to your Clients page and send them a dashboard access request to connect their account to your agency.',
            'cta_label': 'Go to Clients Page',
            'expiry_note': 'The client will need to accept your access request to connect their account to your agency.',
            'plain': 'Hi {agency_name},\n\n{client_name} ({client_email}) has joined Bop Social!\n\nYou can now send them a dashboard access request from your Clients page:\n{frontend_url}/admin/clients\n',
        },
        'es': {
            'subject': '{client_name} se unió a Bop Social — envía una solicitud de acceso al panel',
            'title': '¡Tu cliente se ha unido a Bop Social! 🎉',
            'greeting': 'Hola <strong style="color:#0f172a;">{agency_name}</strong>, ¡excelentes noticias! <strong style="color:#0f172a;">{client_name}</strong> ({client_email}) acaba de verificar su correo y se ha unido a Bop Social.',
            'badge': 'Cliente Registrado',
            'body': 'Ahora puedes ir a tu página de Clientes y enviarles una solicitud de acceso al panel para conectar su cuenta con tu agencia.',
            'cta_label': 'Ir a la Página de Clientes',
            'expiry_note': 'El cliente deberá aceptar tu solicitud de acceso para conectar su cuenta con tu agencia.',
            'plain': 'Hola {agency_name},\n\n{client_name} ({client_email}) se ha unido a Bop Social!\n\nAhora puedes enviarle una solicitud de acceso al panel desde tu página de Clientes:\n{frontend_url}/admin/clients\n',
        },
    },

    'invitation_existing_user': {
        'en': {
            'subject': '{agency_name} wants to manage your Bop Social account',
            'title': 'You have a new invitation',
            'greeting': 'Hi <strong style="color:#0f172a;">{client_name}</strong>, <strong style="color:#0f172a;">{agency_name}</strong> has invited you to let them manage your social media analytics on Bop Social.',
            'msg_box_title': 'Message from {agency_name}',
            'cta_label': 'Accept Invitation',
            'expiry_note': '&#9203; This invitation expires in <strong>7 days</strong>. If you did not expect this, you can safely ignore this email.',
            'plain': 'Hi {client_name},\n\n{agency_name} has invited you to let them manage your social media analytics on Bop Social.\n\nMessage: {message}\n\nAccept or reject here: {link}\n\nThis invitation expires in 7 days.\n',
        },
        'es': {
            'subject': '{agency_name} quiere gestionar tu cuenta de Bop Social',
            'title': 'Tienes una nueva invitación',
            'greeting': 'Hola <strong style="color:#0f172a;">{client_name}</strong>, <strong style="color:#0f172a;">{agency_name}</strong> te ha invitado para gestionar tus analíticas de redes sociales en Bop Social.',
            'msg_box_title': 'Mensaje de {agency_name}',
            'cta_label': 'Aceptar Invitación',
            'expiry_note': '&#9203; Esta invitación expira en <strong>7 días</strong>. Si no esperabas este correo, puedes ignorarlo con seguridad.',
            'plain': 'Hola {client_name},\n\n{agency_name} te ha invitado para gestionar tus analíticas de redes sociales en Bop Social.\n\nMensaje: {message}\n\nAcepta o rechaza aquí: {link}\n\nEsta invitación expira en 7 días.\n',
        },
    },

    'invitation_new_user': {
        'en': {
            'subject': "You've been invited to Bop Social by {agency_name}",
            'title': 'You have a new invitation',
            'greeting': '<strong style="color:#0f172a;">{agency_name}</strong> has invited you to join <strong style="color:#0f172a;">Bop Social</strong> — the social media analytics and management platform.',
            'msg_box_title': 'Message from {agency_name}',
            'body_text': 'Click the button below to create your account and connect with {agency_name}.',
            'cta_label': 'Create Your Account',
            'expiry_note': '&#9203; This invitation expires in <strong>7 days</strong>. If you did not expect this, you can safely ignore this email.',
            'plain': 'Hi,\n\n{agency_name} has invited you to join Bop Social for social media analytics.\n\nMessage: {message}\n\nSign up here: {link}\n\nThis invitation expires in 7 days.\n',
        },
        'es': {
            'subject': 'Has sido invitado a Bop Social por {agency_name}',
            'title': 'Tienes una nueva invitación',
            'greeting': '<strong style="color:#0f172a;">{agency_name}</strong> te ha invitado a unirte a <strong style="color:#0f172a;">Bop Social</strong> — la plataforma de analítica y gestión de redes sociales.',
            'msg_box_title': 'Mensaje de {agency_name}',
            'body_text': 'Haz clic en el botón a continuación para crear tu cuenta y conectarte con {agency_name}.',
            'cta_label': 'Crear tu Cuenta',
            'expiry_note': '&#9203; Esta invitación expira en <strong>7 días</strong>. Si no esperabas este correo, puedes ignorarlo con seguridad.',
            'plain': 'Hola,\n\n{agency_name} te ha invitado a unirte a Bop Social para la gestión de redes sociales.\n\nMensaje: {message}\n\nRegístrate aquí: {link}\n\nEsta invitación expira en 7 días.\n',
        },
    },

    'agency_invite': {
        'en': {
            'subject': '{inviter_name} ({company_name}) wants you to manage their social on Bop Social',
            'title': 'Manage-account request',
            'greeting': '<strong style="color:#0f172a;">{inviter_name}</strong> from <strong style="color:#0f172a;">{company_name}</strong> would like your agency to manage their social media on Bop Social.',
            'msg_label': 'Message',
            'proposed_access_label': 'Proposed access:',
            'cta_label': 'Review the request',
            'expiry_note': '&#9203; This invitation expires in <strong>7 days</strong>.',
            'plain': '{inviter_name} from {company_name} would like your agency to manage their social on Bop Social.\n\nMessage: {message}\n\nReview and respond: {link}\n\nThis invitation expires in 7 days.\n',
        },
        'es': {
            'subject': '{inviter_name} ({company_name}) desea que gestiones sus redes en Bop Social',
            'title': 'Solicitud de gestión de cuenta',
            'greeting': '<strong style="color:#0f172a;">{inviter_name}</strong> de <strong style="color:#0f172a;">{company_name}</strong> desea que tu agencia gestione sus redes sociales en Bop Social.',
            'msg_label': 'Mensaje',
            'proposed_access_label': 'Permisos propuestos:',
            'cta_label': 'Revisar la solicitud',
            'expiry_note': '&#9203; Esta invitación expira en <strong>7 días</strong>.',
            'plain': '{inviter_name} de {company_name} desea que tu agencia gestione sus redes en Bop Social.\n\nMensaje: {message}\n\nRevisar y responder: {link}\n\nEsta invitación expira en 7 días.\n',
        },
    },

    'manage_request': {
        'en': {
            'subject': '{agency_name} wants to manage your social media on Bop Social',
            'title': 'Manage-account invitation',
            'greeting': '<strong style="color:#0f172a;">{agency_name}</strong> would like to help manage your social media accounts on Bop Social. You stay in control — you can pause or terminate at any time.',
            'msg_label': 'Message from {agency_name}',
            'what_asking': "What they're asking to do:",
            'cta_label': 'Review the invitation',
            'expiry_note': '&#9203; This invitation expires in <strong>7 days</strong>.',
            'plain': '{agency_name} would like to manage your social media accounts on Bop Social.\n\nMessage: {message}\n\nReview and respond: {link}\n\nThis invitation expires in 7 days. You can pause or terminate at any time after accepting.\n',
        },
        'es': {
            'subject': '{agency_name} desea gestionar tus redes sociales en Bop Social',
            'title': 'Invitación para gestionar cuenta',
            'greeting': '<strong style="color:#0f172a;">{agency_name}</strong> desea ayudarte a gestionar tus cuentas de redes sociales en Bop Social. Tú mantienes el control — puedes pausar o terminar la relación en cualquier momento.',
            'msg_label': 'Mensaje de {agency_name}',
            'what_asking': 'Permisos solicitados:',
            'cta_label': 'Revisar la invitación',
            'expiry_note': '&#9203; Esta invitación expira en <strong>7 días</strong>.',
            'plain': '{agency_name} desea gestionar tus cuentas de redes sociales en Bop Social.\n\nMensaje: {message}\n\nRevisar y responder: {link}\n\nEsta invitación expira en 7 días. Puedes pausar o terminar la relación en cualquier momento tras aceptar.\n',
        },
    },

    'connected_client': {
        'en': {
            'subject': "You're now connected to {agency_name} on Bop Social",
            'title': "You're connected!",
            'greeting': 'Hi <strong style="color:#0f172a;">{name}</strong>, your account is now connected to <strong style="color:#0f172a;">{agency_name}</strong> on Bop Social. They can now manage your analytics and reports.',
            'badge': 'Connected Agency',
            'cta_label': 'Go to Dashboard',
            'note': 'You can disconnect from your agency at any time from your Account Settings.',
            'plain': 'Hi {name},\n\nYour Bop Social account is now connected to {agency_name} ({agency_email}).\n\nGo to your dashboard: {frontend_url}/dashboard',
        },
        'es': {
            'subject': 'Ya estás conectado con {agency_name} en Bop Social',
            'title': '¡Ya estás conectado!',
            'greeting': 'Hola <strong style="color:#0f172a;">{name}</strong>, tu cuenta ahora está conectada con <strong style="color:#0f172a;">{agency_name}</strong> en Bop Social. Ahora pueden gestionar tus analíticas e informes.',
            'badge': 'Agencia Conectada',
            'cta_label': 'Ir al Panel de Control',
            'note': 'Puedes desconectar tu agencia en cualquier momento desde la Configuración de tu Cuenta.',
            'plain': 'Hola {name},\n\nTu cuenta de Bop Social ahora está conectada con {agency_name} ({agency_email}).\n\nVe a tu panel de control: {frontend_url}/dashboard',
        },
    },

    'account_deleted': {
        'en': {
            'subject': '{client_name} deleted their Bop Social account',
            'title': 'A client deleted their account',
            'greeting': 'Hi <strong style="color:#0f172a;">{name}</strong>, we\'re letting you know that a client has permanently deleted their Bop Social account.',
            'badge': 'Account Deleted',
            'reason_label': 'Reason:',
            'body': 'Their account and all associated data have been permanently removed from Bop Social. You can no longer access their analytics or reports.',
            'cta_label': 'View Clients',
            'note': 'This action is permanent and cannot be undone.',
            'plain': 'Hi {name},\n\n{client_name} ({client_email}) has permanently deleted their Bop Social account.\n\nReason: {reason}\n\nAll their data has been removed.',
        },
        'es': {
            'subject': '{client_name} eliminó su cuenta de Bop Social',
            'title': 'Un cliente eliminó su cuenta',
            'greeting': 'Hola <strong style="color:#0f172a;">{name}</strong>, te informamos que un cliente ha eliminado permanentemente su cuenta de Bop Social.',
            'badge': 'Cuenta Eliminada',
            'reason_label': 'Motivo:',
            'body': 'Su cuenta y todos los datos asociados han sido eliminados permanentemente de Bop Social. Ya no puedes acceder a sus analíticas o informes.',
            'cta_label': 'Ver Clientes',
            'note': 'Esta acción es permanente y no se puede deshacer.',
            'plain': 'Hola {name},\n\n{client_name} ({client_email}) ha eliminado permanentemente su cuenta de Bop Social.\n\nMotivo: {reason}\n\nTodos sus datos han sido eliminados.',
        },
    },

    'disconnected_client': {
        'en': {
            'subject': '{client_name} has disconnected from your agency',
            'title': 'A client has disconnected',
            'greeting': 'Hi <strong style="color:#0f172a;">{name}</strong>, we\'re letting you know that a client has removed your agency\'s access to their Bop Social account.',
            'badge': 'Client Disconnected',
            'body': 'Their data and connected accounts are no longer accessible to your agency. You can send them a new invitation if needed.',
            'cta_label': 'View Clients',
            'note': 'If you believe this was a mistake, you can reach out to the client directly and send a new invitation from your dashboard.',
            'plain': 'Hi {name},\n\n{client_name} ({client_email}) has disconnected from your agency on Bop Social.\n\nYou can send them a new invitation from your dashboard: {frontend_url}/admin/clients',
        },
        'es': {
            'subject': '{client_name} se ha desconectado de tu agencia',
            'title': 'Un cliente se ha desconectado',
            'greeting': 'Hola <strong style="color:#0f172a;">{name}</strong>, te informamos que un cliente ha revocado el acceso de tu agencia a su cuenta de Bop Social.',
            'badge': 'Cliente Desconectado',
            'body': 'Sus datos y cuentas conectadas ya no están accesibles para tu agencia. Puedes enviarle una nueva invitación si es necesario.',
            'cta_label': 'Ver Clientes',
            'note': 'Si crees que esto fue un error, puedes contactar al cliente directamente y enviarle una nueva invitación desde tu panel.',
            'plain': 'Hola {name},\n\n{client_name} ({client_email}) se ha desconectado de tu agencia en Bop Social.\n\nPuedes enviarle una nueva invitación desde tu panel: {frontend_url}/admin/clients',
        },
    },

    'security_login': {
        'en': {
            'subject': '[Bop Social] New login to your account',
            'body': (
                'Hi {name},\n\n'
                'We detected a new sign-in to your Bop Social account at {when}.\n\n'
                '  IP address : {ip}\n'
                '  Browser    : {browser} on {os}\n'
                '  Device     : {device}\n\n'
                'If this was you, no action needed.\n\n'
                "If you don't recognise this sign-in:\n"
                '  1. Change your password immediately: {frontend}/u/settings/security\n'
                '  2. Review and revoke active sessions on the same page\n'
                '  3. Contact support@bopsocial.com\n\n'
                '— Bop Social Security'
            ),
        },
        'es': {
            'subject': '[Bop Social] Nuevo inicio de sesión en tu cuenta',
            'body': (
                'Hola {name},\n\n'
                'Hemos detectado un nuevo inicio de sesión en tu cuenta de Bop Social el {when}.\n\n'
                '  Dirección IP : {ip}\n'
                '  Navegador    : {browser} en {os}\n'
                '  Dispositivo  : {device}\n\n'
                'Si fuiste tú, no es necesario realizar ninguna acción.\n\n'
                'Si no reconoces este inicio de sesión:\n'
                '  1. Cambia tu contraseña inmediatamente: {frontend}/u/settings/security\n'
                '  2. Revisa y revoca las sesiones activas en la misma página\n'
                '  3. Contacta a support@bopsocial.com\n\n'
                '— Seguridad de Bop Social'
            ),
        },
    },

    'data_export_ready': {
        'en': {
            'subject': '[Bop Social] Your data export is ready',
            'body': (
                'Hi {name},\n\n'
                'Your Bop Social personal-data export is ready. Download link (expires in 7 days):\n\n'
                '  {link}\n\n'
                'Archive size: {size:,} bytes\n'
                'Files: {files}\n\n'
                'If you did not request this export, please contact security@bopsocial.com\n'
            ),
        },
        'es': {
            'subject': '[Bop Social] Tu exportación de datos está lista',
            'body': (
                'Hola {name},\n\n'
                'Tu exportación de datos personales de Bop Social está lista. Enlace de descarga (expira en 7 días):\n\n'
                '  {link}\n\n'
                'Tamaño del archivo: {size:,} bytes\n'
                'Archivos: {files}\n\n'
                'Si no solicitaste esta exportación, por favor contacta a security@bopsocial.com\n'
            ),
        },
    },
}


def get_email_copy(category: str, lang: str = 'en', **kwargs: Any) -> dict[str, str]:
    """Retrieve formatted dictionary of email strings for a category and language."""
    cat_dict = EMAIL_COPY.get(category, {})
    lang_dict = cat_dict.get(lang) or cat_dict.get('en', {})
    result = {}
    for key, val in lang_dict.items():
        if isinstance(val, str):
            try:
                result[key] = val.format(**kwargs)
            except (KeyError, ValueError):
                result[key] = val
        else:
            result[key] = val
    return result


# ── Notification Copy Dictionaries ───────────────────────────────────────────

NOTIFICATION_COPY = {
    'approval_requested': {
        'en': {
            'title': '{agency_name} needs your approval',
            'cta_label': 'Review approval',
        },
        'es': {
            'title': '{agency_name} necesita tu aprobación',
            'cta_label': 'Revisar aprobación',
        },
    },
    'approval_approved': {
        'en': {
            'title': '{company} approved your request',
        },
        'es': {
            'title': '{company} aprobó tu solicitud',
        },
    },
    'approval_rejected': {
        'en': {
            'title': '{company} rejected your request',
        },
        'es': {
            'title': '{company} rechazó tu solicitud',
        },
    },
    'invitation_received': {
        'en': {
            'title': '{agency_name} wants to manage your account',
        },
        'es': {
            'title': '{agency_name} quiere gestionar tu cuenta',
        },
    },
    'invitation_accepted': {
        'en': {
            'title': '{user_name} accepted your invitation',
        },
        'es': {
            'title': '{user_name} aceptó tu invitación',
        },
    },
    'invitation_rejected': {
        'en': {
            'title': '{user_name} rejected your invitation',
        },
        'es': {
            'title': '{user_name} rechazó tu invitación',
        },
    },
    'invitation_cancelled': {
        'en': {
            'title': '{agency_name} cancelled their invitation',
        },
        'es': {
            'title': '{agency_name} canceló su invitación',
        },
    },
    'agency_invite_received': {
        'en': {
            'title': '{user_name} wants you to manage their account',
        },
        'es': {
            'title': '{user_name} desea que gestiones su cuenta',
        },
    },
    'agency_invite_accepted': {
        'en': {
            'title': '{agency_name} accepted your invitation',
            'body': 'They can now manage {company}.',
        },
        'es': {
            'title': '{agency_name} aceptó tu invitación',
            'body': 'Ahora pueden gestionar {company}.',
        },
    },
    'agency_invite_declined': {
        'en': {
            'title': '{agency_name} declined your invitation',
        },
        'es': {
            'title': '{agency_name} rechazó tu invitación',
        },
    },
    'manage_request_received': {
        'en': {
            'title': '{agency_name} wants to manage your account',
        },
        'es': {
            'title': '{agency_name} desea gestionar tu cuenta',
        },
    },
    'manage_request_accepted': {
        'en': {
            'title': '{user_name} accepted your invitation',
            'body': 'You can now manage {company}.',
        },
        'es': {
            'title': '{user_name} aceptó tu invitación',
            'body': 'Ahora puedes gestionar {company}.',
        },
    },
    'manage_request_declined': {
        'en': {
            'title': '{user_name} declined your invitation',
        },
        'es': {
            'title': '{user_name} rechazó tu invitación',
        },
    },
    'manage_request_cancelled': {
        'en': {
            'title': '{agency_name} cancelled their invitation',
        },
        'es': {
            'title': '{agency_name} canceló su invitación',
        },
    },
}


def get_notification_copy(event_type: str, lang: str = 'en', **kwargs: Any) -> dict[str, str]:
    """Retrieve formatted notification dictionary for an event type and language."""
    ev_dict = NOTIFICATION_COPY.get(event_type, {})
    lang_dict = ev_dict.get(lang) or ev_dict.get('en', {})
    result = {}
    for key, val in lang_dict.items():
        if isinstance(val, str):
            try:
                result[key] = val.format(**kwargs)
            except (KeyError, ValueError):
                result[key] = val
        else:
            result[key] = val
    return result


# ── Media Publishing Error Copy ───────────────────────────────────────────────

MEDIA_ERROR_COPY = {
    'public_media_required': {
        'en': 'Public media hosting is required to publish this asset to {platform}. Configure media hosting (AWS S3 or BACKEND_PUBLIC_URL) before publishing.',
        'es': 'Se requiere alojamiento público multimedia para publicar este recurso en {platform}. Configure el almacenamiento de medios (AWS S3 o BACKEND_PUBLIC_URL) antes de publicar.',
    },
    'invalid_media_url': {
        'en': 'The media URL provided for {platform} is not publicly accessible over HTTPS ({reason}).',
        'es': 'La URL del medio proporcionada para {platform} no es accesible públicamente vía HTTPS ({reason}).',
    },
    'unsupported_platform': {
        'en': "Platform '{platform}' is not currently supported for automated publishing. Coming soon.",
        'es': "La plataforma '{platform}' no está admitida actualmente para publicación automática. Próximamente.",
    },
    'provider_unavailable': {
        'en': 'The {platform} publishing service is currently unavailable. Please verify your credentials or try again later.',
        'es': 'El servicio de publicación de {platform} no está disponible actualmente. Verifique sus credenciales o intente nuevamente más tarde.',
    },
    'media_validation_failed': {
        'en': 'Media validation failed for {platform}: {reason}',
        'es': 'Error de validación del archivo multimedia para {platform}: {reason}',
    },
}


def get_media_error_message(error_code: str, platform: str, lang: str = 'en', **kwargs: Any) -> str:
    """Retrieve localized user-facing error message for media/publishing failures."""
    platform_label = {
        'facebook': 'Facebook',
        'instagram': 'Instagram',
        'youtube': 'YouTube',
        'linkedin': 'LinkedIn',
        'google_my_business': 'Google Business Profile',
        'gmb': 'Google Business Profile',
        'tiktok': 'TikTok',
        'twitter': 'X (Twitter)',
        'pinterest': 'Pinterest',
    }.get(platform.lower(), platform.title())

    template_dict = MEDIA_ERROR_COPY.get(error_code, {})
    template = template_dict.get(lang) or template_dict.get('en') or 'Media publishing error for {platform}.'
    try:
        return template.format(platform=platform_label, **kwargs)
    except (KeyError, ValueError):
        return template

