"""Generate the exact glyph ranges and the APK launcher's embedded OFL font."""

import json
import re
import sys
from pathlib import Path


def translations(source):
    directory = source / "port/decompui/i18n"
    rows = json.loads((directory / "strings.json").read_text(encoding="utf-8"))
    active = {row["en"] for row in rows}
    zh = json.loads((directory / "zh.json").read_text(encoding="utf-8"))
    text = "简体中文"
    text += "".join(zh[key] for key in active & zh.keys())
    java = source / "port/android/app/src/main/java/com/rekhcom/android/LauncherActivity.java"
    text += "".join(re.findall(r"[\u3000-\u303f\u3400-\u9fff\uff00-\uffef]", java.read_text(encoding="utf-8")))
    required = {ord(character) for character in text if character.isprintable()}
    latin = "Español English Français Deutsch Italiano 日本語 ← ↑ → ↓ ✓ × …"
    extra = latin + "".join(row["en"] + row["es"] for row in rows)
    for locale in ("fr", "de", "it", "ja"):
        table = json.loads((directory / f"{locale}.json").read_text(encoding="utf-8"))
        extra += "".join(table[key] for key in active & table.keys())
    available = required | set(range(32, 127)) | {ord(c) for c in extra if c.isprintable()}
    return required, available


def generate(source, directory, mode):
    from fontTools.ttLib import TTFont

    required, available = translations(source)
    filename = directory / ("regular.ttf" if mode == "collect" else "ReKHCoM-Zh.ttf")
    with TTFont(filename) as font:
        cmap = set(font.getBestCmap())
    missing = required - cmap
    if missing:
        raise SystemExit("Missing Chinese launcher glyphs: " + " ".join(f"U+{cp:04X}" for cp in sorted(missing)))
    points = sorted(cmap & available)
    if mode == "collect":
        (directory / "characters.txt").write_text("".join(map(chr, points)), encoding="utf-8")
        return
    ranges = []
    for point in points:
        if ranges and ranges[-1][1] + 1 == point:
            ranges[-1][1] = point
        else:
            ranges.append([point, point])
    data = filename.read_bytes()
    with (directory / "zh_launcher_font.inc").open("w", encoding="ascii", newline="\n") as output:
        output.write("// Generated from the packaged Noto Sans SC subset (SIL OFL 1.1).\n")
        output.write("static const unsigned char kLauncherFontBytes[] = {\n")
        for start in range(0, len(data), 24):
            output.write("    " + ",".join(map(str, data[start:start + 24])) + ",\n")
        output.write("};\nstatic const ImWchar kLauncherFontRanges[] = {\n")
        for start, end in ranges:
            output.write(f"    0x{start:04x}, 0x{end:04x},\n")
        output.write("    0\n};\n")
    print(f"Embedded font validated: {len(required)} required Chinese UI glyphs, {len(points)} total")


if __name__ == "__main__":
    generate(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
