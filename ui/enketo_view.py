from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtWidgets import (
    QDialog, QLabel, QProgressBar, QToolBar, QVBoxLayout,
)

try:
    from qgis.PyQt.QtWebEngineWidgets import (
        QWebEnginePage,
        QWebEngineProfile,
        QWebEngineView,
    )
    try:
        # Qt 5.13+
        from qgis.PyQt.QtWebEngineWidgets import QWebEngineUrlRequestInterceptor
    except ImportError:
        from qgis.PyQt.QtWebEngineCore import QWebEngineUrlRequestInterceptor
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False


if HAS_WEBENGINE:
    class _AuthInterceptor(QWebEngineUrlRequestInterceptor):
        """Inject Authorization header for all requests to the KoboToolbox host."""

        def __init__(self, token: str, kobo_host: str, parent=None):
            super().__init__(parent)
            self._header = f"Token {token}".encode("utf-8")
            self._kobo_host = kobo_host

        def interceptRequest(self, info):
            host = info.requestUrl().host()
            if self._kobo_host and (self._kobo_host in host or host in self._kobo_host):
                info.setHttpHeader(b"Authorization", self._header)


class EnketoView(QDialog):
    def __init__(self, enketo_url: str, token: str, kobo_base_url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KoboToolbox — Edit Form")
        self.resize(1100, 750)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if not HAS_WEBENGINE:
            self._build_browser_fallback(layout, enketo_url, kobo_base_url)
            return

        # Toolbar: back / forward / reload
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self._back_action = toolbar.addAction("◀")
        self._fwd_action = toolbar.addAction("▶")
        self._reload_action = toolbar.addAction("↺")
        layout.addWidget(toolbar)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setMaximumHeight(4)
        self._progress.setTextVisible(False)
        layout.addWidget(self._progress)

        # Web view with isolated profile + auth interceptor
        kobo_host = QUrl(kobo_base_url).host()
        self._profile = QWebEngineProfile("qbotoolbox_enketo", self)
        self._interceptor = _AuthInterceptor(token, kobo_host, self._profile)
        self._profile.setUrlRequestInterceptor(self._interceptor)

        self._view = QWebEngineView(self)
        self._page = QWebEnginePage(self._profile, self._view)
        self._view.setPage(self._page)

        layout.addWidget(self._view)

        # Wire toolbar
        self._back_action.triggered.connect(self._view.back)
        self._fwd_action.triggered.connect(self._view.forward)
        self._reload_action.triggered.connect(self._view.reload)
        self._view.loadProgress.connect(self._progress.setValue)
        self._view.loadFinished.connect(lambda _: self._progress.setVisible(False))
        self._view.loadStarted.connect(lambda: self._progress.setVisible(True))

        self._view.load(QUrl(enketo_url))

    def _build_browser_fallback(self, layout, enketo_url: str, kobo_base_url: str):
        from qgis.PyQt.QtCore import QTimer
        from qgis.PyQt.QtGui import QDesktopServices
        from qgis.PyQt.QtWidgets import (
            QCheckBox, QHBoxLayout, QPushButton, QSizePolicy, QSpacerItem,
        )

        self.resize(500, 230)

        info = QLabel(
            "<b>Editing a KoboToolbox submission requires a browser session.</b><br><br>"
            "Your browser's KoboToolbox login page is opening now.<br>"
            "Sign in, then check the box below and click <i>Open Form</i>."
        )
        info.setWordWrap(True)
        info.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        info.setContentsMargins(12, 12, 12, 4)
        layout.addWidget(info)

        logged_in_cb = QCheckBox("  I have logged in to KoboToolbox in my browser")
        logged_in_cb.setContentsMargins(12, 0, 12, 0)
        layout.addWidget(logged_in_cb)

        layout.addSpacerItem(QSpacerItem(0, 8, QSizePolicy.Minimum, QSizePolicy.Fixed))

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(12, 0, 12, 12)

        login_url = kobo_base_url.rstrip("/") + "/accounts/login/"

        reopen_btn = QPushButton("Re-open Login Page")
        reopen_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(login_url)))
        btn_row.addWidget(reopen_btn)

        def _open_form():
            QDesktopServices.openUrl(QUrl(enketo_url))
            self.accept()

        open_btn = QPushButton("Open Form")
        open_btn.setDefault(True)
        open_btn.setEnabled(False)
        open_btn.clicked.connect(_open_form)
        btn_row.addWidget(open_btn)

        logged_in_cb.toggled.connect(open_btn.setEnabled)
        layout.addLayout(btn_row)

        # Auto-open the login page as soon as the dialog is shown
        QTimer.singleShot(200, lambda: QDesktopServices.openUrl(QUrl(login_url)))
