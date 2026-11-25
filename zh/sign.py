"""Sign the independent Chinese Android build and verify its APK inventory."""
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

from build import check_members


def main(tools, unsigned, target):
    signing = json.loads(os.environ.pop("SIGNING_BUNDLE"))
    with tempfile.TemporaryDirectory(dir=os.environ["RUNNER_TEMP"]) as directory:
        staging = Path(directory)
        aligned = staging / "aligned.apk"
        keystore = staging / "signing.p12"
        keystore.write_bytes(base64.b64decode(signing["keystore"], validate=True))
        keystore.chmod(0o600)
        subprocess.run([tools / "zipalign", "-P", "16", "-f", "4", unsigned, aligned], check=True)
        subprocess.run([tools / "apksigner", "sign", "--ks", keystore, "--ks-key-alias", "rekhcom-zh",
                        "--ks-pass", "env:SIGNING_PASSWORD", "--v4-signing-enabled", "false",
                        "--out", target, aligned], check=True,
                       env=dict(os.environ, SIGNING_PASSWORD=signing["password"]))
    subprocess.run([tools / "apksigner", "verify", "--verbose", target], check=True)
    subprocess.run([tools / "zipalign", "-c", "-P", "16", "4", target], check=True)
    subprocess.run([tools / "aapt", "dump", "badging", target], check=True, stdout=subprocess.DEVNULL)
    with ZipFile(target) as apk:
        check_members(apk)
        dex = [apk.read(name) for name in apk.namelist() if name.endswith(".dex")]
        if apk.testzip() or not any(b"7ebd009e0a3394ae2ad66e7fab77170053e90056" in item for item in dex):
            raise ValueError("Signed APK is corrupt or the Chinese ROM importer is missing")
        if not any("ReKHCoM · 安全启动".encode() in item for item in dex):
            raise ValueError("Chinese safe-startup screen is missing from the APK")
        font = apk.read("assets/fonts/ReKHCoM-Zh.ttf")
        for abi in ("armeabi-v7a", "arm64-v8a"):
            if not font or font not in apk.read(f"lib/{abi}/liblauncher.so"):
                raise ValueError(f"Bundled Chinese font is missing from the {abi} launcher")


if __name__ == "__main__":
    main(*(Path(value) for value in sys.argv[1:]))
