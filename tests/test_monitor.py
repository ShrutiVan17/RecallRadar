from monitor import monitor_once


def test_monitor_surfaces_only_new_decisions(tmp_path):
    state = tmp_path / "state.json"
    first = monitor_once("data/demo_inventory.csv", "demo", str(state))
    second = monitor_once("data/demo_inventory.csv", "demo", str(state))
    assert len(first["new_decisions"]) == 2
    assert second["new_decisions"] == []
