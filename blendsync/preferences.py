import bpy


class BlendSyncPreferences(bpy.types.AddonPreferences):
    bl_idname = 'blendsync'

    auto_snapshot: bpy.props.BoolProperty(
        name="Auto-snapshot on save",
        description=(
            "Automatically serialize the scene to JSON whenever you save the "
            ".blend file. Disable if you find saves are slow on complex scenes "
            "and prefer to snapshot manually at commit time."
        ),
        default=True,
    )

    def draw(self, context):
        self.layout.prop(self, "auto_snapshot")


classes = [BlendSyncPreferences]
