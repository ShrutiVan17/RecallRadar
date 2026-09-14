from recallradar.sources import load_inventory


def test_flexible_inventory_headers_and_generated_id(tmp_path):
    inventory = tmp_path / "inventory.csv"
    inventory.write_text(
        "product_name,manufacturer,model_number,barcode\n"
        "Air Fryer,NorthStar,AF-900,012345678905\n",
        encoding="utf-8",
    )
    products = load_inventory(inventory)
    assert products[0].product_id == "P001"
    assert products[0].name == "Air Fryer"
    assert products[0].upc == "012345678905"
