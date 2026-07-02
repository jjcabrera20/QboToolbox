import json
import urllib.error
import urllib.parse
import urllib.request


class KoboApiError(Exception):
    pass


class KoboApiClient:
    def __init__(self, base_url: str, token: str):
        self._base_url = base_url.rstrip("/")
        self._token = token

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self._base_url}{path}"
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"Token {self._token}"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise KoboApiError(f"HTTP {e.code} for {path}: {e.reason}")
        except urllib.error.URLError as e:
            raise KoboApiError(f"Request failed for {path}: {e.reason}")

    def _get_paginated(self, path: str, params: dict = None) -> list:
        params = dict(params or {})
        params["format"] = "json"
        results = []
        # First page via path
        data = self._get(path, params)
        results.extend(data.get("results", []))
        next_url = data.get("next")
        # Subsequent pages via full URL
        while next_url:
            req = urllib.request.Request(
                next_url, headers={"Authorization": f"Token {self._token}"}
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.URLError as e:
                raise KoboApiError(f"Pagination request failed: {e.reason}")
            results.extend(data.get("results", []))
            next_url = data.get("next")
        return results

    def get_survey_assets(self) -> list:
        return self._get_paginated("/api/v2/assets/", {"asset_type": "survey"})

    def get_asset_detail(self, uid: str) -> dict:
        return self._get(f"/api/v2/assets/{uid}/", {"format": "json"})

    def get_submissions(self, uid: str) -> list:
        return self._get_paginated(f"/api/v2/assets/{uid}/data/")

    def get_enketo_edit_url(self, uid: str, submission_id) -> str:
        data = self._get(
            f"/api/v2/assets/{uid}/data/{submission_id}/enketo/edit/",
            {"return_url": "false"},
        )
        if "url" not in data:
            raise KoboApiError("No edit URL returned by Enketo endpoint")
        return data["url"]
