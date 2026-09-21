# Backend

## Prerequisites

- Python 3.14+ (see [Python Version](#python-version))
- `uv` installed at user/system level (not inside project venv)
- `backend/.env` file (copy from `backend/.env.example`)

## Python Version

This project requires Python 3.14+. To ensure you're using the correct version:

### Using pyenv (Recommended)

```bash
# Install pyenv (if not already installed)
curl https://pyenv.run | bash

# Install Python 3.14
pyenv install

# Verify
python --version  # Should show 3.14.x
```

### Manual installation

Download Python 3.14 from [python.org](https://www.python.org/downloads/)

## Setup

⚠️ Run all commands from the `backend/` folder.

### 1. Create virtual environment

```bash
uv venv
```

### 2. Activate virtual environment

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
uv sync --extra dev
```

## Environment Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Update `.env` with your local configuration.

## Run

### Production mode

```bash
python -m app.main
```

### Development mode (with auto-reload)

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

**API Documentation:**

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Deactivate Virtual Environment

When done working:

```bash
deactivate
```

## Troubleshooting

**Python version mismatch:**

- Ensure you have Python 3.14+ installed
- Check: `python --version`
- Use pyenv to install the correct version (see [Python Version](#python-version))

**uv not found:**

- Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Or: `pip install uv`

**Module not found errors:**

- Make sure venv is activated (you should see `(.venv)` in your terminal)
- Run `uv sync --extra dev` again
