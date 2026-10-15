# Dependency Inventory

Generated: 2026-10-15 15:30:34 UTC

## Declared Runtime Dependencies

- `PySide6>=6.6.0`
- `SQLAlchemy>=2.0.25`
- `alembic>=1.13.0`
- `pydantic>=2.6.0`
- `httpx>=0.27.0`
- `fastapi>=0.110.0`
- `uvicorn>=0.29.0`
- `numpy>=1.26.0`
- `scipy>=1.12.0`
- `pandas>=2.2.0`
- `statsmodels>=0.14.0`
- `PyMuPDF>=1.24.0`
- `matplotlib>=3.8.0`
- `tomli-w>=1.0.0`

## Declared Development Dependencies

- `pytest>=8.0.0`
- `pytest-cov>=5.0.0`
- `pytest-qt>=4.4.0`
- `ruff>=0.4.0`
- `mypy>=1.9.0`

## Detected Third-Party Imports

| Import name | Occurrences |
| --- | --- |
| `PySide6` | 141 |
| `sqlalchemy` | 114 |
| `pydantic` | 24 |
| `alembic` | 4 |
| `fitz` | 3 |
| `pytesseract` | 2 |
| `PIL` | 1 |
| `httpx` | 1 |
| `tomli_w` | 1 |

## Policy

Every detected third-party import must correspond to a declared dependency. Additions require a documented purpose in `docs/architecture.md` and, where relevant, a license review entry.
