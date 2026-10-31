# KisanSaathi · किसान साथी

A runnable, text-first hackathon prototype for multilingual crop and resource advice in Malwa, Madhya Pradesh. Ask in Hindi, Hinglish or English; receive a short grounded answer, deterministic risk, sources and data gaps. Built with FastAPI, Pydantic v2, HTTPX, SQLAlchemy/SQLite, Streamlit and Plotly. No React, authentication, cloud database or deployment is required.

**Default mode is entirely offline:** fictional farmers, simulated weather, sample prices and a clearly identified mock language model. This is a demonstration, not validated field guidance. Every agronomic rule and calendar is labeled DEMO. Soil moisture is not measured.

## Quick start from a clean copy

Use Python **3.11 or 3.12**. Run commands from the folder containing this README. Keep the API and UI terminals open. The UI is at http://127.0.0.1:8501 and API documentation at http://127.0.0.1:8000/docs.

Windows PowerShell, terminal 1:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m scripts.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Windows PowerShell, terminal 2, in the same project folder:

```powershell
.\.venv\Scripts\python.exe -m streamlit run ui/streamlit_app.py --server.port 8501
```

Linux/macOS, terminal 1:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
cp .env.example .env
.venv/bin/python -m scripts.seed
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Linux/macOS, terminal 2:

```bash
.venv/bin/python -m streamlit run ui/streamlit_app.py --server.port 8501
```

`requirements-lock.txt` records the tested Python 3.12 environment. `requirements.txt` contains bounded direct dependencies for intentional upgrades. The seed inserts missing IDs only; running it again never overwrites edited farmer profiles. Do not overwrite an existing `.env` containing your credentials with the copy step.

### Already-prepared workspace on this computer

The build installed Python 3.12 and dependencies under the enclosing workspace's `work/` folder, without replacing the system Python. From this README's folder, the following commands reuse that environment:

```powershell
& '..\..\work\.venv\Scripts\python.exe' -m scripts.seed
& '..\..\work\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In a second terminal:

```powershell
& '..\..\work\.venv\Scripts\python.exe' -m streamlit run ui/streamlit_app.py --server.port 8501
```

The archive does not bundle a Python runtime, dependencies, database, API keys or personal information. After extracting it elsewhere, use the clean-copy instructions.

## Demo flow

1. Select **Ramesh (DEMO)** and **Rain ahead**. Ask `Soybean mein spray karun kya?` Expect Hindi, HIGH, `dont`, a demo-rule badge and 28 mm of explicitly simulated precipitation.
2. Select **Dry forecast** and ask again. Expect LOW screening risk and a cautious `wait`, not a field-use approval.
3. Ask `Aaj bech dun ya ruk jaun?`. Sample records are displayed; the sale decision remains UNKNOWN.
4. Select **Weather unavailable**. The answer must not guess a forecast or recommend proceeding.
5. Ask `What pesticide dose should I use?`. No tools run; the answer refers to KVK/agriculture staff.
6. Generate alerts without a question; refresh the FPO overview to see all three fictional profiles.
7. Select Meera and ask `Should I spray?`. After the crop clarification, type `soybean`; the UI resubmits the original question plus that crop.

See [the five-minute script](docs/demo_script.md), [API examples](docs/api.md), and [the data contract](docs/contract.md).

## Configuration

All secrets live in environment variables or the ignored `.env`. Never commit `.env`.

| Variable | Default / purpose |
| --- | --- |
| `DATA_MODE` | `demo`; set `live` for Open-Meteo and configured mandi calls |
| `DEMO_SCENARIO` | `rain`; alternatives `dry`, `heatwave`, `api_failure`, `stale_mandi`, `no_mandi` |
| `USE_MOCK_LLM` | `true`; false enables configured Groq/Gemini providers |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | Empty; only required for live model calls |
| `GROQ_BASE_URL`, `GROQ_MODEL` | OpenAI-compatible endpoint and configurable model |
| `GEMINI_BASE_URL`, `GEMINI_MODEL` | OpenAI-compatible endpoint and configurable model |
| `DATA_GOV_API_KEY`, `DATA_GOV_RESOURCE_ID` | Empty; live mandi remains disabled until both are supplied |
| `DATA_GOV_BASE_URL` | Configurable data.gov.in resource URL prefix |
| `DATABASE_URL` | Project-relative SQLite path under `runtime/` |
| `CACHE_PATH` | Separate persistent SQLite last-good tool cache |
| `WEATHER_URL` | Open-Meteo forecast endpoint |
| `WEATHER_TIMEOUT_SECONDS`, `TOOL_RETRIES` | 10 seconds per HTTP request; one retry |
| `WEATHER_TTL_SECONDS`, `WEATHER_MAX_AGE_HOURS` | Cache lookup TTL 3600 seconds; decision age limit 6 hours |
| `MANDI_TTL_SECONDS`, `MANDI_MAX_AGE_HOURS` | Cache TTL 21600 seconds; fetch/arrival age limit 48 hours |
| `LLM_TIMEOUT_SECONDS` | 15 seconds per provider request; SDK retries disabled |
| `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS` | 30 advice/dashboard/alert requests per farmer per 60 seconds |
| `API_BASE_URL` | Address used by Streamlit; default `http://127.0.0.1:8000` |
| `CORS_ORIGINS` | JSON array of allowed local origins |
| `LOG_LEVEL` | `INFO`; logs omit API keys, questions and full farmer profiles |

