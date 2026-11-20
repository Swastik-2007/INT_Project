"""
Stage 1: Independent GPX Analysis & Validation
===============================================
Parses all four original OsmAnd GPX recordings, performs quality checks, 
computes geodesic distances, identifies gaps between recordings, and 
produces a structured JSON report.

This script is READ-ONLY: it never modifies the original GPX files or the database.
"""

import xml.etree.ElementTree as ET
import math
import json
import hashlib
import os
from datetime import datetime
from pathlib import Path

# ---- Configuration ----
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw_surveys"
OUTPUT_DIR = PROJECT_ROOT / "data" / "survey_analysis"

GPX_FILES = [
    "Main_gate to Admission & class area.gpx",
    "Block 30 to 32.gpx",
    "Block 32 to 34.gpx",
    "Block 34 to BH4.gpx",
]

SEGMENT_LABELS = [
    "A: Main Gate → Admission/Academic Area",
    "B: Block 30 Area → Block 32",
    "C: Block 32 → Block 34 (Outdoor)",
    "D: Block 34 → BH4 (Boys Hostel 4)",
]

GPX_NS = "{http://www.topografix.com/GPX/1/1}"
OSMAND_NS = "{https://osmand.net/docs/technical/osmand-file-formats/osmand-gpx}"

# ---- Geodesic helpers ----
def haversine_m(lat1, lon1, lat2, lon2):
    """Haversine distance in meters between two WGS84 points."""
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def bearing_deg(lat1, lon1, lat2, lon2):
    """Initial bearing from point1 to point2 in degrees."""
    dlon = math.radians(lon2 - lon1)
    lat1r, lat2r = math.radians(lat1), math.radians(lat2)
    x = math.sin(dlon) * math.cos(lat2r)
    y = (math.cos(lat1r) * math.sin(lat2r) -
         math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon))
    return (math.degrees(math.atan2(x, y)) + 360) % 360

