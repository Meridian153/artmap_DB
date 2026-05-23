import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared_kernel.domain.base_entity import BaseEntity


class Place(BaseEntity):
    """전시 장소(건물/거점) Entity — Institution Aggregate 소속"""

    __tablename__ = "places"
    __table_args__ = (Index("ix_places_lat_lng", "latitude", "longitude"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=True
    )
    name_en: Mapped[str] = mapped_column(String)
    name_ko: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    opening_hours: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    admission: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    @classmethod
    def create(
        cls,
        name_en: str,
        name_ko: str,
        country: str,
        city: str,
        institution_id: Optional[uuid.UUID] = None,
        address: Optional[str] = None,
        latitude: Optional[Decimal] = None,
        longitude: Optional[Decimal] = None,
        opening_hours: Optional[dict] = None,
        admission: Optional[dict] = None,
    ) -> "Place":
        return cls(
            id=uuid.uuid4(),
            institution_id=institution_id,
            name_en=name_en,
            name_ko=name_ko,
            country=country,
            city=city,
            address=address,
            latitude=latitude,
            longitude=longitude,
            opening_hours=opening_hours,
            admission=admission,
        )
