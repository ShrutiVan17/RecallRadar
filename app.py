"""RecallRadar Streamlit experience."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from recallradar.agent import deterministic_scan, run_strands_scan
from recallradar.core import build_action_packet


st.set_page_config(page_title="RecallRadar", page_icon="◉", layout="wide")

st.markdown(
    """
    <style>
    .stApp {background: #07111f; color: #ecf4ff;}
    [data-testid="stSidebar"] {background: #0b1728;}
    .hero {padding: 1.6rem 0 1rem;}
    .eyebrow {color:#63e6be;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
    .hero h1 {font-size:3.2rem;margin:.15rem 0;background:linear-gradient(90deg,#fff,#63e6be);
      -webkit-background-clip:text;color:transparent}
    .hero p {color:#aebed1;font-size:1.1rem;max-width:780px}
    .status {display:inline-block;background:#10283a;border:1px solid #24506a;
      border-radius:999px;padding:.3rem .8rem;color:#80f3ca}
    .recall-card {background:#0d1c2d;border:1px solid #223b52;border-left:5px solid #ff6b6b;
      border-radius:14px;padding:1.1rem;margin:.8rem 0}
    .muted {color:#9db0c5}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">Always watching. Rarely interrupting.</div>
      <h1>RecallRadar</h1>
      <p>A quiet Strands agent that turns forgotten receipts into a safety inventory,
      verifies product recalls, and surfaces only decisions that need you.</p>
      <span class="status">● Human approval required for every external action</span>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Scan settings")
    source_label = st.radio("Recall source", ["Demo recall feed", "Live CPSC feed"])
    source = "demo" if source_label.startswith("Demo") else "live"
    use_strands = st.toggle(
        "Strands + Amazon Bedrock",
        value=os.getenv("RECALLRADAR_USE_STRANDS", "0") == "1",
        help="Requires configured AWS credentials. Demo scanning works without keys.",
    )
    st.caption("RecallRadar does not store or submit personal information.")
    st.divider()
    st.markdown("**Agent policy**")
    st.write("✓ Exact identifiers first")
    st.write("✓ Weak candidates suppressed")
    st.write("✓ Official verification required")
    st.write("✓ No action without approval")

uploaded = st.file_uploader("Upload household inventory CSV", type=["csv"])
inventory_path = "data/demo_inventory.csv"
preview = pd.read_csv(inventory_path)

if uploaded:
    preview = pd.read_csv(uploaded)
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    preview.to_csv(temp.name, index=False)
    inventory_path = temp.name

with st.expander("Inventory being monitored", expanded=False):
    st.dataframe(preview, use_container_width=True, hide_index=True)

if st.button("Run safety scan", type="primary", use_container_width=True):
    with st.status("Agent is checking your household inventory…", expanded=True) as status:
        st.write("Validating product and receipt identifiers")
        st.write("Retrieving selected recall notices")
        try:
            matches, products = deterministic_scan(inventory_path, source)
            st.write("Rejecting weak or ambiguous candidates")
            st.write("Preparing approval-gated actions")
            status.update(label="Safety scan complete", state="complete")
            st.session_state["matches"] = matches
            st.session_state["product_count"] = len(products)

            if use_strands:
                with st.spinner("Strands is creating the decision brief…"):
                    st.session_state["agent_brief"] = run_strands_scan(inventory_path, source)
        except Exception as exc:
            status.update(label="Scan could not complete", state="error")
            st.error(f"{exc}")
            st.stop()

matches = st.session_state.get("matches")
if matches is not None:
    product_count = st.session_state.get("product_count", 0)
    c1, c2, c3 = st.columns(3)
    c1.metric("Products monitored", product_count)
    c2.metric("Confirmed candidates", len(matches))
    c3.metric("External actions taken", 0)

    if not matches:
        st.success("No evidence-backed recall candidates found.")
    else:
        st.subheader("Decisions requiring your attention")
        for match in matches:
            packet = build_action_packet(match)
            st.markdown(
                f"""
                <div class="recall-card">
                  <div class="eyebrow">{match.risk} risk · {match.confidence}% evidence score</div>
                  <h3>{match.product.brand} {match.product.name}</h3>
                  <div class="muted">Recall {match.recall.recall_id}</div>
                  <p><b>Why it matched:</b> {" · ".join(match.reasons)}</p>
                  <p><b>Do now:</b> {packet["immediate_action"]}</p>
                  <p><b>Proposed resolution:</b> {packet["recommended_remedy"]}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("Review prepared action packet"):
                st.json(packet)
                left, right = st.columns(2)
                if left.button("Approve prepared request", key=f"approve-{match.match_id}"):
                    st.success("Approval recorded. Demo mode does not contact an external party.")
                if right.button("Dismiss and verify manually", key=f"dismiss-{match.match_id}"):
                    st.info("Dismissed. Open the official notice and verify the identifier manually.")

    if st.session_state.get("agent_brief"):
        st.subheader("Strands decision brief")
        st.write(st.session_state["agent_brief"])

st.divider()
st.caption(
    "Prototype only. A candidate match is not an official safety determination. "
    "Always verify model and lot information on the official agency notice."
)