# ---- Parse a single GPX file ----
def parse_gpx(filepath):
    """Parse GPX file and return structured track data."""
    tree = ET.parse(filepath)
    root = tree.getroot()
    
    # Metadata
    meta_name = None
    meta_el = root.find(f"{GPX_NS}metadata/{GPX_NS}name")
    if meta_el is not None:
        meta_name = meta_el.text
    
    creator = root.attrib.get("creator", "unknown")
    
    # File hash for deduplication
    with open(filepath, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    
    # Parse track points
    points = []
    for trk in root.findall(f"{GPX_NS}trk"):
        for seg in trk.findall(f"{GPX_NS}trkseg"):
            for pt in seg.findall(f"{GPX_NS}trkpt"):
                lat = float(pt.attrib["lat"])
                lon = float(pt.attrib["lon"])
                
                ele = None
                ele_el = pt.find(f"{GPX_NS}ele")
                if ele_el is not None:
                    ele = float(ele_el.text)
                
                time_str = None
                time_el = pt.find(f"{GPX_NS}time")
                if time_el is not None:
                    time_str = time_el.text
                
                hdop = None
                hdop_el = pt.find(f"{GPX_NS}hdop")
                if hdop_el is not None:
                    hdop = float(hdop_el.text)
                
                speed = None
                ext = pt.find(f"{GPX_NS}extensions")
                if ext is not None:
                    speed_el = ext.find(f"{OSMAND_NS}speed")
                    if speed_el is not None:
                        speed = float(speed_el.text)
                
                points.append({
                    "lat": lat,
                    "lon": lon,
                    "ele": ele,
                    "time": time_str,
                    "hdop": hdop,
                    "speed": speed,
                })
    
    return {
        "metadata_name": meta_name,
        "creator": creator,
        "file_hash_sha256": file_hash,
        "points": points,
    }

# ---- Validate & analyze a parsed track ----
def analyze_track(parsed, filename):
    """Run quality checks and compute track statistics."""
    points = parsed["points"]
    n = len(points)
    
    result = {
        "filename": filename,
        "metadata_name": parsed["metadata_name"],
        "creator": parsed["creator"],
        "file_hash": parsed["file_hash_sha256"],
        "point_count": n,
        "valid": True,
        "errors": [],
        "warnings": [],
    }
    
    if n == 0:
        result["valid"] = False
        result["errors"].append("No track points found")
        return result
    
    # Coordinate range check (LPU campus is near 31.25°N, 75.70°E)
    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]
    
    result["bbox"] = {
        "min_lat": min(lats), "max_lat": max(lats),
        "min_lon": min(lons), "max_lon": max(lons),
    }
    
    # Sanity: all points should be within reasonable LPU campus area
    for i, p in enumerate(points):
        if not (31.24 < p["lat"] < 31.27):
            result["warnings"].append(f"Point {i}: lat {p['lat']} outside expected LPU range 31.24-31.27")
        if not (75.69 < p["lon"] < 75.72):
            result["warnings"].append(f"Point {i}: lon {p['lon']} outside expected LPU range 75.69-75.72")
    
    # Start/End coordinates
    result["start"] = {"lat": points[0]["lat"], "lon": points[0]["lon"], "time": points[0]["time"]}
    result["end"] = {"lat": points[-1]["lat"], "lon": points[-1]["lon"], "time": points[-1]["time"]}
    
    # Timestamps
    has_timestamps = all(p["time"] is not None for p in points)
    result["has_timestamps"] = has_timestamps
    
    if has_timestamps:
        times = [datetime.fromisoformat(p["time"].replace("Z", "+00:00")) for p in points]
        result["start_time"] = str(times[0])
        result["end_time"] = str(times[-1])
        duration_sec = (times[-1] - times[0]).total_seconds()
        result["duration_seconds"] = duration_sec
        
        # Check timestamp ordering
        out_of_order = []
        for i in range(1, len(times)):
            if times[i] < times[i-1]:
                out_of_order.append(i)
        if out_of_order:
            result["warnings"].append(f"Out-of-order timestamps at indices: {out_of_order}")
        result["timestamps_ordered"] = len(out_of_order) == 0
    
    # HDOP (GPS quality) statistics
    hdops = [p["hdop"] for p in points if p["hdop"] is not None]
    if hdops:
        result["hdop_stats"] = {
            "min": round(min(hdops), 1),
            "max": round(max(hdops), 1),
            "mean": round(sum(hdops) / len(hdops), 2),
            "points_with_hdop": len(hdops),
            "points_hdop_gt_10": sum(1 for h in hdops if h > 10),
        }
    else:
        result["hdop_stats"] = None
        result["warnings"].append("No HDOP data found in GPX file")
    
    # Speed statistics
    speeds = [p["speed"] for p in points if p["speed"] is not None]
    if speeds:
        result["speed_stats_ms"] = {
            "min": round(min(speeds), 2),
            "max": round(max(speeds), 2),
            "mean": round(sum(speeds) / len(speeds), 2),
            "points_with_speed": len(speeds),
        }
    
    # Elevation statistics
    elevations = [p["ele"] for p in points if p["ele"] is not None]
    if elevations:
        result["elevation_stats"] = {
            "min": round(min(elevations), 1),
            "max": round(max(elevations), 1),
            "range": round(max(elevations) - min(elevations), 1),
        }
    
    # Geodesic distance calculation (cumulative along track)
    total_dist = 0.0
    segment_dists = []
    max_jump = 0.0
    max_jump_idx = -1
    duplicates = 0
    
    for i in range(1, n):
        d = haversine_m(points[i-1]["lat"], points[i-1]["lon"],
                        points[i]["lat"], points[i]["lon"])
        segment_dists.append(d)
        total_dist += d
        
        if d > max_jump:
            max_jump = d
            max_jump_idx = i
        
        if d < 0.1:  # < 10cm = effectively duplicate
            duplicates += 1
    
    result["total_distance_m"] = round(total_dist, 2)
    result["total_distance_km"] = round(total_dist / 1000, 4)
    result["max_point_to_point_jump_m"] = round(max_jump, 2)
    result["max_jump_index"] = max_jump_idx
    result["duplicate_consecutive_points"] = duplicates
    
    # Straight-line start-to-end distance
    straight_dist = haversine_m(points[0]["lat"], points[0]["lon"],
                                points[-1]["lat"], points[-1]["lon"])
    result["straight_line_distance_m"] = round(straight_dist, 2)
    
    # Bearing from start to end
    result["bearing_start_to_end_deg"] = round(bearing_deg(
        points[0]["lat"], points[0]["lon"],
        points[-1]["lat"], points[-1]["lon"]
    ), 1)
    
    # Check for unrealistic jumps (>30m in a single 5-second interval at walking speed)
    unrealistic_jumps = []
    for i, d in enumerate(segment_dists):
        if d > 30:
            unrealistic_jumps.append({
                "from_index": i,
                "to_index": i + 1,
                "distance_m": round(d, 2),
                "from_coords": [points[i]["lat"], points[i]["lon"]],
                "to_coords": [points[i+1]["lat"], points[i+1]["lon"]],
            })
    if unrealistic_jumps:
        result["warnings"].append(f"Found {len(unrealistic_jumps)} inter-point distances > 30m")
    result["unrealistic_jumps"] = unrealistic_jumps
    
    # Average recording interval
    if has_timestamps and n > 1:
        total_dt = (times[-1] - times[0]).total_seconds()
        result["avg_recording_interval_sec"] = round(total_dt / (n - 1), 2)
    
    return result

