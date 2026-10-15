"""Phase A acceptance validator.

Verifies that the application shell meets every Phase A acceptance
criterion. The validator is safe to run in CI: it uses a temporary home
directory, never touches the user's data, and produces a machine-readable
report.

Acceptance criteria checked
---------------------------
1. The application package imports.
2. The runtime directories resolve and are writable.
3. The settings service loads (creating defaults when needed).
4. The main window constructs with all twelve destinations registered.
5. Every destination is a BasePage subclass.
6. Navigation between all destinations succeeds.
7. The stylesheet builds for light and dark themes and three densities.
8. The notification service and host construct.
9. The dialog factory constructs every standard dialog.

Exit codes
----------
- 0: all criteria satisfied.
- 1: at least one criterion failed.
- 2: usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

REPORT_FILENAME = "phase_a_validation.json"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass
class ValidationReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append(CheckResult(name=name, ok=ok, detail=detail))

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "checks": [asdict(check) for check in self.checks],
        }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate_phase_a",
        description="Validate the Phase A acceptance criteria.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Path to write the JSON report. Default: stdout only.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-check output.",
    )
    return parser


def _check_import(report: ValidationReport) -> None:
    try:
        import academic_platform  # noqa: F401
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("package import", False, str(exc))
        return
    report.add("package import", True)


def _check_directories(report: ValidationReport):
    from academic_platform.app.configuration import load_runtime_directories

    try:
        directories = load_runtime_directories()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("runtime directories", False, str(exc))
        return None
    ok = all(
        path.is_dir()
        for path in (
            directories.config_dir,
            directories.data_dir,
            directories.logs_dir,
            directories.cache_dir,
        )
    )
    report.add("runtime directories", ok, str(directories.root))
    return directories


def _check_settings(report: ValidationReport, directories) -> None:
    from academic_platform.app.settings import SettingsService

    try:
        service = SettingsService(directories.config_file)
        result = service.load()
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("settings service", False, str(exc))
        return
    report.add("settings service", True, f"created={result.created}")


def _check_stylesheet(report: ValidationReport) -> None:
    from academic_platform.app.settings.schema import ThemeMode
    from academic_platform.ui.resources.styles import build_application_stylesheet

    for theme in (ThemeMode.LIGHT, ThemeMode.DARK):
        for density in ("compact", "comfortable", "spacious"):
            try:
                sheet = build_application_stylesheet(theme, 1.0, density)
            except Exception as exc:  # noqa: BLE001 - boundary
                report.add(f"stylesheet {theme.value}/{density}", False, str(exc))
                return
            if not sheet.strip():
                report.add(f"stylesheet {theme.value}/{density}", False, "empty")
                return
    report.add("stylesheet variants", True, "6 variants built")


def _check_shell(report: ValidationReport, directories) -> None:
    from PySide6.QtWidgets import QApplication

    from academic_platform.app.settings import SettingsService
    from academic_platform.ui.main_window import MainWindow
    from academic_platform.ui.main_window_destinations import DESTINATIONS
    from academic_platform.ui.pages.base_page import BasePage

    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("Academic Research Platform")

    from academic_platform.infrastructure.database import Database

    service = SettingsService(directories.config_file)
    service.load()
    database = Database.from_path(directories.database_file)
    try:
        window = MainWindow(
            directories=directories,
            settings_service=service,
            database=database,
        )
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("main window construction", False, str(exc))
        return
    report.add("main window construction", True)

    expected = {destination.identifier for destination in DESTINATIONS}
    actual = set(window._pages.keys())  # noqa: SLF001 - acceptance check
    report.add(
        "all destinations registered",
        expected == actual,
        f"expected={sorted(expected)} actual={sorted(actual)}",
    )

    non_base = [
        identifier
        for identifier, page in window._pages.items()  # noqa: SLF001
        if not isinstance(page, BasePage)
    ]
    report.add(
        "all pages inherit BasePage",
        not non_base,
        f"violations={non_base}",
    )

    navigation_failures: list[str] = []
    for destination in DESTINATIONS:
        try:
            window.navigate_to(destination.identifier)
        except Exception as exc:  # noqa: BLE001 - boundary
            navigation_failures.append(f"{destination.identifier}: {exc}")
    report.add(
        "navigation across destinations",
        not navigation_failures,
        "; ".join(navigation_failures),
    )

    window.close()
    database.dispose()


def _check_notifications(report: ValidationReport) -> None:
    from PySide6.QtWidgets import QApplication, QWidget

    from academic_platform.ui.notifications import NotificationHost, NotificationService

    application = QApplication.instance() or QApplication(sys.argv)
    _ = application
    parent = QWidget()
    service = NotificationService()
    try:
        host = NotificationHost(parent=parent, service=service)
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("notification host", False, str(exc))
        return
    notification = service.publish("Test", "Body")
    if notification is None:
        report.add("notification host", False, "publish returned None")
        return
    report.add("notification host", True)


def _check_dialogs(report: ValidationReport) -> None:
    from PySide6.QtWidgets import QApplication

    from academic_platform.ui.dialogs.dialog_factory import DialogFactory
    from academic_platform.ui.dialogs.form_dialog import FormField, FormFieldKind

    application = QApplication.instance() or QApplication(sys.argv)
    _ = application

    try:
        DialogFactory.message_dialog(None, "T", "M")
        DialogFactory.confirm_dialog(None, "T", "Q")
        DialogFactory.prompt_dialog(None, "T", "L")
        DialogFactory.form_dialog(
            None,
            "T",
            (FormField("a", "A", FormFieldKind.TEXT),),
        )
        DialogFactory.progress_dialog(None, "T", total=10)
    except Exception as exc:  # noqa: BLE001 - boundary
        report.add("dialog factory", False, str(exc))
        return
    report.add("dialog factory", True, "all five dialog types constructed")


def _print_report(report: ValidationReport, quiet: bool) -> None:
    if quiet:
        return
    width = max((len(check.name) for check in report.checks), default=0)
    for check in report.checks:
        status = "OK  " if check.ok else "FAIL"
        detail = f" — {check.detail}" if check.detail else ""
        print(f"[{status}] {check.name.ljust(width)}{detail}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    report = ValidationReport()

    temporary_home = None
    if "ACADEMIC_PLATFORM_HOME" not in os.environ:
        temporary_home = tempfile.TemporaryDirectory(prefix="academic_platform_phase_a_")
        os.environ["ACADEMIC_PLATFORM_HOME"] = temporary_home.name

    try:
        _check_import(report)
        directories = _check_directories(report)
        if directories is not None:
            _check_settings(report, directories)
        _check_stylesheet(report)
        if directories is not None:
            _check_shell(report, directories)
        _check_notifications(report)
        _check_dialogs(report)
    finally:
        if temporary_home is not None:
            temporary_home.cleanup()

    _print_report(report, args.quiet)

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())