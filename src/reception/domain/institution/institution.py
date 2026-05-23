import uuid
from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared_kernel.domain.base_entity import BaseEntity
from src.shared_kernel.domain.enums import InstitutionType


class Institution(BaseEntity):
    """기관(소유주) Aggregate Root"""

    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_type: Mapped[str] = mapped_column(String)
    country_code: Mapped[str] = mapped_column(String)
    name_en: Mapped[str] = mapped_column(String)
    name_ko: Mapped[str] = mapped_column(String)
    website: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_ko: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wikidata_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    @classmethod
    def create(
        cls,
        institution_type: InstitutionType,
        country_code: str,
        name_en: str,
        name_ko: str,
        website: Optional[str] = None,
        description_en: Optional[str] = None,
        description_ko: Optional[str] = None,
        wikidata_id: Optional[str] = None,
    ) -> "Institution":
        return cls(
            id=uuid.uuid4(),
            institution_type=institution_type.value,
            country_code=country_code,
            name_en=name_en,
            name_ko=name_ko,
            website=website,
            description_en=description_en,
            description_ko=description_ko,
            wikidata_id=wikidata_id,
        )
