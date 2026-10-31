"""Small, auditable Hindi/English fallback vocabulary for the hackathon scope."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from app.schemas import Intent, QuestionLanguage, RiskResult, ToolResult

TERMS = {
    "spray": ("छिड़काव", "spraying"),
    "irrigation": ("सिंचाई", "irrigation"),
    "harvest": ("कटाई", "harvesting"),
    "sowing": ("बुवाई", "sowing"),
    "sell": ("बिक्री", "selling"),
}


def detect_language(text: str, preferred: str = "hi") -> QuestionLanguage:
    if re.search(r"[\u0900-\u097f]", text):
        return "hi"
    if re.search(r"\b(aaj|kal|karu[n]?|karun|kya|mein|mai|ka|ki|hai|pani|paani|"
                 r"bech|dun|ruk|jaun|kitna|kitni|barish|baarish|sinchai|fasal|"
                 r"bhav|bhaav|buwai|buvai|katai)\b", text, re.IGNORECASE):
        return "hinglish"
    return "en" if text.strip() else ("en" if preferred == "en" else "hi")


def reply_language(intent: Intent) -> str:
    return "en" if intent.language == "en" else "hi"


def message(kind: str, language: str) -> str:
    hindi = language != "en"
    templates = {
        "clarify": ("आप किस फसल के बारे में पूछ रहे हैं?", "Which crop are you asking about?"),
        "other": ("मैं मौसम, मंडी भाव और फसल के कामों पर सीमित जानकारी दे सकता हूँ। "
                  "कृपया फसल से जुड़ा सवाल पूछें।", "I can help with weather, mandi prices and crop work. "
                  "Please ask a question about your crop."),
        "expert": ("मैं दवा का नाम, खुराक या मिश्रण नहीं बता सकता। "
                   "इसके लिए अपने कृषि विज्ञान केंद्र या कृषि अधिकारी से सलाह लें।",
                   "I cannot recommend pesticide names, doses or mixtures. "
                   "Please ask your KVK or local agriculture officer."),
    }
    return templates[kind][0 if hindi else 1]


def uncertainty(language: str, intent: str) -> str:
    if language == "en":
        if intent in {"price", "sell"}:
            return "Market prices change; these records do not predict future prices."
        if intent == "crop_stage":
            return "Crop stage is only a calendar estimate; check the actual crop."
        return "Weather can change; check field conditions and local guidance."
    if intent in {"price", "sell"}:
        return "मंडी भाव बदलते हैं; इन रिकॉर्ड से भविष्य का भाव तय नहीं होता।"
    if intent == "crop_stage":
        return "फसल की अवस्था केवल कैलेंडर का अनुमान है; खेत में जाँच करें।"
    return "मौसम बदल सकता है; खेत की स्थिति और स्थानीय सलाह जाँचें।"


def safe_body(intent: Intent, risk: RiskResult | None,
              results: dict[str, ToolResult], language: str) -> tuple[str, str]:
    """Return grounded text and a conservative recommendation; no generated numbers."""
    hi = language != "en"
    weather = results.get("weather")
    mandi = results.get("mandi")
    stage = results.get("crop_stage")
    simulated = any(r.value.get("simulated") or r.value.get("sample") for r in results.values())
    demo = bool(risk and (risk.evidence.get("demo_rule") or "DEMO" in risk.rule_source))
    recommendation = "unknown"
    if risk:
        action = TERMS[risk.risk_type][0 if hi else 1]
        if risk.level == "HIGH":
            body = (f"अभी {action} न करें।" if hi else f"Do not proceed with {action} now.")
            recommendation = "dont"
        elif risk.level == "MEDIUM":
            body = (f"{action} के लिए रुकें और स्थानीय स्थिति जाँचें।" if hi else
                    f"Wait and check local conditions before {action}.")
            recommendation = "wait"
        elif risk.level == "LOW":
            if risk.risk_type == "sell":
                body = ("मंडी के उपलब्ध भावों में अंतर कम है; बिक्री से पहले वास्तविक बोली और खर्च जाँचें।" if hi else
                        "Available mandi quotes are close; check actual bids and costs before selling.")
            else:
                body = (f"{action} में मौसम का जोखिम कम दिख रहा है; पहले खेत की स्थिति जाँचें।" if hi else
                        f"Weather risk for {action} appears lower; check the field before acting.")
            recommendation = "wait"
        else:
            body = ("भरोसेमंद जानकारी अधूरी है, इसलिए अभी काम करने का निर्णय नहीं दे सकता।" if hi else
                    "Reliable evidence is incomplete, so I cannot make an action recommendation.")
        if demo or simulated:
            body = ("डेमो: " if hi else "DEMO: ") + body
    else:
        body = ""

    if intent.intent in {"sell", "price"}:
        rows = mandi.value.get("prices", []) if mandi and not mandi.error else []
        if rows:
            prices = [row["modal_price"] for row in rows if isinstance(row.get("modal_price"), (int, float))]
            if prices:
                label = ("नमूना रिकॉर्ड" if hi else "Sample records") if mandi.value.get("sample") else (
                    "उपलब्ध रिकॉर्ड" if hi else "Available records")
                body += (f" {label} में सामान्य भाव ₹{min(prices):g} से ₹{max(prices):g} प्रति क्विंटल है।" if hi else
                         f" {label} show modal prices of ₹{min(prices):g} to ₹{max(prices):g} per quintal.")
        if not body:
            body = ("मंडी की भरोसेमंद जानकारी उपलब्ध नहीं है।" if hi else
                    "Reliable mandi data is unavailable.")
    elif intent.intent == "crop_stage":
        if stage and not stage.error:
            name = stage.value.get("stage_hi" if hi else "stage", stage.value.get("stage", ""))
            days = stage.value.get("days_since_sowing")
            body = (f"कैलेंडर के अनुसार अनुमानित अवस्था {name} है; बुवाई के बाद {days} दिन हुए हैं।" if hi else
                    f"The estimated calendar stage is {name}, at {days} days after sowing.")
        else:
            body = ("बुवाई की सही तारीख और फसल कैलेंडर के बिना अवस्था नहीं बता सकता।" if hi else
                    "I cannot estimate crop stage without a valid sowing date and crop calendar.")
    elif weather and not weather.error and (not risk or risk.level != "UNKNOWN"):
        rain = weather.value.get("rain_next_48h_mm")
        temp = weather.value.get("temperature_max_c")
        rule_id = str(risk.evidence.get("rule_id", "")) if risk else ""
        if "heat" in rule_id and isinstance(temp, (int, float)):
            body += (f" अधिकतम तापमान {temp:g}°C है, इसलिए गर्मी की स्थिति जाँचें।" if hi else
                     f" Maximum temperature is {temp:g}°C, so check heat conditions.")
        elif "immature" in rule_id and stage and not stage.error:
            name = stage.value.get("stage_hi" if hi else "stage", stage.value.get("stage", ""))
            body += (f" अनुमानित अवस्था {name} है; फसल की वास्तविक परिपक्वता जाँचें।" if hi else
                     f" The estimated stage is {name}; inspect actual crop maturity.")
        elif isinstance(rain, (int, float)):
            label = ("डेमो मौसम में" if hi else "The demo weather scenario has") if weather.value.get("simulated") else (
                "पूर्वानुमान में" if hi else "The forecast has")
            body += (f" {label} अगले 48 घंटों में {rain:g} मिमी बारिश है।" if hi else
                     f" {label} {rain:g} mm of rain over the next 48 hours.")
        if intent.intent == "weather" and isinstance(temp, (int, float)):
            body += (f" अधिकतम तापमान {temp:g}°C है।" if hi else f" Maximum temperature is {temp:g}°C.")
    if not body.strip():
        body = ("भरोसेमंद मौसम जानकारी उपलब्ध नहीं है।" if hi else "Reliable weather data is unavailable.")
    note = uncertainty(language, intent.intent)
    if intent.intent in {"irrigation", "sowing"}:
        note = ("मिट्टी की नमी मापी नहीं गई है; खेत की स्थिति और स्थानीय सलाह जाँचें।" if hi else
                "Soil moisture is not measured; check field conditions and local guidance.")
    body = body.strip() + " " + note
    if demo:
        body += (" नियम डेमो के हैं; कृषि विज्ञान केंद्र से पुष्टि करें।" if hi else
                 "These are demo rules; confirm them with your KVK.")
    return body, recommendation


def source_line(results: dict[str, ToolResult], language: str,
                now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    items = []
    for result in results.values():
        if result.error:
            continue
        stamp = result.fetched_at
        if stamp.tzinfo is None:
            age = "time unknown" if language == "en" else "समय अज्ञात"
        elif (now - stamp).total_seconds() < -60:
            age = "invalid future timestamp" if language == "en" else "समय भविष्य का है; मान्य नहीं"
        else:
            hours = max(0, int((now - stamp).total_seconds() // 3600))
            age = f"{hours}h ago" if language == "en" else f"{hours} घंटे पहले"
        cached = (", cached" if language == "en" else ", कैश") if result.is_cached else ""
        items.append(f"{result.source} ({age}{cached})")
    return ("Sources: " if language == "en" else "स्रोत: ") + "; ".join(items) if items else ""
