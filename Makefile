python3=python3
venv_dir=venv

run_e2e_tests: $(venv_dir)/packages-installed
	$(venv_dir)/bin/python -m pytest -v --tb=native -p no:logging $(pytest_args) e2e_tests

$(venv_dir)/packages-installed:
	test -d $(venv_dir) || $(python3) -m venv $(venv_dir)
	$(venv_dir)/bin/pip install -U pip wheel
	$(venv_dir)/bin/pip install pytest
	$(venv_dir)/bin/pip install -e agent
	$(venv_dir)/bin/pip install -e server
	touch $@
