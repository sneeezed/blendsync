import os

import bpy

from . import git_interface


# ── Shared guard ───────────────────────────────────────────────────────────

def _repo_ready(context):
    blend_path = bpy.data.filepath
    if not blend_path:
        return False
    repo_path = os.path.dirname(blend_path)
    return git_interface.is_available() and git_interface.is_repo(repo_path)


# ── UI Lists ───────────────────────────────────────────────────────────────

class BLENDSYNC_UL_history(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        scene = context.scene
        row = layout.row(align=True)

        # Date + hash + message
        row.label(text=f"{item.date}  {item.hash}", icon='RECOVER_LAST')
        row.label(text=item.message)

        # Highlight if selected as A or B
        is_a = item.hash == scene.blendsync_diff_hash_a
        is_b = item.hash == scene.blendsync_diff_hash_b

        sub = row.row(align=True)
        sub.scale_x = 0.6

        op_a = sub.operator("blendsync.set_diff_a", text="A",
                            depress=is_a, emboss=True)
        op_a.commit_hash = item.hash

        op_b = sub.operator("blendsync.set_diff_b", text="B",
                            depress=is_b, emboss=True)
        op_b.commit_hash = item.hash

        op_r = sub.operator("blendsync.revert_commit", text="", icon='LOOP_BACK')
        op_r.commit_hash = item.hash


class BLENDSYNC_UL_branches(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        icon = 'LAYER_ACTIVE' if item.is_current else 'LAYER_USED'
        row.label(text=item.name, icon=icon)
        if item.is_current:
            row.label(text="current")
        else:
            op = row.operator("blendsync.checkout_branch", text="Switch")
            op.branch_name = item.name


# ── Main panel (status bar) ────────────────────────────────────────────────

class BLENDSYNC_PT_main(bpy.types.Panel):
    bl_label = "BlendSync"
    bl_idname = "BLENDSYNC_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "BlendSync"

    def draw(self, context):
        layout = self.layout
        blend_path = bpy.data.filepath

        if not blend_path:
            layout.label(text="Save your .blend file first.", icon='ERROR')
            return

        if not git_interface.is_available():
            layout.label(text="git not found on PATH.", icon='ERROR')
            layout.label(text="Install git and restart Blender.")
            return

        repo_path = os.path.dirname(blend_path)
        repo_exists = git_interface.is_repo(repo_path)

        col = layout.column(align=True)
        col.label(text=os.path.basename(blend_path), icon='FILE_BLEND')

        if repo_exists:
            branch = git_interface.get_current_branch(repo_path)
            col.label(text=f"Branch: {branch or '(unknown)'}", icon='BOOKMARKS')
        else:
            col.label(text="No repository yet.", icon='INFO')
            col.operator("blendsync.init_repo", icon='ADD')


# ── Commit sub-panel ───────────────────────────────────────────────────────

class BLENDSYNC_PT_commit(bpy.types.Panel):
    bl_label = "Commit"
    bl_idname = "BLENDSYNC_PT_commit"
    bl_parent_id = "BLENDSYNC_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return _repo_ready(context)

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        col = layout.column(align=True)
        col.prop(scene, "blendsync_commit_message", text="", placeholder="Describe this snapshot…")
        col.operator("blendsync.commit", icon='FILE_TICK')


# ── Branches sub-panel ─────────────────────────────────────────────────────

class BLENDSYNC_PT_branches(bpy.types.Panel):
    bl_label = "Branches"
    bl_idname = "BLENDSYNC_PT_branches"
    bl_parent_id = "BLENDSYNC_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _repo_ready(context)

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        row = layout.row()
        row.label(text="All Branches")
        row.operator("blendsync.refresh_branches", text="", icon='FILE_REFRESH')

        if scene.blendsync_branches:
            layout.template_list(
                "BLENDSYNC_UL_branches", "",
                scene, "blendsync_branches",
                scene, "blendsync_branches_index",
                rows=3,
            )
        else:
            layout.label(text="No branches yet (commit first).", icon='INFO')

        layout.separator()
        col = layout.column(align=True)
        col.prop(scene, "blendsync_new_branch_name", text="", placeholder="New branch name…")
        col.operator("blendsync.create_branch", icon='ADD')


# ── History sub-panel ──────────────────────────────────────────────────────

class BLENDSYNC_PT_history(bpy.types.Panel):
    bl_label = "History"
    bl_idname = "BLENDSYNC_PT_history"
    bl_parent_id = "BLENDSYNC_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _repo_ready(context)

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        row = layout.row()
        row.label(text="Commits")
        row.operator("blendsync.refresh_log", text="", icon='FILE_REFRESH')

        if scene.blendsync_history:
            layout.template_list(
                "BLENDSYNC_UL_history", "",
                scene, "blendsync_history",
                scene, "blendsync_history_index",
                rows=6,
            )

            # Diff controls
            layout.separator()
            box = layout.box()
            box.label(text="Compare two commits", icon='ARROW_LEFTRIGHT')

            col = box.column(align=True)
            a = scene.blendsync_diff_hash_a
            b = scene.blendsync_diff_hash_b
            col.label(text=f"A:  {a if a else '— not set —'}", icon='TRIA_RIGHT')
            col.label(text=f"B:  {b if b else '— not set —'}", icon='TRIA_RIGHT')

            row = box.row()
            row.enabled = bool(a and b and a != b)
            row.operator("blendsync.run_diff", icon='VIEWZOOM')
        else:
            layout.label(text="No commits yet.")


# ── Diff results sub-panel ─────────────────────────────────────────────────

class BLENDSYNC_PT_diff_results(bpy.types.Panel):
    bl_label = "Diff Results"
    bl_idname = "BLENDSYNC_PT_diff_results"
    bl_parent_id = "BLENDSYNC_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return _repo_ready(context) and bool(context.scene.blendsync_diff_results)

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text=scene.blendsync_diff_summary, icon='ARROW_LEFTRIGHT')
        layout.separator()

        for item in scene.blendsync_diff_results:
            row = layout.row()
            try:
                row.label(text=item.text, icon=item.icon_name)
            except TypeError:
                row.label(text=item.text, icon='DOT')


# ── Registration list ──────────────────────────────────────────────────────

classes = [
    BLENDSYNC_UL_history,
    BLENDSYNC_UL_branches,
    BLENDSYNC_PT_main,
    BLENDSYNC_PT_commit,
    BLENDSYNC_PT_branches,
    BLENDSYNC_PT_history,
    BLENDSYNC_PT_diff_results,
]
