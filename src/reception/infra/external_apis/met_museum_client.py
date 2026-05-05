from __future__ import annotations

from typing import Any

from src.reception.application.ports import IMetMuseumPort

from .base_client import BaseApiClient


class MetMuseumClient(BaseApiClient, IMetMuseumPort):
    def __init__(self):
        super().__init__(
            base_url="https://collectionapi.metmuseum.org/public/collection/v1",
            api_name="MetMuseum",
            rate_limit_delay=0.1,
        )

    def search_artworks(self, query: str, limit: int = 10, has_images: bool = True) -> list[int]:
        params = {"q": query, "hasImages": str(has_images).lower()}

        response = self._make_request("/search", params=params)
        object_ids = response.get("objectIDs", []) or []
        return object_ids[:limit]

    def get_artwork(self, object_id: int) -> dict[str, Any] | None:
        try:
            response = self._make_request(f"/objects/{object_id}")

            return {
                "source_id": str(object_id),
                "title": response.get("title", ""),
                "artist_display_name": response.get("artistDisplayName", ""),
                "artist_wikidata_url": response.get("artistWikidata_URL", ""),
                "object_date": response.get("objectDate", ""),
                "object_begin_date": response.get("objectBeginDate"),
                "object_end_date": response.get("objectEndDate"),
                "medium": response.get("medium", ""),
                "dimensions": response.get("dimensions", ""),
                "classification": response.get("classification", ""),
                "department": response.get("department", ""),
                "culture": response.get("culture", ""),
                "period": response.get("period", ""),
                "is_public_domain": response.get("isPublicDomain", False),
                "primary_image": response.get("primaryImage", ""),
                "primary_image_small": response.get("primaryImageSmall", ""),
                "additional_images": response.get("additionalImages", []),
                "credit_line": response.get("creditLine", ""),
                "repository": response.get("repository", ""),
                "object_url": response.get("objectURL", ""),
                "tags": response.get("tags", []),
            }
        except Exception as e:
            self.logger.warning(f"Failed to fetch artwork {object_id}: {str(e)}")
            return None

    def get_departments(self) -> list[dict[str, Any]]:
        response = self._make_request("/departments")
        return response.get("departments", [])

    def get_objects_by_department(self, department_id: int) -> list[int]:
        params = {"departmentIds": department_id}
        response = self._make_request("/objects", params=params)
        object_ids = response.get("objectIDs", [])
        return object_ids if object_ids else []
