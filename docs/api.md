# KisanSaathi API

Base URL: `http://127.0.0.1:8000`. Interactive schema: `/docs`. No authentication; bind to loopback for the demo. All shared payloads use `app/schemas.py` unchanged. Extra request fields are rejected.

| Route | Behavior |
| --- | --- |
| `GET /health` | Status, data mode and mock flag |
| `GET /meta` | Configured product labels, examples and demo scenarios; no secrets |
| `GET /farmers` | List profiles |
| `GET /farmers/{farmer_id}` | Read one profile |
| `POST /farmers` | Create a complete `FarmerProfile`; 201 or duplicate-ID 409 |
| `PUT /farmers/{farmer_id}` | Replace a complete profile; body ID must match URL |
| `POST /advise` | Flat `AdvisoryResponse` fields plus `debug` |
| `POST /alerts/generate` | On-demand spray/irrigation/harvest checks for every saved crop; MEDIUM/HIGH only |
| `GET /dashboard/{farmer_id}` | Weather, per-crop market/stage evidence, five risks and data gaps |
| `GET /fpo` | One row per farmer/crop; empty profiles remain visible |

`demo_scenario` is optional on advice/alerts bodies and dashboard/FPO query parameters. It accepts `rain`, `dry`, `heatwave`, `api_failure`, `stale_mandi`, `no_mandi`; live mode rejects it with 422.

## Advice

Request:

```json
{"farmer_id":"F001","question":"Soybean mein spray karun kya?","demo_scenario":"rain"}
```

The response has `answer_text`, `language`, `recommendation`, `risk_level`, `sources`, `uncertainty_note`, `data_gaps`, `refer_to_expert`, and an additional `debug` object. Debug includes validated intent, `ToolResult` dictionaries, `RiskResult` objects, timings in milliseconds, provider identity and guardrail outcomes. The response never includes credentials.

Questions must be nonblank and at most 500 characters. The API is stateless: when it asks which crop, resubmit the original question with the crop. The Streamlit UI performs this small clarification continuation automatically.

Bash/curl examples:

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/farmers
curl -s -X POST http://127.0.0.1:8000/advise -H 'Content-Type: application/json' -d '{"farmer_id":"F001","question":"Should I spray soybean?","demo_scenario":"rain"}'
curl -s -X POST http://127.0.0.1:8000/advise -H 'Content-Type: application/json' -d '{"farmer_id":"F001","question":"Should I spray soybean?","demo_scenario":"dry"}'
curl -s -X POST http://127.0.0.1:8000/alerts/generate -H 'Content-Type: application/json' -d '{"farmer_id":"F001"}'
curl -s 'http://127.0.0.1:8000/dashboard/F001?demo_scenario=rain'
curl -s http://127.0.0.1:8000/fpo
```

PowerShell examples avoid shell-specific JSON quoting:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/health'
$question = @{farmer_id='F001'; question='Should I spray soybean?'; demo_scenario='rain'} | ConvertTo-Json
Invoke-RestMethod 'http://127.0.0.1:8000/advise' -Method Post -ContentType 'application/json' -Body $question
$alert = @{farmer_id='F001'} | ConvertTo-Json
Invoke-RestMethod 'http://127.0.0.1:8000/alerts/generate' -Method Post -ContentType 'application/json' -Body $alert
Invoke-RestMethod 'http://127.0.0.1:8000/fpo'
```

To create another fictional profile or update one, use the exact `FarmerProfile` example in `contract.md` with a chosen demo ID. `POST /farmers` inserts; `PUT /farmers/F001` replaces the profile. The sowing date is required for each listed crop; use an empty crop list when it is unknown.

## Errors and limits

- 400: URL/body ID mismatch.
- 404: farmer not found.
- 409: duplicate farmer ID.
- 422: invalid profile, question, extra fields or demo scenario in live mode.
- 429: per-farmer rate limit; respect `Retry-After`.
- 500: generic controlled internal failure, with no raw exception/request data.

A failed tool usually produces a successful HTTP response with UNKNOWN risk and data gaps, not HTTP 500. Source failure is part of the advisory contract. An empty alert list can mean insufficient evidence; it must not be interpreted as proof of low risk. Check the dashboard's completeness and source ages.

The single-process rate limiter covers advice, alerts, dashboard and group refreshes. Farmer CRUD is unthrottled for this local demo. No alert is sent to a third party; generation returns data only.
