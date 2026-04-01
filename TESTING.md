# BlendSync — Phase 1 Testing Guide

## Project structure

```
BlendSync/
├── blendsync/
│   ├── __init__.py
│   ├── serializer.py
│   ├── differ.py
│   ├── git_interface.py
│   ├── handlers.py
│   ├── operators.py
│   └── panels.py
├── test_blendsync.py
├── blender-vc-spec.md
└── TESTING.md
```

---

## Prerequisites

- Blender 3.6 or later
- `git` installed and on your PATH  
  Verify in Terminal: `git --version`

---

## Installing the addon in Blender

### Step 1 — Zip the addon folder

In Terminal:

```bash
cd /Users/matiassevak/Desktop/BlendSync
zip -r blendsync.zip blendsync/
```

This creates `BlendSync/blendsync.zip`.

### Step 2 — Install in Blender

1. Open Blender.
2. Go to **Edit → Preferences → Add-ons**.
3. Click **Install…** (top right).
4. Navigate to `BlendSync/blendsync.zip` and click **Install Add-on**.
5. Find **BlendSync** in the list and tick the checkbox to enable it.

### Step 3 — Open the panel

1. Open a **3D Viewport** (the default layout has one).
2. Press **N** to open the sidebar on the right.
3. Click the **BlendSync** tab.

> If the tab doesn't appear, make sure the addon is enabled (checkbox ticked in Preferences).

---

## Using the panel

### First time setup

1. **Save your .blend file** somewhere on disk (`Ctrl + S`). The addon uses the file's folder as the git repository root.
2. In the BlendSync panel, click **Initialize Repository**. This runs `git init` in that folder.

### Committing

1. Type a message in the **Commit** field (e.g. `"Initial scene"`).
2. Click **Commit Snapshot**.  
   The addon will:
   - Serialize the scene to a `.blendsync.json` file next to your `.blend`
   - Run `git add . && git commit -m "your message"`

### Viewing history

- The **History** section shows the last 15 commits.
- Click the refresh icon (↺) to reload after committing.

### Auto-snapshot on save

Every `Ctrl + S` automatically writes an updated `.blendsync.json` next to your `.blend`. This file is what the diff engine reads. You still need to manually commit to save a checkpoint to git.

---

## Running the serializer/differ test script

If you just want to verify the serializer and diff logic without installing the addon:

1. Open Blender's **Scripting** workspace (tab at the top).
2. Click **Open** in the Text Editor header and open `test_blendsync.py`.
3. Click **Run Script** (▶) or press `Alt + P`.
4. Output appears in the terminal you launched Blender from (macOS: launch Blender from Terminal to see it).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| BlendSync tab missing | Make sure the addon checkbox is ticked in Edit → Preferences → Add-ons |
| "Save your .blend file first" | The addon needs a saved file path to know where to put the repo |
| "git not found on PATH" | Install git (`brew install git` on macOS), then restart Blender |
| "No repository yet" | Click **Initialize Repository** in the panel |
| Git commit fails with "nothing to commit" | The scene hasn't changed since the last commit — make an edit first |
| Re-installing after code changes | Re-zip the folder and reinstall, or use the [VS Code Blender extension](https://marketplace.visualstudio.com/items?itemName=JacquesLucke.blender-development) for live reloading |
