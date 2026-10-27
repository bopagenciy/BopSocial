# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Author    : Chandrabhan Shekhawat
#  Company   : Gigai Kripa Services
#  Website   : https://gigaikripaservices.com/
#  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
#  Released under the MIT License — see LICENSE. Keep this notice.
# ============================================================================
import uuid
from django.db import models
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from .currencies import CURRENCY_CHOICES
from .fields import EncryptedTextField

PLATFORM_CHOICES = [
    ('facebook',          'Facebook'),
    ('instagram',         'Instagram'),
    ('youtube',           'YouTube'),
    ('linkedin',          'LinkedIn'),
    ('google_my_business','Google My Business'),
]

ROLE_CHOICES = [
    ('superadmin', 'Super Admin'),
    ('staff',      'Staff'),
    ('client',     'Client'),
]

SYNC_STATUS = [
    ('pending', 'Pending'),
    ('running', 'Running'),
    ('success', 'Success'),
    ('partial', 'Partial'),
    ('failed',  'Failed'),
]


# ── Client (Company) ──────────────────────────────────────────────────────────
class Client(models.Model):
    name       = models.CharField(max_length=200)
    company    = models.CharField(max_length=200)
    email      = models.EmailField(unique=True)
    phone      = models.CharField(max_length=30, blank=True)
    whatsapp_number = models.CharField(max_length=30, blank=True)
    website    = models.URLField(blank=True)
    gmb_url    = models.URLField(blank=True, help_text="Google My Business profile URL")
    logo       = models.ImageField(upload_to='logos/', blank=True, null=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Business Profile Fields
    business_category = models.CharField(max_length=100, blank=True, help_text="e.g., Electronics, Retail, Services")
    business_subcategories = models.JSONField(default=list, blank=True, help_text="List of subcategories")
    brand_description = models.TextField(blank=True)
    usp = models.TextField(blank=True, help_text="Unique Selling Points")
    brand_tone = models.CharField(max_length=50, blank=True, choices=[
        ('professional', 'Professional'),
        ('casual', 'Casual'),
        ('funny', 'Funny'),
        ('inspirational', 'Inspirational'),
        ('urgent', 'Urgent'),
        ('friendly', 'Friendly'),
    ])
    target_audience = models.TextField(blank=True)
    gender = models.CharField(max_length=20, blank=True, choices=[
        ('all', 'All'),
        ('male', 'Male'),
        ('female', 'Female'),
        ('non_binary', 'Non-binary'),
        ('unspecified', 'Unspecified'),
    ])
    business_location = models.CharField(max_length=200, blank=True)
    target_locations = models.JSONField(default=list, blank=True, help_text="List of target countries/cities")
    brand_assets = models.JSONField(default=dict, blank=True, help_text="Logo URL, email, phone, etc.")
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    product_images = models.JSONField(default=list, blank=True, help_text="List of product image URLs")

    # Onboarding status
    onboarding_complete = models.BooleanField(default=False)

    # WhatsApp module toggle (Pinbot integration)
    whatsapp_enabled = models.BooleanField(default=False)

    # Per-client feature flags for the unified control center.
    # Example: {"composer": true, "scheduler": true, "inbox": true,
    #           "reviews": true, "video_studio": false, "automations": true,
    #           "ai_studio": true, "audience": true, "competitors": true}
    features_enabled = models.JSONField(default=dict, blank=True)

    # When True, all UnifiedPost rows go to status='pending_approval' before
    # publishing — used by hospitals / large brands for compliance review.
    requires_approval = models.BooleanField(default=False)

    # IANA timezone for accurate scheduled-post timing per client.
    timezone = models.CharField(max_length=64, blank=True, default='')

    # Workspace/tenant default language when user has not set an explicit preference.
    default_language = models.CharField(
        max_length=10,
        choices=[('en', 'English'), ('es', 'Spanish')],
        null=True,
        blank=True,
        default=None,
        help_text="Tenant default language ('en' or 'es'). Unset/None falls back to browser/system fallback.",
    )

    # Canonical workspace/tenant default currency (ISO 4217).
    CURRENCY_CHOICES = CURRENCY_CHOICES
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='USD',
        help_text="Workspace canonical currency code (ISO 4217).",
    )

    # ── Marketplace ownership ────────────────────────────────────
    # Who owns this workspace? Existing rows backfill to 'agency_owned' so the
    # legacy agency-managed flow stays untouched. End-user self-signups create
    # rows with 'end_user_owned' + owner_user set.
    owner_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='owned_workspaces',
    )
    OWNERSHIP_TYPES = [
        ('end_user_owned', 'End User Owned'),
        ('agency_owned',   'Agency Owned'),
        ('orphaned',       'Orphaned'),
    ]
    ownership_type = models.CharField(max_length=20, choices=OWNERSHIP_TYPES, default='agency_owned')
    CREATED_VIA_CHOICES = [
        ('end_user_signup', 'End User Self-Signup'),
        ('agency_invite',   'Agency Created'),
        ('marketplace',     'Marketplace Match'),
    ]
    created_via = models.CharField(max_length=20, choices=CREATED_VIA_CHOICES, default='agency_invite')

    # ── Subscription / plan ──────────────────────────────────────────────────
    SUBSCRIPTION_PLANS = [
        ('free',           'Free'),
        ('pro',            'Pro'),
        ('premium',        'Premium'),
        ('agency_managed', 'Agency Managed'),
    ]
    subscription_plan = models.CharField(max_length=20, choices=SUBSCRIPTION_PLANS, default='free')

    # ── Marketplace listing profile ──────────────────────────────────────────
    display_name                  = models.CharField(max_length=200, blank=True)
    industry                      = models.CharField(max_length=50,  blank=True)
    location_city                 = models.CharField(max_length=100, blank=True)
    location_country              = models.CharField(max_length=2,   blank=True)
    is_discoverable_in_marketplace = models.BooleanField(default=False)

    # ── Meta Conversions API (— CTWA bot builder) ───────────────────
    # When set, lead-capture pushes a 'Lead' event to Meta so CTWA ads can
    # optimize on real conversions. Test code is for sandbox testing only.
    meta_pixel_id        = models.CharField(max_length=50, blank=True)
    meta_capi_test_code  = models.CharField(max_length=30, blank=True)

    # ── — bot safety controls ───────────────────────────────────────
    bot_enabled                = models.BooleanField(default=True)   # workspace kill switch
    bot_max_msgs_per_minute    = models.IntegerField(default=20)     # per-contact rate limit
    bot_max_msgs_per_conv      = models.IntegerField(default=200)    # break runaway loops
    bot_spam_threshold         = models.IntegerField(default=5)      # auto-end at this score

    # ── — GDPR/DPDP "right to restrict processing" toggle ────────────
    # When True: batch sync fan-outs skip this client, AI calls fail with a
    # clear error (503 via AIError), and composer create/schedule/publish
    # return 423. The user can still log in to view existing data.
    is_processing_paused = models.BooleanField(default=False)

    # ── Canonical Bop Universe Identity ──────────────────────────
    bop_organization_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Canonical Bop Universe organization identifier (UUIDv4).",
    )

    def save(self, *args, **kwargs):
        if not self.bop_organization_id:
            self.bop_organization_id = uuid.uuid4()
        elif self.pk:
            orig = Client.objects.filter(pk=self.pk).values('bop_organization_id').first()
            if orig and orig['bop_organization_id'] and str(orig['bop_organization_id']) != str(self.bop_organization_id):
                raise ValueError("bop_organization_id is immutable once assigned.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company} ({self.name})"

    class Meta:
        ordering = ['company']


# ── Competitors ───────────────────────────────────────────────────────────────
class Competitor(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='competitors')
    name = models.CharField(max_length=200)
    social_links = models.JSONField(default=dict, blank=True, help_text="Dict of platform -> URL")
    created_at = models.DateTimeField(auto_now_add=True)

    # Per-platform public handles for snapshot scraping
    # Example: {"facebook": "@nike", "instagram": "@nike", "youtube": "UC...", "linkedin": "nike"}
    public_handles = models.JSONField(default=dict, blank=True, help_text="Dict of platform -> public handle/id")

    # Time series of follower counts per platform: {"facebook": [{"date": "2026-05-01", "n": 12345}, ...]}
    follower_history = models.JSONField(default=dict, blank=True)

    last_synced_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.client.company} - {self.name}"

    class Meta:
        ordering = ['name']


# ── User Profile (roles) ──────────────────────────────────────────────────────
class UserProfile(models.Model):
    user              = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role              = models.CharField(max_length=20, choices=ROLE_CHOICES, default='client')
    client            = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL)
    assigned_clients  = models.ManyToManyField(Client, blank=True, related_name='staff_assigned')
    avatar            = models.ImageField(upload_to='avatars/', blank=True, null=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    terms_accepted    = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    is_self_registered = models.BooleanField(default=False)
    email_verified     = models.BooleanField(default=True)   # False for email/password signups until verified
    language           = models.CharField(
        max_length=10,
        choices=[('en', 'English'), ('es', 'Spanish')],
        null=True,
        blank=True,
        default=None,
        help_text="Explicit user language preference ('en' or 'es'). Unset/None falls back to tenant default or browser.",
    )
    agency             = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_clients')

    # ── Marketplace account type ────────────────────────────────
    # 'legacy' is the default for everyone existing pre-marketplace; the
    # signup flows (end-user vs agency) set the right value going forward.
    ACCOUNT_TYPES = [
        ('end_user',      'End User'),       # B2C, owns one or more workspaces
        ('agency_member', 'Agency Member'),  # works at an agency
        ('legacy',        'Legacy'),         # pre-marketplace, mapped on migration
    ]
    account_type      = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='legacy')
    primary_agency    = models.ForeignKey(
        'Agency', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='primary_members',
    )
    default_workspace = models.ForeignKey(
        Client, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+',
    )

    def __str__(self):
        return f"{self.user.email} ({self.role})"

    def can_access_client(self, client_id):
        if self.role == 'superadmin':
            return True
        if self.role == 'client':
            return self.client_id == int(client_id)
        if self.role == 'staff':
            return self.assigned_clients.filter(id=client_id).exists()
        return False


class EmailVerificationToken(models.Model):
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_verification')
    token      = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used    = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

    def __str__(self):
        return f"Verification token for {self.user.email}"


class PasswordResetToken(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_resets')
    token      = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used    = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(hours=2)
        super().save(*args, **kwargs)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

    def __str__(self):
        return f"Reset token for {self.user.email}"


def ensure_client_profile(profile):
    """
    Ensure client-role users always have a linked Client record.
    This supports direct client signups/social logins in the same way as
    agency-created client accounts.
    """
    if not profile or profile.role != 'client':
        return None
    if profile.client_id:
        return profile.client

    user = profile.user
    email = (user.email or '').strip().lower()
    if not email:
        return None

    with transaction.atomic():
        existing = Client.objects.filter(email__iexact=email).first()
        if existing:
            profile.client = existing
            profile.save(update_fields=['client'])
            return existing

        full_name = (user.get_full_name() or user.username or email.split('@')[0]).strip()
        first_name = (user.first_name or '').strip()
        company = first_name or full_name or email.split('@')[0]

        client = Client.objects.create(
            name=full_name,
            company=company,
            email=email,
        )
        profile.client = client
        profile.save(update_fields=['client'])
        return client


# ── OAuth Credentials per client per platform ─────────────────────────────────
class PlatformCredential(models.Model):
    client        = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='credentials')
    platform      = models.CharField(max_length=30, choices=PLATFORM_CHOICES)

    # OAuth tokens (AES-encrypted at rest)
    access_token  = EncryptedTextField(blank=True)
    refresh_token = EncryptedTextField(blank=True)
    token_type    = models.CharField(max_length=50, blank=True, default='Bearer')
    expires_at    = models.DateTimeField(null=True, blank=True)
    scope         = models.TextField(blank=True)

    platform_user_id = models.CharField(max_length=80, blank=True, db_index=True)

    # Platform-specific IDs (auto-fetched after OAuth)
    page_id              = models.CharField(max_length=200, blank=True)   # Facebook Page ID
    page_name            = models.CharField(max_length=200, blank=True)   # Facebook Page Name
    instagram_account_id = models.CharField(max_length=200, blank=True)   # IG Business Account ID
    channel_id           = models.CharField(max_length=200, blank=True)   # YouTube Channel ID
    channel_name         = models.CharField(max_length=200, blank=True)   # YouTube Channel Name
    organization_id      = models.CharField(max_length=200, blank=True)   # LinkedIn Org ID
    organization_name    = models.CharField(max_length=200, blank=True)   # LinkedIn Org Name
    gmb_account_id       = models.CharField(max_length=200, blank=True)   # GMB Account
    gmb_location_id      = models.CharField(max_length=200, blank=True)   # GMB Location

    is_active    = models.BooleanField(default=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    # How the credential was provisioned. 'oauth' = via Social Stats-owned OAuth app.
    # 'manual_token' = client pasted their own token from their dev account.
    # 'system_user' = Meta System User token (long-lived, ideal for prod).
    auth_method  = models.CharField(
        max_length=20,
        choices=[('oauth', 'OAuth'), ('manual_token', 'Manual Token'), ('system_user', 'System User')],
        default='oauth',
    )

    # BS-4B: Rate limit quota state (stores non-secret provider quota metrics, usage %, cooldowns)
    rate_limit_state = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('client', 'platform')
        ordering = ['platform']

    def __str__(self):
        return f"{self.client.company} — {self.get_platform_display()}"

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at - timedelta(minutes=10)

    @property
    def status(self):
        if not self.access_token:
            return 'not_connected'
        if self.is_expired:
            return 'expired'
        return 'active'

    def get_scopes(self) -> list[str]:
        """Return granted scopes as a sorted list of unique scope strings."""
        if not self.scope:
            return []
        return [s.strip().lower() for s in self.scope.split(',') if s.strip()]

    def has_scope(self, scope_name: str) -> bool:
        """Check whether a specific scope was granted to this credential."""
        if not scope_name:
            return False
        return scope_name.strip().lower() in self.get_scopes()



class ManualCredentialExtras(models.Model):
    """
    Sibling row holding the client-provided Google OAuth-app credentials
    (and optional API key) used by manual-mode YouTube and GMB connections.

    PlatformCredential.access_token / refresh_token already hold the per-account
    tokens; this row only adds the user's Google Cloud OAuth client identity
    so the existing token-refresh path can keep working without an
    Social Stats-owned OAuth app. Encrypted at rest (same Fernet pipeline as tokens).
    """
    credential          = models.OneToOneField(PlatformCredential, on_delete=models.CASCADE, related_name='manual_extras')
    oauth_client_id     = EncryptedTextField(blank=True)
    oauth_client_secret = EncryptedTextField(blank=True)
    api_key             = EncryptedTextField(blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Manual extras — {self.credential}"


# ── Daily Aggregated Metrics ───────────────────────────────────────────────────
class DailyMetric(models.Model):
    client    = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='metrics')
    platform  = models.CharField(max_length=30, choices=PLATFORM_CHOICES)
    date      = models.DateField()

    # Universal metrics
    impressions  = models.BigIntegerField(default=0)
    reach        = models.BigIntegerField(default=0)
    clicks       = models.BigIntegerField(default=0)
    likes        = models.BigIntegerField(default=0)
    comments     = models.BigIntegerField(default=0)
    shares       = models.BigIntegerField(default=0)
    saves        = models.BigIntegerField(default=0)
    video_views  = models.BigIntegerField(default=0)
    followers    = models.BigIntegerField(default=0)
    profile_views= models.BigIntegerField(default=0)

    # Google / Ads specific
    sessions             = models.BigIntegerField(default=0)
    users                = models.BigIntegerField(default=0)
    page_views           = models.BigIntegerField(default=0)
    website_clicks       = models.BigIntegerField(default=0)
    direction_requests   = models.BigIntegerField(default=0)
    phone_calls          = models.BigIntegerField(default=0)

    # GMB-specific extended metrics
    maps_impressions     = models.BigIntegerField(default=0)   # impressions on Google Maps
    search_impressions   = models.BigIntegerField(default=0)   # impressions on Google Search
    photo_views          = models.BigIntegerField(default=0)   # business photo views
    business_conversations = models.BigIntegerField(default=0) # messages/Q&A

    # YouTube-specific
    watch_time_minutes  = models.BigIntegerField(default=0)   # estimatedMinutesWatched
    avg_view_duration   = models.FloatField(default=0)        # averageViewDuration (seconds)
    subscribers_lost    = models.BigIntegerField(default=0)   # subscribersLost

    # Facebook-specific
    followers_lost      = models.BigIntegerField(default=0)   # page_fan_removes (unfollows)
    negative_feedback   = models.BigIntegerField(default=0)   # page_negative_feedback (hides/spam)
    fb_video_views      = models.BigIntegerField(default=0)   # page_video_views
    fb_video_watch_time = models.BigIntegerField(default=0)   # page_video_view_time (ms → seconds)
    reactions           = models.JSONField(default=dict, blank=True)  # {like,love,haha,wow,sad,angry}

    # Instagram-specific
    accounts_engaged    = models.BigIntegerField(default=0)   # accounts that engaged
    total_interactions  = models.BigIntegerField(default=0)   # likes+comments+shares+saves
    email_contacts      = models.BigIntegerField(default=0)   # email button clicks
    phone_call_clicks   = models.BigIntegerField(default=0)   # call button clicks
    direction_clicks    = models.BigIntegerField(default=0)   # get directions clicks
    ig_followers_lost   = models.BigIntegerField(default=0)   # unfollows

    # Calculated
    engagement_rate = models.FloatField(default=0)
    ctr             = models.FloatField(default=0)

    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('client', 'platform', 'date')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['client', 'platform', 'date']),
        ]

    def __str__(self):
        return f"{self.client.company} | {self.platform} | {self.date}"


