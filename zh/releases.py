"""Find compatible upstream releases and publish complete, verified build sets."""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from build import digest


UPSTREAM = "MatyMeatBoy/ReKHCoM"
FORK = "zzgzhzz-star/ReKHCoM"
SUFFIXES = {"windows": "windows-x86-x64.zip", "android": "android-beta.apk"}


def api(path, *, missing_ok=False):
    result = subprocess.run(("gh", "api", path), capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        if missing_ok and "(HTTP 404)" in result.stderr:
            return None
        raise RuntimeError(result.stderr.rstrip())
    return json.loads(result.stdout)


def local_release(tag):
    published = api(f"repos/{FORK}/releases/tags/{tag}", missing_ok=True)
    if published:
        return published
    releases = api(f"repos/{FORK}/releases?per_page=100")
    return next((release for release in releases if release["tag_name"] == tag), None)


def discover():
    requested = os.environ.get("REQUESTED_TAG", "")
    if requested and not re.fullmatch(r"v[0-9]+(?:\.[0-9]+){1,2}(?:-pre[1-9][0-9]?)?", requested):
        raise ValueError("Invalid upstream release tag")
    choice = f"tags/{requested}" if requested else "latest"
    release = api(f"repos/{UPSTREAM}/releases/{choice}")
    tag = release["tag_name"]
    if release["draft"] or not re.fullmatch(r"v[0-9]+(?:\.[0-9]+){1,2}(?:-pre[1-9][0-9]?)?", tag):
        raise ValueError(f"Unsupported upstream release version: {tag}")
    target = tag + "-zh"
    existing = local_release(target)
    outputs = {"needed": "false"}
    if not existing or existing["draft"]:
        outputs.update(needed="true", tag=tag, target=target)
        for platform, suffix in SUFFIXES.items():
            name = f"ReKHCoM-{tag}-{suffix}"
            asset = next((asset for asset in release["assets"] if asset["name"] == name), None)
            if not asset or not re.fullmatch(r"sha256:[a-f0-9]{64}", asset.get("digest") or ""):
                raise ValueError(f"Missing published asset or SHA-256: {name}")
            expected_url = f"https://github.com/{UPSTREAM}/releases/download/{tag}/{name}"
            if asset["browser_download_url"] != expected_url:
                raise ValueError(f"Unexpected download URL for {name}")
            outputs[f"{platform}_url"] = expected_url
            outputs[f"{platform}_sha"] = asset["digest"].split(":")[1]
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.writelines(f"{key}={value}\n" for key, value in outputs.items())


def publish():
    tag, target, commit = (os.environ[key] for key in ("UPSTREAM_TAG", "TARGET_TAG", "GITHUB_SHA"))
    release = api(f"repos/{UPSTREAM}/releases/tags/{tag}")
    title = (release["name"] or tag) + "[ZH]"
    existing = local_release(target)
    if existing and not existing["draft"]:
        print("The localized release is already published.")
        return
    dist = Path("dist")
    files = [dist / f"ReKHCoM-{tag}-zh-CN-Windows.zip", dist / f"ReKHCoM-{tag}-zh-CN-Android.apk"]
    hashes = {file.name: digest(file) for file in files}
    sums = dist / "SHA256SUMS.txt"
    sums.write_text("".join(f"{value}  {name}\n" for name, value in hashes.items()), encoding="ascii")
    files.append(sums)
    hashes[sums.name] = digest(sums)

    mode = ["--prerelease"] if release["prerelease"] else []
    notes = f"""简体中文启动器和已验证的日版汉化 ROM 导入。

- Windows 和 Android 均可导入受支持的 32 MiB 日版汉化 ROM。启动器校验整个文件，并将它保存到单独的日版汉化槽。
- 支持的 ROM SHA-1 为 `7ebd009e0a3394ae2ad66e7fab77170053e90056`。其他原版卡带的校验规则照旧。附件不包含 ROM。
- Windows 和 Android 游戏核心来自同一上游版本。中文剧情和字形取决于 ROM 补丁与核心的兼容性。
- 这个 Android 版本使用独立的 `com.rekhcom.android.zh` 包名，可与上游应用共存。若要迁移存档，请通过启动器导出和导入。

[上游发行版]({release["html_url"]}) · [云构建](https://github.com/{FORK}/actions/runs/{os.environ["GITHUB_RUN_ID"]})
"""
    if not existing:
        with tempfile.TemporaryDirectory() as staging:
            notes_file = Path(staging) / "notes.md"
            notes_file.write_text(notes, encoding="utf-8")
            subprocess.run(("gh", "release", "create", "--repo", FORK, f"--title={title}",
                            "--target", commit, "--notes-file", str(notes_file), "--draft", *mode, target),
                           check=True)
    subprocess.run(("gh", "release", "upload", "--repo", FORK, "--clobber", target,
                    *(str(file) for file in files)), check=True)
    saved = local_release(target)
    if not saved or not saved["draft"] or {asset["name"]: asset["digest"] for asset in saved["assets"]} != {
        name: f"sha256:{value}" for name, value in hashes.items()
    }:
        raise ValueError("Staged release asset inventory or SHA-256 differs from the builds")
    subprocess.run(("gh", "release", "edit", "--repo", FORK, f"--title={title}", "--draft=false", *mode, target),
                   check=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["discover"]:
        discover()
    elif sys.argv[1:] == ["publish"]:
        publish()
    else:
        raise SystemExit("expected discover or publish")
