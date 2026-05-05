import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.reception.domain.artwork.exceptions import (
    ArtworkAlreadyPublishedException,
    InvalidArtworkStatusTransitionException,
)
from src.shared_kernel.domain.base_entity import BaseEntity
from src.shared_kernel.domain.enums import ArtworkStatus


class Artwork(BaseEntity):
    """
    Artwork Aggregate Root
    작품 도메인의 핵심 엔티티로 작품의 생명주기와 비즈니스 규칙을 관리
    """

    __tablename__ = "artworks"
    __table_args__ = (UniqueConstraint("source_api", "source_id", name="uq_artwork_source"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title_en: Mapped[str] = mapped_column(String)
    title_ko: Mapped[str] = mapped_column(String)
    year_created: Mapped[int] = mapped_column(Integer)
    year_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    medium_en: Mapped[str] = mapped_column(String)
    medium_ko: Mapped[str] = mapped_column(String)
    dimensions: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    image_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default=ArtworkStatus.IN_STORAGE.value)
    curation_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    curation_ko: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_api: Mapped[str] = mapped_column(String)
    source_id: Mapped[str] = mapped_column(String)
    is_public_domain: Mapped[bool] = mapped_column(Boolean, default=False)

    @classmethod
    def create_from_external_source(
        cls,
        source_api: str,
        source_id: str,
        title_en: str,
        title_ko: str,
        year_created: int,
        medium_en: str,
        medium_ko: str,
        **kwargs,
    ) -> "Artwork":
        """외부 API로부터 작품 생성 (Factory Method)"""
        return cls(
            id=uuid.uuid4(),
            source_api=source_api,
            source_id=source_id,
            title_en=title_en,
            title_ko=title_ko,
            year_created=year_created,
            medium_en=medium_en,
            medium_ko=medium_ko,
            status=ArtworkStatus.IN_STORAGE.value,
            **kwargs,
        )

    def publish_to_display(self) -> None:
        """작품을 전시 상태로 변경 (비즈니스 로직)"""
        if self.status == ArtworkStatus.ON_DISPLAY:
            raise ArtworkAlreadyPublishedException(str(self.id))

        if self.status == ArtworkStatus.UNDER_RESTORATION:
            raise InvalidArtworkStatusTransitionException(
                self.status, ArtworkStatus.ON_DISPLAY.value
            )

        self.status = ArtworkStatus.ON_DISPLAY.value
        self.updated_at = datetime.now()

    def move_to_storage(self) -> None:
        """작품을 보관 상태로 변경"""
        if self.status == ArtworkStatus.UNDER_RESTORATION:
            raise InvalidArtworkStatusTransitionException(
                self.status, ArtworkStatus.IN_STORAGE.value
            )

        self.status = ArtworkStatus.IN_STORAGE.value
        self.updated_at = datetime.now()

    def start_restoration(self) -> None:
        """작품 복원 시작"""
        if self.status == ArtworkStatus.ON_LOAN:
            raise InvalidArtworkStatusTransitionException(
                self.status, ArtworkStatus.UNDER_RESTORATION.value
            )

        self.status = ArtworkStatus.UNDER_RESTORATION.value
        self.updated_at = datetime.now()

    def complete_restoration(self) -> None:
        """작품 복원 완료"""
        if self.status != ArtworkStatus.UNDER_RESTORATION:
            raise InvalidArtworkStatusTransitionException(
                self.status, ArtworkStatus.IN_STORAGE.value
            )

        self.status = ArtworkStatus.IN_STORAGE.value
        self.updated_at = datetime.now()

    def loan_out(self) -> None:
        """작품 대여"""
        if self.status not in [ArtworkStatus.IN_STORAGE, ArtworkStatus.ON_DISPLAY]:
            raise InvalidArtworkStatusTransitionException(self.status, ArtworkStatus.ON_LOAN.value)

        self.status = ArtworkStatus.ON_LOAN.value
        self.updated_at = datetime.now()

    def is_available_for_display(self) -> bool:
        """전시 가능 여부 확인"""
        return self.status in [ArtworkStatus.IN_STORAGE, ArtworkStatus.ON_DISPLAY]

    def update_curation(self, curation_en: Optional[str], curation_ko: Optional[str]) -> None:
        """큐레이션 정보 업데이트"""
        if curation_en:
            self.curation_en = curation_en
        if curation_ko:
            self.curation_ko = curation_ko
        self.updated_at = datetime.now()
