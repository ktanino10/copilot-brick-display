"""Normalize optional file-browser metadata using Blender's native API, not binary edits."""

import sys

import bpy

for screen in bpy.data.screens:
    for area in screen.areas:
        for space in area.spaces:
            if space.type == "FILE_BROWSER" and space.params:
                space.params.directory = b"//"
bpy.context.scene.render.use_stamp = False
bpy.context.scene.render.use_stamp_filename = False
bpy.context.scene.frame_set(bpy.context.scene.frame_end)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, check_existing=False, compress=False)
print("NATIVE_METADATA_NORMALIZED_WITH_BLENDER_API")
