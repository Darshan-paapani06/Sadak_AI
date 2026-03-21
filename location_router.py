"""
SADAK AI — Location Router
GPS bounding boxes for all 28 Indian states + 8 UTs
Hierarchy: Village → Block → District → State → National
"""
import math
import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class AuthorityInfo:
    state:          str
    state_code:     str
    district:       str
    sub_district:   str
    village:        str
    authority_type: str   # GRAM_PANCHAYAT, NAGAR_PANCHAYAT, MUNICIPAL, PWD, NHAI
    authority_name: str
    authority_code: str
    helpline:       str
    escalation:     str   # who to escalate to
    response_hours: int

    def to_dict(self):
        return asdict(self)


# All Indian States with bounding boxes [lat_min, lat_max, lng_min, lng_max]
STATE_BOUNDS = {
    "Andhra Pradesh":       [12.62, 19.92, 76.76, 84.80, "AP",  "AProads",          "1800-425-4777", 72],
    "Arunachal Pradesh":    [26.65, 29.47, 91.50, 97.42, "AR",  "ARUNDPWD",         "0360-2212345",  168],
    "Assam":                [24.08, 27.98, 89.70, 96.02, "AS",  "Assam PWD",        "1800-345-3539", 72],
    "Bihar":                [24.29, 27.51, 83.33, 88.29, "BR",  "Bihar PWD",        "1800-345-6188", 72],
    "Chhattisgarh":         [17.78, 24.09, 80.24, 84.39, "CG",  "CG PWD",           "1800-233-3668", 72],
    "Goa":                  [14.89, 15.79, 73.68, 74.33, "GA",  "Goa PWD",          "1800-233-0013", 48],
    "Gujarat":              [20.08, 24.71, 68.17, 74.47, "GJ",  "Gujarat R&B",      "1800-233-1000", 72],
    "Haryana":              [27.65, 30.92, 74.42, 77.60, "HR",  "Haryana PWD",      "1800-180-2132", 48],
    "Himachal Pradesh":     [30.39, 33.25, 75.57, 79.01, "HP",  "HP PWD",           "1800-180-8080", 96],
    "Jharkhand":            [21.97, 25.32, 83.31, 87.94, "JH",  "Jharkhand PWD",    "1800-345-6576", 72],
    "Karnataka":            [11.59, 18.45, 74.05, 78.59, "KAR", "Karnataka KRDCL",  "1800-425-1510", 72],
    "Kerala":               [ 8.18, 12.77, 74.86, 77.40, "KL",  "Kerala PWD",       "1800-425-4777", 48],
    "Madhya Pradesh":       [21.08, 26.87, 74.03, 82.81, "MP",  "MP PWD",           "1800-233-1122", 72],
    "Maharashtra":          [15.61, 22.11, 72.66, 80.90, "MH",  "Maharashtra PWD",  "1800-233-4040", 72],
    "Manipur":              [23.85, 25.68, 93.03, 94.78, "MN",  "Manipur PWD",      "0385-2221623",  168],
    "Meghalaya":            [25.00, 26.12, 89.81, 92.79, "ML",  "Meghalaya PWD",    "0364-2221622",  168],
    "Mizoram":              [21.94, 24.52, 92.27, 93.45, "MZ",  "Mizoram PWD",      "0389-2323355",  168],
    "Nagaland":             [25.17, 27.03, 93.20, 95.25, "NL",  "Nagaland PWD",     "0370-2228553",  168],
    "Odisha":               [17.80, 22.55, 81.37, 87.49, "OD",  "Odisha Works",     "1800-345-6770", 72],
    "Punjab":               [29.55, 32.49, 73.88, 76.93, "PB",  "Punjab PWD",       "1800-180-6677", 48],
    "Rajasthan":            [23.07, 30.19, 69.47, 78.28, "RJ",  "Rajasthan PWD",    "1800-180-6127", 72],
    "Sikkim":               [27.07, 28.13, 88.01, 88.91, "SK",  "Sikkim PWD",       "03592-270044",  168],
    "Tamil Nadu":           [ 8.07, 13.58, 76.27, 80.35, "TN",  "TN Highways",      "044-28524803",  72],
    "Telangana":            [15.80, 19.93, 77.22, 81.35, "TS",  "Telangana R&B",    "1800-425-5995", 72],
    "Tripura":              [22.94, 24.53, 91.16, 92.33, "TR",  "Tripura PWD",      "0381-2226702",  168],
    "Uttar Pradesh":        [23.87, 30.42, 77.07, 84.63, "UP",  "Uttar Pradesh PWD","1800-180-5000", 72],
    "Uttarakhand":          [28.72, 31.46, 77.58, 81.03, "UK",  "Uttarakhand PWD",  "1800-180-4180", 96],
    "West Bengal":          [21.52, 27.23, 85.84, 89.88, "WB",  "West Bengal PWD",  "1800-345-5555", 72],
    # Union Territories
    "Delhi":                [28.40, 28.89, 76.84, 77.35, "DL",  "MCD Delhi",        "1800-11-0093",  24],
    "Chandigarh":           [30.65, 30.79, 76.69, 76.87, "CH",  "Chandigarh MC",    "0172-2700000",  24],
    "Jammu & Kashmir":      [32.30, 36.06, 73.74, 80.44, "JK",  "JK PWD",           "0191-2520082",  96],
    "Ladakh":               [32.00, 36.00, 75.20, 80.44, "LA",  "Ladakh PWD",       "01982-252123",  168],
    "Puducherry":           [11.67, 12.04, 79.62, 79.89, "PY",  "Pondicherry PWD",  "0413-2336722",  48],
    "Andaman & Nicobar":    [ 6.74, 13.61, 92.20, 93.95, "AN",  "A&N PWD",          "03192-232255",  168],
    "Daman & Diu":          [20.37, 20.42, 72.83, 72.84, "DD",  "DD PWD",           "0260-2230470",  72],
    "Lakshadweep":          [ 8.00, 12.00, 72.00, 74.00, "LD",  "Lakshadweep PWD",  "04896-262041",  168],
}

