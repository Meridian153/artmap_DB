from typing import Any

from src.reception.application.ports import IWikidataPort

from .base_client import BaseApiClient


class WikidataClient(BaseApiClient, IWikidataPort):
    def __init__(self):
        super().__init__(
            base_url="https://www.wikidata.org/w/api.php", api_name="Wikidata", rate_limit_delay=0.2
        )

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        params = {
            "action": "wbgetentities",
            "ids": entity_id,
            "format": "json",
            "languages": "en|ko",
        }

        response = self._make_request("", params=params)
        entities = response.get("entities", {})

        if entity_id in entities:
            return entities[entity_id]
        return None

    def search_artworks(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "type": "item",
            "limit": limit,
            "format": "json",
        }

        response = self._make_request("", params=params)
        return response.get("search", [])

    def get_artwork_details(self, wikidata_id: str) -> dict[str, Any] | None:
        entity = self.get_entity(wikidata_id)
        if not entity:
            return None

        claims = entity.get("claims", {})
        labels = entity.get("labels", {})

        return {
            "wikidata_id": wikidata_id,
            "title_en": labels.get("en", {}).get("value", ""),
            "title_ko": labels.get("ko", {}).get("value", ""),
            "creator": self._extract_claim_value(claims.get("P170", [])),
            "inception": self._extract_claim_value(claims.get("P571", [])),
            "material": self._extract_claim_value(claims.get("P186", [])),
            "image": self._extract_claim_value(claims.get("P18", [])),
            "collection": self._extract_claim_value(claims.get("P195", [])),
        }

    def _extract_claim_value(self, claims: list[dict]) -> str | None:
        if not claims:
            return None

        try:
            mainsnak = claims[0].get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            value = datavalue.get("value")

            if isinstance(value, dict):
                return value.get("id") or value.get("time") or str(value)
            return str(value) if value else None
        except (IndexError, KeyError):
            return None
