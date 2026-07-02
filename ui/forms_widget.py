from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class FormsWidget(QWidget):
    download_requested = pyqtSignal(dict)  # asset dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._assets = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        layout.addWidget(QLabel("Geographic surveys:"))

        self.list_widget = QListWidget()
        self.list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.list_widget)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.download_btn = QPushButton("Download Selected")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._on_download_clicked)
        layout.addWidget(self.download_btn)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def set_assets(self, assets: list):
        self._assets = assets
        self.list_widget.clear()
        for asset in assets:
            count = asset.get("deployment__submission_count", 0)
            name = asset.get("name", asset.get("uid", "?"))
            item = QListWidgetItem(f"{name}  [{count} submissions]")
            item.setData(0x0100, asset)  # Qt.UserRole
            self.list_widget.addItem(item)
        self.download_btn.setEnabled(len(assets) > 0)

    def _on_download_clicked(self):
        selected = self.list_widget.selectedItems()
        if not selected:
            self.set_status("Select a survey from the list first.", error=True)
            return
        asset = selected[0].data(0x0100)
        self.download_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.set_status("Downloading…")
        self.download_requested.emit(asset)

    def set_progress(self, value):
        self.progress_bar.setValue(int(value))

    def hide_progress(self):
        self.progress_bar.setVisible(False)
        self.download_btn.setEnabled(True)

    def set_status(self, message: str, error: bool = False):
        color = "red" if error else "green"
        self.status_label.setText(f'<span style="color:{color}">{message}</span>')
