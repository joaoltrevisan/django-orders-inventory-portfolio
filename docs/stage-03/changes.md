# Stage 3: file inventory

Paths are relative to the repository root. Local source archives, full issue reports, credentials and intermediate check artifacts are intentionally excluded.

## Created files

- `accounts/authentication.py`
- `accounts/permissions.py`
- `accounts/serializers.py`
- `accounts/services.py`
- `accounts/urls.py`
- `accounts/views.py`
- `catalog/serializers.py`
- `catalog/services.py`
- `catalog/views.py`
- `common/api.py`
- `common/apps.py`
- `common/schema.py`
- `common/serializers.py`
- `docs/stage-03/api.md`
- `docs/stage-03/changes.md`
- `docs/stage-03/import.md`
- `docs/stage-03/review.md`
- `docs/stage-03/verification.md`
- `olist/importer.py`
- `olist/management/__init__.py`
- `olist/management/commands/__init__.py`
- `olist/management/commands/import_olist.py`
- `olist/serializers.py`
- `olist/source-manifest.json`
- `olist/views.py`
- `reports/stage-03/checks.json`
- `reports/stage-03/database.json`
- `reports/stage-03/dry-run.json`
- `reports/stage-03/final-noop-command.json`
- `reports/stage-03/final-noop.json`
- `reports/stage-03/full-import.json`
- `reports/stage-03/http.json`
- `reports/stage-03/import-commands.json`
- `reports/stage-03/openapi-verification.json`
- `reports/stage-03/openapi.json`
- `reports/stage-03/runtime.json`
- `reports/stage-03/schema-verification.json`
- `reports/stage-03/verified-noop.json`
- `tests/olist_fixture.py`
- `tests/test_importer.py`
- `tests/test_stage3_api.py`

## Changed existing files

- `README.md`
- `compose.yaml`
- `config/settings/base.py`
- `config/settings/test.py`
- `config/urls.py`
- `config/views.py`
- `docs/olist/adaptation-plan.md`
- `docs/olist/data-dictionary.md`
- `docs/olist/data-model.md`

Models, migration definitions, the locked dependency versions, and the SQL schema export required no changes. Their consistency was rechecked against PostgreSQL.
