# Backend

Minimal FastAPI backend for Strumok.

## Current tools

- Python 3.14
- Pydantic Settings
- Packaging/build: `pyproject.toml` + Hatchling

## Setup
⚠️ Make sure you have `.env` file in the root of the backend folder.

From project root:

```bash
# py is an alias for python3
py -m venv .venv --upgrade-deps # ensure you're in the backend folder
source .venv/bin/activate # activate .venv
pip install -e . # (.venv) must be activated in the terminal
```

# Useful commands
```bash
rm -rf backend/.venv # can be used for removing packages 
```