-- ArtMap Database Initialization Script
-- This script runs automatically when the PostgreSQL container starts for the first time

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE artmap TO postgres;

-- You can add initial seed data here if needed
