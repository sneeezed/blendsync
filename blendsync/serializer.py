import hashlib
import struct

import bpy


def hash_mesh(obj):
    if obj.type != 'MESH':
        return None
    mesh = obj.data
    h = hashlib.sha256()
    for v in mesh.vertices:
        h.update(struct.pack('fff', *v.co))
    return h.hexdigest()[:16]


def serialize_node_tree(tree):
    nodes = []
    for node in tree.nodes:
        inputs = {}
        for inp in node.inputs:
            if not hasattr(inp, 'default_value'):
                continue
            val = inp.default_value
            # Convert non-JSON-serializable types (e.g. Color, Vector) to lists
            try:
                inputs[inp.name] = list(val)
            except TypeError:
                inputs[inp.name] = val

        nodes.append({
            "name": node.name,
            "type": node.type,
            "location": list(node.location),
            "inputs": inputs,
        })

    links = [
        {
            "from_node": link.from_node.name,
            "from_socket": link.from_socket.name,
            "to_node": link.to_node.name,
            "to_socket": link.to_socket.name,
        }
        for link in tree.links
    ]

    return {"nodes": nodes, "links": links}


def serialize_object(obj):
    modifiers = [
        {
            "name": m.name,
            "type": m.type,
            "show_viewport": m.show_viewport,
        }
        for m in obj.modifiers
    ]

    mesh_summary = None
    if obj.type == 'MESH' and obj.data:
        mesh_summary = {
            "vertex_count": len(obj.data.vertices),
            "poly_count": len(obj.data.polygons),
            "has_uv": bool(obj.data.uv_layers),
        }

    collection = obj.users_collection[0].name if obj.users_collection else None

    return {
        "name": obj.name,
        "type": obj.type,
        "location": list(obj.location),
        "rotation": list(obj.rotation_euler),
        "scale": list(obj.scale),
        "parent": obj.parent.name if obj.parent else None,
        "collection": collection,
        "visible": obj.visible_get(),
        "modifiers": modifiers,
        "mesh_summary": mesh_summary,
        "geometry_hash": hash_mesh(obj),
    }


def serialize_material(mat):
    return {
        "name": mat.name,
        "use_nodes": mat.use_nodes,
        "roughness": mat.roughness,
        "metallic": mat.metallic,
        "node_tree": serialize_node_tree(mat.node_tree) if mat.use_nodes and mat.node_tree else None,
    }


def serialize_scene():
    scene = bpy.context.scene
    render = scene.render

    metadata = {
        "blender_version": bpy.app.version_string,
        "scene_name": scene.name,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "fps": render.fps,
    }

    render_settings = {
        "engine": render.engine,
        "resolution_x": render.resolution_x,
        "resolution_y": render.resolution_y,
        "film_transparent": render.film_transparent,
    }

    objects = [serialize_object(obj) for obj in bpy.data.objects]
    materials = [serialize_material(mat) for mat in bpy.data.materials]

    return {
        "metadata": metadata,
        "render_settings": render_settings,
        "objects": objects,
        "materials": materials,
    }
