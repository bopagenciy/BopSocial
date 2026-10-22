"""
Statistical baseline calculations for Bop Social Business Intelligence.
Favors median and robust percentiles to prevent social outlier distortion.
Zero generative AI or heavy machine-learning dependencies.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Sequence, Tuple, Union


def _to_decimal(val: Union[Decimal, float, int]) -> Decimal:
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def calculate_median(values: Sequence[Union[Decimal, float, int]]) -> Optional[Decimal]:
    """
    Computes exact statistical median.
    Returns None for empty sequences.
    """
    if not values:
        return None

    clean = sorted([_to_decimal(v) for v in values if v is not None])
    n = len(clean)
    if n == 0:
        return None
    if n == 1:
        return clean[0].quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    mid = n // 2
    if n % 2 == 1:
        res = clean[mid]
    else:
        res = (clean[mid - 1] + clean[mid]) / Decimal("2")
    return res.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_mean(values: Sequence[Union[Decimal, float, int]]) -> Optional[Decimal]:
    """
    Computes arithmetic mean.
    Returns None for empty sequences.
    """
    if not values:
        return None

    clean = [_to_decimal(v) for v in values if v is not None]
    if not clean:
        return None
    total = sum(clean, Decimal("0"))
    return (total / Decimal(len(clean))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_percentile(values: Sequence[Union[Decimal, float, int]], p: float) -> Optional[Decimal]:
    """
    Computes the p-th percentile (0 <= p <= 100) using linear interpolation.
    """
    if not values or p < 0 or p > 100:
        return None

    clean = sorted([_to_decimal(v) for v in values if v is not None])
    n = len(clean)
    if n == 0:
        return None
    if n == 1:
        return clean[0].quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    # Rank
    k = (n - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, n - 1)
    d = Decimal(str(k - f))

    res = clean[f] + (clean[c] - clean[f]) * d
    return res.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_mad(values: Sequence[Union[Decimal, float, int]]) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """
    Computes Median Absolute Deviation (MAD):
    MAD = median(|X_i - median(X)|)
    Returns (median, mad).
    """
    if not values:
        return None, None

    med = calculate_median(values)
    if med is None:
        return None, None

    abs_deviations = [abs(_to_decimal(v) - med) for v in values if v is not None]
    mad = calculate_median(abs_deviations)
    return med, mad


def calculate_deltas(observed: Union[Decimal, float, int], baseline: Union[Decimal, float, int]) -> Tuple[Decimal, Optional[Decimal]]:
    """
    Computes absolute_delta and relative_delta.
    absolute_delta = observed - baseline
    relative_delta = (observed - baseline) / baseline (if baseline > 0)
    If baseline == 0, relative_delta is None if observed == 0 else Decimal('1.0000') (or None to prevent fake infinite).
    """
    obs_dec = _to_decimal(observed)
    base_dec = _to_decimal(baseline)

    abs_delta = (obs_dec - base_dec).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    if base_dec == Decimal("0"):
        if obs_dec == Decimal("0"):
            rel_delta = Decimal("0.0000")
        else:
            # Undefined or infinitely above zero; return None to avoid fake infinity or invented benchmark
            rel_delta = None
    else:
        rel_delta = ((obs_dec - base_dec) / base_dec).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return abs_delta, rel_delta


def detect_anomalies(
    values: Sequence[Union[Decimal, float, int]],
    threshold_mad_multiplier: float = 2.5
) -> List[Tuple[int, Decimal, str]]:
    """
    Detects statistical anomalies using Median Absolute Deviation (MAD).
    Returns list of (index, value, 'POSITIVE_OUTLIER' | 'NEGATIVE_OUTLIER').
    Robust to small sample sizes (requires >= 4 observations).
    """
    if len(values) < 4:
        return []

    med, mad = calculate_mad(values)
    if med is None or mad is None or mad == Decimal("0"):
        return []

    mult = Decimal(str(threshold_mad_multiplier))
    cutoff = mad * mult

    outliers = []
    for idx, v in enumerate(values):
        if v is None:
            continue
        v_dec = _to_decimal(v)
        diff = v_dec - med
        if diff > cutoff:
            outliers.append((idx, v_dec, "POSITIVE_OUTLIER"))
        elif diff < -cutoff:
            outliers.append((idx, v_dec, "NEGATIVE_OUTLIER"))

    return outliers
