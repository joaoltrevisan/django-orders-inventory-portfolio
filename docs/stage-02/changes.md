# Stage 2: file inventory

All paths are relative to the repository root. Package initializer files and generated migrations are included. Local credentials, downloaded source data, caches, and private intermediate evidence are excluded.

## Created files

- `.dockerignore`
- `.env.example`
- `.python-version`
- `Dockerfile`
- `accounts/__init__.py`
- `accounts/managers.py`
- `accounts/migrations/0001_initial.py`
- `accounts/migrations/__init__.py`
- `accounts/models.py`
- `catalog/__init__.py`
- `catalog/migrations/0001_initial.py`
- `catalog/migrations/0002_offer_identity.py`
- `catalog/migrations/__init__.py`
- `catalog/models.py`
- `common/__init__.py`
- `common/fields.py`
- `common/limits.py`
- `common/management/__init__.py`
- `common/management/commands/__init__.py`
- `common/management/commands/configure_database_roles.py`
- `common/models.py`
- `compose.yaml`
- `config/__init__.py`
- `config/settings/__init__.py`
- `config/settings/base.py`
- `config/settings/development.py`
- `config/settings/test.py`
- `config/urls.py`
- `config/views.py`
- `docker/postgres/01-roles.sql`
- `docs/stage-02/changes.md`
- `docs/stage-02/database.md`
- `docs/stage-02/review.md`
- `docs/stage-02/setup.md`
- `docs/stage-02/verification.md`
- `inventory/__init__.py`
- `inventory/migrations/0001_initial.py`
- `inventory/migrations/__init__.py`
- `inventory/models.py`
- `manage.py`
- `olist/__init__.py`
- `olist/fields.py`
- `olist/migrations/0001_initial.py`
- `olist/migrations/__init__.py`
- `olist/models.py`
- `orders/__init__.py`
- `orders/migrations/0001_initial.py`
- `orders/migrations/__init__.py`
- `orders/models.py`
- `pyproject.toml`
- `reports/stage-02/checks.json`
- `reports/stage-02/database-roles.json`
- `reports/stage-02/runtime.json`
- `reports/stage-02/schema-verification.json`
- `requirements-dev.txt`
- `requirements.lock`
- `requirements.txt`
- `scripts/__init__.py`
- `scripts/create_env.py`
- `scripts/database_schema.py`
- `scripts/runtime_versions.py`
- `scripts/verify_database_roles.py`
- `scripts/verify_stage2.py`
- `sql/schema.sql`
- `tests/__init__.py`
- `tests/factories.py`
- `tests/test_environment.py`
- `tests/test_historical_models.py`
- `tests/test_simulated_models.py`
- `tests/test_verification_tools.py`

## Changed existing files

- `README.md`
- `docs/olist/data-model.md`
- `scripts/inspect_olist.py`

`scripts/inspect_olist.py` changed only to match the project formatting rules; its source inspection behavior remains unchanged. The README also records the approved service presentation.
