import json
import bpy

from . import serializer


def on_save_post(scene, *args):
    blend_path = bpy.data.filepath
    if not blend_path:
        return

    try:
        data = serializer.serialize_scene()
        json_path = blend_path.replace('.blend', '.blendsync.json')
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[BlendSync] Auto-snapshot failed: {e}")


def register():
    bpy.app.handlers.save_post.append(on_save_post)


def unregister():
    if on_save_post in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(on_save_post)
