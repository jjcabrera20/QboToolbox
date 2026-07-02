import json
import logging
from typing import Callable, List, Optional

from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QCoreApplication

# Version-safe field type constants (QVariant deprecated in QGIS 3.38+/Qt6)
try:
    from qgis.PyQt.QtCore import QMetaType
    _INT = QMetaType.Type.Int
    _STR = QMetaType.Type.QString
except (ImportError, AttributeError):
    from qgis.PyQt.QtCore import QVariant
    _INT = QVariant.Int
    _STR = QVariant.String

from .geometry_parser import GeoField, GeometryParser

LOGGER = logging.getLogger(__name__)
KOBO_LAYER_PROPERTY = "kobo_asset_uid"
INTERNAL_SKIP = {"_geolocation", "_validation_status", "_notes", "_tags", "_submitted_by"}
CHUNK_SIZE = 500  # features inserted per batch to avoid freezing the main thread


class LayerBuilder:
    @staticmethod
    def build_layers(
        asset: dict,
        geo_fields: List[GeoField],
        submissions: list,
        progress_cb: Callable[[float], None] = None,
    ) -> List[QgsVectorLayer]:
        """Build one memory layer per geo field.

        progress_cb receives a float 0.0–1.0 reflecting overall feature-insertion
        progress across all layers. Called on the main thread; Qt events are
        processed between chunks so the UI stays responsive.
        """
        uid = asset.get("uid", "")
        asset_name = asset.get("name", uid)
        geo_field_names = {f.field_name for f in geo_fields}
        fields = LayerBuilder._build_fields(submissions, geo_field_names)
        layers = []
        n_layers = len(geo_fields)

        for layer_idx, geo_field in enumerate(geo_fields):
            layer_name = f"{asset_name} — {geo_field.label or geo_field.field_name}"
            layer = QgsVectorLayer(f"{geo_field.wkt_type}?crs=EPSG:4326", layer_name, "memory")
            dp = layer.dataProvider()
            dp.addAttributes(fields)
            layer.updateFields()

            def _feat_progress(done: int, total: int, _li: int = layer_idx):
                if progress_cb and total > 0:
                    overall = (_li + done / total) / n_layers
                    progress_cb(overall)

            LayerBuilder._add_features(layer, geo_field, submissions, layer.fields(), _feat_progress)
            layer.setCustomProperty(KOBO_LAYER_PROPERTY, uid)
            layers.append(layer)

        return layers

    @staticmethod
    def _build_fields(submissions: list, geo_field_names: set) -> List[QgsField]:
        if not submissions:
            return []
        first = submissions[0]
        fields = []
        seen = {"_id", "_uuid", "kobo_id", "kobo_uuid"}
        fields.append(QgsField("kobo_id", _INT))
        fields.append(QgsField("kobo_uuid", _STR))
        for key in first.keys():
            if key in seen or key in geo_field_names or key in INTERNAL_SKIP or key.startswith("_"):
                seen.add(key)
                continue
            seen.add(key)
            fields.append(QgsField(key[:50], _STR))
        return fields

    @staticmethod
    def _add_features(
        layer: QgsVectorLayer,
        geo_field: GeoField,
        submissions: list,
        qgs_fields: QgsFields,
        progress_cb: Callable[[int, int], None] = None,
    ) -> None:
        # Build all feature objects first (pure Python, very fast)
        features = []
        for sub in submissions:
            raw_geo = sub.get(geo_field.field_name)
            if not raw_geo:
                continue
            geom = GeometryParser.parse_geometry(str(raw_geo), geo_field.wkt_type)
            if geom is None or geom.isEmpty():
                continue
            feat = QgsFeature(qgs_fields)
            feat.setGeometry(geom)
            try:
                feat.setAttribute("kobo_id", int(sub.get("_id", 0)))
            except (TypeError, ValueError):
                feat.setAttribute("kobo_id", 0)
            feat.setAttribute("kobo_uuid", str(sub.get("_uuid", "")))
            for field in qgs_fields:
                fname = field.name()
                if fname in ("kobo_id", "kobo_uuid"):
                    continue
                val = sub.get(fname)
                if val is None:
                    feat.setAttribute(fname, None)
                elif isinstance(val, (dict, list)):
                    feat.setAttribute(fname, json.dumps(val)[:254])
                else:
                    feat.setAttribute(fname, str(val)[:254])
            features.append(feat)

        # Insert in chunks, yielding to the Qt event loop between each batch
        total = len(features)
        for i in range(0, total, CHUNK_SIZE):
            chunk = features[i: i + CHUNK_SIZE]
            layer.dataProvider().addFeatures(chunk)
            if progress_cb:
                progress_cb(min(i + CHUNK_SIZE, total), total)
            QCoreApplication.processEvents()

        layer.updateExtents()

    @staticmethod
    def is_kobo_layer(layer) -> bool:
        if layer is None:
            return False
        return bool(layer.customProperty(KOBO_LAYER_PROPERTY))

    @staticmethod
    def get_asset_uid(layer) -> Optional[str]:
        if layer is None:
            return None
        return layer.customProperty(KOBO_LAYER_PROPERTY) or None
