"""HomeNetMonitor application entry point."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure the project root (parent of src/) is on sys.path so that
# "from src.*" imports work when main.py is run directly as a script
# (e.g. `python src/main.py`).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PyQt6.QtWidgets import QApplication, QMessageBox

from src.core.data_store import DataStore
from src.ui.main_window import MainWindow
from src.utils.constants import APPDATA_DIR, APP_NAME, LOG_PATH, QSS_DARK_THEME


def _configure_logging() -> None:
    """Set up file + console logging for the application."""
    APPDATA_DIR.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def main() -> None:
    """Launch the HomeNetMonitor application."""
    _configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting %s", APP_NAME)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(QSS_DARK_THEME)

    try:
        data_store = DataStore()
    except Exception as exc:
        QMessageBox.critical(
            None,
            "Startup Error",
            f"Failed to initialise the database:\n{exc}",
        )
        logger.exception("DataStore initialisation failed")
        sys.exit(1)

    window = MainWindow(data_store)
    window.show()

    exit_code = app.exec()
    logger.info("Application exiting with code %d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
