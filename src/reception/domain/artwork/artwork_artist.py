import uuid

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared_kernel.domain.base_entity import Base


class ArtworkArtist(Base):
    """Artwork ↔ Artist 다대다 연관 테이블"""

    __tablename__ = "artwork_artists"
    __table_args__ = (Index("ix_artwork_artists_artist_id", "artist_id"),)

    artwork_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("artworks.id"), primary_key=True
    )
    artist_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("artists.id"), primary_key=True
    )
