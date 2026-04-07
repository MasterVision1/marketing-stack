-- init-databases.sql
-- Creates n8n database inside the Postgres instance.
-- Runs automatically on first container start via docker-entrypoint-initdb.d.

CREATE DATABASE n8n;
