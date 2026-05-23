import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared_kernel.domain.base_entity import Base
from src.shared_kernel.domain.enums import LocationType


class ArtworkLocation(Base):
    """작품 위치 이력 Entity — Artwork Aggregate 소속"""

    __tablename__ = "artwork_locations"
    __table_args__ = (Index("ix_artwork_locations_place_id", "place_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artwork_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("artworks.id"), nullable=False
    )
    place_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("places.id"), nullable=False
    )
    location_type: Mapped[str] = mapped_column(String)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @classmethod
    def create(
        cls,
        artwork_id: uuid.UUID,
        place_id: uuid.UUID,
        location_type: LocationType,
        start_date: date,
        end_date: Optional[date] = None,
        source: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> "ArtworkLocation":
        return cls(
            id=uuid.uuid4(),
            artwork_id=artwork_id,
            place_id=place_id,
            location_type=location_type.value,
            start_date=start_date,
            end_date=end_date,
            source=source,
            notes=notes,
        )
