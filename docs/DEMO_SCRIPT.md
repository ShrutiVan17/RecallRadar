# RecallRadar demo script (4 minutes 20 seconds)

## 0:00–0:35 — Problem

“Recall notices are published every day, but households do not maintain searchable model and lot records. People must remember to check multiple sources, interpret notices, and repeat the same verification work. Most never do.”

Show the landing screen and the five-item synthetic inventory.

## 0:35–1:10 — Product

“RecallRadar quietly converts receipt-derived records into a safety inventory. It retrieves notices, verifies exact identifiers, suppresses weak candidates, and interrupts the user only when a genuine safety decision appears.”

Point to the four agent-policy safeguards in the sidebar.

## 1:10–2:25 — Working demonstration

1. Keep **Demo recall feed** selected.
2. Click **Run safety scan**.
3. Show the agent workflow status.
4. Explain the two evidence-backed candidates.
5. Emphasize that the BrightNest product was rejected because its model did not match.
6. Open an action packet and show the evidence, immediate action, remedy, and draft request.

## 2:25–3:15 — Strands implementation

Show \`recallradar/agent.py\`.

“The Strands agent chooses four custom tools: load inventory, retrieve notices, verify exact matches, and prepare the action. Deterministic matching handles safety-critical identifiers. The model handles orchestration and clear decision summaries.”

If AWS credentials are configured, enable **Strands + Amazon Bedrock**, run again, and show the generated decision brief.

## 3:15–3:50 — Human approval

Click **Approve prepared request**.

“RecallRadar records approval but this prototype deliberately does not contact an external party. That is a safety boundary, not a missing feature. A production deployment would send only after authenticated consent.”

## 3:50–4:20 — Impact and close

“RecallRadar changes recall discovery from a task people must remember into background protection. The same agent can later expand across CPSC, FDA, and NHTSA sources while preserving exact-match evidence and human control.”

End on the architecture diagram.
