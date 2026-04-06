-- init-databases.sql
-- Creates separate databases for n8n and Mautic inside the shared Postgres instance.
-- Runs automatically on first container start via docker-entrypoint-initdb.d.

CREATE DATABASE n8n;
CREATE DATABASE mautic;
