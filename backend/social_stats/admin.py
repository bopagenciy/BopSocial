# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Author    : Chandrabhan Shekhawat
#  Company   : Gigai Kripa Services
#  Website   : https://gigaikripaservices.com/
#  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
#  Released under the MIT License — see LICENSE. Keep this notice.
# ============================================================================
from django.contrib import admin
from .models import (
    SocialMetricSnapshot, SocialMetricRollup, BusinessSignal, ExecutiveReport, ExecutiveNarrative, IntelligenceAutomationConfig, IntelligenceAutomationRun,
    Client, UserProfile, PlatformCredential, DailyMetric, PostMetric, SyncLog,
    ROISettings, ROIReport,
    CalendarPost, CalendarNote, PostingSchedule, SiteContent, LookupCollection, LookupItem,
)

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['company', 'name', 'email', 'is_active', 'created_at']
    search_fields = ['company', 'name', 'email']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'client']
    list_filter = ['role']

@admin.register(PlatformCredential)
class CredentialAdmin(admin.ModelAdmin):
    list_display = ['client', 'platform', 'status', 'connected_at', 'expires_at']
    list_filter = ['platform', 'is_active']
    readonly_fields = ['connected_at', 'updated_at']

@admin.register(DailyMetric)
class DailyMetricAdmin(admin.ModelAdmin):
    list_display = ['client', 'platform', 'date', 'impressions', 'reach', 'clicks']
    list_filter = ['platform']
    date_hierarchy = 'date'

@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ['client', 'platform', 'status', 'records_synced', 'started_at']
    list_filter = ['platform', 'status']


@admin.register(ROISettings)
class ROISettingsAdmin(admin.ModelAdmin):
    list_display  = ['client', 'total_budget_display', 'avg_sale_value', 'conversion_rate', 'updated_at']
    search_fields = ['client__company']

    def total_budget_display(self, obj):
        return f"{obj.currency_symbol}{obj.total_budget:,.2f}"
    total_budget_display.short_description = 'Total Budget'


@admin.register(ROIReport)
class ROIReportAdmin(admin.ModelAdmin):
    list_display   = ['client', 'month', 'year', 'total_investment', 'estimated_revenue', 'roi_percentage', 'generated_at']
    list_filter    = ['year', 'month']
    date_hierarchy = 'generated_at'
    search_fields  = ['client__company']


@admin.register(CalendarPost)
class CalendarPostAdmin(admin.ModelAdmin):
    list_display    = ['client', 'platform', 'status', 'post_type', 'title', 'scheduled_at', 'published_at', 'impressions', 'likes']
    list_filter     = ['platform', 'status', 'post_type']
    search_fields   = ['client__company', 'title', 'caption']
    date_hierarchy  = 'published_at'
    readonly_fields = ['impressions', 'reach', 'likes', 'comments', 'shares', 'saves', 'video_views', 'engagement_rate', 'created_at', 'updated_at']
    raw_id_fields   = ['client', 'post_metric', 'created_by']


@admin.register(CalendarNote)
class CalendarNoteAdmin(admin.ModelAdmin):
    list_display  = ['client', 'date', 'title', 'is_client_visible', 'created_at']
    list_filter   = ['is_client_visible']
    search_fields = ['client__company', 'title', 'note']
    raw_id_fields = ['client', 'created_by']


@admin.register(PostingSchedule)
class PostingScheduleAdmin(admin.ModelAdmin):
    list_display  = ['client', 'platform', 'day_of_week', 'hour', 'minute', 'is_active']
    list_filter   = ['platform', 'is_active']
    search_fields = ['client__company']
    raw_id_fields = ['client']


@admin.register(SiteContent)
class SiteContentAdmin(admin.ModelAdmin):
    list_display = ['key', 'title', 'is_public', 'last_updated', 'updated_at']
    list_filter = ['is_public']
    search_fields = ['key', 'title']


