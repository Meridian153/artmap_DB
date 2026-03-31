from typing import Any

from src.reception.application.ports import IArtInstituteChicagoPort

from .base_client import BaseApiClient


class ArtInstituteChicagoClient(BaseApiClient, IArtInstituteChicagoPort):
    def __init__(self):
        super().__init__(
            base_url="https://api.artic.edu/api/v1",
            api_name="ArtInstituteChicago",
            rate_limit_delay=0.1,
        )

    def search_artworks(self, query: str, limit: int = 10, page: int = 1) -> list[dict[str, Any]]:
        params = {
            "q": query,
            "limit": limit,
            "page": page,
            "fields": "id,title,artist_display,date_display,medium_display,dimensions,"
            "image_id,thumbnail,is_public_domain,artwork_type_title,"
            "place_of_origin,credit_line,department_title",
        }

        response = self._make_request("/artworks/search", params=params)
        return response.get("data", [])

    def get_artwork(self, artwork_id: int) -> dict[str, Any] | None:
        try:
            response = self._make_request(f"/artworks/{artwork_id}")
            data = response.get("data", {})
            config = response.get("config", {})

            image_id = data.get("image_id")
            image_url = None
            if image_id and config.get("iiif_url"):
                iiif_url = config["iiif_url"]
                image_url = f"{iiif_url}/{image_id}/full/843,/0/default.jpg"

            return {
                "source_id": str(artwork_id),
                "title": data.get("title", ""),
                "artist_display": data.get("artist_display", ""),
                "date_display": data.get("date_display", ""),
                "date_start": data.get("date_start"),
                "date_end": data.get("date_end"),
                "medium_display": data.get("medium_display", ""),
                "dimensions": data.get("dimensions", ""),
                "artwork_type_title": data.get("artwork_type_title", ""),
                "department_title": data.get("department_title", ""),
                "place_of_origin": data.get("place_of_origin", ""),
                "credit_line": data.get("credit_line", ""),
                "is_public_domain": data.get("is_public_domain", False),
                "image_id": image_id,
                "image_url": image_url,
                "thumbnail": data.get("thumbnail", {}),
                "color": data.get("color", {}),
                "classification_titles": data.get("classification_titles", []),
                "style_titles": data.get("style_titles", []),
                "subject_titles": data.get("subject_titles", []),
                "material_titles": data.get("material_titles", []),
            }
        except Exception as e:
            self.logger.warning(f"Failed to fetch artwork {artwork_id}: {str(e)}")
            return None

    def get_artists(self, limit: int = 10, page: int = 1) -> dict[str, Any]:
        params = {
            "limit": limit,
            "page": page,
            "fields": "id,title,birth_date,death_date,description",
        }

        response = self._make_request("/artists", params=params)
        return {"data": response.get("data", []), "pagination": response.get("pagination", {})}

    def get_artist(self, artist_id: int) -> dict[str, Any] | None:
        try:
            response = self._make_request(f"/artists/{artist_id}")
            return response.get("data", {})
        except Exception as e:
            self.logger.warning(f"Failed to fetch artist {artist_id}: {str(e)}")
            return None
