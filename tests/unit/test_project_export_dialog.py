"""Tests for the project export dialog."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QPushButton,
)

from academic_platform.application.project_export.model import (  # noqa: E402
    ExportFormat,
    ExportSection,
)
from academic_platform.application.project_export.service import (  # noqa: E402
    ProjectExportService,
)
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.database.models import ResearchProject  # noqa: E402
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.ui.dialogs.project_export_dialog import (  # noqa: E402
    ProjectExportDialog,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _ShimmedManager:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._sessions: list = []

    def get(self, key: str):
        session = self._database._session_factory()  # noqa: SLF001
        self._sessions.append(session)
        return _REPOSITORY_REGISTRY[key](session)

    def register_all(self, mapping) -> None:
        return None

    def close_all(self) -> None:
        for session in self._sessions:
            try:
                session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()
            finally:
                session.close()
        self._sessions.clear()


def _seed(database: Database) -> None:
    with database.session() as session:
        session.add(ResearchProject(key="study-1", title="Study One"))


def test_dialog_default_path_set(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = ProjectExportService(manager)  # type: ignore[arg-type]
    dialog = ProjectExportDialog(service, "study-1")
    path_input = dialog.findChild(QLineEdit, "projectExportPath")
    assert path_input is not None
    assert path_input.text().endswith(".json")
    dialog.close()
    manager.close_all()
    database.dispose()


def test_dialog_format_switch_updates_path(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = ProjectExportService(manager)  # type: ignore[arg-type]
    dialog = ProjectExportDialog(service, "study-1")
    combo = dialog.findChild(QComboBox, "projectExportFormat")
    assert combo is not None
    combo.setCurrentIndex(1)
    path_input = dialog.findChild(QLineEdit, "projectExportPath")
    assert path_input is not None
    assert path_input.text().endswith(".md")
    dialog.close()
    manager.close_all()
    database.dispose()


def test_dialog_sections_present(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = ProjectExportService(manager)  # type: ignore[arg-type]
    dialog = ProjectExportDialog(service, "study-1")
    for section in ExportSection:
        checkbox = dialog.findChild(
            QCheckBox, f"projectExportSection_{section.value}"
        )
        assert checkbox is not None, section.value
        assert checkbox.isChecked()
    dialog.close()
    manager.close_all()
    database.dispose()


def test_dialog_export_writes_file(app: QApplication, tmp_path: Path) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = ProjectExportService(manager)  # type: ignore[arg-type]
    dialog = ProjectExportDialog(service, "study-1")
    target = tmp_path / "out.json"
    path_input = dialog.findChild(QLineEdit, "projectExportPath")
    assert path_input is not None
    path_input.setText(str(target))
    received: list = []
    dialog.exported.connect(lambda result: received.append(result))
    export_button = dialog.findChild(QPushButton, "projectExportAccept")
    assert export_button is not None
    export_button.click()
    assert target.exists()
    assert len(received) == 1
    dialog.close()
    manager.close_all()
    database.dispose()


def test_dialog_export_requires_destination(app: QApplication) -> None:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    _seed(database)
    manager = _ShimmedManager(database)
    service = ProjectExportService(manager)  # type: ignore[arg-type]
    dialog = ProjectExportDialog(service, "study-1")
    path_input = dialog.findChild(QLineEdit, "projectExportPath")
    assert path_input is not None
    path_input.setText("")
    received: list = []
    dialog.exported.connect(lambda result: received.append(result))
    export_button = dialog.findChild(QPushButton, "projectExportAccept")
    assert export_button is not None
    export_button.click()
    assert not received
    dialog.close()
    manager.close_all()
    database.dispose()