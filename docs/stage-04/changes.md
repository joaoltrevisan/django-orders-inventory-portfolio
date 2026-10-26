# Stage 4: file inventory

Paths are relative to the repository root. Downloaded source data, private credentials, complete local issue reports, and intermediate evidence are excluded.

## Created files

- `catalog/locking.py`
- `common/exceptions.py`
- `common/validation.py`
- `docs/stage-04/api.md`
- `docs/stage-04/changes.md`
- `docs/stage-04/review.md`
- `docs/stage-04/rules.md`
- `docs/stage-04/verification.md`
- `inventory/serializers.py`
- `inventory/services.py`
- `inventory/urls.py`
- `inventory/views.py`
- `orders/exceptions.py`
- `orders/integrity.py`
- `orders/lifecycle.py`
- `orders/selectors.py`
- `orders/serializers.py`
- `orders/services.py`
- `orders/urls.py`
- `orders/validation.py`
- `orders/views.py`
- `reports/stage-04/checks.json`
- `reports/stage-04/concurrency.json`
- `reports/stage-04/database.json`
- `reports/stage-04/historical-preservation-command.json`
- `reports/stage-04/historical-preservation.json`
- `reports/stage-04/http.json`
- `reports/stage-04/openapi-verification.json`
- `reports/stage-04/openapi.json`
- `reports/stage-04/runtime.json`
- `reports/stage-04/schema-verification.json`
- `tests/controlled_concurrency.py`
- `tests/operational_fixture.py`
- `tests/test_operational_api.py`
- `tests/test_operational_concurrency.py`
- `tests/test_operational_services.py`

## Changed existing files

- `README.md`
- `accounts/permissions.py`
- `common/serializers.py`
- `compose.yaml`
- `config/settings/base.py`
- `config/urls.py`
- `config/views.py`
- `docs/olist/data-model.md`
- `tests/test_environment.py`

No model, migration, dependency-pin or SQL-export changes were required. The pre-existing unimplemented-route check now uses another absent route because `/api/orders/` is implemented and independently tested for access control.
