# Migrations

Hand-written SQL, applied manually against the production database (no
Alembic, no runner yet -- see issue #140). `init_db()` only runs
`SQLModel.metadata.create_all()` in development, so these files are the only
way a schema change reaches production.

Files are numbered in the order they must be applied, `NNNN_description.sql`.
When adding one, also update the corresponding `SQLModel` field(s) in
`app/db/models.py` in the same change, so development/test databases (which
get the column via `create_all`) and production (which gets it via this file)
stay in sync.
