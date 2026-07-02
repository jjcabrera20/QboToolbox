import logging

from qgis.core import QgsTask
from qgis.PyQt.QtCore import pyqtSignal

from ..core.api_client import KoboApiClient

LOGGER = logging.getLogger(__name__)


class FetchAssetsTask(QgsTask):
    assets_fetched = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, client: KoboApiClient):
        super().__init__("Fetching KoboToolbox surveys", QgsTask.CanCancel)
        self._client = client
        self.assets = []
        self.exception = None

    def run(self) -> bool:
        try:
            self.assets = self._client.get_survey_assets()
            return True
        except Exception as e:
            self.exception = e
            return False

    def finished(self, result: bool) -> None:
        if result:
            self.assets_fetched.emit(self.assets)
        else:
            msg = str(self.exception) if self.exception else "Task was cancelled"
            self.error_occurred.emit(msg)
