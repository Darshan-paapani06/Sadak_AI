"""
SADAK AI — 22 Indian Language Support
Translates UI strings and complaint descriptions using
Google Translate API (free tier) or falls back to English.
"""
import logging, urllib.request, urllib.parse, json

logger = logging.getLogger(__name__)

# All 22 scheduled languages of India + English
LANGUAGES = {
    "en":    "English",
    "hi":    "हिंदी (Hindi)",
    "bn":    "বাংলা (Bengali)",
    "te":    "తెలుగు (Telugu)",
    "mr":    "मराठी (Marathi)",
    "ta":    "தமிழ் (Tamil)",
    "ur":    "اردو (Urdu)",
    "gu":    "ગુજરાતી (Gujarati)",
    "kn":    "ಕನ್ನಡ (Kannada)",
    "ml":    "മലയാളം (Malayalam)",
    "pa":    "ਪੰਜਾਬੀ (Punjabi)",
    "or":    "ଓଡ଼ିଆ (Odia)",
    "as":    "অসমীয়া (Assamese)",
    "mai":   "मैथिली (Maithili)",
    "sat":   "ᱥᱟᱱᱛᱟᱲᱤ (Santali)",
    "ks":    "کٲشُر (Kashmiri)",
    "ne":    "नेपाली (Nepali)",
    "si":    "සිංහල (Sinhala)",
    "kok":   "कोंकणी (Konkani)",
    "doi":   "डोगरी (Dogri)",
    "mni":   "মৈতৈলোন্ (Manipuri)",
    "bho":   "भोजपुरी (Bhojpuri)",
    "sd":    "سنڌي (Sindhi)",
}

