import json
import bpy

from . import serializer


@bpy.app.handlers.persistent
def on_save_post(scene, *args):
    blend_path = bpy.data.filepath
    if not blend_path:
        return

    addon = bpy.context.preferences.addons.get('blendsync')
    if addon and not addon.preferences.auto_snapshot:
        return

    try:
        data = serializer.serialize_scene()
        json_path = blend_path.replace('.blend', '.blendsync.json')
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[BlendSync] Auto-snapshot failed: {e}")


@bpy.app.handlers.persistent
def on_load_post(*args):
    # @persistent ensures this survives across file loads.
    # Register a short timer so bpy.data is fully settled before we refresh.
    def _refresh():
        try:
            bpy.ops.blendsync.refresh_branches()
            bpy.ops.blendsync.refresh_log()
            bpy.ops.blendsync.refresh_staged()
        except Exception as e:
            print(f"[BlendSync] Auto-refresh failed: {e}")
        return None

    bpy.app.timers.register(_refresh, first_interval=0.3)


def register():
    bpy.app.handlers.save_post.append(on_save_post)
    bpy.app.handlers.load_post.append(on_load_post)


def unregister():
    if on_save_post in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(on_save_post)
    if on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load_post)
