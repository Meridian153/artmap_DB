import uuid

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared_kernel.domain.base_entity import Base


class ArtMovement(Base):
    """미술 사조 Aggregate Root"""

    __tablename__ = "art_movements"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name_en: Mapped[str] = mapped_column(String)
    name_ko: Mapped[str] = mapped_column(String)
    period_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    @classmethod
    def create(
        cls,
        name_en: str,
        name_ko: str,
        period_start: int | None = None,
        period_end: int | None = None,
        description: str | None = None,
    ) -> "ArtMovement":
        return cls(
            id=uuid.uuid4(),
            name_en=name_en,
            name_ko=name_ko,
            period_start=period_start,
            period_end=period_end,
            description=description,
        )
