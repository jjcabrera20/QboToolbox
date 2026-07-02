import logging
import os
import threading

from qgis.core import QgsProject
from qgis.PyQt.QtCore import QTimer, Qt, pyqtSignal
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QLabel,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.api_client import KoboApiClient
from ..core.auth import KoboAuth, KoboAuthError
from ..core.geometry_parser import GeometryParser
from ..core.layer_builder import LayerBuilder
from .connection_widget import ConnectionWidget
from .forms_widget import FormsWidget

LOGGER = logging.getLogger(__name__)

# Warn the user before downloading more than this many submissions
LARGE_DOWNLOAD_THRESHOLD = 5000


class MainDock(QDockWidget):
    layers_added = pyqtSignal(list, object)  # (layers, client)

    # Internal signals — marshal results from background threads → main thread
    _assets_ready   = pyqtSignal(list)
    _assets_error   = pyqtSignal(str)
    _count_ready    = pyqtSignal(dict, int)   # asset, submission count
    _count_error    = pyqtSignal(str)
    _data_ready     = pyqtSignal(dict, list, list)  # asset_detail, geo_fields, submissions
    _download_error = pyqtSignal(str)
    _progress       = pyqtSignal(int)          # 0-100

    def __init__(self, iface, plugin, parent=None):
        super().__init__("QboToolbox", parent or iface.mainWindow())
        self.iface = iface
        self._plugin = plugin
        self._client = None
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setMinimumWidth(300)
        self._build_ui()
        self._wire_internal_signals()
        self._restore_credentials()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.conn_widget = ConnectionWidget()
        self.conn_widget.connect_requested.connect(self._on_connect_requested)
        self.tabs.addTab(self.conn_widget, "Connection")

        self.forms_widget = FormsWidget()
        self.forms_widget.download_requested.connect(self._on_download_requested)
        self.tabs.addTab(self.forms_widget, "Surveys")

        self.tabs.addTab(self._build_about_tab(), "About")

        layout.addWidget(self.tabs)
        self.setWidget(container)

    def _build_about_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        icon_path = os.path.join(os.path.dirname(__file__), "..", "resources", "icons", "icon_connect.png")
        icon_lbl = QLabel()
        pix = QPixmap(icon_path)
        if not pix.isNull():
            icon_lbl.setPixmap(pix.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        for text, center in [
            ("<b style='font-size:13pt'>QboToolbox</b>", True),
            ("<span style='color:#888'>Version 1.0.0</span>", True),
            (
                "Connects QGIS to <b>KoboToolbox</b> via the v2 API.<br>"
                "Browse geographic surveys, download submissions as<br>"
                "vector layers, and edit records directly in the webform.",
                True,
            ),
        ]:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            if center:
                lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl)

        div = QLabel()
        div.setFixedHeight(1)
        div.setStyleSheet("background:#cccccc; margin:4px 0;")
        layout.addWidget(div)

        author = QLabel("<b>Author:</b> Jorge J. Cabrera")
        author.setAlignment(Qt.AlignCenter)
        layout.addWidget(author)

        for href, label in [
            ("https://www.linkedin.com/in/info-management-gis", "linkedin.com/in/info-management-gis"),
            ("https://github.com/jjcabrera20/QboToolbox", "github.com/jjcabrera20/QboToolbox"),
        ]:
            lnk = QLabel(f'<a href="{href}">{label}</a>')
            lnk.setOpenExternalLinks(True)
            lnk.setAlignment(Qt.AlignCenter)
            layout.addWidget(lnk)

        layout.addStretch()
        return tab

    def _wire_internal_signals(self):
        self._assets_ready.connect(self._on_assets_fetched)
        self._assets_error.connect(self._on_fetch_error)
        self._count_ready.connect(self._on_count_ready)
        self._count_error.connect(self._on_download_error)
        self._data_ready.connect(self._on_data_ready)
        self._download_error.connect(self._on_download_error)
        self._progress.connect(self.forms_widget.set_progress)

    def _restore_credentials(self):
        url, token, username, password = KoboAuth.load_credentials()
        if url:
            self.conn_widget.load_saved(url, username, password)
        if url and token:
            self._client = KoboApiClient(url, token)
            self._plugin.set_client(self._client)

    # ── Connection ───────────────────────────────────────────────────────────

    def _on_connect_requested(self, url: str, username: str, password: str):
        try:
            token = KoboAuth.acquire_token(url, username, password)
        except KoboAuthError as e:
            self.conn_widget.set_status(str(e), error=True)
            self.conn_widget.reset_connect_button()
            return
        except Exception as e:
            self.conn_widget.set_status(f"Unexpected error: {e}", error=True)
            self.conn_widget.reset_connect_button()
            return

        KoboAuth.save_credentials(url, token, username, password)
        self._client = KoboApiClient(url, token)
        self._plugin.set_client(self._client)
        self.conn_widget.set_status("Connected! Loading surveys…")
        self.conn_widget.reset_connect_button()
        QTimer.singleShot(50, self._fetch_assets_bg)

    def _fetch_assets_bg(self):
        client = self._client

        def _run():
            try:
                self._assets_ready.emit(client.get_survey_assets())
            except Exception as e:
                self._assets_error.emit(str(e))

        threading.Thread(target=_run, daemon=True).start()

    def _on_assets_fetched(self, assets: list):
        active = [
            a for a in assets
            if a.get("deployment_status") == "deployed" and a.get("name", "").strip()
        ]
        self.forms_widget.set_assets(active)
        self.forms_widget.set_status(f"{len(active)} survey(s) found.")
        self.tabs.setCurrentIndex(1)
        self._plugin.set_assets({a["uid"]: a for a in active})

    def _on_fetch_error(self, message: str):
        self.conn_widget.set_status(f"Error loading surveys: {message}", error=True)
        LOGGER.error(message)

    # ── Download — phase 1: get count ────────────────────────────────────────

    def _on_download_requested(self, asset: dict):
        if self._client is None:
            self.forms_widget.set_status("Not connected.", error=True)
            self.forms_widget.hide_progress()
            return

        client = self._client
        self.forms_widget.set_status("Checking submission count…")
        self._progress.emit(5)

        def _run():
            try:
                count = client.get_submission_count(asset["uid"])
                self._count_ready.emit(asset, count)
            except Exception as e:
                self._count_error.emit(str(e))

        threading.Thread(target=_run, daemon=True).start()

    def _on_count_ready(self, asset: dict, count: int):
        """Called on main thread after submission count is known."""
        if count == 0:
            self.forms_widget.hide_progress()
            self.forms_widget.set_status("This survey has no submissions yet.", error=True)
            return

        if count > LARGE_DOWNLOAD_THRESHOLD:
            reply = QMessageBox.question(
                self,
                "QboToolbox — Large Dataset",
                f"This survey has <b>{count:,} submissions</b>.<br><br>"
                f"Downloading and rendering {count:,} features may take a while "
                f"and use significant memory.<br><br>"
                "Do you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                self.forms_widget.hide_progress()
                self.forms_widget.set_status(f"{count:,} submissions — download cancelled.")
                return

        self.forms_widget.set_status(f"Downloading {count:,} submissions…")
        self._start_download(asset, count)

    # ── Download — phase 2: fetch data ───────────────────────────────────────

    def _start_download(self, asset: dict, total_count: int):
        client = self._client

        def _progress_cb(downloaded: int, total: int):
            # Maps download progress to 10–75% of the overall bar
            if total > 0:
                pct = 10 + int(65 * downloaded / total)
                self._progress.emit(pct)

        def _run():
            try:
                self._progress.emit(10)
                asset_detail = client.get_asset_detail(asset["uid"])
                self._progress.emit(12)

                geo_fields = GeometryParser.detect_geo_fields(asset_detail)
                if not geo_fields:
                    raise ValueError(
                        "No geographic fields (geopoint/geotrace/geoshape) found in this survey."
                    )
                self._progress.emit(15)

                submissions = client.get_submissions(
                    asset["uid"],
                    page_size=5000,
                    progress_cb=_progress_cb,
                )
                # emit raw data — QGIS objects must be built on the main thread
                self._data_ready.emit(asset_detail, geo_fields, submissions)
            except Exception as e:
                self._download_error.emit(str(e))

        threading.Thread(target=_run, daemon=True).start()

    # ── Download — phase 3: build layers on main thread ──────────────────────

    def _on_data_ready(self, asset_detail: dict, geo_fields: list, submissions: list):
        n = len(submissions)
        self.forms_widget.set_status(f"Building layers for {n:,} submissions…")
        self._progress.emit(75)

        def _layer_progress(frac: float):
            # Maps layer-building progress to 75–98%
            self._progress.emit(75 + int(23 * frac))

        layers = LayerBuilder.build_layers(asset_detail, geo_fields, submissions, _layer_progress)
        self._progress.emit(100)
        self.forms_widget.hide_progress()

        if not layers:
            self.forms_widget.set_status("No features with valid geometry found.", error=True)
            return

        for layer in layers:
            QgsProject.instance().addMapLayer(layer)
        self.iface.setActiveLayer(layers[0])

        sub_count = len(submissions)
        if len(layers) == 1:
            status = f"1 layer added — {layers[0].featureCount():,} features."
        else:
            names = ", ".join(l.name().split(" — ")[-1] for l in layers)
            status = (
                f"{len(layers)} layers added from {sub_count:,} submissions "
                f"({names} — one layer per geographic field)."
            )
        self.forms_widget.set_status(status)
        self.layers_added.emit(layers, self._client)

    def _on_download_error(self, message: str):
        self.forms_widget.hide_progress()
        self.forms_widget.set_status(f"Error: {message}", error=True)
        LOGGER.error(message)
