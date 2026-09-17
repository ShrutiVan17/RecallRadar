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
    .hero {padding:1.35rem 0 .55rem;position:relative}
    .eyebrow {color:var(--mint);font-weight:700;letter-spacing:.13em;text-transform:uppercase;font-size:.78rem}
    .hero h1 {font-size:clamp(3rem,7vw,5.2rem);line-height:.95;margin:.3rem 0;
      background:linear-gradient(90deg,#fff 25%,#63e6be 70%,#91b7ff);
      -webkit-background-clip:text;color:transparent}
    .hero p {color:#b4c4d6;font-size:1.12rem;max-width:790px}
    .status-pill {display:inline-flex;gap:.45rem;align-items:center;background:#10283a;
      border:1px solid #24506a;border-radius:999px;padding:.42rem .9rem;color:#9af5d5}
    .status-dot {width:8px;height:8px;border-radius:50%;background:var(--mint);
      box-shadow:0 0 0 0 rgba(99,230,190,.7);animation:pulse 2s infinite}

    .radar-wrap {display:grid;grid-template-columns:minmax(290px,410px) 1fr;gap:1.2rem;
      background:linear-gradient(135deg,rgba(14,35,52,.95),rgba(9,24,39,.92));
      border:1px solid #203d55;border-radius:24px;padding:1.3rem;margin:.8rem 0 1.5rem;
      box-shadow:0 24px 70px rgba(0,0,0,.23);overflow:hidden}
    .radar-stage {position:relative;min-height:280px;display:grid;place-items:center}
    .radar-halo {position:absolute;width:252px;height:252px;border:1px solid rgba(99,230,190,.15);border-radius:50%;animation:breathe 2.8s ease-in-out infinite}
    .radar {position:relative;width:230px;height:230px;border-radius:50%;margin:auto;
      background:repeating-radial-gradient(circle,transparent 0 32px,rgba(99,230,190,.2) 33px 34px),
      linear-gradient(90deg,transparent 49.5%,rgba(99,230,190,.18) 50%,transparent 50.5%),
      linear-gradient(transparent 49.5%,rgba(99,230,190,.18) 50%,transparent 50.5%),#0a1d2a;
      border:1px solid rgba(99,230,190,.4);box-shadow:inset 0 0 35px rgba(99,230,190,.08),0 0 35px rgba(23,120,104,.12)}
    .sweep {position:absolute;inset:0;border-radius:50%;
      background:conic-gradient(from 0deg,transparent 0 78%,rgba(99,230,190,.03) 82%,rgba(99,230,190,.55) 100%);
      animation:spin 3s linear infinite}
    .blip {position:absolute;width:9px;height:9px;border-radius:50%;background:#ff7575;
      box-shadow:0 0 0 4px rgba(255,107,107,.12),0 0 18px #ff6b6b;animation:blip 2.1s infinite}
    .b1 {left:64%;top:31%}.b2 {left:31%;top:65%;animation-delay:.7s}.b3 {left:57%;top:72%;animation-delay:1.3s}
    .radar-core {position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:46px;height:46px;
      display:grid;place-items:center;border-radius:50%;background:#0d2932;border:1px solid #63e6be;color:#9af5d5;
      font:700 .7rem 'Space Grotesk';letter-spacing:.1em;box-shadow:0 0 22px rgba(99,230,190,.35)}
    .radar-tag {position:absolute;background:#10283a;border:1px solid #31546a;border-radius:999px;padding:.28rem .55rem;
      font-size:.66rem;color:#bcd0dd;animation:float 3s ease-in-out infinite}
    .tag-a{top:13px;right:5px}.tag-b{bottom:16px;left:0;animation-delay:.8s}.tag-c{top:54%;right:-12px;animation-delay:1.5s}
    .radar-copy {display:flex;flex-direction:column;justify-content:center;padding:.4rem 1rem}
    .radar-copy h2 {font-size:1.75rem;margin:.25rem 0 .5rem}
    .radar-copy p {color:var(--muted);max-width:590px;margin:.15rem 0 1rem}
    .signal-row {display:grid;grid-template-columns:repeat(3,1fr);gap:.65rem}
    .signal {background:rgba(255,255,255,.035);border:1px solid #20384e;border-radius:12px;padding:.75rem}
    .signal strong {display:block;color:white;font-size:1.05rem}.signal span{color:#87a0b7;font-size:.78rem}

    .signal-ticker {overflow:hidden;border-top:1px solid #1e3b50;border-bottom:1px solid #1e3b50;padding:.58rem 0;margin:0 0 1.2rem;
      color:#7fa5b8;font-size:.72rem;font-weight:700;letter-spacing:.12em;white-space:nowrap}
    .ticker-track {display:inline-block;min-width:200%;animation:ticker 19s linear infinite}
    .ticker-track span{color:#63e6be;margin:0 .55rem}

    .agent-flow {position:relative;display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin:1.1rem 0 1.5rem}
    .agent-flow:before {content:"";position:absolute;left:8%;right:8%;top:25px;height:2px;background:#20384e;overflow:hidden}
    .agent-flow:after {content:"";position:absolute;left:8%;top:25px;height:2px;background:linear-gradient(90deg,#63e6be,#91b7ff);
      animation:flowLine 1.8s .3s ease-out both;box-shadow:0 0 12px rgba(99,230,190,.6)}
    .flow-step {position:relative;background:#0d1c2d;border:1px solid #203a51;border-radius:14px;
      padding:.8rem;opacity:0;transform:translateY(12px);animation:stepIn .45s forwards;z-index:1}
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
      background:conic-gradient(var(--ring,var(--danger)) calc(var(--score)*1%),#23384b 0);position:relative;margin:auto}
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
    .result-banner {display:flex;align-items:center;justify-content:space-between;gap:1rem;border:1px solid #294158;
      border-radius:16px;padding:1rem 1.15rem;margin:.8rem 0;background:linear-gradient(100deg,#102235,#0b1928);animation:resultIn .65s both}
    .result-banner strong{font:700 1.2rem 'Space Grotesk';display:block}.result-banner span{color:#9db0c5;font-size:.84rem}
    .result-orb {width:48px;height:48px;display:grid;place-items:center;border-radius:50%;background:rgba(99,230,190,.1);
      border:1px solid rgba(99,230,190,.4);color:#9af5d5;animation:pulse 2s infinite}

    div.stButton > button {border-radius:12px;border:1px solid #39715f;transition:.25s ease}
    div.stButton > button:hover {transform:translateY(-2px);box-shadow:0 8px 25px rgba(99,230,190,.18)}
    @keyframes spin {to{transform:rotate(360deg)}}
    @keyframes breathe {50%{transform:scale(1.08);opacity:.35}}
    @keyframes float {50%{transform:translateY(-5px)}}
    @keyframes ticker {to{transform:translateX(-50%)}}
    @keyframes flowLine {from{width:0}to{width:84%}}
    @keyframes resultIn {from{opacity:0;transform:scale(.98)}to{opacity:1;transform:none}}
    @keyframes pulse {70%{box-shadow:0 0 0 8px rgba(99,230,190,0)}100%{box-shadow:0 0 0 0 rgba(99,230,190,0)}}
    @keyframes blip {0%,100%{opacity:.25;transform:scale(.7)}50%{opacity:1;transform:scale(1.2)}}
    @keyframes stepIn {to{opacity:1;transform:none}}
    @keyframes cardIn {from{opacity:0;transform:translateX(25px)}to{opacity:1;transform:none}}
    /* Recruiter-ready, plain-language visual layer */
    .stApp:before,.stApp:after{content:"";position:fixed;border-radius:999px;filter:blur(70px);
      pointer-events:none;z-index:0;opacity:.22}
    .stApp:before{width:360px;height:360px;background:#2dd4bf;top:-120px;right:8%;animation:orbA 12s ease-in-out infinite}
    .stApp:after{width:310px;height:310px;background:#617cff;bottom:-120px;left:18%;animation:orbB 15s ease-in-out infinite}
    section.main>div{position:relative;z-index:1}
    [data-testid="stSidebar"]{background:linear-gradient(180deg,#0c1d31 0%,#071522 100%)!important;
      border-right:1px solid rgba(99,230,190,.22)!important}
    [data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,[data-testid="stSidebar"] label{color:#eaf4ff!important}
    [data-testid="stSidebar"] small{color:#9fb6c9!important}
    [data-testid="stSidebar"] [data-baseweb="select"] *{color:#102235!important}
    [data-testid="stSidebar"] .stAlert{background:rgba(43,127,255,.12)!important;border:1px solid rgba(93,164,255,.25)}
    [data-testid="stSidebar"] .stAlert p{color:#cfe4ff!important}

    .brand-chip{display:inline-flex;align-items:center;gap:.55rem;padding:.42rem .75rem;border-radius:999px;
      border:1px solid rgba(99,230,190,.35);background:rgba(99,230,190,.08);color:#9af5d5;
      font:700 .78rem 'Space Grotesk';letter-spacing:.08em;text-transform:uppercase;animation:heroIn .65s both}
    .brand-orb{width:9px;height:9px;border-radius:50%;background:#63e6be;box-shadow:0 0 16px #63e6be;animation:pulse 2s infinite}
    .hero h1{max-width:900px;font-size:clamp(2.8rem,6.3vw,5.6rem);letter-spacing:-.055em;
      animation:heroIn .75s .08s both}
    .hero .hero-lead{font-size:clamp(1.05rem,2vw,1.28rem);line-height:1.7;max-width:760px;
      color:#c0d1e1;animation:heroIn .75s .16s both}
    .trust-row{display:flex;flex-wrap:wrap;gap:.65rem;margin:1.15rem 0 .2rem;animation:heroIn .75s .24s both}
    .trust-pill{display:flex;align-items:center;gap:.45rem;padding:.5rem .76rem;border-radius:12px;
      background:rgba(255,255,255,.045);border:1px solid rgba(145,183,255,.18);color:#dce9f5;font-size:.82rem}
    .trust-pill i{width:8px;height:8px;border-radius:50%;display:inline-block}
    .trust-pill:nth-child(1) i{background:#63e6be}.trust-pill:nth-child(2) i{background:#91b7ff}.trust-pill:nth-child(3) i{background:#ffbe6b}

    .plain-intro{text-align:center;margin:2rem auto 1rem;max-width:760px}
    .plain-intro .eyebrow{margin-bottom:.35rem}.plain-intro h2{font-size:clamp(1.8rem,3vw,2.55rem);margin:.2rem 0}
    .plain-intro p{color:#9fb3c7;font-size:1rem}
    .simple-steps{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin:1rem 0 2rem}
    .simple-card{position:relative;overflow:hidden;background:linear-gradient(145deg,rgba(18,43,64,.95),rgba(10,27,43,.92));
      border:1px solid rgba(102,180,200,.22);border-radius:20px;padding:1.25rem;min-height:180px;
      box-shadow:0 18px 45px rgba(0,0,0,.18);animation:cardRise .65s both;transition:.28s ease}
    .simple-card:nth-child(2){animation-delay:.12s}.simple-card:nth-child(3){animation-delay:.24s}
    .simple-card:hover{transform:translateY(-7px);border-color:rgba(99,230,190,.55);box-shadow:0 24px 55px rgba(0,0,0,.25)}
    .simple-card:after{content:"";position:absolute;width:110px;height:110px;border-radius:50%;right:-42px;bottom:-55px;
      background:var(--card-glow,#63e6be);filter:blur(34px);opacity:.14}
    .simple-card:nth-child(2){--card-glow:#91b7ff}.simple-card:nth-child(3){--card-glow:#ff9f7f}
    .simple-icon{width:48px;height:48px;display:grid;place-items:center;border-radius:15px;margin-bottom:1rem;
      background:rgba(99,230,190,.1);border:1px solid rgba(99,230,190,.24);font-size:1.35rem;animation:iconFloat 3s ease-in-out infinite}
    .simple-card:nth-child(2) .simple-icon{animation-delay:.4s}.simple-card:nth-child(3) .simple-icon{animation-delay:.8s}
    .simple-card b{display:block;color:#fff;font:700 1.15rem 'Space Grotesk';margin-bottom:.4rem}
    .simple-card p{color:#a9bdcf;line-height:1.55;margin:0;font-size:.91rem}
    .step-badge{position:absolute;right:1rem;top:1rem;color:#648096;font:700 .72rem 'Space Grotesk';letter-spacing:.1em}
    .friendly-banner{display:flex;align-items:center;gap:.9rem;margin:.5rem 0 1.3rem;padding:1rem 1.1rem;
      border-radius:16px;background:linear-gradient(90deg,rgba(99,230,190,.11),rgba(145,183,255,.08));
      border:1px solid rgba(99,230,190,.25);animation:softGlow 4s ease-in-out infinite}
    .friendly-banner .face{font-size:1.6rem}.friendly-banner b{color:#fff}.friendly-banner span{color:#a9bdcf;font-size:.9rem}
    div.stButton>button[kind="primary"]{background:linear-gradient(90deg,#2dd4bf,#5f8dff)!important;color:#06131f!important;
      border:0!important;font-weight:800!important;min-height:3.2rem;box-shadow:0 12px 30px rgba(45,212,191,.2)}
    div.stButton>button[kind="primary"]:hover{box-shadow:0 16px 40px rgba(45,212,191,.34);transform:translateY(-3px)}
    @keyframes heroIn{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
    @keyframes cardRise{from{opacity:0;transform:translateY(24px) scale(.98)}to{opacity:1;transform:none}}
    @keyframes iconFloat{50%{transform:translateY(-6px) rotate(3deg)}}
    @keyframes softGlow{50%{border-color:rgba(145,183,255,.42);box-shadow:0 0 30px rgba(99,230,190,.08)}}
    @keyframes orbA{50%{transform:translate(-90px,80px) scale(1.15)}}
    @keyframes orbB{50%{transform:translate(110px,-70px) scale(.86)}}

    /* Keep Streamlit widgets readable against the dark visual system */
    [data-testid="stFileUploader"] label p,[data-testid="stWidgetLabel"] p,
    [data-testid="stMetricLabel"] *{color:#afc3d5!important}
    [data-testid="stMetricValue"] *{color:#f4fbff!important}
    [data-testid="stFileUploaderDropzone"]{background:#10283a!important;border:1px dashed #3f6f86!important}
    [data-testid="stFileUploaderDropzone"] p,[data-testid="stFileUploaderDropzone"] small,
    [data-testid="stFileUploaderDropzone"] span{color:#dceaf4!important}
    [data-testid="stFileUploaderDropzone"] button{background:#63e6be!important;border:0!important}
    [data-testid="stFileUploaderDropzone"] button *{color:#06131f!important}
    [data-testid="stDownloadButton"] button,.stDownloadButton button{background:#10283a!important;border:1px solid #3f6f86!important}
    [data-testid="stDownloadButton"] button *,.stDownloadButton button *{color:#f3f8fc!important}
    [data-testid="stStatusWidget"]{background:#0d1c2d!important;border:1px solid #294158!important}
    [data-testid="stStatusWidget"] *{color:#dceaf4!important}
    [data-testid="stExpander"] details{background:rgba(12,31,48,.72)!important;border-color:#294158!important}
    @media(max-width:800px){.radar-wrap{grid-template-columns:1fr}.agent-flow{grid-template-columns:1fr 1fr}
      .recall-card{grid-template-columns:1fr}.signal-row{grid-template-columns:1fr}
      .simple-steps{grid-template-columns:1fr}.hero h1{font-size:clamp(2.55rem,13vw,4rem)}
      .trust-row{display:grid;grid-template-columns:1fr}.friendly-banner{align-items:flex-start}}
    @media(prefers-reduced-motion:reduce){*,*:before,*:after{animation-duration:.01ms!important;animation-iteration-count:1!important}}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <div class="brand-chip"><span class="brand-orb"></span> RecallRadar · product safety made simple</div>
      <h1>Know when something you own is recalled.</h1>
      <p class="hero-lead">Add a simple list of products. RecallRadar checks recall notices,
      matches the important details, and tells you what to do next in plain language.</p>
      <div class="trust-row">
        <div class="trust-pill"><i></i>No account needed for the demo</div>
        <div class="trust-pill"><i></i>Checks exact model and lot details</div>
        <div class="trust-pill"><i></i>You approve every action</div>
      </div>
    </div>
    <div class="radar-wrap">
      <div class="radar-stage">
        <div class="radar-halo"></div>
        <div class="radar">
          <div class="sweep"></div><span class="blip b1"></span><span class="blip b2"></span><span class="blip b3"></span>
          <div class="radar-core">CHECK</div>
        </div>
        <span class="radar-tag tag-a">official notices</span>
        <span class="radar-tag tag-b">your product</span>
        <span class="radar-tag tag-c">your decision</span>
      </div>
      <div class="radar-copy">
        <div class="eyebrow">Simple on the surface · careful underneath</div>
        <h2>It checks the details people often miss</h2>
        <p>Product names can look alike. RecallRadar compares model, lot, barcode, brand, and product details before showing an alert.</p>
        <div class="signal-row">
          <div class="signal"><strong>Check</strong><span>official recall notices</span></div>
          <div class="signal"><strong>Compare</strong><span>exact product details</span></div>
          <div class="signal"><strong>Explain</strong><span>the safest next step</span></div>
        </div>
      </div>
    </div>
    <div class="signal-ticker"><div class="ticker-track">
      ADD YOUR PRODUCTS <span>●</span> CHECK OFFICIAL NOTICES <span>●</span> VERIFY THE DETAILS <span>●</span> CHOOSE WHAT HAPPENS NEXT <span>●</span>
      ADD YOUR PRODUCTS <span>●</span> CHECK OFFICIAL NOTICES <span>●</span> VERIFY THE DETAILS <span>●</span> CHOOSE WHAT HAPPENS NEXT <span>●</span>
    </div></div>
    <div class="plain-intro">
      <div class="eyebrow">How it works</div>
      <h2>Three steps. No technical knowledge needed.</h2>
      <p>Use the example products first. When you are ready, upload your own simple CSV list.</p>
    </div>
    <div class="simple-steps">
      <div class="simple-card"><span class="step-badge">STEP 01</span><div class="simple-icon">📦</div><b>Add your products</b><p>Start with the ready-made example or upload a list with product names and model numbers.</p></div>
      <div class="simple-card"><span class="step-badge">STEP 02</span><div class="simple-icon">🔎</div><b>RecallRadar checks</b><p>It searches recall notices and compares the exact details so similar names do not create panic.</p></div>
      <div class="simple-card"><span class="step-badge">STEP 03</span><div class="simple-icon">✓</div><b>You get a clear answer</b><p>See why a product was flagged, what to do now, and the official notice before deciding.</p></div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Start here")
    source_label = st.radio(
        "1 · What would you like to check?",
        ["Try the example products", "Check official recalls"],
        captions=["Best choice for a quick walkthrough", "Search the live U.S. CPSC database"],
    )
    source = "demo" if source_label.startswith("Try") else "live"
    provider_label = st.selectbox(
        "2 · Choose how it runs",
        ["Quick demo · recommended", "AI assistant · Gemini", "AI assistant · Amazon Bedrock"],
        index=0,
    )
    use_strands = provider_label.startswith("AI")
    provider = "gemini" if "Gemini" in provider_label else "bedrock"
    st.caption("New here? Keep the recommended choices and press the main button.")
    st.info("Your uploaded list stays in this browser session. Nothing is sent to a company automatically.")
    st.divider()
    st.markdown("**How RecallRadar keeps you safe**")
    st.write("✓ Checks exact product details")
    st.write("✓ Hides weak or uncertain matches")
    st.write("✓ Links to the official notice")
    st.write("✓ Waits for your approval")

st.subheader("Ready to check your products?")
st.markdown(
    '<div class="friendly-banner"><div class="face">👋</div><div><b>First time here?</b><br>'
    '<span>Use the example products. It takes one click and shows exactly how RecallRadar works.</span></div></div>',
    unsafe_allow_html=True,
)

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

scan_label = "Check the official recall database" if source == "live" else "Show me how RecallRadar works"
if st.button(scan_label, type="primary", width="stretch", disabled=bool(preview_error)):
    with st.status("Radar is investigating product signals…", expanded=True) as status:
        scan_progress = st.progress(12, text="Reading household identifiers")
        st.write("✓ Inventory accepted")
        try:
            scan_progress.progress(38, text="Searching selected recall source")
            matches, products = deterministic_scan(inventory_path, source)
            st.write("✓ Recall notices retrieved")
            scan_progress.progress(68, text="Verifying model, lot, UPC, and brand evidence")
            st.write("✓ Ambiguous candidates suppressed")
            st.session_state["matches"] = matches
            st.session_state["product_count"] = len(products)
            st.session_state["scan_source"] = source
            st.session_state["scan_time"] = datetime.now(timezone.utc).isoformat()
            st.session_state["decisions"] = {}
            st.session_state.pop("agent_brief", None)
            st.session_state.pop("agent_error", None)

            if use_strands:
                scan_progress.progress(84, text="Strands is preparing human decisions")
                try:
                    with st.spinner("Strands is generating the decision brief…"):
                        st.session_state["agent_brief"] = run_strands_scan(inventory_path, source, provider)
                except Exception as agent_exc:
                    st.session_state["agent_error"] = str(agent_exc)
                    st.write("AI explanation unavailable; verified matching results are still ready.")
            scan_progress.progress(100, text="Safety scan complete")
            st.write("✓ Decision packets ready")
            status.update(label="Scan complete — only actionable evidence is shown", state="complete")
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

    if matches:
        st.markdown(
            f'<div class="result-banner"><div><strong>{len(matches)} decision{"s" if len(matches) != 1 else ""} need review</strong>'
            '<span>Open each card to see the exact evidence and choose what happens next.</span></div>'
            '<div class="result-orb">!</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="result-banner"><div><strong>No evidence-backed match today</strong>'
            '<span>The monitor found nothing strong enough to interrupt you.</span></div>'
            '<div class="result-orb">✓</div></div>',
            unsafe_allow_html=True,
        )

    if not matches:
        if st.session_state.get("scan_source") == "live":
            st.success(
                f"Live CPSC search completed successfully. {product_count} products were checked, "
                "and no exact evidence-backed recall match was found."
            )
        else:
            st.success("The guided scan completed with no evidence-backed candidate.")
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
            risk_color = {"Critical": "#ff6b6b", "High": "#ffb454", "Moderate": "#91b7ff"}.get(match.risk, "#91b7ff")
            chips = "".join(f'<span class="chip">{escape(reason)}</span>' for reason in match.reasons)
            st.markdown(
                f"""
                <div class="recall-card" style="animation-delay:{index * .16}s;border-left-color:{risk_color}">
                  <div class="score-ring" style="--score:{match.confidence};--ring:{risk_color}">
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
                st.markdown("**Why RecallRadar surfaced this**")
                for reason in packet["evidence"]:
                    st.write(f"✓ {reason}")
                st.markdown("**Prepared message — review before using**")
                st.code(packet["draft_message"], language=None)
                left, right = st.columns(2)
                if left.button("Approve prepared request", key=f"approve-{match.match_id}"):
                    st.session_state["decisions"][match.match_id] = "APPROVED FOR MANUAL ACTION"
                    st.toast("Approval recorded. No company was contacted automatically.", icon="✓")
                if right.button("Dismiss and verify manually", key=f"dismiss-{match.match_id}"):
                    st.session_state["decisions"][match.match_id] = "DISMISSED — MANUAL VERIFICATION"
                    st.toast("Decision saved for manual verification.", icon="↗")
                st.caption("Technical audit data")
                st.json(packet, expanded=False)

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
        with st.expander("How the Strands agent reached this result"):
            st.write(st.session_state["agent_brief"])

    if st.session_state.get("agent_error"):
        st.warning(
            "The optional AI explanation could not run, but the deterministic recall search "
            "and verified results completed successfully. Select Fast preview to continue without an AI key."
        )
        with st.expander("Technical provider error"):
            st.code(st.session_state["agent_error"], language=None)

st.divider()
st.caption(
    "RecallRadar is a decision-support agent. A candidate is not an official safety determination. "
    "Always verify model and lot information on the official agency notice."
)
