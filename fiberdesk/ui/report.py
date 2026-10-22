"""One-page PDF line report: budget, expected vs measured, OTDR events and trace."""

from __future__ import annotations

import os
from datetime import datetime
from html import escape

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt, QUrl
from PySide6.QtGui import (QColor, QFont, QImage, QPageLayout, QPageSize, QPainter,
                           QPainterPath, QPdfWriter, QPen, QTextDocument)

from .. import __version__
from ..core.budget import calculate_budget
from ..core.defaults import Defaults
from ..core.otdr import EventKind, compare_expected, evaluate_event, link_breakdown
from ..core.status import Status
from ..i18n import tr
from ..storage.db import MeasurementView
from . import theme

# Darker variants that read well on white paper.
PRINT_WAVELENGTH = {1310: "#1f77b4", 1490: "#2e9e4f", 1550: "#7b3fbf", 1625: "#d9771e"}
PRINT_STATUS = {Status.PASS: "#1e8a4c", Status.WARN: "#b7791f", Status.FAIL: "#c53030"}


def render_trace(primary: MeasurementView, overlays: list[MeasurementView], defaults: Defaults,
                 width: int = 1800, height: int = 600) -> QImage:
    from .pages.otdr import trace_for  # local import: pyqtgraph is only needed for the UI

    img = QImage(width, height, QImage.Format.Format_ARGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont(theme.app_font(9))
    font.setPixelSize(22)
    p.setFont(font)
    left, right, top, bottom = 90, width - 20, 20, height - 70
    curves = [(v, *trace_for(v, defaults)) for v in [primary] + [o for o in overlays
                                                                if o is not primary]]
    x_min = min(float(c[1][0]) for c in curves)
    x_max = max(float(c[1][-1]) for c in curves)
    y_min = 0.0
    y_max = max(float(c[2].max()) for c in curves) + 2

    def pt(x: float, y: float) -> QPointF:
        return QPointF(left + (x - x_min) / (x_max - x_min) * (right - left),
                       bottom - (y - y_min) / (y_max - y_min) * (bottom - top))

    p.setPen(QPen(QColor("#e2e8f0"), 1))
    for i in range(6):
        y = y_min + (y_max - y_min) * i / 5
        a = pt(x_min, y)
        p.drawLine(QPointF(left, a.y()), QPointF(right, a.y()))
        p.setPen(QColor("#4a5568"))
        p.drawText(QRectF(0, a.y() - 14, left - 10, 28),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{y:.0f}")
        p.setPen(QPen(QColor("#e2e8f0"), 1))
    for i in range(9):
        x = x_min + (x_max - x_min) * i / 8
        a = pt(x, y_min)
        p.drawLine(QPointF(a.x(), top), QPointF(a.x(), bottom))
        p.setPen(QColor("#4a5568"))
        p.drawText(QRectF(a.x() - 60, bottom + 6, 120, 28), Qt.AlignmentFlag.AlignCenter,
                   f"{x:.2f}")
        p.setPen(QPen(QColor("#e2e8f0"), 1))
    p.setPen(QColor("#4a5568"))
    p.drawText(QRectF(left, bottom + 34, right - left, 30), Qt.AlignmentFlag.AlignCenter,
               f"{tr('otdr.axis_x')}  ·  {tr('otdr.axis_y')}")

    for e in primary.events:
        status = evaluate_event(e, primary.measurement.wavelength_nm, defaults)
        color = QColor(PRINT_STATUS[status]) if status is not Status.PASS else QColor("#a0aec0")
        a = pt(e.distance_km, y_min)
        p.setPen(QPen(color, 1.5, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(a.x(), top + 26), QPointF(a.x(), bottom))
        p.setPen(color)
        p.drawText(QRectF(a.x() - 20, top, 40, 26), Qt.AlignmentFlag.AlignCenter, str(e.number))

    legend_x = right - 20
    for view, xs, ys in reversed(curves):
        wl = view.measurement.wavelength_nm
        color = QColor(PRINT_WAVELENGTH.get(wl, "#000000"))
        path = QPainterPath()
        step = max(1, len(xs) // 2400)
        path.moveTo(pt(float(xs[0]), float(ys[0])))
        for x, y in zip(xs[::step], ys[::step], strict=True):
            path.lineTo(pt(float(x), float(y)))
        p.setPen(QPen(color, 2.4 if view is primary else 1.6))
        p.drawPath(path)
        label = f"{wl} nm"
        w = p.fontMetrics().horizontalAdvance(label)
        legend_x -= w + 50
        p.fillRect(QRectF(legend_x, top + 40, 26, 6), color)
        p.setPen(QColor("#1a202c"))
        p.drawText(QPointF(legend_x + 32, top + 50), label)
    p.end()
    return img


def _status_cell(status: Status | None) -> str:
    if status is None:
        return "—"
    return f"<b style='color:{PRINT_STATUS[status]}'>{status.value}</b>"


def build_html(view: MeasurementView, defaults: Defaults, image_width: int = 640) -> str:
    m, line = view.measurement, view.line
    budget = calculate_budget(line.budget_input(m.wavelength_nm), defaults)
    cmp = compare_expected(budget.loss_by_key, link_breakdown(view.events), defaults)
    th = "style='text-align:left; background:#edf2f7; padding:3px 6px'"
    td = "style='padding:2px 6px; border-bottom:1px solid #e2e8f0'"
    tdr = "style='padding:2px 6px; border-bottom:1px solid #e2e8f0; text-align:right'"

    def num(v, d=2):
        return "—" if v is None else f"{v:.{d}f}"

    info = [
        (tr("report.project"), view.project.name),
        (tr("report.route"), f"{line.a_end} → {line.b_end}"),
        (tr("line.length"), f"{line.length_km:.2f} km · {line.fiber_type} · "
                            f"{line.connectors} conn. · {line.splices} splices"
                            + (f" · {line.splitters}" if line.splitters else "")),
        (tr("report.measurement"), f"{view.device.profile.model} ({view.device.serial}) · "
                                   f"{m.wavelength_nm} nm · {m.pulse_ns} ns · "
                                   f"{m.measured_at.replace('T', ' ')} · {m.operator}"),
    ]
    info_rows = "".join(f"<tr><td {td}><b>{escape(k)}</b></td><td {td}>{escape(v)}</td></tr>"
                        for k, v in info)

    budget_rows = "".join(
        f"<tr><td {td}>{tr(f'loss.{r.key}')}</td><td {tdr}>{num(r.expected_db)}</td>"
        f"<td {tdr}>{num(r.measured_db)}</td><td {tdr}>{r.delta_db:+.2f}</td></tr>"
        for r in cmp.rows)
    budget_rows += (f"<tr><td {td}><b>{tr('otdr.cmp_total')}</b></td>"
                    f"<td {tdr}><b>{num(cmp.expected_total_db)}</b></td>"
                    f"<td {tdr}><b>{num(cmp.measured_total_db)}</b></td>"
                    f"<td {tdr}><b>{cmp.delta_db:+.2f}</b></td></tr>")

    event_rows = ""
    for e in view.events:
        status = None if e.kind is EventKind.END else evaluate_event(e, m.wavelength_nm, defaults)
        kind = tr(f"event.{e.kind.value}") + (f" 1:{e.splitter_ratio}" if e.splitter_ratio else "")
        event_rows += (f"<tr><td {tdr}>{e.number}</td><td {tdr}>{e.distance_km:.3f}</td>"
                       f"<td {td}>{kind}</td><td {tdr}>{num(e.loss_db, 3)}</td>"
                       f"<td {tdr}>{num(e.reflectance_db, 1)}</td>"
                       f"<td {tdr}>{num(e.section_db_km, 3)}</td>"
                       f"<td {td}>{_status_cell(status)}</td></tr>")

    headers = "".join(f"<th {th}>{tr(k)}</th>" for k in (
        "otdr.ev_no", "otdr.ev_distance", "otdr.ev_type", "otdr.ev_loss", "otdr.ev_refl",
        "otdr.ev_section", "otdr.ev_status"))
    cmp_headers = "".join(f"<th {th}>{tr(k)}</th>" for k in (
        "otdr.cmp_item", "otdr.cmp_expected", "otdr.cmp_measured", "otdr.cmp_delta"))

    return f"""
    <html><body style="font-family:'{theme.app_font().family()}'; font-size:8.5pt; color:#1a202c">
    <h2 style="margin:0">{escape(tr('report.title', line=line.name))}</h2>
    <p style="color:#4a5568; margin-top:2px">{escape(tr('report.generated',
        time=datetime.now().strftime('%Y-%m-%d %H:%M'), version=__version__))}</p>
    <table width="100%" cellspacing="0">{info_rows}</table>
    <h3>{tr('report.budget')}</h3>
    <p>{tr('budget.available')}: <b>{budget.available_db:.2f} dB</b> ·
       {tr('budget.total_loss')}: <b>{budget.total_loss_db:.2f} dB</b> ·
       {tr('budget.safety')}: {budget.safety_margin_db:.2f} dB ·
       {tr('budget.remaining')}: <b>{budget.remaining_db:+.2f} dB</b> {_status_cell(budget.status)}
       &nbsp;&nbsp;|&nbsp;&nbsp; {tr('otdr.compare')}: {_status_cell(cmp.status)}
       · OTDR: {_status_cell(view.status)}</p>
    <table width="100%" cellspacing="0"><tr>{cmp_headers}</tr>{budget_rows}</table>
    <h3>{tr('report.trace')}</h3>
    <p><img src="trace.png" width="{image_width}"></p>
    <h3>{tr('report.events')}</h3>
    <table width="100%" cellspacing="0"><tr>{headers}</tr>{event_rows}</table>
    </body></html>"""


def export_line_report(path: str, view: MeasurementView, overlays: list[MeasurementView],
                       defaults: Defaults) -> None:
    writer = QPdfWriter(path)
    writer.setResolution(150)
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4),
                                     QPageLayout.Orientation.Portrait,
                                     QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter))
    writer.setTitle(tr("report.title", line=view.line.name))
    writer.setCreator(f"FiberDesk {__version__}")
    doc = QTextDocument()
    doc.documentLayout().setPaintDevice(writer)  # lay text out at the printer's resolution
    rect = writer.pageLayout().paintRectPixels(writer.resolution())
    doc.setPageSize(QSizeF(rect.width(), rect.height()))
    doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("trace.png"),
                    render_trace(view, overlays, defaults))
    # Image sizes are in screen pixels (96 dpi) and scaled up to the printer's resolution.
    image_width = int(rect.width() * 96 / writer.logicalDpiX() * 0.98)
    doc.setHtml(build_html(view, defaults, image_width))
    doc.print_(writer)
    if not os.path.exists(path):
        raise OSError(f"PDF was not written: {path}")