Restart the API after changing environment or configuration files. Restart the UI if its API address changes. A demo scenario in a request is rejected when `DATA_MODE=live`.

## Official API verification checklist

The following documentation was checked during the build on **31 October 2026**. Provider examples can change; verify again with the credentials and account you intend to use.

**Groq:** `.env.example` uses `https://api.groq.com/openai/v1` and `openai/gpt-oss-20b`. Verify your account's model access, current identifier, JSON-object support, rate limits and timeout behavior in [OpenAI compatibility](https://console.groq.com/docs/openai) and [model listings](https://console.groq.com/docs/models). The SDK sends `chat.completions.create`; Pydantic performs local JSON-schema validation.

**Gemini:** `.env.example` uses `https://generativelanguage.googleapis.com/v1beta/openai/` and `gemini-3.8-flash`, as shown in the [official compatibility guide](https://ai.google.dev/gemini-api/docs/openai). Verify current model availability, JSON output support, quotas and billing with your own account in the [model catalog](https://ai.google.dev/gemini-api/docs/models). Native Gemini API methods are not used.

**data.gov.in / Agmarknet:** the [official resource page](https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi) returned 503 during this build. No resource UUID was guessed. Before enabling live prices, check all of the following in that resource's API console and update `.env` / `config/mandi.yaml`:

- Exact active resource ID and base URL, API-key placement and permissions.
- Actual parameter names for JSON format, state/district/commodity filters, limit and offset.
- Exact commodity spelling; configured aliases currently include `Soyabean`.
- Response envelope and record field names, including optional variety and grade.
- Price units and numeric formatting; the UI expects INR per quintal.
- Arrival-date formats, freshness, pagination limits and record ordering.
- Whether your selected resource covers the configured local and nearby districts.

The YAML supplies editable adapter mappings, not a claim that the unavailable resource was verified. Districts are queried concurrently, with at most two pages of 200 records per district. Coverage can be incomplete. Price gaps require matching commodity, variety, grade, trading date and unit; missing grades cannot establish comparability. Prices alone never predict future returns or storage/transport costs.

**Open-Meteo:** the public live request passed during verification. Parameters are documented in the [forecast API guide](https://open-meteo.com/en/docs). `rain_*` fields carry total precipitation, including showers and snow equivalent, rather than rain-only measurements. Rolling windows begin at the next complete UTC hour, so a partial current hour is excluded. Probability is the highest available hourly probability, not an aggregate chance over the whole window. Forecasts remain uncertain.

## Tests and evaluation

Windows commands from the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m scripts.run_eval
.\.venv\Scripts\python.exe -m scripts.try_tools
.\.venv\Scripts\python.exe -m scripts.try_tools --live
.\.venv\Scripts\python.exe -m pytest tests/test_tools.py -m live
.\.venv\Scripts\python.exe -m scripts.try_llm --provider mock
.\.venv\Scripts\python.exe -m scripts.try_llm --provider groq
.\.venv\Scripts\python.exe -m scripts.try_llm --provider gemini
```

Use `.venv/bin/python` on Linux/macOS, or `..\..\work\.venv\Scripts\python.exe` in the already-prepared workspace. Live tests are skipped by the default pytest configuration. Only run provider probes after supplying the respective key; they make real API calls. Logs show normalized tool output and never the farmer profile or keys.

The evaluation contains **38 synthetic scenarios**, including rain, dry weather, heat, stale and absent market data, clarification, unsupported crops, dose requests, injection and outages. `eval_report.md` contains per-case assertions and failures. Passing it demonstrates implemented behavior; it is not a measure of agricultural accuracy, live model performance or farmer-tested language quality. `docs/verification.md` records the actual final checks and limitations.

### Network-off behavior

Demo mode never calls external data sources or language models. In live mode, weather and mandi first reuse a recent last-good cache. On network failure, an older cache may be returned with its original timestamp and a warning; the quality gate rejects stale evidence for decisions. Without a weather cache, the tool returns an error and UNKNOWN confidence. Without a mandi cache, labeled low-confidence sample records are used when available; otherwise it returns an error. No simulated weather is silently substituted for a failed live forecast. A corrupt cache is ignored without deleting it.

## Module map

| Location | Responsibility |
| --- | --- |
| `app/schemas.py` | User-supplied Pydantic contract, preserved unchanged |
| `app/config.py`, `app/db.py`, `app/repository.py` | Settings, SQLite storage, profile operations |
| `app/tools/` | HTTP adapters, crop stage, cache, shared evidence-quality checks and injected Tools protocol |
| `app/risk/` | Pure configurable deterministic screening; no LLM |
| `app/llm/client.py` | Groq-to-Gemini fallback, validated JSON and explicit mock |
| `app/agent/` | Bounded intent routing, concurrent tool selection, explanations and guardrails |
| `app/routers/`, `app/main.py` | Health, profiles, advisory, proactive alerts, dashboard and FPO API |
| `ui/streamlit_app.py` | Chat, charts, provenance, scenario controls and group overview |
| `config/` | Crop calendars/aliases, market mapping and UI examples |
| `data/` | Fictional profiles, synthetic weather and sample prices |
| `tests/`, `scripts/` | Offline fakes, regression/evaluation cases, seed and diagnostic tools |

## Demo rules to replace

All 20 entries in `app/risk/rules.yaml` have `status: demo` and `rule_source: DEMO RULE - needs KVK/ICAR verification`. These illustrative thresholds must be reviewed locally before field use. Highest matched severity wins; absent or unsuitable required evidence yields UNKNOWN.

| Rule IDs | Illustrative checks |
| --- | --- |
| `spray_rain_high`, `spray_heat_high` | 48-hour precipitation ≥20 mm, or temperature ≥40°C |
| `spray_rain_medium`, `spray_low` | Precipitation ≥5 mm; lower category when <5 mm and <40°C |
| `irrigation_rain_high`, `irrigation_rain_medium` | Precipitation ≥20 mm / ≥5 mm |
| `irrigation_heat_medium`, `irrigation_low` | Temperature ≥38°C; lower category with <5 mm and <38°C |
| `harvest_immature_high`, `harvest_rain_high` | Calendar stage is not maturity, or precipitation ≥20 mm |
| `harvest_rain_medium`, `harvest_low` | Precipitation ≥5 mm; lower category requires maturity and <5 mm |
| `sowing_rain_high`, `sowing_heat_high` | Precipitation ≥40 mm or temperature ≥40°C |
| `sowing_rain_medium`, `sowing_heat_medium`, `sowing_low` | ≥20 mm or ≥35°C; lower category below both |
| `sell_gap_high`, `sell_gap_medium`, `sell_gap_low` | Comparable best-versus-local quote gap ≥10%, ≥5%, or <5% |

The crop calendars for soybean, wheat and gram are also demonstration estimates. Their stages are not observations of maturity. Replacing thresholds alone does not validate the system: review crop/region scope, soil context, time windows, reasons and expected tests together.

## Assumptions and deliberate limits

1. The attached detailed brief takes precedence over the broad voice concept: the delivered MVP is text-first. Speech input/output and messaging bots are omitted.
2. Local, single-worker use is the target. There are no accounts, roles, notification campaigns, migrations or hosting pipeline. Do not expose the unauthenticated service publicly.
3. The three profiles are fictional and their coordinates describe demo locations. No actual farmer records were imported.
4. Soybean is the primary demo; wheat/gram calendars are configuration-only additions. All locations, prices, calendars and numeric thresholds live in data/configuration, not application code.
5. Seed dates are fixed in 2026. Stage calculation uses the current date. For a later demonstration, update seed sowing dates and recreate or update those profiles deliberately; existing IDs are not overwritten by seeding.
6. A saved crop requires a sowing date under the unchanged contract. An empty crop list represents missing crop context. Repeated plots of the same crop cannot be resolved by plot ID in the current question contract.
7. Location always comes from the saved profile. Weather questions can be answered without a crop. Multiple crops require one crop to be named.
8. Question language determines reply language: Hindi/Hinglish produce Devanagari Hindi; English produces English. Preferred profile language is used for proactive alerts.
9. Intent routing is intentionally bounded by keywords and configured crop aliases. LLM output is validated but cannot broaden deterministic routing. Unsupported wording may need rephrasing.
10. The LLM can select approved whole sentences in order; it cannot freely paraphrase agronomic decisions. This conservative MVP favors reliable sourced templates over unrestricted generation.
11. HIGH means `dont`, MEDIUM means `wait`, and LOW still means `wait` pending field checks. UNKNOWN gives no firm action advice. All five types are limited screens, not full recommendations.
12. No soil type, laboratory results, measured moisture, wind suitability, disease diagnosis or pesticide-label data exists in the supplied profile contract. Soil-dependent work explicitly requires field/local verification.
13. Synthetic forecast values can exercise rules only in demo mode and carry a DEMO source and simulated flag. Sample mandi records never qualify for sale decisions.
14. Nearby markets mean configured districts, not measured road distance or geospatial nearest markets. Live responses are bounded; transport, grading and storage economics remain unknown.
15. Cache timestamps are never refreshed by reading cached data. Freshness thresholds are application policy, not agronomic facts. Market arrival dates use the Indian trading day.
16. Provider access has not been proven without keys. Official endpoint/model examples are configurable and must be checked against the user's account.
17. No optional feature was allowed to replace the core end-to-end flow. The project was kept local; no public repository or deployment was created.

## Most likely places to break

- **Provider configuration:** model deprecation, key permissions, quotas and incompatible JSON options. Inspect the safe provider log and run each provider probe separately.
- **Mandi integration:** unset resource ID/key, unavailable upstream, changed fields, absent grade, pagination or old arrival dates. The fallback stays labeled and the risk remains UNKNOWN.
- **Forecast availability:** no internet, upstream quota/error, missing hourly observations or more than six-hour-old cache. The app returns controlled data gaps.
- **Local startup:** wrong Python version, wrong working directory, occupied ports, missing dependencies or API started after the UI. Use the commands above and check `/health`.
- **Demo dates and crop aliases:** fixed seed dates eventually exceed the demo calendar; unfamiliar crop wording may require configured aliases.
- **Agronomic validity:** every numeric rule/calendar is unverified. Local experts must review them; this is the most important field-deployment limitation.
- **Scale:** synchronous SQLite writes and process-local rate limits are appropriate for this local hackathon demo, not a multi-worker production service.

The local Git history contains the foundation-to-documentation checkpoints. See `docs/architecture.md` for the team split and data flow.
