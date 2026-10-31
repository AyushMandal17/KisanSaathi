"""Validated extraction, with deterministic safety and crop-resolution boundaries."""
from __future__ import annotations

import json
import re
from typing import Any

import yaml

from app.agent.language import detect_language
from app.agent.prompts import INTENT_SYSTEM
from app.llm.client import LLM, LLMUnavailable
from app.schemas import FarmerProfile, Intent

DOSAGE = re.compile(
    r"\b(dosage|dose|mix(?:ing)?|ratio|pesticide\s+name|chemical\s+name|"
    r"millilit(?:er|re)|ml|mg|ppm)\b|खुराक|मात्रा|मिलाऊ|मिलाना|मिश्रण|"
    r"कौन\s*सी\s*दवा|कौनसा\s*कीटनाशक|कितनी\s*दवा|kitn[ai].*dawa|"
    r"kitn[ai].*(?:chemical|pesticide)|kaun.*dawa|\b(?:matra|maatra)\b|"
    r"how\s+(?:much|many).*(?:pesticide|insecticide|fungicide|chemical|spray)|"
    r"(?:pesticide|insecticide|fungicide|chemical).*(?:quantity|concentration)|"
    r"(?:quantity|concentration).*(?:pesticide|insecticide|fungicide|chemical)|"
    r"lit(?:er|re)s?\s*(?:per|/)\s*(?:acre|hectare|tank)", re.IGNORECASE)
INJECTION = re.compile(
    r"ignore.{0,50}(?:instruction|rule|previous)|system\s*(?:prompt|message)|"
    r"reveal.{0,25}(?:key|secret)|override|jailbreak|developer\s+message|"
    r"निर्देश.*भूल|नियम.*भूल", re.IGNORECASE)
NON_FARM = re.compile(r"\b(stock\s+price|share\s+price|bitcoin|cryptocurrency|laptop|"
                      r"movie|football|cricket|car|vehicle|politics)\b", re.IGNORECASE)
KEYWORDS = [
    ("sell", r"\b(sell|bech|bechu|bechun|bikri)\b|बेच|बिक्री"),
    ("price", r"\b(price|prices|rate|bhav|bhaav|mandi)\b|भाव|मंडी|कीमत"),
    ("spray", r"\b(spray|spraying|chhidkav|chidkav|chhidkau)\b|स्प्रे|छिड़क|छिडक"),
    ("irrigation", r"\b(irrigat\w*|water|watering|pani|paani|sinchai)\b|सिंचाई|पानी"),
    ("harvest", r"\b(harvest\w*|cut|katai|kaat)\b|कटाई|काट"),
    ("sowing", r"\b(sow\w*|plant\w*|buwai|buvai|boye|boon)\b|बुवाई|बोना|बोऊ"),
    ("crop_stage", r"\b(stage|growth|age|days.*sow)\b|अवस्था|कितने दिन|फसल.*उम्र"),
    ("weather", r"\b(weather|rain|rainfall|temperature|mausam|barish|baarish|heatwave)\b|मौसम|बारिश|वर्षा|तापमान"),
]


def blocked_question(question: str) -> bool:
    return bool(DOSAGE.search(question) or INJECTION.search(question) or NON_FARM.search(question))


class IntentExtractor:
    def __init__(self, settings: Any, llm: LLM):
        self.llm = llm
        self.catalog = yaml.safe_load(settings.crops_path.read_text(encoding="utf-8"))["crops"]

    def seed(self, profile: FarmerProfile, question: str) -> Intent:
        language = detect_language(question, profile.language)
        kind = "other"
        if not blocked_question(question):
            kind = next((name for name, pattern in KEYWORDS
                         if re.search(pattern, question, re.IGNORECASE)), "other")
        text = question.casefold()
        names = set(self.catalog) | {plot.crop for plot in profile.crops}
        matches = []
        for crop in names:
            aliases = [crop] + list(self.catalog.get(crop, {}).get("aliases", []))
            if any(re.search(r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)", text)
                   for alias in aliases):
                matches.append(crop)
        crop = matches[0] if len(matches) == 1 else None
        # An explicitly named unsupported crop must not silently become the saved crop.
        named = re.findall(r"\b(?:spray|irrigate|harvest|sow|plant|sell|water)\s+"
                           r"(?:(?:my|the)\s+)?([a-z]+)\b|\b([a-z]+)\s+(?:mein|ki|ka)\b",
                           text)
        stop = {"today", "now", "tomorrow", "crop", "crops", "field", "seed", "seeds",
                "please", "it", "my", "the", "aaj", "kal", "karun", "karu", "kya", "weather"}
        aliases = {alias.casefold() for name in names for alias in
                   [name] + list(self.catalog.get(name, {}).get("aliases", []))}
        unknown_named = any(token and token not in aliases and token not in stop
                            for pair in named for token in pair)
        if not matches and not unknown_named and len(profile.crops) == 1:
            crop = profile.crops[0].crop
        missing = ["crop"] if kind not in {"other", "weather"} and not crop else []
        return Intent(intent=kind, crop=crop, language=language,
                      missing_fields=missing, confidence=0.95 if kind != "other" else 0.5)

    async def extract(self, profile: FarmerProfile, question: str) -> Intent:
        seed = self.seed(profile, question)
        if blocked_question(question):
            return seed
        payload = {"question": question, "available_crops": list(self.catalog),
                   "seed": seed.model_dump()}
        try:
            inferred = await self.llm.complete([
                {"role": "system", "content": INTENT_SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}], Intent)
            if not isinstance(inferred, Intent):
                return seed
            # Keep deterministic safety, language and profile resolution authoritative.
            # Unknown wording stays conservative in this deliberately bounded MVP.
            return inferred.model_copy(update={"intent": seed.intent, "crop": seed.crop,
                                               "language": seed.language,
                                               "missing_fields": seed.missing_fields})
        except (LLMUnavailable, ValueError, TypeError):
            return seed
