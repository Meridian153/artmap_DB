import src.reception.domain.art_movement.art_movement  # noqa: F401
import src.reception.domain.artist.artist  # noqa: F401
import src.reception.domain.artist.artist_movement  # noqa: F401
import src.reception.domain.artwork.artwork  # noqa: F401
import src.reception.domain.artwork.artwork_artist  # noqa: F401
import src.reception.domain.artwork.artwork_location  # noqa: F401
import src.reception.domain.artwork.artwork_ownership  # noqa: F401
import src.reception.domain.institution.institution  # noqa: F401
import src.reception.domain.institution.place  # noqa: F401
from src.shared_kernel.domain.base_entity import Base
from src.shared_kernel.infra.database.connection import engine, initialize_database


def create_tables():
    initialize_database()
    print("✓ 모든 테이블이 생성되었습니다.")


def drop_tables():
    Base.metadata.drop_all(bind=engine)
    print("✓ 모든 테이블이 삭제되었습니다.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        confirm = input("정말로 모든 테이블을 삭제하시겠습니까? (yes/no): ")
        if confirm.lower() == "yes":
            drop_tables()
        else:
            print("취소되었습니다.")
    else:
        create_tables()