# ---- Gap analysis between consecutive recordings ----
def analyze_gaps(all_results):
    """Analyze the physical gaps between consecutive recording segments."""
    gaps = []
    for i in range(len(all_results) - 1):
        r1 = all_results[i]
        r2 = all_results[i + 1]
        
        if not r1.get("end") or not r2.get("start"):
            continue
        
        gap_dist = haversine_m(
            r1["end"]["lat"], r1["end"]["lon"],
            r2["start"]["lat"], r2["start"]["lon"],
        )
        
        gap_bearing = bearing_deg(
            r1["end"]["lat"], r1["end"]["lon"],
            r2["start"]["lat"], r2["start"]["lon"],
        )
        
        # Time gap
        time_gap_sec = None
        if r1.get("end_time") and r2.get("start_time"):
            t1 = datetime.fromisoformat(r1["end_time"])
            t2 = datetime.fromisoformat(r2["start_time"])
            time_gap_sec = (t2 - t1).total_seconds()
        
        gaps.append({
            "from_recording": r1["filename"],
            "to_recording": r2["filename"],
            "gap_distance_m": round(gap_dist, 2),
            "gap_bearing_deg": round(gap_bearing, 1),
            "time_gap_sec": time_gap_sec,
            "from_endpoint": {"lat": r1["end"]["lat"], "lon": r1["end"]["lon"]},
            "to_startpoint": {"lat": r2["start"]["lat"], "lon": r2["start"]["lon"]},
            "note": "Recording was stopped and restarted; physical path was not GPS-recorded during this gap."
        })
    
    return gaps

# ---- GeoJSON generation for map overlay ----
def tracks_to_geojson(all_parsed, all_results):
    """Create GeoJSON FeatureCollection with all four tracks and gap lines."""
    features = []
    colors = ["#E63946", "#2A9D8F", "#E9C46A", "#264653"]
    
    for i, (parsed, result) in enumerate(zip(all_parsed, all_results)):
        # Track LineString
        coords = [[p["lon"], p["lat"]] for p in parsed["points"]]
        if parsed["points"][0].get("ele") is not None:
            coords = [[p["lon"], p["lat"], p["ele"]] for p in parsed["points"]]
        
        features.append({
            "type": "Feature",
            "properties": {
                "type": "recorded_track",
                "name": result["filename"],
                "segment_label": SEGMENT_LABELS[i],
                "point_count": result["point_count"],
                "distance_m": result["total_distance_m"],
                "duration_sec": result.get("duration_seconds"),
                "color": colors[i],
                "stroke": colors[i],
                "stroke-width": 4,
                "stroke-opacity": 0.85,
                "verified": False,
                "source": "osmand_gpx",
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            }
        })
        
        # Start marker
        features.append({
            "type": "Feature",
            "properties": {
                "type": "track_start",
                "track_name": result["filename"],
                "marker-color": colors[i],
                "marker-symbol": "s",
                "label": f"Start: {SEGMENT_LABELS[i]}",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [parsed["points"][0]["lon"], parsed["points"][0]["lat"]],
            }
        })
        
        # End marker
        features.append({
            "type": "Feature",
            "properties": {
                "type": "track_end",
                "track_name": result["filename"],
                "marker-color": colors[i],
                "marker-symbol": "e",
                "label": f"End: {SEGMENT_LABELS[i]}",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [parsed["points"][-1]["lon"], parsed["points"][-1]["lat"]],
            }
        })
    
    return {
        "type": "FeatureCollection",
        "features": features,
    }