# ── Per-Post Metrics (Instagram / Facebook) ───────────────────────────────────
class PostMetric(models.Model):
    client        = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='post_metrics')
    platform      = models.CharField(max_length=30, choices=PLATFORM_CHOICES)
    post_id       = models.CharField(max_length=300)
    # BS-4B: Optional prospective linkage to Bop Social authored UnifiedPost
    unified_post  = models.ForeignKey('social_stats.UnifiedPost', on_delete=models.SET_NULL, null=True, blank=True, related_name='legacy_post_metrics')
    post_url      = models.TextField(blank=True)
    post_type     = models.CharField(max_length=50, blank=True)
    caption       = models.TextField(blank=True)
    thumbnail_url = models.TextField(blank=True)
    published_at  = models.DateTimeField(null=True, blank=True)

    impressions  = models.BigIntegerField(default=0)
    reach        = models.BigIntegerField(default=0)
    clicks       = models.BigIntegerField(default=0)
    likes        = models.BigIntegerField(default=0)
    comments     = models.BigIntegerField(default=0)
    shares       = models.BigIntegerField(default=0)
    saves        = models.BigIntegerField(default=0)
    video_views  = models.BigIntegerField(default=0)

    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('client', 'platform', 'post_id')
        ordering = ['-published_at']


# ── GMB Business Info (synced from Business Information API) ──────────────────
class GMBBusinessInfo(models.Model):
    client          = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='gmb_info')
    business_name   = models.CharField(max_length=300, blank=True)
    address         = models.TextField(blank=True)
    phone           = models.CharField(max_length=50, blank=True)
    website         = models.URLField(blank=True)
    category        = models.CharField(max_length=200, blank=True)       # primary category
    additional_categories = models.JSONField(default=list, blank=True)   # extra categories
    description     = models.TextField(blank=True)
    opening_date    = models.DateField(null=True, blank=True)
    is_verified     = models.BooleanField(default=False)
    is_open         = models.BooleanField(default=True)                  # currently open?
    regular_hours   = models.JSONField(default=dict, blank=True)         # {MON: [{open:'09:00',close:'17:00'}]}
    special_hours   = models.JSONField(default=list, blank=True)         # holiday hours
    profile_photo_url  = models.URLField(blank=True)
    cover_photo_url    = models.URLField(blank=True)
    maps_url           = models.URLField(blank=True)
    place_id           = models.CharField(max_length=200, blank=True)
    latitude           = models.FloatField(null=True, blank=True)
    longitude          = models.FloatField(null=True, blank=True)
    # Aggregate review stats (refreshed on each sync)
    avg_rating         = models.FloatField(default=0)
    total_reviews      = models.IntegerField(default=0)
    synced_at          = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.client.company} — GMB Info"


# ── GMB Reviews (synced via Account Management API) ───────────────────────────
class GMBReview(models.Model):
    client          = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='gmb_reviews')
    review_id       = models.CharField(max_length=300, unique=True)
    reviewer_name   = models.CharField(max_length=200, blank=True)
    reviewer_photo  = models.URLField(blank=True)
    rating          = models.PositiveSmallIntegerField(default=5)        # 1–5
    comment         = models.TextField(blank=True)
    owner_reply     = models.TextField(blank=True)
    reply_updated_at = models.DateTimeField(null=True, blank=True)
    published_at    = models.DateTimeField(null=True, blank=True)
    synced_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at']
        indexes = [models.Index(fields=['client', 'published_at'])]

    def __str__(self):
        return f"{self.client.company} — ★{self.rating} by {self.reviewer_name}"


GOAL_METRIC_CHOICES = [
    ('impressions',    'Impressions'),
    ('reach',          'Reach'),
    ('clicks',         'Clicks'),
    ('likes',          'Likes'),
    ('followers',      'Followers'),
    ('video_views',    'Video Views'),
    ('website_clicks', 'Website Clicks'),
    ('phone_calls',    'Phone Calls'),
]

GOAL_PLATFORM_CHOICES = PLATFORM_CHOICES + [('all', 'All Platforms')]


# ── Monthly Goals ─────────────────────────────────────────────────────────────
class ClientGoal(models.Model):
    client       = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='goals')
    platform     = models.CharField(max_length=30, choices=GOAL_PLATFORM_CHOICES)
    metric       = models.CharField(max_length=30, choices=GOAL_METRIC_CHOICES)
    target_value = models.BigIntegerField()
    month        = models.PositiveSmallIntegerField()   # 1–12
    year         = models.PositiveSmallIntegerField()
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('client', 'platform', 'metric', 'month', 'year')
        ordering = ['-year', '-month', 'platform', 'metric']

    def __str__(self):
        return f"{self.client.company} | {self.platform} | {self.metric} | {self.month}/{self.year}"


ALERT_TYPE_CHOICES = [
    ('token_expired',      'Token Expired'),
    ('sync_failed',        'Sync Failed'),
    ('reach_drop',         'Reach Drop'),
    ('viral_post',         'Viral Post'),
    ('goal_at_risk',       'Goal At Risk'),
    ('follower_milestone', 'Follower Milestone'),
]


# ── Smart Alerts ──────────────────────────────────────────────────────────────
class Alert(models.Model):
    client     = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='alerts')
    platform   = models.CharField(max_length=30, blank=True)
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPE_CHOICES)
    message    = models.TextField()
    is_read    = models.BooleanField(default=False)
    dedup_key  = models.CharField(max_length=200, blank=True)  # prevents duplicate alerts per day
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.client.company} | {self.alert_type} | {self.created_at:%Y-%m-%d}"


# ── AI Insights ───────────────────────────────────────────────────────────────
class AIInsight(models.Model):
    """
    AI-generated insight for a client. Originally a per-month rollup; extended
    in the AI infra to support feed-style insights with severity,
    confidence, action recommendations, and dismiss/acted-on tracking.

    Two coexisting shapes:
      * Legacy monthly: month + year + content (kept working for existing data)
      * Feed-style: insight_type + confidence_score + data_sources + action_recommended
    """
    SEVERITY_CHOICES = [
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical'),
    ]

    client            = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='ai_insights')
    month             = models.PositiveSmallIntegerField(null=True, blank=True)
    year              = models.PositiveSmallIntegerField(null=True, blank=True)
    content           = models.TextField()

    # Feed-style fields — added AI infra
    title             = models.CharField(max_length=200, blank=True)
    insight_type      = models.CharField(max_length=60, blank=True,
                                         help_text='engagement_trend, competitor_alert, best_time_shift, etc.')
    severity          = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='medium', blank=True)
    confidence_score  = models.FloatField(default=0.0,
                                          help_text='0.0-1.0 — how certain Claude is about this insight')
    data_sources      = models.JSONField(default=list, blank=True,
                                         help_text='Brief description of what was analysed')
    action_recommended = models.TextField(blank=True)
    dismissed         = models.BooleanField(default=False)
    acted_upon        = models.BooleanField(default=False)
    expires_at        = models.DateTimeField(null=True, blank=True)
    generated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['client', '-generated_at']),
            models.Index(fields=['client', 'dismissed', '-generated_at']),
            models.Index(fields=['insight_type']),
        ]

    def __str__(self):
        if self.title:
            return f"{self.client.company} | {self.title}"
        return f"{self.client.company} | {self.month}/{self.year}"


# ── Weekly Top Posts ──────────────────────────────────────────────────────────
class WeeklyTopPost(models.Model):
    client      = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='weekly_top_posts')
    platform    = models.CharField(max_length=30, choices=PLATFORM_CHOICES)
    post_metric = models.ForeignKey('PostMetric', on_delete=models.CASCADE, null=True, blank=True)
    week_start  = models.DateField()   # Monday of the scored week
    score       = models.FloatField(default=0)
    rank        = models.PositiveSmallIntegerField(default=1)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('client', 'platform', 'week_start', 'rank')
        ordering = ['-week_start', 'platform', 'rank']

    def __str__(self):
        return f"{self.client.company} | {self.platform} | {self.week_start} | #{self.rank}"


# ── Shareable Public Reports ──────────────────────────────────────────────────
class SharedReport(models.Model):
    client      = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='shared_reports')
    token       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    date_from   = models.DateField()
    date_until  = models.DateField()
    platforms   = models.JSONField(default=list)        # e.g. ['facebook', 'instagram']
    is_password_protected = models.BooleanField(default=False)
    password_hash         = models.CharField(max_length=128, blank=True)
    expires_at    = models.DateTimeField(null=True, blank=True)
    view_count    = models.PositiveIntegerField(default=0)
    last_viewed_at= models.DateTimeField(null=True, blank=True)
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.client.company} | {self.token}"

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(raw_password)

    def verify_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password_hash)


# ── Client Onboarding Checklist ───────────────────────────────────────────────
ONBOARDING_STEP_CHOICES = [
    ('connect_platform',  'Connect a Platform'),
    ('first_sync',        'Run First Sync'),
    ('set_goals',         'Set Monthly Goals'),
    ('add_credentials',   'Add API Credentials'),
    ('invite_team',       'Invite Team Members'),
    ('configure_alerts',  'Configure Alerts'),
]

ONBOARDING_STEP_DESCRIPTIONS = {
    'connect_platform': 'Connect at least one social media platform via OAuth.',
    'first_sync':       'Run a successful data sync to pull in your first metrics.',
    'set_goals':        'Create at least one monthly performance goal.',
    'add_credentials':  'Add API credentials for manual platform access.',
    'invite_team':      'Invite a team member or verify your account is set up.',
    'configure_alerts': 'Review and configure your smart alert preferences.',
}


class OnboardingStep(models.Model):
    client       = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='onboarding_steps')
    step_key     = models.CharField(max_length=40, choices=ONBOARDING_STEP_CHOICES)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('client', 'step_key')
        ordering = ['id']

    def __str__(self):
        status = '✓' if self.is_completed else '○'
        return f"{self.client.company} | {status} {self.step_key}"

    def mark_complete(self, user=None):
        if not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()
            self.completed_by = user
            self.save(update_fields=['is_completed', 'completed_at', 'completed_by'])


# ── Signals: auto-create onboarding steps + auto-mark complete ────────────────
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Client)
def create_onboarding_steps(sender, instance, created, **kwargs):
    if created:
        for step_key, _ in ONBOARDING_STEP_CHOICES:
            OnboardingStep.objects.get_or_create(client=instance, step_key=step_key)


@receiver(post_save, sender='social_stats.PlatformCredential')
def mark_connect_platform(sender, instance, created, **kwargs):
    if created:
        OnboardingStep.objects.filter(
            client=instance.client, step_key='connect_platform', is_completed=False
        ).update(is_completed=True, completed_at=timezone.now())
        OnboardingStep.objects.filter(
            client=instance.client, step_key='add_credentials', is_completed=False
        ).update(is_completed=True, completed_at=timezone.now())


@receiver(post_save, sender='social_stats.SyncLog')
def mark_first_sync(sender, instance, **kwargs):
    if instance.status == 'success' and instance.client_id:
        OnboardingStep.objects.filter(
            client=instance.client, step_key='first_sync', is_completed=False
        ).update(is_completed=True, completed_at=timezone.now())


@receiver(post_save, sender='social_stats.ClientGoal')
def mark_set_goals(sender, instance, created, **kwargs):
    if created:
        OnboardingStep.objects.filter(
            client=instance.client, step_key='set_goals', is_completed=False
        ).update(is_completed=True, completed_at=timezone.now())


