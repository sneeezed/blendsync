import json
import os

import bpy

from . import git_interface, serializer


# ── Branch color palette ───────────────────────────────────────────────────

BRANCH_COLORS = [
    'COLORSET_04_VEC',  # green  — main/master
    'COLORSET_01_VEC',  # red
    'COLORSET_06_VEC',  # blue
    'COLORSET_03_VEC',  # yellow
    'COLORSET_07_VEC',  # purple
    'COLORSET_02_VEC',  # orange
    'COLORSET_05_VEC',  # teal
    'COLORSET_08_VEC',  # violet
    'COLORSET_11_VEC',  # light green
    'COLORSET_09_VEC',  # dark blue
]


def _color_for_branch(name, all_names):
    if name in ('main', 'master'):
        return BRANCH_COLORS[0]
    others = sorted(n for n in all_names if n not in ('main', 'master'))
    try:
        idx = (others.index(name) + 1) % len(BRANCH_COLORS)
    except ValueError:
        idx = 1
    return BRANCH_COLORS[idx]


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_repo_path():
    blend_path = bpy.data.filepath
    if not blend_path:
        return None, None
    return blend_path, os.path.dirname(blend_path)


def _format_change(c):
    t = c.get('type', '')
    name = c.get('name', c.get('object', ''))

    if t == 'object_added':
        return 'ADD', f"Object added: {name}"
    if t == 'object_removed':
        return 'REMOVE', f"Object removed: {name}"
    if t == 'object_moved':
        fr = [f"{v:.3f}" for v in c.get('from', [])]
        to = [f"{v:.3f}" for v in c.get('to', [])]
        return 'DRIVER_TRANSFORM', f"{name}: moved  {fr} → {to}"
    if t == 'object_rotated':
        fr = [f"{v:.3f}" for v in c.get('from', [])]
        to = [f"{v:.3f}" for v in c.get('to', [])]
        return 'DRIVER_ROTATIONAL_DIFFERENCE', f"{name}: rotated  {fr} → {to}"
    if t == 'object_scaled':
        fr = [f"{v:.3f}" for v in c.get('from', [])]
        to = [f"{v:.3f}" for v in c.get('to', [])]
        return 'DRIVER_DISTANCE', f"{name}: scaled  {fr} → {to}"
    if t == 'object_reparented':
        return 'LINKED', f"{name}: parent  {c.get('from')} → {c.get('to')}"
    if t == 'object_visibility_changed':
        return 'HIDE_OFF', f"{name}: visibility → {c.get('to')}"
    if t == 'geometry_changed':
        return 'MESH_DATA', f"{name}: mesh edited  ({c.get('detail', '')})"
    if t == 'modifier_added':
        return 'MODIFIER', f"{name}: modifier '{c.get('modifier', '')}' added"
    if t == 'modifier_removed':
        return 'MODIFIER', f"{name}: modifier '{c.get('modifier', '')}' removed"
    if t == 'modifier_changed':
        return 'MODIFIER', (
            f"{name} / '{c.get('modifier', '')}': "
            f"{c.get('property')} → {c.get('to')}"
        )
    if t == 'geo_nodes_edited':
        return 'GEOMETRY_NODES', f"{name}: Geometry Nodes '{c.get('modifier', '')}' edited"
    if t == 'geo_nodes_reassigned':
        return 'GEOMETRY_NODES', (
            f"{name}: Geometry Nodes '{c.get('modifier', '')}' "
            f"reassigned  {c.get('from')} → {c.get('to')}"
        )
    if t == 'material_added':
        return 'MATERIAL', f"Material added: {name}"
    if t == 'material_removed':
        return 'MATERIAL', f"Material removed: {name}"
    if t == 'material_changed':
        fr, to = c.get('from'), c.get('to')
        prop = c.get('property', '')
        if isinstance(fr, float) and isinstance(to, float):
            return 'MATERIAL', f"{name}: {prop}  {fr:.4f} → {to:.4f}"
        return 'MATERIAL', f"{name}: {prop}  {fr} → {to}"
    if t == 'node_changed':
        return 'NODETREE', (
            f"{c.get('material', '')} / {c.get('node', '')}: "
            f"'{c.get('input', '')}' value changed"
        )
    if t == 'shader_node_added':
        return 'NODETREE', f"{c.get('material', '')}: shader node '{c.get('node', '')}' added"
    if t == 'shader_node_removed':
        return 'NODETREE', f"{c.get('material', '')}: shader node '{c.get('node', '')}' removed"
    if t == 'shader_links_changed':
        return 'NODETREE', f"{c.get('material', '')}: shader connections changed"
    if t == 'shader_nodes_enabled':
        return 'NODETREE', f"{c.get('material', '')}: shader nodes enabled"
    if t == 'shader_nodes_disabled':
        return 'NODETREE', f"{c.get('material', '')}: shader nodes disabled"
    if t == 'render_changed':
        return 'RENDER_RESULT', (
            f"Render {c.get('property', '')}: {c.get('from')} → {c.get('to')}"
        )
    return 'DOT', str(c)


