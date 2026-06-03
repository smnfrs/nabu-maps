"""
Shared data prep for the three terramap-driven hornet maps.

Loads GBIF occurrence records for *Vespa velutina* (Asian hornet, the
invasive subject) and *Vespa crabro* (European hornet, the stable-population
control), cleans them, and bins them by Landkreis / H3 cell / time.

Data source
-----------
The raw GBIF CSVs are published weekly to public Azure Blob Storage. If a
CSV is not already present in ``data/raw/`` it is downloaded once and cached
there (the files are ~75–80 MB each and are gitignored), so the maps
regenerate from a clean clone with no manual download step.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
GEO_DIR = ROOT / "data" / "geo"

# Public Azure Blob container the GBIF exports refresh to (Mon 03:00 UTC).
AZURE_BASE = "https://sthornetprodvsh.blob.core.windows.net/gbif-data"

# Germany bounding box (lon_min, lon_max, lat_min, lat_max). Records outside
# this box are data-entry errors per EDA — drop them.
DE_BOX = (5.5, 15.5, 47.0, 55.5)

USE_COLS = ["species", "year", "month", "decimalLatitude", "decimalLongitude"]


def _ensure_local(filename: str) -> Path:
    """Return the local path to a raw CSV, downloading from Azure if absent."""
    path = RAW_DIR / filename
    if not path.exists():
        url = f"{AZURE_BASE}/{filename}"
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[data] {filename} not cached locally — downloading from {url}")
        urllib.request.urlretrieve(url, path)
        print(f"[data] cached {path} ({path.stat().st_size // (1024 * 1024)} MB)")
    return path


def _load_species(filename: str) -> pd.DataFrame:
    df = pd.read_csv(
        _ensure_local(filename),
        usecols=lambda c: c in USE_COLS,
        low_memory=False,
    )
    df = df.dropna(subset=["year", "month", "decimalLatitude", "decimalLongitude"])
    df = df.astype({"year": int, "month": int})
    df = df.query(
        f"{DE_BOX[0]} <= decimalLongitude <= {DE_BOX[1]} "
        f"and {DE_BOX[2]} <= decimalLatitude <= {DE_BOX[3]}"
    )
    return df.rename(columns={"decimalLongitude": "lon", "decimalLatitude": "lat"})


def load_velutina() -> pd.DataFrame:
    """Asian hornet records, cleaned + bbox-filtered."""
    return _load_species("asian_hornet_DE.csv").assign(species_short="vel")


def load_crabro() -> pd.DataFrame:
    """European hornet records, cleaned + bbox-filtered."""
    return _load_species("european_hornet_DE.csv").assign(species_short="cra")


def load_landkreise() -> gpd.GeoDataFrame:
    """
    Landkreis polygons keyed by ``lk_id`` (GAdM ``ID_3``).

    Strips top-level ``feature.id`` (which is the array index, not the
    Landkreis ID) so ``ChoroplethLayer`` falls through to ``properties.ID_3``.
    """
    path = GEO_DIR / "landkreise.geojson"
    raw = json.loads(path.read_text(encoding="utf-8"))
    for feat in raw["features"]:
        feat.pop("id", None)
    gdf = gpd.GeoDataFrame.from_features(raw["features"], crs="EPSG:4326")
    gdf = gdf.rename(columns={"ID_3": "lk_id", "NAME_3": "lk_name"})
    return gdf[["lk_id", "lk_name", "geometry"]]


def landkreis_geojson_for_layer() -> dict:
    """
    GeoJSON dict ready for ``ChoroplethLayer(geojson=...)``: top-level ``id``
    removed on every feature so the layer matches on ``properties.ID_3``.
    """
    path = GEO_DIR / "landkreise.geojson"
    raw = json.loads(path.read_text(encoding="utf-8"))
    for feat in raw["features"]:
        feat.pop("id", None)
    return raw


def landkreis_geojson_subset(lk_ids: Iterable) -> dict:
    """GeoJSON restricted to features whose ``ID_3`` is in ``lk_ids``."""
    keep = set(lk_ids)
    raw = landkreis_geojson_for_layer()
    raw["features"] = [
        f for f in raw["features"]
        if f.get("properties", {}).get("ID_3") in keep
    ]
    return raw


def assign_landkreis(records: pd.DataFrame, lk: gpd.GeoDataFrame) -> pd.DataFrame:
    """Point-in-polygon: tag each record with its Landkreis (``lk_id``)."""
    gdf = gpd.GeoDataFrame(
        records.copy(),
        geometry=gpd.points_from_xy(records["lon"], records["lat"]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(gdf, lk[["lk_id", "geometry"]], how="left", predicate="within")
    return joined.drop(columns=["geometry", "index_right"])


def build_vc_ratio_series(
    years: Iterable[int],
    crabro_min: int = 3,
) -> pd.DataFrame:
    """
    One row per Landkreis with ``vel_per_crabro_series`` — a list of floats
    (or NaN) per year. NaN where crabro records that year < ``crabro_min``,
    matching the low-signal filter used throughout the analysis.

    Returns: DataFrame with columns [lk_id, lk_name, vel_per_crabro_series].
    """
    years = list(years)
    lk = load_landkreise()

    vel = assign_landkreis(load_velutina(), lk)
    cra = assign_landkreis(load_crabro(), lk)

    def _by_lk_year(df: pd.DataFrame) -> pd.DataFrame:
        return (
            df.dropna(subset=["lk_id"])
            .query("@years[0] <= year <= @years[-1]")
            .groupby(["lk_id", "year"])
            .size()
            .unstack("year", fill_value=0)
            .reindex(columns=years, fill_value=0)
        )

    v = _by_lk_year(vel)
    c = _by_lk_year(cra)

    all_ids = lk["lk_id"].tolist()
    v = v.reindex(all_ids, fill_value=0)
    c = c.reindex(all_ids, fill_value=0)

    ratio = v.div(c.where(c >= crabro_min))  # NaN where crabro under threshold

    out = lk[["lk_id", "lk_name"]].copy()
    out["vel_per_crabro_series"] = [
        # JSON can't hold NaN; emit None for missing values so the JS sees
        # null and falls back to missing_color.
        [None if pd.isna(v) else float(v) for v in ratio.loc[i].tolist()]
        for i in out["lk_id"]
    ]
    return out
