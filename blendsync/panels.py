import os

import bpy

from . import git_interface


def _repo_ready(context):
    blend_path = bpy.data.filepath
    if not blend_path:
        return False
    repo_path = os.path.dirname(blend_path)
    return git_interface.is_available() and git_interface.is_repo(repo_path)


# ── UI Lists ───────────────────────────────────────────────────────────────

class BLENDSYNC_UL_history(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)

        # "You are here" arrow on the current HEAD commit
        row.label(text="", icon='TRIA_RIGHT' if item.is_head else 'BLANK1')

        # Branch color dot
        row.label(text="", icon=item.color_tag if item.color_tag else 'DOT')

        row.label(text=f"{item.date}  {item.hash}")

        if item.branch_label:
            sub = row.row()
            sub.scale_x = 0.7
            sub.label(text=item.branch_label)

        row.label(text=item.message)

        if not item.is_head:
            op = row.operator("blendsync.revert_commit", text="", icon='LOOP_BACK')
            op.commit_hash = item.hash


class BLENDSYNC_UL_branches(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        row.label(text="", icon=item.color_tag if item.color_tag else 'DOT')
        row.label(text=item.name, icon='LAYER_ACTIVE' if item.is_current else 'NONE')

        if item.is_current:
            row.label(text="current")
        else:
            op = row.operator("blendsync.checkout_branch", text="Switch")
            op.branch_name = item.name


# ── Main panel ─────────────────────────────────────────────────────────────

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
        if not git_interface.is_repo(repo_path):
            layout.label(text="No repository yet.", icon='INFO')
            layout.operator("blendsync.init_repo", icon='ADD')


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


# ── Tracked changes sub-panel ─────────────────────────────────────────────

class BLENDSYNC_PT_changes(bpy.types.Panel):
    bl_label = "Tracked Changes"
    bl_idname = "BLENDSYNC_PT_changes"
    bl_parent_id = "BLENDSYNC_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return _repo_ready(context)

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        row = layout.row()
        summary = getattr(scene, 'blendsync_staged_summary', '')
        row.label(text=summary if summary else "Changes", icon='RADIOBUT_ON')
        row.operator("blendsync.refresh_staged", text="", icon='FILE_REFRESH')

        staged = getattr(scene, 'blendsync_staged_changes', [])
        if staged:
            for item in staged:
                r = layout.row()
                try:
                    r.label(text=item.text, icon=item.icon_name)
                except TypeError:
                    r.label(text=item.text, icon='DOT')
        elif summary:
            layout.label(text="Nothing to commit.", icon='CHECKMARK')
        else:
            layout.label(text="Click ↺ to scan for changes.", icon='INFO')


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
                rows=min(len(scene.blendsync_branches), 5),
            )
        else:
            layout.label(text="No branches yet.", icon='INFO')

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
        else:
            layout.label(text="No commits yet.")


# ── Registration list ──────────────────────────────────────────────────────

classes = [
    BLENDSYNC_UL_history,
    BLENDSYNC_UL_branches,
    BLENDSYNC_PT_main,
    BLENDSYNC_PT_commit,
    BLENDSYNC_PT_changes,
    BLENDSYNC_PT_branches,
    BLENDSYNC_PT_history,
]
