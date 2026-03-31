import uuid
from decimal import Decimal

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
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=True
    )
    name_en: Mapped[str] = mapped_column(String)
    name_ko: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    opening_hours: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    admission: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    @classmethod
    def create(
        cls,
        name_en: str,
        name_ko: str,
        country: str,
        city: str,
        institution_id: uuid.UUID | None = None,
        address: str | None = None,
        latitude: Decimal | None = None,
        longitude: Decimal | None = None,
        opening_hours: dict | None = None,
        admission: dict | None = None,
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
