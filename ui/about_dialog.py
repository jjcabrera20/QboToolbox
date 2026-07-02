import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

_PLUGIN_DIR = os.path.join(os.path.dirname(__file__), "..")


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About QboToolbox")
        self.setFixedWidth(420)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 16)

        # ── Icon + title row ────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(14)

        icon_lbl = QLabel()
        icon_path = os.path.join(_PLUGIN_DIR, "resources", "icons", "qbo_toolbox.png")
        pix = QPixmap(icon_path)
        if not pix.isNull():
            icon_lbl.setPixmap(pix.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        top.addWidget(icon_lbl, 0, Qt.AlignTop)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)

        name_lbl = QLabel("<b style='font-size:14pt'>QboToolbox</b>")
        version_lbl = QLabel("<span style='color:#666'>Version 1.0.0</span>")
        author_lbl = QLabel("<span style='color:#666'>By Juan Cabrera</span>")

        title_col.addWidget(name_lbl)
        title_col.addWidget(version_lbl)
        title_col.addWidget(author_lbl)
        title_col.addStretch()
        top.addLayout(title_col)
        top.addStretch()
        layout.addLayout(top)

        # ── Description ─────────────────────────────────────────────────────
        desc = QLabel(
            "QboToolbox connects QGIS to <b>KoboToolbox</b> via the v2 API, "
            "allowing you to browse geographic surveys, download submissions as "
            "vector layers (Point, LineString, Polygon), and open individual "
            "records for editing directly in the web form — all without leaving QGIS."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(desc)

        # ── Links ────────────────────────────────────────────────────────────
        links = QLabel(
            '<a href="https://github.com/jjcabrera20/QboToolbox">GitHub repository</a>'
            " &nbsp;·&nbsp; "
            '<a href="https://www.kobotoolbox.org">KoboToolbox</a>'
        )
        links.setOpenExternalLinks(True)
        links.setAlignment(Qt.AlignCenter)
        layout.addWidget(links)

        # ── OK button ────────────────────────────────────────────────────────
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
