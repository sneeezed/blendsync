import json
import os

import bpy

from . import git_interface, serializer


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
        return 'MESH_DATA', f"{name}: geometry changed  ({c.get('detail', '')})"
    if t == 'modifier_added':
        return 'MODIFIER', f"{name}: modifier '{c.get('modifier', '')}' added"
    if t == 'modifier_removed':
        return 'MODIFIER', f"{name}: modifier '{c.get('modifier', '')}' removed"
    if t == 'modifier_changed':
        return 'MODIFIER', (
            f"{name} / '{c.get('modifier', '')}': "
            f"{c.get('property')} → {c.get('to')}"
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
            f"'{c.get('input', '')}' changed"
        )
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


class BlendSyncBranchItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    is_current: bpy.props.BoolProperty()


class BlendSyncDiffLineItem(bpy.types.PropertyGroup):
    text: bpy.props.StringProperty()
    icon_name: bpy.props.StringProperty()


# ── Repository ─────────────────────────────────────────────────────────────

class BLENDSYNC_OT_init_repo(bpy.types.Operator):
    bl_idname = "blendsync.init_repo"
    bl_label = "Initialize Repository"
    bl_description = "Create a git repository in the same folder as your .blend file"

    def execute(self, context):
        blend_path, repo_path = _get_repo_path()
        if not blend_path:
            self.report({'ERROR'}, "Save your .blend file first.")
            return {'CANCELLED'}
        try:
            git_interface.init_repo(repo_path)
            bpy.ops.blendsync.refresh_branches()
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

        context.scene.blendsync_commit_message = ""
        bpy.ops.blendsync.refresh_log()
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

        entries = git_interface.get_log(repo_path)
        scene = context.scene
        scene.blendsync_history.clear()
        for e in entries:
            item = scene.blendsync_history.add()
            item.hash = e['hash']
            item.message = e['message']
            item.date = e['date']
        return {'FINISHED'}


class BLENDSYNC_OT_set_diff_a(bpy.types.Operator):
    bl_idname = "blendsync.set_diff_a"
    bl_label = "Set as Diff A"
    bl_description = "Use this commit as the 'before' snapshot for comparison"

    commit_hash: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.blendsync_diff_hash_a = self.commit_hash
        return {'FINISHED'}


class BLENDSYNC_OT_set_diff_b(bpy.types.Operator):
    bl_idname = "blendsync.set_diff_b"
    bl_label = "Set as Diff B"
    bl_description = "Use this commit as the 'after' snapshot for comparison"

    commit_hash: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.blendsync_diff_hash_b = self.commit_hash
        return {'FINISHED'}


class BLENDSYNC_OT_run_diff(bpy.types.Operator):
    bl_idname = "blendsync.run_diff"
    bl_label = "Compare A → B"
    bl_description = "Show all changes between the two selected commits"

    def execute(self, context):
        from . import differ

        scene = context.scene
        hash_a = scene.blendsync_diff_hash_a
        hash_b = scene.blendsync_diff_hash_b

        if not hash_a or not hash_b:
            self.report({'ERROR'}, "Mark both an A and a B commit first.")
            return {'CANCELLED'}
        if hash_a == hash_b:
            self.report({'ERROR'}, "A and B are the same commit.")
            return {'CANCELLED'}

        blend_path, repo_path = _get_repo_path()
        json_filename = os.path.basename(blend_path).replace('.blend', '.blendsync.json')

        try:
            snap_a = git_interface.get_snapshot_at_commit(repo_path, hash_a, json_filename)
            snap_b = git_interface.get_snapshot_at_commit(repo_path, hash_b, json_filename)
        except (git_interface.GitError, json.JSONDecodeError, ValueError) as e:
            self.report({'ERROR'}, f"Could not load snapshots: {e}")
            return {'CANCELLED'}

        changes = differ.diff(snap_a, snap_b)

        scene.blendsync_diff_results.clear()
        n = len(changes)
        scene.blendsync_diff_summary = (
            f"{hash_a} → {hash_b}   "
            f"({n} change{'s' if n != 1 else ''})"
        )

        if not changes:
            item = scene.blendsync_diff_results.add()
            item.text = "No differences found."
            item.icon_name = 'CHECKMARK'
        else:
            for change in changes:
                icon, text = _format_change(change)
                item = scene.blendsync_diff_results.add()
                item.text = text
                item.icon_name = icon

        self.report({'INFO'}, f"Diff complete: {n} change{'s' if n != 1 else ''}")
        return {'FINISHED'}


class BLENDSYNC_OT_revert_commit(bpy.types.Operator):
    bl_idname = "blendsync.revert_commit"
    bl_label = "Revert to this Commit"
    bl_description = (
        "Restore the .blend and JSON to this commit's state. "
        "Your current work will be overwritten."
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

        # Reload the .blend from disk using a timer so the operator can finish first
        def _reload():
            bpy.ops.wm.revert_mainfile()
            return None

        bpy.app.timers.register(_reload, first_interval=0.05)
        self.report({'INFO'}, f"Reverted to {self.commit_hash}")
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

        current, branches = git_interface.get_branches(repo_path)
        scene = context.scene
        scene.blendsync_branches.clear()
        for b in branches:
            item = scene.blendsync_branches.add()
            item.name = b['name']
            item.is_current = b['is_current']
        return {'FINISHED'}


class BLENDSYNC_OT_create_branch(bpy.types.Operator):
    bl_idname = "blendsync.create_branch"
    bl_label = "Create Branch"
    bl_description = "Create a new branch and switch to it"

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

        bpy.ops.blendsync.refresh_branches()
        bpy.ops.blendsync.refresh_log()

        def _reload():
            bpy.ops.wm.revert_mainfile()
            return None

        bpy.app.timers.register(_reload, first_interval=0.05)
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
    BLENDSYNC_OT_set_diff_a,
    BLENDSYNC_OT_set_diff_b,
    BLENDSYNC_OT_run_diff,
    BLENDSYNC_OT_revert_commit,
    BLENDSYNC_OT_refresh_branches,
    BLENDSYNC_OT_create_branch,
    BLENDSYNC_OT_checkout_branch,
]
