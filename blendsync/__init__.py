bl_info = {
    "name": "BlendSync",
    "author": "BlendSync",
    "version": (0, 2, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > BlendSync",
    "description": "Git-style version control and async collaboration for Blender",
    "category": "System",
}

import bpy

from . import handlers, operators, panels


def register():
    # Unregister first in case a previous load left classes registered
    try:
        unregister()
    except Exception:
        pass

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

    bpy.types.Scene.blendsync_diff_hash_a = bpy.props.StringProperty(default="")
    bpy.types.Scene.blendsync_diff_hash_b = bpy.props.StringProperty(default="")
    bpy.types.Scene.blendsync_diff_summary = bpy.props.StringProperty(default="")
    bpy.types.Scene.blendsync_diff_results = bpy.props.CollectionProperty(
        type=operators.BlendSyncDiffLineItem,
    )

    for cls in panels.classes:
        bpy.utils.register_class(cls)

    handlers.register()


def unregister():
    handlers.unregister()

    for cls in reversed(panels.classes):
        bpy.utils.unregister_class(cls)

    for prop in (
        'blendsync_commit_message',
        'blendsync_history', 'blendsync_history_index',
        'blendsync_branches', 'blendsync_branches_index',
        'blendsync_new_branch_name',
        'blendsync_diff_hash_a', 'blendsync_diff_hash_b',
        'blendsync_diff_summary', 'blendsync_diff_results',
    ):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)

    for cls in reversed(operators.classes):
        bpy.utils.unregister_class(cls)
