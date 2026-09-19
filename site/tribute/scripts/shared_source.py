"""Reuse verified shared source; never substitute a lookalike connector implementation."""
import hashlib
import json
import subprocess
import types


def load_shared(project):
    repo = project.parents[1]
    lock = json.loads((project / "shared-lock.json").read_text())
    blobs = {}
    for path, expected in lock["files"].items():
        source = repo / path
        content = source.read_bytes() if source.is_file() else None
        if content is None or hashlib.sha256(content).hexdigest() != expected:
            result = subprocess.run(["git", "show", f"{lock['commit']}:{path}"],
                                    cwd=repo, capture_output=True, check=False)
            if result.returncode:
                raise RuntimeError(f"Shared source {path} at {lock['commit']} is unavailable; "
                                   "restore the locked root source or fetch the pinned commit.")
            content = result.stdout
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"Shared source hash mismatch: {path}")
        blobs[path] = content
    module = types.ModuleType("locked_shared_freecad_geometry")
    exec(compile(blobs["scripts/freecad_geometry.py"], "<locked shared FreeCAD geometry>", "exec"),
         module.__dict__)
    for path in ("resources/fonts/B612Mono-Bold.ttf", "resources/fonts/OFL.txt"):
        target = project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blobs[path])
    parameters = json.loads(blobs["design/parameters.json"])
    interface = json.loads(blobs["design/interface.json"])
    catalog = json.loads(blobs["design/catalog.json"])
    if interface["brick"] != parameters["interface"] or interface["message"] != parameters["message"]:
        raise ValueError("Shared interface and parameter snapshot disagree")
    return module, parameters, interface, catalog
