import logging
import threading

from qgis.core import QgsProject
from qgis.PyQt.QtCore import QTimer, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDockWidget,
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


class MainDock(QDockWidget):
    layers_added = pyqtSignal(list, object)  # (layers, client)

    # Internal signals used to marshal results from background thread → main thread
    _assets_ready = pyqtSignal(list)
    _assets_error = pyqtSignal(str)
    _data_ready = pyqtSignal(dict, list, list)  # asset_detail, geo_fields, submissions
    _download_error = pyqtSignal(str)
    _progress = pyqtSignal(int)

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

        layout.addWidget(self.tabs)
        self.setWidget(container)

    def _wire_internal_signals(self):
        self._assets_ready.connect(self._on_assets_fetched)
        self._assets_error.connect(self._on_fetch_error)
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

    # ---- Connection ----

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
        # Defer the network call so the status message paints first
        QTimer.singleShot(50, self._fetch_assets_bg)

    def _fetch_assets_bg(self):
        client = self._client

        def _run():
            try:
                assets = client.get_survey_assets()
                self._assets_ready.emit(assets)
            except Exception as e:
                self._assets_error.emit(str(e))

        threading.Thread(target=_run, daemon=True).start()

    def _on_assets_fetched(self, assets: list):
        self.forms_widget.set_assets(assets)
        self.forms_widget.set_status(f"{len(assets)} survey(s) found.")
        self.tabs.setCurrentIndex(1)
        self._plugin.set_assets({a["uid"]: a for a in assets})

    def _on_fetch_error(self, message: str):
        self.conn_widget.set_status(f"Error loading surveys: {message}", error=True)
        LOGGER.error(message)

    # ---- Download ----

    def _on_download_requested(self, asset: dict):
        if self._client is None:
            self.forms_widget.set_status("Not connected.", error=True)
            self.forms_widget.hide_progress()
            return
        client = self._client

        def _run():
            try:
                self._progress.emit(10)
                asset_detail = client.get_asset_detail(asset["uid"])
                self._progress.emit(20)
                geo_fields = GeometryParser.detect_geo_fields(asset_detail)
                if not geo_fields:
                    raise ValueError(
                        "No geographic fields (geopoint/geotrace/geoshape) found in this survey."
                    )
                self._progress.emit(35)
                submissions = client.get_submissions(asset["uid"])
                self._progress.emit(90)
                # emit raw data — QGIS objects must be built on the main thread
                self._data_ready.emit(asset_detail, geo_fields, submissions)
            except Exception as e:
                self._download_error.emit(str(e))

        threading.Thread(target=_run, daemon=True).start()

    def _on_data_ready(self, asset_detail: dict, geo_fields: list, submissions: list):
        # Build QGIS layers here on the main thread to preserve object types
        layers = LayerBuilder.build_layers(asset_detail, geo_fields, submissions)
        self.forms_widget.hide_progress()
        if not layers:
            self.forms_widget.set_status("No features with valid geometry found.", error=True)
            return
        for layer in layers:
            QgsProject.instance().addMapLayer(layer)
        self.iface.setActiveLayer(layers[0])
        self.forms_widget.set_status(f"{len(layers)} layer(s) added to the map.")
        self.layers_added.emit(layers, self._client)

    def _on_download_error(self, message: str):
        self.forms_widget.hide_progress()
        self.forms_widget.set_status(f"Error: {message}", error=True)
        LOGGER.error(message)
