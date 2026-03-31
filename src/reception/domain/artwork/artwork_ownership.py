import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared_kernel.domain.base_entity import Base


class ArtworkOwnership(Base):
    """작품 ↔ 기관 소유권 연관 테이블 (지분 + 주소유자 여부 포함)"""

    __tablename__ = "artwork_ownerships"

    artwork_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("artworks.id"), primary_key=True
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id"), primary_key=True
    )
    ownership_share: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    is_primary_owner: Mapped[bool] = mapped_column(Boolean, default=False)
