"""
SADAK AI — Road Quality Index Engine
Calculates a 0-100 quality score per road segment/district/state.
Higher = better road. Below 40 = poor. Below 20 = critical.
"""
import sqlite3, os, math, logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

logger  = logging.getLogger(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sadak_ai.db")

@dataclass
class RoadQualityScore:
    zone:         str       # district or state name
    zone_type:    str       # district / state
    score:        int       # 0-100
    grade:        str       # A / B / C / D / F
    total_reports:int
    critical:     int
    high:         int
    resolved_pct: float
    trend:        str       # improving / worsening / stable
    worst_spots:  list      # top 3 GPS hotspots

def _grade(score: int) -> str:
    if score >= 80: return "A"
    if score >= 60: return "B"
    if score >= 40: return "C"
    if score >= 20: return "D"
    return "F"

def _trend(recent: int, older: int) -> str:
    if older == 0: return "stable"
    change = (recent - older) / max(older, 1)
    if change > 0.2:  return "worsening"
    if change < -0.2: return "improving"
    return "stable"

def calculate_district_score(district: str, state: str) -> RoadQualityScore:
    """Calculate road quality score for a district."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        now   = datetime.now(timezone.utc)
        d30   = (now - timedelta(days=30)).isoformat()
        d60   = (now - timedelta(days=60)).isoformat()

        rows = conn.execute("""
            SELECT severity, status, latitude, longitude, filed_at, ai_confidence
            FROM complaints
            WHERE LOWER(district)=LOWER(?) AND LOWER(state)=LOWER(?)
        """, (district, state)).fetchall()

        if not rows:
            conn.close()
            return RoadQualityScore(
                zone=district, zone_type="district", score=100,
                grade="A", total_reports=0, critical=0, high=0,
                resolved_pct=100.0, trend="stable", worst_spots=[]
            )

        total    = len(rows)
        critical = sum(1 for r in rows if r["severity"] == "CRITICAL")
        high     = sum(1 for r in rows if r["severity"] == "HIGH")
        medium   = sum(1 for r in rows if r["severity"] == "MEDIUM")
        resolved = sum(1 for r in rows if r["status"]   == "RESOLVED")

        # Recent vs older complaints for trend
        recent = sum(1 for r in rows if (r["filed_at"] or "") >= d30)
        older  = sum(1 for r in rows if d60 <= (r["filed_at"] or "") < d30)

        # Score formula:
        # Start at 100, deduct for each complaint weighted by severity
        # Critical = -8, High = -5, Medium = -2, Low = -1
        # Bonus for resolved: +3 each
        base = 100
        base -= critical * 8
        base -= high     * 5
        base -= medium   * 2
        base += resolved * 3
        base  = max(0, min(100, base))

        # Resolution boost
        res_pct = (resolved / total * 100) if total > 0 else 100
        if res_pct > 80: base = min(100, base + 5)

        # Find worst GPS clusters (group nearby points)
        spots = _find_hotspots(rows)

        conn.close()
        return RoadQualityScore(
            zone=district, zone_type="district",
            score=int(base), grade=_grade(int(base)),
            total_reports=total, critical=critical, high=high,
            resolved_pct=round(res_pct, 1),
            trend=_trend(recent, older),
            worst_spots=spots[:3]
        )
    except Exception as e:
        logger.error("Score error: %s", e)
        return RoadQualityScore(district, "district", 50, "C", 0, 0, 0, 0, "stable", [])

def calculate_state_scores() -> list:
    """Calculate scores for all states with complaints."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        states = conn.execute(
            "SELECT DISTINCT state FROM complaints WHERE state IS NOT NULL"
        ).fetchall()
        conn.close()

        results = []
        for s in states:
            state = s["state"]
            conn  = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows  = conn.execute(
                "SELECT severity, status, latitude, longitude, filed_at FROM complaints WHERE LOWER(state)=LOWER(?)",
                (state,)
            ).fetchall()
            conn.close()

            total    = len(rows)
            critical = sum(1 for r in rows if r["severity"] == "CRITICAL")
            high     = sum(1 for r in rows if r["severity"] == "HIGH")
            resolved = sum(1 for r in rows if r["status"]   == "RESOLVED")
            base     = max(0, min(100, 100 - critical*8 - high*5 + resolved*3))
            res_pct  = resolved / total * 100 if total > 0 else 100

            results.append({
                "state":       state,
                "score":       int(base),
                "grade":       _grade(int(base)),
                "total":       total,
                "critical":    critical,
                "resolved_pct": round(res_pct, 1),
            })

        results.sort(key=lambda x: x["score"])
        return results
    except Exception as e:
        logger.error("State scores error: %s", e)
        return []

def _find_hotspots(rows) -> list:
    """Group GPS points into clusters — top hotspots."""
    points = [(r["latitude"], r["longitude"], r["severity"])
              for r in rows if r["latitude"] and r["longitude"]]
    if not points: return []

    clusters = []
    used     = set()

    for i, (lat, lng, sev) in enumerate(points):
        if i in used: continue
        cluster = [(lat, lng, sev)]
        used.add(i)
        for j, (lat2, lng2, sev2) in enumerate(points):
            if j in used: continue
            if _dist(lat, lng, lat2, lng2) < 0.5:  # within 500m
                cluster.append((lat2, lng2, sev2))
                used.add(j)
        sev_score = sum({"CRITICAL":4,"HIGH":3,"MEDIUM":2,"LOW":1}.get(s,1) for _,_,s in cluster)
        clat = sum(p[0] for p in cluster) / len(cluster)
        clng = sum(p[1] for p in cluster) / len(cluster)
        clusters.append({"lat": round(clat,5), "lng": round(clng,5),
                          "count": len(cluster), "severity_score": sev_score})

    clusters.sort(key=lambda x: -x["severity_score"])
    return clusters[:3]

def _dist(lat1, lng1, lat2, lng2) -> float:
    """Approximate distance in km between two GPS points."""
    R    = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a    = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))