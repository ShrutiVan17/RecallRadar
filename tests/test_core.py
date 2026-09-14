from recallradar.core import Product, Recall, build_action_packet, match_product


def test_exact_model_creates_high_confidence_match():
    product = Product("P1", "Digital Air Fryer", "NorthStar", "AF-900")
    recall = Recall("R1", "Air fryer recall", "NorthStar", "Air Fryer", "AF-800, AF-900", hazard="fire")
    match = match_product(product, recall)
    assert match is not None
    assert match.confidence >= 80
    assert match.risk == "Critical"


def test_wrong_model_is_suppressed_even_when_brand_matches():
    product = Product("P1", "Infant Travel Seat", "BrightNest", "BN-22")
    recall = Recall("R1", "Travel seat recall", "BrightNest", "Infant Travel Seat", "BN-40")
    assert match_product(product, recall) is None


def test_action_never_auto_submits():
    product = Product("P1", "Snack Bars", "NutriPeak", lot="L2407A")
    recall = Recall("R1", "Snack recall", "NutriPeak", "Snack Bars", lots="L2407A")
    packet = build_action_packet(match_product(product, recall))
    assert packet["status"] == "AWAITING_HUMAN_APPROVAL"


def test_exact_upc_match_is_supported():
    product = Product("P1", "Countertop Cooker", "Example", upc="012345678905")
    recall = Recall("R1", "Cooker recall", "Other", "Cooker", upcs="012345678905")
    match = match_product(product, recall)
    assert match is not None
    assert match.confidence >= 75
