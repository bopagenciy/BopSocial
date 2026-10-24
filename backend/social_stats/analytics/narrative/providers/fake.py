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

        has_mc = bool(context.get("multichannel_intelligence"))
        mc_sig_7 = "MC-SIG-7" if "MC-SIG-7" in evidence_registry else sig_ref
        mc_sig_8 = "MC-SIG-8" if "MC-SIG-8" in evidence_registry else lim_ref

        # Default Valid JSON
        if has_mc:
            if language == "es":
                valid_payload = {
                    "executive_summary": [
                        "Durante el periodo analizado, Instagram registr? 50 seguidores frente a 20 en Facebook; esta diferencia corresponde al tama?o de audiencia y no implica superioridad general de rendimiento.",
                        "La comparaci?n entre plataformas permanece limitada: solo 3 de 15 m?tricas son comparables debido a restricciones de proveedor en Instagram."
                    ],
                    "performance_observations": [
                        "Instagram registr? 6 reacciones frente a 0 en Facebook durante el per?odo analizado.",
                        "Dado que la l?nea base de Facebook es cero en reacciones, no se expresa una variaci?n porcentual.",
                        "SAVES y VIDEO_VIEWS no se comparan directamente entre ambas plataformas por diferencias sem?nticas de proveedor."
                    ],
                    "recommendations": [
                        {
                            "text": "Revisar los permisos del proveedor en Instagram para ampliar la disponibilidad de m?tricas comparables entre plataformas.",
                            "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                            "strength": "CONSIDER",
                            "confidence": "HIGH",
                            "evidence_refs": [mc_sig_8]
                        },
                        {
                            "text": "Revisar el rendimiento espec?fico en reacciones observadas en cada plataforma manteniendo la estrategia actual.",
                            "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                            "strength": "CONSIDER",
                            "confidence": "HIGH",
                            "evidence_refs": [mc_sig_7]
                        }
                    ],
                    "limitations": [
                        "La cobertura de datos entre plataformas es limitada: solo 3 de 15 m?tricas son comparables en este periodo.",
                        "SAVES y VIDEO_VIEWS no admiten una comparaci?n directa por divergencia sem?ntica entre Facebook e Instagram."
                    ]
                }
            else:
                valid_payload = {
                    "executive_summary": [
                        "During the analyzed period, Instagram recorded 50 followers compared to 20 on Facebook; this reflects audience size only and does not imply superior performance.",
                        "Cross-platform comparison remains limited: only 3 of 15 metrics are comparable due to provider restrictions on Instagram."
                    ],
                    "performance_observations": [
                        "Instagram recorded 6 reactions compared to 0 on Facebook during the analyzed period.",
                        "Given that Facebook baseline is zero for reactions, no percentage variation is stated.",
                        "SAVES and VIDEO_VIEWS are not directly comparable between platforms due to provider semantic differences."
                    ],
                    "recommendations": [
                        {
                            "text": "Review provider permissions on Instagram to increase comparable metric availability.",
                            "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                            "strength": "CONSIDER",
                            "confidence": "HIGH",
                            "evidence_refs": [mc_sig_8]
                        },
                        {
                            "text": "Review specific reaction performance observed across platforms maintaining current strategy.",
                            "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                            "strength": "CONSIDER",
                            "confidence": "HIGH",
                            "evidence_refs": [mc_sig_7]
                        }
                    ],
                    "limitations": [
                        "Cross-platform data coverage is limited: only 3 of 15 metrics are comparable in this period.",
                        "SAVES and VIDEO_VIEWS are not directly comparable between Facebook and Instagram."
                    ]
                }
        elif language == "es":
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

        elif mode == "OVERALL_WINNER_ATTACK":
            payload = dict(valid_payload)
            payload["performance_observations"] = [
                "Instagram es la mejor plataforma en general."
            ]

        elif mode == "FAKE_PERCENTAGE_ATTACK":
            payload = dict(valid_payload)
            payload["performance_observations"] = [
                "Instagram tuvo 600% m?s reacciones."
            ]

        elif mode == "ENGAGEMENT_HALLUCINATION_ATTACK":
            payload = dict(valid_payload)
            payload["performance_observations"] = [
                "Instagram tuvo mayor engagement total."
            ]

        elif mode == "NON_COMPARABLE_ATTACK":
            payload = dict(valid_payload)
            payload["performance_observations"] = [
                "Instagram tuvo mejores VIDEO_VIEWS."
            ]

        elif mode == "AUDIENCE_PERFORMANCE_ATTACK":
            payload = dict(valid_payload)
            payload["performance_observations"] = [
                "Instagram rinde mejor porque tiene m?s seguidores."
            ]

        elif mode == "CAUSALITY_ATTACK":
            payload = dict(valid_payload)
            payload["performance_observations"] = [
                "Instagram obtuvo m?s reacciones porque su contenido fue mejor."
            ]

        elif mode == "UNSUPPORTED_BUDGET_ACTION":
            payload = dict(valid_payload)
            payload["recommendations"] = [
                {
                    "text": "Debemos mover el presupuesto de Facebook a Instagram.",
                    "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                    "strength": "RECOMMEND",
                    "confidence": "HIGH",
                    "evidence_refs": [sig_ref]
                }
            ]

        elif mode == "BAD_EVIDENCE_REF":
            payload = dict(valid_payload)
            payload["recommendations"] = [
                {
                    "text": "Revisar los permisos de conexi?n.",
                    "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                    "strength": "CONSIDER",
                    "confidence": "HIGH",
                    "evidence_refs": ["MC-SIG-999"]
                }
            ]

        elif mode == "CONFIDENCE_MISMATCH":
            payload = dict(valid_payload)
            payload["recommendations"] = [
                {
                    "text": "Revisar los permisos del proveedor en Instagram.",
                    "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                    "strength": "CONSIDER",
                    "confidence": "LOW",  # Mismatch: MC-SIG-8 is HIGH!
                    "evidence_refs": [mc_sig_8]
                }
            ]

        elif mode == "LIMITATION_OMISSION":
            payload = dict(valid_payload)
            payload["limitations"] = [
                "Instagram opera en modo parcial con m?tricas de interacci?n registradas."
            ]

        elif mode == "LANGUAGE_MISMATCH":
            payload = dict(valid_payload)
            payload["executive_summary"] = [
                "During the analyzed period, Instagram recorded 50 followers compared to 20 on Facebook.",
                "Cross-platform comparisons show limited data coverage with 3 comparable metrics."
            ]
            payload["performance_observations"] = [
                "Instagram recorded 6 reactions compared to 0 on Facebook."
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
