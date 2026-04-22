"""Dashboard tab showing live traffic graph and KPI cards."""
from __future__ import annotations

import time
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.data_store import DataStore
from src.utils.constants import ACCENT, TRAFFIC_HISTORY_SECONDS

try:
    import pyqtgraph as pg  # type: ignore

    _HAS_PYQTGRAPH = True
except ImportError:
    _HAS_PYQTGRAPH = False


class KpiCard(QWidget):
    """A small KPI display card with a title and a large value label.

    Args:
        title: Card title text.
        value: Initial value string.
        parent: Parent widget.
    """

    def __init__(self, title: str, value: str = "0", parent: Optional[QWidget] = None) -> None:
        """Initialise the KPI card."""
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        self._title_label = QLabel(title)
        self._title_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        self._value_label = QLabel(value)
        self._value_label.setStyleSheet(
            f"color: {ACCENT}; font-size: 22px; font-weight: bold;"
        )
        layout.addWidget(self._title_label)
        layout.addWidget(self._value_label)
        self.setStyleSheet("background: #16213e; border-radius: 6px;")

    def set_value(self, value: str) -> None:
        """Update the displayed value.

        Args:
            value: New value string.
        """
        self._value_label.setText(value)


class DashboardTab(QWidget):
    """Main dashboard tab with live traffic graph, KPI cards, and top destinations.

    Args:
        data_store: Shared :class:`~src.core.data_store.DataStore`.
        parent: Parent widget.
    """

    def __init__(self, data_store: DataStore, parent: Optional[QWidget] = None) -> None:
        """Initialise the dashboard tab."""
        super().__init__(parent)
        self._store = data_store
        self._in_curve = None
        self._out_curve = None
        self._plot_widget = None
        self._setup_ui()
        self._start_refresh_timer()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the dashboard layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Interface selector
        iface_row = QHBoxLayout()
        iface_row.addWidget(QLabel("Interface:"))
        self._iface_combo = QComboBox()
        self._populate_interfaces()
        iface_row.addWidget(self._iface_combo)
        iface_row.addStretch()
        root.addLayout(iface_row)

        # KPI cards row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)
        self._kpi_devices = KpiCard("Devices Online")
        self._kpi_connections = KpiCard("Active Connections")
        self._kpi_bw_in = KpiCard("Bandwidth Today ↓")
        self._kpi_bw_out = KpiCard("Bandwidth Today ↑")
        for card in (
            self._kpi_devices,
            self._kpi_connections,
            self._kpi_bw_in,
            self._kpi_bw_out,
        ):
            kpi_row.addWidget(card)
        root.addLayout(kpi_row)

        # Traffic graph
        graph_group = QGroupBox("Live Traffic (bytes/sec)")
        graph_layout = QVBoxLayout(graph_group)
        if _HAS_PYQTGRAPH:
            pg.setConfigOption("background", "#16213e")
            pg.setConfigOption("foreground", "#e0e0e0")
            self._plot_widget = pg.PlotWidget()
            self._plot_widget.setMinimumHeight(180)
            self._plot_widget.showGrid(x=True, y=True, alpha=0.2)
            self._plot_widget.setLabel("left", "Bytes/s")
            self._plot_widget.setLabel("bottom", "Seconds ago")
            self._in_curve = self._plot_widget.plot(
                pen=pg.mkPen(color="#00b4d8", width=2), name="IN"
            )
            self._out_curve = self._plot_widget.plot(
                pen=pg.mkPen(color="#ff6b6b", width=2), name="OUT"
            )
            legend = self._plot_widget.addLegend()
            legend.addItem(self._in_curve, "Download (↓)")
            legend.addItem(self._out_curve, "Upload (↑)")
            graph_layout.addWidget(self._plot_widget)
        else:
            graph_layout.addWidget(QLabel("pyqtgraph not installed — graph unavailable"))
        root.addWidget(graph_group)

        # Top destinations table
        top_group = QGroupBox("Top 5 Destinations")
        top_layout = QVBoxLayout(top_group)
        self._top_table = QTableWidget(0, 4)
        self._top_table.setHorizontalHeaderLabels(
            ["Destination IP", "Hostname", "Country", "Bytes"]
        )
        self._top_table.horizontalHeader().setStretchLastSection(True)
        self._top_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._top_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._top_table.verticalHeader().setVisible(False)
        self._top_table.setMaximumHeight(200)
        top_layout.addWidget(self._top_table)
        root.addWidget(top_group)

    def _populate_interfaces(self) -> None:
        """Fill the interface combo box from psutil/netifaces."""
        self._iface_combo.clear()
        try:
            import netifaces  # type: ignore

            ifaces = netifaces.interfaces()
            self._iface_combo.addItems(ifaces)
        except Exception:  # noqa: BLE001
            try:
                import psutil  # type: ignore

                self._iface_combo.addItems(list(psutil.net_if_addrs().keys()))
            except Exception:  # noqa: BLE001
                self._iface_combo.addItem("default")

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _start_refresh_timer(self) -> None:
        """Start the 2-second UI refresh timer."""
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _refresh(self) -> None:
        """Refresh all dashboard widgets from the data store."""
        devices = self._store.get_devices()
        connections = self._store.get_connections()

        online = sum(1 for d in devices if d.status == "Online")
        self._kpi_devices.set_value(str(online))
        self._kpi_connections.set_value(str(len(connections)))

        bw_in, bw_out = self._store.get_bandwidth_today()
        self._kpi_bw_in.set_value(_format_bytes(bw_in))
        self._kpi_bw_out.set_value(_format_bytes(bw_out))

        self._refresh_graph()
        self._refresh_top_table(connections)

    def _refresh_graph(self) -> None:
        """Update the pyqtgraph curves with latest bandwidth history."""
        if not _HAS_PYQTGRAPH or self._plot_widget is None:
            return

        now = time.time()
        samples_in = self._store.get_bandwidth_history("in", TRAFFIC_HISTORY_SECONDS)
        samples_out = self._store.get_bandwidth_history("out", TRAFFIC_HISTORY_SECONDS)

        def _to_xy(samples: list[tuple[float, int]]) -> tuple[list[float], list[int]]:
            xs = [-(now - ts) for ts, _ in samples]
            ys = [b for _, b in samples]
            return xs, ys

        xs_in, ys_in = _to_xy(samples_in)
        xs_out, ys_out = _to_xy(samples_out)

        if self._in_curve:
            self._in_curve.setData(xs_in, ys_in)
        if self._out_curve:
            self._out_curve.setData(xs_out, ys_out)

    def _refresh_top_table(self, connections: list) -> None:
        """Populate the top-5 destinations table.

        Args:
            connections: Current list of :class:`Connection` objects.
        """
        # Aggregate bytes by dst_ip
        agg: dict[str, dict] = {}
        for c in connections:
            key = c.dst_ip
            if key not in agg:
                agg[key] = {"ip": key, "host": c.dst_host, "country": c.country, "bytes": 0}
            agg[key]["bytes"] += c.bytes_transferred
            if c.dst_host:
                agg[key]["host"] = c.dst_host
            if c.country:
                agg[key]["country"] = c.country

        top5 = sorted(agg.values(), key=lambda x: x["bytes"], reverse=True)[:5]

        self._top_table.setRowCount(len(top5))
        for row, entry in enumerate(top5):
            self._top_table.setItem(row, 0, QTableWidgetItem(entry["ip"]))
            self._top_table.setItem(row, 1, QTableWidgetItem(entry["host"] or ""))
            country = entry["country"] or ""
            flag = _country_flag(country)
            self._top_table.setItem(row, 2, QTableWidgetItem(f"{flag} {country}"))
            self._top_table.setItem(row, 3, QTableWidgetItem(_format_bytes(entry["bytes"])))

    def get_selected_interface(self) -> str:
        """Return the currently selected network interface name.

        Returns:
            Interface name string.
        """
        return self._iface_combo.currentText()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_bytes(n: int) -> str:
    """Format a byte count as a human-readable string.

    Args:
        n: Number of bytes.

    Returns:
        Formatted string such as ``"1.2 MB"``.
    """
    if n < 1024:
        return f"{n} B"
    elif n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    elif n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    else:
        return f"{n / 1024 ** 3:.2f} GB"


def _country_flag(country: str) -> str:
    """Convert a country name to an approximate flag emoji.

    Uses a small lookup table for common countries; returns 🌐 otherwise.

    Args:
        country: Country name string.

    Returns:
        Flag emoji string.
    """
    _MAP: dict[str, str] = {
        "United States": "🇺🇸",
        "United Kingdom": "🇬🇧",
        "Germany": "🇩🇪",
        "France": "🇫🇷",
        "Japan": "🇯🇵",
        "China": "🇨🇳",
        "Russia": "🇷🇺",
        "Canada": "🇨🇦",
        "Australia": "🇦🇺",
        "Netherlands": "🇳🇱",
        "Italy": "🇮🇹",
        "Brazil": "🇧🇷",
        "India": "🇮🇳",
        "South Korea": "🇰🇷",
        "Sweden": "🇸🇪",
    }
    return _MAP.get(country, "🌐")
