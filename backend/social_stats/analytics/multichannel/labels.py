"""
Bilingual ES/EN Reason and Status Labels for Multichannel Comparisons.
Phase BS-5A: Multichannel Metric Compatibility & Comparison Model.

Machine results strictly use deterministic ComparisonReasonCode;
human labels provide Spanish and English contextual explanations without altering machine state.
"""
from typing import Dict, Union
from .taxonomies import ComparisonReasonCode, ComparisonStatus, ComparisonWinner


REASON_LABELS: Dict[ComparisonReasonCode, Dict[str, str]] = {
    ComparisonReasonCode.DIRECTLY_COMPARABLE: {
        "es": "Métricas directamente comparables con semántica y medición homogénea.",
        "en": "Metrics are directly comparable with identical measurement semantics.",
    },
    ComparisonReasonCode.NORMALIZATION_REQUIRED: {
        "es": "Comparación válida únicamente tras normalización dimensional requerida.",
        "en": "Comparison valid only after required dimensional normalization.",
    },
    ComparisonReasonCode.SOURCE_UNAVAILABLE: {
        "es": "Datos de origen no disponibles o sin observaciones en el período seleccionado.",
        "en": "Source data unavailable or no observations in selected period.",
    },
    ComparisonReasonCode.PROVIDER_PARTIAL: {
        "es": "Comparación no disponible por cobertura parcial del proveedor en la plataforma.",
        "en": "Comparison unavailable due to partial provider coverage on platform.",
    },
    ComparisonReasonCode.METRIC_NOT_EQUIVALENT: {
        "es": "Discrepancia semántica fundamental entre plataformas; ranking directo no admitido.",
        "en": "Fundamental semantic discrepancy between platforms; direct ranking disallowed.",
    },
    ComparisonReasonCode.PERIOD_MISMATCH: {
        "es": "Desalineación en el rango de fechas, granularidad o huso horario de comparación.",
        "en": "Mismatch in comparison date range, granularity, or timezone boundaries.",
    },
    ComparisonReasonCode.DENOMINATOR_UNAVAILABLE: {
        "es": "Denominador requerido para la normalización no disponible.",
        "en": "Required denominator for normalization is unavailable.",
    },
    ComparisonReasonCode.ZERO_BASELINE: {
        "es": "Línea base en cero; variación relativa omitida para evitar división por cero.",
        "en": "Baseline is zero; relative delta omitted to prevent division by zero.",
    },
    ComparisonReasonCode.INSUFFICIENT_SAMPLE: {
        "es": "Tamaño de muestra insuficiente para emitir una comparación estadísticamente válida.",
        "en": "Insufficient sample size to issue a statistically valid comparison.",
    },
    ComparisonReasonCode.NON_RANKABLE_METRIC: {
        "es": "Métrica de volumen o audiencia; no clasifica desempeño competitivo.",
        "en": "Volume or audience size metric; does not rank competitive performance.",
    },
    ComparisonReasonCode.UNSUPPORTED_METRIC: {
        "es": "Identificador de métrica desconocido o no registrado en el modelo canónico.",
        "en": "Metric identifier unknown or unmapped in canonical registry.",
    },
    ComparisonReasonCode.UNSUPPORTED_PLATFORM: {
        "es": "Plataforma no soportada para comparativas multicanal en esta versión.",
        "en": "Platform unsupported for multichannel comparisons in this version.",
    },
    ComparisonReasonCode.TENANT_MISMATCH: {
        "es": "Entidades de clientes distintas o acceso no autorizado entre cuentas.",
        "en": "Differing client entities or unauthorized cross-tenant access.",
    },
    ComparisonReasonCode.COMPONENT_UNAVAILABLE: {
        "es": "Uno o más componentes requeridos para la métrica derivada no están disponibles.",
        "en": "One or more required sub-components for derived metric are unavailable.",
    },
    ComparisonReasonCode.NON_AGGREGATABLE_SUMMATION_REJECTED: {
        "es": "Suma aritmética rechazada: la métrica de alcance único no es agregable entre días.",
        "en": "Arithmetic sum rejected: unique reach metric is non-aggregatable across days.",
    },
}

STATUS_LABELS: Dict[ComparisonStatus, Dict[str, str]] = {
    ComparisonStatus.AVAILABLE: {
        "es": "Comparación disponible",
        "en": "Comparison available",
    },
    ComparisonStatus.UNAVAILABLE: {
        "es": "Comparación no disponible",
        "en": "Comparison unavailable",
    },
    ComparisonStatus.INVALID: {
        "es": "Solicitud de comparación inválida",
        "en": "Invalid comparison request",
    },
}

WINNER_LABELS: Dict[ComparisonWinner, Dict[str, str]] = {
    ComparisonWinner.PLATFORM_A: {
        "es": "Plataforma A con mejor desempeño",
        "en": "Platform A outperformed",
    },
    ComparisonWinner.PLATFORM_B: {
        "es": "Plataforma B con mejor desempeño",
        "en": "Platform B outperformed",
    },
    ComparisonWinner.TIE: {
        "es": "Empate en el valor medido",
        "en": "Tie between platforms",
    },
    ComparisonWinner.NO_WINNER: {
        "es": "Sin ganador (métrica no calificable competitivamente)",
        "en": "No winner (metric not rankable by performance)",
    },
    ComparisonWinner.UNAVAILABLE: {
        "es": "Ganador no disponible",
        "en": "Winner unavailable",
    },
}


def get_reason_labels(reason_code: Union[ComparisonReasonCode, str]) -> Dict[str, str]:
    """Retrieve bilingual labels for a given reason code."""
    if isinstance(reason_code, str):
        try:
            reason_code = ComparisonReasonCode(reason_code)
        except ValueError:
            return {"es": f"Código desconocido: {reason_code}", "en": f"Unknown code: {reason_code}"}
    return REASON_LABELS.get(reason_code, {"es": reason_code.value, "en": reason_code.value})


def get_status_labels(status_val: Union[ComparisonStatus, str]) -> Dict[str, str]:
    """Retrieve bilingual labels for a given comparison status."""
    if isinstance(status_val, str):
        try:
            status_val = ComparisonStatus(status_val)
        except ValueError:
            return {"es": status_val, "en": status_val}
    return STATUS_LABELS.get(status_val, {"es": status_val.value, "en": status_val.value})


def get_winner_labels(winner_val: Union[ComparisonWinner, str]) -> Dict[str, str]:
    """Retrieve bilingual labels for a given winner determination."""
    if isinstance(winner_val, str):
        try:
            winner_val = ComparisonWinner(winner_val)
        except ValueError:
            return {"es": winner_val, "en": winner_val}
    return WINNER_LABELS.get(winner_val, {"es": winner_val.value, "en": winner_val.value})
