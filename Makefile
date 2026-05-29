pytest_args=

run_e2e_tests:
	uv run pytest -v --tb=native -p no:logging $(pytest_args) agent/tests
	uv run pytest -v --tb=native -p no:logging $(pytest_args) server/tests
	uv run pytest -v --tb=native -p no:logging $(pytest_args) e2e_tests
