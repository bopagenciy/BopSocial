"""
Business Intelligence & Deterministic Signal Foundation for Bop Social.
Phase BS-4F.
"""
from .rules import SignalType, PerformanceTier, ConfidenceTier, THRESHOLDS, SAMPLE_THRESHOLDS
from .baselines import (
    calculate_median,
    calculate_mean,
    calculate_percentile,
    calculate_mad,
    calculate_deltas,
    detect_anomalies,
)
from .service import generate_business_signals

__all__ = [
    'SignalType',
    'PerformanceTier',
    'ConfidenceTier',
    'THRESHOLDS',
    'SAMPLE_THRESHOLDS',
    'calculate_median',
    'calculate_mean',
    'calculate_percentile',
    'calculate_mad',
    'calculate_deltas',
    'detect_anomalies',
    'generate_business_signals',
]
