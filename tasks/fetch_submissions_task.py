import logging

from qgis.core import QgsMessageLog, QgsTask
from qgis.PyQt.QtCore import pyqtSignal

from ..core.api_client import KoboApiClient
from ..core.geometry_parser import GeometryParser

LOGGER = logging.getLogger(__name__)
TAG = "QboToolbox"


class FetchSubmissionsTask(QgsTask):
    # Emit raw data so the receiver can build QGIS objects on the main thread
    data_ready = pyqtSignal(dict, list, list)  # asset_detail, geo_fields, submissions
    error_occurred = pyqtSignal(str)

    def __init__(self, client: KoboApiClient, asset: dict):
        name = asset.get("name", asset.get("uid", "survey"))
        super().__init__(f"Downloading '{name}'", QgsTask.CanCancel)
        self._client = client
        self._asset = asset
        self._result_data = None
        self.exception = None
        self._debug_info = []

    def run(self) -> bool:
        try:
            uid = self._asset["uid"]
            self.setProgress(10)

            asset_detail = self._client.get_asset_detail(uid)
            self.setProgress(20)

            survey_items = asset_detail.get("content", {}).get("survey", [])
            self._debug_info.append(f"Survey items: {len(survey_items)}")

            geo_fields = GeometryParser.detect_geo_fields(asset_detail)
            self._debug_info.append(f"Geo fields found: {[f.field_name for f in geo_fields]}")

            if not geo_fields:
                raise ValueError(
                    "No geographic fields (geopoint/geotrace/geoshape) detected. "
                    "See QGIS Log Messages → QboToolbox for field types."
                )

            self.setProgress(30)
            submissions = self._client.get_submissions(uid)
            self._debug_info.append(f"Submissions downloaded: {len(submissions)}")
            self.setProgress(100)

            self._result_data = (asset_detail, geo_fields, submissions)
            return True
        except Exception as e:
            self.exception = e
            return False

    def finished(self, result: bool) -> None:
        for line in self._debug_info:
            QgsMessageLog.logMessage(line, TAG)
        if result and self._result_data:
            self.data_ready.emit(*self._result_data)
        else:
            msg = str(self.exception) if self.exception else "Task was cancelled"
            QgsMessageLog.logMessage(f"Task failed: {msg}", TAG)
            self.error_occurred.emit(msg)
