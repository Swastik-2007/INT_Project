import urllib.request, json, urllib.parse, sys, os
from pathlib import Path
from datetime import datetime, timedelta
from jose import jwt
from dotenv import load_dotenv

# Load secret key for test JWT generation without altering .env
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecretkey")

results = []

def test(name, fn):
    try:
        fn()
        results.append((name, 'PASSED', ''))
    except Exception as e:
        results.append((name, 'FAILED', str(e)))

# 1. Public homepage accessible without login
def t1():
    req = urllib.request.Request('http://127.0.0.1:5173/')
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
        html = r.read().decode()
        assert '<div id="root">' in html
test('1. Public Homepage (/) accessible without login', t1)

# 2. Interactive Map accessible without login
def t2():
    req = urllib.request.Request('http://127.0.0.1:5173/map')
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
test('2. Interactive Map (/map) accessible without login', t2)

# 3. Admin login page accessible
def t3():
    req = urllib.request.Request('http://127.0.0.1:5173/admin/login')
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
test('3. Admin Login (/admin/login) accessible', t3)

# 4. Admin survey tool accessible
def t4():
    req = urllib.request.Request('http://127.0.0.1:5173/admin/survey')
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
test('4. GPS Survey Tool (/admin/survey) accessible', t4)

# 5. Public /api/locations returns actual DB records through Vite proxy
def t5():
    req = urllib.request.Request('http://127.0.0.1:5173/api/locations')
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
        data = json.loads(r.read().decode())
        locs = data if isinstance(data, list) else data.get('value', [])
        assert len(locs) >= 5, f'Expected >=5 locations, got {len(locs)}'
        blocks = [l.get('block_number') for l in locs]
        assert '28' in blocks and '34' in blocks
test('5. Public /api/locations via Vite proxy returns database records', t5)

# 6. Route API correctly identifies unmapped routes
def t6():
    req = urllib.request.Request('http://127.0.0.1:5173/api/route?origin_id=1&destination_id=4')
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
        res = json.loads(r.read().decode())
        assert res.get('available') is False
        assert 'awaiting mapping' in res.get('message', '').lower()
test('6. Public /api/route returns unmapped notice without fake routes', t6)

# 7. Admin login strictly rejects invalid credentials (401) — requiring real configured password
def t7():
    data = urllib.parse.urlencode({'username': 'admin', 'password': 'invalid_test_password'}).encode()
    req = urllib.request.Request('http://127.0.0.1:5173/api/admin/token', data=data, method='POST')
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, 'Expected 401 Unauthorized for incorrect password'
    except urllib.error.HTTPError as e:
        assert e.code == 401, f'Expected 401, got {e.code}'
test('7. Admin login strictly rejects invalid credentials (401)', t7)

