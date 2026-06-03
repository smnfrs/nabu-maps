"""
Map 2 — V. velutina / V. crabro ratio per Landkreis, yearly timeline.

Per-Landkreis choropleth shaded by velutina-per-crabro ratio. Both species
share the same observer pool, so the ratio cancels effort + population
bias. Landkreise with crabro < 3 in a given year render grey (low signal).

Output: maps/ratio_choropleth.html (self-contained).
"""
from __future__ import annotations

from pathlib import Path

from terramap import ChoroplethLayer, Map

from _data_prep import build_vc_ratio_series, landkreis_geojson_for_layer

OUT = Path(__file__).resolve().parents[1] / "maps" / "ratio_choropleth.html"

YEARS = list(range(2014, 2026))


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)

    rows = build_vc_ratio_series(YEARS, crabro_min=3)
    timestamps = [str(y) for y in YEARS]

    n_lk = len(rows)
    n_finite = sum(
        1 for s in rows["vel_per_crabro_series"] for v in s if v is not None
    )
    print(f"Landkreise: {n_lk}; finite (lk, year) cells: {n_finite} / {n_lk * len(YEARS)}")

    m = Map(
        region="germany",
        style="strategy-dark",
        terrain="high",
        title="V. velutina / V. crabro ratio per Landkreis",
        timestamps=timestamps,
        timeline_start="end",
    )
    m.add_layer(ChoroplethLayer(
        rows,
        geojson=landkreis_geojson_for_layer(),
        region_id="lk_id",
        id_field="ID_3",
        time_value="vel_per_crabro_series",
        color_scale="reds",
        log_scale=True,
        vmin=0.05,
        vmax=10.0,
        opacity=0.78,
        missing_color="#3a3a3a",
        legend_label="V. velutina / V. crabro",
    ))

    m.to_html(OUT)
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
