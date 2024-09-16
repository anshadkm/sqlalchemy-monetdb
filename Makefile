venv/:
	python3 -m venv venv
	venv/bin/pip install --upgrade pip wheel setuptools

venv/bin/pytest: venv/
	venv/bin/pip install -e ".[test]"

pytest: venv/bin/pytest
	venv/bin/pytest -r A
