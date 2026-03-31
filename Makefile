.PHONY: help docker-up docker-down docker-restart db-init db-reset logs clean

help:
	@echo "ArtMap - Available Commands"
	@echo "============================"
	@echo "docker-up        : Start PostgreSQL database"
	@echo "docker-down      : Stop PostgreSQL database"
	@echo "docker-restart   : Restart PostgreSQL database"
	@echo "db-init          : Initialize database tables"
	@echo "db-reset         : Drop and recreate all tables"
	@echo "logs             : Show database logs"
	@echo "clean            : Remove all containers and volumes"

docker-up:
	@echo "🚀 Starting PostgreSQL database..."
	docker-compose up -d
	@echo "⏳ Waiting for database to be ready..."
	@sleep 3
	@echo "✅ Database is ready!"

docker-down:
	@echo "🛑 Stopping PostgreSQL database..."
	docker-compose down

docker-restart:
	@echo "🔄 Restarting PostgreSQL database..."
	docker-compose restart

db-init:
	@echo "📦 Initializing database tables..."
	python3 init_db.py
	@echo "✅ Database initialized!"

db-reset:
	@echo "⚠️  Resetting database (dropping all tables)..."
	python3 init_db.py --drop
	@echo "📦 Recreating tables..."
	python3 init_db.py
	@echo "✅ Database reset complete!"

logs:
	docker-compose logs -f postgres

clean:
	@echo "🧹 Cleaning up Docker containers and volumes..."
	docker-compose down -v
	@echo "✅ Cleanup complete!"
