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
    summary_data = report_data.get('summary', {})
    kpis = {
        "followers_total": summary_data.get('followers_total', 0),
        "reactions": summary_data.get('reactions', 0),
        "comments": summary_data.get('comments', 0),
        "average_daily_reach": summary_data.get('average_daily_reach', 0),
        "shares": summary_data.get('shares', 0),
        "saves": summary_data.get('saves', 0),
        "video_views": summary_data.get('video_views', 0),
        "engagement_total": summary_data.get('engagement_total', 0),
    }

    # 3. Platform Breakdown & Capabilities
    raw_platforms = report_data.get('platforms', {})
    platforms = {}
    for platform_name, p_data in raw_platforms.items():
        if not isinstance(p_data, dict):
            continue
        platforms[platform_name] = {
            "status": p_data.get('capability', 'COMPLETE'),
            "supported_metrics": p_data.get('supported_metrics', []),
            "unsupported_metrics": p_data.get('unsupported_metrics', []),
            "metrics": p_data.get('metrics', {}),
        }

    # 4. Signals & Evidence Registry
    evidence_registry = {}
    signals_list = []

    # Get signals from parameter or from report_data or database
    raw_signals = []
    if business_signals is not None:
        for s in business_signals:
            if hasattr(s, 'to_dict'):
                raw_signals.append(s.to_dict())
            elif hasattr(s, 'signal_type'):
                conf = getattr(s, 'confidence_level', getattr(s, 'confidence', 'NONE'))
                summ = getattr(s, 'explanation_template', getattr(s, 'summary', ''))
                raw_signals.append({
                    "id": getattr(s, 'id', None),
                    "signal_type": s.signal_type,
                    "confidence": conf,
                    "summary": summ,
                    "status": getattr(s, 'status', 'ACTIVE'),
                    "evidence": getattr(s, 'evidence', {}),
                })
            elif isinstance(s, dict):
                conf = s.get('confidence_level') or s.get('confidence') or 'NONE'
                summ = s.get('explanation_template') or s.get('summary') or ''
                raw_signals.append({
                    "id": s.get('id'),
                    "signal_type": s.get('signal_type', 'GENERAL'),
                    "confidence": conf,
                    "summary": summ,
                    "status": s.get('status', 'ACTIVE'),
                    "evidence": s.get('evidence', {}),
                })
    else:
        for s in report_data.get('signals', []):
            if isinstance(s, dict):
                conf = s.get('confidence_level') or s.get('confidence') or 'NONE'
                summ = s.get('explanation_template') or s.get('summary') or s.get('explanation') or ''
                raw_signals.append({
                    "id": s.get('id'),
                    "signal_type": s.get('signal_type', 'GENERAL'),
                    "confidence": conf,
                    "summary": summ,
                    "status": s.get('status', 'ACTIVE'),
                    "evidence": s.get('evidence', {}),
                })

    sig_counter = 1
    for s in raw_signals[:MAX_SIGNALS_IN_CONTEXT]:
        sig_type = s.get('signal_type', 'GENERAL')
        ref_id = f"SIG-{sig_counter}"
        sig_entry = {
            "ref_id": ref_id,
            "signal_type": sig_type,
            "status": s.get('status', 'ACTIVE'),
            "confidence": s.get('confidence', 'NONE'),
            "summary": s.get('summary', ''),
            "evidence": s.get('evidence', {}),
        }
        signals_list.append(sig_entry)
        evidence_registry[ref_id] = {
            "type": "BUSINESS_SIGNAL",
            "signal_type": sig_type,
            "confidence": s.get('confidence', 'NONE'),
            "summary": s.get('summary', ''),
            "evidence": s.get('evidence', {}),
        }
        sig_counter += 1

    # 5. Limitations & Evidence
    limitations_list = []
    raw_limitations = report_data.get('limitations', [])
    # Always include known platform partial limitations
    if any(p.get('status') == 'PARTIAL' for p in platforms.values()):
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
    # If any signal has INSUFFICIENT_SAMPLE or sample size is small
    if any(s.get('signal_type') == 'INSUFFICIENT_SAMPLE' for s in signals_list) or not report_data.get('has_sufficient_data', True):
        supported_recommendations.append({
            "type": "CONTINUE_COLLECTING_DATA",
            "allowed_strengths": ["OBSERVE", "CONSIDER"],
            "guidance": "Recommend accumulating more comparable post publications before altering format or cadence strategy.",
        })
    if any(s.get('signal_type') == 'PROVIDER_PARTIAL' for s in signals_list) or any(p.get('status') == 'PARTIAL' for p in platforms.values()):
        supported_recommendations.append({
            "type": "REVIEW_PROVIDER_PERMISSIONS",
            "allowed_strengths": ["OBSERVE", "CONSIDER"],
            "guidance": "Recommend reviewing provider permissions if advanced metrics like Reach or Shares become required.",
        })

    # Assemble context dict
    context = {
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "report": context_report,
        "kpis": kpis,
        "platforms": platforms,
        "signals": signals_list,
        "limitations": limitations_list,
        "supported_recommendations": supported_recommendations,
        "evidence_registry": evidence_registry,
        "has_sufficient_data": report_data.get('has_sufficient_data', False),
    }

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
