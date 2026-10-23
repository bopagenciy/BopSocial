"""
Deterministic Fake/Stub Narrative Provider for testing and local validation.
Generates fully grounded valid responses or targeted defect mock modes.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .base import BaseNarrativeProvider, NarrativeProviderResult


class FakeNarrativeProvider(BaseNarrativeProvider):
    """
    Stub provider that produces deterministic narrative responses without any live network or LLM calls.
    Supports injecting specific mock failure modes for test suite assertions.
    """

    def __init__(self, model_name: str = "fake-grounded-v1", mock_mode: str = "VALID"):
        super().__init__(model_name=model_name)
        self.mock_mode = mock_mode

    def generate(
        self,
        context: Dict[str, Any],
        language: str = "es",
        style: str = "EXECUTIVE",
        mock_mode: Optional[str] = None,
        **kwargs
    ) -> NarrativeProviderResult:
        mode = mock_mode or self.mock_mode

        report_info = context.get("report", {})
        client_name = report_info.get("client_name", "Cliente")
        period_start = report_info.get("period_start", "")
        period_end = report_info.get("period_end", "")
        signals = context.get("signals", [])
        evidence_registry = context.get("evidence_registry", {})

        # Find available signal refs
        sig_ref = "SIG-1" if "SIG-1" in evidence_registry else (list(evidence_registry.keys())[0] if evidence_registry else "SIG-1")
        lim_ref = "LIMITATION-IG-PARTIAL" if "LIMITATION-IG-PARTIAL" in evidence_registry else sig_ref

        # Default Valid JSON
        if language == "es":
            valid_payload = {
                "executive_summary": [
                    f"Resumen ejecutivo del período {period_start} al {period_end} para {client_name}.",
                    "El rendimiento de los canales sociales se mantuvo estable con métricas base consolidadas."
                ],
                "performance_observations": [
                    "Las publicaciones registradas muestran actividad consistente en los canales conectados.",
                    "La capacidad analítica de Instagram permanece en modo parcial con métricas de interacción registradas."
                ],
                "recommendations": [
                    {
                        "text": "Continuar recopilando datos de publicaciones comparables para ampliar la muestra analítica.",
                        "recommendation_type": "CONTINUE_COLLECTING_DATA",
                        "strength": "OBSERVE",
                        "confidence": "LOW",
                        "evidence_refs": [sig_ref]
                    },
                    {
                        "text": "Revisar los permisos de conexión de Instagram si se requiere acceder a métricas avanzadas.",
                        "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                        "strength": "CONSIDER",
                        "confidence": "LOW",
                        "evidence_refs": [lim_ref]
                    }
                ],
                "limitations": [
                    "La muestra actual es insuficiente para identificar de forma definitiva un formato ganador.",
                    "Instagram opera en modo parcial con alcance y guardados no disponibles en este período."
                ]
            }
        else:
            valid_payload = {
                "executive_summary": [
                    f"Executive summary for period {period_start} to {period_end} for {client_name}.",
                    "Social channel performance remained stable with consolidated baseline metrics."
                ],
                "performance_observations": [
                    "Registered publications show consistent activity across connected platforms.",
                    "Instagram analytics capability remains in partial mode with interaction metrics recorded."
                ],
                "recommendations": [
                    {
                        "text": "Continue collecting comparable post data to build a larger analytical sample.",
                        "recommendation_type": "CONTINUE_COLLECTING_DATA",
                        "strength": "OBSERVE",
                        "confidence": "LOW",
                        "evidence_refs": [sig_ref]
                    },
                    {
                        "text": "Review Instagram connection permissions if advanced metrics are required.",
                        "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                        "strength": "CONSIDER",
                        "confidence": "LOW",
                        "evidence_refs": [lim_ref]
                    }
                ],
                "limitations": [
                    "Current sample is insufficient to reliably identify a winning format.",
                    "Instagram operates in partial mode with reach and saves unavailable for this period."
                ]
            }

        if mode == "VALID":
            payload = valid_payload

        elif mode == "HALLUCINATED_FACT":
            payload = dict(valid_payload)
            payload["performance_observations"] = [
                "Engagement increased 87% across the campaign."
            ]

        elif mode == "UNAVAILABLE_METRIC":
            payload = dict(valid_payload)
            payload["performance_observations"] = [
                "Instagram reached 5000 people during the period."
            ]

        elif mode == "INSUFFICIENT_SAMPLE_OVERRIDE":
            payload = dict(valid_payload)
            payload["performance_observations"] = [
                "Carousels are your best format and deliver maximum return."
            ]

        elif mode == "CONFIDENCE_UPGRADE":
            payload = dict(valid_payload)
            payload["recommendations"] = [
                {
                    "text": "Increase carousel allocation immediately.",
                    "recommendation_type": "INCREASE_FORMAT_ALLOCATION",
                    "strength": "RECOMMEND",
                    "confidence": "HIGH",  # Upgraded from LOW!
                    "evidence_refs": [sig_ref]
                }
            ]

        elif mode == "UNSUPPORTED_CAUSALITY":
            payload = dict(valid_payload)
            payload["performance_observations"] = [
                "Posting at night caused higher engagement across posts."
            ]

        elif mode == "UNSUPPORTED_CAUSALITY_ES":
            payload = dict(valid_payload)
            payload["performance_observations"] = [
                "Publicar los viernes causó un incremento en las reacciones."
            ]

        elif mode == "MISSING_EVIDENCE_REFS":
            payload = dict(valid_payload)
            payload["recommendations"] = [
                {
                    "text": "Publish more frequently.",
                    "recommendation_type": "MAINTAIN_CURRENT_STRATEGY",
                    "strength": "OBSERVE",
                    "confidence": "LOW",
                    "evidence_refs": []  # Empty!
                }
            ]

        elif mode == "UNKNOWN_TAXONOMY":
            payload = dict(valid_payload)
            payload["recommendations"] = [
                {
                    "text": "Do viral marketing tricks.",
                    "recommendation_type": "GO_VIRAL_NOW",  # Invalid!
                    "strength": "RECOMMEND",
                    "confidence": "LOW",
                    "evidence_refs": [sig_ref]
                }
            ]

        elif mode == "MALFORMED_JSON":
            raw_str = "{ 'executive_summary': [broken json..."
            return NarrativeProviderResult(
                raw_response=raw_str,
                parsed_json={},
                provider_name="fake",
                model_name=self.model_name,
                token_usage={"input_tokens": 120, "output_tokens": 50},
                metadata={"mock_mode": mode}
            )

        else:
            payload = valid_payload

        if mode == "VALID":
            from ..confidence import enrich_narrative_with_derived_confidence
            payload = enrich_narrative_with_derived_confidence(payload, context)

        raw_json_str = json.dumps(payload, indent=2, ensure_ascii=False)
        return NarrativeProviderResult(
            raw_response=raw_json_str,
            parsed_json=payload,
            provider_name="fake",
            model_name=self.model_name,
            token_usage={"input_tokens": 250, "output_tokens": 180},
            metadata={"mock_mode": mode}
        )
