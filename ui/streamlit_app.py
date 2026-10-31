"""Mobile-friendly client. All profiles, evidence and advice come from the API."""
from datetime import datetime
from html import escape
from pathlib import Path
import sys

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings
from app.schemas import AdvisoryResponse, FarmerProfile, ToolResult

st.set_page_config(page_title="KisanSaathi · किसान साथी", page_icon="🌱", layout="wide")
st.markdown("""<style>
.block-container{max-width:1200px;padding-top:2.3rem;padding-bottom:3rem}
h1,h2,h3{letter-spacing:-.035em}h1{font-size:2.7rem!important;color:#173e2d}
[data-testid="stMetric"]{background:#fff;border:1px solid #dfe7da;border-radius:14px;padding:18px}
[data-testid="stSidebar"]{border-right:1px solid #dfe7da}
.eyebrow{font-size:.75rem;letter-spacing:.18em;text-transform:uppercase;color:#587366;font-weight:700}
.hero{background:#e6eedb;border:1px solid #d6e2c7;border-radius:22px;padding:25px 30px;margin:8px 0 22px}
.hero p{color:#4a6253;margin:0}.hero h1{margin:5px 0 8px}
.pill{display:inline-block;padding:5px 12px;border-radius:30px;font-size:.8rem;font-weight:700;margin-right:8px}
.HIGH{background:#ffe4dc;color:#923e27}.MEDIUM{background:#fff0cd;color:#80600e}
.LOW{background:#e4f0dc;color:#316437}.UNKNOWN{background:#e9ecea;color:#58605a}
.demo{background:#f4eddb;color:#7e672e}
div[data-testid="stChatMessage"]{border:1px solid #e0e7dc;border-radius:16px}
@media(max-width:640px){.block-container{padding:1rem}h1{font-size:2rem!important}.hero{padding:20px}}
</style>""", unsafe_allow_html=True)

API_URL = get_settings().api_base_url.rstrip("/")


def api(method: str, path: str, payload=None, params=None):
    try:
        response = httpx.request(method, API_URL + path, json=payload, params=params, timeout=240)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 429:
            st.warning("Please wait a moment before asking again.")
        else:
            st.error(f"The service could not complete this request ({error.response.status_code}).")
    except (httpx.HTTPError, ValueError):
        st.error("The advisory service is unavailable. Start the API, then refresh this page.")
    return None


