"""MAC OUI (vendor) lookup backed by a bundled JSON file."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MacVendorLookup:
    """Offline MAC OUI → vendor name lookup.

    Loads the bundled ``mac_oui.json`` file once on first use and caches
    it in memory for the lifetime of the instance.

    The JSON file must be a flat object mapping 6-char uppercase hex OUI
    prefixes (e.g. ``"A4C138"``) to vendor name strings.
    """

    def __init__(self, oui_json_path: Path) -> None:
        """Initialise the lookup with a path to the OUI JSON file.

        Args:
            oui_json_path: Absolute path to the ``mac_oui.json`` file.
        """
        self._path = oui_json_path
        self._data: dict[str, str] = {}
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load the OUI database from disk into memory.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._loaded:
            return
        try:
            with open(self._path, encoding="utf-8") as fh:
                self._data = json.load(fh)
            self._loaded = True
            logger.debug("Loaded %d OUI entries from %s", len(self._data), self._path)
        except FileNotFoundError:
            logger.warning("mac_oui.json not found at %s — vendor lookup disabled", self._path)
            self._loaded = True  # don't retry
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse mac_oui.json: %s", exc)
            self._loaded = True

    def get_vendor(self, mac: str) -> str:
        """Return the vendor name for a MAC address, or an empty string.

        Args:
            mac: MAC address in any common format (colon-, hyphen-, or dot-
                 separated, upper or lower case). Examples::

                     "a4:c1:38:xx:xx:xx"
                     "A4-C1-38-xx-xx-xx"
                     "a4c1.38xx.xxxx"

        Returns:
            Vendor name string, or ``""`` if not found.
        """
        if not self._loaded:
            self.load()

        normalized = self._normalize_mac(mac)
        if len(normalized) < 6:
            return ""

        oui = normalized[:6].upper()
        return self._data.get(oui, "")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_mac(mac: str) -> str:
        """Strip all non-hex characters from a MAC address string."""
        return "".join(c for c in mac if c in "0123456789abcdefABCDEF")
