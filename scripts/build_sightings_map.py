"""
Map 1 — V. velutina sightings, monthly timeline.

Each sighting appears red in its month of observation and fades to grey
from the following month onward. Markers stay visible once they've
appeared (a sighting is a fact, not a state).

Uses PointLayer's compact event API (``time_appears_at`` + ``time_fades_at``):
one integer per row instead of a per-step list, which makes the HTML
~50× smaller at this scale.

Output: maps/sightings_timeline.html (self-contained).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from terramap import ChoroplethLayer, LabelLayer, Lollipop, Map, PointLayer

from _data_prep import (
    assign_landkreis,
    landkreis_geojson_subset,
    load_landkreise,
    load_velutina,
)

# A small set of large German cities for orientation. Coordinates are
# city centre (lon, lat). Kept short to avoid label collisions on the
# default camera framing.
CITIES = pd.DataFrame([
    ("Berlin",      13.4050, 52.5200),
    ("Hamburg",      9.9937, 53.5511),
    ("München",     11.5820, 48.1351),
    ("Köln",         6.9603, 50.9375),
    ("Frankfurt",    8.6821, 50.1109),
    ("Stuttgart",    9.1829, 48.7758),
    ("Düsseldorf",   6.7735, 51.2277),
    ("Leipzig",     12.3731, 51.3397),
    ("Bremen",       8.8017, 53.0793),
    ("Dresden",     13.7373, 51.0504),
    ("Hannover",     9.7320, 52.3759),
    ("Nürnberg",    11.0767, 49.4521),
], columns=["name", "lon", "lat"])

OUT = Path(__file__).resolve().parents[1] / "maps" / "sightings_timeline.html"

FRESH = "#ff3030"      # red in the sighting's month
FADED = "#888888"      # grey from the next month onward
CITY_FILL = "#d6c08e"  # warm sand — subtle city polygon highlight under labels
START_YEAR = 2014


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)

    rec = load_velutina()
    rec = rec[(rec["year"] >= START_YEAR) & (rec["year"] <= 2025)].copy()

    last_year = int(rec["year"].max())
    last_month = int(rec.loc[rec["year"] == last_year, "month"].max())
    n_steps = (last_year - START_YEAR) * 12 + last_month
    timestamps = [
        f"{START_YEAR + i // 12}-{i % 12 + 1:02d}" for i in range(n_steps)
    ]

    # Step at sighting (month index from START_YEAR-01).
    rec["step"] = (rec["year"] - START_YEAR) * 12 + (rec["month"] - 1)
    # Step at which colour flips to grey — the month after the sighting.
    rec["fade_step"] = rec["step"] + 1

    rec = rec[(rec["step"] >= 0) & (rec["step"] < n_steps)]

    print(f"Rendering {len(rec):,} sightings across {n_steps} monthly steps "
          f"(2014-01 to {timestamps[-1]}).")

    # Find the Landkreis each city centre falls in, then shade just those
    # polygons. Stadtstaaten and kreisfreie Städte (Berlin, Hamburg,
    # München, …) each map to a single feature in landkreise.geojson.
    lk = load_landkreise()
    cities_lk = assign_landkreis(CITIES, lk).dropna(subset=["lk_id"]).copy()
    cities_lk["fill"] = 1.0

    m = Map(
        region="germany",
        style="strategy-dark",
        terrain="high",
        title="V. velutina sightings in Germany",
        subtitle="Red in the month of observation, grey thereafter",
        timestamps=timestamps,
        timeline_start="end",
    )
    m.add_layer(ChoroplethLayer(
        cities_lk[["lk_id", "fill"]],
        geojson=landkreis_geojson_subset(cities_lk["lk_id"]),
        region_id="lk_id",
        id_field="ID_3",
        value="fill",
        color_stops=[CITY_FILL, CITY_FILL],
        vmin=0.0, vmax=1.0,
        opacity=0.6,
        show_legend=False,
    ))
    m.add_layer(PointLayer(
        rec[["lon", "lat", "step", "fade_step"]],
        lon="lon", lat="lat",
        style=Lollipop(head_radius=0.04),
        color=FRESH,
        faded_color=FADED,
        time_appears_at="step",
        time_fades_at="fade_step",
    ))
    m.add_layer(LabelLayer(
        CITIES, lon="lon", lat="lat", text="name",
        color="#000000", font_size=30, offset_y=0.15, flat=True,
    ))

    m.to_html(OUT)
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
