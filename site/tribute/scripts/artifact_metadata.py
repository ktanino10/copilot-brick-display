"""Remove UI-only local paths through Blender's API and strip PNG text metadata."""
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]


def sanitize_blender_metadata(bpy):
    changed = 0
    for screen in bpy.data.screens:
        for area in screen.areas:
            for space in area.spaces:
                if space.type == "FILE_BROWSER" and space.params is not None:
                    space.params.directory = b"//"
                    changed += 1
    for scene in bpy.data.scenes:
        scene.render.use_stamp_filename = False
    return changed


def strip_png_text(path):
    data = path.read_bytes()
    signature = b"\x89PNG\r\n\x1a\n"
    if not data.startswith(signature):
        raise ValueError(f"Not a PNG: {path.name}")
    output, offset, ended = bytearray(signature), 8, False
    while offset + 12 <= len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        end = offset + length + 12
        kind = data[offset+4:offset+8]
        payload = data[offset+8:offset+8+length]
        crc = struct.unpack_from(">I", data, offset+8+length)[0]
        if zlib.crc32(kind + payload) & 0xffffffff != crc:
            raise ValueError(f"Corrupt PNG chunk in {path.name}")
        if kind not in (b"tEXt", b"zTXt", b"iTXt"):
            output.extend(data[offset:end])
        offset = end
        if kind == b"IEND":
            ended = True
            break
    if not ended or offset != len(data):
        raise ValueError(f"Invalid PNG ending in {path.name}")
    path.write_bytes(output)


def main():
    import bpy
    path = ROOT / "media/character-assembly.blend"
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
    count = sanitize_blender_metadata(bpy)
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=False)
    strip_png_text(ROOT / "media/finished.png")
    print(f"ARTIFACT_METADATA_CLEANED {count} file-browser spaces; PNG pixels unchanged")


if __name__ == "__main__":
    main()
