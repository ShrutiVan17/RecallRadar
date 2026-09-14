# Free setup: Strands + Gemini

This route does not require AWS or a paid cloud account.

## Create the key

1. Open https://aistudio.google.com/apikey
2. Sign in with your Google account.
3. Select **Create API key**.
4. Copy the key temporarily.
5. Do not paste it into GitHub, screenshots, videos, or chat.

## Run on Windows PowerShell

~~~powershell
git clone https://github.com/ShrutiVan17/RecallRadar.git
cd RecallRadar
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GEMINI_API_KEY="PASTE_YOUR_KEY_HERE"
$env:RECALLRADAR_PROVIDER="gemini"
streamlit run app.py
~~~

Open http://localhost:8501 if the browser does not open automatically.

In the sidebar:

1. Choose **Demo recall feed**.
2. Choose **Strands + Gemini free tier**.
3. Click **Start animated safety scan**.
4. Confirm the animated attention map and Strands decision brief appear.

The environment variable exists only in the current PowerShell window. Close that window after the demo to clear it.

## If PowerShell blocks activation

~~~powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
~~~

## If Gemini returns 429

Wait briefly and retry. Free-tier requests have rate limits.

## Zero-key visual fallback

Choose **Visual demo · no key**. Matching, animations, safety cards, and approval controls work, but the generated Strands decision brief is disabled.
