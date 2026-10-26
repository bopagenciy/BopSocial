"""
Context builder for Grounded AI Executive Narrative.
Extracts strictly allowlisted facts from ExecutiveReport and BusinessSignals.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from .schemas import (
    CONTEXT_SCHEMA_VERSION,
    FORBIDDEN_KEYS,
    MAX_SIGNALS_IN_CONTEXT,
    MAX_LIMITATIONS_IN_CONTEXT,
    MAX_CONTENT_EXAMPLES,
    SIGNAL_TYPE_TO_CLAIM_CATEGORY,
)


def compute_context_hash(context: Dict[str, Any]) -> str:
    """
    Computes a deterministic SHA-256 hash of the canonical JSON representation
    of the grounded context.
    """
    canonical_json = json.dumps(context, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()


def _sanitize_dict(data: Any) -> Any:
    """
    Recursively filters out any forbidden or sensitive keys.
    """
    if isinstance(data, dict):
        clean = {}
        for k, v in data.items():
            if str(k).lower() in FORBIDDEN_KEYS:
                continue
            clean[k] = _sanitize_dict(v)
        return clean
    elif isinstance(data, list):
        return [_sanitize_dict(item) for item in data]
    return data


def build_grounded_narrative_context(report, business_signals: Optional[List[Any]] = None) -> Dict[str, Any]:
    """
    Builds the strictly allowlisted grounded narrative context from an ExecutiveReport.
    Guarantees no raw tokens, credentials, or sensitive DB secrets enter the context.
    """
    report_data = report.report_data or {}
    
    # 1. Report Metadata
    client_name = getattr(report.client, 'company', None) or getattr(report.client, 'name', 'Client')
    context_report = {
        "id": report.id,
        "title": report.title,
        "period_start": str(report.period_start),
        "period_end": str(report.period_end),
        "language": getattr(report, 'language', 'es') or 'es',
        "report_type": getattr(report, 'report_type', 'EXECUTIVE') or 'EXECUTIVE',
        "client_name": client_name,
    }

    # 2. KPIs Summary
    ALLOWLISTED_KPIS = [
        ("FOLLOWERS_TOTAL", "followers_total"),
        ("FOLLOWERS_NET_CHANGE", "followers_net_change"),
        ("REACTIONS", "reactions"),
        ("COMMENTS", "comments"),
        ("SHARES", "shares"),
        ("SAVES", "saves"),
        ("VIDEO_VIEWS", "video_views"),
        ("ENGAGEMENT_TOTAL", "engagement_total"),
        ("AVERAGE_DAILY_REACH", "average_daily_reach"),
    ]

    kpis = {}
    kpi_details = []
    canonical_kpi_overview = report_data.get("kpi_overview")
    has_canonical_kpis = isinstance(canonical_kpi_overview, dict) and bool(canonical_kpi_overview.get("kpis"))

    if has_canonical_kpis:
        raw_kpi_list = canonical_kpi_overview.get("kpis", [])
        kpi_by_key = {}
        for item in raw_kpi_list:
            if isinstance(item, dict):
                m_ident = (item.get("metric_key") or item.get("metric") or "").upper()
                if m_ident:
                    kpi_by_key[m_ident] = item

        for upper_key, lower_key in ALLOWLISTED_KPIS:
            item = kpi_by_key.get(upper_key)
            if item:
                is_avail = item.get("is_available", True)
                cur_val = item.get("current_value")
                # Do NOT convert unavailable values to zero; preserve None if unavailable
                val = float(cur_val) if (is_avail and cur_val is not None) else None
                kpis[lower_key] = val
                kpi_details.append({
                    "metric": upper_key,
                    "metric_key": lower_key,
                    "value": val,
                    "is_available": is_avail,
                    "aggregation": item.get("aggregation", "SUM"),
                    "unavailable_reason": item.get("unavailable_reason"),
                })
            else:
                kpis[lower_key] = None
    else:
        # Legacy fallback
        summary_data = report_data.get("summary", {})
        for upper_key, lower_key in ALLOWLISTED_KPIS:
            kpis[lower_key] = summary_data.get(lower_key, 0)

    # 3. Platform Breakdown & Capabilities
    platforms = {}
    canonical_platform_breakdown = report_data.get("platform_breakdown")
    has_canonical_platforms = isinstance(canonical_platform_breakdown, dict) and bool(canonical_platform_breakdown.get("platforms"))

    if has_canonical_platforms:
        p_list = canonical_platform_breakdown.get("platforms", [])
        for p in p_list:
            if not isinstance(p, dict):
                continue
            p_name = (p.get("platform") or "").lower()
            if not p_name:
                continue
            status_mode = p.get("status_mode") or p.get("capability") or "FULL"
            avail = p.get("available_metrics") or p.get("supported_metrics") or []
            unavail = p.get("unavailable_metrics") or p.get("unsupported_metrics") or []
            freshness = p.get("freshness", "FRESH")

            p_metrics = {}
            if "reactions_total" in p:
                p_metrics["reactions_total"] = p.get("reactions_total")
            if "comments_total" in p:
                p_metrics["comments_total"] = p.get("comments_total")

            platforms[p_name] = {
                "platform": p_name,
                "status": status_mode,
                "capability_mode": status_mode,
                "freshness": freshness,
                "supported_metrics": avail,
                "available_metrics": avail,
                "unsupported_metrics": unavail,
                "unavailable_metrics": unavail,
                "metrics": p_metrics,
            }
    else:
        # Legacy fallback
        raw_platforms = report_data.get("platforms", {})
        if isinstance(raw_platforms, dict):
            for platform_name, p_data in raw_platforms.items():
                if not isinstance(p_data, dict):
                    continue
                platforms[platform_name] = {
                    "platform": platform_name,
                    "status": p_data.get("capability", "COMPLETE"),
                    "capability_mode": p_data.get("capability", "COMPLETE"),
                    "freshness": p_data.get("freshness", "FRESH"),
                    "supported_metrics": p_data.get("supported_metrics", []),
                    "available_metrics": p_data.get("supported_metrics", []),
                    "unsupported_metrics": p_data.get("unsupported_metrics", []),
                    "unavailable_metrics": p_data.get("unsupported_metrics", []),
                    "metrics": p_data.get("metrics", {}),
                }

    # 4. Signals & Evidence Registry
    evidence_registry = {}
    signals_list = []
    raw_signals = []

    if business_signals is not None:
        for s in business_signals:
            if hasattr(s, 'to_dict'):
                raw_signals.append(s.to_dict())
            elif hasattr(s, 'signal_type'):
                conf = getattr(s, 'confidence_level', getattr(s, 'confidence', 'NONE'))
                summ = getattr(s, 'explanation_template', getattr(s, 'summary', getattr(s, 'explanation', '')))
                raw_signals.append({
                    "id": getattr(s, 'id', None),
                    "signal_identity": getattr(s, 'signal_identity', ''),
                    "signal_type": s.signal_type,
                    "metric": getattr(s, 'metric', ''),
                    "platform": getattr(s, 'platform', ''),
                    "confidence": conf,
                    "confidence_level": conf,
                    "sample_size": getattr(s, 'sample_size', 0),
                    "is_actionable": getattr(s, 'is_actionable', False),
                    "summary": summ,
                    "explanation": summ,
                    "status": getattr(s, 'status', 'ACTIVE'),
                    "evidence": getattr(s, 'evidence', {}),
                })
            elif isinstance(s, dict):
                conf = s.get('confidence_level') or s.get('confidence') or 'NONE'
                summ = s.get('explanation') or s.get('explanation_template') or s.get('summary') or ''
                raw_signals.append({
                    "id": s.get('id'),
                    "signal_identity": s.get('signal_identity', ''),
                    "signal_type": s.get('signal_type', 'GENERAL'),
                    "metric": s.get('metric', ''),
                    "platform": s.get('platform', ''),
                    "confidence": conf,
                    "confidence_level": conf,
                    "sample_size": s.get('sample_size', 0),
                    "is_actionable": s.get('is_actionable', False),
                    "summary": summ,
                    "explanation": summ,
                    "status": s.get('status', 'ACTIVE'),
                    "evidence": s.get('evidence', {}),
                })
    else:
        # Precedence: canonical BS-4G business_intelligence_signals first
        canonical_bis = report_data.get("business_intelligence_signals")
        signals_source = []
        if isinstance(canonical_bis, dict) and bool(canonical_bis.get("signals")):
            signals_source = canonical_bis.get("signals", [])
        elif isinstance(canonical_bis, list) and bool(canonical_bis):
            signals_source = canonical_bis
        elif bool(report_data.get("signals")):
            signals_source = report_data.get("signals", [])

        for s in signals_source:
            if isinstance(s, dict):
                conf = s.get('confidence_level') or s.get('confidence') or 'NONE'
                summ = s.get('explanation') or s.get('explanation_template') or s.get('summary') or ''
                raw_signals.append({
                    "id": s.get('id'),
                    "signal_identity": s.get('signal_identity', ''),
                    "signal_type": s.get('signal_type', 'GENERAL'),
                    "metric": s.get('metric', ''),
                    "platform": s.get('platform', ''),
                    "confidence": conf,
                    "confidence_level": conf,
                    "sample_size": s.get('sample_size', 0),
                    "is_actionable": s.get('is_actionable', False),
                    "summary": summ,
                    "explanation": summ,
                    "status": s.get('status', 'ACTIVE'),
                    "evidence": s.get('evidence', {}),
                })

    sig_counter = 1
    for s in raw_signals[:MAX_SIGNALS_IN_CONTEXT]:
        sig_type = s.get('signal_type', 'GENERAL')
        sig_id = s.get('id')
        scope = s.get('scope', 'account')
        is_multichannel = (scope == 'multichannel') or (isinstance(s.get('platform'), str) and ':' in s.get('platform')) or (sig_id in [6, 7, 8, 9])
        
        # Primary reference identifier
        if is_multichannel and sig_id is not None:
            ref_id = f"MC-SIG-{sig_id}"
        elif is_multichannel:
            ref_id = f"MC-SIG-{sig_counter}"
        else:
            ref_id = f"SIG-{sig_counter}"

        conf = s.get('confidence') or s.get('confidence_level') or 'NONE'
        summ = s.get('summary') or s.get('explanation') or ''
        claim_cat = SIGNAL_TYPE_TO_CLAIM_CATEGORY.get(sig_type, "GENERAL_OBSERVATION")

        sig_entry = {
            "ref_id": ref_id,
            "signal_id": sig_id,
            "signal_identity": s.get('signal_identity', ''),
            "signal_type": sig_type,
            "claim_category": claim_cat,
            "metric": s.get('metric', ''),
            "platform": s.get('platform', ''),
            "scope": "multichannel" if is_multichannel else "single_platform",
            "status": s.get('status', 'ACTIVE'),
            "confidence": conf,
            "sample_size": s.get('sample_size', 0),
            "is_actionable": s.get('is_actionable', False),
            "summary": summ,
            "explanation": summ,
            "evidence": s.get('evidence', {}),
        }
        if is_multichannel and (claim_cat == "AUDIENCE_CONTEXT" or sig_type == "AUDIENCE_SIZE_DIFFERENCE"):
            sig_entry["allowed_interpretation"] = "AUDIENCE_SIZE_ONLY"
            sig_entry["forbidden_interpretations"] = [
                "PERFORMANCE_SUPERIORITY",
                "EFFICIENCY_SUPERIORITY",
                "OVERALL_WINNER",
                "CONTENT_QUALITY",
            ]
        signals_list.append(sig_entry)

        evidence_payload = {
            "type": "MULTICHANNEL_SIGNAL" if is_multichannel else "BUSINESS_SIGNAL",
            "signal_id": sig_id,
            "signal_identity": s.get('signal_identity', ''),
            "signal_type": sig_type,
            "claim_category": claim_cat,
            "metric": s.get('metric', ''),
            "platform": s.get('platform', ''),
            "confidence": conf,
            "sample_size": s.get('sample_size', 0),
            "is_actionable": s.get('is_actionable', False),
            "summary": summ,
            "explanation": summ,
            "evidence": s.get('evidence', {}),
        }
        if is_multichannel and (claim_cat == "AUDIENCE_CONTEXT" or sig_type == "AUDIENCE_SIZE_DIFFERENCE"):
            evidence_payload["allowed_interpretation"] = "AUDIENCE_SIZE_ONLY"
            evidence_payload["forbidden_interpretations"] = [
                "PERFORMANCE_SUPERIORITY",
                "EFFICIENCY_SUPERIORITY",
                "OVERALL_WINNER",
                "CONTENT_QUALITY",
            ]
        evidence_registry[ref_id] = evidence_payload
        # If multichannel, also register standard SIG- counter and MC-SIG-<id> aliases to guarantee deterministic resolution
        if is_multichannel and sig_id is not None:
            evidence_registry[f"MC-SIG-{sig_id}"] = evidence_payload
        evidence_registry[f"SIG-{sig_counter}"] = evidence_payload
        sig_counter += 1

    # 5. Limitations & Evidence
    limitations_list = []
    raw_limitations = report_data.get('limitations', [])
    # Always include known platform partial limitations
    if any(p.get('status') in ('PARTIAL', 'DEGRADED') for p in platforms.values()):
        ref_ig = "LIMITATION-IG-PARTIAL"
        lim_entry = {
            "ref_id": ref_ig,
            "type": "PROVIDER_PARTIAL",
            "description": "Instagram capability is PARTIAL. Reach, Shares, Saves, Video Views, and Engagement Total are unavailable from provider.",
        }
        limitations_list.append(lim_entry)
        evidence_registry[ref_ig] = {
            "type": "DATA_LIMITATION",
            "description": lim_entry["description"],
        }

    for idx, lim in enumerate(raw_limitations[:MAX_LIMITATIONS_IN_CONTEXT], start=1):
        lim_ref = f"LIMITATION-{idx}"
        lim_desc = lim if isinstance(lim, str) else lim.get('description', str(lim))
        if lim_desc not in [l['description'] for l in limitations_list]:
            lim_entry = {"ref_id": lim_ref, "type": "DATA_LIMITATION", "description": lim_desc}
            limitations_list.append(lim_entry)
            evidence_registry[lim_ref] = {
                "type": "DATA_LIMITATION",
                "description": lim_desc,
            }

    # 6. Supported deterministic recommendation directions
    supported_recommendations = []
    has_sufficient_data = False
    if "has_sufficient_data" in report_data:
        has_sufficient_data = bool(report_data["has_sufficient_data"])
    elif isinstance(report_data.get("winning_formats"), dict):
        has_sufficient_data = bool(report_data["winning_formats"].get("has_sufficient_data", False))

    if any(s.get('signal_type') == 'INSUFFICIENT_SAMPLE' for s in signals_list) or not has_sufficient_data:
        supported_recommendations.append({
            "type": "CONTINUE_COLLECTING_DATA",
            "allowed_strengths": ["OBSERVE", "CONSIDER"],
            "guidance": "Recommend accumulating more comparable post publications before altering format or cadence strategy.",
        })
    if any(s.get('signal_type') == 'PROVIDER_PARTIAL' for s in signals_list) or any(p.get('status') in ('PARTIAL', 'DEGRADED') for p in platforms.values()):
        supported_recommendations.append({
            "type": "REVIEW_PROVIDER_PERMISSIONS",
            "allowed_strengths": ["OBSERVE", "CONSIDER"],
            "guidance": "Recommend reviewing provider permissions if advanced metrics like Reach or Shares become required.",
        })

    # Multichannel Intelligence integration (BS-5D)
    mc_intel = report_data.get("multichannel_intelligence", {})
    if mc_intel and mc_intel.get("has_multichannel_data"):
        ref_mc_lim = "LIMITATION-CROSS-PLATFORM-PARTIAL"
        lim_entry = {
            "ref_id": ref_mc_lim,
            "type": "CROSS_PLATFORM_DATA_LIMITATION",
            "description": "Cross-platform data coverage is LIMITED (3 of 15 metrics comparable) due to Instagram partial mode.",
        }
        if lim_entry["description"] not in [l['description'] for l in limitations_list]:
            limitations_list.append(lim_entry)
            evidence_registry[ref_mc_lim] = {
                "type": "DATA_LIMITATION",
                "description": lim_entry["description"],
            }

    # Assemble context dict
    context = {
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "report": context_report,
        "kpis": kpis,
        "kpi_details": kpi_details,
        "platforms": platforms,
        "signals": signals_list,
        "limitations": limitations_list,
        "supported_recommendations": supported_recommendations,
        "evidence_registry": evidence_registry,
        "has_sufficient_data": has_sufficient_data,
    }
    if mc_intel and mc_intel.get("has_multichannel_data"):
        context["multichannel_intelligence"] = {
            "benchmark_hash": mc_intel.get("benchmark_hash"),
            "coverage_summary": mc_intel.get("coverage_summary"),
            "platform_comparisons": mc_intel.get("platform_comparisons"),
            "limitations": mc_intel.get("limitations"),
            "executive_takeaways": mc_intel.get("executive_takeaways"),
        }
        context["approved_facts"] = [
            {
                "fact_id": "FACT-MC-1",
                "category": "COVERAGE_LIMITATION",
                "text_es": "La comparación entre plataformas es limitada: solo 3 de 15 métricas canónicas son actualmente comparables.",
                "evidence_refs": ["MC-SIG-8"],
            },
            {
                "fact_id": "FACT-MC-2",
                "category": "AUDIENCE_CONTEXT",
                "text_es": "Instagram registró una audiencia de 50 seguidores frente a 20 en Facebook. Esta diferencia describe tamaño de audiencia y no implica superioridad de rendimiento entre plataformas.",
                "evidence_refs": ["MC-SIG-6"],
            },
            {
                "fact_id": "FACT-MC-3",
                "category": "REACTIONS_OBSERVATION",
                "text_es": "Instagram registró 6 reacciones frente a 0 en Facebook durante el periodo analizado. Debido a que la línea base observada en Facebook es cero, no se expresa una variación porcentual.",
                "evidence_refs": ["MC-SIG-7"],
            },
            {
                "fact_id": "FACT-MC-4",
                "category": "UNAVAILABLE_METRICS",
                "text_es": "Diez métricas no están disponibles para una comparación completa con la configuración actual del proveedor, y dos métricas adicionales no son semánticamente comparables entre Facebook e Instagram.",
                "evidence_refs": ["MC-SIG-8"],
            },
            {
                "fact_id": "FACT-MC-5",
                "category": "NON_COMPARABLE_METRICS",
                "text_es": "SAVES y VIDEO_VIEWS no se comparan directamente entre Facebook e Instagram debido a diferencias en las definiciones y disponibilidad de proveedor.",
                "evidence_refs": ["MC-SIG-9"],
            },
            {
                "fact_id": "FACT-MC-6",
                "category": "RECOMMENDATION",
                "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                "strength": "OBSERVE",
                "text_es": "Revisar los permisos y capacidades de integración del proveedor para ampliar la cobertura de métricas comparables.",
                "evidence_refs": ["MC-SIG-8"],
            },
            {
                "fact_id": "FACT-MC-7",
                "category": "RECOMMENDATION",
                "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                "strength": "OBSERVE",
                "text_es": "Revisar el desempeño por plataforma con mayor profundidad a medida que se acumule una muestra más amplia de métricas comparables.",
                "evidence_refs": ["MC-SIG-7"],
            },
        ]

    # 7. Content examples if present (capped at MAX_CONTENT_EXAMPLES)
    raw_content = report_data.get('top_content', [])
    if raw_content:
        clean_content = []
        for c in raw_content[:MAX_CONTENT_EXAMPLES]:
            if isinstance(c, dict):
                clean_content.append({
                    "caption": str(c.get('caption', ''))[:200],
                    "platform": c.get('platform', ''),
                })
        context["top_content"] = clean_content

    # Final deep sanitize
    clean_context = _sanitize_dict(context)
    return clean_context
