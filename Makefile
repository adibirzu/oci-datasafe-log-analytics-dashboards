PYTHON ?= python3

.PHONY: format lint test verify dashboard-bundle orm-package terraform-validate preflight e2e

format:
	$(PYTHON) -m ruff format src scripts tests function

lint:
	$(PYTHON) -m ruff check src scripts tests function

test:
	PYTHONPATH=src $(PYTHON) -m pytest

dashboard-bundle:
	$(PYTHON) scripts/build_dashboard_bundle.py

orm-package:
	$(PYTHON) scripts/build_orm_package.py

terraform-validate:
	terraform -chdir=terraform init -backend=false
	terraform -chdir=terraform validate

verify: lint test dashboard-bundle orm-package terraform-validate

preflight:
	PYTHONPATH=src $(PYTHON) scripts/preflight.py \
		--profile "$${OCI_PROFILE:-cap}" \
		--data-safe-compartment-id "$${DATA_SAFE_COMPARTMENT_ID:?set DATA_SAFE_COMPARTMENT_ID}" \
		--solution-compartment-id "$${SOLUTION_COMPARTMENT_ID:?set SOLUTION_COMPARTMENT_ID}"

e2e:
	PYTHONPATH=src $(PYTHON) scripts/e2e.py \
		--profile "$${OCI_PROFILE:-cap}" \
		--compartment-id "$${SOLUTION_COMPARTMENT_ID:?set SOLUTION_COMPARTMENT_ID}"
