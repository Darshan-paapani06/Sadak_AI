"""
SADAK AI — Complaint Lifecycle Engine
ID generation, routing, SLA tracking, escalation
"""
import random
import string
from datetime import datetime
from location_router import get_authority, get_response_deadline, validate_coordinates
from detector import DetectionResult
import logging

logger = logging.getLogger(__name__)

SEVERITY_LABELS = {
    "CRITICAL": {"emoji": "🔴", "hi": "अत्यंत गंभीर", "sla_hrs": 24},
    "HIGH":     {"emoji": "🟠", "hi": "गंभीर",         "sla_hrs": 72},
    "MEDIUM":   {"emoji": "🟡", "hi": "मध्यम",         "sla_hrs": 168},
    "LOW":      {"emoji": "🟢", "hi": "साधारण",        "sla_hrs": 720},
}

STATUS_FLOW = [
    "FILED", "ACKNOWLEDGED", "IN_PROGRESS", "RESOLVED"
]
STATUS_LABELS = {
    "FILED":        {"next": "ACKNOWLEDGED", "emoji": "📋", "hi": "दर्ज"},
    "ACKNOWLEDGED": {"next": "IN_PROGRESS",  "emoji": "👀", "hi": "स्वीकृत"},
    "IN_PROGRESS":  {"next": "RESOLVED",     "emoji": "🔧", "hi": "प्रगति में"},
    "RESOLVED":     {"next": None,           "emoji": "✅", "hi": "हल"},
    "ESCALATED":    {"next": "IN_PROGRESS",  "emoji": "⚡", "hi": "वृद्धि"},
}


def generate_complaint_id(state_code: str) -> str:
    date_part = datetime.utcnow().strftime("%y%m%d")
    uid = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"SADAK-{state_code.upper()}-{date_part}-{uid}"


def build_complaint(
    lat: float,
    lng: float,
    severity: str,
    description: str,
    reporter_name: str,
    reporter_phone: str,
    image_path: str | None,
    detection: DetectionResult | None,
    is_village: bool = False,
) -> dict:
    """
    Assemble a complete complaint record combining
    form data, AI detection, and authority routing.
    """
    # Validate & route
    if not validate_coordinates(lat, lng):
        raise ValueError(f"Coordinates ({lat}, {lng}) outside India")

    authority = get_authority(lat, lng, is_village)

    # If AI detected, override submitted severity with detected severity
    ai_detected = detection is not None and detection.detected
    if ai_detected and detection.severity not in ("UNKNOWN",):
        final_severity = detection.severity
    else:
        final_severity = severity if severity in SEVERITY_LABELS else "MEDIUM"

    complaint_id    = generate_complaint_id(authority.state_code)
    deadline        = get_response_deadline(final_severity, authority.response_hours)

    return {
        "complaint_id":     complaint_id,
        "latitude":         lat,
        "longitude":        lng,
        "state":            authority.state,
        "district":         authority.district,
        "sub_district":     authority.sub_district,
        "village":          authority.village,
        "severity":         final_severity,
        "status":           "FILED",
        "description":      description,
        "reporter_name":    reporter_name,
        "reporter_phone":   reporter_phone,
        "image_path":       image_path,
        "ai_detected":      ai_detected,
        "ai_confidence":    detection.confidence if detection else None,
        "ai_pothole_count": detection.pothole_count if detection else 0,
        "ai_area_px2":      detection.total_area_px2 if detection else None,
        "authority_code":   authority.authority_code,
        "authority_name":   authority.authority_name,
        "authority_type":   authority.authority_type,
        "helpline":         authority.helpline,
        "response_deadline": deadline,
        "extra_data": {
            "escalation":    authority.escalation,
            "response_hours": authority.response_hours,
            "ai_stages":     detection.stage_results if detection else {},
            "severity_label": SEVERITY_LABELS.get(final_severity, {}),
        },
    }


def format_complaint_response(complaint: dict) -> dict:
    """Format complaint dict for API response (clean, no internals)."""
    extra = {}
    if complaint.get("extra_data"):
        import json
        try:
            extra = json.loads(complaint["extra_data"]) if isinstance(complaint["extra_data"], str) else complaint["extra_data"]
        except Exception:
            pass

    sev_info = SEVERITY_LABELS.get(complaint.get("severity", "MEDIUM"), {})
    return {
        "complaint_id":    complaint["complaint_id"],
        "status":          complaint["status"],
        "severity":        complaint["severity"],
        "severity_emoji":  sev_info.get("emoji", ""),
        "severity_hindi":  sev_info.get("hi", ""),
        "state":           complaint["state"],
        "district":        complaint["district"],
        "latitude":        complaint["latitude"],
        "longitude":       complaint["longitude"],
        "description":     complaint.get("description", ""),
        "reporter_name":   complaint.get("reporter_name", "Anonymous"),
        "authority_name":  complaint.get("authority_name", ""),
        "authority_type":  complaint.get("authority_type", ""),
        "helpline":        complaint.get("helpline", ""),
        "escalation":      extra.get("escalation", ""),
        "response_deadline": complaint.get("response_deadline", ""),
        "ai_detected":     bool(complaint.get("ai_detected")),
        "ai_confidence":   complaint.get("ai_confidence"),
        "ai_pothole_count": complaint.get("ai_pothole_count", 0),
        "filed_at":        complaint.get("filed_at", ""),
        "updated_at":      complaint.get("updated_at", ""),
        "image_url":       f"/uploads/{complaint['image_path']}" if complaint.get("image_path") else None,
        "timeline":        complaint.get("timeline", []),
    }