"""Free fixture: project a GeoJSON file onto inline SVG, the way the map agent is told to."""
import json, math, sys, pathlib
src = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2])
fc = json.loads(src.read_text())
pts = [c for f in fc['features'] for c in ([f['geometry']['coordinates']] if f['geometry']['type'] == 'Point' else f['geometry']['coordinates'])]
lons, lats = [p[0] for p in pts], [p[1] for p in pts]
k = math.cos(math.radians(sum(lats) / len(lats)))
pad = 0.01
x0, x1, y0, y1 = min(lons) - pad, max(lons) + pad, min(lats) - pad, max(lats) + pad
W = 800; H = int(W * (y1 - y0) / ((x1 - x0) * k))
proj = lambda p: ((p[0] - x0) / (x1 - x0) * W, H - (p[1] - y0) / (y1 - y0) * H)
parts = []
for f in fc['features']:
    g = f['geometry']
    if g['type'] == 'LineString':
        parts.append('<polyline fill="none" stroke="#c2410c" stroke-width="3" stroke-dasharray="8 5" points="%s"/>' % ' '.join('%.1f,%.1f' % proj(p) for p in g['coordinates']))
for f in fc['features']:
    g = f['geometry']
    if g['type'] == 'Point':
        x, y = proj(g['coordinates'])
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="#0f766e" stroke="#fff" stroke-width="3"/><text x="{x + 14:.1f}" y="{y + 5:.1f}" font-size="16" fill="#1c1917">{f["properties"]["name"]}</text>')
grid = ''.join(f'<line x1="{i * W / 4:.0f}" y1="0" x2="{i * W / 4:.0f}" y2="{H}" stroke="#d6d3d1"/>' for i in range(1, 4))
out.write_text(f'<!doctype html><meta charset="utf-8"><body style="margin:0;background:#f5f5f4;font-family:Georgia,serif"><svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;background:#e7e5e4">{grid}{"".join(parts)}</svg><p style="margin:8px 16px;color:#57534e">Paris landmarks, equirectangular projection. {len(fc["features"])} features.</p></body>')
