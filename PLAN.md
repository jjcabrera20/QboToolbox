# QboToolbox — Architecture & Development Notes

Reference document for future development. Captures design decisions, known gotchas, and the overall structure.

---

## Plugin Structure

```
QboToolbox/
├── __init__.py                  # classFactory → Plugin
├── plugin.py                    # Toolbar actions, layer/selection state, edit/refresh logic
├── metadata.txt                 # QGIS plugin manifest
├── core/
│   ├── auth.py                  # Token acquisition (Basic Auth), QgsSettings persistence
│   ├── api_client.py            # All HTTP via urllib; KoboToolbox API v2
│   ├── geometry_parser.py       # Detect geo fields; parse geopoint/geotrace/geoshape
│   └── layer_builder.py         # Build QGIS memory layers from raw submissions
├── tasks/
│   ├── fetch_assets_task.py     # QgsTask: list survey assets
│   └── fetch_submissions_task.py # QgsTask: download data (emits raw data, not layers)
├── ui/
│   ├── main_dialog.py           # MainDock (QDockWidget): 3-tab panel
│   ├── connection_widget.py     # Login form with reveal-password toggle + icon header
│   ├── forms_widget.py          # Survey list + download button + progress bar
│   └── about_dialog.py          # Standalone About dialog (also accessible from menu)
└── resources/
    └── icons/
        ├── qbo_toolbox.png      # Plugin icon (menu, About dialog)
        ├── icon_connect.png     # Connect toolbar button + Connection tab header
        ├── icon_edit.png        # Edit in Webform toolbar button
        └── icon_refresh.png     # Refresh Layer toolbar button
```

---

## Key Design Decisions

### Threading model
- **HTTP calls** use `urllib` (not `QgsBlockingNetworkRequest` — unreliable from background threads).
- `MainDock` uses `threading.Thread` + internal `pyqtSignal` for asset listing and data download.
- `FetchSubmissionsTask` (QgsTask) is used only for the Refresh Layer action.
- **Critical:** `QgsVectorLayer` and `QgsFeature` must be created on the **main thread**. Tasks emit raw `(asset_detail, geo_fields, submissions)` via `data_ready` signal; `LayerBuilder.build_layers()` is called in the signal handler on the main thread.
- Keep a Python reference (`self._active_task = task`) to prevent garbage collection before QgsTask signals fire.

### Authentication
- `GET /token/?format=json` with `Authorization: Basic base64(user:pass)` header.
- Token stored in `QgsSettings` under `QboToolbox/api_token`.
- Username and password also stored (`QboToolbox/username`, `QboToolbox/password`) and restored on startup.
- All subsequent API calls use `Authorization: Token {token}`.

### Geometry parsing
- KoboToolbox stores geopoint as `"lat lon alt acc"` — **must swap to `QgsPointXY(lon, lat)`**.
- Geotrace: semicolon-separated `"lat lon alt acc"` points → `fromPolylineXY`.
- Geoshape: same as geotrace + explicit ring closure if `points[0] != points[-1]`.

### QgsField type constants (version-safe)
```python
try:
    from qgis.PyQt.QtCore import QMetaType
    _INT = QMetaType.Type.Int
    _STR = QMetaType.Type.QString
except (ImportError, AttributeError):
    from qgis.PyQt.QtCore import QVariant
    _INT = QVariant.Int
    _STR = QVariant.String
```
`QVariant` constants deprecated in QGIS 3.38+ / Qt6. The try/except handles both.

### Enketo / Webform editing
- Call `GET /api/v2/assets/{uid}/data/{id}/enketo/edit/?return_url=false` with API token.
- Response: `{"url": "https://ee.kobotoolbox.org/edit/{token}?instance_id=...&return_url=false"}`.
- Open the returned URL directly via `QDesktopServices.openUrl()` — the URL contains its own session token and works without browser auth.
- HTTP 405 = record locked by active Enketo session; wait ~30 seconds and retry.

### Survey filtering
- API returns all assets including drafts, archived, and soft-deleted.
- Filter: `deployment_status == "deployed"` AND `name` is non-empty.

### Layer identification
- Custom property `KOBO_LAYER_PROPERTY = "kobo_asset_uid"` set on each layer.
- `LayerBuilder.is_kobo_layer(layer)` and `get_asset_uid(layer)` used throughout.

---

## API Endpoints (v2)

| Purpose | Method | Endpoint |
|---|---|---|
| Token | GET | `/token/?format=json` |
| List surveys | GET | `/api/v2/assets/?asset_type=survey&format=json` |
| Asset detail | GET | `/api/v2/assets/{uid}/?format=json` |
| Submissions | GET | `/api/v2/assets/{uid}/data/?format=json` |
| Edit URL | GET | `/api/v2/assets/{uid}/data/{id}/enketo/edit/?return_url=false` |

Pagination: loop on the `next` field in responses until `null`.

---

## Known Issues & Workarounds

| Issue | Cause | Fix |
|---|---|---|
| QgsVectorLayer downcast to QObject via pyqtSignal | QGIS objects created off main thread lose their type | Build layers in main-thread signal handler, pass raw data through signals |
| QgsTask GC before signals fire | Python has no reference to task | Store `self._active_task = task` |
| Stale `.pyc` after signature changes | QGIS bytecode cache | Delete all `__pycache__/` dirs; `.gitignore` now excludes them |
| HTTP 405 on Enketo re-open | KoboToolbox locks record during active session | Show message; user must close form or wait ~30s |

---

## Possible Future Enhancements

- Filter/search box in Surveys list
- Display download progress per submission page
- Attribute table panel inside the dock
- Support for repeat groups in form schema
- Multi-server profile switching
- Offline/cached layer support
