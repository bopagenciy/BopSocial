# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Author    : Chandrabhan Shekhawat
#  Company   : Gigai Kripa Services
#  Website   : https://gigaikripaservices.com/
#  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
#  Released under the MIT License — see LICENSE. Keep this notice.
# ============================================================================
"""
Meta OAuth Capabilities & Scope Negotiation Framework
=====================================================

Central source of truth for Meta OAuth capabilities, requested scopes,
scope normalization, validation, and granted permissions introspection.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, Optional
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Canonical Meta Capabilities ───────────────────────────────────────────────
#
# facebook_page:
#   Requested baseline scopes:
#     - pages_show_list
#     - pages_read_engagement
#     - pages_manage_metadata
#     - pages_manage_posts
#     - read_insights
#   Required for Facebook publishing / management:
#     - pages_manage_posts (critical for automated page publishing)
#     - pages_show_list    (critical for discovering/selecting managed pages)
#   Optional / recommended:
#     - pages_read_engagement
#     - pages_manage_metadata
#     - read_insights
#
# instagram_professional:
#   Decoupled from Facebook-only flow to prevent Meta 'Invalid Scopes' errors
#   in current App Review tier.
#   Uses modern Meta permission naming ('instagram_content_publishing') with
#   backward compatibility for legacy 'instagram_content_publish' grants.
#
META_OAUTH_CAPABILITIES = {
    'facebook_page': {
        'label': 'Facebook Page Publishing & Management',
        'platform': 'facebook',
        'required_scopes': [
            'pages_manage_posts',
            'pages_show_list',
        ],
        'optional_scopes': [
            'pages_read_engagement',
            'pages_manage_metadata',
            'read_insights',
        ],
    },
    'instagram_professional': {
        'label': 'Instagram Professional Publishing & Insights',
        'platform': 'instagram',
        'required_scopes': [
            'instagram_basic',
            'instagram_content_publishing',
            'pages_show_list',
            'business_management',
        ],
        'optional_scopes': [
            'instagram_manage_insights',
            'pages_read_engagement',
        ],
    },
}

DEFAULT_META_CAPABILITY = 'facebook_page'

# Canonical aliases for permission evaluation (canonical -> set of acceptable equivalents)
SCOPE_EQUIVALENCE_ALIASES: dict[str, set[str]] = {
    'instagram_content_publishing': {'instagram_content_publishing', 'instagram_content_publish'},
    'instagram_content_publish': {'instagram_content_publishing', 'instagram_content_publish'},
}
SCOPE_ALIASES = SCOPE_EQUIVALENCE_ALIASES


def get_capability_config(capability: str = DEFAULT_META_CAPABILITY) -> dict:
    """Return configuration dict for given capability, falling back to default."""
    return META_OAUTH_CAPABILITIES.get(capability) or META_OAUTH_CAPABILITIES[DEFAULT_META_CAPABILITY]


def get_capability_scopes(capability: str = DEFAULT_META_CAPABILITY) -> list[str]:
    """
    Return the full ordered list of scopes requested for a capability.
    Maintains clean canonical ordering.
    """
    cfg = get_capability_config(capability)
    # Maintain canonical Facebook ordering if facebook_page
    if capability == 'facebook_page':
        canonical_order = [
            'pages_show_list',
            'pages_read_engagement',
            'pages_manage_metadata',
            'pages_manage_posts',
            'read_insights',
        ]
        all_scopes = set(cfg['required_scopes'] + cfg['optional_scopes'])
        return [s for s in canonical_order if s in all_scopes]

    return cfg['required_scopes'] + cfg['optional_scopes']


def get_capability_scope_string(capability: str = DEFAULT_META_CAPABILITY) -> str:
    """Return comma-separated scope string for OAuth authorization URL."""
    return ','.join(get_capability_scopes(capability))


def normalize_scopes(scopes: Iterable[str] | str) -> str:
    """
    Normalize scopes into a canonical sorted comma-separated string.
    Deduplicates and strips whitespace.
    """
    if not scopes:
        return ''
    if isinstance(scopes, str):
        raw_list = [s.strip().lower() for s in scopes.replace(' ', ',').split(',') if s.strip()]
    else:
        raw_list = [str(s).strip().lower() for s in scopes if s and str(s).strip()]
    return ','.join(sorted(set(raw_list)))


def parse_scopes(scope_str: Iterable[str] | str) -> list[str]:
    """Parse scopes into a sorted unique list of scope strings."""
    normalized = normalize_scopes(scope_str)
    if not normalized:
        return []
    return normalized.split(',')


def validate_capability_scopes(
    capability: str,
    granted_scopes: Iterable[str] | str,
) -> dict:
    """
    Validates granted scopes against a Meta capability definition.

    Returns dict:
      {
        'capability': str,
        'is_valid': bool,
        'requested_scopes': list[str],
        'required_scopes': list[str],
        'optional_scopes': list[str],
        'granted_scopes': list[str],
        'missing_required_scopes': list[str],
        'missing_optional_scopes': list[str],
      }
    """
    cfg = get_capability_config(capability)
    required = cfg.get('required_scopes', [])
    optional = cfg.get('optional_scopes', [])
    requested = get_capability_scopes(capability)

    granted_list = parse_scopes(granted_scopes)
    granted_set = set(granted_list)

    missing_required = []
    for s in required:
        acceptable = SCOPE_EQUIVALENCE_ALIASES.get(s, {s})
        if not (acceptable & granted_set):
            missing_required.append(s)

    missing_optional = []
    for s in optional:
        acceptable = SCOPE_EQUIVALENCE_ALIASES.get(s, {s})
        if not (acceptable & granted_set):
            missing_optional.append(s)

    is_valid = len(missing_required) == 0

    return {
        'capability': capability if capability in META_OAUTH_CAPABILITIES else DEFAULT_META_CAPABILITY,
        'is_valid': is_valid,
        'requested_scopes': requested,
        'required_scopes': required,
        'optional_scopes': optional,
        'granted_scopes': granted_list,
        'missing_required_scopes': missing_required,
        'missing_optional_scopes': missing_optional,
    }


def fetch_meta_granted_scopes(
    user_token: str,
    page_token: Optional[str] = None,
    app_id: Optional[str] = None,
    app_secret: Optional[str] = None,
    api_version: Optional[str] = None,
    timeout: int = 10,
) -> list[str]:
    """
    Fetch granted scopes from Meta Graph API.
    Probes both debug_token (token introspection) and /me/permissions.
    Never exposes or logs tokens or secrets.
    """
    version = api_version or getattr(settings, 'META_API_VERSION', 'v21.0')
    app_id = app_id or getattr(settings, 'META_APP_ID', '')
    app_secret = app_secret or getattr(settings, 'META_APP_SECRET', '')

    discovered: set[str] = set()

    # 1. Probe debug_token if app credentials exist
    if app_id and app_secret:
        app_token = f"{app_id}|{app_secret}"
        # Inspect page_token first if provided (since it carries granular page permissions)
        target_tokens = [t for t in [page_token, user_token] if t]
        for token in target_tokens:
            try:
                resp = requests.get(
                    f"https://graph.facebook.com/{version}/debug_token",
                    params={'input_token': token, 'access_token': app_token},
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    data = resp.json().get('data', {})
                    if data.get('scopes'):
                        for s in data['scopes']:
                            discovered.add(str(s).strip().lower())
                    if data.get('granular_scopes'):
                        for gs in data['granular_scopes']:
                            g_scope = gs.get('scope')
                            if g_scope:
                                discovered.add(str(g_scope).strip().lower())
                    if discovered:
                        break
            except Exception as e:
                logger.warning("debug_token probe exception: %s", type(e).__name__)

    # 2. Probe /me/permissions on user_token
    if user_token:
        try:
            resp = requests.get(
                f"https://graph.facebook.com/{version}/me/permissions",
                params={'access_token': user_token},
                timeout=timeout,
            )
            if resp.status_code == 200:
                perms = resp.json().get('data', [])
                if isinstance(perms, list):
                    for p in perms:
                        if isinstance(p, dict) and p.get('status') == 'granted' and p.get('permission'):
                            discovered.add(str(p['permission']).strip().lower())
        except Exception as e:
            logger.warning("/me/permissions probe exception: %s", type(e).__name__)

    # 3. If page_token provided and discovered is still empty, probe /me/permissions on page_token
    if page_token and not discovered:
        try:
            resp = requests.get(
                f"https://graph.facebook.com/{version}/me/permissions",
                params={'access_token': page_token},
                timeout=timeout,
            )
            if resp.status_code == 200:
                perms = resp.json().get('data', [])
                if isinstance(perms, list):
                    for p in perms:
                        if isinstance(p, dict) and p.get('status') == 'granted' and p.get('permission'):
                            discovered.add(str(p['permission']).strip().lower())
        except Exception as e:
            logger.warning("page_token /me/permissions probe exception: %s", type(e).__name__)

    return sorted(discovered)
