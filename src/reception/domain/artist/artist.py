import uuid
from datetime import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared_kernel.domain.base_entity import BaseEntity


class Artist(BaseEntity):
    """
    Artist Aggregate Root
    작가 도메인의 핵심 엔티티
    """

    __tablename__ = "artists"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name_en: Mapped[str] = mapped_column(String)
    name_ko: Mapped[str] = mapped_column(String)
    birth_year: Mapped[int] = mapped_column(Integer)
    death_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nationality: Mapped[str] = mapped_column(String)
    bio_en: Mapped[str] = mapped_column(Text, default="")
    bio_ko: Mapped[str] = mapped_column(Text, default="")
    thumbnail_url: Mapped[str] = mapped_column(String, default="")
    wikidata_id: Mapped[str | None] = mapped_column(String, nullable=True)

    @classmethod
    def create(
        cls,
        name_en: str,
        name_ko: str,
        birth_year: int,
        nationality: str,
        bio_en: str = "",
        bio_ko: str = "",
        death_year: int | None = None,
        thumbnail_url: str = "",
        wikidata_id: str | None = None,
    ) -> "Artist":
        """작가 생성 (Factory Method)"""
        return cls(
            id=uuid.uuid4(),
            name_en=name_en,
            name_ko=name_ko,
            birth_year=birth_year,
            death_year=death_year,
            nationality=nationality,
            bio_en=bio_en,
            bio_ko=bio_ko,
            thumbnail_url=thumbnail_url,
            wikidata_id=wikidata_id,
        )

    def update_biography(self, bio_en: str | None, bio_ko: str | None) -> None:
        """작가 약력 업데이트"""
        if bio_en:
            self.bio_en = bio_en
        if bio_ko:
            self.bio_ko = bio_ko
        self.updated_at = datetime.now()

    def mark_deceased(self, death_year: int) -> None:
        """작가 사망 연도 기록"""
        if death_year < self.birth_year:
            raise ValueError(
                f"Death year {death_year} cannot be before birth year {self.birth_year}"
            )

        self.death_year = death_year
        self.updated_at = datetime.now()

    def is_alive(self) -> bool:
        """생존 여부"""
        return self.death_year is None

    def get_age(self, current_year: int | None = None) -> int:
        """나이 계산"""
        if current_year is None:
            current_year = datetime.now().year

        end_year = self.death_year if self.death_year else current_year
        return end_year - self.birth_year
