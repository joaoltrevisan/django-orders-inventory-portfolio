-- Runs once, only on this project's new PostgreSQL volume.
-- psql quotes environment-derived passwords as literals, not SQL identifiers.
\getenv database POSTGRES_DB
\getenv owner_password MIGRATION_DB_PASSWORD
\getenv importer_password IMPORT_DB_PASSWORD
\getenv api_password APP_DB_PASSWORD
\getenv test_password TEST_DB_PASSWORD

CREATE ROLE olist_owner LOGIN PASSWORD :'owner_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE olist_importer LOGIN PASSWORD :'importer_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE olist_api LOGIN PASSWORD :'api_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
-- CREATEDB belongs only to the automated-test runner, never the API/importer.
CREATE ROLE olist_test LOGIN PASSWORD :'test_password' NOSUPERUSER CREATEDB NOCREATEROLE;
ALTER DATABASE :"database" OWNER TO olist_owner;
REVOKE ALL ON DATABASE :"database" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"database" TO olist_owner, olist_importer, olist_api, olist_test;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO olist_owner;
GRANT USAGE ON SCHEMA public TO olist_api, olist_importer;
