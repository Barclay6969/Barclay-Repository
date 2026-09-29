#!/usr/bin/env python3
import hashlib
import os
import re
import shutil
import urllib.request
import zipfile
from pathlib import Path

UPSTREAM_VERSION = "7.4.4"
PATCH_VERSION = "7.4.4+barclay.1"
UPSTREAM_URL = (
    "https://github.com/anxdpanic/plugin.video.youtube/releases/download/"
    f"v{UPSTREAM_VERSION}/plugin.video.youtube-{UPSTREAM_VERSION}.zip"
)
UPSTREAM_SHA256 = "2baa7f389816e961f2a509f639c5788ea1a8f9ce95bcd551916bb34df82e2da3"

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".youtube-patch-work"
SOURCE_ZIP = WORK / f"plugin.video.youtube-{UPSTREAM_VERSION}.zip"
EXTRACT = WORK / "extract"
ADDON_DIR = EXTRACT / "plugin.video.youtube"
PLAYER_CLIENT = ADDON_DIR / "resources/lib/youtube_plugin/youtube/client/player_client.py"
ADDON_XML = ADDON_DIR / "addon.xml"
OUTPUT_DIR = ROOT / "zips" / "plugin.video.youtube"
OUTPUT_ZIP = OUTPUT_DIR / f"plugin.video.youtube-{PATCH_VERSION}.zip"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    EXTRACT.mkdir()

    print(f"Downloading official YouTube {UPSTREAM_VERSION}...")
    urllib.request.urlretrieve(UPSTREAM_URL, SOURCE_ZIP)
    actual_sha = sha256(SOURCE_ZIP)
    if actual_sha != UPSTREAM_SHA256:
        raise SystemExit(
            f"Upstream SHA256 mismatch: expected {UPSTREAM_SHA256}, got {actual_sha}"
        )

    with zipfile.ZipFile(SOURCE_ZIP, "r") as zf:
        zf.extractall(EXTRACT)

    if not PLAYER_CLIENT.exists() or not ADDON_XML.exists():
        raise SystemExit("Unexpected upstream ZIP layout")

    player = PLAYER_CLIENT.read_text(encoding="utf-8")
    target = "                'android_vr',\n"
    count = player.count(target)
    if count != 1:
        raise SystemExit(f"Expected exactly one android_vr playback entry, found {count}")
    player = player.replace(
        target,
        "                # 'android_vr',  # Barclay fix: avoids playback stall / HTTP 403\n",
        1,
    )
    PLAYER_CLIENT.write_text(player, encoding="utf-8")

    addon = ADDON_XML.read_text(encoding="utf-8")
    addon, count = re.subn(
        r'(<addon\s+id="plugin\.video\.youtube"\s+name="YouTube"\s+version=")[^"]+(")',
        rf'\g<1>{PATCH_VERSION}\2',
        addon,
        count=1,
    )
    if count != 1:
        raise SystemExit("Could not update addon.xml version")
    ADDON_XML.write_text(addon, encoding="utf-8")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ADDON_DIR.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(EXTRACT))

    # Verify the produced package before publishing.
    with zipfile.ZipFile(OUTPUT_ZIP, "r") as zf:
        patched_player = zf.read(
            "plugin.video.youtube/resources/lib/youtube_plugin/youtube/client/player_client.py"
        ).decode("utf-8")
        patched_addon = zf.read("plugin.video.youtube/addon.xml").decode("utf-8")
        if "'android_vr'," in patched_player.replace("# 'android_vr',", ""):
            raise SystemExit("android_vr playback entry still active in output ZIP")
        if f'version="{PATCH_VERSION}"' not in patched_addon:
            raise SystemExit("Patched version missing from output addon.xml")

    print(f"Built: {OUTPUT_ZIP.relative_to(ROOT)}")
    print(f"SHA256: {sha256(OUTPUT_ZIP)}")
    shutil.rmtree(WORK)


if __name__ == "__main__":
    main()
