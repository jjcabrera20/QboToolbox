# QboToolbox

A QGIS plugin that connects to **KoboToolbox** via the v2 API, allowing you to browse geographic surveys, download submissions as vector layers, and edit records directly in the web form — without leaving QGIS.

---

## Features

- **Connect** to any KoboToolbox server using your username and password
- **Browse** all active deployed surveys in your account
- **Download** geographic submissions as QGIS vector layers (Point, LineString, Polygon)
- **Edit** selected features directly in the KoboToolbox web form (Enketo)
- **Refresh** layers to pull the latest submissions
- Credentials (URL, username, password) saved and restored between sessions
- Dockable panel with Connection, Surveys, and About tabs
- Three toolbar buttons: Connect, Edit in Webform, Refresh Layer

---

## Requirements

- QGIS 3.22 or later
- A KoboToolbox account (hosted on kf.kobotoolbox.org or a self-hosted instance)

---

## Installation

### From ZIP (recommended)

1. Download `QboToolbox.zip` from the [Releases](https://github.com/jjcabrera20/QboToolbox/releases) page
2. Open QGIS → **Plugins** → **Manage and Install Plugins**
3. Click **Install from ZIP**
4. Select the downloaded `QboToolbox.zip` and click **Install Plugin**

### Manual

1. Clone or download this repository
2. Copy the `QboToolbox` folder into your QGIS plugins directory:
   - **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux/Mac:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
3. Restart QGIS and enable the plugin from **Plugins → Manage and Install Plugins**

---

## Usage

### 1. Connect to KoboToolbox

Click the **Connect** toolbar button (or go to **Plugins → QboToolbox → Connect to KoboToolbox**) to open the dock panel.

Enter your:
- **Server URL** — e.g. `https://kf.kobotoolbox.org`
- **Username**
- **Password** (use the eye button to reveal)

Click **Connect**. Your credentials are saved for future sessions.

### 2. Download a Survey

Switch to the **Surveys** tab. Select a survey from the list and click **Download Selected**.

Layers are added to the QGIS map canvas — one layer per geographic field (geopoint → Point, geotrace → LineString, geoshape → Polygon).

### 3. Edit a Feature in the Webform

1. Select one or more features on the map canvas
2. Click the **Edit in Webform** toolbar button

The KoboToolbox edit form opens in your default browser. If prompted, log in with your KoboToolbox credentials. Your edits are saved directly to the KoboToolbox server.

> **Note:** A record locked by an active editing session cannot be opened again until the form is closed or ~30 seconds have passed.

### 4. Refresh a Layer

With a KoboToolbox layer active, click the **Refresh Layer** toolbar button to re-download the latest submissions and replace the layer on the map.

---

## API

This plugin uses the **KoboToolbox API v2** exclusively:

| Action | Endpoint |
|---|---|
| Authenticate | `GET /token/?format=json` (Basic Auth) |
| List surveys | `GET /api/v2/assets/?asset_type=survey` |
| Asset detail | `GET /api/v2/assets/{uid}/` |
| Download data | `GET /api/v2/assets/{uid}/data/` |
| Edit URL | `GET /api/v2/assets/{uid}/data/{id}/enketo/edit/?return_url=false` |

---

## Author

**Jorge J. Cabrera**
[linkedin.com/in/info-management-gis](https://www.linkedin.com/in/info-management-gis)
[jorge.cabrera.chiriboga@gmail.com](mailto:jorge.cabrera.chiriboga@gmail.com)

---

## License

This project is licensed under the GNU General Public License v2 or later.
