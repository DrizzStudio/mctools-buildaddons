"""Shared helpers for the mctools-buildaddons scripts (pure Python, no dependencies)."""

from __future__ import annotations
import json
import re
import struct
import zlib
from pathlib import Path

LICENSE_NOTE = "CC0-1.0: original procedurally generated artwork, free to use in any add-on, no attribution required"
SOFTWARE_NOTE = "mctools-buildaddons procedural texture generator"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


# ----------------------------------------------------------------------------- PNG writing


def _chunk(tag: bytes, data: bytes) -> bytes:
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def png_bytes(rows, text: dict | None = None) -> bytes:
    """rows: list of rows, each a list of (r, g, b, a) tuples. Returns an 8-bit RGBA PNG."""
    height = len(rows)
    width = len(rows[0])
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for r, g, b, a in row:
            raw.extend((r, g, b, a))
    out = PNG_SIGNATURE
    out += _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    for key, value in (text or {}).items():
        out += _chunk(b"tEXt", key.encode("latin-1") + b"\0" + value.encode("latin-1", "replace"))
    out += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    out += _chunk(b"IEND", b"")
    return out


def write_png(path: Path, rows, text: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png_bytes(rows, text))


def upscale(rows, factor: int):
    """Nearest-neighbour upscale (keeps pixel art crisp)."""
    if factor <= 1:
        return rows
    out = []
    for row in rows:
        wide = [px for px in row for _ in range(factor)]
        out.extend([list(wide) for _ in range(factor)])
    return out


# ----------------------------------------------------------------------------- PNG reading (validation)


def read_png_info(path: Path) -> dict:
    """Parse a PNG and report size and whether it contains visible pixels.

    Returns keys: ok, problem, width, height, bit_depth, color_type, interlace, visible (None if unknown).
    """
    info = {"ok": False, "problem": None, "width": 0, "height": 0, "bit_depth": 0, "color_type": 0, "interlace": 0, "visible": None}
    data = path.read_bytes()
    if data[:8] != PNG_SIGNATURE:
        info["problem"] = "not a PNG file (bad signature)"
        return info
    pos, idat, seen_ihdr, seen_iend = 8, bytearray(), False, False
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        crc = data[pos + 8 + length:pos + 12 + length]
        if len(body) != length or len(crc) != 4:
            info["problem"] = "truncated PNG"
            return info
        if zlib.crc32(tag + body) & 0xFFFFFFFF != struct.unpack(">I", crc)[0]:
            info["problem"] = f"corrupt chunk {tag!r} (CRC mismatch)"
            return info
        if tag == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            info.update(width=w, height=h, bit_depth=depth, color_type=ctype, interlace=interlace)
            seen_ihdr = True
        elif tag == b"IDAT":
            idat.extend(body)
        elif tag == b"IEND":
            seen_iend = True
            break
        pos += 12 + length
    if not seen_ihdr or not seen_iend:
        info["problem"] = "PNG is missing IHDR or IEND"
        return info
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error:
        info["problem"] = "PNG image data cannot be decompressed"
        return info
    info["ok"] = True

    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(info["color_type"])
    if info["bit_depth"] != 8 or info["interlace"] != 0 or channels is None:
        return info  # valid PNG, but visibility check only supports plain 8-bit images
    w, h = info["width"], info["height"]
    stride = w * channels
    if len(raw) != h * (stride + 1):
        info["ok"], info["problem"] = False, "PNG pixel data has the wrong length"
        return info
    if info["color_type"] in (0, 2):
        info["visible"] = True
        return info

    prev = bytearray(stride)
    visible = False
    for y in range(h):
        ftype = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            if ftype == 1:
                line[i] = (line[i] + a) & 255
            elif ftype == 2:
                line[i] = (line[i] + b) & 255
            elif ftype == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 255
        if any(line[channels - 1::channels]):
            visible = True
        prev = line
    info["visible"] = visible
    return info


# ----------------------------------------------------------------------------- JSON / text helpers


def dumps_json(value, level: int = 0) -> str:
    """Pretty JSON where lists of plain numbers/strings stay on one line, e.g. "version": [1, 0, 0]."""
    pad, inner = "  " * level, "  " * (level + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [f"{inner}{json.dumps(k, ensure_ascii=False)}: {dumps_json(v, level + 1)}" for k, v in value.items()]
        return "{\n" + ",\n".join(items) + f"\n{pad}}}"
    if isinstance(value, list):
        if all(not isinstance(v, (dict, list)) for v in value):
            return "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in value) + "]"
        items = [f"{inner}{dumps_json(v, level + 1)}" for v in value]
        return "[\n" + ",\n".join(items) + f"\n{pad}]"
    return json.dumps(value, ensure_ascii=False)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_json(data) + "\n", encoding="utf-8")


def read_json_strict(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} is not valid JSON ({exc.msg}, line {exc.lineno}). Fix it first; refusing to overwrite.")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "addon"


def valid_identifier_part(text: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_]{0,63}", text))


def hex_to_rgb(text: str):
    value = text.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise SystemExit(f"Color must be a hex value like #d81e5b, got: {text!r}")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


# ----------------------------------------------------------------------------- resource pack registration


def register_texture(rp_dir: Path, kind: str, shortname: str, rel_path: str, pack_name: str) -> Path:
    """Add a texture shortname to item_texture.json (kind='item') or terrain_texture.json (kind='block')."""
    if kind == "item":
        path = rp_dir / "textures" / "item_texture.json"
        base = {"resource_pack_name": pack_name, "texture_name": "atlas.items", "texture_data": {}}
    else:
        path = rp_dir / "textures" / "terrain_texture.json"
        base = {"resource_pack_name": pack_name, "texture_name": "atlas.terrain", "padding": 8, "num_mip_levels": 4, "texture_data": {}}
    data = read_json_strict(path) if path.exists() else base
    data.setdefault("texture_data", {})[shortname] = {"textures": rel_path}
    write_json(path, data)
    return path


def add_lang(rp_dir: Path, key: str, value: str) -> Path:
    """Add or update `key=value` in texts/en_US.lang and make sure languages.json lists en_US."""
    value = value.replace("\n", " ").strip()
    lang = rp_dir / "texts" / "en_US.lang"
    lines = lang.read_text(encoding="utf-8").splitlines() if lang.exists() else []
    entry, replaced = f"{key}={value}", False
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[i], replaced = entry, True
    if not replaced:
        lines.append(entry)
    lang.parent.mkdir(parents=True, exist_ok=True)
    lang.write_text("\n".join(lines) + "\n", encoding="utf-8")

    languages = rp_dir / "texts" / "languages.json"
    if not languages.exists():
        write_json(languages, ["en_US"])
    else:
        current = read_json_strict(languages)
        if isinstance(current, list) and "en_US" not in current:
            current.append("en_US")
            write_json(languages, current)
    return lang