# ── Property Groups ────────────────────────────────────────────────────────

class BlendSyncCommitItem(bpy.types.PropertyGroup):
    hash: bpy.props.StringProperty()
    message: bpy.props.StringProperty()
    date: bpy.props.StringProperty()
    branch_label: bpy.props.StringProperty()
    color_tag: bpy.props.StringProperty()
    is_head: bpy.props.BoolProperty()


class BlendSyncBranchItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    is_current: bpy.props.BoolProperty()
    color_tag: bpy.props.StringProperty()


class BlendSyncDiffLineItem(bpy.types.PropertyGroup):
    text: bpy.props.StringProperty()
    icon_name: bpy.props.StringProperty()


# ── Repository ─────────────────────────────────────────────────────────────

class BLENDSYNC_OT_init_repo(bpy.types.Operator):
    bl_idname = "blendsync.init_repo"
    bl_label = "Initialize Repository"
    bl_description = "Create a git repository with a main branch in the same folder as your .blend file"

    def execute(self, context):
        blend_path, repo_path = _get_repo_path()
        if not blend_path:
            self.report({'ERROR'}, "Save your .blend file first.")
            return {'CANCELLED'}
        try:
            git_interface.init_repo(repo_path)
            bpy.ops.blendsync.refresh_branches()
            bpy.ops.blendsync.refresh_log()
            self.report({'INFO'}, f"Repository initialized at: {repo_path}")
        except git_interface.GitError as e:
            self.report({'ERROR'}, f"Git error: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}


# ── Commit ─────────────────────────────────────────────────────────────────

class BLENDSYNC_OT_commit(bpy.types.Operator):
    bl_idname = "blendsync.commit"
    bl_label = "Commit Snapshot"
    bl_description = "Serialize the scene to JSON and create a git commit"

    def execute(self, context):
        blend_path, repo_path = _get_repo_path()
        if not blend_path:
            self.report({'ERROR'}, "Save your .blend file first.")
            return {'CANCELLED'}

        message = context.scene.blendsync_commit_message.strip()
        if not message:
            self.report({'ERROR'}, "Enter a commit message.")
            return {'CANCELLED'}

        if not git_interface.is_repo(repo_path):
            self.report({'ERROR'}, "No repository found. Click 'Initialize Repository' first.")
            return {'CANCELLED'}

        bpy.ops.wm.save_mainfile()

        try:
            data = serializer.serialize_scene()
            json_path = blend_path.replace('.blend', '.blendsync.json')
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.report({'ERROR'}, f"Serialization failed: {e}")
            return {'CANCELLED'}

        try:
            git_interface.commit(repo_path, message)
        except git_interface.GitError as e:
            self.report({'ERROR'}, f"Git error: {e}")
            return {'CANCELLED'}

        # Committing always brings us back to real HEAD — clear any revert marker
        git_interface.clear_head_marker(repo_path)

        context.scene.blendsync_commit_message = ""
        bpy.ops.blendsync.refresh_branches()
        bpy.ops.blendsync.refresh_log()
        bpy.ops.blendsync.refresh_staged()
        self.report({'INFO'}, f"Committed: {message}")
        return {'FINISHED'}


# ── History ────────────────────────────────────────────────────────────────

class BLENDSYNC_OT_refresh_log(bpy.types.Operator):
    bl_idname = "blendsync.refresh_log"
    bl_label = "Refresh History"
    bl_description = "Reload the commit history from git"

    def execute(self, context):
        blend_path, repo_path = _get_repo_path()
        if not blend_path or not git_interface.is_repo(repo_path):
            return {'CANCELLED'}

        branch_colors = {b.name: b.color_tag for b in context.scene.blendsync_branches}
        current_hash = git_interface.get_effective_commit(repo_path)

        entries = git_interface.get_log(repo_path)
        scene = context.scene
        scene.blendsync_history.clear()

        for e in entries:
            item = scene.blendsync_history.add()
            item.hash = e['hash']
            item.message = e['message']
            item.date = e['date']
            item.is_head = (e['hash'] == current_hash)
            for ref in e.get('refs', []):
                if ref in branch_colors:
                    item.branch_label = ref
                    item.color_tag = branch_colors[ref]
                    break

        return {'FINISHED'}


class BLENDSYNC_OT_revert_commit(bpy.types.Operator):
    bl_idname = "blendsync.revert_commit"
    bl_label = "Revert to this Commit"
    bl_description = (
        "Restore the .blend and JSON to this commit's state. "
        "Your current uncommitted work will be overwritten."
    )

    commit_hash: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        blend_path, repo_path = _get_repo_path()
        if not blend_path:
            self.report({'ERROR'}, "No .blend file path found.")
            return {'CANCELLED'}

        try:
            git_interface.revert_to_commit(repo_path, self.commit_hash)
        except git_interface.GitError as e:
            self.report({'ERROR'}, f"Git error: {e}")
            return {'CANCELLED'}

        # Write marker so the ▶ indicator survives the file reload
        git_interface.write_head_marker(repo_path, self.commit_hash)

        _blend_path = blend_path

        def _reload():
            bpy.ops.wm.open_mainfile(filepath=_blend_path, load_ui=False)
            return None

        bpy.app.timers.register(_reload, first_interval=0.1)
        self.report({'INFO'}, f"Reverted to {self.commit_hash}")
        return {'FINISHED'}


# ── Staged changes (live diff) ─────────────────────────────────────────────

class BLENDSYNC_OT_refresh_staged(bpy.types.Operator):
    bl_idname = "blendsync.refresh_staged"
    bl_label = "Refresh Changes"
    bl_description = "Compare the current scene against the last commit"

    def execute(self, context):
        from . import differ

        blend_path, repo_path = _get_repo_path()
        scene = context.scene
        scene.blendsync_staged_changes.clear()
        scene.blendsync_staged_summary = ""

        if not blend_path or not git_interface.is_repo(repo_path):
            return {'CANCELLED'}

        json_path = blend_path.replace('.blend', '.blendsync.json')
        current_ref = git_interface.get_effective_commit(repo_path)
        if not current_ref:
            scene.blendsync_staged_summary = "No commits yet."
            return {'FINISHED'}

        try:
            snap_committed = git_interface.get_snapshot_at_commit(
                repo_path, current_ref, json_path
            )
        except (git_interface.GitError, json.JSONDecodeError, ValueError):
            scene.blendsync_staged_summary = "No committed snapshot to compare against."
            return {'FINISHED'}

        try:
            snap_current = serializer.serialize_scene()
        except Exception as e:
            scene.blendsync_staged_summary = f"Serialization error: {e}"
            return {'FINISHED'}

        changes = differ.diff(snap_committed, snap_current)
        n = len(changes)

        if not changes:
            scene.blendsync_staged_summary = "No changes since last commit."
        else:
            scene.blendsync_staged_summary = f"{n} change{'s' if n != 1 else ''} since last commit"
            for change in changes:
                icon, text = _format_change(change)
                item = scene.blendsync_staged_changes.add()
                item.text = text
                item.icon_name = icon

        return {'FINISHED'}


# ── Branches ───────────────────────────────────────────────────────────────

class BLENDSYNC_OT_refresh_branches(bpy.types.Operator):
    bl_idname = "blendsync.refresh_branches"
    bl_label = "Refresh Branches"
    bl_description = "Reload the branch list from git"

    def execute(self, context):
        blend_path, repo_path = _get_repo_path()
        if not blend_path or not git_interface.is_repo(repo_path):
            return {'CANCELLED'}

        _, branches = git_interface.get_branches(repo_path)
        all_names = [b['name'] for b in branches]

        scene = context.scene
        scene.blendsync_branches.clear()
        for b in branches:
            item = scene.blendsync_branches.add()
            item.name = b['name']
            item.is_current = b['is_current']
            item.color_tag = _color_for_branch(b['name'], all_names)

        return {'FINISHED'}


class BLENDSYNC_OT_create_branch(bpy.types.Operator):
    bl_idname = "blendsync.create_branch"
    bl_label = "Create Branch"
    bl_description = "Create a new branch from the current commit and switch to it"

    def execute(self, context):
        blend_path, repo_path = _get_repo_path()
        if not blend_path:
            self.report({'ERROR'}, "No .blend file found.")
            return {'CANCELLED'}

        name = context.scene.blendsync_new_branch_name.strip()
        if not name:
            self.report({'ERROR'}, "Enter a branch name.")
            return {'CANCELLED'}

        if not git_interface.is_repo(repo_path):
            self.report({'ERROR'}, "No repository found.")
            return {'CANCELLED'}

        try:
            git_interface.create_branch(repo_path, name)
        except git_interface.GitError as e:
            self.report({'ERROR'}, f"Git error: {e}")
            return {'CANCELLED'}

        context.scene.blendsync_new_branch_name = ""
        bpy.ops.blendsync.refresh_branches()
        bpy.ops.blendsync.refresh_log()
        self.report({'INFO'}, f"Switched to new branch: {name}")
        return {'FINISHED'}


class BLENDSYNC_OT_checkout_branch(bpy.types.Operator):
    bl_idname = "blendsync.checkout_branch"
    bl_label = "Switch Branch"
    bl_description = "Switch to this branch and reload the .blend file"

    branch_name: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        blend_path, repo_path = _get_repo_path()
        if not blend_path:
            self.report({'ERROR'}, "No .blend file found.")
            return {'CANCELLED'}

        try:
            git_interface.checkout_branch(repo_path, self.branch_name)
        except git_interface.GitError as e:
            self.report({'ERROR'}, f"Git error: {e}")
            return {'CANCELLED'}

        # Switching branch means we're on a real branch HEAD — clear revert marker
        git_interface.clear_head_marker(repo_path)

        _blend_path = blend_path

        def _reload():
            bpy.ops.wm.open_mainfile(filepath=_blend_path, load_ui=False)
            return None

        bpy.app.timers.register(_reload, first_interval=0.1)
        self.report({'INFO'}, f"Switched to branch: {self.branch_name}")
        return {'FINISHED'}


# ── Registration list ──────────────────────────────────────────────────────

classes = [
    BlendSyncCommitItem,
    BlendSyncBranchItem,
    BlendSyncDiffLineItem,
    BLENDSYNC_OT_init_repo,
    BLENDSYNC_OT_commit,
    BLENDSYNC_OT_refresh_log,
    BLENDSYNC_OT_revert_commit,
    BLENDSYNC_OT_refresh_staged,
    BLENDSYNC_OT_refresh_branches,
    BLENDSYNC_OT_create_branch,
    BLENDSYNC_OT_checkout_branch,
]