# Key UI strings — translated manually for reliability
UI_STRINGS = {
    "scan_road":        {"en":"Scan Road","hi":"सड़क स्कैन करें","ta":"சாலை ஸ்கேன்","te":"రోడ్ స్కాన్","kn":"ರಸ್ತೆ ಸ್ಕ್ಯಾನ್","ml":"റോഡ് സ്കാൻ","mr":"रस्ता स्कॅन","gu":"રોડ સ્કેન","bn":"রাস্তা স্ক্যান","pa":"ਸੜਕ ਸਕੈਨ","or":"ରାସ୍ତା ସ୍କ୍ୟାନ","as":"ৰাস্তা স্কেন","ur":"سڑک اسکین"},
    "report_pothole":   {"en":"Report Pothole","hi":"गड्ढा रिपोर्ट करें","ta":"குழி புகார்","te":"గుంత నివేదన","kn":"ಗುಂಡಿ ವರದಿ","ml":"കുഴി റിപ്പോർട്ട്","mr":"खड्डा नोंदवा","gu":"ખાડો નોંધો","bn":"গর্ত রিপোর্ট","pa":"ਖੱਡਾ ਰਿਪੋਰਟ","or":"ଗାତ ରିପୋର୍ଟ","as":"গাঁত ৰিপোৰ্ট","ur":"گڑھا رپورٹ"},
    "my_complaints":    {"en":"My Complaints","hi":"मेरी शिकायतें","ta":"என் புகார்கள்","te":"నా ఫిర్యాదులు","kn":"ನನ್ನ ದೂರುಗಳು","ml":"എൻ്റെ പരാതികൾ","mr":"माझ्या तक्रारी","gu":"મારી ફરિયાદ","bn":"আমার অভিযোগ","pa":"ਮੇਰੀਆਂ ਸ਼ਿਕਾਇਤਾਂ","or":"ମୋ ଅଭିଯୋଗ","as":"মোৰ অভিযোগ","ur":"میری شکایات"},
    "road_quality":     {"en":"Road Quality","hi":"सड़क गुणवत्ता","ta":"சாலை தரம்","te":"రోడ్ నాణ్యత","kn":"ರಸ್ತೆ ಗುಣಮಟ್ಟ","ml":"റോഡ് ഗുണനിലവാരം","mr":"रस्ता गुणवत्ता","gu":"રોડ ગુણવત્તા","bn":"রাস্তার মান","pa":"ਸੜਕ ਗੁਣਵੱਤਾ","or":"ରାସ୍ତା ଗୁଣ","as":"ৰাস্তাৰ মান","ur":"سڑک معیار"},
    "pothole_detected": {"en":"Pothole Detected","hi":"गड्ढा मिला","ta":"குழி கண்டுபிடிக்கப்பட்டது","te":"గుంత గుర్తించబడింది","kn":"ಗುಂಡಿ ಕಂಡುಬಂದಿದೆ","ml":"കുഴി കണ്ടെത്തി","mr":"खड्डा आढळला","gu":"ખાડો મળ્યો","bn":"গর্ত পাওয়া গেছে","pa":"ਖੱਡਾ ਮਿਲਿਆ","or":"ଗାତ ଚିହ୍ନଟ","as":"গাঁত পোৱা গৈছে","ur":"گڑھا ملا"},
    "file_complaint":   {"en":"File Complaint","hi":"शिकायत दर्ज करें","ta":"புகார் பதிவு","te":"ఫిర్యాదు నమోదు","kn":"ದೂರು ಸಲ್ಲಿಸಿ","ml":"പരാതി ഫയൽ","mr":"तक्रार नोंदवा","gu":"ફરિયાદ નોંધો","bn":"অভিযোগ করুন","pa":"ਸ਼ਿਕਾਇਤ ਦਰਜ","or":"ଅଭିଯୋଗ ଦାଖଲ","as":"অভিযোগ দাখিল","ur":"شکایت درج"},
    "severity_critical":{"en":"Critical","hi":"अति गंभीर","ta":"மிகவும் தீவிரம்","te":"చాలా తీవ్రమైన","kn":"ತೀವ್ರ","ml":"ഗുരുതര","mr":"अतिशय गंभीर","gu":"ખૂب ગંભીર","bn":"অতি গুরুতর","pa":"ਬਹੁਤ ਗੰਭੀਰ","or":"ଅତ୍ୟନ୍ତ ଗୁରୁତର","as":"অতি গুৰুতৰ","ur":"انتہائی سنگین"},
    "authority_nhai":   {"en":"NHAI (National Highway)","hi":"NHAI (राष्ट्रीय राजमार्ग)","ta":"NHAI (தேசிய நெடுஞ்சாலை)","te":"NHAI (జాతీయ రహదారి)","kn":"NHAI (ರಾಷ್ಟ್ರೀಯ ಹೆದ್ದಾರಿ)","ml":"NHAI (ദേശീയ പാത)","mr":"NHAI (राष्ट्रीय महामार्ग)","gu":"NHAI (રાષ્ટ્રીય ધોરી માર્ગ)","bn":"NHAI (জাতীয় সড়ক)","pa":"NHAI (ਰਾਸ਼ਟਰੀ ਰਾਜਮਾਰਗ)","ur":"NHAI (قومی شاہراہ)"},
}

def get_language_list():
    """Return all 22+ languages for dropdown."""
    return [{"code": k, "name": v} for k, v in LANGUAGES.items()]

def get_ui_string(key: str, lang: str) -> str:
    """Get translated UI string. Falls back to English."""
    strings = UI_STRINGS.get(key, {})
    return strings.get(lang) or strings.get("en") or key

def translate_text(text: str, target_lang: str) -> str:
    """
    Translate text to target language using Google Translate (free endpoint).
    Falls back gracefully if unavailable.
    """
    if not text or target_lang == "en": return text
    try:
        params = urllib.parse.urlencode({
            "client": "gtx",
            "sl":     "auto",
            "tl":     target_lang,
            "dt":     "t",
            "q":      text[:500]
        })
        url = f"https://translate.googleapis.com/translate_a/single?{params}"
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read().decode())
        translated = "".join(part[0] for part in data[0] if part[0])
        return translated or text
    except Exception as e:
        logger.debug("Translate fallback: %s", e)
        return text

def translate_complaint_description(desc: str, target_lang: str) -> str:
    """Translate a complaint description."""
    return translate_text(desc, target_lang) if desc else desc