# Verification record

Verified on **31 October 2026**, using Python **3.12.16** on Windows. The dependency versions are recorded in `requirements-lock.txt`.

| Check | Result |
| --- | --- |
| Complete offline pytest suite | **157 passed**, one live test deselected |
| Repeat suite in a fresh source copy with no database/cache/.env | **157 passed** |
| Scenario evaluation | **38/38 passed (100%)**; case table in `eval_report.md` |
| Live Open-Meteo pytest check | **1 passed** |
| `scripts.try_tools --live` | Open-Meteo returned a noncached success; mandi returned labeled sample data; crop stage returned an estimated demo-calendar result |
| Mock provider probe | Passed, with provider explicitly reported as `mock` |
| Seed in fresh source copy | First run inserted 3 profiles; repeat inserted 0 |
| Dependency consistency | `pip check`: no broken requirements |
| Supplied schema and contract | Matched attachment text after newline normalization; no field/type changes |
| API scenarios | Health, profile operations, rainy/dry/failed weather advice, refusal, clarification, dashboard, alerts, FPO, 4xx validation and 429 behavior passed |
| Browser flow | Hindi rainy HIGH advisory, dry LOW advisory, source/demo badges, rainfall/price charts, generated alerts, FPO table and custom pesticide-dose refusal observed |
| Mobile layout | Inspected at 390 × 844; buttons stack, Hindi text wraps, tabs scroll, and the chat remains usable |

The normalized schema SHA-256 is `679a256b16a74b30c342de980f03dbd4b6a7b33e0361230887baa7acdbcbf90a`. The contract markdown was also compared against the supplied examples. The clean source check reused the prepared Python environment; it verified independence from local source state/database/cache, not a second operating system or new package download.

One non-failing warning remains: the installed Starlette test client deprecates its HTTPX bridge in favor of HTTPX2. This affects two foundation tests' testing interface, not the runtime HTTPX data adapters. API tests use HTTPX's ASGI transport directly. HTTPX2 was not added because the requested stack uses HTTPX and the tests pass.

## Not verified or not validated

- Real Groq/Gemini responses: no provider keys were supplied. Fallback and JSON validation were tested with mocks; configured model access remains an account-specific check.
- Live data.gov.in records: its resource page returned 503, and no resource ID/key was supplied. The adapter uses configurable mappings and transparent fallbacks.
- Agronomic rule accuracy: all 20 rules and three calendars are demonstration configurations, not sourced field guidance.
- Forecast/market accuracy, field safety, farmer comprehension and production scale: synthetic regression tests do not establish these properties.
- Speech, authentication, hosted deployment and campaigns: intentionally outside the delivered text-first MVP.

The archive packaging step verifies every archived source byte against the delivered folder and excludes runtime files, secrets, dependencies and Git metadata. The accompanying complete-source Markdown contains every delivered text file in its own code block, followed by setup commands, assumptions and likely breakpoints.
