"""Screenshot capture for visual verification.

Launches the application in an offscreen-capable configuration, navigates
to every primary destination, and writes a PNG per destination into the
specified output directory. Also writes a machine-readable manifest that
records the destination, the object name of the page, and the file path.

The script is deterministic: given the same application state, it produces
the same set of files with stable names. It never modifies the user's
data directory; it uses a temporary directory unless one is supplied.

Usage
-----
    python scripts/capture_screenshots.py
    python scripts/capture_screenshots.py --output docs/screenshots/phase_a
    python scripts/capture_screenshots.py --offscreen

The ``--offscreen`` flag forces the Qt offscreen platform plugin, which is
suitable for CI where no display is available.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

DEFAULT_OUTPUT = REPO_ROOT / "docs" / "screenshots" / "phase_a"

MANIFEST_FILENAME = "manifest.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="capture_screenshots",
        description="Capture a screenshot of every primary destination.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Directory to write PNG files and the manifest. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--offscreen",
        action="store_true",
        help="Force the Qt offscreen platform plugin.",
    )
    parser.add_argument(
        "--size",
        type=str,
        default="1280x800",
        help="Window size in WIDTHxHEIGHT form. Default: 1280x800.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output.",
    )
    return parser


def _parse_size(value: str) -> tuple[int, int]:
    parts = value.lower().split("x")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"Invalid size: {value!r}")
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid size: {value!r}") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError(f"Size must be positive: {value!r}")
    return width, height


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    width, height = _parse_size(args.size)

    if args.offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    # The application must not write into the user's real data directory
    # during capture. A temporary home is used unless one is already set.
    temporary_home = None
    if "ACADEMIC_PLATFORM_HOME" not in os.environ:
        temporary_home = tempfile.TemporaryDirectory(prefix="academic_platform_capture_")
        os.environ["ACADEMIC_PLATFORM_HOME"] = temporary_home.name

    try:
        exit_code = _run_capture(args, width, height)
    finally:
        if temporary_home is not None:
            temporary_home.cleanup()

    return exit_code


def _run_capture(args: argparse.Namespace, width: int, height: int) -> int:
    from PySide6.QtCore import QCoreApplication, Qt
    from PySide6.QtWidgets import QApplication

    from academic_platform.app.configuration import load_runtime_directories
    from academic_platform.app.logging_setup import configure_logging
    from academic_platform.app.settings import SettingsService
    from academic_platform.ui.main_window import MainWindow
    from academic_platform.ui.main_window_destinations import DESTINATIONS
    from academic_platform.ui.notifications import NotificationHost, NotificationService

    output_dir: Path = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    directories = load_runtime_directories()
    configure_logging(
        directories.logs_dir,
        level_override="WARNING",
        write_to_file=False,
    )

    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("Academic Research Platform")
    application.setOrganizationName("Academic Platform")

    settings_service = SettingsService(directories.config_file)
    settings_service.load()

    window = MainWindow(directories=directories, settings_service=settings_service)
    notification_service = NotificationService(max_size=5)
    window.attach_notification_service(notification_service)
    host = NotificationHost(parent=window, service=notification_service)
    host.container().hide()

    window.resize(width, height)
    window.show()
    QCoreApplication.processEvents()

    manifest_entries: list[dict[str, object]] = []
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()

    for destination in DESTINATIONS:
        window.navigate_to(destination.identifier)
        QCoreApplication.processEvents()
        page = window._pages[destination.identifier]  # noqa: SLF001 - capture tool
        filename = f"{destination.identifier}.png"
        target = output_dir / filename
        pixmap = window.grab()
        if not pixmap.save(str(target), "PNG"):
            print(f"Failed to write {target}", file=sys.stderr)
            return 1
        manifest_entries.append(
            {
                "destination": destination.identifier,
                "label": destination.label,
                "page_object_name": page.objectName(),
                "page_class": type(page).__name__,
                "file": filename,
            }
        )
        if not args.quiet:
            print(f"Captured {destination.identifier} -> {target}")

    manifest = {
        "generated_at": timestamp,
        "window_size": [width, height],
        "application_version": _application_version(),
        "entries": manifest_entries,
    }
    manifest_path = output_dir / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if not args.quiet:
        print(f"Manifest written to {manifest_path}")

    window.close()
    QCoreApplication.processEvents()
    return 0


def _application_version() -> str:
    from academic_platform import __version__

    return __version__


if __name__ == "__main__":
    raise SystemExit(main())