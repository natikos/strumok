PYTHON ?= python3.14
VENV_PYTHON := backend/.venv/bin/python

.PHONY: install install-backend install-frontend dev

install: install-backend install-frontend

install-backend:
	$(PYTHON) -m venv backend/.venv
	$(VENV_PYTHON) -m pip install -r backend/requirements.txt

install-frontend:
	npm --prefix frontend install

dev:
	./scripts/dev.sh
