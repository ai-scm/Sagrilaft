-- P20-C inventory-only PostgreSQL principal.
-- Run manually against the approved P20 clone only, after separate approval.
-- Supply the password interactively with psql's \password command; do not put
-- it in shell history, this file, or evidence.
\set ON_ERROR_STOP on

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'p20_c_inventory') THEN
    RAISE EXCEPTION 'Role p20_c_inventory already exists; reconcile it before proceeding';
  END IF;
  CREATE ROLE p20_c_inventory
    LOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    NOBYPASSRLS
    NOINHERIT;
END
$$;

\password p20_c_inventory

ALTER ROLE p20_c_inventory SET default_transaction_read_only = on;
GRANT CONNECT ON DATABASE sagrilaft TO p20_c_inventory;
GRANT USAGE ON SCHEMA public TO p20_c_inventory;
GRANT SELECT (version_num) ON TABLE public.alembic_version TO p20_c_inventory;
GRANT SELECT (version_num) ON TABLE public.p20_b_alembic_version TO p20_c_inventory;
GRANT SELECT (id, razon_social, ciudad, estado, p20_b_probe)
  ON TABLE public.formularios TO p20_c_inventory;

-- No table ownership, role membership, DML, sequence, schema CREATE, or
-- default privileges are granted. Column-level grants prevent this inventory
-- from reading unrelated form fields. The task enforces read-only transactions
-- and verifies current_user before inventory queries.