# ── ROI Settings ──────────────────────────────────────────────────────────────
class ROISettings(models.Model):
    client              = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='roi_settings')
    facebook_budget     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    instagram_budget    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    youtube_budget      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    linkedin_budget     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gmb_budget          = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    agency_fee          = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    avg_sale_value      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    conversion_rate     = models.DecimalField(max_digits=5, decimal_places=2, default=2.5)
    lead_to_sale_rate   = models.DecimalField(max_digits=5, decimal_places=2, default=20.0)
    currency            = models.CharField(max_length=10, default='USD')
    currency_symbol     = models.CharField(max_length=5, default='$')
    monthly_revenue_goal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monthly_leads_goal  = models.IntegerField(default=0)
    updated_at          = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ROI Settings — {self.client.company}"

    @property
    def total_budget(self):
        return (self.facebook_budget + self.instagram_budget + self.youtube_budget +
                self.linkedin_budget + self.gmb_budget + self.agency_fee)


# ── ROI Report ────────────────────────────────────────────────────────────────
class ROIReport(models.Model):
    client            = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='roi_reports')
    month             = models.IntegerField()
    year              = models.IntegerField()
    currency          = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    total_investment  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    agency_fee        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_clicks      = models.BigIntegerField(default=0)
    total_impressions = models.BigIntegerField(default=0)
    total_reach       = models.BigIntegerField(default=0)
    website_clicks    = models.BigIntegerField(default=0)
    estimated_leads   = models.IntegerField(default=0)
    estimated_sales   = models.IntegerField(default=0)
    estimated_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    roi_percentage    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cost_per_click    = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    cost_per_lead     = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    cost_per_sale     = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    platform_breakdown = models.JSONField(default=dict)
    generated_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('client', 'month', 'year')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"ROI Report — {self.client.company} {self.month}/{self.year}"


# ── Sync Log ──────────────────────────────────────────────────────────────────
class SyncLog(models.Model):
    client         = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='sync_logs', null=True)
    platform       = models.CharField(max_length=30, choices=PLATFORM_CHOICES)
    status         = models.CharField(max_length=20, choices=SYNC_STATUS, default='pending')
    records_synced = models.IntegerField(default=0)
    error_message  = models.TextField(blank=True)
    started_at     = models.DateTimeField(auto_now_add=True)
    finished_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.platform} | {self.status} | {self.started_at:%Y-%m-%d %H:%M}"


# ── Content Calendar ───────────────────────────────────────────────────────────

POST_TYPE_CHOICES = [
    ('image',    'Image'),
    ('video',    'Video'),
    ('reel',     'Reel'),
    ('story',    'Story'),
    ('carousel', 'Carousel'),
    ('text',     'Text'),
    ('article',  'Article'),
    ('short',    'Short'),
]

CALENDAR_STATUS_CHOICES = [
    ('published', 'Published'),
    ('scheduled', 'Scheduled'),
    ('draft',     'Draft'),
    ('failed',    'Failed'),
]


class CalendarPost(models.Model):
    client      = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='calendar_posts')
    platform    = models.CharField(max_length=30, choices=PLATFORM_CHOICES)
    post_type   = models.CharField(max_length=20, choices=POST_TYPE_CHOICES, default='image')
    status      = models.CharField(max_length=20, choices=CALENDAR_STATUS_CHOICES, default='draft')
    title       = models.CharField(max_length=200, blank=True)
    caption     = models.TextField(blank=True)
    hashtags    = models.TextField(blank=True)
    media_url   = models.URLField(blank=True)
    post_url    = models.URLField(blank=True)
    scheduled_at  = models.DateTimeField(null=True, blank=True)
    published_at  = models.DateTimeField(null=True, blank=True)
    post_metric   = models.OneToOneField(
        'PostMetric', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='calendar_post'
    )

    # Performance snapshot
    impressions     = models.BigIntegerField(default=0)
    reach           = models.BigIntegerField(default=0)
    likes           = models.BigIntegerField(default=0)
    comments        = models.BigIntegerField(default=0)
    shares          = models.BigIntegerField(default=0)
    saves           = models.BigIntegerField(default=0)
    video_views     = models.BigIntegerField(default=0)
    engagement_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0)

    # Meta
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_calendar_posts')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    external_id = models.CharField(max_length=300, blank=True)
    notes       = models.TextField(blank=True)

    class Meta:
        ordering = ['-scheduled_at', '-published_at']

    def __str__(self):
        return f"{self.client.company} | {self.platform} | {self.status} | {self.title or self.caption[:40]}"

    @property
    def best_time(self):
        return self.scheduled_at or self.published_at


class CalendarNote(models.Model):
    client            = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='calendar_notes')
    date              = models.DateField()
    title             = models.CharField(max_length=200)
    note              = models.TextField(blank=True)
    color             = models.CharField(max_length=7, default='#2563EB')
    is_client_visible = models.BooleanField(default=False)
    created_by        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_calendar_notes')
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'id']

    def __str__(self):
        return f"{self.client.company} | {self.date} | {self.title}"


class PostingSchedule(models.Model):
    client      = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='posting_schedules')
    platform    = models.CharField(max_length=30, choices=PLATFORM_CHOICES)
    day_of_week = models.IntegerField()   # 0=Monday … 6=Sunday
    hour        = models.IntegerField()
    minute      = models.IntegerField(default=0)
    is_active   = models.BooleanField(default=True)
    note        = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ('client', 'platform', 'day_of_week', 'hour', 'minute')
        ordering = ['platform', 'day_of_week', 'hour']

    def __str__(self):
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        return f"{self.client.company} | {self.platform} | {days[self.day_of_week]} {self.hour:02d}:{self.minute:02d}"


# ── Access Management ─────────────────────────────────────────────────────────

PERMISSION_CATEGORY_CHOICES = [
    ('pages',    'Pages'),
    ('sections', 'Sections'),
    ('actions',  'Actions'),
    ('data',     'Data'),
]

ALL_PERMISSIONS = [
    # Dashboard
    ('dashboard.view',               'View Dashboard',                'See the main dashboard page',                          'pages',    True,  True,  10),
    ('dashboard.kpi_cards',          'See KPI Cards',                 'View stat cards at top of dashboard',                  'sections', True,  True,  11),
    ('dashboard.charts',             'See Charts',                    'View charts and graphs',                               'sections', True,  True,  12),
    ('dashboard.platform_tabs',      'Platform Tabs',                 'Switch between platforms',                             'sections', True,  True,  13),
    ('dashboard.date_range',         'Change Date Range',             'Modify date range filter',                             'actions',  True,  True,  14),
    ('dashboard.posts_table',        'Recent Posts Table',            'See recent posts section',                             'sections', True,  True,  15),
    ('dashboard.platform_breakdown', 'Platform Breakdown',            'See platform breakdown table',                         'sections', True,  True,  16),
    ('dashboard.sync_now',           'Sync Now Button',               'Trigger manual sync',                                  'actions',  True,  False, 17),
    ('dashboard.export_pdf',         'Export PDF',                    'Export dashboard as PDF report',                       'actions',  True,  True,  18),
    # Analytics
    ('analytics.view',               'View Analytics',                'Access analytics page',                                'pages',    True,  True,  20),
    ('analytics.impressions',        'Impressions Data',              'See impressions metrics',                              'data',     True,  True,  21),
    ('analytics.reach',              'Reach Data',                    'See reach metrics',                                    'data',     True,  True,  22),
    ('analytics.engagement',         'Engagement Data',               'See engagement metrics',                               'data',     True,  True,  23),
    ('analytics.video_views',        'Video Views Data',              'See video view counts',                                'data',     True,  True,  24),
    ('analytics.followers',          'Followers Data',                'See follower counts',                                  'data',     True,  True,  25),
    ('analytics.website_clicks',     'Website Clicks',                'See website click data',                               'data',     True,  True,  26),
    ('analytics.phone_calls',        'Phone Calls',                   'See phone call data (GMB)',                            'data',     True,  False, 27),
    ('analytics.direction_requests', 'Direction Requests',            'See direction requests (GMB)',                         'data',     True,  False, 28),
    # Calendar
    ('calendar.view',                'View Calendar',                 'Access content calendar page',                         'pages',    True,  True,  30),
    ('calendar.month_view',          'Month View',                    'See monthly calendar grid',                            'sections', True,  True,  31),
    ('calendar.list_view',           'List View',                     'See list view of posts',                               'sections', True,  True,  32),
    ('calendar.stats_view',          'Stats View',                    'See posting stats',                                    'sections', True,  False, 33),
    ('calendar.create_post',         'Create Posts',                  'Schedule new posts',                                   'actions',  True,  False, 34),
    ('calendar.edit_post',           'Edit Posts',                    'Edit existing calendar posts',                         'actions',  True,  False, 35),
    ('calendar.delete_post',         'Delete Posts',                  'Delete calendar posts',                                'actions',  True,  False, 36),
    ('calendar.add_notes',           'Add Notes',                     'Add calendar notes',                                   'actions',  True,  False, 37),
    ('calendar.view_notes',          'View Notes',                    'See calendar notes',                                   'sections', True,  True,  38),
    ('calendar.best_times',          'Best Posting Times',            'See recommended posting times',                        'sections', True,  False, 39),
    # ROI
    ('roi.view',                     'View ROI Calculator',           'Access ROI calculator page',                           'pages',    True,  True,  40),
    ('roi.view_results',             'See ROI Results',               'View calculated ROI results',                          'sections', True,  True,  41),
    ('roi.edit_settings',            'Edit ROI Settings',             'Modify budgets and conversion rates',                  'actions',  True,  False, 42),
    ('roi.view_history',             'ROI History',                   'View past ROI reports',                                'sections', True,  True,  43),
    ('roi.export',                   'Export ROI Report',             'Download ROI as PDF',                                  'actions',  True,  False, 44),
    # Reports
    ('reports.view',                 'View Reports',                  'Access reports page',                                  'pages',    True,  True,  50),
    ('reports.download_pdf',         'Download PDF',                  'Download report PDFs',                                 'actions',  True,  True,  51),
    ('reports.view_history',         'Report History',                'See past generated reports',                           'sections', True,  True,  52),
    ('reports.schedule',             'Schedule Reports',              'Configure automated report delivery',                  'actions',  True,  False, 53),
    # Alerts
    ('alerts.view',                  'View Alerts',                   'Access alerts page',                                   'pages',    True,  False, 60),
    ('alerts.mark_read',             'Mark Alerts Read',              'Dismiss and mark alerts as read',                      'actions',  True,  False, 61),
    ('alerts.configure',             'Configure Alerts',              'Set up alert rules and thresholds',                    'actions',  True,  False, 62),
    # Reviews
    ('reviews.view',                 'View Reviews',                  'Access reviews page',                                  'pages',    True,  False, 70),
    ('reviews.reply',                'Reply to Reviews',              'Post replies to Google reviews',                       'actions',  True,  False, 71),
    ('reviews.view_stats',           'Review Statistics',             'See review rating analytics',                          'sections', True,  False, 72),
    # Settings
    ('settings.view',                'View Settings',                 'Access settings page',                                 'pages',    True,  True,  80),
    ('settings.connect_accounts',    'Connect Accounts',              'Link social media accounts via OAuth',                 'actions',  True,  True,  81),
    ('settings.disconnect_accounts', 'Disconnect Accounts',           'Unlink connected accounts',                            'actions',  True,  False, 82),
    ('settings.view_credentials',    'View Connected Status',         'See which platforms are connected',                    'sections', True,  True,  83),
    # Billing
    ('billing.view',                 'View Billing',                  'Access billing page',                                  'pages',    True,  False, 90),
    ('billing.view_invoices',        'View Invoices',                 'See invoice history',                                  'sections', True,  False, 91),
    ('billing.download_invoices',    'Download Invoices',             'Download invoice PDFs',                                'actions',  True,  False, 92),
    # Data
    ('data.view_all_clients',        'View All Clients',              'Access data for all clients',                          'data',     True,  False, 100),
    ('data.view_assigned_clients',   'View Assigned Clients',         'Access data only for assigned clients',                'data',     True,  False, 101),
    ('data.view_own_client',         'View Own Client Data',          'Access own client data only',                          'data',     False, True,  102),
    ('data.impressions',             'Impressions Numbers',           'See impressions figures',                              'data',     True,  True,  103),
    ('data.revenue_data',            'Revenue / ROI Numbers',         'See financial and ROI data',                           'data',     True,  False, 104),
    ('data.competitor_data',         'Competitor Data',               'Access competitor benchmarks',                         'data',     True,  False, 105),
]

# Page groupings for the UI
PERMISSION_PAGE_GROUPS = {
    'dashboard': {'label': 'Dashboard',         'icon': '📊', 'prefix': 'dashboard.'},
    'analytics': {'label': 'Analytics',         'icon': '📈', 'prefix': 'analytics.'},
    'calendar':  {'label': 'Content Calendar',  'icon': '📅', 'prefix': 'calendar.'},
    'roi':       {'label': 'ROI Calculator',    'icon': '💰', 'prefix': 'roi.'},
    'reports':   {'label': 'Reports',           'icon': '📄', 'prefix': 'reports.'},
    'alerts':    {'label': 'Alerts',            'icon': '🔔', 'prefix': 'alerts.'},
    'reviews':   {'label': 'Reviews',           'icon': '⭐', 'prefix': 'reviews.'},
    'settings':  {'label': 'Settings',          'icon': '⚙️', 'prefix': 'settings.'},
    'billing':   {'label': 'Billing',           'icon': '💳', 'prefix': 'billing.'},
    'data':      {'label': 'Data Access',       'icon': '🗄️', 'prefix': 'data.'},
    'whatsapp':  {'label': 'WhatsApp',          'icon': '💬', 'prefix': 'whatsapp.'},
    'composer':      {'label': 'Composer',          'icon': '✍️', 'prefix': 'composer.'},
    'inbox':         {'label': 'Inbox',             'icon': '📥', 'prefix': 'inbox.'},
    'video_studio':  {'label': 'Video Studio',      'icon': '🎬', 'prefix': 'video.'},
    'automations':   {'label': 'Automations',       'icon': '⚡', 'prefix': 'automations.'},
    'ai_studio':     {'label': 'AI Studio',         'icon': '✨', 'prefix': 'ai.'},
    'audience':      {'label': 'Audience Insights', 'icon': '👥', 'prefix': 'audience.'},
    'competitors':   {'label': 'Competitors',       'icon': '🏆', 'prefix': 'competitors.'},
    'audit':         {'label': 'Audit Log',         'icon': '📜', 'prefix': 'audit.'},
    # CTWA Bot Builder
    'bot_flows':     {'label': 'Bot Flows',         'icon': '🤖', 'prefix': 'bot.'},
    'leads':         {'label': 'Leads',             'icon': '👥', 'prefix': 'leads.'},
    'ctwa':          {'label': 'CTWA Campaigns',    'icon': '📣', 'prefix': 'ctwa.'},
}


