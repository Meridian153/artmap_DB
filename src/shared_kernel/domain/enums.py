from enum import Enum


class ArtworkStatus(str, Enum):
    ON_DISPLAY = "on_display"
    IN_STORAGE = "in_storage"
    ON_LOAN = "on_loan"
    UNDER_RESTORATION = "under_restoration"


class LocationType(str, Enum):
    PERMANENT_COLLECTION = "permanent_collection"
    PERMANENT_EXHIBITION = "permanent_exhibition"
    TEMPORARY_EXHIBITION = "temporary_exhibition"
    ON_LOAN = "on_loan"
    STORAGE = "storage"
    TRANSIT = "transit"


class InstitutionType(str, Enum):
    MUSEUM = "museum"
    GALLERY = "gallery"
    PRIVATE_COLLECTION = "private_collection"
    FOUNDATION = "foundation"


class ExternalApiSource(str, Enum):
    WIKIDATA = "wikidata"
    MET_MUSEUM = "met_museum"
    ART_INSTITUTE_CHICAGO = "art_institute_chicago"
