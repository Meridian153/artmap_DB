from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BaseEntity(Base):
    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
