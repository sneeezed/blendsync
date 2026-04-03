def _vec_changed(a, b, threshold=1e-5):
    return any(abs(x - y) > threshold for x, y in zip(a, b))


def _diff_object(obj_a, obj_b, changes):
    name = obj_a['name']

    if _vec_changed(obj_a['location'], obj_b['location']):
        changes.append({
            "type": "object_moved",
            "name": name,
            "from": obj_a['location'],
            "to": obj_b['location'],
        })

    if _vec_changed(obj_a['rotation'], obj_b['rotation']):
        changes.append({
            "type": "object_rotated",
            "name": name,
            "from": obj_a['rotation'],
            "to": obj_b['rotation'],
        })

    if _vec_changed(obj_a['scale'], obj_b['scale']):
        changes.append({
            "type": "object_scaled",
            "name": name,
            "from": obj_a['scale'],
            "to": obj_b['scale'],
        })

    if obj_a.get('parent') != obj_b.get('parent'):
        changes.append({
            "type": "object_reparented",
            "name": name,
            "from": obj_a.get('parent'),
            "to": obj_b.get('parent'),
        })

    if obj_a.get('visible') != obj_b.get('visible'):
        changes.append({
            "type": "object_visibility_changed",
            "name": name,
            "from": obj_a.get('visible'),
            "to": obj_b.get('visible'),
        })

    # Geometry hash (mesh changes)
    hash_a = obj_a.get('geometry_hash')
    hash_b = obj_b.get('geometry_hash')
    if hash_a and hash_b and hash_a != hash_b:
        summary_a = obj_a.get('mesh_summary') or {}
        summary_b = obj_b.get('mesh_summary') or {}
        vc_a = summary_a.get('vertex_count', '?')
        vc_b = summary_b.get('vertex_count', '?')
        changes.append({
            "type": "geometry_changed",
            "name": name,
            "detail": f"vertex count {vc_a} → {vc_b}",
        })

    # Modifiers
    mods_a = {m['name']: m for m in (obj_a.get('modifiers') or [])}
    mods_b = {m['name']: m for m in (obj_b.get('modifiers') or [])}

    for mod_name in set(mods_a) - set(mods_b):
        changes.append({"type": "modifier_removed", "object": name, "modifier": mod_name})

    for mod_name in set(mods_b) - set(mods_a):
        changes.append({"type": "modifier_added", "object": name, "modifier": mod_name})

    for mod_name in set(mods_a) & set(mods_b):
        ma, mb = mods_a[mod_name], mods_b[mod_name]

        if ma.get('show_viewport') != mb.get('show_viewport'):
            changes.append({
                "type": "modifier_changed",
                "object": name,
                "modifier": mod_name,
                "property": "show_viewport",
                "from": ma.get('show_viewport'),
                "to": mb.get('show_viewport'),
            })

        # Geometry Nodes
        if ma.get('type') == 'NODES':
            na, nb = ma.get('geo_nodes_name'), mb.get('geo_nodes_name')
            ha, hb = ma.get('geo_nodes_hash'), mb.get('geo_nodes_hash')
            if na != nb:
                changes.append({
                    "type": "geo_nodes_reassigned",
                    "object": name,
                    "modifier": mod_name,
                    "from": na,
                    "to": nb,
                })
            elif ha and hb and ha != hb:
                changes.append({
                    "type": "geo_nodes_edited",
                    "object": name,
                    "modifier": mod_name,
                })


def _diff_materials(snapshot_a, snapshot_b, changes):
    mats_a = {m['name']: m for m in snapshot_a.get('materials', [])}
    mats_b = {m['name']: m for m in snapshot_b.get('materials', [])}

    for name in set(mats_a) - set(mats_b):
        changes.append({"type": "material_removed", "name": name})

    for name in set(mats_b) - set(mats_a):
        changes.append({"type": "material_added", "name": name})

    for name in set(mats_a) & set(mats_b):
        ma, mb = mats_a[name], mats_b[name]

        for prop in ('roughness', 'metallic'):
            va, vb = ma.get(prop), mb.get(prop)
            if va is not None and vb is not None and abs(va - vb) > 1e-5:
                changes.append({
                    "type": "material_changed",
                    "name": name,
                    "property": prop,
                    "from": va,
                    "to": vb,
                })

        # Shader node tree — only do detailed diff if the hash changed
        sha, shb = ma.get('shader_hash'), mb.get('shader_hash')
        if sha and shb and sha == shb:
            continue  # Identical tree, skip

        tree_a = ma.get('node_tree')
        tree_b = mb.get('node_tree')

        if tree_a and tree_b:
            nodes_a = {n['name']: n for n in tree_a.get('nodes', [])}
            nodes_b = {n['name']: n for n in tree_b.get('nodes', [])}

            for node_name in set(nodes_b) - set(nodes_a):
                changes.append({
                    "type": "shader_node_added",
                    "material": name,
                    "node": node_name,
                })

            for node_name in set(nodes_a) - set(nodes_b):
                changes.append({
                    "type": "shader_node_removed",
                    "material": name,
                    "node": node_name,
                })

            # Changed input values on existing nodes
            for node_name in set(nodes_a) & set(nodes_b):
                inputs_a = nodes_a[node_name].get('inputs', {})
                inputs_b = nodes_b[node_name].get('inputs', {})
                for inp_name in set(inputs_a) & set(inputs_b):
                    va, vb = inputs_a[inp_name], inputs_b[inp_name]
                    if va != vb:
                        changes.append({
                            "type": "node_changed",
                            "material": name,
                            "node": node_name,
                            "input": inp_name,
                            "from": va,
                            "to": vb,
                        })

            # Changed links
            def _link_set(tree):
                return {
                    f"{l['from_node']}:{l['from_socket']}->{l['to_node']}:{l['to_socket']}"
                    for l in tree.get('links', [])
                }

            links_a, links_b = _link_set(tree_a), _link_set(tree_b)
            if links_a != links_b:
                changes.append({
                    "type": "shader_links_changed",
                    "material": name,
                })

        elif tree_b and not tree_a:
            changes.append({"type": "shader_nodes_enabled", "material": name})
        elif tree_a and not tree_b:
            changes.append({"type": "shader_nodes_disabled", "material": name})


def _diff_render(snapshot_a, snapshot_b, changes):
    ra = snapshot_a.get('render_settings', {})
    rb = snapshot_b.get('render_settings', {})

    for prop in ('engine', 'resolution_x', 'resolution_y', 'film_transparent'):
        va, vb = ra.get(prop), rb.get(prop)
        if va != vb:
            changes.append({
                "type": "render_changed",
                "property": prop,
                "from": va,
                "to": vb,
            })


def diff(snapshot_a, snapshot_b):
    changes = []

    objs_a = {o['name']: o for o in snapshot_a.get('objects', [])}
    objs_b = {o['name']: o for o in snapshot_b.get('objects', [])}

    for name in set(objs_a) - set(objs_b):
        changes.append({"type": "object_removed", "name": name})

    for name in set(objs_b) - set(objs_a):
        changes.append({"type": "object_added", "name": name})

    for name in set(objs_a) & set(objs_b):
        _diff_object(objs_a[name], objs_b[name], changes)

    _diff_materials(snapshot_a, snapshot_b, changes)
    _diff_render(snapshot_a, snapshot_b, changes)

    return changes