class LookupItemInline(admin.TabularInline):
    model = LookupItem
    extra = 0


@admin.register(LookupCollection)
class LookupCollectionAdmin(admin.ModelAdmin):
    list_display = ['key', 'title', 'is_public', 'updated_at']
    search_fields = ['key', 'title']
    list_filter = ['is_public']
    inlines = [LookupItemInline]


@admin.register(SocialMetricSnapshot)
class SocialMetricSnapshotAdmin(admin.ModelAdmin):
    list_display = ['client', 'platform', 'metric_scope', 'object_id', 'normalized_metric', 'metric_value', 'bucket_period', 'bucket_timestamp', 'freshness_state']
    list_filter = ['platform', 'metric_scope', 'normalized_metric', 'bucket_period', 'freshness_state']
    search_fields = ['client__company', 'object_id', 'normalized_metric', 'raw_metric_name']
    raw_id_fields = ['client', 'unified_post', 'publish_log']
    readonly_fields = ['dimensions_hash', 'captured_at', 'updated_at']


@admin.register(SocialMetricRollup)
class SocialMetricRollupAdmin(admin.ModelAdmin):
    list_display = ['client', 'platform', 'metric_scope', 'object_id', 'normalized_metric', 'period', 'period_start', 'metric_value']
    list_filter = ['platform', 'metric_scope', 'normalized_metric', 'period']
    search_fields = ['client__company', 'object_id', 'normalized_metric']
    raw_id_fields = ['client']
    readonly_fields = ['computed_at']

@admin.register(BusinessSignal)
class BusinessSignalAdmin(admin.ModelAdmin):
    list_display = ['client', 'platform', 'signal_type', 'metric', 'confidence_level', 'severity', 'is_actionable', 'period_end']
    list_filter = ['platform', 'signal_type', 'confidence_level', 'severity', 'is_actionable']
    search_fields = ['client__company', 'signal_type', 'metric', 'signal_identity']
    readonly_fields = ['signal_identity', 'created_at', 'updated_at']


@admin.register(ExecutiveReport)
class ExecutiveReportAdmin(admin.ModelAdmin):
    list_display = ['client', 'title', 'report_type', 'period_start', 'period_end', 'language', 'status', 'generated_at']
    list_filter = ['report_type', 'language', 'status']
    search_fields = ['client__company', 'title', 'source_hash']
    readonly_fields = ['source_hash', 'created_at', 'updated_at']


@admin.register(ExecutiveNarrative)
class ExecutiveNarrativeAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'executive_report', 'status', 'provider', 'model_name', 'prompt_version', 'validation_status', 'generated_at']
    list_filter = ['status', 'validation_status', 'provider', 'language']
    search_fields = ['client__name', 'client__company', 'source_hash', 'context_hash']
    readonly_fields = ['source_hash', 'context_hash', 'created_at', 'updated_at']


@admin.register(IntelligenceAutomationConfig)
class IntelligenceAutomationConfigAdmin(admin.ModelAdmin):
    list_display = ['client', 'enabled', 'timezone', 'reporting_frequency', 'reporting_day', 'reporting_hour', 'generate_report', 'generate_narrative', 'require_operator_approval', 'provider_call_budget', 'updated_at']
    list_filter = ['enabled', 'reporting_frequency', 'generate_report', 'generate_narrative', 'require_operator_approval']
    search_fields = ['client__name', 'client__company', 'timezone']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(IntelligenceAutomationRun)
class IntelligenceAutomationRunAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'status', 'current_stage', 'period_start', 'period_end', 'trigger_type', 'dry_run', 'provider_call_count', 'error_code', 'started_at', 'finished_at']
    list_filter = ['status', 'current_stage', 'trigger_type', 'dry_run']
    search_fields = ['client__name', 'client__company', 'execution_identity', 'error_code']
    readonly_fields = ['execution_identity', 'started_at', 'finished_at', 'created_at', 'updated_at']
