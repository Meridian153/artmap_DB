from sqlalchemy import Engine

from src.shared_kernel.infra.log.logger import setup_logger

logger = setup_logger("DatabaseInitializer")


class DatabaseInitializer:
    _initialized = False

    @classmethod
    def initialize(cls, engine: Engine):
        if cls._initialized:
            logger.info("Database already initialized, skipping...")
            return

        try:
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

            Base.metadata.create_all(bind=engine)
            logger.info("✓ All tables created successfully")
            cls._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise
