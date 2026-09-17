"""Deterministic safety logic used by RecallRadar's Strands tools."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable


STOPWORDS = {
    "the", "and", "for", "with", "product", "products", "model", "models",
    "portable", "electric", "consumer", "recall", "recalled",
}


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str
    brand: str
    model: str = ""
    lot: str = ""
    purchase_date: str = ""
    retailer: str = ""
    upc: str = ""


@dataclass(frozen=True)
class Recall:
    recall_id: str
    title: str
    brand: str
    product_name: str
    models: str = ""
    lots: str = ""
    hazard: str = ""
    remedy: str = ""
    official_url: str = ""
    recall_date: str = ""
    upcs: str = ""


@dataclass(frozen=True)
class Match:
    match_id: str
    product_id: str
    recall_id: str
    confidence: int
    risk: str
    reasons: tuple[str, ...]
    product: Product
    recall: Recall

    def to_dict(self) -> dict:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data


def normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def tokens(value: object) -> set[str]:
    words = re.findall(r"[a-z0-9]+", str(value or "").lower())
    return {word for word in words if len(word) > 2 and word not in STOPWORDS}


def split_identifiers(value: object) -> set[str]:
    return {normalize(part) for part in re.split(r"[,;/|\s]+", str(value or "")) if normalize(part)}


def risk_level(hazard: str) -> str:
    text = str(hazard or "").lower()
    if any(term in text for term in ("death", "fire", "burn", "shock", "poison", "choking")):
        return "Critical"
    if any(term in text for term in ("injury", "laceration", "fall", "overheat")):
        return "High"
    return "Moderate"


def match_product(product: Product, recall: Recall) -> Match | None:
    """Return only evidence-backed candidates; exact model/lot matches dominate."""
    reasons: list[str] = []
    score = 0

    product_model = normalize(product.model)
    product_lot = normalize(product.lot)
    recall_models = split_identifiers(recall.models)
    recall_lots = split_identifiers(recall.lots)
    recall_upcs = split_identifiers(recall.upcs)

    if product_model and product_model in recall_models:
        score += 65
        reasons.append(f"Exact model match: {product.model}")
    if product_lot and product_lot in recall_lots:
        score += 75
        reasons.append(f"Exact lot match: {product.lot}")
    product_upc = normalize(product.upc)
    if product_upc and product_upc in recall_upcs:
        score += 75
        reasons.append(f"Exact UPC match: {product.upc}")

    normalized_brand = normalize(product.brand)
    recall_identity = normalize(f"{recall.brand} {recall.product_name} {recall.title}")
    brand_match = bool(normalized_brand) and (
        normalized_brand == normalize(recall.brand) or normalized_brand in recall_identity
    )
    if brand_match:
        score += 15
        reasons.append(f"Brand match: {product.brand}")

    left = tokens(product.name)
    right = tokens(f"{recall.product_name} {recall.title}")
    overlap = left & right
    if overlap:
        similarity = len(overlap) / max(1, len(left))
        score += min(20, round(similarity * 20))
        reasons.append("Product evidence: " + ", ".join(sorted(overlap)))

    exact_identifier = any(reason.startswith("Exact ") for reason in reasons)
    if not exact_identifier and not (brand_match and score >= 28):
        return None
    if score < 55:
        return None

    confidence = min(score, 99)
    return Match(
        match_id=f"{product.product_id}-{recall.recall_id}",
        product_id=product.product_id,
        recall_id=recall.recall_id,
        confidence=confidence,
        risk=risk_level(recall.hazard),
        reasons=tuple(reasons),
        product=product,
        recall=recall,
    )


def scan(products: Iterable[Product], recalls: Iterable[Recall]) -> list[Match]:
    matches = [
        match
        for product in products
        for recall in recalls
        if (match := match_product(product, recall)) is not None
    ]
    risk_order = {"Critical": 0, "High": 1, "Moderate": 2}
    return sorted(matches, key=lambda item: (risk_order[item.risk], -item.confidence))


def build_action_packet(match: Match) -> dict:
    """Prepare an action; execution always remains behind human approval."""
    remedy = match.recall.remedy or "Stop using the item and contact the manufacturer."
    return {
        "match_id": match.match_id,
        "status": "AWAITING_HUMAN_APPROVAL",
        "immediate_action": "Stop using and isolate the product safely.",
        "recommended_remedy": remedy,
        "hazard": match.recall.hazard,
        "recall_date": match.recall.recall_date,
        "evidence": list(match.reasons),
        "official_notice": match.recall.official_url,
        "draft_message": (
            f"I own {match.product.brand} {match.product.name}, model "
            f"{match.product.model or 'not recorded'}. It appears to match recall "
            f"{match.recall.recall_id}. Please confirm eligibility and next steps."
        ),
        "disclaimer": "Verify against the official notice before acting.",
    }
