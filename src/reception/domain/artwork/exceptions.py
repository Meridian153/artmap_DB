class ArtworkDomainException(Exception):
    """작품 도메인 예외 기본 클래스"""

    pass


class ArtworkAlreadyPublishedException(ArtworkDomainException):
    def __init__(self, artwork_id: str):
        self.artwork_id = artwork_id
        super().__init__(f"Artwork {artwork_id} is already published")


class InvalidArtworkStatusTransitionException(ArtworkDomainException):
    def __init__(self, current_status: str, target_status: str):
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(f"Cannot transition from {current_status} to {target_status}")


class ArtworkNotFoundException(ArtworkDomainException):
    def __init__(self, artwork_id: str):
        self.artwork_id = artwork_id
        super().__init__(f"Artwork not found: {artwork_id}")


class DuplicateArtworkException(ArtworkDomainException):
    def __init__(self, source_api: str, source_id: str):
        self.source_api = source_api
        self.source_id = source_id
        super().__init__(f"Artwork already exists from {source_api}: {source_id}")
