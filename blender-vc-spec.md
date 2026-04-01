# BlendSync — Async Version Control for Blender

### Project Specification & Implementation Guide

---

## What This Is

A Blender addon + lightweight backend that gives Blender users Git-style async collaboration and version control. Users can commit snapshots of their projects, push/pull to a shared repository, propose changes like pull requests, and review human-readable diffs — all without leaving Blender.

**The key insight:** instead of trying to diff binary .blend files, serialize the scene to JSON on every save and diff that. Store the binary .blend for rollback. Show the JSON diff to the user.

**Storage model:** users bring their own GitHub repository. You never pay for storage. You are the software, not the host.

---

## Core Features (v1 Scope)

- Commit scene snapshots with a message
- Push/pull to a user-owned GitHub repo
- Human-readable diff between any two commits ("Object 'Arm_L' moved, Material 'Skin' roughness changed 0.4→0.6, geometry of 'Head' mesh modified")
- Branch support — collaborator works on a branch, proposes merge
- Owner reviews diff and accepts/rejects — no auto-merging, always manual
- Conflict detection (both people modified same object — flag it, don't try to resolve it)
- Addon preferences panel for GitHub auth setup

**Out of scope for v1:**

- Real-time collaboration
- Auto-merging of any kind
- Hosting your own storage
- Support for externally linked .blend libraries (later problem)

---

## Architecture Overview

```
Blender Addon (Python / bpy)
    │
    ├── save_post handler → triggers on every Ctrl+S
    ├── Scene Serializer → bpy.data → JSON
    ├── Diff Engine → compare two JSON snapshots
    ├── Git Interface → subprocess calls to git CLI
    └── UI Panels → sidebar panels in Blender
         ├── Commit panel
         ├── History panel
         └── Review/diff panel

GitHub Repo (user-owned)
    ├── snapshots/
    │   ├── abc123.json       ← serialized scene (diffable)
    │   └── abc123.blend      ← binary file (stored via Git LFS)
    ├── commits.json          ← commit log/metadata
    └── branches/
        └── feature-arm-rig/
            └── ...
```

No custom backend needed for v1. Everything goes through git CLI + GitHub.

---

## File Structure of the Addon

```
blendsync/
├── __init__.py           ← bl_info, register(), unregister()
├── operators.py          ← all bpy.types.Operator classes (buttons)
├── panels.py             ← all bpy.types.Panel classes (UI)
├── preferences.py        ← AddonPreferences (GitHub token, repo URL)
├── serializer.py         ← bpy.data → JSON (core logic)
├── differ.py             ← JSON diff engine
├── git_interface.py      ← subprocess wrappers for git commands
└── handlers.py           ← bpy.app.handlers registrations
```

---

## Module Breakdown

### `serializer.py` — The Heart of the System

This is the most important file. It walks `bpy.data` and extracts everything diffable into a structured JSON document.

**What to serialize:**

```python
scene = {
    "metadata": {
        "blender_version": bpy.app.version_string,
        "scene_name": bpy.context.scene.name,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "fps": scene.render.fps,
    },
    "render_settings": {
        "engine": scene.render.engine,
        "resolution_x": scene.render.resolution_x,
        "resolution_y": scene.render.resolution_y,
        "film_transparent": scene.render.film_transparent,
    },
    "objects": [...],      # see below
    "materials": [...],    # see below
    "collections": [...],
    "cameras": [...],
    "lights": [...],
    "world": {...},
}
```

**Objects:**

```python
{
    "name": obj.name,
    "type": obj.type,          # MESH, ARMATURE, CAMERA, LIGHT, EMPTY...
    "location": list(obj.location),
    "rotation": list(obj.rotation_euler),
    "scale": list(obj.scale),
    "parent": obj.parent.name if obj.parent else None,
    "collection": obj.users_collection[0].name,
    "visible": obj.visible_get(),
    "modifiers": [
        {"name": m.name, "type": m.type, "show_viewport": m.show_viewport}
        for m in obj.modifiers
    ],
    "mesh_summary": {         # NOT raw geometry — just metadata
        "vertex_count": len(obj.data.vertices) if obj.type == 'MESH' else None,
        "poly_count": len(obj.data.polygons) if obj.type == 'MESH' else None,
        "has_uv": bool(obj.data.uv_layers) if obj.type == 'MESH' else None,
    },
    "geometry_hash": hash_mesh(obj),   # SHA256 of vertex data — changes = "geometry modified"
}
```

**Geometry hash** — this is how you detect mesh changes without storing raw geometry in the diff:

```python
import hashlib, struct

def hash_mesh(obj):
    if obj.type != 'MESH':
        return None
    mesh = obj.data
    h = hashlib.sha256()
    for v in mesh.vertices:
        h.update(struct.pack('fff', *v.co))
    return h.hexdigest()[:16]   # first 16 chars is enough
```

**Materials:**

```python
{
    "name": mat.name,
    "use_nodes": mat.use_nodes,
    "roughness": mat.roughness,
    "metallic": mat.metallic,
    "node_tree": serialize_node_tree(mat.node_tree) if mat.use_nodes else None,
}
```

**Node trees** (shader graphs):

```python
def serialize_node_tree(tree):
    return {
        "nodes": [
            {
                "name": node.name,
                "type": node.type,
                "location": list(node.location),
                "inputs": {
                    inp.name: inp.default_value
                    for inp in node.inputs
                    if hasattr(inp, 'default_value')
                },
            }
            for node in tree.nodes
        ],
        "links": [
            {
                "from_node": link.from_node.name,
                "from_socket": link.from_socket.name,
                "to_node": link.to_node.name,
                "to_socket": link.to_socket.name,
            }
            for link in tree.links
        ]
    }
```

---

### `differ.py` — The Diff Engine

Takes two JSON snapshots, compares them, and returns a human-readable list of changes.

**Output format:**

```python
[
    {"type": "object_moved",    "name": "Arm_L",   "from": [0,0,0], "to": [1.2, 0, 0.5]},
    {"type": "object_added",    "name": "Sword"},
    {"type": "object_removed",  "name": "OldProp"},
    {"type": "geometry_changed","name": "Head",    "detail": "vertex count 8420 → 9102"},
    {"type": "material_changed","name": "Skin",    "property": "roughness", "from": 0.4, "to": 0.6},
    {"type": "node_changed",    "material": "Skin","node": "Principled BSDF", "input": "Roughness"},
    {"type": "render_changed",  "property": "resolution_x", "from": 1920, "to": 2560},
    {"type": "modifier_added",  "object": "Body",  "modifier": "Subdivision"},
]
```

**Diff logic (pseudocode):**

```python
def diff(snapshot_a, snapshot_b):
    changes = []

    # Compare objects
    a_objs = {o['name']: o for o in snapshot_a['objects']}
    b_objs = {o['name']: o for o in snapshot_b['objects']}

    for name in set(a_objs) | set(b_objs):
        if name not in a_objs:
            changes.append({"type": "object_added", "name": name})
        elif name not in b_objs:
            changes.append({"type": "object_removed", "name": name})
        else:
            diff_object(a_objs[name], b_objs[name], changes)

    # Compare materials, render settings, etc.
    diff_materials(snapshot_a, snapshot_b, changes)
    diff_render(snapshot_a, snapshot_b, changes)

    return changes
```

---

### `git_interface.py` — Git as the Backend

All git operations done via `subprocess`. Requires git to be installed on the user's machine (reasonable assumption for developers, needs a clear error message if missing).

```python
import subprocess, os

def run_git(args, cwd):
    result = subprocess.run(
        ['git'] + args,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise GitError(result.stderr)
    return result.stdout

def commit(repo_path, message):
    run_git(['add', '.'], cwd=repo_path)
    run_git(['commit', '-m', message], cwd=repo_path)

def push(repo_path):
    run_git(['push', 'origin', 'HEAD'], cwd=repo_path)

def pull(repo_path):
    run_git(['pull', 'origin', 'HEAD'], cwd=repo_path)

def create_branch(repo_path, branch_name):
    run_git(['checkout', '-b', branch_name], cwd=repo_path)

def get_log(repo_path):
    output = run_git(['log', '--oneline', '-20'], cwd=repo_path)
    # parse into list of {hash, message}
    ...

def checkout(repo_path, commit_hash):
    run_git(['checkout', commit_hash], cwd=repo_path)
```

**Git LFS setup** — needed for .blend files. The addon should initialize this automatically on first use:

```python
def setup_lfs(repo_path):
    run_git(['lfs', 'install'], cwd=repo_path)
    # write .gitattributes
    with open(os.path.join(repo_path, '.gitattributes'), 'w') as f:
        f.write('*.blend filter=lfs diff=lfs merge=lfs -text\n')
```

---

### `handlers.py` — Hooking Into Blender

```python
import bpy
from . import serializer, git_interface

def on_save_post(scene, *args):
    prefs = bpy.context.preferences.addons['blendsync'].preferences
    if not prefs.auto_snapshot:
        return
    # serialize and write JSON alongside the .blend
    data = serializer.serialize_scene()
    json_path = bpy.data.filepath.replace('.blend', '.blendsync.json')
    with open(json_path, 'w') as f:
        import json
        json.dump(data, f, indent=2)

def register():
    bpy.app.handlers.save_post.append(on_save_post)

def unregister():
    bpy.app.handlers.save_post.remove(on_save_post)
```

---

### `preferences.py` — Persistent Settings

```python
class BlendSyncPreferences(bpy.types.AddonPreferences):
    bl_idname = 'blendsync'

    github_token: bpy.props.StringProperty(
        name="GitHub Token",
        subtype='PASSWORD'
    )
    repo_url: bpy.props.StringProperty(
        name="Repository URL"
    )
    auto_snapshot: bpy.props.BoolProperty(
        name="Auto-snapshot on save",
        default=True
    )
    local_repo_path: bpy.props.StringProperty(
        name="Local repo path",
        subtype='DIR_PATH'
    )
```

---

## The Async Collaboration Flow

### Setup (one time)

1. User installs addon
2. Goes to addon preferences, pastes GitHub token and repo URL
3. Addon initializes local git repo, sets up LFS, links to remote

### Solo version control

1. User works in Blender, saves normally (Ctrl+S)
2. `save_post` fires, JSON snapshot written alongside .blend
3. User opens BlendSync panel, types a commit message, clicks Commit
4. Addon runs `git add . && git commit -m "message" && git push`
5. History panel shows log of all commits, click any to see its diff

### Inviting a collaborator

1. Owner adds collaborator to GitHub repo (standard GitHub — addon doesn't handle this)
2. Collaborator installs addon, clones repo, points addon at local path
3. Collaborator pulls latest, gets both the .blend and the JSON snapshot

### Proposing changes

1. Collaborator clicks "New Branch" in BlendSync panel, gives it a name
2. They work, commit their changes to that branch
3. Click "Propose Changes" — addon pushes branch to GitHub
4. Owner sees notification in BlendSync panel: "Alex proposed changes on branch 'feature-sword'"

### Reviewing changes

1. Owner clicks "Review" on the proposal
2. BlendSync fetches the branch's latest JSON snapshot
3. Diff engine compares it to main's JSON snapshot
4. Diff panel shows the human-readable list of changes
5. For geometry changes: "Head mesh modified (8420 → 9102 vertices)" — no detail possible, but owner can preview by temporarily checking out the branch
6. Owner clicks Accept → addon merges branch into main (fast-forward only — no auto-merge of conflicts)
7. Or owner clicks Reject with an optional comment

### Conflict detection

Before allowing a merge, the addon checks if any object was modified on BOTH branches since they diverged:

```python
def detect_conflicts(base_snapshot, branch_a_snapshot, branch_b_snapshot):
    conflicts = []
    for obj_name in all_objects:
        changed_in_a = object_changed(base_snapshot, branch_a_snapshot, obj_name)
        changed_in_b = object_changed(base_snapshot, branch_b_snapshot, obj_name)
        if changed_in_a and changed_in_b:
            conflicts.append(obj_name)
    return conflicts
```

If conflicts exist, the merge is blocked. Owner must manually decide which version to keep, then commit that as the resolution.

---

## Roadblocks & How to Handle Them

### 1. File paths and linked assets

**Problem:** .blend files reference external textures, HDRIs, other .blend files by absolute path. If a collaborator has a different folder structure, assets go missing.

**v1 solution:** Before committing, run `bpy.ops.file.pack_all()` to embed all external assets into the .blend file itself. Warn the user this increases file size. Add a preference to toggle this.

**Later solution:** build an asset registry — map asset filenames to hashes, store assets separately in the repo, resolve paths on checkout.

### 2. Git LFS limits

**Problem:** GitHub's free Git LFS is 1GB storage + 1GB bandwidth/month. A project with many .blend snapshots can hit this fast.

**Mitigation:** Only commit .blend when the user explicitly clicks "Commit" — not on every auto-snapshot. The JSON snapshots are tiny (usually <100KB) and commit freely. The .blend only gets committed when the user decides it's a meaningful checkpoint.

**Later:** let users bring their own LFS backend (Cloudflare R2 is cheap, ~$0.015/GB/month).

### 3. Git not installed

**Problem:** Not all Blender users have git installed.

**Solution:** Check for git on addon load. If missing, show a clear error with a link to git-scm.com. Consider bundling libgit2 (via pygit2) as a fallback — but this is complex cross-platform, so v1 just requires git.

### 4. Blender's threading restrictions

**Problem:** `bpy` calls must happen on the main thread. Git operations (push/pull) can take seconds. If you do them synchronously they freeze Blender.

**Solution:** Use `bpy.app.timers` for deferred execution, or run git in a `threading.Thread` and only touch `bpy` from a timer callback. For v1, sync is acceptable with a clear loading indicator — just warn users it'll take a moment.

### 5. Merge safety

**Problem:** If you do a `git merge` on binary .blend files, git produces a broken file.

**Solution:** Never run `git merge` on the .blend. Instead:

- Accept = fast-forward only (`git merge --ff-only`)
- If fast-forward isn't possible, require the collaborator to rebase first
- The JSON can be safely merged by git since it's text, but don't rely on the result — always re-serialize from the actual .blend

### 6. Blender version mismatches

**Problem:** A .blend saved in Blender 4.2 might not open correctly in Blender 3.6.

**Solution:** Store `blender_version` in the JSON snapshot metadata. Warn users when checking out a snapshot made in a different major version.

---

## Build Order (Phase by Phase)

### Phase 1 — Local version control only

**Goal:** single user, no network, just commit/checkout on their own machine.

1. Write `serializer.py` — get a clean JSON out of a real .blend file
2. Write `differ.py` — compare two JSONs, get readable output
3. Wire up `save_post` handler to auto-write JSON on save
4. Basic git init + commit via `git_interface.py`
5. Simple panel in Blender: Commit button + message field + history list

**This alone is a shippable, useful tool.** Ship it here before adding anything.

### Phase 2 — GitHub sync

1. Add preferences panel for GitHub token + repo URL
2. Push/pull buttons in the panel
3. Set up Git LFS on first push
4. Handle auth errors clearly

### Phase 3 — Collaboration

1. Branch creation
2. "Propose changes" flow (push branch, write metadata)
3. Diff review panel — fetch branch snapshot, run differ, display results
4. Accept/reject merge
5. Conflict detection

### Phase 4 — Polish

1. Asset packing on commit
2. Thumbnail preview of commits (render a small preview, store as PNG)
3. Better diff display (highlight changed values visually)
4. Notifications when collaborators propose changes

---

## Starting Point for Coding Agent

Heres the promt:

> "I'm building a Blender addon called BlendSync. Start with Phase 1 only. Create the addon file structure with `__init__.py`, `serializer.py`, and `differ.py`. 
>
> `serializer.py` should have a `serialize_scene()` function that uses `bpy.data` and `bpy.context` to extract objects (name, type, location, rotation, scale, parent, collection, modifiers, and a SHA256 hash of vertex positions for meshes), materials (name, roughness, metallic, and node tree if use_nodes), render settings (engine, resolution, fps), and scene metadata (blender version, scene name, frame range) into a dictionary.
>
> `differ.py` should have a `diff(snapshot_a, snapshot_b)` function that compares two of these dictionaries and returns a list of change objects, each with a `type`, `name`, and relevant `from`/`to` values.
>
> Don't add any UI yet. Just the serialization and diff logic, with a test script I can run from Blender's scripting workspace to verify the output."

That gives you something you can test immediately in Blender's built-in Python console before writing a single line of UI code.

---

## Resources

- [Blender Python API docs](https://docs.blender.org/api/current/)
- [bpy.app.handlers reference](https://docs.blender.org/api/current/bpy.app.handlers.html)
- [Addon tutorial (official)](https://docs.blender.org/manual/en/latest/advanced/scripting/addon_tutorial.html)
- [Git LFS docs](https://git-lfs.com/)
- [GitHub REST API](https://docs.github.com/en/rest) — for later if you want to create PRs programmatically
- [VS Code + Blender extension](https://marketplace.visualstudio.com/items?itemName=JacquesLucke.blender-development) — makes addon dev much smoother