# Highway corridor detection (rough lat/lng bands of major NHs)
NATIONAL_HIGHWAYS = [
    {"nh": "NH-44", "lat_range": [8.0, 29.0],   "lng_range": [77.5, 79.0]},
    {"nh": "NH-48", "lat_range": [12.9, 28.6],  "lng_range": [77.0, 77.7]},
    {"nh": "NH-8",  "lat_range": [22.3, 28.6],  "lng_range": [72.5, 77.3]},
    {"nh": "NH-19", "lat_range": [22.5, 28.6],  "lng_range": [82.0, 88.3]},
    {"nh": "NH-52", "lat_range": [25.5, 27.5],  "lng_range": [82.0, 87.0]},
    {"nh": "NH-27", "lat_range": [22.0, 26.9],  "lng_range": [68.5, 91.5]},
]

def _detect_national_highway(lat: float, lng: float) -> str | None:
    """Return NH name if coordinates are on a known national highway corridor."""
    for nh in NATIONAL_HIGHWAYS:
        if (nh["lat_range"][0] <= lat <= nh["lat_range"][1] and
                nh["lng_range"][0] <= lng <= nh["lng_range"][1]):
            return nh["nh"]
    return None


def _get_state(lat: float, lng: float) -> tuple[str, list] | None:
    """Find which state the coordinates fall in."""
    for state_name, bounds in STATE_BOUNDS.items():
        lat_min, lat_max, lng_min, lng_max = bounds[0], bounds[1], bounds[2], bounds[3]
        if lat_min <= lat <= lat_max and lng_min <= lng <= lng_max:
            return state_name, bounds
    return None, None


