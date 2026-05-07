"""Alerts tab for managing alert rules and viewing the alert log."""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.data_store import DataStore

logger = logging.getLogger(__name__)

_RULE_TYPES = ["new_device", "bandwidth", "ip_comm", "port"]
_RULE_TYPE_LABELS = {
    "new_device": "New Unknown Device",
    "bandwidth": "Bandwidth Threshold",
    "ip_comm": "IP Communication",
    "port": "Port Activity",
}

# Minimum seconds between repeated firings of the same (rule, device) pair.
_ALERT_COOLDOWN_SECONDS: int = 60


class AddRuleDialog(QDialog):
    """Modal dialog for adding a new alert rule.

    Args:
        parent: Parent widget.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialise the add-rule dialog."""
        super().__init__(parent)
        self.setWindowTitle("Add Alert Rule")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("My Alert")
        form.addRow("Rule Name:", self._name_edit)

        self._type_combo = QComboBox()
        for rt in _RULE_TYPES:
            self._type_combo.addItem(_RULE_TYPE_LABELS[rt], rt)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Rule Type:", self._type_combo)

        self._param1_label = QLabel("Device IP:")
        self._param1_edit = QLineEdit()
        self._param1_edit.setPlaceholderText("any")
        form.addRow(self._param1_label, self._param1_edit)

        self._param2_label = QLabel("Target IP:")
        self._param2_edit = QLineEdit()
        self._param2_edit.setPlaceholderText("e.g. 8.8.8.8")
        self._param2_label.hide()
        self._param2_edit.hide()
        form.addRow(self._param2_label, self._param2_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_type_changed(0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _on_type_changed(self, _index: int) -> None:
        """Update label text to match the selected rule type.

        Args:
            _index: Current combo box index (unused).
        """
        rt = self._type_combo.currentData()
        if rt == "new_device":
            self._param1_label.setText("(No parameters needed)")
            self._param1_edit.hide()
            self._param2_label.hide()
            self._param2_edit.hide()
        elif rt == "bandwidth":
            self._param1_label.setText("Device IP (or 'any'):")
            self._param1_edit.show()
            self._param2_label.setText("MB threshold:")
            self._param2_edit.show()
            self._param2_edit.setPlaceholderText("e.g. 100")
        elif rt == "ip_comm":
            self._param1_label.setText("Source IP (or 'any'):")
            self._param1_edit.show()
            self._param2_label.setText("Destination IP:")
            self._param2_edit.show()
            self._param2_edit.setPlaceholderText("e.g. 1.2.3.4")
        elif rt == "port":
            self._param1_label.setText("Device IP (or 'any'):")
            self._param1_edit.show()
            self._param2_label.setText("Port number:")
            self._param2_edit.show()
            self._param2_edit.setPlaceholderText("e.g. 4444")

    def get_rule(self) -> Optional[dict]:
        """Return the entered rule as a dict, or ``None`` if invalid.

        Shows an in-dialog error message for invalid parameter values so
        the user can correct the input before closing.

        Returns:
            Dict with keys ``name``, ``rule_type``, ``params``, or ``None``.
        """
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Rule name cannot be empty.")
            return None
        rt = self._type_combo.currentData()
        params: dict = {"device": self._param1_edit.text().strip() or "any"}
        if rt in ("bandwidth", "ip_comm", "port"):
            value = self._param2_edit.text().strip()
            if rt == "bandwidth":
                try:
                    float(value)
                except ValueError:
                    QMessageBox.warning(
                        self, "Validation Error", "Bandwidth threshold must be a number."
                    )
                    return None
            elif rt == "port":
                try:
                    port_num = int(value)
                    if not (0 < port_num <= 65535):
                        raise ValueError
                except ValueError:
                    QMessageBox.warning(
                        self, "Validation Error", "Port must be an integer between 1 and 65535."
                    )
                    return None
            params["value"] = value
        return {"name": name, "rule_type": rt, "params": json.dumps(params)}


class AlertsTab(QWidget):
    """Tab for alert rule management and alert log display.

    Args:
        data_store: Shared :class:`~src.core.data_store.DataStore`.
        parent: Parent widget.
    """

    alert_fired = pyqtSignal(str, str, str)  # rule_name, device_ip, detail

    def __init__(self, data_store: DataStore, parent: Optional[QWidget] = None) -> None:
        """Initialise the alerts tab."""
        super().__init__(parent)
        self._store = data_store
        # Track MACs already seen so we can detect genuinely new devices.
        self._known_macs: set[str] = {d.mac for d in self._store.get_devices()}
        # Cooldown tracking: (rule_name, device_ip) -> last_fired_timestamp
        self._last_fired: dict[tuple[str, str], float] = {}
        self._setup_ui()
        self._start_refresh_timer()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the alerts tab layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Rules section
        rules_group = QGroupBox("Alert Rules")
        rules_layout = QVBoxLayout(rules_group)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Rule")
        self._add_btn.clicked.connect(self._add_rule)
        self._del_btn = QPushButton("Delete Selected")
        self._del_btn.clicked.connect(self._delete_rule)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._del_btn)
        btn_row.addStretch()
        rules_layout.addLayout(btn_row)

        self._rules_table = QTableWidget(0, 3)
        self._rules_table.setHorizontalHeaderLabels(["ID", "Type", "Name"])
        self._rules_table.horizontalHeader().setStretchLastSection(True)
        self._rules_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._rules_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._rules_table.verticalHeader().setVisible(False)
        self._rules_table.setMaximumHeight(200)
        rules_layout.addWidget(self._rules_table)
        root.addWidget(rules_group)

        # Alert log section
        log_group = QGroupBox("Alert Log")
        log_layout = QVBoxLayout(log_group)

        self._log_table = QTableWidget(0, 4)
        self._log_table.setHorizontalHeaderLabels(
            ["Timestamp", "Rule", "Device IP", "Detail"]
        )
        self._log_table.horizontalHeader().setStretchLastSection(True)
        self._log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._log_table.setAlternatingRowColors(True)
        self._log_table.verticalHeader().setVisible(False)
        log_layout.addWidget(self._log_table)
        root.addWidget(log_group)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _start_refresh_timer(self) -> None:
        """Start the 3-second refresh timer."""
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    def refresh(self) -> None:
        """Refresh both the rules and log tables."""
        self._refresh_rules()
        self._refresh_log()

    def _refresh_rules(self) -> None:
        """Reload and display all alert rules."""
        rules = self._store.get_alert_rules()
        self._rules_table.setRowCount(len(rules))
        for row, rule in enumerate(rules):
            self._rules_table.setItem(row, 0, QTableWidgetItem(str(rule.get("id", ""))))
            self._rules_table.setItem(
                row, 1, QTableWidgetItem(_RULE_TYPE_LABELS.get(rule.get("rule_type", ""), ""))
            )
            self._rules_table.setItem(row, 2, QTableWidgetItem(rule.get("name", "")))
        self._rules_table.resizeColumnsToContents()

    def _refresh_log(self) -> None:
        """Reload and display the alert log."""
        entries = self._store.get_alert_log()
        self._log_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self._log_table.setItem(row, 0, QTableWidgetItem(str(entry.get("ts", ""))))
            self._log_table.setItem(row, 1, QTableWidgetItem(entry.get("rule_name", "")))
            self._log_table.setItem(row, 2, QTableWidgetItem(entry.get("device_ip", "")))
            self._log_table.setItem(row, 3, QTableWidgetItem(entry.get("detail", "")))
        self._log_table.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def _add_rule(self) -> None:
        """Open the add-rule dialog and save the new rule."""
        dlg = AddRuleDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            rule = dlg.get_rule()
            if rule:
                self._store.add_alert_rule(
                    rule_type=rule["rule_type"],
                    name=rule["name"],
                    params=rule["params"],
                )
                self._refresh_rules()

    def _delete_rule(self) -> None:
        """Delete the currently selected alert rule."""
        rows = self._rules_table.selectedItems()
        if not rows:
            return
        selected_row = self._rules_table.currentRow()
        id_item = self._rules_table.item(selected_row, 0)
        if id_item:
            try:
                rule_id = int(id_item.text())
                self._store.delete_alert_rule(rule_id)
                self._refresh_rules()
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Alert evaluation
    # ------------------------------------------------------------------

    def evaluate_alerts(self) -> None:
        """Check current state against all rules and fire matching alerts.

        Called periodically from the main window.
        """
        rules = self._store.get_alert_rules()
        devices = self._store.get_devices()
        connections = self._store.get_connections()

        # Detect devices that appeared since the last evaluation.
        new_devices = [d for d in devices if d.mac not in self._known_macs]
        self._known_macs.update(d.mac for d in devices)

        for rule in rules:
            if not rule.get("enabled", 1):
                continue
            rt = rule.get("rule_type", "")
            try:
                params = json.loads(rule.get("params", "{}"))
            except json.JSONDecodeError:
                continue

            if rt == "new_device":
                for device in new_devices:
                    detail = (
                        f"Nuovo dispositivo: {device.ip} "
                        f"({device.mac}) — {device.vendor or 'Vendor sconosciuto'}"
                    )
                    self._fire(rule["name"], device.ip, detail)

            elif rt == "bandwidth":
                device_filter = params.get("device", "any")
                try:
                    threshold_bytes = float(params.get("value", "0")) * 1024 * 1024
                except ValueError:
                    continue
                for conn in connections:
                    if device_filter != "any" and conn.src_ip != device_filter:
                        continue
                    if conn.bytes_transferred > threshold_bytes:
                        detail = (
                            f"{conn.src_ip} → {conn.dst_ip}: "
                            f"{conn.bytes_transferred / 1_000_000:.1f} MB"
                        )
                        self._fire(rule["name"], conn.src_ip, detail)
                        break

            elif rt == "ip_comm":
                src_filter = params.get("device", "any")
                dst_target = params.get("value", "")
                for conn in connections:
                    if src_filter != "any" and conn.src_ip != src_filter:
                        continue
                    if conn.dst_ip == dst_target:
                        detail = f"{conn.src_ip} communicating with {dst_target}"
                        self._fire(rule["name"], conn.src_ip, detail)
                        break

            elif rt == "port":
                device_filter = params.get("device", "any")
                try:
                    target_port = int(params.get("value", "0"))
                except ValueError:
                    continue
                for conn in connections:
                    if device_filter != "any" and conn.src_ip != device_filter:
                        continue
                    if conn.port == target_port:
                        detail = f"{conn.src_ip} using port {target_port}"
                        self._fire(rule["name"], conn.src_ip, detail)
                        conn.flagged = True
                        break

    def _fire(self, rule_name: str, device_ip: str, detail: str) -> None:
        """Record an alert and emit the signal, subject to a cooldown period.

        Repeated firings of the same (rule, device) pair are suppressed for
        ``_ALERT_COOLDOWN_SECONDS`` to prevent log spam.

        Args:
            rule_name: Name of the triggered rule.
            device_ip: Source device IP.
            detail: Human-readable description.
        """
        key = (rule_name, device_ip)
        now = time.time()
        if now - self._last_fired.get(key, 0.0) < _ALERT_COOLDOWN_SECONDS:
            return
        self._last_fired[key] = now
        self._store.add_alert(rule_name, device_ip, detail)
        self.alert_fired.emit(rule_name, device_ip, detail)
        logger.info("Alert: [%s] %s — %s", rule_name, device_ip, detail)
