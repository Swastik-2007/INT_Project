# LPU Wayfinder — OsmAnd Survey Analysis
**Survey date:** 20 November 2026 · **Status:** field-collected, not route-verified

## Recorded data
| Track | GPS points | Distance (m) | Duration | Start (IST) | End (IST) |
|---|---:|---:|---:|---|---|
| Main Gate to Admission & class area | 138 | 910.9 | 12:00 | 12:07:11 | 12:19:11 |
| Block 30 to 32 | 13 | 78.1 | 1:03 | 12:19:32 | 12:20:35 |
| Block 32 to 34 | 14 | 94.3 | 1:11 | 12:20:44 | 12:21:55 |
| Block 34 to BH4 | 98 | 650.7 | 8:34 | 12:23:45 | 12:32:19 |
| **TOTAL** | **263** | **1734.0** | **22:48** | — | — |

Lengths measure the recorded polyline, not validated walkway length. Time gaps between recordings are not included in durations.

## Recording continuity & endpoint gaps
| Consecutive tracks | Endpoint separation | Elapsed unrecorded time | Disposition |
|---|---:|---:|---|
| Main Gate to Admission & class area → Block 30 to 32 | 21.9 m | 21 s | Confirm manually; do not auto-connect |
| Block 30 to 32 → Block 32 to 34 | 8.3 m | 9 s | Confirm manually; do not auto-connect |
| Block 32 to 34 → Block 34 to BH4 | 73.6 m | 110 s | Confirm manually; do not auto-connect |

**Critical:** The ~73.6 m gap between Block 32 → 34 and Block 34 → BH4 is the strongest current routing blocker. The two endpoint positions have no recorded intermediate pedestrian geometry. Do not bridge them by generating a straight connecting walkway.

## GPS QA observations
- All four files are well-formed GPX tracks exported from OsmAnd 5.4.11.
- Point intervals were between 5 and 6 seconds in all four tracks; no timestamp reversals or recording gaps within the tracks.
- No consecutive-point implied speed exceeded 3.5 m/s, so there were no obvious large locomotion spikes.
- GPX HDOP values are unitless satellite-geometry measures; **they are not GPS accuracy radii in metres**.
- Buildings 25–29 may lie near the first survey track, but this does not establish their entrance coordinates, accessible pedestrian links, or verified status.
- Start and end labels are based on user-provided filenames, not independent landmark verification.
- Recorded track start/end points may not be exact building entrances, especially where recording began or ended after walking.

## Recommended review workflow
1. Keep all four original GPX files as immutable raw source evidence.
2. Open `survey_tracks_interactive_map.html` (requires internet for OpenStreetMap tiles) and visually check alignment with paths, building boundaries, and junctions.
3. Confirm the four named track endpoints on the ground or from field photos. Identify the real entrances to Block 30, Block 32, Block 34, BH4 and any Main Gate waypoint.
4. Collect or confirm the missing ~74 m connection near Block 34, and inspect the ~22 m and ~8 m breaks.
5. Identify individual entrance coordinates for Blocks 25, 26, 27, 28, 29. Nearby buildings should not be linked merely because the path passes nearby.
6. Review potentially unsafe or inaccurate sections before marking any walkway as verified.
7. Load reviewed, individually approved edges and their junctions into the actual routing graph; do **not** import this four-LineString survey directly as a fully connected network.
8. Validate routing from Main Gate to Block 34, and Block 34 to BH4, in the public map and on a phone only after topology is verified.

## Bundle files
- `four_recorded_tracks_unverified.geojson`: one Feature per GPX recording, GeoJSON EPSG:4326 (longitude, latitude). No inferred gap features.
- `survey_points.csv`: per-point GPS metadata, timestamps, HDOP and optional recorded speed.
- `unrecorded_gaps.csv`: endpoint separations and unrecorded intervals.
- `survey_tracks_interactive_map.html`: OSM-backed interactive map showing actual recorded polylines and **clearly dashed unsurveyed gaps**.
- `survey_track_overview.png`: static coordinate plot suitable for project-review illustration.
- `README_analysis.md`: this quality and next-steps report.
- `raw_gpx/`: preserved copies of all user-provided GPX files.

The source GPX timestamps are UTC. Times in the summary table are converted to Asia/Kolkata (IST).
