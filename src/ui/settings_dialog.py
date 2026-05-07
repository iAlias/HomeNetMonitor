"""Settings dialog for HomeNetMonitor."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

try:
    import netifaces  # type: ignore
except ImportError:
    netifaces = None  # type: ignore


class SettingsDialog(QDialog):
    """Application settings dialog.

    Args:
        current_settings: Dict of current settings values.
        parent: Parent widget.
    """

    def __init__(
        self,
        current_settings: dict,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialise the settings dialog."""
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Interface selector
        self._iface_combo = QComboBox()
        try:
            ifaces = netifaces.interfaces() if netifaces is not None else []
            self._iface_combo.addItems(ifaces)
        except Exception:  # noqa: BLE001
            self._iface_combo.addItem("default")

        current_iface = current_settings.get("interface", "")
        idx = self._iface_combo.findText(current_iface)
        if idx >= 0:
            self._iface_combo.setCurrentIndex(idx)
        form.addRow("Capture Interface:", self._iface_combo)

        # Scan interval
        self._scan_spin = QSpinBox()
        self._scan_spin.setRange(10, 300)
        self._scan_spin.setSuffix(" s")
        self._scan_spin.setValue(current_settings.get("scan_interval", 30))
        form.addRow("ARP Scan Interval:", self._scan_spin)

        # DB retention
        self._retention_spin = QSpinBox()
        self._retention_spin.setRange(1, 365)
        self._retention_spin.setSuffix(" days")
        self._retention_spin.setValue(current_settings.get("retention_days", 7))
        form.addRow("DB Retention:", self._retention_spin)

        # Alert sound
        self._sound_check = QCheckBox()
        self._sound_check.setChecked(current_settings.get("alert_sound", True))
        form.addRow("Alert Sound:", self._sound_check)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self) -> dict:
        """Return the settings as entered by the user.

        Returns:
            Dict with keys ``interface``, ``scan_interval``,
            ``retention_days``, ``alert_sound``.
        """
        return {
            "interface": self._iface_combo.currentText(),
            "scan_interval": self._scan_spin.value(),
            "retention_days": self._retention_spin.value(),
            "alert_sound": self._sound_check.isChecked(),
        }
