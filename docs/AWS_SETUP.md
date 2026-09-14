# Connect RecallRadar to Amazon Bedrock

RecallRadar uses the standard AWS credential chain. Never commit access keys to GitHub or paste them into chat.

## 1. Select the Region

In the AWS Console, switch the Region selector to **US East (N. Virginia) — us-east-1**.

## 2. Test Amazon Nova Lite

1. Open [Amazon Bedrock](https://console.aws.amazon.com/bedrock/).
2. Open **Model catalog**.
3. Search for **Amazon Nova Lite**.
4. Open the model and choose **Open in playground**.
5. Send a short test prompt.

Bedrock generally enables foundation-model access by default. If the console shows an access or Marketplace agreement step, complete that account-level prompt first.

## 3. Give your development identity minimum inference permission

Attach the policy in "infra/bedrock-policy.json" to the IAM user or role used for this project. The application needs:

- bedrock:InvokeModel
- bedrock:InvokeModelWithResponseStream

For a hackathon account, the included policy permits these two actions. Restrict resources further before production use.

## 4. Install AWS CLI v2

Follow the official installer:
https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

Close and reopen PowerShell, then check:

~~~powershell
aws --version
~~~

## 5. Sign in securely

Preferred for a personal console account with a current AWS CLI:

~~~powershell
aws login
~~~

Complete the browser sign-in. If your organization uses IAM Identity Center, use:

~~~powershell
aws configure sso
aws sso login
~~~

If neither method is available, create a dedicated least-privilege IAM identity and run "aws configure". Never use root-account access keys.

Confirm the identity:

~~~powershell
aws sts get-caller-identity
~~~

## 6. Run RecallRadar on Windows

~~~powershell
git clone https://github.com/ShrutiVan17/RecallRadar.git
cd RecallRadar
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:AWS_REGION="us-east-1"
$env:AWS_DEFAULT_REGION="us-east-1"
$env:RECALLRADAR_MODEL_ID="us.amazon.nova-lite-v1:0"
$env:RECALLRADAR_USE_STRANDS="1"
streamlit run app.py
~~~

Your browser should open at http://localhost:8501.

## 7. Verify the real agent path

1. Keep **Demo recall feed** selected.
2. Confirm **Strands + Amazon Bedrock** is on.
3. Click **Start animated safety scan**.
4. Wait for the animated attention map.
5. Confirm a **Strands decision brief** appears below the recall cards.

## Common errors

### AccessDeniedException

The active identity lacks one of the two Bedrock invoke permissions, or an organization policy blocks cross-Region inference.

### UnrecognizedClientException or expired token

Run "aws login" again, or "aws sso login" for an SSO profile.

### Model unavailable

Confirm the Region is us-east-1, open Nova Lite once in the Bedrock playground, and keep the model ID exactly:

us.amazon.nova-lite-v1:0

### PowerShell blocks activation

Run this only for the current PowerShell process, then activate again:

~~~powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
~~~