class Permission(models.Model):
    code             = models.CharField(max_length=100, unique=True)
    label            = models.CharField(max_length=200)
    description      = models.CharField(max_length=300, blank=True)
    category         = models.CharField(max_length=20, choices=PERMISSION_CATEGORY_CHOICES, default='pages')
    page             = models.CharField(max_length=50, blank=True)
    is_default_staff  = models.BooleanField(default=False)
    is_default_client = models.BooleanField(default=False)
    sort_order        = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f"{self.code} — {self.label}"


class RolePermission(models.Model):
    role       = models.CharField(max_length=20, choices=[('staff','Staff'),('client','Client')])
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='role_permissions')
    is_granted = models.BooleanField(default=True)

    class Meta:
        unique_together = ('role', 'permission')

    def __str__(self):
        return f"{self.role} | {self.permission.code} | {'✓' if self.is_granted else '✗'}"


class UserPermission(models.Model):
    user_profile = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='permission_overrides')
    permission   = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='user_overrides')
    is_granted   = models.BooleanField()
    granted_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='granted_permissions')
    granted_at   = models.DateTimeField(auto_now_add=True)
    note         = models.CharField(max_length=300, blank=True)

    class Meta:
        unique_together = ('user_profile', 'permission')

    def __str__(self):
        return f"{self.user_profile.user.email} | {self.permission.code} | {'✓' if self.is_granted else '✗'}"


class StaffClientAssignment(models.Model):
    staff_profile = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='client_assignments')
    client        = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='staff_assignments')
    assigned_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='made_assignments')
    assigned_at   = models.DateTimeField(auto_now_add=True)
    can_edit      = models.BooleanField(default=False)
    can_sync      = models.BooleanField(default=True)
    can_export    = models.BooleanField(default=True)
    note          = models.CharField(max_length=300, blank=True)

    class Meta:
        unique_together = ('staff_profile', 'client')

    def __str__(self):
        return f"{self.staff_profile.user.email} → {self.client.company}"


class ClientPageConfig(models.Model):
    client               = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='page_config')
    portal_title         = models.CharField(max_length=200, default='My Dashboard')
    show_platform_tabs   = models.BooleanField(default=True)
    show_date_picker     = models.BooleanField(default=True)
    show_export_button   = models.BooleanField(default=True)
    show_sync_button     = models.BooleanField(default=False)
    show_posts_section   = models.BooleanField(default=True)
    show_reviews_section = models.BooleanField(default=False)
    show_roi_section     = models.BooleanField(default=False)
    show_calendar        = models.BooleanField(default=False)
    default_platform     = models.CharField(max_length=30, default='all')
    default_date_range   = models.IntegerField(default=30)
    custom_logo_url      = models.URLField(blank=True)
    custom_accent_color  = models.CharField(max_length=7, default='#2563EB')
    welcome_message      = models.TextField(blank=True)
    updated_at           = models.DateTimeField(auto_now=True)
    updated_by           = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_portal_configs')

    def __str__(self):
        return f"Portal config — {self.client.company}"


class CaptionRequest(models.Model):
    TONE_CHOICES = [
        ('professional', 'Professional'),
        ('casual', 'Casual'),
        ('funny', 'Funny'),
        ('inspirational', 'Inspirational'),
        ('urgent', 'Urgent'),
        ('friendly', 'Friendly'),
    ]
    POST_TYPE_CHOICES = [
        ('promotion', 'Promotion'),
        ('announcement', 'Announcement'),
        ('educational', 'Educational'),
        ('behind_scenes', 'Behind the Scenes'),
        ('product', 'Product Showcase'),
        ('event', 'Event'),
        ('tip', 'Tip & Advice'),
    ]

    client             = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='caption_requests')
    topic              = models.TextField()
    tone               = models.CharField(max_length=20, choices=TONE_CHOICES, default='professional')
    post_type          = models.CharField(max_length=20, choices=POST_TYPE_CHOICES, default='promotion')
    platforms          = models.JSONField(default=list)
    keywords           = models.TextField(blank=True, default='')
    call_to_action     = models.CharField(max_length=200, blank=True, default='')
    generated_captions = models.JSONField(default=dict)
    created_at         = models.DateTimeField(auto_now_add=True)
    created_by         = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.client.company} – {self.topic[:50]}"


# ── AI Post Ideas Generator ────────────────────────────────────────────────────

BUSINESS_TYPE_CHOICES = [
    ('restaurant',   'Restaurant'),
    ('retail',       'Retail'),
    ('healthcare',   'Healthcare'),
    ('fitness',      'Fitness'),
    ('real_estate',  'Real Estate'),
    ('education',    'Education'),
    ('tech',         'Tech'),
    ('beauty',       'Beauty'),
    ('legal',        'Legal'),
    ('finance',      'Finance'),
    ('other',        'Other'),
]


class PostIdeaSet(models.Model):
    client          = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='post_idea_sets')
    month           = models.IntegerField()
    year            = models.IntegerField()
    business_type   = models.CharField(max_length=50, choices=BUSINESS_TYPE_CHOICES)
    location        = models.CharField(max_length=200, blank=True)
    upcoming_events = models.TextField(blank=True)
    target_audience = models.CharField(max_length=300, blank=True)
    platforms       = models.JSONField(default=list)
    ideas           = models.JSONField(default=dict)   # raw AI response
    posts_per_week  = models.IntegerField(default=5)
    generated_at    = models.DateTimeField(auto_now_add=True)
    generated_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_idea_sets')

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        import calendar
        month_name = calendar.month_name[self.month]
        return f"{self.client.company} | {month_name} {self.year}"


class PostIdea(models.Model):
    idea_set             = models.ForeignKey(PostIdeaSet, on_delete=models.CASCADE, related_name='post_ideas')
    week_number          = models.IntegerField()
    day_of_week          = models.CharField(max_length=20)
    scheduled_date       = models.DateField(null=True, blank=True)
    platform             = models.CharField(max_length=30)
    post_type            = models.CharField(max_length=30)
    topic                = models.CharField(max_length=500)
    caption_hint         = models.TextField()
    hashtag_hints        = models.JSONField(default=list)
    best_time            = models.CharField(max_length=50, blank=True)
    notes                = models.TextField(blank=True)
    is_approved          = models.BooleanField(default=False)
    is_added_to_calendar = models.BooleanField(default=False)
    converted_post       = models.ForeignKey(
        'CalendarPost', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='post_idea_source'
    )

    class Meta:
        ordering = ['scheduled_date', 'week_number', 'id']

    def __str__(self):
        return f"{self.idea_set.client.company} | {self.scheduled_date or self.day_of_week} | {self.topic[:50]}"


# ── AI Hashtag Research Tool ───────────────────────────────────────────────────

class HashtagSet(models.Model):
    PLATFORM_CHOICES = [
        ('instagram', 'Instagram'),
        ('facebook',  'Facebook'),
        ('linkedin',  'LinkedIn'),
        ('youtube',   'YouTube'),
    ]

    client      = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='hashtag_sets')
    niche       = models.CharField(max_length=200)
    location    = models.CharField(max_length=200, blank=True)
    platform    = models.CharField(max_length=30, choices=PLATFORM_CHOICES)
    hashtags    = models.JSONField(default=dict)   # full AI response
    saved_sets  = models.JSONField(default=list)   # [{name, tags, platform, created_at}]
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='generated_hashtag_sets'
    )

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.client.company} | {self.niche} | {self.platform}"


class SiteContent(models.Model):
    key = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=255)
    effective_date = models.DateField(null=True, blank=True)
    last_updated = models.DateField(null=True, blank=True)
    content = models.JSONField(default=dict, blank=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']
        verbose_name = 'Site Content'
        verbose_name_plural = 'Site Content'

    def __str__(self):
        return f"{self.key} — {self.title}"


class LookupCollection(models.Model):
    key = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=255)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return self.title


class LookupItem(models.Model):
    collection = models.ForeignKey(LookupCollection, on_delete=models.CASCADE, related_name='items')
    key = models.CharField(max_length=120)
    label = models.CharField(max_length=255)
    value = models.CharField(max_length=255, blank=True)
    parent_key = models.CharField(max_length=120, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['collection__key', 'sort_order', 'label']
        unique_together = [('collection', 'key')]

    def __str__(self):
        return f"{self.collection.key} — {self.label}"


# ── Client Invitation ─────────────────────────────────────────────────────────
INVITATION_STATUS_CHOICES = [
    ('pending',   'Pending'),
    ('accepted',  'Accepted'),
    ('rejected',  'Rejected'),
    ('cancelled', 'Cancelled'),
    ('expired',   'Expired'),
]

class ClientInvitation(models.Model):
    invited_by    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    client_user   = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='received_invitations')
    client_email  = models.EmailField()
    client_record = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name='invitations')
    token         = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status        = models.CharField(max_length=20, choices=INVITATION_STATUS_CHOICES, default='pending')
    message       = models.TextField(blank=True)
    invited_at    = models.DateTimeField(auto_now_add=True)
    responded_at  = models.DateTimeField(null=True, blank=True)
    expires_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-invited_at']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return self.status == 'pending' and timezone.now() > self.expires_at

    def __str__(self):
        return f"Invitation from {self.invited_by.email} to {self.client_email} ({self.status})"


# ── Notification ──────────────────────────────────────────────────────────────
NOTIF_TYPE_CHOICES = [
    ('invitation_received',  'Invitation Received'),
    ('invitation_accepted',  'Invitation Accepted'),
    ('invitation_rejected',  'Invitation Rejected'),
    ('invitation_cancelled', 'Invitation Cancelled'),
    # Marketplace
    ('manage_request_received',  'Manage Request Received'),
    ('manage_request_accepted',  'Manage Request Accepted'),
    ('manage_request_declined',  'Manage Request Declined'),
    ('manage_request_cancelled', 'Manage Request Cancelled'),
    ('system',                   'System'),
]

class Notification(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    client     = models.ForeignKey('Client', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    notif_type = models.CharField(max_length=30, choices=NOTIF_TYPE_CHOICES, default='system')
    title      = models.CharField(max_length=200)
    body       = models.TextField(blank=True)
    data       = models.JSONField(default=dict, blank=True)
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'client', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.title}"


# ── WhatsApp (Pinbot integration) ─────────────────────────────────────────────

WA_QUALITY_CHOICES = [
    ('GREEN',   'Green'),
    ('YELLOW',  'Yellow'),
    ('RED',     'Red'),
    ('UNKNOWN', 'Unknown'),
]

WA_TIER_CHOICES = [
    ('TIER_1K',       '1,000 / 24h'),
    ('TIER_10K',      '10,000 / 24h'),
    ('TIER_100K',     '100,000 / 24h'),
    ('TIER_UNLIMITED','Unlimited'),
]

WA_OPT_IN_CHOICES = [
    ('pending',    'Pending'),
    ('opted_in',   'Opted In'),
    ('opted_out',  'Opted Out'),
]

WA_TEMPLATE_CATEGORY_CHOICES = [
    ('marketing',      'Marketing'),
    ('utility',        'Utility'),
    ('authentication', 'Authentication'),
]

WA_TEMPLATE_TYPE_CHOICES = [
    ('text',     'Text'),
    ('image',    'Image'),
    ('video',    'Video'),
    ('document', 'Document'),
    ('location', 'Location'),
    ('carousel', 'Carousel'),
    ('coupon',   'Coupon'),
    ('mpm',      'Multi-Product Message'),
    ('lto',      'Limited-Time Offer'),
]

WA_TEMPLATE_STATUS_CHOICES = [
    ('draft',    'Draft'),
    ('pending',  'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('paused',   'Paused'),
]

WA_CAMPAIGN_STATUS_CHOICES = [
    ('draft',     'Draft'),
    ('scheduled', 'Scheduled'),
    ('running',   'Running'),
    ('completed', 'Completed'),
    ('failed',    'Failed'),
    ('cancelled', 'Cancelled'),
    ('paused',    'Paused'),
]

WA_MESSAGE_STATUS_CHOICES = [
    ('queued',    'Queued'),
    ('sent',      'Sent'),
    ('delivered', 'Delivered'),
    ('read',      'Read'),
    ('failed',    'Failed'),
]

WA_DIRECTION_CHOICES = [
    ('outbound', 'Outbound'),
    ('inbound',  'Inbound'),
]


class WhatsAppAccount(models.Model):
    """Pinbot WABA (WhatsApp Business Account) configured per Client."""
    client            = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='whatsapp_account')
    waba_id           = models.CharField(max_length=100)
    phone_number_id   = models.CharField(max_length=100)
    phone_number      = models.CharField(max_length=30, blank=True)
    api_key_encrypted = models.BinaryField(blank=True, null=True)
    display_name      = models.CharField(max_length=200, blank=True)
    is_active         = models.BooleanField(default=True)
    quality_rating    = models.CharField(max_length=10, choices=WA_QUALITY_CHOICES, default='UNKNOWN')
    messaging_tier    = models.CharField(max_length=20, choices=WA_TIER_CHOICES, default='TIER_1K')
    last_synced_at    = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.client.company} — WhatsApp ({self.phone_number or self.phone_number_id})"

    # ── api_key encryption (Fernet via settings.WHATSAPP_ENCRYPTION_KEY) ──
    @property
    def api_key(self):
        if not self.api_key_encrypted:
            return ''
        from cryptography.fernet import Fernet
        from django.conf import settings
        key = settings.WHATSAPP_ENCRYPTION_KEY
        if not key:
            return ''
        f = Fernet(key.encode() if isinstance(key, str) else key)
        try:
            return f.decrypt(bytes(self.api_key_encrypted)).decode()
        except Exception:
            return ''

    @api_key.setter
    def api_key(self, value):
        if not value:
            self.api_key_encrypted = b''
            return
        from cryptography.fernet import Fernet
        from django.conf import settings
        key = settings.WHATSAPP_ENCRYPTION_KEY
        if not key:
            raise ValueError('WHATSAPP_ENCRYPTION_KEY is not configured')
        f = Fernet(key.encode() if isinstance(key, str) else key)
        self.api_key_encrypted = f.encrypt(value.encode())


