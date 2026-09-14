"""Background monitor for RecallRadar.

Run once with:
    python monitor.py --once
Run continuously with:
    python monitor.py --interval 3600
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from recallradar.agent import deterministic_scan
from recallradar.core import build_action_packet


def monitor_once(inventory: str, source: str, state_file: str) -> dict:
    state_path = Path(state_file)
    previous = set()
    if state_path.exists():
        try:
            previous = set(json.loads(state_path.read_text(encoding="utf-8")).get("seen", []))
        except (json.JSONDecodeError, OSError):
            previous = set()

    matches, products = deterministic_scan(inventory, source)
    current = {match.match_id for match in matches}
    new_matches = [match for match in matches if match.match_id not in previous]

    state_path.write_text(
        json.dumps(
            {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "seen": sorted(current | previous),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "products_checked": len(products),
        "matches_found": len(matches),
        "new_decisions": [
            build_action_packet(match) for match in new_matches
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RecallRadar in the background.")
    parser.add_argument("--inventory", default="data/demo_inventory.csv")
    parser.add_argument("--source", choices=("demo", "live"), default="demo")
    parser.add_argument("--state-file", default=".recallradar_state.json")
    parser.add_argument("--interval", type=int, default=3600)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    while True:
        result = monitor_once(args.inventory, args.source, args.state_file)
        print(json.dumps(result, indent=2))
        if args.once:
            return
        time.sleep(max(60, args.interval))


if __name__ == "__main__":
    main()
