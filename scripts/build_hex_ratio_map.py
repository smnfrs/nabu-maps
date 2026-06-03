"""
Map 3 — V. velutina / V. crabro ratio as 3D hexagon height, animated yearly.

H3-hexbinned ratio map: each hexagon's HEIGHT and colour encode that
year's velutina-per-crabro ratio, animated year by year from 2014.
Both species share the observer pool, so the ratio cancels effort +
population bias (see CLAUDE.md). A hexagon shows only in years that
record a velutina sighting in its cell, its height the ratio for that
year; it vanishes again in years with no velutina.

Design choices (per the brief):
* Yearly (not cumulative) — height, colour, and tooltip all use the raw
  counts for the displayed year.
* Linear, not log — height and colour are both linear in the ratio, so
  "no velutina → hidden" and "a little velutina → a little height".
* A year with velutina but no crabro (empty denominator) treats crabro as
  1, so a lone sighting reads ~1:1. Height/colour share a display ceiling
  (RATIO_MAX) since a linear channel can't span 0→max legibly; ~1% of
  cell-years exceed it and saturate, but tooltips show the raw counts.

Mechanics:
* ``HexBin(time=..., cumulative=False)`` bins each species into a per-cell,
  per-year count; the two grids share centroids, so we merge on
  (lon, lat) and divide to get the ratio series (a bin aggregates one
  dataset, not a quotient).
* Height comes from ``Scale`` magnitude (linear over the value range, base
  0 → zero height at ratio 0); ``time_value`` animates it per step.
* No ``bin=`` on the layer (we pre-binned), so the hexagon is sized by
  hand via ``autosize_radius`` × HEX_FILL — at HEX_FILL=1.0 each hexagon
  fills its H3 cell (raise RESOLUTION for smaller bins, not HEX_FILL).

Output: maps/ratio_hexbin.html (self-contained).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from terramap import HexBin, Hexagon, LabelLayer, Map, PointLayer, Scale
from terramap.regions import get_region

from _data_prep import load_crabro, load_velutina

OUT = Path(__file__).resolve().parents[1] / "maps" / "ratio_hexbin.html"

YEAR_MIN, YEAR_MAX = 2014, 2025
RESOLUTION = 5          # H3 resolution (~8.5 km edge → smaller bins)
CRABRO_MIN = 3          # drop cells whose total crabro signal is too thin
RATIO_MAX = 10.0        # display ceiling for height + colour (matches
                        # ratio_choropleth's vmax); ~1% of cell-years exceed it
                        # and saturate. Not a data cap — tooltips show raw counts.
HEX_FILL = 1.0          # hexagon radius as a fraction of the H3 cell (fills it)
HEIGHT_ASPECT = 16.0    # tallest column ≈ this × the hexagon radius

# A few large cities for orientation in the 3D scene (lon, lat = centre).
CITIES = pd.DataFrame([
    ("Berlin",    13.4050, 52.5200),
    ("Hamburg",    9.9937, 53.5511),
    ("München",   11.5820, 48.1351),
    ("Köln",       6.9603, 50.9375),
    ("Frankfurt",  8.6821, 50.1109),
    ("Stuttgart",  9.1829, 48.7758),
    ("Leipzig",   12.3731, 51.3397),
], columns=["name", "lon", "lat"])


def autosize_radius(bin: HexBin, region: Dict[str, Any]) -> float:
    """Hex radius (world units) that fills an H3 cell on this region.

    Mirrors terramap's renderer-side cell fill: take the cell's geographic
    size in degrees and convert through the region's linear projection.
    """
    w_deg, h_deg = bin._cell_size_deg()
    w_per_lon = region["terrain_w"] / (region["lon_max"] - region["lon_min"])
    w_per_lat = region["terrain_d"] / (region["lat_max"] - region["lat_min"])
    return (w_deg * w_per_lon + h_deg * w_per_lat) / 2


def load_years(loader) -> pd.DataFrame:
    df = loader()
    df = df[(df["year"] >= YEAR_MIN) & (df["year"] <= YEAR_MAX)].copy()
    df["yr"] = df["year"].astype(str)
    return df


def year_steps(*frames: pd.DataFrame) -> List[str]:
    """Contiguous YYYY strings from YEAR_MIN to the last observed year."""
    last_y = max(int(f["year"].max()) for f in frames)
    return [str(y) for y in range(YEAR_MIN, last_y + 1)]


def binned_series(df: pd.DataFrame, steps: List[str], name: str) -> pd.DataFrame:
    """Per-cell, per-year count (not cumulative), one row per cell centroid."""
    bin = HexBin(resolution=RESOLUTION, time="yr", timestamps=steps,
                 cumulative=False)
    cells, _ = bin.apply(df)             # [{lon, lat, count: [per-step]}, ...]
    return pd.DataFrame(cells).rename(columns={"count": name})


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)

    vel = load_years(load_velutina)
    cra = load_years(load_crabro)
    steps = year_steps(vel, cra)
    n = len(steps)
    zero = [0.0] * n

    cells = binned_series(vel, steps, "vel").merge(
        binned_series(cra, steps, "cra"), on=["lon", "lat"], how="outer")
    # Cells present for only one species come back NaN — fill with a zero
    # series of the right length.
    for col in ("vel", "cra"):
        cells[col] = cells[col].apply(lambda s: s if isinstance(s, list) else zero)

    # Yearly ratio per cell. Crabro absent → treat the denominator as 1, so a
    # lone velutina sighting reads ~1:1 rather than infinite; real (crabro>0)
    # ratios are untouched. A year with no velutina is 0 (and hidden).
    def year_ratio(v, c):
        if v == 0:
            return 0.0
        return v / max(c, 1)

    cells["ratio"] = [
        [year_ratio(v, c) for v, c in zip(vs, cs)]
        for vs, cs in zip(cells["vel"], cells["cra"])
    ]
    cells["total_cra"] = [sum(cs) for cs in cells["cra"]]
    cells["total_vel"] = [sum(vs) for vs in cells["vel"]]

    # Keep only cells with enough crabro overall to be worth showing at all.
    cells = cells[cells["total_cra"] >= CRABRO_MIN].copy()

    # True peak (for reporting), then clamp only the visual channel to the
    # display ceiling — the linear height/colour can't legibly span 0→max.
    true_max = max((max(rs) for rs in cells["ratio"]), default=0.0)
    cells["ratio"] = [[min(r, RATIO_MAX) for r in rs] for rs in cells["ratio"]]

    # Visible only in years that actually have a velutina sighting.
    cells["visible"] = [[v > 0 for v in vs] for vs in cells["vel"]]

    # Tooltip columns: that year's raw counts (column names = tooltip labels).
    cells["velutina (this year)"] = [[int(v) for v in vs] for vs in cells["vel"]]
    cells["crabro (this year)"] = [[int(c) for c in cs] for cs in cells["cra"]]

    ever_vel = int((cells["total_vel"] > 0).sum())
    print(
        f"H3 res {RESOLUTION}: {len(cells)} cells (crabro >= {CRABRO_MIN}), "
        f"{ever_vel} ever recording velutina; {n} yearly steps "
        f"({steps[0]}–{steps[-1]}); true peak ratio {true_max:.1f} "
        f"(display ceiling {RATIO_MAX:g})"
    )

    hex_radius = autosize_radius(
        HexBin(resolution=RESOLUTION), get_region("germany")) * HEX_FILL
    max_height = hex_radius * HEIGHT_ASPECT

    m = Map(
        region="germany",
        style="strategy-dark",
        terrain="high",
        title="V. velutina / V. crabro ratio — hexbinned, yearly",
        timestamps=steps,
        timeline_start="end",
    )
    m.add_layer(PointLayer(
        cells,
        style=Hexagon(radius=hex_radius, height=1.0),
        magnitude=Scale(base=0.0, max=max_height),
        time_value="ratio",       # drives height per year (linear, 0 → flat)
        time_color_by="ratio",    # drives colour per year (linear reds)
        time_visible="visible",   # shown only in years with a velutina sighting
        color_scale="reds",
        vmin=0.0, vmax=RATIO_MAX,
        legend_label="V. velutina / V. crabro",
        tooltip=["velutina (this year)", "crabro (this year)"],
        prefix="velutina / crabro = ",
        show_flags=False,
    ))
    m.add_layer(LabelLayer(
        CITIES, lon="lon", lat="lat", text="name",
        color="#000000", font_size=26, offset_y=0.15, flat=True,
    ))

    m.to_html(OUT)
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
