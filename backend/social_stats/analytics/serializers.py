"""
Safe Serializers for SocialMetricSnapshot and SocialMetricRollup.
Exposes analytical telemetry without any sensitive tokens or secrets.
"""
from rest_framework import serializers

from social_stats.models import SocialMetricSnapshot, SocialMetricRollup


class SocialMetricSnapshotSerializer(serializers.ModelSerializer):
    """Safe serializer for point-in-time metric snapshot observations."""
    client_company = serializers.CharField(source="client.company", read_only=True)

    class Meta:
        model = SocialMetricSnapshot
        fields = [
            "id",
            "client",
            "client_company",
            "platform",
            "account_id",
            "metric_scope",
            "object_id",
            "unified_post",
            "publish_log",
            "raw_metric_name",
            "normalized_metric",
            "metric_value",
            "extra_dimensions",
            "dimensions_hash",
            "bucket_period",
            "bucket_timestamp",
            "provider_timestamp",
            "captured_at",
            "updated_at",
            "freshness_state",
            "is_derived",
            "metadata",
        ]
        read_only_fields = [
            "id",
            "dimensions_hash",
            "captured_at",
            "updated_at",
        ]


class SocialMetricRollupSerializer(serializers.ModelSerializer):
    """Safe serializer for materialized metric rollups."""
    client_company = serializers.CharField(source="client.company", read_only=True)

    class Meta:
        model = SocialMetricRollup
        fields = [
            "id",
            "client",
            "client_company",
            "platform",
            "metric_scope",
            "object_id",
            "normalized_metric",
            "dimensions_hash",
            "period",
            "period_start",
            "metric_value",
            "extra_dimensions",
            "sample_count",
            "computed_at",
            "metadata",
        ]
        read_only_fields = [
            "id",
            "computed_at",
        ]
