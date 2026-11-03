---
name: map-geojson
description: Rules for correct GeoJSON maps (places, routes, regions): coordinate order, real coordinates, route order, closed rings. Load before writing map.json.
license: MIT
metadata:
  source: original, written for agent-route from the agents-cc-20261031 failures
---
# Writing a map that puts things in the right place

Baseline failures: a missing file, a route stop 11 km off, a missing region, and routes that skipped or reordered stops. Judges also marked down wrong attributions and invented geometry.

## Method

1. List every place, route and region the task names. One feature per item, named as the task names it.
2. Write coordinates from memory of real places, as `[lng, lat]`. Longitude is the east-west value: Mumbai is `[72.8777, 19.0760]`, New York `[-74.0060, 40.7128]`. If you wrote the pair the other way, the first number will be the smaller one for most of Europe, Africa, India and North America, which is a tell.
3. Sanity-check each point against a rough bounding box you know: Paris near lng 2.3, lat 48.9; Los Angeles near lng -118.2, lat 34.0; Berlin near lng 13.4, lat 52.5. Landmarks should sit within about 1 km of the real spot. Do not move a landmark to fit a route.
4. Build the collection in a Python script and `json.dump` it to `out/map.json`. Write the file even when you are unsure of one coordinate; use your best estimate and say so in the feature description.

## Routes

- A LineString visits the stops in the order the task gives. Include every stop's coordinate as a vertex, in that order, and add intermediate vertices at real turns when you know them. Do not add straight segments across water or between distant cities if a known waypoint exists.
- Add each stop as its own Point too, named, with a short `description`.
- A trek, trail, coast or border follows the real path through well-known waypoints. Name the waypoints.

## Regions

- A Polygon ring is closed: the last position equals the first. Outer ring counterclockwise.
- Draw the region with at least 5 vertices around real boundaries or landmarks. A territory split (north, south, east, west) gives each part its own polygon that does not overlap the others.
- Name every region as the task names it.

## Descriptions

Say only what you are sure of. A wrong date, owner or attribution in a description costs more than leaving it out.

## Self-check before you finish

Print each feature's name, geometry type and first coordinate. Confirm:
- Every item from step 1 is present and spelled as the task spells it.
- Each `[lng, lat]` passes the bounding-box check.
- Route vertices follow the stop order; polygon rings close.
- The file parses with `json.load`.