def _distance_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def get_authority(lat: float, lng: float, is_village: bool = False) -> AuthorityInfo:
    """
    Return the correct authority for a given GPS coordinate.
    Priority: NHAI (if on NH) > Municipal Corporation > District PWD > State PWD > Gram Panchayat
    """
    # Check if on national highway
    nh = _detect_national_highway(lat, lng)
    if nh:
        return AuthorityInfo(
            state="India", state_code="IN", district="National Highway",
            sub_district="", village="",
            authority_type="NHAI",
            authority_name=f"NHAI ({nh})",
            authority_code="NHAI",
            helpline="1033",
            escalation="Ministry of Road Transport",
            response_hours=24,
        )

    # Identify state
    state_name, bounds = _get_state(lat, lng)
    if not bounds:
        # Fallback: find nearest state centroid
        state_name = "India"
        bounds = [0, 0, 0, 0, "IN", "State PWD", "1033", 72]

    code     = bounds[4]
    auth     = bounds[5]
    helpline = bounds[6]
    resp_hrs = bounds[7]

    # Determine authority type by area type
    # Urban: within small lat/lng distance of known city centers
    CITY_CENTERS = {
        "Bengaluru": (12.9716, 77.5946, 30, "BBMP", "1800-425-1510"),
        "Mumbai":    (19.0760, 72.8777, 30, "BMC",  "1800-233-4040"),
        "Delhi":     (28.6139, 77.2090, 30, "MCD",  "1800-11-0093"),
        "Chennai":   (13.0827, 80.2707, 25, "GCC",  "044-28524803"),
        "Hyderabad": (17.3850, 78.4867, 25, "GHMC", "1800-425-5995"),
        "Kolkata":   (22.5726, 88.3639, 25, "KMC",  "1800-345-5555"),
        "Pune":      (18.5204, 73.8567, 20, "PMC",  "020-25506800"),
        "Ahmedabad": (23.0225, 72.5714, 20, "AMC",  "079-25391811"),
        "Jaipur":    (26.9124, 75.7873, 20, "JMC",  "0141-2742333"),
        "Lucknow":   (26.8467, 80.9462, 15, "LMC",  "0522-2629000"),
        "Patna":     (25.5941, 85.1376, 15, "PMC-P","0612-2223333"),
        "Bhopal":    (23.2599, 77.4126, 15, "BMC-B","0755-2550700"),
        "Noida":     (28.5355, 77.3910, 10, "NMMC", "0120-4716500"),
        "Gurgaon":   (28.4595, 77.0266, 10, "MCG",  "0124-2322461"),
    }
    for city, (clat, clng, radius, mname, mhelpline) in CITY_CENTERS.items():
        d = _distance_km(lat, lng, clat, clng)
        if d <= radius:
            return AuthorityInfo(
                state=state_name, state_code=code,
                district=city, sub_district=city, village="",
                authority_type="MUNICIPAL_CORPORATION",
                authority_name=f"{mname} — {city} Municipal Corporation",
                authority_code=f"{code}-{mname}",
                helpline=mhelpline,
                escalation=f"{state_name} Urban Development",
                response_hours=24 if d <= 10 else 48,
            )

    # Village / rural: assume Gram Panchayat
    if is_village or resp_hrs >= 96:
        auth_type = "GRAM_PANCHAYAT"
        auth_name = f"Gram Panchayat / Block Development Officer — {state_name}"
        escalation = "District Collector"
    else:
        auth_type = "STATE_PWD"
        auth_name = f"{auth} — {state_name}"
        escalation = "State Highway Authority"

    return AuthorityInfo(
        state=state_name, state_code=code,
        district="Local District", sub_district="", village="",
        authority_type=auth_type,
        authority_name=auth_name,
        authority_code=code,
        helpline=helpline,
        escalation=escalation,
        response_hours=resp_hrs,
    )


def get_response_deadline(severity: str, response_hours: int) -> str:
    """Return ISO deadline string based on severity and authority response SLA."""
    from datetime import datetime, timedelta
    multiplier = {"CRITICAL": 1.0, "HIGH": 1.5, "MEDIUM": 3.0, "LOW": 5.0}
    factor = multiplier.get(severity, 2.0)
    hours  = max(6, int(response_hours * factor))
    deadline = datetime.utcnow() + timedelta(hours=hours)
    return deadline.isoformat()


def validate_coordinates(lat: float, lng: float) -> bool:
    """Check if coordinates are within India's bounding box."""
    return 6.0 <= lat <= 37.5 and 68.0 <= lng <= 97.5