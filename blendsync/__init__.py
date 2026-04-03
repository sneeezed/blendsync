bl_info = {
    "name": "BlendSync",
    "author": "BlendSync",
    "version": (0, 5, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > BlendSync",
    "description": "Git-style version control and async collaboration for Blender",
    "category": "System",
}

import bpy

from . import handlers, operators, panels, preferences


def register():
    try:
        unregister()
    except Exception:
        pass

    for cls in preferences.classes:
        bpy.utils.register_class(cls)

    for cls in operators.classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.blendsync_commit_message = bpy.props.StringProperty(
        name="Commit Message", default="",
    )
    bpy.types.Scene.blendsync_history = bpy.props.CollectionProperty(
        type=operators.BlendSyncCommitItem,
    )
    bpy.types.Scene.blendsync_history_index = bpy.props.IntProperty(default=0)

    bpy.types.Scene.blendsync_branches = bpy.props.CollectionProperty(
        type=operators.BlendSyncBranchItem,
    )
    bpy.types.Scene.blendsync_branches_index = bpy.props.IntProperty(default=0)
    bpy.types.Scene.blendsync_new_branch_name = bpy.props.StringProperty(
        name="New Branch Name", default="",
    )

    # Live staged changes (current scene vs last commit)
    bpy.types.Scene.blendsync_staged_summary = bpy.props.StringProperty(default="")
    bpy.types.Scene.blendsync_staged_changes = bpy.props.CollectionProperty(
        type=operators.BlendSyncDiffLineItem,
    )

    for cls in panels.classes:
        bpy.utils.register_class(cls)

    handlers.register()

    # Run a full refresh once the session is ready (covers addon enable + reload)
    def _startup_refresh():
        try:
            bpy.ops.blendsync.refresh_branches()
            bpy.ops.blendsync.refresh_log()
            bpy.ops.blendsync.refresh_staged()
        except Exception:
            pass
        return None

    bpy.app.timers.register(_startup_refresh, first_interval=0.5)


def unregister():
    handlers.unregister()

    for cls in reversed(panels.classes):
        bpy.utils.unregister_class(cls)

    for prop in (
        'blendsync_commit_message',
        'blendsync_history', 'blendsync_history_index',
        'blendsync_branches', 'blendsync_branches_index',
        'blendsync_new_branch_name',
        'blendsync_staged_summary', 'blendsync_staged_changes',
    ):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)

    for cls in reversed(operators.classes):
        bpy.utils.unregister_class(cls)

    for cls in reversed(preferences.classes):
        bpy.utils.unregister_class(cls)
