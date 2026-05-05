from __future__ import annotations

import time
from typing import Any

import requests

from src.reception.application.ports import IWikidataPort
from src.reception.infra.external_apis.exceptions import ExternalApiException

from .base_client import BaseApiClient

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"


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

    # ── SPARQL 기반 검색 ─────────────────────────────────────

    def _execute_sparql(self, query: str) -> list[dict[str, Any]]:
        """Wikidata SPARQL 엔드포인트에 쿼리를 실행하고 결과를 반환한다."""
        try:
            time.sleep(self.rate_limit_delay)

            response = self.session.get(
                SPARQL_ENDPOINT,
                params={"query": query, "format": "json"},
                headers={"Accept": "application/sparql-results+json"},
                timeout=60,
            )

            if response.status_code == 429:
                self.logger.warning("SPARQL rate limit hit, retrying after 5s...")
                time.sleep(5)
                response = self.session.get(
                    SPARQL_ENDPOINT,
                    params={"query": query, "format": "json"},
                    headers={"Accept": "application/sparql-results+json"},
                    timeout=60,
                )

            response.raise_for_status()
            return response.json().get("results", {}).get("bindings", [])

        except requests.exceptions.RequestException as e:
            self.logger.error(f"SPARQL query failed: {str(e)}")
            raise ExternalApiException("Wikidata SPARQL", str(e))

    def _parse_sparql_results(self, bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """SPARQL 결과 바인딩을 정규화된 dict 리스트로 변환한다."""
        results = []
        for row in bindings:
            artwork_uri = row.get("artwork", {}).get("value", "")
            wikidata_id = artwork_uri.split("/")[-1] if artwork_uri else ""

            results.append({
                "wikidata_id": wikidata_id,
                "title_en": row.get("artworkLabel", {}).get("value", ""),
                "title_ko": row.get("artworkLabel_ko", {}).get("value", ""),
                "creator": row.get("creatorLabel", {}).get("value", ""),
                "creator_id": (row.get("creator", {}).get("value", "").split("/")[-1]
                               if row.get("creator") else ""),
                "inception": row.get("inception", {}).get("value", ""),
                "image": row.get("image", {}).get("value", ""),
                "collection": row.get("collectionLabel", {}).get("value", ""),
                "material": row.get("materialLabel", {}).get("value", ""),
            })
        return results

    def search_artworks_by_collection(
        self, collection_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """소장처(institution) 기준으로 회화 작품 검색"""
        query = f"""
        SELECT ?artwork ?artworkLabel ?artworkLabel_ko
               ?creator ?creatorLabel ?inception ?image
               ?collectionLabel ?materialLabel
        WHERE {{
          ?artwork wdt:P31 wd:Q3305213 .
          ?artwork wdt:P195 wd:{collection_id} .
          OPTIONAL {{ ?artwork wdt:P170 ?creator . }}
          OPTIONAL {{ ?artwork wdt:P571 ?inception . }}
          OPTIONAL {{ ?artwork wdt:P18 ?image . }}
          OPTIONAL {{ ?artwork wdt:P186 ?material . }}
          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en" .
            ?artwork rdfs:label ?artworkLabel .
            ?creator rdfs:label ?creatorLabel .
            ?material rdfs:label ?materialLabel .
          }}
          OPTIONAL {{
            ?artwork rdfs:label ?artworkLabel_ko .
            FILTER(LANG(?artworkLabel_ko) = "ko")
          }}
          BIND(wd:{collection_id} AS ?collection)
          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en" .
            ?collection rdfs:label ?collectionLabel .
          }}
        }}
        LIMIT {limit}
        """

        self.logger.info(f"Searching artworks by collection: {collection_id} (limit={limit})")
        bindings = self._execute_sparql(query)
        results = self._parse_sparql_results(bindings)
        self.logger.info(f"Found {len(results)} artworks for collection {collection_id}")
        return results

    def search_artworks_by_creator(
        self, creator_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """제작자(artist) 기준으로 회화 작품 검색"""
        query = f"""
        SELECT ?artwork ?artworkLabel ?artworkLabel_ko
               ?creator ?creatorLabel ?inception ?image
               ?collectionLabel ?materialLabel
        WHERE {{
          ?artwork wdt:P31 wd:Q3305213 .
          ?artwork wdt:P170 wd:{creator_id} .
          OPTIONAL {{ ?artwork wdt:P195 ?collection . }}
          OPTIONAL {{ ?artwork wdt:P571 ?inception . }}
          OPTIONAL {{ ?artwork wdt:P18 ?image . }}
          OPTIONAL {{ ?artwork wdt:P186 ?material . }}
          BIND(wd:{creator_id} AS ?creator)
          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en" .
            ?artwork rdfs:label ?artworkLabel .
            ?creator rdfs:label ?creatorLabel .
            ?collection rdfs:label ?collectionLabel .
            ?material rdfs:label ?materialLabel .
          }}
          OPTIONAL {{
            ?artwork rdfs:label ?artworkLabel_ko .
            FILTER(LANG(?artworkLabel_ko) = "ko")
          }}
        }}
        LIMIT {limit}
        """

        self.logger.info(f"Searching artworks by creator: {creator_id} (limit={limit})")
        bindings = self._execute_sparql(query)
        results = self._parse_sparql_results(bindings)
        self.logger.info(f"Found {len(results)} artworks for creator {creator_id}")
        return results

    def search_artworks_by_collection_and_creator(
        self, collection_id: str, creator_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """소장처 + 제작자 동시 조건으로 회화 작품 검색"""
        query = f"""
        SELECT ?artwork ?artworkLabel ?artworkLabel_ko
               ?creator ?creatorLabel ?inception ?image
               ?collectionLabel ?materialLabel
        WHERE {{
          ?artwork wdt:P31 wd:Q3305213 .
          ?artwork wdt:P195 wd:{collection_id} .
          ?artwork wdt:P170 wd:{creator_id} .
          OPTIONAL {{ ?artwork wdt:P571 ?inception . }}
          OPTIONAL {{ ?artwork wdt:P18 ?image . }}
          OPTIONAL {{ ?artwork wdt:P186 ?material . }}
          BIND(wd:{collection_id} AS ?collection)
          BIND(wd:{creator_id} AS ?creator)
          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en" .
            ?artwork rdfs:label ?artworkLabel .
            ?creator rdfs:label ?creatorLabel .
            ?collection rdfs:label ?collectionLabel .
            ?material rdfs:label ?materialLabel .
          }}
          OPTIONAL {{
            ?artwork rdfs:label ?artworkLabel_ko .
            FILTER(LANG(?artworkLabel_ko) = "ko")
          }}
        }}
        LIMIT {limit}
        """

        self.logger.info(
            f"Searching artworks by collection={collection_id}, creator={creator_id} (limit={limit})"
        )
        bindings = self._execute_sparql(query)
        results = self._parse_sparql_results(bindings)
        self.logger.info(
            f"Found {len(results)} artworks for collection={collection_id}, creator={creator_id}"
        )
        return results
