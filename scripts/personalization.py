"""Strict text-as-data input and explicit public/private publication boundaries."""

import json
from pathlib import Path
import string

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = set(string.ascii_letters + string.digits + " .,/:@_-!'()")
GENERIC_LINES = ["Same icon, New adventures", "github.com/USER"]
GENERIC_FIRST_LINES = {"Same icon, New adventures", "YOUR MESSAGE HERE", "YOUR DISPLAY NAME", "YOUR TEXT"}


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field; correct the input explicitly.")
        result[key] = value
    return result


def validate_lines(lines):
    if not isinstance(lines, list) or len(lines) != 2:
        raise ValueError("Exactly two display lines are required; no truncation or implicit third line.")
    for index, line in enumerate(lines, 1):
        if not isinstance(line, str) or not 1 <= len(line) <= 120:
            raise ValueError(f"Display line {index} must be a nonempty string of at most120 characters.")
        if line != line.strip():
            raise ValueError(f"Display line {index} has surrounding whitespace; correct it explicitly.")
        for position, character in enumerate(line, 1):
            if character not in ALLOWED:
                raise ValueError(f"Unsupported character in line {index} at position {position}; stop and select a supported font/layout.")
    return list(lines)


def validate_public(parameters, policy=None):
    policy = policy if policy is not None else json.loads(
        (ROOT / "design/publication-policy.json").read_text(), object_pairs_hook=strict_object)
    if not isinstance(policy, dict):
        raise ValueError("Publication policy must be a JSON object.")
    if set(policy) != {"schema_version", "mode", "public_text_approved", "generic_lines",
                       "private_input", "private_output", "warning"} or type(policy["schema_version"]) is not int or policy["schema_version"] != 1:
        raise ValueError("Unknown publication-policy schema.")
    lines = validate_lines(parameters["message"]["lines"])
    if policy["mode"] == "generic":
        if (policy["generic_lines"] != GENERIC_LINES or lines[0] not in GENERIC_FIRST_LINES
                or lines[1] != GENERIC_LINES[1] or policy["public_text_approved"] is not False):
            raise ValueError("Generic public mode accepts only the documented placeholders; use private input or an explicitly approved public fork.")
    elif policy["mode"] == "public_personalization":
        if policy["public_text_approved"] is not True:
            raise ValueError("Public personalization requires an explicit public-text approval in the fork's policy.")
    else:
        raise ValueError("Unknown public mode; private data must not enter the public build.")
    return parameters


def load_private(path):
    path = Path(path).resolve()
    if path.is_relative_to(ROOT) and not path.is_relative_to(ROOT / ".private"):
        raise ValueError("Private configuration inside this repository must be under the ignored .private directory.")
    if path.stat().st_size > 8192:
        raise ValueError("Private configuration exceeds the 8KiB input limit.")
    data = json.loads(path.read_text(), object_pairs_hook=strict_object)
    if not isinstance(data, dict):
        raise ValueError("Private configuration must be a JSON object.")
    if set(data) != {"schema_version", "visibility", "model", "lines"}:
        raise ValueError("Unknown private configuration fields.")
    if (type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["visibility"] != "private" or data["model"] not in ("A", "B", "C")):
        raise ValueError("Unsupported private configuration; choose A/B/C and visibility private.")
    return {**data, "lines": validate_lines(data["lines"])}


def private_output(path):
    result = Path(path).resolve()
    if not result.is_relative_to(ROOT / ".private"):
        raise ValueError("Private generated artifacts must stay in the ignored .private directory.")
    result.mkdir(parents=True, exist_ok=True)
    return result
