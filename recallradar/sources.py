"""Inventory loaders and recall-source adapters."""

from __future__ import annotations

import csv
import html
import io
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import requests

from .core import Product, Recall


CPSC_URL = "https://www.saferproducts.gov/RestWebServices/Recall"
CPSC_CSV_URL = "https://www.cpsc.gov/s3fs-public/recall-data/recalls_recall_listing.csv"

FIELD_ALIASES = {
    "product": "name", "product_name": "name", "item": "name",
    "manufacturer": "brand", "make": "brand",
    "model_number": "model", "model_no": "model",
    "lot_number": "lot", "lot_no": "lot",
    "purchase": "purchase_date", "date": "purchase_date",
    "store": "retailer", "upc_code": "upc", "barcode": "upc",
}


def load_inventory(path: str | Path) -> list[Product]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not rows:
        raise ValueError("Inventory is empty. Add at least one product row.")
    if len(rows) > 500:
        raise ValueError("Inventory is limited to 500 products per scan.")

    fields = {
        FIELD_ALIASES.get((name or "").strip().lower(), (name or "").strip().lower())
        for name in (reader.fieldnames or [])
    }
    if "name" not in fields:
        raise ValueError("Inventory needs a 'name' or 'product_name' column.")

    allowed = set(Product.__dataclass_fields__)
    products: list[Product] = []
    for index, raw in enumerate(rows, start=1):
        normalized = {}
        for key, value in raw.items():
            clean_key = (key or "").strip().lower()
            normalized[FIELD_ALIASES.get(clean_key, clean_key)] = str(value or "").strip()
        values = {field: normalized.get(field, "") for field in allowed}
        values["product_id"] = values["product_id"] or f"P{index:03d}"
        if not values["name"]:
            raise ValueError(f"Row {index} has no product name.")
        products.append(Product(**values))
    return products


def demo_recalls(path: str | Path = "data/demo_recalls.csv") -> list[Recall]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [Recall(**row) for row in csv.DictReader(handle)]


def _join(values: list[dict], *keys: str) -> str:
    found: list[str] = []
    for item in values or []:
        for key in keys:
            if item.get(key):
                found.append(str(item[key]))
    return ", ".join(dict.fromkeys(found))


def _parse_cpsc_payload(payload: list[dict], limit: int) -> list[Recall]:
    recalls: list[Recall] = []
    for item in payload[:limit]:
        products = item.get("Products") or [{}]
        product_text = _join(products, "Name", "Description")
        explicit_models = _join(products, "Model")
        model_text = ", ".join(part for part in (explicit_models, product_text) if part)
        upc_text = _join(item.get("ProductUPCs") or [], "UPC")
        brands = item.get("Manufacturers") or []
        brand_text = _join(brands, "Name")
        hazards = _join(item.get("Hazards") or [], "Name")
        remedies = _join(item.get("Remedies") or [], "Name")
        recall_id = str(item.get("RecallID") or item.get("RecallNumber") or "unknown")
        recalls.append(
            Recall(
                recall_id=recall_id,
                title=str(item.get("Title") or product_text or "CPSC recall"),
                brand=brand_text,
                product_name=product_text,
                models=model_text,
                lots=product_text,
                hazard=hazards,
                remedy=remedies,
                official_url=str(item.get("URL") or ""),
                recall_date=str(item.get("RecallDate") or ""),
                upcs=upc_text,
            )
        )
    return recalls


@lru_cache(maxsize=256)
def _fetch_cpsc_query(query_items: tuple[tuple[str, str], ...], limit: int, timeout: int) -> tuple[Recall, ...]:
    """Fetch one CPSC query and briefly reuse identical results."""
    response = requests.get(
        CPSC_URL,
        params={"format": "json", **dict(query_items)},
        headers={"User-Agent": "RecallRadar/1.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("The CPSC API returned an unexpected response.")
    return tuple(_parse_cpsc_payload(payload, limit))


def _clean_cpsc_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"https?://(?:www\.)?cpsc\.gov/\S+", " ", text)
    text = re.sub(r'\s*lang="[^"]*">', " ", text)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).replace("\xa0", " ").strip()


