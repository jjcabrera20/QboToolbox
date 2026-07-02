import os

from qgis.core import Qgis, QgsApplication, QgsProject
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox

from .core.layer_builder import LayerBuilder
from .tasks.fetch_submissions_task import FetchSubmissionsTask

WEBFORM_CONFIRM_THRESHOLD = 5


class Plugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = "&QboToolbox"
        self._dock = None
        self._client = None
        self._assets_by_uid = {}
        self._connected_layer_ids = set()

    # ---- QGIS lifecycle ----

    def initGui(self):
        icons = os.path.join(self.plugin_dir, "resources", "icons")

        self._action_connect = self._make_toolbar_action(
            os.path.join(icons, "icon_connect.png"),
            "Connect to KoboToolbox",
            self._open_dock,
            enabled=True,
        )
        self._action_edit = self._make_toolbar_action(
            os.path.join(icons, "icon_edit.png"),
            "Edit Feature in Webform",
            self._edit_feature,
            enabled=False,
        )
        self._action_refresh = self._make_toolbar_action(
            os.path.join(icons, "icon_refresh.png"),
            "Refresh Layer",
            self._refresh_layer,
            enabled=False,
        )

        # About entry in plugin menu (no toolbar icon)
        self._action_about = QAction(
            QIcon(os.path.join(icons, "qbo_toolbox.png")),
            "About QboToolbox",
            self.iface.mainWindow(),
        )
        self._action_about.triggered.connect(self._show_about)
        self.iface.addPluginToMenu(self.menu, self._action_about)
        self.actions.append(self._action_about)

        self.iface.currentLayerChanged.connect(self._on_layer_changed)

    def unload(self):
        self.iface.currentLayerChanged.disconnect(self._on_layer_changed)
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        self.actions.clear()
        if self._dock:
            self.iface.removeDockWidget(self._dock)
            self._dock.deleteLater()
            self._dock = None

    # ---- Toolbar actions ----

    def _make_toolbar_action(self, icon_path: str, text: str, callback, enabled: bool) -> QAction:
        action = QAction(QIcon(icon_path), text, self.iface.mainWindow())
        action.triggered.connect(callback)
        action.setEnabled(enabled)
        self.iface.addPluginToMenu(self.menu, action)
        self.iface.addToolBarIcon(action)
        self.actions.append(action)
        return action

    # ---- Dock widget ----

    def _open_dock(self):
        if self._dock is None:
            from .ui.main_dialog import MainDock
            self._dock = MainDock(self.iface, self)
            self._dock.layers_added.connect(self._on_layers_added)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self._dock)
        self._dock.show()
        self._dock.raise_()

    # ---- About ----

    def _show_about(self):
        from .ui.about_dialog import AboutDialog
        dlg = AboutDialog(self.iface.mainWindow())
        dlg.exec_()

    # ---- Called by the dock after login / download ----

    def set_client(self, client):
        self._client = client

    def set_assets(self, assets_by_uid: dict):
        self._assets_by_uid = assets_by_uid

    def _on_layers_added(self, layers, client):
        self._client = client
        layer = self.iface.activeLayer()
        self._on_layer_changed(layer)

    # ---- Layer / selection state management ----

    def _on_layer_changed(self, layer):
        is_kobo = LayerBuilder.is_kobo_layer(layer)
        self._action_refresh.setEnabled(is_kobo)
        has_sel = is_kobo and layer.selectedFeatureCount() > 0
        self._action_edit.setEnabled(has_sel)
        if is_kobo and layer.id() not in self._connected_layer_ids:
            layer.selectionChanged.connect(self._on_selection_changed)
            self._connected_layer_ids.add(layer.id())

    def _on_selection_changed(self, *args):
        layer = self.iface.activeLayer()
        has_sel = LayerBuilder.is_kobo_layer(layer) and layer.selectedFeatureCount() > 0
        self._action_edit.setEnabled(has_sel)

    # ---- Edit in Webform ----

    def _edit_feature(self):
        if self._client is None:
            QMessageBox.warning(
                self.iface.mainWindow(), "QboToolbox",
                "Not connected. Open the Connect panel first."
            )
            return
        layer = self.iface.activeLayer()
        if not LayerBuilder.is_kobo_layer(layer):
            QMessageBox.warning(self.iface.mainWindow(), "QboToolbox",
                                "Active layer is not a KoboToolbox layer.")
            return
        uid = LayerBuilder.get_asset_uid(layer)
        features = layer.selectedFeatures()
        if not features:
            QMessageBox.information(self.iface.mainWindow(), "QboToolbox",
                                    "Select one or more features on the map first.")
            return
        if len(features) > WEBFORM_CONFIRM_THRESHOLD:
            reply = QMessageBox.question(
                self.iface.mainWindow(), "QboToolbox",
                f"Open {len(features)} records in the webform?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        from .core.api_client import KoboApiError

        opened = 0
        errors = []

        for feat in features:
            kobo_id = feat.attribute("kobo_id")
            if not kobo_id:
                continue
            try:
                url = self._client.get_enketo_edit_url(uid, int(kobo_id))
                QDesktopServices.openUrl(QUrl(url))
                opened += 1
            except KoboApiError as e:
                msg = str(e)
                if "405" in msg or "already being edited" in msg.lower():
                    errors.append(
                        f"Record {kobo_id} is locked (being edited). "
                        "Wait ~30 seconds and try again."
                    )
                else:
                    errors.append(f"Record {kobo_id}: {msg}")

        if errors:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "QboToolbox — Webform",
                "\n".join(errors),
            )
        if opened:
            self.iface.messageBar().pushMessage(
                "QboToolbox",
                f"Webform opened for {opened} record(s). Submit the form to save changes.",
                level=Qgis.Info,
                duration=7,
            )

    # ---- Refresh layer ----

    def _refresh_layer(self):
        if self._client is None:
            QMessageBox.warning(self.iface.mainWindow(), "QboToolbox",
                                "Not connected. Open the Connect panel first.")
            return
        layer = self.iface.activeLayer()
        if not LayerBuilder.is_kobo_layer(layer):
            return
        uid = LayerBuilder.get_asset_uid(layer)
        asset = self._assets_by_uid.get(uid)
        if asset is None:
            QMessageBox.warning(self.iface.mainWindow(), "QboToolbox",
                                "Survey metadata not found. Re-download from the Surveys tab.")
            return

        self._layers_to_replace = [
            lyr for lyr in QgsProject.instance().mapLayers().values()
            if LayerBuilder.get_asset_uid(lyr) == uid
        ]

        task = FetchSubmissionsTask(self._client, asset)
        task.data_ready.connect(self._on_refresh_data_ready)
        task.error_occurred.connect(lambda msg: QMessageBox.warning(
            self.iface.mainWindow(), "QboToolbox", f"Refresh failed: {msg}"
        ))
        self._active_task = task
        QgsApplication.taskManager().addTask(task)

    def _on_refresh_data_ready(self, asset_detail: dict, geo_fields: list, submissions: list):
        from .core.layer_builder import LayerBuilder as LB
        new_layers = LB.build_layers(asset_detail, geo_fields, submissions)
        project = QgsProject.instance()
        for old in getattr(self, "_layers_to_replace", []):
            project.removeMapLayer(old.id())
        self._layers_to_replace = []
        for layer in new_layers:
            project.addMapLayer(layer)
        if new_layers:
            self.iface.setActiveLayer(new_layers[0])
            self._on_layer_changed(new_layers[0])
