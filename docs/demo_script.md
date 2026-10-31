# Five-minute KisanSaathi demonstration

Before presenting: run the seed, API and Streamlit commands from README. Open the UI, keep `DATA_MODE=demo` and `USE_MOCK_LLM=true`, and start with Ramesh (DEMO). No external network or credentials are needed. Read the visible DEMO notice aloud once.

| Time | Action | What to show and say |
| --- | --- | --- |
| 0:00–0:35 | Introduce the problem and fictional profile | “A farmer asks one question in their own language. We bring weather, market records and crop context together, with clear uncertainty.” |
| 0:35–1:15 | Rain ahead → Can I spray? | Read the Hindi answer: do not spray in this simulated rainy scenario. Point to HIGH, DEMO RULE and the source age. Open Sources to show code-owned evidence. |
| 1:15–1:40 | Dry forecast → Can I spray? | Risk falls to LOW. Explain that this is a limited weather screen and still asks for field checks. The LLM cannot alter the computed level. |
| 1:40–2:15 | Sell or wait? → Farm data | Show market comparison, fixed arrival dates and SAMPLE/CACHED badges. Sale advice remains UNKNOWN because synthetic prices are unsuitable evidence. |
| 2:15–2:45 | Weather unavailable → Can I spray? | Show UNKNOWN and explicit data gaps. Explain that live outages use original-timestamp cache, or no forecast when none exists; fake live weather is never invented. |
| 2:45–3:15 | Type “What pesticide dose should I use?” | Show refusal and KVK referral, with no chemical name, dose or external tool calls. |
| 3:15–3:40 | Select Meera → “Should I spray?” → “soybean” | Show one crop clarification, then a grounded reply. Location was already saved and is never taken from the question. |
| 3:40–4:15 | Rain ahead → Alerts → Check all demo farmers → Generate alerts | Show proactive MEDIUM/HIGH checks without a farmer question. This generates local cards; it sends no messages. |
| 4:15–4:40 | FPO overview → Refresh group overview | Show crop stage estimates, risks and missing information. Dev has no saved crop/sowing date; sample prices lower completeness. |
| 4:40–5:00 | Show evaluation report | “Thirty-eight synthetic regression scenarios pass. Live weather was checked. Market credentials and model credentials are separate integration checks, and agronomic rules still need expert verification.” |

Backup: leave the app in demo mode if the venue network fails. The bundled data is explicitly synthetic. If a live provider fails during a separate technical demonstration, show the source warning and safe fallback rather than describing the call as successful.

Prepare later-date demonstrations by updating fictional sowing dates through the API or editing the seed before creating a fresh database. The seed does not overwrite existing rows. Do not present a simulated rule threshold as an ICAR/KVK recommendation.
