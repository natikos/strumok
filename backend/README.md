# Backend

## Prerequisites

- Python 3.14+
- `uv` installed at user/system level (not inside project venv)
- `backend/.env` file (copy from `backend/.env.example`)

## Setup

⚠️ Run these commands from the `backend/` folder.

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
```

## Run

```bash
python -m app.main
```

or dev mode:

```bash
uvicorn app.main:app --reload
```
