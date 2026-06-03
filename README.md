# Hornet spread in Germany — maps

Three interactive maps tracking the invasive **Asian hornet** (*Vespa velutina*)
across Germany, built from [GBIF](https://www.gbif.org/) occurrence records
(2014–2025). Produced for a [CorrelAid](https://correlaid.org/) × NABU
collaboration.

**▶ View the maps: https://smnfrs.github.io/nabu-maps/**

| Map | What it shows |
| --- | --- |
| [Sightings timeline](https://smnfrs.github.io/nabu-maps/maps/sightings_timeline.html) | Every *V. velutina* sighting, month by month — red in its month of observation, grey thereafter. |
| [Ratio choropleth](https://smnfrs.github.io/nabu-maps/maps/ratio_choropleth.html) | Velutina-to-crabro ratio per Landkreis, animated by year. |
| [Ratio hexbin (3D)](https://smnfrs.github.io/nabu-maps/maps/ratio_hexbin.html) | The same ratio as animated 3D hexagon height on a topographic map. |

The pre-rendered HTML files in [`maps/`](maps/) are fully self-contained — open
any of them directly in a browser, no server or network needed.

## Why the velutina / crabro ratio?

Raw sighting counts are badly confounded. Citizen-science observer effort has
grown enormously (native *V. crabro* records grew ~17× from 2016 to 2025 with no
real change in its population — that's pure observer effort), and records cluster
where people are.

The native **European hornet (*V. crabro*)** has a stable population and shares
the *same* observer base as the invasive velutina. So dividing velutina by crabro
per region per year cancels **both** effort growth and population density at once,
leaving a signal that reflects the invasive's actual relative spread. Regions with
too little crabro signal (`crabro_count < 3`) are filtered out, since the ratio
blows up on thin denominators.

## Regenerate the maps

Requires Python 3.9+.

```bash
pip install -r requirements.txt
python scripts/build_sightings_map.py
python scripts/build_ratio_map.py
python scripts/build_hex_ratio_map.py
```

Each script writes a self-contained `.html` into `maps/`. The raw GBIF CSVs
(~75–80 MB each) are **not** committed; on first run they download automatically
from public Azure Blob Storage and cache into `data/raw/` (gitignored). The
rendering library, [terramap](https://github.com/smnfrs/terramap) (MIT), installs
from GitHub via `requirements.txt`.

## Layout

```
index.html               landing page linking the three maps
maps/                     pre-rendered, self-contained map HTML
scripts/
  _data_prep.py           shared GBIF load / clean / Landkreis join
  build_sightings_map.py  map 1
  build_ratio_map.py      map 2
  build_hex_ratio_map.py  map 3
data/geo/landkreise.geojson   district polygons (GADM)
data/raw/                 downloaded GBIF CSVs (gitignored, auto-fetched)
```

## Data & licensing

- Occurrence data: GBIF, filtered to `countryCode == DE`, refreshed weekly.
- District boundaries: [GADM](https://gadm.org/) level-3.
- Code and rendering library: MIT.
