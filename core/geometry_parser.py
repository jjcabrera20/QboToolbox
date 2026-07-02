from typing import List, NamedTuple, Optional

from qgis.core import QgsGeometry, QgsPointXY

GEO_FIELD_MAP = {
    "geopoint": "Point",
    "geotrace": "LineString",
    "geoshape": "Polygon",
}


class GeoField(NamedTuple):
    field_name: str
    wkt_type: str
    label: str


class GeometryParser:
    @staticmethod
    def detect_geo_fields(asset: dict) -> List[GeoField]:
        survey = asset.get("content", {}).get("survey", [])
        fields = []
        for item in survey:
            field_type = item.get("type", "")
            if field_type in GEO_FIELD_MAP:
                name = item.get("$autoname") or item.get("name", "")
                label_raw = item.get("label", [])
                label = label_raw[0] if isinstance(label_raw, list) and label_raw else str(label_raw or name)
                fields.append(GeoField(field_name=name, wkt_type=GEO_FIELD_MAP[field_type], label=label))
        return fields

    @staticmethod
    def _parse_point_str(point_str: str) -> Optional[QgsPointXY]:
        parts = point_str.strip().split()
        if len(parts) < 2:
            return None
        try:
            lat = float(parts[0])
            lon = float(parts[1])
            return QgsPointXY(lon, lat)  # QGIS: X=lon, Y=lat
        except ValueError:
            return None

    @staticmethod
    def parse_geopoint(value: str) -> Optional[QgsGeometry]:
        if not value or not value.strip():
            return None
        pt = GeometryParser._parse_point_str(value)
        if pt is None:
            return None
        return QgsGeometry.fromPointXY(pt)

    @staticmethod
    def parse_geotrace(value: str) -> Optional[QgsGeometry]:
        if not value or not value.strip():
            return None
        points = []
        for seg in value.split(";"):
            seg = seg.strip()
            if not seg:
                continue
            pt = GeometryParser._parse_point_str(seg)
            if pt:
                points.append(pt)
        if len(points) < 2:
            return None
        return QgsGeometry.fromPolylineXY(points)

    @staticmethod
    def parse_geoshape(value: str) -> Optional[QgsGeometry]:
        if not value or not value.strip():
            return None
        points = []
        for seg in value.split(";"):
            seg = seg.strip()
            if not seg:
                continue
            pt = GeometryParser._parse_point_str(seg)
            if pt:
                points.append(pt)
        if len(points) < 3:
            return None
        # Close ring explicitly
        if points[0].x() != points[-1].x() or points[0].y() != points[-1].y():
            points.append(points[0])
        return QgsGeometry.fromPolygonXY([points])

    @staticmethod
    def parse_geometry(value: str, wkt_type: str) -> Optional[QgsGeometry]:
        if not value:
            return None
        if wkt_type == "Point":
            return GeometryParser.parse_geopoint(value)
        if wkt_type == "LineString":
            return GeometryParser.parse_geotrace(value)
        if wkt_type == "Polygon":
            return GeometryParser.parse_geoshape(value)
        return None
