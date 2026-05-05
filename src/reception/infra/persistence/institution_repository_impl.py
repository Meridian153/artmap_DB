from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.reception.domain.institution.institution import Institution
from src.reception.domain.institution.repository import InstitutionRepository


class InstitutionRepositoryImpl(InstitutionRepository):
    """Institution Repository 구현체 (Infrastructure Layer)"""

    def __init__(self, session: Session):
        self._session = session

    def find_by_id(self, institution_id: UUID) -> Institution | None:
        return self._session.get(Institution, institution_id)

    def find_by_wikidata_id(self, wikidata_id: str) -> Institution | None:
        return self._session.execute(
            select(Institution).where(Institution.wikidata_id == wikidata_id)
        ).scalar_one_or_none()

    def save(self, institution: Institution) -> Institution:
        self._session.add(institution)
        self._session.flush()
        return institution

    def find_all(self, limit: int = 100, offset: int = 0) -> list[Institution]:
        return list(
            self._session.execute(select(Institution).limit(limit).offset(offset)).scalars().all()
        )

    def search_by_name(self, name: str, limit: int = 20) -> list[Institution]:
        return list(
            self._session.execute(
                select(Institution)
                .where(
                    Institution.name_en.ilike(f"%{name}%") | Institution.name_ko.ilike(f"%{name}%")
                )
                .limit(limit)
            )
            .scalars()
            .all()
        )
