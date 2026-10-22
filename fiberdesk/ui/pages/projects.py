"""Projects and their lines: list, search, filter, add / edit / delete."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                               QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget)

from ...core.budget import format_splitters, parse_splitters
from ...core.defaults import FIBER_TYPES, WAVELENGTHS_NM, Defaults
from ...core.status import Status
from ...i18n import tr
from .. import icons
from ..context import AppContext
from ..widgets import (Card, Item, PageHeader, dspin, fit_columns, ispin, make_table, num_item,
                       status_item)
from ...storage.models import Line, Project

ALL = -1


def _button(text: str, icon_name: str | None = None, object_name: str = "") -> QPushButton:
    btn = QPushButton(text)
    if icon_name:
        btn.setIcon(icons.icon(icon_name, "#08321c" if object_name == "Primary" else "#ffffff", 16))
    if object_name:
        btn.setObjectName(object_name)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


class ProjectDialog(QDialog):
    def __init__(self, project: Project | None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("proj.edit") if project else tr("proj.new"))
        self.project = project or Project(None, "")
        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 16)
        form.setSpacing(10)
        self.name = QLineEdit(self.project.name)
        self.kind = QLineEdit(self.project.kind)
        self.region = QLineEdit(self.project.region)
        self.description = QPlainTextEdit(self.project.description)
        self.description.setFixedHeight(80)
        form.addRow(tr("proj.name"), self.name)
        form.addRow(tr("proj.kind"), self.kind)
        form.addRow(tr("proj.region"), self.region)
        form.addRow(tr("proj.description"), self.description)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.setMinimumWidth(420)

    def _accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, tr("common.invalid"), tr("common.required", field=tr("proj.name")))
            return
        self.project.name = self.name.text().strip()
        self.project.kind = self.kind.text().strip()
        self.project.region = self.region.text().strip()
        self.project.description = self.description.toPlainText().strip()
        self.accept()


class LineDialog(QDialog):
    def __init__(self, line: Line, projects: list[Project], defaults: Defaults,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("line.edit") if line.id else tr("line.new"))
        self.line = line
        self.defaults = defaults
        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 16)
        form.setSpacing(9)
        self.project = QComboBox()
        for p in projects:
            self.project.addItem(p.name, p.id)
        self.project.setCurrentIndex(max(0, self.project.findData(line.project_id)))
        self.name = QLineEdit(line.name)
        self.a_end = QLineEdit(line.a_end)
        self.b_end = QLineEdit(line.b_end)
        self.length = dspin(0.0, 200.0, line.length_km, 0.1, 2, tr("common.km"))
        self.fiber = QComboBox()
        self.fiber.addItems(FIBER_TYPES)
        self.fiber.setCurrentText(line.fiber_type)
        self.connectors = ispin(0, 60, line.connectors)
        self.splices = ispin(0, 200, line.splices)
        self.splitters = QLineEdit(line.splitters)
        self.splitters.setPlaceholderText(tr("line.splitters_hint"))
        self.wavelength = QComboBox()
        for wl in WAVELENGTHS_NM:
            self.wavelength.addItem(f"{wl} nm", wl)
        self.wavelength.setCurrentIndex(max(0, self.wavelength.findData(line.wavelength_nm)))
        self.tx = dspin(-20.0, 20.0, line.tx_power_dbm, 0.5, 1, tr("common.dbm"))
        self.rx = dspin(-45.0, 0.0, line.rx_sensitivity_dbm, 0.5, 1, tr("common.dbm"))
        self.notes = QPlainTextEdit(line.notes)
        self.notes.setFixedHeight(60)
        for label, widget in (
            ("line.project", self.project), ("line.name", self.name), ("line.a_end", self.a_end),
            ("line.b_end", self.b_end), ("line.length", self.length), ("line.fiber", self.fiber),
            ("line.connectors", self.connectors), ("line.splices", self.splices),
            ("line.splitters", self.splitters), ("line.wavelength", self.wavelength),
            ("line.tx", self.tx), ("line.rx", self.rx), ("line.notes", self.notes),
        ):
            form.addRow(tr(label), widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.setMinimumWidth(460)

    def _accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, tr("common.invalid"), tr("common.required", field=tr("line.name")))
            return
        try:
            ratios = parse_splitters(self.splitters.text())
            for r in ratios:
                self.defaults.splitter(r)
        except ValueError:
            QMessageBox.warning(self, tr("common.invalid"), tr("budget.bad_splitter"))
            return
        ln = self.line
        ln.project_id = self.project.currentData()
        ln.name = self.name.text().strip()
        ln.a_end = self.a_end.text().strip()
        ln.b_end = self.b_end.text().strip()
        ln.length_km = self.length.value()
        ln.fiber_type = self.fiber.currentText()
        ln.connectors = self.connectors.value()
        ln.splices = self.splices.value()
        ln.splitters = format_splitters(ratios)
        ln.wavelength_nm = self.wavelength.currentData()
        ln.tx_power_dbm = self.tx.value()
        ln.rx_sensitivity_dbm = self.rx.value()
        ln.notes = self.notes.toPlainText().strip()
        self.accept()


class ProjectsPage(QWidget):
    COLUMNS = ("col.name", "col.a_end", "col.b_end", "col.length", "col.fiber", "col.conn",
               "col.splices", "col.splitters", "col.wavelength", "col.budget", "col.remaining")

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._lines: list[Line] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(PageHeader(tr("proj.title"), tr("proj.subtitle")))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(14)

        # Project list
        left = Card(tr("proj.projects"))
        add_project = _button("", "plus")
        add_project.setToolTip(tr("proj.new"))
        add_project.clicked.connect(self.add_project)
        left.add_header_widget(add_project)
        self.project_list = QListWidget()
        self.project_list.setObjectName("RowList")
        self.project_list.currentItemChanged.connect(lambda *_: self._fill_lines())
        self.project_list.itemDoubleClicked.connect(lambda *_: self.edit_project())
        left.body.addWidget(self.project_list, 1)
        self.project_info = QLabel()
        self.project_info.setObjectName("Hint")
        self.project_info.setWordWrap(True)
        left.body.addWidget(self.project_info)
        row = QHBoxLayout()
        self.edit_project_btn = _button(tr("common.edit"), "edit")
        self.edit_project_btn.clicked.connect(self.edit_project)
        self.delete_project_btn = _button(tr("common.delete"), "trash", "Danger")
        self.delete_project_btn.clicked.connect(self.delete_project)
        row.addWidget(self.edit_project_btn)
        row.addWidget(self.delete_project_btn)
        left.body.addLayout(row)
        left.setMinimumWidth(230)

        # Lines
        right = Card(tr("proj.lines"))
        self.count_label = QLabel()
        self.count_label.setObjectName("Hint")
        right.add_header_widget(self.count_label)
        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("common.search"))
        self.search.addAction(icons.icon("search", "#93a8d2", 16), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        self.fiber_filter = QComboBox()
        self.fiber_filter.addItem(tr("proj.filter_fiber"), "")
        for ft in FIBER_TYPES:
            self.fiber_filter.addItem(ft, ft)
        self.fiber_filter.currentIndexChanged.connect(self._apply_filter)
        self.status_filter = QComboBox()
        self.status_filter.addItem(tr("proj.filter_status"), "")
        for st in Status:
            self.status_filter.addItem(tr(f"status.{st.value}"), st.value)
        self.status_filter.currentIndexChanged.connect(self._apply_filter)
        tools.addWidget(self.search, 1)
        tools.addWidget(self.fiber_filter)
        tools.addWidget(self.status_filter)
        right.body.addLayout(tools)

        self.table = make_table([tr(c) for c in self.COLUMNS], stretch_column=None)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.doubleClicked.connect(lambda *_: self.edit_line())
        right.body.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.add_line_btn = _button(tr("proj.add_line"), "plus", "Primary")
        self.add_line_btn.clicked.connect(self.add_line)
        self.edit_line_btn = _button(tr("common.edit"), "edit")
        self.edit_line_btn.clicked.connect(self.edit_line)
        self.delete_line_btn = _button(tr("common.delete"), "trash", "Danger")
        self.delete_line_btn.clicked.connect(self.delete_line)
        self.budget_btn = _button(tr("proj.open_budget"), "budget")
        self.budget_btn.clicked.connect(self._open_budget)
        self.otdr_btn = _button(tr("proj.view_otdr"), "otdr")
        self.otdr_btn.clicked.connect(self._open_otdr)
        for b in (self.add_line_btn, self.edit_line_btn, self.delete_line_btn):
            actions.addWidget(b)
        actions.addStretch(1)
        actions.addWidget(self.budget_btn)
        actions.addWidget(self.otdr_btn)
        right.body.addLayout(actions)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([255, 950])
        lay.addWidget(splitter, 1)

        ctx.data_changed.connect(self.refresh)
        self.refresh()

    # --- data ----------------------------------------------------------------

    def on_show(self, payload: object = None) -> None:
        self.refresh()
        if isinstance(payload, dict) and "project" in payload:
            self._select_project(payload["project"])

    def _current_project_id(self) -> int:
        item = self.project_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else ALL

    def _select_project(self, project_id: int) -> None:
        for i in range(self.project_list.count()):
            if self.project_list.item(i).data(Qt.ItemDataRole.UserRole) == project_id:
                self.project_list.setCurrentRow(i)
                return

    def refresh(self) -> None:
        current = self._current_project_id()
        self._projects = self.ctx.db.projects()
        all_lines = self.ctx.db.lines()
        counts: dict[int, int] = {}
        for ln in all_lines:
            counts[ln.project_id] = counts.get(ln.project_id, 0) + 1
        self.project_list.blockSignals(True)
        self.project_list.clear()
        entries = [(ALL, tr("proj.all"), len(all_lines))]
        entries += [(p.id, p.name, counts.get(p.id, 0)) for p in self._projects]
        for pid, name, n in entries:
            item = QListWidgetItem(icons.icon("folder" if pid != ALL else "dashboard", "#cfdcf5", 18),
                                   f"{name}   ·  {n}")
            item.setData(Qt.ItemDataRole.UserRole, pid)
            item.setSizeHint(QSize(0, 40))
            self.project_list.addItem(item)
        self.project_list.blockSignals(False)
        self._select_project(current)
        if self.project_list.currentRow() < 0:
            self.project_list.setCurrentRow(0)
        self._fill_lines()

    def _fill_lines(self) -> None:
        pid = self._current_project_id()
        self._lines = self.ctx.db.lines(None if pid == ALL else pid)
        project = next((p for p in self._projects if p.id == pid), None)
        if project:
            info = " · ".join(x for x in (project.kind, project.region) if x)
            self.project_info.setText(f"{info}\n{project.description}".strip())
        else:
            self.project_info.setText("")
        self.edit_project_btn.setEnabled(project is not None)
        self.delete_project_btn.setEnabled(project is not None)

        table = self.table
        table.setSortingEnabled(False)
        table.setRowCount(len(self._lines))
        for r, ln in enumerate(self._lines):
            name = Item(ln.name)
            name.setData(Qt.ItemDataRole.UserRole, ln.id)
            cells = [
                name, Item(ln.a_end), Item(ln.b_end), num_item(ln.length_km),
                Item(ln.fiber_type), num_item(ln.connectors, 0), num_item(ln.splices, 0),
                Item(ln.splitters or "—"), num_item(ln.wavelength_nm, 0),
                status_item(ln.budget_status), num_item(ln.budget_remaining_db),
            ]
            for c, item in enumerate(cells):
                table.setItem(r, c, item)
        table.setSortingEnabled(True)
        fit_columns(table)
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self.search.text().strip().lower()
        fiber = self.fiber_filter.currentData()
        status = self.status_filter.currentData()
        by_id = {ln.id: ln for ln in self._lines}
        shown = 0
        for r in range(self.table.rowCount()):
            ln = by_id[self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)]
            haystack = " ".join((ln.name, ln.a_end, ln.b_end, ln.splitters, ln.notes)).lower()
            visible = (not text or text in haystack) and (not fiber or ln.fiber_type == fiber) \
                and (not status or (ln.budget_status and ln.budget_status.value == status))
            self.table.setRowHidden(r, not visible)
            shown += visible
        self.count_label.setText(tr("proj.count", shown=shown, total=len(self._lines)))
        self._update_buttons()

    def _selected_line(self) -> Line | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        line_id = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        return next((ln for ln in self._lines if ln.id == line_id), None)

    def _update_buttons(self) -> None:
        has = self._selected_line() is not None
        for b in (self.edit_line_btn, self.delete_line_btn, self.budget_btn, self.otdr_btn):
            b.setEnabled(has)
        self.add_line_btn.setEnabled(bool(self._projects))

    # --- actions -------------------------------------------------------------

    def add_project(self) -> None:
        dlg = ProjectDialog(None, self)
        if dlg.exec():
            pid = self.ctx.db.save_project(dlg.project)
            self.ctx.data_changed.emit()
            self._select_project(pid)

    def edit_project(self) -> None:
        pid = self._current_project_id()
        if pid == ALL:
            return
        dlg = ProjectDialog(self.ctx.db.project(pid), self)
        if dlg.exec():
            self.ctx.db.save_project(dlg.project)
            self.ctx.data_changed.emit()

    def delete_project(self) -> None:
        pid = self._current_project_id()
        if pid == ALL:
            return
        project = self.ctx.db.project(pid)
        n = len(self.ctx.db.lines(pid))
        if QMessageBox.question(self, tr("common.delete"), tr(
                "common.confirm_delete_project", name=project.name, lines=n)) \
                == QMessageBox.StandardButton.Yes:
            self.ctx.db.delete_project(pid)
            self.project_list.setCurrentRow(0)
            self.ctx.data_changed.emit()

    def add_line(self) -> None:
        if not self._projects:
            QMessageBox.information(self, tr("proj.add_line"), tr("proj.no_project"))
            return
        pid = self._current_project_id()
        pid = self._projects[0].id if pid == ALL else pid
        line = Line(None, pid, "", wavelength_nm=1310)
        dlg = LineDialog(line, self._projects, self.ctx.defaults, self)
        if dlg.exec():
            self.ctx.db.save_line(dlg.line)
            self.ctx.data_changed.emit()
            self._select_line(dlg.line.id)

    def edit_line(self) -> None:
        line = self._selected_line()
        if line is None:
            return
        dlg = LineDialog(line, self._projects, self.ctx.defaults, self)
        if dlg.exec():
            self.ctx.db.save_line(dlg.line)
            self.ctx.data_changed.emit()
            self._select_line(line.id)

    def delete_line(self) -> None:
        line = self._selected_line()
        if line and QMessageBox.question(self, tr("common.delete"),
                                         tr("common.confirm_delete", name=line.name)) \
                == QMessageBox.StandardButton.Yes:
            self.ctx.db.delete_line(line.id)
            self.ctx.data_changed.emit()

    def _select_line(self, line_id: int) -> None:
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) == line_id:
                self.table.selectRow(r)
                return

    def _open_budget(self) -> None:
        line = self._selected_line()
        if line:
            self.ctx.navigate.emit("budget", {"line": line.id})

    def _open_otdr(self) -> None:
        line = self._selected_line()
        if line:
            self.ctx.navigate.emit("otdr", {"line": line.id})