# ---- Main ----
def main():
    print("=" * 70)
    print("LPU WAYFINDER — GPX SURVEY ANALYSIS (Stage 1)")
    print("=" * 70)
    
    all_parsed = []
    all_results = []
    
    for i, fname in enumerate(GPX_FILES):
        filepath = RAW_DIR / fname
        print(f"\n--- [{i+1}/4] {fname} ---")
        
        if not filepath.exists():
            print(f"  ERROR: File not found at {filepath}")
            continue
        
        fsize = filepath.stat().st_size
        print(f"  File size: {fsize:,} bytes")
        
        parsed = parse_gpx(filepath)
        result = analyze_track(parsed, fname)
        
        all_parsed.append(parsed)
        all_results.append(result)
        
        print(f"  Segment: {SEGMENT_LABELS[i]}")
        print(f"  Metadata name: {result['metadata_name']}")
        print(f"  Creator: {result['creator']}")
        print(f"  Point count: {result['point_count']}")
        print(f"  Track distance: {result['total_distance_m']:.1f} m ({result['total_distance_km']:.4f} km)")
        print(f"  Straight-line: {result['straight_line_distance_m']:.1f} m")
        print(f"  Bearing (start→end): {result['bearing_start_to_end_deg']}°")
        print(f"  Duration: {result.get('duration_seconds', 'N/A')} sec")
        print(f"  Avg interval: {result.get('avg_recording_interval_sec', 'N/A')} sec")
        print(f"  Start: ({result['start']['lat']:.7f}, {result['start']['lon']:.7f}) @ {result['start']['time']}")
        print(f"  End:   ({result['end']['lat']:.7f}, {result['end']['lon']:.7f}) @ {result['end']['time']}")
        
        if result.get("hdop_stats"):
            h = result["hdop_stats"]
            print(f"  HDOP: min={h['min']} max={h['max']} mean={h['mean']} (available for {h['points_with_hdop']} pts)")
        
        if result.get("speed_stats_ms"):
            s = result["speed_stats_ms"]
            print(f"  Speed (m/s): min={s['min']} max={s['max']} mean={s['mean']}")
        
        print(f"  Duplicate consecutive points: {result['duplicate_consecutive_points']}")
        print(f"  Max point-to-point jump: {result['max_point_to_point_jump_m']:.1f} m")
        
        if result["unrealistic_jumps"]:
            print(f"  ⚠ Unrealistic jumps (>30m): {len(result['unrealistic_jumps'])}")
        
        if result["warnings"]:
            for w in result["warnings"]:
                print(f"  ⚠ {w}")
        if result["errors"]:
            for e in result["errors"]:
                print(f"  ✗ {e}")
    
    # Gap analysis
    gaps = analyze_gaps(all_results)
    print(f"\n{'=' * 70}")
    print("INTER-RECORDING GAPS")
    print(f"{'=' * 70}")
    for g in gaps:
        print(f"\n  {g['from_recording']}")
        print(f"    → {g['to_recording']}")
        print(f"    Gap distance: {g['gap_distance_m']:.1f} m")
        print(f"    Gap bearing: {g['gap_bearing_deg']}°")
        if g['time_gap_sec'] is not None:
            print(f"    Time gap: {g['time_gap_sec']:.0f} sec ({g['time_gap_sec']/60:.1f} min)")
        print(f"    Note: {g['note']}")
    
    # Summary
    total_pts = sum(r["point_count"] for r in all_results)
    total_dist = sum(r["total_distance_m"] for r in all_results)
    total_duration = sum(r.get("duration_seconds", 0) for r in all_results)
    
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total recorded points: {total_pts}")
    print(f"  Total recorded distance: {total_dist:.1f} m ({total_dist/1000:.4f} km)")
    print(f"  Total recording duration: {total_duration:.0f} sec ({total_duration/60:.1f} min)")
    print(f"  Number of unrecorded gaps: {len(gaps)}")
    print(f"  Total gap distance: {sum(g['gap_distance_m'] for g in gaps):.1f} m")
    print(f"  All files valid GPX: {all(r['valid'] for r in all_results)}")
    
    # Block 34 indoor corridor gap (gap between Track C end and Track D start)
    if len(gaps) >= 3:
        blk34_gap = gaps[2]  # C→D gap
        print(f"\n  Block 34 Indoor Corridor:")
        print(f"    GPS endpoint displacement: {blk34_gap['gap_distance_m']:.1f} m")
        print(f"    This gap represents the unrecorded indoor passage through Block 34.")
        print(f"    NOT a measured walking distance.")
    
    # Save JSON report
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source_files": GPX_FILES,
        "source_directory": str(RAW_DIR),
        "segment_labels": SEGMENT_LABELS,
        "tracks": all_results,
        "gaps": gaps,
        "summary": {
            "total_points": total_pts,
            "total_distance_m": round(total_dist, 2),
            "total_distance_km": round(total_dist / 1000, 4),
            "total_duration_sec": round(total_duration, 1),
            "unrecorded_gaps": len(gaps),
            "total_gap_distance_m": round(sum(g["gap_distance_m"] for g in gaps), 2),
            "all_valid": all(r["valid"] for r in all_results),
        },
    }
    
    report_path = OUTPUT_DIR / "gpx_analysis_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved: {report_path}")
    
    # Save GeoJSON for map overlay
    geojson = tracks_to_geojson(all_parsed, all_results)
    geojson_path = OUTPUT_DIR / "verified_tracks_overlay.geojson"
    with open(geojson_path, "w") as f:
        json.dump(geojson, f, indent=2)
    print(f"  GeoJSON overlay saved: {geojson_path}")
    
    # Verify original files were not modified
    print(f"\n  Verifying source files unchanged...")
    for i, fname in enumerate(GPX_FILES):
        filepath = RAW_DIR / fname
        with open(filepath, "rb") as f:
            current_hash = hashlib.sha256(f.read()).hexdigest()
        matches = current_hash == all_results[i]["file_hash"]
        status = "✓" if matches else "✗ MODIFIED!"
        print(f"    {status} {fname}")
    
    print(f"\n{'=' * 70}")
    print("Stage 1 complete. All analysis is read-only.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
