"""Modal dialogs: the pre-transmit authorization gate and the tool-path settings editor."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QCheckBox, QLineEdit,
    QDialogButtonBox,
)
from .. import config as _config

# Spec §1 (Purpose & Context): GhostSignal transmits simulated GNSS signals
# over RF and is intended only for authorized research/development/testing
# in a shielded (Faraday) environment with proper permission.
AUTHORIZATION_NOTICE = (
    "GhostSignal generates and can transmit simulated GNSS signals over RF.\n\n"
    "This tool is intended ONLY for authorized research, development, and "
    "testing — Faraday-cage labs, sanctioned drone-test ranges, and "
    "academic work carried out with proper permission.\n\n"
    "Transmitting GNSS signals outside a shielded environment, or without "
    "explicit authorization, is illegal in most jurisdictions and can "
    "interfere with safety-of-life navigation systems.\n\n"
    "By continuing you confirm that this transmission is authorized and "
    "will take place in a properly shielded (Faraday) environment."
)


class AuthorizationDialog(QDialog):
    """Modal legal/authorization gate shown before the first real transmit.

    The OK button stays disabled until the "I am authorized" checkbox is
    ticked, so ``exec()`` can only be accepted once the box is checked.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Authorization Required")
        self.setModal(True)

        layout = QVBoxLayout(self)

        notice = QLabel(AUTHORIZATION_NOTICE)
        notice.setWordWrap(True)
        layout.addWidget(notice)

        self.confirm_checkbox = QCheckBox(
            "I am authorized to transmit in a shielded/Faraday environment."
        )
        layout.addWidget(self.confirm_checkbox)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)
        self.confirm_checkbox.toggled.connect(self.ok_button.setEnabled)

    @staticmethod
    def confirm(parent=None) -> bool:
        """Show the dialog modally; return True only if accepted with the box ticked."""
        dlg = AuthorizationDialog(parent)
        result = dlg.exec()
        return result == QDialog.DialogCode.Accepted and dlg.confirm_checkbox.isChecked()


class SettingsDialog(QDialog):
    """Tool-path overrides (one QLineEdit per ``config.DEFAULT_TOOL_KEYS`` entry)
    plus Earthdata (CDDIS) credentials for the RINEX/ephemeris downloader.

    Fields are left blank unless an explicit override is passed in
    ``initial`` or was previously saved; the auto-detected path (env var /
    PATH / PothosSDR dir, via ``ToolConfig.resolve_tool``) is shown only as
    placeholder text, so an untouched field means "use auto-detection" and
    ``values()`` won't freeze a one-time auto-detected path in as a
    permanent override.
    """

    def __init__(self, parent=None, initial: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        initial = dict(initial or {})

        layout = QVBoxLayout(self)
        form = QFormLayout()

        tool_cfg = _config.ToolConfig()
        self.tool_fields: dict[str, QLineEdit] = {}
        for key in sorted(_config.DEFAULT_TOOL_KEYS):
            field = QLineEdit(initial.get(key, ""))
            field.setPlaceholderText(tool_cfg.resolve_tool(key))
            form.addRow(key, field)
            self.tool_fields[key] = field

        self.earthdata_username = QLineEdit(initial.get("earthdata_username", ""))
        form.addRow("Earthdata username", self.earthdata_username)

        self.earthdata_password = QLineEdit(initial.get("earthdata_password", ""))
        self.earthdata_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Earthdata password", self.earthdata_password)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict:
        """Return ``{tool_key: text}`` for every tool field plus the Earthdata
        credential fields. An empty string means "no override" for a tool key.
        """
        result = {key: field.text() for key, field in self.tool_fields.items()}
        result["earthdata_username"] = self.earthdata_username.text()
        result["earthdata_password"] = self.earthdata_password.text()
        return result
