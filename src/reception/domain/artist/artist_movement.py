import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared_kernel.domain.base_entity import Base


class ArtistMovement(Base):
    """Artist ↔ ArtMovement 다대다 연관 테이블"""

    __tablename__ = "artist_movements"

    artist_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("artists.id"), primary_key=True
    )
    movement_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("art_movements.id"), primary_key=True
    )