@lru_cache(maxsize=1)
def _fetch_recent_cpsc_csv(timeout: int = 12) -> tuple[Recall, ...]:
    """Read the newest official CPSC CSV rows without downloading the 17 MB archive."""
    response = requests.get(
        CPSC_CSV_URL,
        headers={
            "User-Agent": "RecallRadar/1.0",
            "Range": "bytes=0-1048575",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    text = response.content.decode("utf-8-sig", errors="ignore")
    if "\n" in text:
        text = text.rsplit("\n", 1)[0] + "\n"

    recalls: list[Recall] = []
    for row in csv.DictReader(io.StringIO(text)):
        recall_id = _clean_cpsc_text(row.get("Recall Number"))
        if not recall_id:
            continue
        title = _clean_cpsc_text(row.get("Recall Heading"))
        product_name = _clean_cpsc_text(row.get("Name of product"))
        description = _clean_cpsc_text(row.get("Description"))
        brand = ", ".join(
            part
            for part in (
                _clean_cpsc_text(row.get("Importers")),
                _clean_cpsc_text(row.get("Manufacturers")),
                _clean_cpsc_text(row.get("Distributors")),
            )
            if part
        )
        consumer_action = _clean_cpsc_text(row.get("Consumer Action"))
        remedy_type = _clean_cpsc_text(row.get("Remedy Type"))
        recalls.append(
            Recall(
                recall_id=recall_id,
                title=title or product_name or "CPSC recall",
                brand=brand,
                product_name=" ".join(part for part in (product_name, description) if part),
                models=description,
                lots=description,
                hazard=_clean_cpsc_text(row.get("Hazard Description")),
                remedy=consumer_action or remedy_type,
                official_url=f"https://www.cpsc.gov/Recalls?search_combined_fields={quote(recall_id)}",
                recall_date=_clean_cpsc_text(row.get("Date")),
            )
        )
    return tuple(recalls)


def fetch_cpsc_recalls(products: list[Product] | None = None, limit: int = 75, timeout: int = 8) -> list[Recall]:
    """Query CPSC concurrently, deduplicate results, and avoid repeated identical calls."""
    raw_queries: list[dict[str, str]] = []
    for product in (products or [])[:40]:
        if product.model:
            raw_queries.append({"ProductModel": product.model})
        if product.name:
            raw_queries.append({"ProductName": product.name})
    if not raw_queries:
        raw_queries = [{"RecallDateStart": (date.today() - timedelta(days=1095)).strftime("%m/%d/%Y")}]

    query_keys = list(dict.fromkeys(tuple(sorted(query.items())) for query in raw_queries))
    collected: dict[str, Recall] = {}
    failures: list[str] = []
    worker_count = min(6, len(query_keys))

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = {
            pool.submit(_fetch_cpsc_query, query_key, limit, timeout): query_key
            for query_key in query_keys
        }
        for future in as_completed(futures):
            try:
                for recall in future.result():
                    collected[recall.recall_id] = recall
            except Exception as exc:
                failures.append(str(exc))

    if not collected and products:
        # The API's model/name indexes occasionally lag behind newly published notices.
        # Search the current year's official feed as a fallback, then let the
        # deterministic matcher verify exact identifiers from the product description.
        fallback_key = (("RecallDateStart", date.today().replace(month=1, day=1).strftime("%m/%d/%Y")),)
        try:
            for recall in _fetch_cpsc_query(fallback_key, max(limit, 600), max(timeout, 12)):
                collected[recall.recall_id] = recall
        except Exception as exc:
            failures.append(str(exc))

    # Merge the newest rows from CPSC's official weekly CSV. This covers
    # notices that can appear before the legacy API's search index catches up.
    try:
        for recall in _fetch_recent_cpsc_csv(max(timeout, 12)):
            collected[recall.recall_id] = recall
    except Exception as exc:
        failures.append(str(exc))

    if failures and not collected:
        raise RuntimeError(
            "The official CPSC service did not respond. Please wait a moment and try again."
        )
    return list(collected.values())

