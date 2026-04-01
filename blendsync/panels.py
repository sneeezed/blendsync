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

        # Color dot: branch tip gets its branch color, other commits get a dim dot
        dot_icon = item.color_tag if item.color_tag else 'DOT'
        row.label(text="", icon=dot_icon)

        row.label(text=f"{item.date}  {item.hash}")

        # Show branch label badge when this commit is the tip of a branch
        if item.branch_label:
            sub = row.row()
            sub.scale_x = 0.7
            sub.label(text=item.branch_label)

        row.label(text=item.message)

        op = row.operator("blendsync.revert_commit", text="", icon='LOOP_BACK')
        op.commit_hash = item.hash


class BLENDSYNC_UL_branches(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        dot_icon = item.color_tag if item.color_tag else 'DOT'
        row.label(text="", icon=dot_icon)

        name_icon = 'LAYER_ACTIVE' if item.is_current else 'NONE'
        row.label(text=item.name, icon=name_icon)

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
        repo_exists = git_interface.is_repo(repo_path)

        col = layout.column(align=True)
        col.label(text=os.path.basename(blend_path), icon='FILE_BLEND')

        if repo_exists:
            scene = context.scene
            branch = git_interface.get_current_branch(repo_path)
            # Find the color for the current branch
            color_icon = 'LAYER_ACTIVE'
            for b in scene.blendsync_branches:
                if b.name == branch:
                    color_icon = b.color_tag or 'LAYER_ACTIVE'
                    break
            row = col.row(align=True)
            row.label(text="", icon=color_icon)
            row.label(text=branch or "(unknown branch)")
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


# ── Last commit diff sub-panel ─────────────────────────────────────────────

class BLENDSYNC_PT_last_commit(bpy.types.Panel):
    bl_label = "Last Commit Changes"
    bl_idname = "BLENDSYNC_PT_last_commit"
    bl_parent_id = "BLENDSYNC_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _repo_ready(context) and bool(context.scene.blendsync_diff_summary)

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
    BLENDSYNC_PT_last_commit,
]
