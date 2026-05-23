import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

_raw_url = os.getenv("DATABASE_URL")

if _raw_url:
    # DATABASE_URL이 설정된 경우 직접 사용 (Neon 등 외부 DB 지원)
    # postgresql:// → postgresql+psycopg2:// 로 드라이버 보정
    if _raw_url.startswith("postgresql://"):
        _raw_url = _raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    _DATABASE_URL = _raw_url
else:
    # 개별 환경변수로 URL 조합 — 모든 값은 .env에서만 읽음
    _required = {"DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"}
    _missing = [k for k in _required if not os.getenv(k)]
    if _missing:
        raise RuntimeError(
            f"DB 환경변수가 설정되지 않았습니다: {', '.join(sorted(_missing))}\n"
            f".env 파일을 생성하세요. (.env.example 참고)"
        )
    _DATABASE_URL = (
        f"postgresql+psycopg2://"
        f"{os.getenv('DB_USER')}:"
        f"{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:"
        f"{os.getenv('DB_PORT', '5432')}/"
        f"{os.getenv('DB_NAME')}"
    )
    _sslmode = os.getenv("DB_SSLMODE", "")
    if _sslmode:
        _DATABASE_URL += f"?sslmode={_sslmode}"

engine = create_engine(_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def initialize_database():
    from src.shared_kernel.infra.database.initializer import DatabaseInitializer

    DatabaseInitializer.initialize(engine)
