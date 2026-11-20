import urllib.request, urllib.parse, json, re

def overpass_query(query: str):
    # Use GET request to avoid 406 errors on POST without proper headers
    base_url = "https://overpass-api.de/api/interpreter"
    params = urllib.parse.urlencode({'data': query})
    url = f"{base_url}?{params}"
    headers = {
        'User-Agent': 'LPUWayfinderResearch/1.0 (+https://github.com/yourrepo)',
        'Accept': 'application/json'
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())

def fetch_blocks():
    # Approximate bounding box for LPU campus (lat_min, lon_min, lat_max, lon_max)
    bbox = "31.25,75.68,31.30,75.73"
    query = f"""
    [out:json][timeout:25];
    (
      node[\"name\"]{bbox}[\"name\"]~\"Block\\s*\\d+\" i];
      way[\"name\"]{bbox}[\"name\"]~\"Block\\s*\\d+\" i];
    );
    out center;"""
    data = overpass_query(query)
    results = []
    for el in data.get('elements', []):
        tags = el.get('tags', {})
        name = tags.get('name')
        if not name:
            continue
        m = re.search(r"Block\s*(\\d+)", name, re.I)
        if not m:
            continue
        block_num = m.group(1)
        if el['type'] == 'node':
            lat = el['lat']
            lon = el['lon']
        else:
            lat = el['center']['lat']
            lon = el['center']['lon']
        results.append({
            "block_number": block_num,
            "name": name,
            "latitude": lat,
            "longitude": lon,
            "verified": True,
            "source": "OpenStreetMap Overpass"
        })
    return results

if __name__ == "__main__":
    blocks = fetch_blocks()
    out_path = "C:/Users/swast/OneDrive/Desktop/INT_PROJECT/data/blocks_verified.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({"blocks": blocks}, f, indent=2)
    print(f"Fetched {len(blocks)} blocks, saved to {out_path}")