class WhatsAppContact(models.Model):
    client          = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='whatsapp_contacts')
    phone           = models.CharField(max_length=20, db_index=True)
    name            = models.CharField(max_length=200, blank=True)
    email           = models.EmailField(blank=True)
    tags            = models.JSONField(default=list, blank=True)
    custom_fields   = models.JSONField(default=dict, blank=True)
    opt_in_status   = models.CharField(max_length=20, choices=WA_OPT_IN_CHOICES, default='pending')
    opt_in_source   = models.CharField(max_length=100, blank=True)
    opt_in_at       = models.DateTimeField(null=True, blank=True)
    opt_in_evidence = models.JSONField(default=dict, blank=True)
    opt_out_at      = models.DateTimeField(null=True, blank=True)
    opt_out_keyword = models.CharField(max_length=40, blank=True)  # what they typed to opt out
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_inbound_at = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    # ── Canonical Bop Universe Identity ──────────────────────────
    bop_contact_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Canonical Bop Universe contact identifier (UUIDv4).",
    )

    def save(self, *args, **kwargs):
        if not self.bop_contact_id:
            self.bop_contact_id = uuid.uuid4()
        elif self.pk:
            orig = WhatsAppContact.objects.filter(pk=self.pk).values('bop_contact_id').first()
            if orig and orig['bop_contact_id'] and str(orig['bop_contact_id']) != str(self.bop_contact_id):
                raise ValueError("bop_contact_id is immutable once assigned.")
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ('client', 'phone')
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['client', 'opt_in_status']),
        ]

    def __str__(self):
        return f"{self.name or self.phone} ({self.client.company})"

    @property
    def within_24h_window(self):
        """True if a free-form (non-template) message can be sent right now."""
        if not self.last_inbound_at:
            return False
        return (timezone.now() - self.last_inbound_at) < timedelta(hours=24)


class WhatsAppContactList(models.Model):
    client      = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='whatsapp_lists')
    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    contacts    = models.ManyToManyField(WhatsAppContact, related_name='lists', blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.client.company})"


class WhatsAppTemplate(models.Model):
    client             = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='whatsapp_templates')
    name               = models.CharField(max_length=100, help_text='Lowercase slug-like, e.g. order_confirmation')
    category           = models.CharField(max_length=20, choices=WA_TEMPLATE_CATEGORY_CHOICES, default='marketing')
    language           = models.CharField(max_length=20, default='en_US')
    template_type      = models.CharField(max_length=20, choices=WA_TEMPLATE_TYPE_CHOICES, default='text')
    header             = models.JSONField(default=dict, blank=True)
    body               = models.TextField()
    footer             = models.CharField(max_length=200, blank=True)
    buttons            = models.JSONField(default=list, blank=True)
    pinbot_template_id = models.CharField(max_length=200, blank=True)
    status             = models.CharField(max_length=20, choices=WA_TEMPLATE_STATUS_CHOICES, default='draft')
    rejection_reason   = models.TextField(blank=True)
    variables_count    = models.IntegerField(default=0)
    created_by         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_wa_templates')
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('client', 'name', 'language')
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.language}) — {self.client.company}"

    def save(self, *args, **kwargs):
        # Auto-calculate variable count from body placeholders {{1}}, {{2}}, ...
        import re
        if self.body:
            placeholders = re.findall(r'\{\{(\d+)\}\}', self.body)
            self.variables_count = len(set(placeholders))
        super().save(*args, **kwargs)


class WhatsAppCampaign(models.Model):
    client             = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='whatsapp_campaigns')
    name               = models.CharField(max_length=200)
    template           = models.ForeignKey(WhatsAppTemplate, on_delete=models.PROTECT, related_name='campaigns')
    contact_list       = models.ForeignKey(WhatsAppContactList, on_delete=models.PROTECT, related_name='campaigns')
    template_variables = models.JSONField(default=dict, blank=True, help_text='Mapping of {{n}} → value or {{n}} → contact field')
    scheduled_at       = models.DateTimeField(null=True, blank=True)
    started_at         = models.DateTimeField(null=True, blank=True)
    completed_at       = models.DateTimeField(null=True, blank=True)
    status             = models.CharField(max_length=20, choices=WA_CAMPAIGN_STATUS_CHOICES, default='draft')
    total_count        = models.IntegerField(default=0)
    sent_count         = models.IntegerField(default=0)
    delivered_count    = models.IntegerField(default=0)
    read_count         = models.IntegerField(default=0)
    failed_count       = models.IntegerField(default=0)
    created_by         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_wa_campaigns')
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.status}) — {self.client.company}"

    @property
    def progress_percent(self):
        if not self.total_count:
            return 0
        terminal = self.delivered_count + self.read_count + self.failed_count
        return int(round((terminal / self.total_count) * 100))


class WhatsAppMessage(models.Model):
    client            = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='whatsapp_messages')
    campaign          = models.ForeignKey(WhatsAppCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    contact           = models.ForeignKey(WhatsAppContact, on_delete=models.CASCADE, related_name='messages')
    pinbot_message_id = models.CharField(max_length=200, blank=True, db_index=True)
    direction         = models.CharField(max_length=10, choices=WA_DIRECTION_CHOICES, default='outbound')
    message_type      = models.CharField(max_length=30, default='text')
    payload           = models.JSONField(default=dict, blank=True)
    status            = models.CharField(max_length=15, choices=WA_MESSAGE_STATUS_CHOICES, default='queued')
    error_code        = models.CharField(max_length=50, blank=True)
    error_message     = models.TextField(blank=True)
    sent_at           = models.DateTimeField(null=True, blank=True)
    delivered_at      = models.DateTimeField(null=True, blank=True)
    read_at           = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['contact', '-created_at']),
        ]

    def __str__(self):
        return f"{self.direction} → {self.contact.phone} | {self.status}"


class AdsWaitlist(models.Model):
    """Email signups for the upcoming Ads module."""
    email      = models.EmailField()
    source     = models.CharField(max_length=50, blank=True, help_text='Where the signup came from')
    user       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ads_waitlist')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['email'])]

    def __str__(self):
        return f"{self.email} ({self.created_at:%Y-%m-%d})"


class WhatsAppWebhookLog(models.Model):
    client     = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='whatsapp_webhooks')
    event_type = models.CharField(max_length=100, default='unknown')
    payload    = models.JSONField(default=dict, blank=True)
    processed  = models.BooleanField(default=False)
    error      = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['processed', '-created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} | {'✓' if self.processed else '○'} | {self.created_at:%Y-%m-%d %H:%M}"


# ══════════════════════════════════════════════════════════════════════════════
# UNIFIED CONTROL CENTER — Composer + Inbox + Engagement + Automation
# ══════════════════════════════════════════════════════════════════════════════

# ── Choice tuples ─────────────────────────────────────────────────────────────
UNIFIED_POST_STATUS_CHOICES = [
    ('draft',             'Draft'),
    ('pending_approval',  'Pending Approval'),
    ('scheduled',         'Scheduled'),
    ('queued',            'Queued'),
    ('publishing',        'Publishing'),
    ('published',         'Published'),
    ('partial',           'Partially Published'),
    ('failed',            'Failed'),
    ('cancelled',         'Cancelled'),
]

UNIFIED_MEDIA_TYPE_CHOICES = [
    ('text',     'Text only'),
    ('image',    'Image'),
    ('video',    'Video'),
    ('carousel', 'Carousel'),
    ('reel',     'Reel'),
    ('story',    'Story'),
]

PUBLISH_LOG_STATUS_CHOICES = [
    ('pending',    'Pending'),
    ('publishing', 'Publishing'),
    ('success',    'Success'),
    ('failed',     'Failed'),
    ('skipped',    'Skipped'),
]

CONVERSATION_TYPE_CHOICES = [
    ('comment',  'Comment'),
    ('dm',       'Direct message'),
    ('mention',  'Mention'),
    ('review',   'Review'),
]

MESSAGE_DIRECTION_CHOICES = [
    ('inbound',  'Inbound'),
    ('outbound', 'Outbound'),
]

SENTIMENT_CHOICES = [
    ('positive', 'Positive'),
    ('neutral',  'Neutral'),
    ('negative', 'Negative'),
    ('unknown',  'Unknown'),
]

QUEUE_STRATEGY_CHOICES = [
    ('round_robin', 'Round robin'),
    ('random',      'Random'),
    ('sequential',  'Sequential'),
]

QUEUED_ITEM_STATUS_CHOICES = [
    ('waiting', 'Waiting'),
    ('used',    'Used'),
    ('skipped', 'Skipped'),
]

REVIEW_STATUS_CHOICES = [
    ('new',     'New'),
    ('replied', 'Replied'),
    ('flagged', 'Flagged'),
]

AUTOMATION_TRIGGER_CHOICES = [
    ('new_comment',         'New comment'),
    ('new_dm',              'New direct message'),
    ('new_review',          'New review'),
    ('keyword_mention',     'Keyword mention'),
    ('negative_sentiment',  'Negative sentiment detected'),
    ('viral_post',          'Post going viral'),
    ('new_follower',        'New follower'),
]

AUTOMATION_ACTION_CHOICES = [
    ('auto_reply',     'Auto-reply'),
    ('ai_smart_reply', 'AI smart reply'),
    ('notify',         'Send notification'),
    ('assign',         'Assign to user'),
    ('add_tag',        'Add tag'),
    ('webhook',        'Call webhook'),
]


# ── Composer & Publishing ─────────────────────────────────────────────────────
def media_asset_upload_path(instance, filename):
    now = timezone.now()
    client_id = getattr(instance, 'client_id', None) or 'shared'
    return f"media_assets/tenant_{client_id}/{now.year:04d}/{now.month:02d}/{filename}"


def media_asset_thumb_upload_path(instance, filename):
    now = timezone.now()
    client_id = getattr(instance, 'client_id', None) or 'shared'
    return f"media_assets/thumbs/tenant_{client_id}/{now.year:04d}/{now.month:02d}/{filename}"


class MediaAsset(models.Model):
    """Uploaded media library — photos, videos, gifs available to the composer."""
    client       = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='media_assets')
    uploaded_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_media')
    file         = models.FileField(upload_to=media_asset_upload_path)
    thumbnail    = models.ImageField(upload_to=media_asset_thumb_upload_path, null=True, blank=True)
    mime_type    = models.CharField(max_length=100, blank=True)
    file_size    = models.BigIntegerField(default=0)
    width        = models.IntegerField(default=0)
    height       = models.IntegerField(default=0)
    duration_seconds = models.FloatField(default=0)
    alt_text     = models.CharField(max_length=500, blank=True)
    tags         = models.JSONField(default=list, blank=True)
    folder       = models.CharField(max_length=100, blank=True)
    technical_metadata = models.JSONField(default=dict, blank=True)
    is_used      = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['client', 'folder']),
        ]

    def __str__(self):
        return f"{self.client.company} — {self.file.name}"

    def get_authorized_url(self, request=None, thumb=False) -> str:
        from .media_access import generate_media_asset_url
        return generate_media_asset_url(self, request=request, thumb=thumb)

    def get_public_publishing_url(self, expires_in=172800) -> str:
        from .media_access import generate_public_publishing_token
        from django.conf import settings
        token = generate_public_publishing_token(self.id, self.client_id, max_age=expires_in)
        base = (getattr(settings, 'BACKEND_PUBLIC_URL', '') or getattr(settings, 'FRONTEND_URL', '')).rstrip('/')
        return f"{base}/api/media/public/{token}/"

    def delete(self, *args, **kwargs):
        from . import media_service
        if media_service._s3_enabled():
            if self.file and self.file.name:
                media_service.delete_s3_object(self.file.name)
            if self.thumbnail and self.thumbnail.name:
                media_service.delete_s3_object(self.thumbnail.name)
        else:
            if self.file:
                self.file.delete(save=False)
            if self.thumbnail:
                self.thumbnail.delete(save=False)
        return super().delete(*args, **kwargs)


class UnifiedPost(models.Model):
    """A post composed in Social Stats, fanned out to one or more platforms."""
    client            = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='unified_posts')
    created_by        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_unified_posts')
    title             = models.CharField(max_length=200, blank=True, help_text='Optional internal label')
    content           = models.TextField(blank=True)
    media_urls        = models.JSONField(default=list, blank=True, help_text='Ordered list of media URLs')
    media_assets      = models.ManyToManyField(MediaAsset, blank=True, related_name='used_in_posts')
    media_type        = models.CharField(max_length=20, choices=UNIFIED_MEDIA_TYPE_CHOICES, default='text')
    target_platforms  = models.JSONField(default=list, blank=True, help_text='List of platform keys to publish to')
    platform_overrides = models.JSONField(default=dict, blank=True, help_text='{platform: {content, media_urls, hashtags}}')
    status            = models.CharField(max_length=20, choices=UNIFIED_POST_STATUS_CHOICES, default='draft')
    scheduled_at      = models.DateTimeField(null=True, blank=True)
    queued_at         = models.DateTimeField(null=True, blank=True)
    published_at      = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)
    ai_generated      = models.BooleanField(default=False)
    ai_prompt         = models.TextField(blank=True)
    is_recurring      = models.BooleanField(default=False)
    recurrence_rule   = models.CharField(max_length=500, blank=True, help_text='RFC 5545 RRULE')
    approved_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_unified_posts')
    approved_at       = models.DateTimeField(null=True, blank=True)
    source_queue      = models.ForeignKey('social_stats.PostQueue', on_delete=models.SET_NULL, null=True, blank=True, related_name='unified_posts')
    source_queued_item = models.ForeignKey('social_stats.QueuedItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='materialized_posts')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['status', 'scheduled_at']),
        ]

    def __str__(self):
        return f"{self.client.company} | {self.status} | {self.title or self.content[:40]}"


class PlatformPublishLog(models.Model):
    """One row per (UnifiedPost × target platform) — tracks per-platform outcome."""
    unified_post       = models.ForeignKey(UnifiedPost, on_delete=models.CASCADE, related_name='publish_logs')
    platform           = models.CharField(max_length=30, choices=PLATFORM_CHOICES)
    status             = models.CharField(max_length=20, choices=PUBLISH_LOG_STATUS_CHOICES, default='pending')
    platform_post_id   = models.CharField(max_length=300, blank=True, db_index=True)
    platform_url       = models.URLField(blank=True)
    error_code         = models.CharField(max_length=80, blank=True)
    error_message      = models.TextField(blank=True)
    attempted_at       = models.DateTimeField(null=True, blank=True)
    completed_at       = models.DateTimeField(null=True, blank=True)
    engagement_synced_at = models.DateTimeField(null=True, blank=True)
    raw_response       = models.JSONField(default=dict, blank=True)

    # BS-3I Traceability & Provider Reconciliation
    provider_request_id    = models.CharField(max_length=255, blank=True, default='', db_index=True)
    provider_container_id  = models.CharField(max_length=255, blank=True, default='', db_index=True)
    provider_attempt_token = models.CharField(max_length=100, blank=True, default='')

    # BS-3J Ambiguous Provider Reconciliation
    last_reconciled_at           = models.DateTimeField(null=True, blank=True)
    reconciliation_status        = models.CharField(max_length=50, blank=True, default='')
    reconciliation_evidence_type = models.CharField(max_length=80, blank=True, default='')
    reconciliation_reference     = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        unique_together = ('unified_post', 'platform')
        ordering = ['-attempted_at']
        indexes = [
            models.Index(fields=['platform', 'platform_post_id']),
            models.Index(fields=['unified_post', 'status']),
        ]

    def __str__(self):
        return f"{self.unified_post_id} → {self.platform} ({self.status})"


