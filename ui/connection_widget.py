import os

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.PyQt.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

_PLUGIN_DIR = os.path.join(os.path.dirname(__file__), "..")


class ConnectionWidget(QWidget):
    connect_requested = pyqtSignal(str, str, str)  # url, username, password

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ── Header: icon + plugin name ──────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(10)

        icon_label = QLabel()
        icon_path = os.path.join(_PLUGIN_DIR, "resources", "icons", "icon_connect.png")
        pix = QPixmap(icon_path)
        if not pix.isNull():
            icon_label.setPixmap(pix.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        header.addWidget(icon_label)

        title_block = QVBoxLayout()
        title_block.setSpacing(1)
        title = QLabel("<b style='font-size:13pt'>QboToolbox</b>")
        subtitle = QLabel(
            "<span style='color:#888;font-size:8pt'>KoboToolbox connector for QGIS</span>"
        )
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addLayout(title_block)
        header.addStretch()

        layout.addLayout(header)

        # ── Divider ─────────────────────────────────────────────────────────
        divider = QLabel()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background:#cccccc;")
        layout.addWidget(divider)

        # ── Form ────────────────────────────────────────────────────────────
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setSpacing(8)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://kf.kobotoolbox.org")
        form.addRow("Server URL:", self.url_edit)

        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("username")
        form.addRow("Username:", self.user_edit)

        # Password row with reveal toggle
        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(4)
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)
        self.pass_edit.setPlaceholderText("password")
        pwd_row.addWidget(self.pass_edit)

        self._reveal_btn = QToolButton()
        self._reveal_btn.setText("👁")
        self._reveal_btn.setCheckable(True)
        self._reveal_btn.setFixedWidth(28)
        self._reveal_btn.setToolTip("Show / hide password")
        self._reveal_btn.toggled.connect(self._toggle_password_visibility)
        pwd_row.addWidget(self._reveal_btn)

        pwd_container = QWidget()
        pwd_container.setLayout(pwd_row)
        form.addRow("Password:", pwd_container)

        layout.addLayout(form)

        # ── Connect button ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        btn_row.addWidget(self.connect_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── Status ───────────────────────────────────────────────────────────
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        layout.addStretch()

    # ── Slots ────────────────────────────────────────────────────────────────

    def _toggle_password_visibility(self, checked: bool):
        self.pass_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)

    def _on_connect_clicked(self):
        url = self.url_edit.text().strip()
        user = self.user_edit.text().strip()
        pwd = self.pass_edit.text()
        if not url or not user or not pwd:
            self.set_status("Please fill in all fields.", error=True)
            return
        self.connect_btn.setEnabled(False)
        self.set_status("Connecting…")
        self.connect_requested.emit(url, user, pwd)

    def set_status(self, message: str, error: bool = False):
        color = "red" if error else "green"
        self.status_label.setText(f'<span style="color:{color}">{message}</span>')

    def reset_connect_button(self):
        self.connect_btn.setEnabled(True)

    def load_saved(self, url: str, username: str = "", password: str = ""):
        if url:
            self.url_edit.setText(url)
        if username:
            self.user_edit.setText(username)
        if password:
            self.pass_edit.setText(password)
