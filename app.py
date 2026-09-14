"""RecallRadar Streamlit experience."""

from __future__ import annotations

import os
import tempfile
import json
from dataclasses import asdict
from datetime import datetime, timezone
from html import escape

import pandas as pd
import streamlit as st

from recallradar.agent import deterministic_scan, run_strands_scan
from recallradar.core import build_action_packet
from recallradar.sources import load_inventory


# Streamlit Community Cloud stores root-level secrets in st.secrets. Mirror only
# the expected configuration keys into the process environment used by Strands.
try:
    for secret_name in ("GEMINI_API_KEY", "RECALLRADAR_PROVIDER", "RECALLRADAR_GEMINI_MODEL"):
        if secret_name in st.secrets and not os.getenv(secret_name):
            os.environ[secret_name] = str(st.secrets[secret_name])
except Exception:
    pass


st.set_page_config(page_title="RecallRadar", page_icon="◉", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&family=Space+Grotesk:wght@600;700&display=swap');
    :root {--mint:#63e6be;--ink:#07111f;--panel:#0d1c2d;--line:#223b52;--muted:#9db0c5;--danger:#ff6b6b}
    .stApp {
      background:
        radial-gradient(circle at 12% 12%,rgba(32,122,112,.16),transparent 28%),
        radial-gradient(circle at 88% 6%,rgba(42,86,145,.16),transparent 25%),
        linear-gradient(#07111f,#081421);
      color:#ecf4ff;font-family:'DM Sans',sans-serif
    }
    [data-testid="stSidebar"] {background:#0a1625;border-right:1px solid #1b3247}
    [data-testid="stHeader"] {background:transparent}
    h1,h2,h3 {font-family:'Space Grotesk',sans-serif}
    .hero {padding:1.8rem 0 .8rem;position:relative}
    .eyebrow {color:var(--mint);font-weight:700;letter-spacing:.13em;text-transform:uppercase;font-size:.78rem}
    .hero h1 {font-size:clamp(3rem,7vw,5.5rem);line-height:.95;margin:.3rem 0;
      background:linear-gradient(90deg,#fff 25%,#63e6be 70%,#91b7ff);
      -webkit-background-clip:text;color:transparent}
    .hero p {color:#b4c4d6;font-size:1.12rem;max-width:790px}
    .status-pill {display:inline-flex;gap:.45rem;align-items:center;background:#10283a;
      border:1px solid #24506a;border-radius:999px;padding:.42rem .9rem;color:#9af5d5}
    .status-dot {width:8px;height:8px;border-radius:50%;background:var(--mint);
      box-shadow:0 0 0 0 rgba(99,230,190,.7);animation:pulse 2s infinite}

    .radar-wrap {display:grid;grid-template-columns:minmax(250px,390px) 1fr;gap:1.2rem;
      background:linear-gradient(135deg,rgba(14,35,52,.95),rgba(9,24,39,.92));
      border:1px solid #203d55;border-radius:24px;padding:1.3rem;margin:.8rem 0 1.5rem;
      box-shadow:0 24px 70px rgba(0,0,0,.23);overflow:hidden}
    .radar {position:relative;width:220px;height:220px;border-radius:50%;margin:auto;
      background:repeating-radial-gradient(circle,transparent 0 31px,rgba(99,230,190,.2) 32px 33px),
      linear-gradient(90deg,transparent 49.5%,rgba(99,230,190,.18) 50%,transparent 50.5%),
      linear-gradient(transparent 49.5%,rgba(99,230,190,.18) 50%,transparent 50.5%),#0a1d2a;
      border:1px solid rgba(99,230,190,.4);box-shadow:inset 0 0 35px rgba(99,230,190,.08),0 0 35px rgba(23,120,104,.12)}
    .sweep {position:absolute;inset:0;border-radius:50%;
      background:conic-gradient(from 0deg,transparent 0 78%,rgba(99,230,190,.03) 82%,rgba(99,230,190,.55) 100%);
      animation:spin 3s linear infinite}
    .blip {position:absolute;width:9px;height:9px;border-radius:50%;background:#ff7575;
      box-shadow:0 0 0 4px rgba(255,107,107,.12),0 0 18px #ff6b6b;animation:blip 2.1s infinite}
    .b1 {left:64%;top:31%}.b2 {left:31%;top:65%;animation-delay:.7s}.b3 {left:57%;top:72%;animation-delay:1.3s}
    .radar-copy {display:flex;flex-direction:column;justify-content:center;padding:.4rem 1rem}
    .radar-copy h2 {font-size:1.75rem;margin:.25rem 0 .5rem}
    .radar-copy p {color:var(--muted);max-width:590px;margin:.15rem 0 1rem}
    .signal-row {display:grid;grid-template-columns:repeat(3,1fr);gap:.65rem}
    .signal {background:rgba(255,255,255,.035);border:1px solid #20384e;border-radius:12px;padding:.75rem}
    .signal strong {display:block;color:white;font-size:1.05rem}.signal span{color:#87a0b7;font-size:.78rem}

    .agent-flow {display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin:1.1rem 0 1.5rem}
    .flow-step {position:relative;background:#0d1c2d;border:1px solid #203a51;border-radius:14px;
      padding:.8rem;opacity:0;transform:translateY(12px);animation:stepIn .45s forwards}
    .flow-step:nth-child(2){animation-delay:.22s}.flow-step:nth-child(3){animation-delay:.44s}
    .flow-step:nth-child(4){animation-delay:.66s}
    .flow-num {display:inline-grid;place-items:center;width:24px;height:24px;border-radius:50%;
      background:rgba(99,230,190,.12);color:var(--mint);font-weight:700;margin-right:.4rem}
    .flow-step small {display:block;color:#7f96aa;margin:.4rem 0 0 2rem}

    .recall-card {display:grid;grid-template-columns:118px 1fr;gap:1.15rem;
      background:linear-gradient(120deg,#101f31,#0b1827);border:1px solid #294158;
      border-left:5px solid var(--danger);border-radius:18px;padding:1.2rem;margin:.9rem 0;
      box-shadow:0 14px 40px rgba(0,0,0,.2);animation:cardIn .65s both}
    .score-ring {--score:90;display:grid;place-items:center;width:96px;height:96px;border-radius:50%;
      background:conic-gradient(var(--danger) calc(var(--score)*1%),#23384b 0);position:relative;margin:auto}
    .score-ring:before {content:"";position:absolute;inset:8px;border-radius:50%;background:#0d1c2d}
    .score-ring strong,.score-ring span {position:relative;z-index:1}
    .score-ring strong {font:700 1.35rem 'Space Grotesk';line-height:1}.score-ring span{font-size:.62rem;color:#a8bacb}
    .card-body h3 {font-size:1.45rem;margin:.2rem 0}.muted{color:var(--muted)}
    .chips {display:flex;flex-wrap:wrap;gap:.45rem;margin:.7rem 0}
    .chip {border:1px solid #355069;border-radius:999px;padding:.24rem .58rem;color:#c3d2df;font-size:.75rem}
    .action-line {display:grid;grid-template-columns:1fr 1fr;gap:.65rem;margin-top:.7rem}
    .action-box {background:rgba(255,255,255,.035);border-radius:10px;padding:.7rem;color:#dce8f2}
    .action-box b {color:var(--mint);display:block;font-size:.7rem;text-transform:uppercase;letter-spacing:.08em}
    .setup-card {background:rgba(13,28,45,.82);border:1px solid #203a51;border-radius:16px;
      padding:1rem 1.1rem;margin:.55rem 0 1rem;min-height:116px}
    .setup-card .step {color:var(--mint);font-weight:700;font-size:.72rem;letter-spacing:.11em;text-transform:uppercase}
    .setup-card h3 {font-size:1.05rem;margin:.35rem 0}.setup-card p{color:var(--muted);font-size:.85rem;margin:0}
    .source-banner {border-radius:12px;padding:.7rem .9rem;margin:.4rem 0 1rem;background:#10283a;border:1px solid #24506a;color:#bfe9dc}
    .source-banner.demo {background:#292318;border-color:#6c5730;color:#ffe0a3}
    .hazard {background:rgba(255,107,107,.08);border:1px solid rgba(255,107,107,.2);border-radius:10px;padding:.7rem;margin:.65rem 0;color:#ffd1d1}
    .decision-state {font-weight:700;color:#9af5d5}

    div.stButton > button {border-radius:12px;border:1px solid #39715f;transition:.25s ease}
    div.stButton > button:hover {transform:translateY(-2px);box-shadow:0 8px 25px rgba(99,230,190,.18)}
    @keyframes spin {to{transform:rotate(360deg)}}
    @keyframes pulse {70%{box-shadow:0 0 0 8px rgba(99,230,190,0)}100%{box-shadow:0 0 0 0 rgba(99,230,190,0)}}
    @keyframes blip {0%,100%{opacity:.25;transform:scale(.7)}50%{opacity:1;transform:scale(1.2)}}
    @keyframes stepIn {to{opacity:1;transform:none}}
    @keyframes cardIn {from{opacity:0;transform:translateX(25px)}to{opacity:1;transform:none}}
    @media(max-width:800px){.radar-wrap{grid-template-columns:1fr}.agent-flow{grid-template-columns:1fr 1fr}
      .recall-card{grid-template-columns:1fr}.signal-row{grid-template-columns:1fr}}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">Always watching · rarely interrupting</div>
      <h1>RecallRadar</h1>
      <p>Your purchases become a living safety inventory. The agent monitors recall signals,
      verifies exact identifiers, and surfaces only decisions that genuinely need you.</p>
      <span class="status-pill"><span class="status-dot"></span> Human approval protects every external action</span>
    </div>
    <div class="radar-wrap">
      <div class="radar">
        <div class="sweep"></div><span class="blip b1"></span><span class="blip b2"></span><span class="blip b3"></span>
      </div>
      <div class="radar-copy">
        <div class="eyebrow">Live safety signal</div>
        <h2>Quiet protection in the background</h2>
        <p>Receipt records become searchable evidence. Weak signals disappear; exact model and lot matches become clear actions.</p>
        <div class="signal-row">
          <div class="signal"><strong>Exact-first</strong><span>model + lot evidence</span></div>
          <div class="signal"><strong>Silent</strong><span>until risk changes</span></div>
          <div class="signal"><strong>Human-safe</strong><span>approval before action</span></div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Safety monitor")
    source_label = st.radio("Recall source", ["Demo recall feed", "Live CPSC feed"])
    source = "demo" if source_label.startswith("Demo") else "live"
    provider_label = st.selectbox(
        "Agent intelligence",
        ["Visual demo · no key", "Strands + Gemini free tier", "Strands + Amazon Bedrock"],
        index=1 if os.getenv("RECALLRADAR_PROVIDER", "").lower() == "gemini" else 0,
    )
    use_strands = not provider_label.startswith("Visual")
    provider = "gemini" if "Gemini" in provider_label else "bedrock"
    st.caption("No personal data is saved or submitted.")
    st.divider()
    st.markdown("**Agent guardrails**")
    st.write("✓ Exact identifiers first")
    st.write("✓ Weak candidates suppressed")
    st.write("✓ Official verification required")
    st.write("✓ No action without approval")

st.subheader("Run a household safety check")
step1, step2, step3 = st.columns(3)
step1.markdown('<div class="setup-card"><span class="step">Step 1</span><h3>Add your inventory</h3><p>Upload a receipt export or simple CSV. Only the product name is mandatory.</p></div>', unsafe_allow_html=True)
step2.markdown('<div class="setup-card"><span class="step">Step 2</span><h3>Choose intelligence</h3><p>Use official live notices, then let Strands prepare only evidence-backed decisions.</p></div>', unsafe_allow_html=True)
step3.markdown('<div class="setup-card"><span class="step">Step 3</span><h3>Review safely</h3><p>Open the official notice, approve or dismiss, and download an audit-ready report.</p></div>', unsafe_allow_html=True)

upload_col, template_col = st.columns([3, 1])
with upload_col:
    uploaded = st.file_uploader("Household inventory CSV", type=["csv"], help="Accepted fields include name/product_name, brand, model, lot, UPC, purchase date, and retailer.")
with template_col:
    st.caption("Need the correct format?")
    st.download_button(
        "Download CSV template",
        data=open("data/demo_inventory.csv", "rb").read(),
        file_name="recallradar_inventory_template.csv",
        mime="text/csv",
        width="stretch",
    )

inventory_path = "data/demo_inventory.csv"
preview_error = None
try:
    if uploaded:
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp.write(uploaded.getvalue())
        temp.close()
        inventory_path = temp.name
    products_preview = load_inventory(inventory_path)
    preview = pd.DataFrame([asdict(product) for product in products_preview])
except Exception as exc:
    products_preview, preview = [], pd.DataFrame()
    preview_error = str(exc)

if source == "live":
    st.markdown('<div class="source-banner"><b>LIVE MODE</b> · Searches the official U.S. CPSC Recall API using each product model or name. Results depend on agency coverage.</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="source-banner demo"><b>DEMONSTRATION MODE</b> · Uses synthetic notices to provide a reliable judging walkthrough. No result is a real recall.</div>', unsafe_allow_html=True)

if preview_error:
    st.error(preview_error)
else:
    identifier_ready = sum(bool(item.model or item.lot or item.upc) for item in products_preview)
    duplicates = int(preview["product_id"].duplicated().sum()) if not preview.empty else 0
    q1, q2, q3 = st.columns(3)
    q1.metric("Products loaded", len(products_preview))
    q2.metric("Identifier-ready", f"{identifier_ready}/{len(products_preview)}")
    q3.metric("Duplicate IDs", duplicates)
    if identifier_ready < len(products_preview):
        st.warning("Some products have no model, lot, or UPC. RecallRadar will search them, but it suppresses weak matches to avoid false alarms.")
    with st.expander("Review products before scanning", expanded=False):
        st.dataframe(preview, width="stretch", hide_index=True)

if st.button("Start animated safety scan", type="primary", width="stretch", disabled=bool(preview_error)):
    with st.status("Radar is investigating product signals…", expanded=True) as status:
        st.write("◌ Reading receipt-derived identifiers")
        st.write("◌ Retrieving recall intelligence")
        try:
            matches, products = deterministic_scan(inventory_path, source)
            st.write("◌ Rejecting ambiguous candidates")
            st.write("◉ Building decision packets")
            status.update(label="Scan complete — attention map updated", state="complete")
            st.session_state["matches"] = matches
            st.session_state["product_count"] = len(products)
            st.session_state["scan_source"] = source
            st.session_state["scan_time"] = datetime.now(timezone.utc).isoformat()
            st.session_state["decisions"] = {}
            st.session_state.pop("agent_brief", None)

            if use_strands:
                with st.spinner("Strands is generating the decision brief…"):
                    st.session_state["agent_brief"] = run_strands_scan(inventory_path, source, provider)
        except Exception as exc:
            status.update(label="Scan could not complete", state="error")
            st.error(f"{exc}")
            st.stop()

matches = st.session_state.get("matches")
if matches is not None:
    st.markdown(
        """
        <div class="agent-flow">
          <div class="flow-step"><span class="flow-num">1</span><b>Observe</b><small>inventory loaded</small></div>
          <div class="flow-step"><span class="flow-num">2</span><b>Investigate</b><small>notices retrieved</small></div>
          <div class="flow-step"><span class="flow-num">3</span><b>Verify</b><small>weak signals removed</small></div>
          <div class="flow-step"><span class="flow-num">4</span><b>Escalate</b><small>decisions prepared</small></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    product_count = st.session_state.get("product_count", 0)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Protected products", product_count)
    c2.metric("Decisions surfaced", len(matches))
    c3.metric("Source", "CPSC" if st.session_state.get("scan_source") == "live" else "Synthetic")
    c4.metric("Unauthorized actions", 0)

    if not matches:
        st.success("No evidence-backed candidate was found in this scan.")
        st.caption("This does not certify that a product is safe. Keep identifiers updated and scan again when new notices appear.")
    else:
        st.subheader("Attention map")
        for index, match in enumerate(matches):
            packet = build_action_packet(match)
            safe_product = escape(f"{match.product.brand} {match.product.name}")
            safe_recall_id = escape(match.recall.recall_id)
            safe_immediate = escape(packet["immediate_action"])
            safe_remedy = escape(packet["recommended_remedy"])
            safe_hazard = escape(packet.get("hazard") or "Hazard details were not supplied by the source.")
            chips = "".join(f'<span class="chip">{escape(reason)}</span>' for reason in match.reasons)
            st.markdown(
                f"""
                <div class="recall-card" style="animation-delay:{index * .16}s">
                  <div class="score-ring" style="--score:{match.confidence}">
                    <div><strong>{match.confidence}%</strong><br><span>EVIDENCE</span></div>
                  </div>
                  <div class="card-body">
                    <div class="eyebrow">{escape(match.risk)} signal · recall {safe_recall_id}</div>
                    <h3>{safe_product}</h3>
                    <div class="chips">{chips}</div>
                    <div class="hazard"><b>Why it matters:</b> {safe_hazard}</div>
                    <div class="action-line">
                      <div class="action-box"><b>Do now</b>{safe_immediate}</div>
                      <div class="action-box"><b>Prepared remedy</b>{safe_remedy}</div>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander(f"Decision packet · {match.match_id}"):
                current_state = st.session_state.setdefault("decisions", {}).get(match.match_id, "AWAITING REVIEW")
                st.markdown(f'Current status: <span class="decision-state">{escape(current_state)}</span>', unsafe_allow_html=True)
                if st.session_state.get("scan_source") == "live" and match.recall.official_url:
                    st.link_button("Open official CPSC notice ↗", match.recall.official_url, width="stretch")
                else:
                    st.caption("Synthetic notice used for demonstration; there is no official recall page.")
                st.json(packet)
                left, right = st.columns(2)
                if left.button("Approve prepared request", key=f"approve-{match.match_id}"):
                    st.session_state["decisions"][match.match_id] = "APPROVED FOR MANUAL ACTION"
                    st.toast("Approval recorded. No company was contacted automatically.", icon="✓")
                if right.button("Dismiss and verify manually", key=f"dismiss-{match.match_id}"):
                    st.session_state["decisions"][match.match_id] = "DISMISSED — MANUAL VERIFICATION"
                    st.toast("Decision saved for manual verification.", icon="↗")

        export_rows = []
        for match in matches:
            packet = build_action_packet(match)
            export_rows.append({
                "product_id": match.product_id,
                "product": f"{match.product.brand} {match.product.name}".strip(),
                "model": match.product.model,
                "lot": match.product.lot,
                "upc": match.product.upc,
                "recall_id": match.recall_id,
                "risk": match.risk,
                "confidence": match.confidence,
                "hazard": packet.get("hazard", ""),
                "recommended_remedy": packet["recommended_remedy"],
                "official_notice": packet["official_notice"],
                "decision": st.session_state.get("decisions", {}).get(match.match_id, "AWAITING REVIEW"),
            })
        export_frame = pd.DataFrame(export_rows)
        export_json = {
            "generated_at": st.session_state.get("scan_time"),
            "source": st.session_state.get("scan_source"),
            "products_checked": product_count,
            "decisions": export_rows,
            "disclaimer": "Potential matches only. Verify with the official agency notice before acting.",
        }
        st.subheader("Take the results with you")
        dl1, dl2 = st.columns(2)
        dl1.download_button("Download decision report (CSV)", export_frame.to_csv(index=False), "recallradar_decisions.csv", "text/csv", width="stretch")
        dl2.download_button("Download audit packet (JSON)", json.dumps(export_json, indent=2), "recallradar_audit.json", "application/json", width="stretch")

    if st.session_state.get("agent_brief"):
        st.subheader("Strands decision brief")
        st.write(st.session_state["agent_brief"])

st.divider()
st.caption(
    "RecallRadar is a decision-support agent. A candidate is not an official safety determination. "
    "Always verify model and lot information on the official agency notice."
)
