# RecallRadar — Devpost submission copy

## Inspiration

Recall systems assume people will notice an announcement, remember what they bought, locate a model or lot number, interpret the notice, and complete a remedy. Each step is small, but together they make safety action unlikely. We wanted recall protection to work like a smoke detector: quiet most of the time, specific when it matters, and impossible to confuse with a generic chatbot.

## What it does

RecallRadar creates a private, receipt-derived inventory and checks it against product-recall notices. A Strands agent loads and validates the inventory, retrieves notices, verifies candidates with conservative identifier rules, ranks the hazard, and prepares the next action. Weak candidates are suppressed. Confirmed candidates surface with evidence, an immediate safety step, the official notice, and a refund or replacement draft. Nothing external happens without human approval.

## How we built it

- Strands Agents SDK for autonomous orchestration and tool selection
- Google Gemini 3.5 Flash-Lite through Strands as the zero-cost model path
- Amazon Bedrock as an optional deployment path
- Custom Python tools for inventory validation, notice retrieval, exact matching, risk classification, and action preparation
- CPSC public recall service as the live source
- Streamlit for the complete product experience
- Pandas for receipt-derived inventory processing
- Pytest for safety-boundary and matcher tests
- Docker for reproducible deployment

## Challenges we ran into

Product names alone are unsafe matching signals. Similar products can have different models, and a false alarm can undermine trust. We designed an evidence-first matcher where exact model or lot identifiers dominate and weak candidates are withheld. We also separated autonomous preparation from external execution so the agent can do useful work without acting beyond user consent.

## Accomplishments that we're proud of

- A real end-to-end Strands workflow rather than a conversational wrapper
- Conservative matching that correctly rejects a same-brand, wrong-model scenario
- A useful product experience that works without personal data
- Approval-gated action packets with transparent evidence
- A key-free demo mode plus an Amazon Bedrock execution path

## What we learned

The most useful agent is not the one that speaks the most. It is the one that performs repetitive investigation quietly, exposes its evidence, and recognizes when a person should decide.

## What's next

Add receipt-email ingestion, barcode and image extraction, FDA and NHTSA adapters, encrypted household inventories, scheduled EventBridge scans, notifications, and AgentCore deployment with observability.

## Track

Everyday Agents

## One-line pitch

RecallRadar silently monitors what you own, verifies exact product recalls, and interrupts you only when a real safety decision requires approval.
