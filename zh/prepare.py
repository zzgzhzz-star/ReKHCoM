"""Validate the applied source overlay and collect shipped Chinese glyphs."""

import json
import os
import re
import sys
from pathlib import Path


def main(root):
    config = root / "port/decompui/i18n"
    translations = json.loads((config / "zh.json").read_text(encoding="utf-8"))
    source = json.loads((config / "strings.json").read_text(encoding="utf-8"))
    active = {entry["en"] for entry in source}
    placeholders = re.compile(r"%[-+.0-9]*[a-zA-Z%]")
    for key in active & translations.keys():
        if placeholders.findall(key) != placeholders.findall(translations[key]):
            raise ValueError(f"Translation placeholders differ: {key}")
    if missing := sorted(active - translations.keys()):
        print(f"{len(missing)} new or changed launcher strings retain English")
    rom_hash = "7ebd009e0a3394ae2ad66e7fab77170053e90056"
    for filename in ("port/decompui/decompui.cpp",
                     "port/android/app/src/main/java/com/rekhcom/android/RomImport.java"):
        if rom_hash not in (root / filename).read_text(encoding="utf-8"):
            raise ValueError(f"Chinese ROM support not applied: {filename}")
    sdl_build = (root / "port/tools/build_android.py").read_text(encoding="utf-8")
    sdl_version = re.search(r"SDL3-([0-9]+\.[0-9]+\.[0-9]+)", sdl_build)
    if not sdl_version:
        raise ValueError("Cannot determine upstream SDL version")
    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as env:
        env.write(f"SDL_VERSION={sdl_version[1]}\n")
    for directory in ("font", "deps", "dist"):
        Path(directory).mkdir(exist_ok=True)
    characters = set("简体中文" + "".join(translations[k] for k in active & translations.keys()))
    Path("font/characters.txt").write_text("".join(sorted(characters)), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
