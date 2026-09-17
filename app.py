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


st.set_page_config(page_title="RecallRadar", page_icon="◉", layout="wide", initial_sidebar_state="collapsed")

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
    /* Editorial product-site theme inspired by task-first public safety services */
    .stApp:before,.stApp:after{display:none!important}
    .stApp{background:#f4f6f1!important;color:#17302c!important}
    [data-testid="stHeader"]{background:transparent!important}
    [data-testid="stToolbar"],#MainMenu,footer{visibility:hidden!important}
    .block-container{max-width:1180px!important;padding-top:1rem!important;padding-bottom:4rem!important}
    h1,h2,h3{font-family:'Space Grotesk',sans-serif!important;color:#142b27!important}
    p{font-family:'DM Sans',sans-serif}
    .site-nav{display:flex;align-items:center;justify-content:space-between;padding:.8rem 0 1.2rem;border-bottom:1px solid #d8dfda;margin-bottom:3.4rem}
    .wordmark{display:flex;align-items:center;gap:.7rem;color:#153d36;font:700 1.05rem 'Space Grotesk'}
    .wordmark-mark{display:grid;place-items:center;width:34px;height:34px;border-radius:9px;background:#184f45;color:#fff;font-size:.72rem}
    .site-links{display:flex;align-items:center;gap:1.35rem;color:#59706a;font-size:.82rem}
    .site-links a{color:#184f45;text-decoration:none;font-weight:700;border-bottom:1px solid #184f45}
    .source-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#2b8b76;margin-right:.4rem}
    .site-hero{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(330px,.75fr);gap:5rem;align-items:center;padding:1.5rem 0 4.4rem}
    .kicker{color:#ad4f3d;font-size:.75rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase;margin:0 0 1rem}
    .site-hero h1{font-size:clamp(3rem,5.7vw,5.25rem)!important;line-height:1.01!important;letter-spacing:-.055em!important;
      max-width:780px;margin:0 0 1.35rem!important;color:#142b27!important;animation:siteRise .65s both}
    .site-hero .lead{color:#526b65;font-size:1.15rem;line-height:1.72;max-width:670px;margin:0 0 1.5rem;animation:siteRise .65s .08s both}
    .hero-actions{display:flex;align-items:center;gap:1rem;animation:siteRise .65s .16s both}
    .hero-link{display:inline-flex;align-items:center;justify-content:center;background:#184f45;color:#fff!important;padding:.85rem 1.1rem;
      border-radius:8px;text-decoration:none!important;font-weight:800;font-size:.9rem;box-shadow:0 8px 20px rgba(24,79,69,.14);transition:.2s ease}
    .hero-link:hover{background:#103d35;transform:translateY(-2px)}.hero-note{color:#6c7f7a;font-size:.82rem}
    .preview-card{background:#fff;border:1px solid #d8dfda;border-radius:14px;padding:1.15rem;box-shadow:0 18px 55px rgba(38,62,55,.1);
      animation:siteRise .7s .12s both}
    .preview-head{display:flex;align-items:center;justify-content:space-between;padding:.15rem .1rem .9rem;border-bottom:1px solid #e6ebe7;
      color:#1d3833;font-weight:800;font-size:.88rem}
    .preview-head b{font-size:.69rem;color:#1f6c5d;background:#e6f3ee;border-radius:999px;padding:.28rem .55rem;text-transform:uppercase}
    .preview-row{display:grid;grid-template-columns:34px 1fr auto;align-items:center;gap:.65rem;padding:.85rem .1rem;border-bottom:1px solid #edf0ed;
      animation:rowIn .45s both}
    .preview-row:nth-child(3){animation-delay:.16s}.preview-row:nth-child(4){animation-delay:.28s}
    .preview-row>span{display:grid;place-items:center;width:28px;height:28px;border-radius:7px;background:#edf3ef;color:#184f45;font-size:.75rem;font-weight:800}
    .preview-row b{display:block;color:#203a35;font-size:.82rem}.preview-row small{display:block;color:#7b8d88;font-size:.72rem;margin-top:.12rem}
    .preview-row em{font-style:normal;color:#55706a;font-size:.7rem;font-weight:700}
    .preview-note{display:flex;align-items:center;gap:.5rem;padding-top:.85rem;color:#5e746f;font-size:.75rem}
    .preview-note i{width:8px;height:8px;border-radius:50%;background:#2b8b76;animation:quietPulse 2.2s infinite}
    .value-strip{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #d8dfda;border-bottom:1px solid #d8dfda;margin-bottom:4rem}
    .value-item{padding:1.15rem 1.2rem;border-right:1px solid #d8dfda}.value-item:last-child{border-right:0}
    .value-item b{display:block;color:#203a35;font-size:.83rem;margin-bottom:.25rem}.value-item span{color:#70817d;font-size:.78rem}
    .process-wrap{margin:0 0 4rem}.section-kicker{color:#ad4f3d;font-size:.72rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
    .process-wrap h2{font-size:clamp(1.8rem,3vw,2.7rem);margin:.4rem 0 1.6rem}.process-line{display:grid;grid-template-columns:repeat(3,1fr);gap:2.2rem}
    .process-step{position:relative;padding-top:1rem;border-top:3px solid #cfd8d3}.process-step:first-child{border-color:#184f45}
    .process-step b{display:block;color:#203a35;font-size:1rem;margin:.6rem 0 .35rem}.process-step p{color:#6a7e78;line-height:1.55;font-size:.86rem;margin:0}
    .process-num{color:#184f45;font:800 .74rem 'Space Grotesk'}
    .check-panel{background:#fff;border:1px solid #d8dfda;border-radius:14px;padding:1.35rem;margin:0 0 1.2rem;box-shadow:0 10px 30px rgba(38,62,55,.06)}
    .check-panel h2{font-size:1.65rem;margin:0 0 .35rem}.check-panel p{color:#6b7f79;margin:0}
    .upload-copy{margin:1.7rem 0 .8rem}.upload-copy b{display:block;color:#203a35;font-size:1rem}.upload-copy span{color:#71837e;font-size:.83rem}
    .friendly-banner,.plain-intro,.simple-steps,.radar-wrap,.signal-ticker,.brand-chip,.trust-row{display:none!important}
    div.stButton>button[kind="primary"]{background:#184f45!important;color:#fff!important;border:1px solid #184f45!important;border-radius:8px!important;
      box-shadow:none!important;min-height:3.1rem;font-weight:800!important}
    div.stButton>button[kind="primary"]:hover{background:#103d35!important;transform:none!important;box-shadow:none!important}
    [data-testid="stFileUploaderDropzone"]{background:#f8faf7!important;border:1px dashed #9eb0a8!important;border-radius:10px!important}
    [data-testid="stFileUploaderDropzone"] p,[data-testid="stFileUploaderDropzone"] small,[data-testid="stFileUploaderDropzone"] span{color:#415b55!important}
    [data-testid="stFileUploaderDropzone"] button{background:#e2ebe6!important;border:1px solid #b9c9c1!important}
    [data-testid="stFileUploaderDropzone"] button *{color:#17302c!important}
    [data-testid="stDownloadButton"] button,.stDownloadButton button{background:#fff!important;border:1px solid #9eb0a8!important;border-radius:8px!important}
    [data-testid="stDownloadButton"] button *,.stDownloadButton button *{color:#184f45!important}
    [data-testid="stMetric"]{background:#fff;border:1px solid #dfe5e1;border-radius:10px;padding:.8rem}
    [data-testid="stMetricLabel"] *{color:#6b7f79!important}[data-testid="stMetricValue"] *{color:#17302c!important}
    [data-testid="stStatusWidget"]{background:#f1f6f3!important;border:1px solid #c9d8d1!important}[data-testid="stStatusWidget"] *{color:#17302c!important}
    [data-testid="stExpander"] details{background:#fff!important;border-color:#d8dfda!important}[data-testid="stExpander"] *{color:#29443e!important}
    .source-banner{background:#eef5f1!important;border:1px solid #cadbd3!important;color:#31584f!important}
    .source-banner.demo{background:#faf4e8!important;border-color:#e4d2ab!important;color:#705a2f!important}
    .agent-flow:before{background:#d9e1dc}.agent-flow:after{background:#2b8b76;box-shadow:none}
    .flow-step{background:#fff!important;border:1px solid #d8dfda!important;border-radius:10px!important}.flow-step b{color:#203a35}
    .flow-step small{color:#748681}.flow-num{background:#e5f1ec!important;color:#184f45!important}
    .result-banner{background:#fff!important;border:1px solid #d8dfda!important;border-radius:12px!important;box-shadow:none!important}
    .result-banner strong{color:#203a35}.result-banner span{color:#6a7e78}.result-orb{background:#e7f2ed!important;border-color:#a8c7b9!important;color:#184f45!important}
    .recall-card{background:#fff!important;border:1px solid #d8dfda!important;border-left:5px solid var(--danger)!important;border-radius:12px!important;
      box-shadow:0 10px 28px rgba(38,62,55,.07)!important}
    .card-body h3{color:#203a35!important}.muted{color:#6a7e78!important}.score-ring:before{background:#fff!important}
    .score-ring strong{color:#203a35}.score-ring span{color:#6b7f79}.chip{border-color:#c8d5cf!important;color:#405d56!important;background:#f7faf8}
    .hazard{background:#fff3ef!important;border-color:#efc8bd!important;color:#733b2f!important}
    .action-box{background:#f3f7f4!important;color:#29443e!important}.action-box b{color:#184f45!important}.eyebrow{color:#ad4f3d!important}
    .stAlert{border-radius:10px!important}
    @keyframes siteRise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
    @keyframes rowIn{from{opacity:0;transform:translateX(10px)}to{opacity:1;transform:none}}
    @keyframes quietPulse{70%{box-shadow:0 0 0 7px rgba(43,139,118,0)}100%{box-shadow:0 0 0 0 rgba(43,139,118,0)}}

    .live-search-panel{background:#e9f2ee;border:1px solid #c4d8cf;border-radius:12px;padding:1.15rem 1.2rem;margin:1.5rem 0 1rem}
    .live-search-panel b{display:block;color:#173d35;font-size:1.05rem;margin-bottom:.25rem}
    .live-search-panel span{color:#58706a;font-size:.86rem;line-height:1.5}
    [data-testid="stTextInput"] input{background:#fff!important;color:#17302c!important;border-color:#aebeb7!important}
    [data-testid="stTextInput"] input::placeholder{color:#8b9b96!important}
    [data-testid="stTextInput"] label p{color:#425d56!important;font-weight:700!important}
    @media(max-width:800px){.agent-flow{grid-template-columns:1fr 1fr}.recall-card{grid-template-columns:1fr}
      .site-nav{margin-bottom:2rem}.site-links span{display:none}.site-hero{grid-template-columns:1fr;gap:2rem;padding-bottom:3rem}
      .site-hero h1{font-size:clamp(2.65rem,13vw,4.2rem)!important}.hero-actions{align-items:flex-start;flex-direction:column}
      .value-strip,.process-line{grid-template-columns:1fr}.value-item{border-right:0;border-bottom:1px solid #d8dfda}
      .value-item:last-child{border-bottom:0}.process-step{margin-bottom:.8rem}}
    @media(prefers-reduced-motion:reduce){*,*:before,*:after{animation-duration:.01ms!important;animation-iteration-count:1!important}}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="site-nav">
      <div class="wordmark"><span class="wordmark-mark">RR</span> RecallRadar</div>
      <div class="site-links">
        <span><i class="source-dot"></i>Uses official CPSC recall notices</span>
        <a href="https://github.com/ShrutiVan17/RecallRadar" target="_blank">View source</a>
      </div>
    </div>
    <section class="site-hero">
      <div>
        <p class="kicker">Personal product-safety monitor</p>
        <h1>Check the products you own. Know what to do next.</h1>
        <p class="lead">RecallRadar compares your product details with recall notices, filters out weak matches, and gives you a clear next step to review.</p>
        <div class="hero-actions"><a class="hero-link" href="#check-products">Search live recalls</a><span class="hero-note">Live U.S. CPSC data · No account required</span></div>
      </div>
      <div class="preview-card">
        <div class="preview-head"><span>Product safety check</span><b>Ready</b></div>
        <div class="preview-row"><span>01</span><div><b>Add a product list</b><small>Name, model, lot or barcode</small></div><em>Input</em></div>
        <div class="preview-row"><span>02</span><div><b>Compare recall notices</b><small>Exact identifiers are checked first</small></div><em>Check</em></div>
        <div class="preview-row"><span>03</span><div><b>Review the next step</b><small>Evidence, remedy and official source</small></div><em>Decide</em></div>
        <div class="preview-note"><i></i>Nothing happens without your approval</div>
      </div>
    </section>
    <div class="value-strip">
      <div class="value-item"><b>Evidence before alerts</b><span>Weak or uncertain matches stay hidden.</span></div>
      <div class="value-item"><b>Official source links</b><span>Every live result points back to the notice.</span></div>
      <div class="value-item"><b>Plain-language guidance</b><span>See what happened and what to do next.</span></div>
    </div>
    <section class="process-wrap">
      <span class="section-kicker">How it works</span><h2>One careful check, from product list to decision.</h2>
      <div class="process-line">
        <div class="process-step"><span class="process-num">01</span><b>Add products</b><p>Enter one product directly, or upload a CSV when you want to check several.</p></div>
        <div class="process-step"><span class="process-num">02</span><b>Verify matches</b><p>RecallRadar checks official notices and compares exact identifiers.</p></div>
        <div class="process-step"><span class="process-num">03</span><b>Review the action</b><p>Read the evidence, open the official notice, and choose what happens next.</p></div>
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div id="check-products" class="check-panel"><span class="section-kicker">Start a check</span>'
    '<h2>Search official product recall notices</h2><p>Live CPSC search opens first. The example walkthrough remains available only when you choose it.</p></div>',
    unsafe_allow_html=True,
)
control_a, control_b = st.columns(2)
with control_a:
    source_label = st.radio(
        "Product source",
        ["Official CPSC search", "Example products"],
        captions=["Search live government notices", "Optional synthetic walkthrough"],
        horizontal=True,
    )
with control_b:
    provider_label = st.selectbox(
        "Processing mode",
        ["Standard check · recommended", "AI explanation · Gemini", "AI explanation · Amazon Bedrock"],
        index=0,
    )
source = "demo" if source_label.startswith("Example") else "live"
use_strands = provider_label.startswith("AI")
provider = "gemini" if "Gemini" in provider_label else "bedrock"
st.caption("Standard check is fastest and does not require an AI key. Uploaded data remains in this browser session.")
uploaded = None
manual_name = ""
manual_brand = ""
manual_model = ""
manual_lot = ""
manual_upc = ""

def clear_previous_scan() -> None:
    """Hide results as soon as the product query changes."""
    for key in (
        "matches",
        "product_count",
        "scan_source",
        "scan_time",
        "decisions",
        "agent_brief",
        "agent_error",
        "visible_query_signature",
    ):
        st.session_state.pop(key, None)

if source == "live":
    st.markdown(
        '<div class="live-search-panel"><b>Search the live U.S. CPSC recall database</b>'
        '<span>Enter the product information printed on the item, label, packaging, or receipt. '
        'A model, lot, or barcode gives the most reliable result.</span></div>',
        unsafe_allow_html=True,
    )
    name_col, brand_col = st.columns([2, 1])
    with name_col:
        manual_name = st.text_input("Product name", placeholder="Example: digital air fryer", on_change=clear_previous_scan)
    with brand_col:
        manual_brand = st.text_input("Brand", placeholder="Example: NorthStar", on_change=clear_previous_scan)
    model_col, lot_col, upc_col = st.columns(3)
    with model_col:
        manual_model = st.text_input("Model number", placeholder="Example: AF-900", on_change=clear_previous_scan)
    with lot_col:
        manual_lot = st.text_input("Lot number", placeholder="Optional", on_change=clear_previous_scan)
    with upc_col:
        manual_upc = st.text_input("UPC or barcode", placeholder="Optional", on_change=clear_previous_scan)

    with st.expander("Check several products with a CSV instead"):
        uploaded = st.file_uploader(
            "Product inventory CSV",
            type=["csv"],
            help="Accepted fields include name/product_name, brand, model, lot, UPC, purchase date, and retailer.",
            key="live_inventory_upload",
        )
        st.download_button(
            "Download CSV template",
            data=open("data/demo_inventory.csv", "rb").read(),
            file_name="recallradar_inventory_template.csv",
            mime="text/csv",
            width="stretch",
            key="live_template",
        )
else:
    st.markdown(
        '<div class="upload-copy"><b>Optional: use your own product list</b>'
        '<span>Leave this empty to run the prepared example. Upload a CSV only when you want to test your own records.</span></div>',
        unsafe_allow_html=True,
    )
    upload_col, template_col = st.columns([3, 1])
    with upload_col:
        uploaded = st.file_uploader(
            "Product inventory CSV",
            type=["csv"],
            help="Accepted fields include name/product_name, brand, model, lot, UPC, purchase date, and retailer.",
            key="demo_inventory_upload",
        )
    with template_col:
        st.caption("Need the correct format?")
        st.download_button(
            "Download CSV template",
            data=open("data/demo_inventory.csv", "rb").read(),
            file_name="recallradar_inventory_template.csv",
            mime="text/csv",
            width="stretch",
            key="demo_template",
        )

inventory_path = "data/demo_inventory.csv" if source == "demo" else ""
preview_error = None
products_preview = []
preview = pd.DataFrame()
try:
    if uploaded:
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp.write(uploaded.getvalue())
        temp.close()
        inventory_path = temp.name
    elif source == "live" and manual_name.strip():
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        temp.close()
        pd.DataFrame([{
            "name": manual_name.strip(),
            "brand": manual_brand.strip(),
            "model": manual_model.strip(),
            "lot": manual_lot.strip(),
            "upc": manual_upc.strip(),
        }]).to_csv(temp.name, index=False)
        inventory_path = temp.name

    if inventory_path:
        products_preview = load_inventory(inventory_path)
        preview = pd.DataFrame([asdict(product) for product in products_preview])
except Exception as exc:
    products_preview, preview = [], pd.DataFrame()
    preview_error = str(exc)

query_signature = json.dumps(
    {
        "source": source,
        "provider": provider_label,
        "products": [asdict(product) for product in products_preview],
    },
    sort_keys=True,
)
if st.session_state.get("visible_query_signature") != query_signature:
    for stale_key in ("matches", "product_count", "scan_source", "scan_time", "decisions", "agent_brief", "agent_error"):
        st.session_state.pop(stale_key, None)

if source == "live":
    st.markdown('<div class="source-banner"><b>LIVE MODE</b> · Searches the official U.S. CPSC Recall API using each product model or name. Results depend on agency coverage.</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="source-banner demo"><b>DEMONSTRATION MODE</b> · Uses synthetic notices to provide a reliable judging walkthrough. No result is a real recall.</div>', unsafe_allow_html=True)

if preview_error:
    st.error(preview_error)
elif source == "live" and not products_preview:
    st.info("Enter a product name above, or upload a CSV, to start a live CPSC search.")
else:
    identifier_ready = sum(bool(item.model or item.lot or item.upc) for item in products_preview)
    duplicates = int(preview["product_id"].duplicated().sum()) if not preview.empty else 0
    q1, q2, q3 = st.columns(3)
    q1.metric("Products ready", len(products_preview))
    q2.metric("With exact identifiers", f"{identifier_ready}/{len(products_preview)}")
    q3.metric("Duplicate records", duplicates)
    if identifier_ready < len(products_preview):
        st.warning("Add a model, lot, or UPC when possible. Name-only searches are broader, and weak matches will be hidden.")
    with st.expander("Review the product details being searched", expanded=False):
        st.dataframe(preview, width="stretch", hide_index=True)

scan_label = "Search live CPSC notices" if source == "live" else "Check the example products"
scan_disabled = bool(preview_error) or not products_preview
if st.button(scan_label, type="primary", width="stretch", disabled=scan_disabled):
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
            st.session_state["visible_query_signature"] = query_signature
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
            f'<div class="result-banner"><div><strong>{len(matches)} decision{"s need" if len(matches) != 1 else " needs"} review</strong>'
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
