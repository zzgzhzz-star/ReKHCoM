"""Package the localized launchers against binaries from the same upstream release."""

import argparse
import hashlib
import os
import re
import shutil
import sys
import urllib.request
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def verify_archive(path, expected):
    if digest(path) != expected:
        raise ValueError(f"Upstream SHA-256 mismatch: {path.name}")


def check_members(archive):
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError("Upstream archive has duplicate entries")
    if any(Path(name).suffix.lower() in {".gba", ".agb", ".sav", ".khst"} for name in names):
        raise ValueError("Upstream archive unexpectedly contains ROM, save or save-state data")


def windows(args):
    verify_archive(args.upstream, args.sha256)
    with ZipFile(args.upstream) as source, ZipFile(args.output, "w", ZIP_DEFLATED) as target:
        check_members(source)
        if "ReKHCoM.exe" not in source.namelist():
            raise ValueError("Upstream Windows launcher is missing")
        for member in source.infolist():
            data = args.launcher.read_bytes() if member.filename == "ReKHCoM.exe" else source.read(member)
            target.writestr(member, data)
        target.write(args.font, "assets/fonts/ReKHCoM-Zh.ttf")
        target.write(args.font.with_name("OFL.txt"), "assets/fonts/ReKHCoM-Zh-OFL.txt")
    with ZipFile(args.output) as archive:
        if archive.testzip():
            raise ValueError("Corrupt Windows package")


def android(args):
    verify_archive(args.upstream, args.sha256)
    root = args.source.resolve()
    sys.path.insert(0, str(root / "port/tools"))
    from build_android import package_identity, prepare_java_first_entry

    version_header = (root / "port/include/port/port_version.h").read_text(encoding="utf-8")
    source_version = re.search(r'#define REKHCOM_VERSION\s+"([^"]+)"', version_header)[1]
    identity = package_identity(source_version)
    hotfix = os.environ.get("ANDROID_HOTFIX") == "true"
    version_code = identity["version_code"] + int(hotfix)
    version_name = f"{source_version}[ZH]" + (".1" if hotfix else "")
    identity["application_id"] = "com.rekhcom.android.zh"
    stage, sdl = args.output.resolve(), args.sdl.resolve()
    shutil.copytree(root / "port/android/app", stage / "app")
    prepare_java_first_entry(stage, sdl, identity)
    main = stage / "app/src/main"
    manifest = main / "AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")
    if 'android:label="ReKHCoM Beta"' not in text:
        raise ValueError("Upstream Android app label changed")
    manifest.write_text(text.replace('android:label="ReKHCoM Beta"', 'android:label="ReKHCoM [ZH]"', 1),
                        encoding="utf-8")
    skeleton = sdl / "android-project"
    shutil.copytree(skeleton / "app/src/main/java/org", main / "java/org")
    shutil.copytree(skeleton / "gradle", stage / "gradle")
    shutil.copyfile(skeleton / "gradlew", stage / "gradlew")
    (stage / "gradlew").chmod(0o755)
    gradle_version = "8.12"
    gradle_distribution = f"https://services.gradle.org/distributions/gradle-{gradle_version}-bin.zip"
    with urllib.request.urlopen(gradle_distribution + ".sha256", timeout=30) as checksum:
        gradle_sha256 = checksum.read().decode().strip()
    if not re.fullmatch(r"[a-f0-9]{64}", gradle_sha256):
        raise ValueError("Invalid Gradle distribution checksum")
    (stage / "gradle/wrapper/gradle-wrapper.properties").write_text(
        "distributionBase=GRADLE_USER_HOME\ndistributionPath=wrapper/dists\n"
        f"distributionUrl={gradle_distribution}\ndistributionSha256Sum={gradle_sha256}\n"
        "zipStoreBase=GRADLE_USER_HOME\nzipStorePath=wrapper/dists\n", encoding="ascii")
    (stage / "settings.gradle").write_text(
        "pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }\n"
        "dependencyResolutionManagement { repositories { google(); mavenCentral() } }\n"
        "rootProject.name = 'ReKHCoMZH'\ninclude ':app'\n", encoding="ascii")
    (stage / "build.gradle").write_text(
        "plugins { id 'com.android.application' version '8.7.3' apply false }\n", encoding="ascii")
    (stage / "app/build.gradle").write_text(f"""plugins {{ id 'com.android.application' }}
android {{
    namespace 'com.rekhcom.android'
    compileSdk 35
    defaultConfig {{
        applicationId '{identity["application_id"]}'
        minSdk 21
        targetSdk 35
        versionCode {version_code}
        versionName '{version_name}'
    }}
    compileOptions {{
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }}
    packaging {{ jniLibs {{ useLegacyPackaging = true; keepDebugSymbols += ['**/*.so'] }} }}
}}
""", encoding="utf-8")

    launchers = {"armeabi-v7a": args.launcher, "arm64-v8a": args.arm64}
    required = {f"lib/{abi}/lib{name}.so" for abi, names in {
        "armeabi-v7a": ("SDL3", "launcher", "rekhcom_eu", "rekhcom_us", "rekhcom_jp"),
        "arm64-v8a": ("SDL3", "launcher", "rekhcom64"),
    }.items() for name in names}
    required.update(f"assets/guest-{region}.macho" for region in ("eu", "us", "jp"))
    with ZipFile(args.upstream) as archive:
        check_members(archive)
        if not required <= set(archive.namelist()):
            raise ValueError("Upstream Android APK is missing expected game libraries or images")
        for member in archive.infolist():
            if member.is_dir():
                continue
            pieces = member.filename.split("/")
            if not member.filename.startswith(("assets/", "lib/")):
                continue
            if any(part in {"", ".", ".."} or "\\" in part or ":" in part for part in pieces):
                raise ValueError(f"Unexpected member in upstream APK: {member.filename}")
            if pieces[0] == "lib":
                if len(pieces) != 3 or pieces[1] not in launchers or not pieces[2].endswith(".so"):
                    raise ValueError(f"Unexpected native library in upstream APK: {member.filename}")
                out = main / "jniLibs" / pieces[1] / pieces[2]
                launcher = launchers[pieces[1]] if pieces[2] == "liblauncher.so" else None
            else:
                out = main.joinpath(*pieces)
                launcher = None
            out.parent.mkdir(parents=True, exist_ok=True)
            if launcher:
                shutil.copyfile(launcher, out)
            else:
                with archive.open(member) as binary, out.open("wb") as destination:
                    shutil.copyfileobj(binary, destination)
    shutil.copyfile(args.font, main / "assets/fonts/ReKHCoM-Zh.ttf")
    shutil.copyfile(args.font.with_name("OFL.txt"), main / "assets/fonts/ReKHCoM-Zh-OFL.txt")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=("windows", "android"))
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--launcher", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--arm64", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--sdl", type=Path)
    args = parser.parse_args()
    if args.platform == "android":
        if not all((args.arm64, args.source, args.sdl)):
            parser.error("Android requires --arm64, --source and --sdl")
        android(args)
    else:
        windows(args)


if __name__ == "__main__":
    main()