class PostEngagement(models.Model):
    """Live engagement counters for a published post (refreshed periodically)."""
    publish_log    = models.OneToOneField(PlatformPublishLog, on_delete=models.CASCADE, related_name='engagement')
    likes          = models.BigIntegerField(default=0)
    comments       = models.BigIntegerField(default=0)
    shares         = models.BigIntegerField(default=0)
    saves          = models.BigIntegerField(default=0)
    reach          = models.BigIntegerField(default=0)
    impressions    = models.BigIntegerField(default=0)
    video_views    = models.BigIntegerField(default=0)
    watch_time_seconds = models.BigIntegerField(default=0)
    click_throughs = models.BigIntegerField(default=0)
    pulled_at      = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Engagement — {self.publish_log}"


# ── Canonical Analytics Foundation (BS-4B) ───────────────────────────────────

METRIC_SCOPE_CHOICES = [
    ('account',  'Account / Page'),
    ('post',     'Post / Media'),
    ('story',    'Story'),
    ('reel',     'Reel'),
    ('video',    'Video'),
    ('campaign', 'Campaign / Tag'),
]

BUCKET_PERIOD_CHOICES = [
    ('hour',     'Hour'),
    ('day',      'Day'),
    ('month',    'Month'),
    ('lifetime', 'Lifetime'),
]

ROLLUP_PERIOD_CHOICES = [
    ('day',   'Day'),
    ('week',  'Week'),
    ('month', 'Month'),
    ('year',  'Year'),
]

FRESHNESS_STATE_CHOICES = [
    ('FRESH',       'Fresh'),
    ('AGING',       'Aging'),
    ('STALE',       'Stale'),
    ('UNAVAILABLE', 'Unavailable'),
]


class SocialMetricSnapshot(models.Model):
    """
    Durable, idempotent observation snapshot for social analytics telemetry.
    Supports provider-native raw metrics, canonical normalized metrics,
    deterministic dimension hashing, and optional UnifiedPost linking.
    """
    client        = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='metric_snapshots', db_index=True)
    platform      = models.CharField(max_length=30, choices=PLATFORM_CHOICES, db_index=True)
    account_id    = models.CharField(max_length=120, blank=True, db_index=True)
    metric_scope  = models.CharField(max_length=20, choices=METRIC_SCOPE_CHOICES, db_index=True)
    object_id     = models.CharField(max_length=255, db_index=True)

    unified_post  = models.ForeignKey(
        'social_stats.UnifiedPost',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='metric_snapshots',
    )
    publish_log   = models.ForeignKey(
        'social_stats.PlatformPublishLog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='metric_snapshots',
    )

    raw_metric_name   = models.CharField(max_length=100)
    normalized_metric = models.CharField(max_length=60, db_index=True)
    metric_value      = models.DecimalField(max_digits=20, decimal_places=4, default=0)

    extra_dimensions  = models.JSONField(default=dict, blank=True)
    dimensions_hash   = models.CharField(max_length=64, default='', db_index=True)

    bucket_period     = models.CharField(max_length=20, choices=BUCKET_PERIOD_CHOICES, default='day')
    bucket_timestamp  = models.DateTimeField(db_index=True)

    provider_timestamp = models.DateTimeField(null=True, blank=True)
    captured_at        = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at         = models.DateTimeField(auto_now=True)

    freshness_state    = models.CharField(max_length=20, choices=FRESHNESS_STATE_CHOICES, default='FRESH')
    is_derived         = models.BooleanField(default=False)
    metadata           = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-bucket_timestamp']
        unique_together = (
            'client',
            'platform',
            'metric_scope',
            'object_id',
            'normalized_metric',
            'dimensions_hash',
            'bucket_period',
            'bucket_timestamp',
        )
        indexes = [
            models.Index(fields=['client', 'platform', 'bucket_timestamp']),
            models.Index(fields=['client', 'normalized_metric', 'bucket_timestamp']),
            models.Index(fields=['platform', 'object_id']),
            models.Index(fields=['unified_post']),
        ]

    def __str__(self):
        return f"{self.client_id} | {self.platform} | {self.normalized_metric} = {self.metric_value} ({self.bucket_period} @ {self.bucket_timestamp:%Y-%m-%d %H:%M})"

    def clean(self):
        super().clean()
        if self.unified_post_id and self.unified_post.client_id != self.client_id:
            raise ValidationError("unified_post must belong to the same client as snapshot.")
        if self.publish_log_id and self.publish_log.unified_post.client_id != self.client_id:
            raise ValidationError("publish_log must belong to the same client as snapshot.")


class SocialMetricRollup(models.Model):
    """
    Materialized, derivable rollup cache for high-speed client dashboard queries.
    Always rebuildable from SocialMetricSnapshot source-of-truth observations.
    """
    client        = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='metric_rollups', db_index=True)
    platform      = models.CharField(max_length=30, choices=PLATFORM_CHOICES, db_index=True)
    metric_scope  = models.CharField(max_length=20, choices=METRIC_SCOPE_CHOICES, db_index=True)
    object_id     = models.CharField(max_length=255, blank=True, default='', db_index=True)

    normalized_metric = models.CharField(max_length=60, db_index=True)
    dimensions_hash   = models.CharField(max_length=64, default='', db_index=True)

    period        = models.CharField(max_length=20, choices=ROLLUP_PERIOD_CHOICES)
    period_start  = models.DateField(db_index=True)

    metric_value  = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    extra_dimensions = models.JSONField(default=dict, blank=True)
    sample_count  = models.IntegerField(default=1)

    computed_at   = models.DateTimeField(auto_now=True)
    metadata      = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-period_start']
        unique_together = (
            'client',
            'platform',
            'metric_scope',
            'object_id',
            'normalized_metric',
            'dimensions_hash',
            'period',
            'period_start',
        )
        indexes = [
            models.Index(fields=['client', 'platform', 'period', 'period_start']),
            models.Index(fields=['client', 'normalized_metric', 'period_start']),
        ]

    def __str__(self):
        return f"{self.client_id} | {self.platform} | {self.normalized_metric} = {self.metric_value} ({self.period} @ {self.period_start})"


# ── BS-4F Deterministic Business Intelligence Foundation ───────────────────────
SIGNAL_DIRECTION_CHOICES = [
    ('UP', 'Up'),
    ('DOWN', 'Down'),
    ('NEUTRAL', 'Neutral'),
    ('FLAT', 'Flat'),
]

SIGNAL_SEVERITY_CHOICES = [
    ('INFO', 'Info'),
    ('POSITIVE', 'Positive'),
    ('WARNING', 'Warning'),
    ('CRITICAL', 'Critical'),
]

CONFIDENCE_LEVEL_CHOICES = [
    ('LOW', 'Low'),
    ('MEDIUM', 'Medium'),
    ('HIGH', 'High'),
    ('NONE', 'None'),
]


class BusinessSignal(models.Model):
    """
    Deterministic, explainable business intelligence signal derived from
    normalized analytics rollups and snapshots without generative AI.
    """
    client        = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='business_signals', db_index=True)
    platform      = models.CharField(max_length=30, db_index=True)
    signal_type   = models.CharField(max_length=60, db_index=True)
    metric        = models.CharField(max_length=60, blank=True, db_index=True)
    scope         = models.CharField(max_length=30, default='account', db_index=True)
    object_id     = models.CharField(max_length=255, blank=True, default='', db_index=True)
    unified_post  = models.ForeignKey('UnifiedPost', null=True, blank=True, on_delete=models.SET_NULL, related_name='business_signals')

    period_start  = models.DateField(db_index=True)
    period_end    = models.DateField(db_index=True)

    observed_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    baseline_value = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    absolute_delta = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    relative_delta = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)

    sample_size      = models.IntegerField(default=0)
    confidence_level = models.CharField(max_length=20, choices=CONFIDENCE_LEVEL_CHOICES, default='NONE')

    direction     = models.CharField(max_length=20, choices=SIGNAL_DIRECTION_CHOICES, default='NEUTRAL')
    severity      = models.CharField(max_length=20, choices=SIGNAL_SEVERITY_CHOICES, default='INFO')

    is_actionable = models.BooleanField(default=False)

    evidence              = models.JSONField(default=dict, blank=True)
    explanation_template  = models.TextField(blank=True)
    metadata              = models.JSONField(default=dict, blank=True)
    cohort_hash           = models.CharField(max_length=64, blank=True, default='')

    # Stable identity key ensuring zero duplicate signals
    signal_identity = models.CharField(max_length=128, unique=True, db_index=True)

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-period_end', '-created_at']
        indexes = [
            models.Index(fields=['client', 'signal_type', 'period_end']),
            models.Index(fields=['client', 'platform', 'period_end']),
            models.Index(fields=['client', 'severity']),
            models.Index(fields=['client', 'confidence_level']),
        ]

    def __str__(self):
        return f"{self.client_id} | {self.signal_type} | {self.platform} ({self.confidence_level}) @ {self.period_end}"


REPORT_TYPE_CHOICES = [
    ('EXECUTIVE', 'Executive Summary'),
    ('MONTHLY', 'Monthly Performance'),
    ('WEEKLY', 'Weekly Digest'),
    ('CUSTOM', 'Custom Period'),
]

REPORT_STATUS_CHOICES = [
    ('DRAFT', 'Draft'),
    ('GENERATED', 'Generated'),
    ('FAILED', 'Failed'),
]

NARRATIVE_STATUS_CHOICES = [
    ('DRAFT', 'Draft'),
    ('GENERATED', 'Generated'),
    ('VALIDATED', 'Validated'),
    ('REJECTED', 'Rejected'),
    ('FAILED', 'Failed'),
]


class ExecutiveReport(models.Model):
    """
    Deterministic client-facing executive report capturing structured analytics,
    business intelligence signals, and rendered PDF artifact metadata.
    """
    client               = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='executive_reports', db_index=True)
    report_type          = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, default='EXECUTIVE', db_index=True)
    period_start         = models.DateField(db_index=True)
    period_end           = models.DateField(db_index=True)
    platform_filter      = models.CharField(max_length=30, blank=True, null=True, default=None)
    language             = models.CharField(max_length=10, default='es')
    status               = models.CharField(max_length=20, choices=REPORT_STATUS_CHOICES, default='GENERATED', db_index=True)
    title                = models.CharField(max_length=255)

    generated_at         = models.DateTimeField(default=timezone.now)
    generated_by         = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='generated_executive_reports')

    source_rollup_count  = models.IntegerField(default=0)
    source_signal_count  = models.IntegerField(default=0)
    source_hash          = models.CharField(max_length=64, db_index=True)

    report_data          = models.JSONField(default=dict)
    pdf_file             = models.FileField(upload_to='reports/executive/%Y/%m/', null=True, blank=True)
    pdf_checksum         = models.CharField(max_length=64, null=True, blank=True)
    template_version     = models.CharField(max_length=20, default='bs4g-v1')
    metadata             = models.JSONField(default=dict, blank=True)

    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-period_end', '-generated_at']
        indexes = [
            models.Index(fields=['client', 'report_type', 'period_end']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['client', 'source_hash']),
        ]

    def __str__(self):
        return f"ExecutiveReport #{self.id} | {self.client_id} | {self.title} ({self.period_start} to {self.period_end})"


class ExecutiveNarrative(models.Model):
    """
    Grounded client-facing narrative and recommendations generated from deterministic
    ExecutiveReport.report_data and BusinessSignal evidence, validated against hallucinations,
    unsupported causality, and unobserved metrics.
    """
    client                 = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='executive_narratives', db_index=True)
    executive_report       = models.ForeignKey(ExecutiveReport, on_delete=models.CASCADE, related_name='narratives', db_index=True)
    language               = models.CharField(max_length=10, default='es')
    status                 = models.CharField(max_length=20, choices=NARRATIVE_STATUS_CHOICES, default='DRAFT', db_index=True)

    provider               = models.CharField(max_length=50, default='fake')
    model_name             = models.CharField(max_length=100, default='stub-model-v1')
    prompt_version         = models.CharField(max_length=50, default='bs4h-prompt-v1')
    context_schema_version = models.CharField(max_length=50, default='bs4h-context-v1')

    source_hash            = models.CharField(max_length=64, db_index=True)
    context_hash           = models.CharField(max_length=64, db_index=True)

    narrative_json         = models.JSONField(default=dict)
    rendered_text          = models.TextField(blank=True, default='')
    validation_status      = models.CharField(max_length=20, default='PENDING')  # PENDING, PASS, FAIL
    validation_results     = models.JSONField(default=dict, blank=True)

    generated_at           = models.DateTimeField(default=timezone.now)
    created_by             = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_executive_narratives')
    metadata               = models.JSONField(default=dict, blank=True)

    created_at             = models.DateTimeField(auto_now_add=True)
    updated_at             = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['executive_report', '-created_at']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['source_hash']),
            models.Index(fields=['context_hash']),
        ]

    def __str__(self):
        return f"ExecutiveNarrative #{self.id} | Report #{self.executive_report_id} | {self.status} | {self.provider}"

    @property
    def is_stale(self) -> bool:
        """Determines if the underlying report source_hash has changed since narrative generation."""
        if not self.executive_report:
            return True
        return self.source_hash != self.executive_report.source_hash


# ============================================================================
#  BS-6A Intelligence Automation & Scheduling Foundation
# ============================================================================

INTELLIGENCE_AUTOMATION_FREQUENCY_CHOICES = [
    ('MONTHLY', 'Monthly'),
    ('WEEKLY', 'Weekly'),
]

INTELLIGENCE_AUTOMATION_TRIGGER_CHOICES = [
    ('MANUAL', 'Manual'),
    ('SCHEDULED', 'Scheduled'),
    ('RETRY', 'Retry'),
    ('ADMIN', 'Admin'),
]

