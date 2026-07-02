import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from qgis.core import QgsSettings

KEY_URL = "QboToolbox/server_url"
KEY_TOKEN = "QboToolbox/api_token"
KEY_USERNAME = "QboToolbox/username"
KEY_PASSWORD = "QboToolbox/password"


class KoboAuthError(Exception):
    pass


class KoboAuth:
    @staticmethod
    def acquire_token(base_url: str, username: str, password: str) -> str:
        url = base_url.rstrip("/") + "/token/?format=json"
        credentials = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
        req = urllib.request.Request(
            url, headers={"Authorization": f"Basic {credentials}"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise KoboAuthError("Invalid username or password.")
            raise KoboAuthError(f"Token endpoint returned HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise KoboAuthError(f"Cannot reach server: {e.reason}")

        if "token" not in data:
            raise KoboAuthError("No token in response. Check credentials.")
        return data["token"]

    @staticmethod
    def save_credentials(base_url: str, token: str, username: str = "", password: str = "") -> None:
        s = QgsSettings()
        s.setValue(KEY_URL, base_url.rstrip("/"))
        s.setValue(KEY_TOKEN, token)
        if username:
            s.setValue(KEY_USERNAME, username)
        if password:
            s.setValue(KEY_PASSWORD, password)

    @staticmethod
    def load_credentials() -> tuple:
        """Returns (url, token, username, password)."""
        s = QgsSettings()
        return (
            s.value(KEY_URL, ""),
            s.value(KEY_TOKEN, ""),
            s.value(KEY_USERNAME, ""),
            s.value(KEY_PASSWORD, ""),
        )
