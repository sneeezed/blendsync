"""
BlendSync Phase 1 — Test Script
================================
Run this from Blender's Scripting workspace (Text Editor > Run Script).

The script does three things:
  1. Serializes the current scene and pretty-prints the JSON.
  2. Simulates a second snapshot with manual changes applied in-memory.
  3. Runs the diff engine and prints the results.

You don't need to install the addon first — the script adds the blendsync
package directory to sys.path so it can import directly.
"""

import sys
import os
import json
import copy

# ── Path setup ──────────────────────────────────────────────────────────────
# Point this to wherever you cloned / extracted the BlendSync folder.
# If this script sits next to the `blendsync/` folder you don't need to change it.
BLENDSYNC_DIR = "/Users/matiassevak/Desktop/BlendSync"
if BLENDSYNC_DIR not in sys.path:
    sys.path.insert(0, BLENDSYNC_DIR)

# Re-import in case a previous run cached an old version
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith('blendsync'):
        del sys.modules[mod_name]

from blendsync import serializer, differ

# ── 1. Serialize the current scene ──────────────────────────────────────────
print("\n" + "=" * 60)
print("SNAPSHOT A — current scene")
print("=" * 60)

snapshot_a = serializer.serialize_scene()
print(json.dumps(snapshot_a, indent=2))

# ── 2. Build a fake snapshot_b with deliberate mutations ────────────────────
snapshot_b = copy.deepcopy(snapshot_a)

# Move the first object (if any)
if snapshot_b['objects']:
    obj = snapshot_b['objects'][0]
    obj_name = obj['name']
    obj['location'] = [loc + 2.0 for loc in obj['location']]
    print(f"\n[test] Will move object '{obj_name}' by +2 on all axes")

# Change roughness of the first material (if any)
if snapshot_b['materials']:
    mat = snapshot_b['materials'][0]
    mat_name = mat['name']
    original_roughness = mat['roughness']
    mat['roughness'] = round((original_roughness + 0.3) % 1.0, 4)
    print(f"[test] Will change material '{mat_name}' roughness "
          f"{original_roughness} → {mat['roughness']}")

# Add a fake object
snapshot_b['objects'].append({
    "name": "__TestNewObject__",
    "type": "MESH",
    "location": [5.0, 5.0, 0.0],
    "rotation": [0.0, 0.0, 0.0],
    "scale": [1.0, 1.0, 1.0],
    "parent": None,
    "collection": "Scene Collection",
    "visible": True,
    "modifiers": [],
    "mesh_summary": {"vertex_count": 8, "poly_count": 6, "has_uv": False},
    "geometry_hash": "aabbccdd11223344",
})
print("[test] Will add fake object '__TestNewObject__'")

# Remove the last object (if more than one exists)
if len(snapshot_b['objects']) > 2:
    removed = snapshot_b['objects'].pop(-2)
    print(f"[test] Will remove object '{removed['name']}'")

# Change resolution
snapshot_b['render_settings']['resolution_x'] = 2560
print("[test] Will change resolution_x to 2560")

# ── 3. Run the diff ──────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("DIFF RESULTS (snapshot_a → snapshot_b)")
print("=" * 60)

changes = differ.diff(snapshot_a, snapshot_b)

if not changes:
    print("No changes detected.")
else:
    for i, change in enumerate(changes, 1):
        print(f"\n[{i}] type: {change['type']}")
        for k, v in change.items():
            if k != 'type':
                print(f"     {k}: {v}")

print(f"\nTotal changes: {len(changes)}")
print("=" * 60)
print("Test complete. Check the output above for correctness.")