INTELLIGENCE_AUTOMATION_STATUS_CHOICES = [
    ('PENDING', 'Pending'),
    ('ELIGIBILITY_CHECK', 'Eligibility Check'),
    ('RUNNING', 'Running'),
    ('BLOCKED', 'Blocked'),
    ('FAILED', 'Failed'),
    ('COMPLETED', 'Completed'),
    ('CANCELLED', 'Cancelled'),
]

INTELLIGENCE_AUTOMATION_STAGE_CHOICES = [
    ('ELIGIBILITY', 'Eligibility'),
    ('SYNC_CHECK', 'Sync Check'),
    ('SNAPSHOT_CHECK', 'Snapshot Check'),
    ('ROLLUP_CHECK', 'Rollup Check'),
    ('SIGNAL_CHECK', 'Signal Check'),
    ('REPORT_CHECK', 'Report Check'),
    ('NARRATIVE_CHECK', 'Narrative Check'),
    ('COMPLETE', 'Complete'),
]

INTELLIGENCE_AUTOMATION_FRESHNESS_CHOICES = [
    ('FRESH', 'Fresh (<=24h)'),
    ('AGING', 'Aging (<=48h)'),
]


class IntelligenceAutomationConfig(models.Model):
    """
    Tenant/Client-level configuration governing scheduled intelligence automation,
    reporting periods, data freshness requirements, provider-call budgets, and approval boundaries.
    """
    client                      = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='intelligence_automation_config', db_index=True)
    enabled                     = models.BooleanField(default=False, db_index=True)
    timezone                    = models.CharField(max_length=64, default='America/New_York')
    reporting_frequency         = models.CharField(max_length=20, choices=INTELLIGENCE_AUTOMATION_FREQUENCY_CHOICES, default='MONTHLY', db_index=True)
    reporting_day               = models.IntegerField(default=1, help_text="Day of month (1-31) or weekday (0=Mon..6=Sun)")
    reporting_hour              = models.IntegerField(default=6, help_text="Reporting hour in tenant timezone (0-23)")
    lookback_days               = models.IntegerField(default=30, help_text="Lookback days window for analytics aggregation")
    minimum_data_freshness      = models.CharField(max_length=20, choices=INTELLIGENCE_AUTOMATION_FRESHNESS_CHOICES, default='FRESH')
    max_data_staleness_hours    = models.IntegerField(default=24, help_text="Max acceptable staleness in hours")
    generate_report             = models.BooleanField(default=True)
    generate_narrative          = models.BooleanField(default=False)
    require_operator_approval   = models.BooleanField(default=True)
    provider_call_budget        = models.IntegerField(default=1, help_text="Max provider LLM calls permitted per run")
    max_retry_count             = models.IntegerField(default=0, help_text="Max automatic retries permitted (default 0: fail-closed)")
    metadata                    = models.JSONField(default=dict, blank=True)
    created_at                  = models.DateTimeField(auto_now_add=True)
    updated_at                  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['client_id']
        verbose_name = 'Intelligence Automation Config'
        verbose_name_plural = 'Intelligence Automation Configs'

    def __str__(self):
        return f"IntelligenceAutomationConfig(client_id={self.client_id}, enabled={self.enabled}, freq={self.reporting_frequency})"


class IntelligenceAutomationRun(models.Model):
    """
    Durable execution record of a scheduled or manual intelligence automation pipeline run
    for one tenant, one reporting period, and one pipeline version.
    """
    client               = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='intelligence_automation_runs', db_index=True)
    agency_id            = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    period_start         = models.DateField(db_index=True)
    period_end           = models.DateField(db_index=True)
    pipeline_version     = models.CharField(max_length=50, default='bs6a-v1', db_index=True)
    execution_identity   = models.CharField(max_length=64, db_index=True)
    trigger_type         = models.CharField(max_length=20, choices=INTELLIGENCE_AUTOMATION_TRIGGER_CHOICES, default='MANUAL', db_index=True)
    status               = models.CharField(max_length=30, choices=INTELLIGENCE_AUTOMATION_STATUS_CHOICES, default='PENDING', db_index=True)
    current_stage        = models.CharField(max_length=30, choices=INTELLIGENCE_AUTOMATION_STAGE_CHOICES, default='ELIGIBILITY', db_index=True)
    started_at           = models.DateTimeField(null=True, blank=True)
    finished_at          = models.DateTimeField(null=True, blank=True)
    requested_by         = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='requested_automation_runs')
    dry_run              = models.BooleanField(default=False, db_index=True)
    provider_call_count  = models.IntegerField(default=0)
    retry_count          = models.IntegerField(default=0)
    fallback_count       = models.IntegerField(default=0)
    error_code           = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    error_message_safe   = models.TextField(blank=True, default='')
    report               = models.ForeignKey(ExecutiveReport, null=True, blank=True, on_delete=models.SET_NULL, related_name='automation_runs')
    narrative            = models.ForeignKey(ExecutiveNarrative, null=True, blank=True, on_delete=models.SET_NULL, related_name='automation_runs')
    metadata             = models.JSONField(default=dict, blank=True)
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['execution_identity']),
            models.Index(fields=['period_start', 'period_end']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['client', 'period_start', 'period_end', 'pipeline_version'],
                condition=models.Q(status__in=['PENDING', 'ELIGIBILITY_CHECK', 'RUNNING']),
                name='unique_active_intelligence_run',
            )
        ]

    def __str__(self):
        return f"AutomationRun #{self.id} | Client #{self.client_id} | {self.status} | {self.current_stage} | dry_run={self.dry_run}"


class PostQueue(models.Model):
    """A reusable schedule (e.g. 'every weekday 10am') that drains QueuedItems."""
    client          = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='post_queues')
    name            = models.CharField(max_length=200)
    platforms       = models.JSONField(default=list, blank=True)
    schedule_rule   = models.CharField(max_length=500, blank=True, help_text='RFC 5545 RRULE or simple cron')
    queue_strategy  = models.CharField(max_length=20, choices=QUEUE_STRATEGY_CHOICES, default='sequential')
    is_active       = models.BooleanField(default=True)
    last_dispatched_at = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.client.company} — {self.name}"

    def save(self, *args, **kwargs):
        if self.pk:
            orig = PostQueue.objects.filter(pk=self.pk).values('platforms').first()
            if orig and set(orig.get('platforms') or []) != set(self.platforms or []):
                self.items.filter(status='waiting').update(approved_by=None, approved_at=None)
        super().save(*args, **kwargs)


class QueuedItem(models.Model):
    """A pre-written post sitting in a PostQueue waiting to be dispatched."""
    queue        = models.ForeignKey(PostQueue, on_delete=models.CASCADE, related_name='items')
    content      = models.TextField(blank=True)
    media_urls   = models.JSONField(default=list, blank=True)
    hashtags     = models.JSONField(default=list, blank=True)
    sort_order   = models.IntegerField(default=0)
    status       = models.CharField(max_length=20, choices=QUEUED_ITEM_STATUS_CHOICES, default='waiting')
    used_at      = models.DateTimeField(null=True, blank=True)
    unified_post = models.ForeignKey(UnifiedPost, on_delete=models.SET_NULL, null=True, blank=True, related_name='source_queue_item')
    approved_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_queue_items')
    approved_at  = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['queue', 'sort_order', 'id']
        indexes = [models.Index(fields=['queue', 'status', 'sort_order'])]

    def __str__(self):
        return f"{self.queue.name} #{self.sort_order} ({self.status})"

    @property
    def is_approved(self) -> bool:
        return self.approved_by_id is not None and self.approved_at is not None

    def save(self, *args, **kwargs):
        if self.pk:
            orig = QueuedItem.objects.filter(pk=self.pk).values(
                'content', 'media_urls', 'hashtags', 'approved_by_id', 'approved_at',
            ).first()
            if orig and (orig['approved_by_id'] is not None or orig['approved_at'] is not None):
                content_changed = self.content != orig['content']
                media_changed = self.media_urls != orig['media_urls']
                hashtags_changed = self.hashtags != orig['hashtags']
                if content_changed or media_changed or hashtags_changed:
                    self.approved_by = None
                    self.approved_at = None
                    if 'update_fields' in kwargs and kwargs['update_fields'] is not None:
                        fields = set(kwargs['update_fields'])
                        fields.update(['approved_by', 'approved_at'])
                        kwargs['update_fields'] = list(fields)
        super().save(*args, **kwargs)


# ── Inbox & Engagement ────────────────────────────────────────────────────────
class Conversation(models.Model):
    """A thread on any platform — DM, comment thread, mention, or review."""
    client              = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='conversations')
    platform            = models.CharField(max_length=30, choices=PLATFORM_CHOICES)
    platform_thread_id  = models.CharField(max_length=300, db_index=True)
    type                = models.CharField(max_length=20, choices=CONVERSATION_TYPE_CHOICES, default='comment')
    contact_name        = models.CharField(max_length=200, blank=True)
    contact_handle      = models.CharField(max_length=200, blank=True)
    contact_avatar_url  = models.URLField(blank=True)
    last_message_preview = models.CharField(max_length=500, blank=True)
    last_message_at     = models.DateTimeField(null=True, blank=True)
    last_outbound_at    = models.DateTimeField(null=True, blank=True)
    unread_count        = models.IntegerField(default=0)
    is_starred          = models.BooleanField(default=False)
    is_archived         = models.BooleanField(default=False)
    is_resolved         = models.BooleanField(default=False)
    assigned_to         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_conversations')
    sentiment           = models.CharField(max_length=20, choices=SENTIMENT_CHOICES, default='unknown')
    linked_publish_log  = models.ForeignKey(PlatformPublishLog, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations')
    linked_flow         = models.ForeignKey('social_stats.BotFlow', on_delete=models.SET_NULL, null=True, blank=True, related_name='inbox_conversations')
    tags                = models.JSONField(default=list, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('client', 'platform', 'platform_thread_id')
        ordering = ['-last_message_at']
        indexes = [
            models.Index(fields=['client', '-last_message_at']),
            models.Index(fields=['client', 'is_archived', 'is_resolved']),
            models.Index(fields=['client', 'platform', 'type']),
        ]

    def __str__(self):
        return f"{self.client.company} | {self.platform} | {self.contact_handle or self.contact_name}"


class Message(models.Model):
    """An individual message inside a Conversation."""
    conversation         = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    platform_message_id  = models.CharField(max_length=300, blank=True, db_index=True)
    direction            = models.CharField(max_length=10, choices=MESSAGE_DIRECTION_CHOICES, default='inbound')
    author_name          = models.CharField(max_length=200, blank=True)
    author_handle        = models.CharField(max_length=200, blank=True)
    author_avatar_url    = models.URLField(blank=True)
    content              = models.TextField(blank=True)
    media_urls           = models.JSONField(default=list, blank=True)
    sent_at              = models.DateTimeField(null=True, blank=True)
    read_at              = models.DateTimeField(null=True, blank=True)
    replied_at           = models.DateTimeField(null=True, blank=True)
    sentiment            = models.CharField(max_length=20, choices=SENTIMENT_CHOICES, default='unknown')
    ai_suggested_reply   = models.TextField(blank=True)
    sent_by              = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_messages', help_text='User who composed an outbound reply')
    linked_bot_step      = models.ForeignKey('social_stats.BotConversationStep', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sent_at', 'id']
        indexes = [
            models.Index(fields=['conversation', 'sent_at']),
        ]

    def __str__(self):
        return f"{self.conversation_id} | {self.direction} | {self.content[:40]}"


class UnifiedReview(models.Model):
    """
    Cross-platform review (currently GMB; structured for future Yelp/TripAdvisor too).
    Distinct from the existing GMBReview so we can extend without disturbing the
    legacy GMB sync. New review syncs populate this; existing GMBReview stays.
    """
    client              = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='unified_reviews')
    platform            = models.CharField(max_length=30, choices=PLATFORM_CHOICES, default='google_my_business')
    platform_review_id  = models.CharField(max_length=300, db_index=True)
    reviewer_name       = models.CharField(max_length=200, blank=True)
    reviewer_avatar_url = models.URLField(blank=True)
    rating              = models.PositiveSmallIntegerField(default=5)
    comment             = models.TextField(blank=True)
    language            = models.CharField(max_length=10, blank=True)
    sentiment           = models.CharField(max_length=20, choices=SENTIMENT_CHOICES, default='unknown')
    status              = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='new')
    reply_text          = models.TextField(blank=True)
    replied_at          = models.DateTimeField(null=True, blank=True)
    replied_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='replied_reviews')
    created_at_platform = models.DateTimeField(null=True, blank=True)
    synced_at           = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('client', 'platform', 'platform_review_id')
        ordering = ['-created_at_platform']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['client', '-created_at_platform']),
        ]

    def __str__(self):
        return f"{self.client.company} | ★{self.rating} {self.reviewer_name}"


# ── AI & Automation ───────────────────────────────────────────────────────────
class BrandVoiceProfile(models.Model):
    """Per-client brand voice trained from sample posts; used by AI prompts."""
    TRAINING_STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('training', 'Training'),
        ('ready',    'Ready'),
        ('failed',   'Failed'),
    ]
    EMOJI_USAGE_CHOICES = [
        ('heavy',    'Heavy'),
        ('moderate', 'Moderate'),
        ('minimal',  'Minimal'),
        ('none',     'None'),
    ]

    client            = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='brand_voice')
    sample_posts      = models.JSONField(default=list, blank=True, help_text='List of sample post strings')
    voice_summary     = models.TextField(blank=True, help_text='AI-generated summary of brand voice')
    tone_descriptors  = models.JSONField(default=list, blank=True, help_text='["friendly", "concise", "expert"]')

    # Vocabulary controls
    forbidden_words   = models.JSONField(default=list, blank=True, help_text='Words/phrases to avoid')
    preferred_words   = models.JSONField(default=list, blank=True, help_text='Brand vocabulary to favour')
    style_rules       = models.JSONField(default=list, blank=True)

    # Audience + content fences (added AI infra)
    target_audience   = models.TextField(blank=True)
    prohibited_topics = models.JSONField(default=list, blank=True)
    emoji_usage       = models.CharField(max_length=10, choices=EMOJI_USAGE_CHOICES, default='moderate', blank=True)
    hashtag_style     = models.CharField(max_length=30, blank=True,
                                         help_text='e.g. "minimal", "grouped-at-end", "inline"')

    # Training pipeline state
    training_status   = models.CharField(max_length=10, choices=TRAINING_STATUS_CHOICES, default='pending')
    training_error    = models.CharField(max_length=500, blank=True)
    last_trained_at   = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Brand voice — {self.client.company}"


