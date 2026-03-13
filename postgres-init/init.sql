-- This file runs on first DB initialization
-- Tables are created by SQLAlchemy on app startup,
-- but you can add any custom extensions or roles here.

CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- useful for fuzzy search later