def stamp(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%d %b %Y, %H:%M %Z")
    except (ValueError, AttributeError):
        return "Time unavailable"


def badge(level: str, demo: bool = False):
    css = level if level in {"LOW", "MEDIUM", "HIGH", "UNKNOWN"} else "UNKNOWN"
    markup = f'<span class="pill {css}">{escape(level)} risk</span>'
    if demo:
        markup += '<span class="pill demo">DEMO RULE · needs verification</span>'
    st.markdown(markup, unsafe_allow_html=True)


def tool_caption(raw):
    tool = ToolResult.model_validate(raw)
    labels = []
    if tool.value.get("sample"):
        labels.append("SAMPLE DATA")
    if tool.value.get("simulated"):
        labels.append("SIMULATED")
    if tool.value.get("estimated"):
        labels.append("ESTIMATED")
    if tool.is_cached:
        labels.append("CACHED")
    if tool.value.get("stale"):
        labels.append("STALE")
    st.caption(f"{tool.source} · Data as of {stamp(raw['fetched_at'])} · {tool.confidence} confidence"
               + (" · " + " / ".join(labels) if labels else ""))
    if tool.error:
        st.warning(tool.error)
    for warning in tool.value.get("warnings", []):
        st.caption(f"Data note: {warning}")


def answer_card(payload):
    response = AdvisoryResponse.model_validate({k: v for k, v in payload.items() if k != "debug"})
    debug = payload.get("debug", {})
    demo_rule = any(r.get("evidence", {}).get("demo_rule") for r in debug.get("risk_results", []))
    badge(response.risk_level, demo_rule)
    st.markdown(response.answer_text)
    if response.uncertainty_note:
        st.caption(response.uncertainty_note)
    if response.refer_to_expert:
        st.caption("Confirm with your KVK or local agriculture officer before acting.")
    with st.expander("Sources, freshness & evidence"):
        for tool in debug.get("tool_results", {}).values():
            tool_caption(tool)
        if response.data_gaps:
            st.warning("Data gaps: " + "; ".join(response.data_gaps))
        if not response.sources:
            st.caption("No external data was used for this reply.")
        st.json(debug, expanded=False)


meta = api("GET", "/meta")
farmers_raw = api("GET", "/farmers") if meta else None
if not meta or farmers_raw is None:
    st.stop()
if not farmers_raw:
    st.info("No farmer profiles are available. Run the demo seed step in the README, then refresh.")
    st.stop()
profiles = {p["farmer_id"]: FarmerProfile.model_validate(p) for p in farmers_raw}

with st.sidebar:
    st.markdown("### 🌱 KisanSaathi")
    st.caption(meta["product"]["hindi_name"] + " · FARM ADVISORY")
    st.divider()
    selected = st.selectbox("Your farmer profile", list(profiles),
                            format_func=lambda key: profiles[key].name)
    profile = profiles[selected]
    st.caption(f"{profile.village}, {profile.district}\n\n{profile.state}")
    scenario = None
    if meta["data_mode"] == "demo":
        st.divider()
        st.caption("DEMO CONTROLS")
        scenarios = meta["scenarios"]
        scenario = st.selectbox("Weather & data scenario", list(scenarios),
                                index=list(scenarios).index(meta["demo_scenario"]),
                                format_func=lambda key: scenarios[key])
        st.caption("These controls change simulated evidence for the hackathon demo.")
    st.divider()
    st.caption("Text-first · हिंदी / Hinglish / English")
    st.caption("Mock language model" if meta["mock_llm"] else "Configured language model providers")
    if st.button("Refresh farm data", use_container_width=True):
        st.session_state.pop("snapshot_key", None)
        st.rerun()

query = {"demo_scenario": scenario} if scenario else {}
body_base = {"farmer_id": selected, **query}
context_key = (selected, scenario)
if st.session_state.get("snapshot_key") != context_key:
    with st.spinner("Reading your farm context…"):
        snapshot = api("GET", f"/dashboard/{selected}", params=query)
    if snapshot:
        st.session_state["snapshot"] = snapshot
        st.session_state["snapshot_key"] = context_key
    else:
        st.stop()
snapshot = st.session_state["snapshot"]

st.markdown(f'<div class="hero"><div class="eyebrow">{escape(meta["product"]["region"])} · FIELD NOTES</div>'
            f'<h1>{escape(meta["product"]["tagline"])}</h1>'
            f'<p>{escape(meta["product"]["description"])}</p></div>', unsafe_allow_html=True)
if meta["data_mode"] == "demo":
    st.caption(meta["data_note"])
else:
    st.caption("LIVE DATA MODE · Cached and sample fallbacks remain labeled. Rules still need local agronomic verification.")

weather = snapshot["weather"]
weather_value = weather["value"] if not weather["error"] else {}
metrics = st.columns(3)
rain = weather_value.get("rain_next_48h_mm")
temp = weather_value.get("temperature_max_c")
metrics[0].metric("Rain · next 48 hours", f"{rain:g} mm" if rain is not None else "Unavailable")
metrics[1].metric("Forecast high", f"{temp:g} °C" if temp is not None else "Unavailable")
metrics[2].metric("Saved crop plots", len(profile.crops))
tool_caption(weather)

chat, data, alerts, fpo = st.tabs(["💬 Ask Saathi", "🌦 Farm data", "🔔 Alerts", "🌾 FPO overview"])

with chat:
    st.subheader("What would you like to know?")
    st.caption("Ask naturally. Hindi and Hinglish questions receive a simple Hindi reply.")
    history_key = f"chat:{selected}:{scenario}"
    history = st.session_state.setdefault(history_key, [])
    pending_key = f"clarify:{selected}:{scenario}"
    example_columns = st.columns(3)
    submitted = None
    for index, example in enumerate(meta["examples"]):
        if example_columns[index % 3].button(example["label"], key=f"example-{index}", use_container_width=True):
            submitted = example["question"]
    for item in history:
        with st.chat_message("user"):
            st.write(item["question"])
        with st.chat_message("assistant", avatar="🌱"):
            answer_card(item["answer"])
    typed = st.chat_input("अपना सवाल पूछें… / Ask about your crop", max_chars=500)
    submitted = typed or submitted
    if submitted:
        full_question = submitted
        if typed and st.session_state.get(pending_key):
            full_question = st.session_state[pending_key] + " Crop: " + submitted
        if len(full_question) > 500:
            st.warning("Please include the crop in a shorter question (up to 500 characters).")
        else:
            with st.spinner("Checking the evidence…"):
                reply = api("POST", "/advise", {**body_base, "question": full_question})
            if reply:
                history.append({"question": submitted, "answer": reply})
                if "crop" in reply.get("debug", {}).get("intent", {}).get("missing_fields", []):
                    st.session_state[pending_key] = full_question
                else:
                    st.session_state.pop(pending_key, None)
                st.rerun()

with data:
    st.subheader("The evidence behind your advice")
    daily = weather_value.get("daily", [])
    if daily:
        frame = pd.DataFrame(daily)
        chart = px.bar(frame, x="date", y="rain_mm", labels={"date": "Forecast day", "rain_mm": "Precipitation (mm)"},
                       color_discrete_sequence=["#337851"], title="Rain outlook")
        chart.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=290,
                            margin=dict(l=10, r=10, t=45, b=10), xaxis_type="category")
        st.plotly_chart(chart, use_container_width=True)
    for plot in snapshot["plots"]:
        st.divider()
        st.subheader(plot["crop"].title())
        stage = plot["tool_results"]["crop_stage"]
        st.write("Estimated crop stage: **" + str(stage["value"].get("stage", "Unknown")) + "**")
        tool_caption(stage)
        mandi = plot["tool_results"]["mandi"]
        prices = mandi["value"].get("prices", [])
        st.markdown("**Nearby market records**")
        tool_caption(mandi)
        if prices:
            st.dataframe(pd.DataFrame(prices), hide_index=True, use_container_width=True)
            chart = px.bar(pd.DataFrame(prices), x="market", y="modal_price", color_discrete_sequence=["#A48644"],
                           labels={"market": "Market", "modal_price": "Modal price (₹ / quintal)"})
            chart.update_layout(height=260, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.info("No comparable price records are available.")
        st.caption("Market grouping uses configured districts; transport costs and future prices are unknown.")
        for risk in plot["risk_results"]:
            with st.expander(f"{risk['risk_type'].title()} · {risk['level']}"):
                badge(risk["level"], risk["evidence"].get("demo_rule", False))
                st.write(" ".join(risk["reasons"]))
                st.caption(risk["rule_source"])
        if plot["data_gaps"]:
            st.warning("; ".join(plot["data_gaps"]))
    if not snapshot["plots"]:
        st.info("This profile has no saved crop or sowing date, so crop-level checks are unavailable.")

with alerts:
    st.subheader("A heads-up before the next field task")
    st.caption("Checks spraying, irrigation and harvesting. Only medium and high risks appear.")
    all_farmers = st.checkbox("Check all demo farmers")
    if st.button("Generate alerts", type="primary"):
        targets = list(profiles) if all_farmers else [selected]
        results = []
        with st.spinner("Checking field risks…"):
            for farmer_id in targets:
                result = api("POST", "/alerts/generate", {"farmer_id": farmer_id, **query})
                if result:
                    results.append(result)
        st.session_state["alerts_result"] = {"context": context_key, "results": results}
    stored = st.session_state.get("alerts_result", {})
    for result in stored.get("results", []) if stored.get("context") == context_key else []:
        st.markdown(f"**{profiles[result['farmer_id']].name}** · {stamp(result['generated_at'])}")
        if not result["alerts"]:
            st.info("No medium or high alerts were generated. Missing evidence can also prevent an alert; review Farm data.")
        for alert in result["alerts"]:
            with st.container(border=True):
                intent = alert.get("debug", {}).get("intent", {})
                st.caption(f"{intent.get('crop', '')} · {intent.get('intent', '').title()}")
                answer_card(alert)

with fpo:
    st.subheader("One view of the farmer group")
    st.caption("Fictional demo profiles · Calendar estimates · No measured soil-moisture data")
    if st.button("Refresh group overview", type="primary"):
        with st.spinner("Checking the group…"):
            group = api("GET", "/fpo", params=query)
        if group:
            st.session_state["fpo_result"] = {"context": context_key, "result": group}
    group = st.session_state.get("fpo_result", {})
    if group.get("context") == context_key:
        rows = []
        for row in group["result"]["rows"]:
            rows.append({"Farmer": row["farmer"], "Village": row["village"], "Crop": row["crop"],
                         "Stage (estimated)": row["stage"], **{key.title(): value for key, value in row["risks"].items()},
                         "Reliable sources": f"{row['reliable_sources']}/{row['expected_sources']}",
                         "Data gaps": "; ".join(row["data_gaps"]), "Demo rule": row["demo_rule"]})
        st.caption("Checked " + stamp(group["result"]["as_of"]))
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.info("Refresh the overview to check each crop and its current evidence.")

st.divider()
st.caption("KisanSaathi · A hackathon prototype for climate and resource resilience · Local guidance comes first.")