class AIReplyTemplate(models.Model):
    """Reusable reply template (with optional AI-personalization)."""
    client            = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='ai_reply_templates')
    name              = models.CharField(max_length=200)
    trigger_keywords  = models.JSONField(default=list, blank=True, help_text='Keywords this template responds to')
    reply_text        = models.TextField()
    platforms         = models.JSONField(default=list, blank=True)
    is_ai_dynamic     = models.BooleanField(default=False, help_text='If True, AI personalizes per message')
    use_count         = models.IntegerField(default=0)
    is_active         = models.BooleanField(default=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-use_count', 'name']

    def __str__(self):
        return f"{self.client.company} — {self.name}"


class AutomationRule(models.Model):
    """IF (trigger + filters) THEN action — runs on inbox/engagement events."""
    client          = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='automation_rules')
    name            = models.CharField(max_length=200)
    trigger_type    = models.CharField(max_length=40, choices=AUTOMATION_TRIGGER_CHOICES)
    trigger_filters = models.JSONField(default=dict, blank=True, help_text='{platforms, keywords, sentiment, ...}')
    action_type     = models.CharField(max_length=40, choices=AUTOMATION_ACTION_CHOICES)
    action_config   = models.JSONField(default=dict, blank=True)
    is_active       = models.BooleanField(default=True)
    run_count       = models.IntegerField(default=0)
    last_run_at     = models.DateTimeField(null=True, blank=True)
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_automation_rules')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'is_active', 'trigger_type']),
        ]

    def __str__(self):
        return f"{self.client.company} | {self.trigger_type} → {self.action_type}"


# ── Competitor snapshots ──────────────────────────────────────────────────────
class CompetitorSnapshot(models.Model):
    """Daily metric snapshot of a competitor on one platform."""
    competitor       = models.ForeignKey(Competitor, on_delete=models.CASCADE, related_name='snapshots')
    platform         = models.CharField(max_length=30, choices=PLATFORM_CHOICES)
    date             = models.DateField()
    followers        = models.BigIntegerField(default=0)
    posts_count      = models.IntegerField(default=0)
    engagement_rate  = models.FloatField(default=0)
    avg_likes        = models.FloatField(default=0)
    avg_comments     = models.FloatField(default=0)
    sample_top_posts = models.JSONField(default=list, blank=True, help_text='Top public posts captured for this snapshot')
    raw              = models.JSONField(default=dict, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('competitor', 'platform', 'date')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['competitor', 'platform', '-date']),
        ]

    def __str__(self):
        return f"{self.competitor.name} | {self.platform} | {self.date}"


# ══════════════════════════════════════════════════════════════════════════════

ACTION_RESULT_CHOICES = [
    ('success', 'Success'),
    ('failed',  'Failed'),
    ('partial', 'Partial'),
]


class ActionLog(models.Model):
    """
    Append-only record of every write action Social Stats performs against a
    platform on behalf of a client. Used for compliance review and the
    "what did SocialStats do for me?" page.
    """
    actor       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='action_logs')
    client      = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='action_logs')
    action      = models.CharField(max_length=80, db_index=True,
                                    help_text='e.g. composer.publish, inbox.reply, automation.fired')
    object_type = models.CharField(max_length=80, blank=True, help_text='e.g. UnifiedPost, Conversation')
    object_id   = models.CharField(max_length=80, blank=True)
    platform    = models.CharField(max_length=30, blank=True)
    result      = models.CharField(max_length=20, choices=ACTION_RESULT_CHOICES, default='success')
    details     = models.JSONField(default=dict, blank=True)
    error       = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['client', 'action', '-created_at']),
            models.Index(fields=['actor', '-created_at']),
        ]

    def __str__(self):
        actor = self.actor.email if self.actor_id else 'system'
        return f'{actor} | {self.action} | {self.result} | {self.created_at:%Y-%m-%d %H:%M}'


SMART_NOTIFICATION_EVENT_CHOICES = [
    ('viral_post',        'Viral post'),
    ('engagement_drop',   'Engagement drop'),
    ('negative_cluster',  'Negative-sentiment cluster'),
    ('follower_milestone', 'Follower milestone'),
    ('best_time_window',  'Best-time-to-post window'),
    ('mention',           'Mention or tag'),
    ('token_expiring',    'Token expiring soon'),
    ('publish_failed',    'Publish failed'),
    ('post_published',    'Post published'),
    ('approval_pending',  'Post needs approval'),
    ('inbox_message',     'New inbound message'),
    ('inbox_review',      'New review'),
    # Marketplace
    ('manage_request_received', 'Agency wants to manage your account'),
    ('agency_invite_received',  'Client invited your agency'),
    ('relation_terminated',     'Agency relationship ended'),
    ('approval_requested',      'Action needs your approval'),
    ('approval_decided',        'Your approval request was decided'),
    ('new_review_received',     'New review left for your agency'),
    ('review_response',         'Agency replied to your review'),
    ('marketplace_inquiry',     'Marketplace inquiry'),
    # CTWA bot builder
    ('bot_handoff',          'Bot handed a conversation to you'),
    ('bot_lead_captured',    'New CTWA lead captured'),
    ('bot_ai_takeover',      'AI chat took over a conversation'),
    ('invitation_received',     'Invitation to manage an account'),
    ('invitation_accepted',     'Your invitation was accepted'),
    ('invitation_rejected',     'Your invitation was rejected'),
    ('invitation_cancelled',    'Invitation was cancelled'),
    ('agency_invite_accepted',  'Agency accepted your invitation'),
    ('agency_invite_declined',  'Agency declined your invitation'),
    ('manage_request_accepted', 'Your manage request was accepted'),
    ('manage_request_declined', 'Your manage request was declined'),
    ('manage_request_cancelled', 'Manage request was cancelled'),
    ('permission_changed', 'A client updated your permissions'),
    ('relation_paused',    'A client paused your access'),
    ('relation_resumed',   'A client resumed your access'),
    ('agency_disconnected',     'A client disconnected from your agency'),
    ('client_account_deleted',  'A client deleted their account'),
    ('client_joined',           'Your invited client joined Social Stats'),
]

NOTIFICATION_CHANNEL_CHOICES = [
    ('in_app',  'In-app'),
    ('email',   'Email'),
    ('whatsapp','WhatsApp'),
    ('browser', 'Browser push'),
]


class NotificationPreference(models.Model):
    """
    Per-user opt-in/out matrix. Default policy: in_app=True, others=False
    until explicitly opted in.
    """
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_prefs')
    event_type = models.CharField(max_length=40, choices=SMART_NOTIFICATION_EVENT_CHOICES)
    channel    = models.CharField(max_length=20, choices=NOTIFICATION_CHANNEL_CHOICES)
    enabled    = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'event_type', 'channel')
        ordering = ['user', 'event_type', 'channel']

    def __str__(self):
        return f'{self.user.email} | {self.event_type} | {self.channel} | {self.enabled}'


# ════════════════════════════════════════════════════════════════════════
# AI Infrastructure — added in the AI build-out
# ════════════════════════════════════════════════════════════════════════


class AIUsageLog(models.Model):
    """One row per AI request — used for cost analytics, audit, dedup signals."""
    STATUS_CHOICES = [
        ("success",       "Success"),
        ("error",         "Error"),
        ("rate_limited",  "Rate limited"),
        ("budget_capped", "Budget capped"),
    ]

    client          = models.ForeignKey(Client, on_delete=models.CASCADE,
                                         related_name="ai_usage_logs", null=True, blank=True)
    user            = models.ForeignKey(User,   on_delete=models.SET_NULL,
                                         related_name="ai_usage_logs", null=True, blank=True)
    feature         = models.CharField(max_length=60,
                                       help_text="caption | reply_suggest | chat | sentiment | …")
    model           = models.CharField(max_length=80)
    input_tokens    = models.IntegerField(default=0)
    output_tokens   = models.IntegerField(default=0)
    total_cost_usd  = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    request_id      = models.CharField(max_length=120, blank=True, help_text="Anthropic request id")
    prompt_hash     = models.CharField(max_length=64, blank=True, help_text="For dedup analytics")
    cached          = models.BooleanField(default=False)
    request_payload = models.JSONField(default=dict, blank=True, help_text="Sanitised request preview")
    response_summary = models.TextField(blank=True, help_text="First ~200 chars of response")
    duration_ms     = models.IntegerField(default=0)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default="success")
    error_message   = models.CharField(max_length=1000, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client", "-created_at"]),
            models.Index(fields=["user",   "-created_at"]),
            models.Index(fields=["feature", "-created_at"]),
            models.Index(fields=["prompt_hash"]),
        ]

    def __str__(self):
        return f"{self.feature} | {self.model} | {self.created_at:%Y-%m-%d %H:%M}"


class AIConversation(models.Model):
    """A chat thread between a user and Social Stats."""
    CONTEXT_CHOICES = [
        ("general",         "General"),
        ("client_specific", "Client-specific"),
        ("data_query",      "Data query"),
    ]

    client           = models.ForeignKey(Client, on_delete=models.CASCADE,
                                          related_name="ai_conversations", null=True, blank=True)
    user             = models.ForeignKey(User,   on_delete=models.CASCADE,
                                          related_name="ai_conversations")
    title            = models.CharField(max_length=200, blank=True,
                                         help_text="Auto-generated from first user message")
    context_type     = models.CharField(max_length=20, choices=CONTEXT_CHOICES, default="general")
    pinned_resources = models.JSONField(default=list, blank=True,
                                         help_text="References to specific posts/campaigns/data")
    archived         = models.BooleanField(default=False)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "archived", "-updated_at"]),
            models.Index(fields=["client", "-updated_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} | {self.title or self.context_type}"


class AIMessage(models.Model):
    """One message inside an AIConversation."""
    ROLE_CHOICES = [
        ("user",      "User"),
        ("assistant", "Assistant"),
        ("system",    "System"),
    ]
    FEEDBACK_CHOICES = [
        ("positive", "Positive"),
        ("negative", "Negative"),
    ]

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    role         = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content      = models.TextField()
    attachments  = models.JSONField(default=list, blank=True,
                                     help_text="[{type, url, name}] image/file refs")
    tool_calls   = models.JSONField(default=list, blank=True,
                                     help_text="Anthropic tool-use blocks emitted by assistant")
    tool_results = models.JSONField(default=list, blank=True,
                                     help_text="Results returned to assistant for follow-up")
    model_used   = models.CharField(max_length=80, blank=True)
    tokens_used  = models.IntegerField(default=0)
    cost_usd     = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    feedback     = models.CharField(max_length=10, choices=FEEDBACK_CHOICES, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    edited_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
        ]

    def __str__(self):
        return f"{self.role} | {self.content[:50]}"


class AIScheduledRun(models.Model):
    """A recurring AI analysis (e.g. weekly report, daily competitor check)."""
    FEATURE_CHOICES = [
        ("weekly_report",    "Weekly report"),
        ("monthly_report",   "Monthly report"),
        ("competitor_check", "Competitor check"),
        ("trend_radar",      "Trend radar"),
        ("crisis_scan",      "Crisis scan"),
        ("daily_briefing",   "Daily briefing"),
        ("custom",           "Custom"),
    ]
    STATUS_CHOICES = [
        ("never_run", "Never run"),
        ("running",   "Running"),
        ("success",   "Success"),
        ("failed",    "Failed"),
    ]

    client          = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="ai_scheduled_runs")
    feature         = models.CharField(max_length=40, choices=FEATURE_CHOICES)
    schedule_rule   = models.CharField(max_length=200, blank=True,
                                        help_text="iCal RRULE or human-readable cadence")
    is_active       = models.BooleanField(default=True)
    last_run_at     = models.DateTimeField(null=True, blank=True)
    last_run_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="never_run")
    last_result     = models.JSONField(default=dict, blank=True)
    config          = models.JSONField(default=dict, blank=True, help_text="Per-feature parameters")
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = ("client", "feature")

    def __str__(self):
        return f"{self.client.company} | {self.feature} | {self.last_run_status}"


class AITrainedAsset(models.Model):
    """RAG-style indexed asset for retrieval (post snippets, brand docs, FAQ)."""
    ASSET_TYPE_CHOICES = [
        ("post",     "Post"),
        ("article",  "Article"),
        ("document", "Document"),
        ("website",  "Website"),
        ("faq",      "FAQ"),
        ("brand",    "Brand guideline"),
    ]

    client     = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="ai_trained_assets")
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPE_CHOICES)
    source_id  = models.CharField(max_length=120, blank=True,
                                   help_text="External id (post id, doc id) for de-dup")
    content    = models.TextField()
    embedding  = models.JSONField(default=list, blank=True,
                                   help_text="Vector — empty until RAG is enabled")
    metadata   = models.JSONField(default=dict, blank=True)
    indexed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["client", "asset_type", "-updated_at"]),
            models.Index(fields=["client", "source_id"]),
        ]

    def __str__(self):
        return f"{self.client.company} | {self.asset_type} | {self.source_id or self.id}"


# ── Marketplace(two-sided platform) ──────────────────────────────
# Models live in marketplace_models.py for readability; re-exported here so
# Django picks them up under the social_stats app label.
from .marketplace_models import (  # noqa: E402,F401
    AGENCY_CLIENT_PERMISSIONS,
    Agency,
    AgencyMembership,
    AgencyClientRelation,
    ApprovalRequest,
    ActivityLog,
    AgencyReview,
    ManageRequest,
    AgencyInviteFromUser,
    Subscription,
    Invoice,
    Dispute,
)

# ── CTWA Bot Builder(bot/lead funnel) ─────────────────────────────
from .bot_models import (  # noqa: E402,F401
    NODE_TYPES,
    BotFlow,
    BotConversation,
    BotConversationStep,
    Lead,
    LeadActivity,
    BotFlowTemplate,
    CTWACampaign,
)

# ── security build-out — active session tracking ──────────────────────
from .security.sessions import UserSession  # noqa: E402,F401

# ── security build-out — MFA ──────────────────────────────────────────
from .security.mfa import UserMFA  # noqa: E402,F401

# ── security build-out — API keys ─────────────────────────────────────
from .security.api_keys import APIKey  # noqa: E402,F401

# ── security build-out — webhook replay protection ────────────────────
from .security.webhook_replay import WebhookEvent  # noqa: E402,F401

# ── security build-out — security audit log ───────────────────────────
from .security.audit import SecurityAuditLog  # noqa: E402,F401

# ── security build-out — privacy / data-subject rights ────────────────
from .security.privacy_models import (  # noqa: E402,F401
    DataExportRequest, AccountDeletionRequest, UserConsent,
)

# ── security build-out — Meta/Google platform compliance ─────────────
from .security.platform_compliance import PlatformDataDeletionRequest  # noqa: E402,F401

# ── central event bus ──────────────────────────────────
from .events.models import EventLog  # noqa: E402,F401