# 8. Unauthenticated requests to /api/admin/surveys are rejected (401)
def t8():
    # GET rejected
    req = urllib.request.Request('http://127.0.0.1:5173/api/admin/surveys')
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, 'Expected 401 Unauthorized for GET /api/admin/surveys'
    except urllib.error.HTTPError as e:
        assert e.code == 401, f'Expected 401, got {e.code}'
    # POST rejected (verifying write protection without modifying database)
    post_req = urllib.request.Request(
        'http://127.0.0.1:5173/api/admin/surveys',
        data=b'{"name":"unauthorized_attempt"}',
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        urllib.request.urlopen(post_req, timeout=5)
        assert False, 'Expected 401 Unauthorized for unauthenticated POST'
    except urllib.error.HTTPError as e:
        assert e.code == 401, f'Expected 401, got {e.code}'
test('8. Admin protected /api/admin/surveys rejects unauthenticated calls (401)', t8)

# 9. Authenticated request to /api/admin/surveys succeeds (200) via non-mutating GET
def t9():
    # Generate ephemeral test JWT from server SECRET_KEY without database writes
    exp = datetime.utcnow() + timedelta(hours=1)
    tok = jwt.encode({'sub': 'admin', 'exp': exp}, SECRET_KEY, algorithm='HS256')
    req = urllib.request.Request('http://127.0.0.1:5173/api/admin/surveys', headers={'Authorization': f'Bearer {tok}'})
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
        data = json.loads(r.read().decode())
        assert isinstance(data, list)
test('9. Admin protected /api/admin/surveys accepts valid JWT (200, non-mutating)', t9)

# 10. Database read-only verification (confirming existing locations are preserved and intact)
def t10():
    req = urllib.request.Request('http://127.0.0.1:5173/api/locations')
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
        data = json.loads(r.read().decode())
        locs = data if isinstance(data, list) else data.get('value', [])
        assert len(locs) >= 5, f"Expected 5 locations, found {len(locs)}"
        names = [l['name'] for l in locs]
        for expected in ['Block 28', 'Block 29', 'Block 30', 'Block 34', 'Block 36']:
            assert expected in names, f"Missing expected location: {expected}"
test('10. Database integrity check (all real records preserved without modification)', t10)

# 11. Survey tracks endpoint returns valid GeoJSON with 4 tracks and start/end markers
def t11():
    req = urllib.request.Request('http://127.0.0.1:5173/api/survey-tracks')
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
        data = json.loads(r.read().decode())
        assert data.get('type') == 'FeatureCollection'
        features = data.get('features', [])
        tracks = [f for f in features if f.get('properties', {}).get('type') == 'recorded_track']
        assert len(tracks) == 4, f"Expected 4 tracks, got {len(tracks)}"
        for t in tracks:
            assert t['properties']['verified'] is False
            assert t['geometry']['type'] == 'LineString'
test('11. Public /api/survey-tracks returns 4 unverified GeoJSON tracks', t11)

# 12. Survey analysis report endpoint returns valid stats
def t12():
    req = urllib.request.Request('http://127.0.0.1:5173/api/survey-tracks/analysis')
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
        data = json.loads(r.read().decode())
        assert 'summary' in data
        assert data['summary']['total_points'] == 263
        assert len(data.get('tracks', [])) == 4
        assert len(data.get('gaps', [])) == 3
test('12. Public /api/survey-tracks/analysis returns full GPX report (263 pts, 4 tracks, 3 gaps)', t12)

# 13. Public /api/network/status returns pedestrian routing network topology
def t13():
    req = urllib.request.Request('http://127.0.0.1:5173/api/network/status')
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
        data = json.loads(r.read().decode())
        assert data.get('recorded_track_count') == 4
        assert data.get('recorded_point_count') == 263
        assert data.get('disconnected_components_count') == 1
        assert data.get('routing_status', {}).get('available') is True
        assert data.get('routing_status', {}).get('public_navigation_ready') is True
        assert len(data.get('unrecorded_gaps', [])) == 3
        assert len(data.get('confirmed_connections', [])) == 3
test('13. Public /api/network/status returns 4 tracks, 1 connected component, routing active', t13)

# 14. Route API supports GPS snapping coordinates and returns safe unmapped notice
def t14():
    req = urllib.request.Request('http://127.0.0.1:5173/api/route?origin_lat=31.253018&origin_lon=75.703517&destination_id=4&gps_accuracy=8.0')
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
        res = json.loads(r.read().decode())
        assert res.get('available') is False
        assert 'awaiting mapping' in res.get('message', '').lower()
        assert res.get('origin', {}).get('id') == -1
        assert res.get('destination', {}).get('id') == 4
test('14. Public /api/route with live GPS coordinates snaps and handles unverified safely', t14)

# 15. Public /api/verification/status returns verification metrics
def t15():
    req = urllib.request.Request('http://127.0.0.1:5173/api/verification/status')
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
        data = json.loads(r.read().decode())
        assert 'tracks' in data
        assert data['tracks']['total'] == 4
        assert 'gaps' in data
        assert data['gaps']['total'] == 3
        assert 'entrances' in data
        assert data['entrances']['total'] >= 5
        assert data['routing_ready'] is True
        assert data['distance']['total_meters'] == 1734.03
test('15. Public /api/verification/status returns verification progress summary and routing readiness', t15)

# 16. Admin verification endpoint strictly requires authentication
def t16():
    req = urllib.request.Request('http://127.0.0.1:5173/api/admin/verification/pending')
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, 'Expected 401 Unauthorized'
    except urllib.error.HTTPError as e:
        assert e.code == 401, f'Expected 401, got {e.code}'
test('16. Admin /api/admin/verification/pending rejects unauthenticated calls (401)', t16)

# 17. Authenticated request to /api/admin/verification/pending succeeds (non-mutating)
def t17():
    exp = datetime.utcnow() + timedelta(hours=1)
    tok = jwt.encode({'sub': 'admin', 'exp': exp}, SECRET_KEY, algorithm='HS256')
    req = urllib.request.Request(
        'http://127.0.0.1:5173/api/admin/verification/pending',
        headers={'Authorization': f'Bearer {tok}'}
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
        data = json.loads(r.read().decode())
        assert len(data.get('tracks', [])) == 4
        assert len(data.get('gaps', [])) == 3
        assert len(data.get('locations', [])) >= 5
test('17. Admin /api/admin/verification/pending accepts valid JWT and lists items', t17)

# 18. Authenticated request to /api/admin/verification/history succeeds
def t18():
    exp = datetime.utcnow() + timedelta(hours=1)
    tok = jwt.encode({'sub': 'admin', 'exp': exp}, SECRET_KEY, algorithm='HS256')
    req = urllib.request.Request(
        'http://127.0.0.1:5173/api/admin/verification/history',
        headers={'Authorization': f'Bearer {tok}'}
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
        logs = json.loads(r.read().decode())
        assert isinstance(logs, list)
test('18. Admin /api/admin/verification/history returns decision audit log', t18)

# 19. Admin Verification UI page accessible
def t19():
    req = urllib.request.Request('http://127.0.0.1:5173/admin/verify')
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
        html = r.read().decode()
        assert '<div id="root">' in html
test('19. Route Verification Interface (/admin/verify) accessible in frontend', t19)

# 20. Live routing from BH4 Area to Main Gate is functional
def t20():
    req = urllib.request.Request('http://127.0.0.1:5173/api/route?origin_id=-2&destination_id=-1')
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200
        res = json.loads(r.read().decode())
        assert res.get('available') is True
        assert abs(res.get('distance', 0) - 1837.8) < 2.0
        assert abs(res.get('duration', 0) - 1531) < 10
        assert res.get('has_indoor') is True
test('20. Live campus routing from BH4 Area to Main Gate available (1837.8m, 1531s)', t20)

print('\n' + '='*70)
print('AUTOMATED VERIFICATION TEST RESULTS')
print('='*70)
for name, status, err in results:
    icon = 'PASS' if status == 'PASSED' else 'FAIL'
    print(f'[{icon}] {name}')
    if err:
        print(f'       Error: {err}')
print('='*70)
passed_count = sum(1 for _, s, _ in results if s == 'PASSED')
print(f'Summary: {passed_count}/{len(results)} tests passed.')
print('='*70)

if passed_count != len(results):
    sys.exit(1)
