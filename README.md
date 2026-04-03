# BlendSync

Git-style version control for Blender. Commit snapshots of your scene, browse history, and track changes — all without leaving Blender.

---

## Requirements

- Blender 3.6 or later
- [Git](https://git-scm.com/) installed and available on your system PATH

---

## Installation

1. Download or clone this repository.
2. In Blender, go to **Edit → Preferences → Add-ons → Install** and select the `blendsync` folder (or a zipped version of it).
3. Enable the **BlendSync** addon.
4. Save your `.blend` file somewhere on disk — BlendSync needs a file path to work.
5. Open the **BlendSync** tab in the 3D Viewport sidebar (press `N` to open it).

---

## Quick Start

1. Click **Initialize Repository** to create a git repo in the same folder as your `.blend` file.
2. Work on your scene normally.
3. When you want to save a checkpoint, type a message in the commit field and click **Commit Snapshot**.
4. Use the **History** panel to browse past commits and revert to any of them.
5. The **Tracked Changes** panel shows what has changed since your last commit.

---

## Preferences

Open **Edit → Preferences → Add-ons → BlendSync** to access:

| Setting | Default | Description |
|---|---|---|
| Auto-snapshot on save | On | Serializes the scene to JSON every time you press Ctrl+S. Disable this if saves feel slow on very complex scenes — the snapshot will still be generated at commit time. |

---

## Known Limitations

### Git must be installed before opening Blender

BlendSync checks whether git is installed **once**, when the addon first loads. This result is cached for the entire Blender session for performance reasons — checking on every UI redraw would otherwise cause significant slowdown.

**What this means:** If you install git while Blender is open, the BlendSync panel will still show "git not found on PATH" until you **restart Blender**. After restarting, it will detect git correctly.

**Fix:** Install git first, then open Blender.

---

### Manually deleting the `.git` folder is not detected live

BlendSync caches whether a given folder contains a git repository. This cache is updated when you click **Initialize Repository**, but it does not watch the filesystem for external changes.

**What this means:** If you manually delete the `.git` folder inside your project folder while Blender is open, the BlendSync panel may still appear to function normally and show stale history. Attempting to commit or refresh will fail with a git error at that point.

**Fix:** Do not delete the `.git` folder manually. If you need to reset the repository, use **Initialize Repository** again after the folder is gone, or restart Blender so the cache is cleared.

---

### Geometry hash changes after updating from an older version

The mesh hashing algorithm was updated to use a faster method (`foreach_get` instead of a per-vertex Python loop). The hash values are different from those produced by older versions of BlendSync.

**What this means:** The first time you use **Tracked Changes** or **Commit Snapshot** after updating, all mesh objects may appear as "geometry changed" even if you have not edited them. This is a one-time cosmetic issue. After that first commit, hashes will be stable and geometry change detection will work correctly again.

---

## File Structure

BlendSync creates the following files alongside your `.blend`:

| File | Purpose |
|---|---|
| `yourfile.blendsync.json` | Scene snapshot used for diffing and change tracking |
| `.git/` | Standard git repository — contains all commit history |
| `.gitignore` | Pre-configured to ignore Blender's backup files (`.blend1`, `.blend2`) |
| `.blendsync_head` | Temporary marker written when you revert to an older commit; deleted on the next commit or branch switch |

---

## Roadmap

- **Phase 2** — GitHub sync: push/pull to a user-owned GitHub repository
- **Phase 3** — Collaboration: branches, change proposals, diff review, conflict detection
- **Phase 4** — Polish: asset packing, commit thumbnails, visual diff display
