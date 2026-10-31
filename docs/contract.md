# Data contract

All modules exchange data using the models in `app/schemas.py`.
Each model below has one example. `tests/test_schemas.py` reads the JSON blocks
in this file and validates them, so **keep the headings and examples in sync with
the code**. Each heading must be exactly the model's class name.

Datetimes are ISO 8601 and timezone-aware (UTC in these examples).

All models reject unknown fields (`extra="forbid"`).

---

## CropPlot

One crop planted by a farmer.

```json
{
  "crop": "soybean",
  "sowing_date": "2026-07-05",
  "area_acres": 2.5
}
```

## FarmerProfile

Saved farmer profile. Location lives here, not in the question.

```json
{
  "farmer_id": "F001",
  "name": "Ramesh (demo)",
  "village": "Pithampur",
  "district": "Dhar",
  "state": "Madhya Pradesh",
  "lat": 22.6,
  "lon": 75.7,
  "language": "hi",
  "crops": [
    {
      "crop": "soybean",
      "sowing_date": "2026-07-05",
      "area_acres": 2.5
    }
  ]
}
```

## ToolResult

Standard output of a data tool. A failed tool sets `error` and `confidence`
must then be `"unknown"`.

```json
{
  "tool": "weather",
  "value": {
    "rain_next_48h_mm": 28.0,
    "rain_probability_pct": 70,
    "daily": [
      {"date": "2026-10-31", "rain_mm": 12.0},
      {"date": "2026-11-01", "rain_mm": 16.0}
    ]
  },
  "source": "Open-Meteo",
  "fetched_at": "2026-10-31T06:00:00Z",
  "is_cached": false,
  "confidence": "high",
  "error": null
}
```

Failed tool example (kept in the pipeline, never crashes it):

```json
{
  "tool": "mandi",
  "value": {},
  "source": "data.gov.in (Agmarknet)",
  "fetched_at": "2026-10-31T06:00:00Z",
  "is_cached": false,
  "confidence": "unknown",
  "error": "API timeout"
}
```

## RiskResult

Output of the rule-based risk engine. The LLM must not override it.

```json
{
  "risk_type": "spray",
  "level": "HIGH",
  "reasons": ["Rain above 20 mm expected within 48 hours"],
  "evidence": {"rain_next_48h_mm": 28.0, "threshold_mm": 20},
  "rule_source": "DEMO RULE - replace with KVK/ICAR sourced rule"
}
```

## Intent

Structured meaning of the farmer's question.

```json
{
  "intent": "spray",
  "crop": "soybean",
  "language": "hinglish",
  "missing_fields": [],
  "confidence": 0.93
}
```

## SourceRef

A cited data source. Filled in code from tool results, not by the LLM.

```json
{
  "name": "Open-Meteo",
  "fetched_at": "2026-10-31T06:00:00Z",
  "is_cached": false
}
```

## AdvisoryResponse

Final answer for the farmer and the dashboard.

```json
{
  "answer_text": "आज स्प्रे न करें। अगले 48 घंटों में लगभग 28 मिमी बारिश की संभावना है, दवा धुल सकती है। स्रोत: Open-Meteo।",
  "language": "hi",
  "recommendation": "dont",
  "risk_level": "HIGH",
  "sources": [
    {
      "name": "Open-Meteo",
      "fetched_at": "2026-10-31T06:00:00Z",
      "is_cached": false
    }
  ],
  "uncertainty_note": "बारिश की संभावना लगभग 70% है, मौसम बदल सकता है।",
  "data_gaps": [],
  "refer_to_expert": false
}
```
