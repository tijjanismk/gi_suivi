-- Base de développement locale (poste du développeur), une fois.
-- Valeurs de .env.exemple et de la CI : compte gic / mot de passe gic, base gic.
-- CREATEDB : pytest-django crée et détruit sa base de test (test_gic) à chaque passage.
-- À lancer avec le super-utilisateur de l'installation PostgreSQL (le mot de passe est demandé) :
--   & 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -U postgres -h localhost -f scripts\dev\creer_base_dev.sql
-- Rejouable : ne recrée rien de ce qui existe.

SELECT 'CREATE ROLE gic LOGIN CREATEDB PASSWORD ''gic'''
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gic')\gexec

SELECT 'CREATE DATABASE gic OWNER gic ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'gic')\gexec

\echo 'Base de développement prête : postgres://gic:gic@localhost:5432/gic'
