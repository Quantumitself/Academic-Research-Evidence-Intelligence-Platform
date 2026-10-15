"""Environment validation script.

Verifies that the interpreter version, required directories, and required
third-party packages are available. Returns a non-zero exit code and prints a
diagnostic report when the environment is not usable. This script is safe to
run before installing the package.
"""

from __future__ import annotations

import argparse
import importlib
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

MINIMUM_PYTHON = (3, 11)

REQUIRED_PACKAGES: tuple[tuple[str, str], ...] = (
    ("PySide6", "PySide6.QtWidgets"),
    ("SQLAlchemy", "sqlalchemy"),
    ("alembic", "alembic"),
    ("pydantic", "pydantic"),
    ("httpx", "httpx"),
    ("FastAPI", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("NumPy", "numpy"),
    ("SciPy", "scipy"),
    ("pandas", "pandas"),
    ("statsmodels", "statsmodels"),
    ("PyMuPDF", "fitz"),
    ("Matplotlib", "matplotlib"),
    ("tomli-w", "tomli_w"),
    ("pytest", "pytest"),
    ("pytest-qt", "pytestqt"),
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_DIRECTORIES = (
    REPO_ROOT / "src" / "academic_platform",
    REPO_ROOT / "docs",
    REPO_ROOT / "scripts",
    REPO_ROOT / "tests",
)


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _check_python() -> CheckResult:
    current = sys.version_info[:3]
    ok = current >= MINIMUM_PYTHON
    detail = f"Python {'.'.join(str(part) for part in current)} at {sys.executable}"
    if not ok:
        required = ".".join(str(part) for part in MINIMUM_PYTHON)
        detail += f" is below required minimum {required}"
    return CheckResult(name="Python version", ok=ok, detail=detail)


def _check_platform() -> CheckResult:
    system = platform.system()
    detail = f"{system} {platform.release()} ({platform.machine()})"
    return CheckResult(name="Platform", ok=True, detail=detail)


def _check_directories() -> CheckResult:
    missing = [str(path) for path in REQUIRED_DIRECTORIES if not path.is_dir()]
    ok = not missing
    detail = "all required directories present" if ok else f"missing: {', '.join(missing)}"
    return CheckResult(name="Repository layout", ok=ok, detail=detail)


def _check_package(display_name: str, module_name: str) -> CheckResult:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - report any import failure
        return CheckResult(name=display_name, ok=False, detail=f"import failed: {exc}")
    version = getattr(module, "__version__", "unknown")
    return CheckResult(name=display_name, ok=True, detail=f"imported, version {version}")


def _print_results(results: list[CheckResult]) -> None:
    width = max(len(result.name) for result in results)
    for result in results:
        status = "OK  " if result.ok else "FAIL"
        print(f"[{status}] {result.name.ljust(width)} : {result.detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the development environment.")
    parser.add_argument(
        "--skip-packages",
        action="store_true",
        help="Skip third-party package import checks.",
    )
    args = parser.parse_args(argv)

    results: list[CheckResult] = [
        _check_python(),
        _check_platform(),
        _check_directories(),
    ]

    if not args.skip_packages:
        for display_name, module_name in REQUIRED_PACKAGES:
            results.append(_check_package(display_name, module_name))

    _print_results(results)

    failures = [result for result in results if not result.ok]
    if failures:
        print(f"\n{len(failures)} check(s) failed.")
        return 1
    print("\nAll environment checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())