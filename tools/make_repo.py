#!/usr/bin/env python3
import hashlib
import os
import re
import zipfile
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ADDONS_DIR = os.path.join(ROOT, "addons")
ZIPS_DIR = os.path.join(ROOT, "zips")

# Only these video add-ons are published by Barclay Repository.
ALLOWED_VIDEO_IDS = {
    "plugin.video.xship",
    "plugin.video.youtube",
}


def md5_for_text(text):
    m = hashlib.md5()
    m.update(text.encode("utf-8"))
    return m.hexdigest()


def version_key(version):
    # Good fit for our date-based xShip versions and YouTube's semver/local suffix.
    parts = re.findall(r"[0-9]+|[A-Za-z]+", version or "")
    return tuple((1, int(p)) if p.isdigit() else (0, p.lower()) for p in parts)


def addon_xml_from_zip(zip_path, expected_id):
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            preferred = f"{expected_id}/addon.xml"
            names = zf.namelist()
            if preferred in names:
                candidates = [preferred]
            else:
                candidates = sorted(
                    (n for n in names if n.endswith("/addon.xml") or n == "addon.xml"),
                    key=lambda n: (n.count("/"), len(n)),
                )

            for name in candidates:
                try:
                    text = zf.read(name).decode("utf-8", errors="strict").lstrip("\ufeff")
                    root = ET.fromstring(text)
                except Exception:
                    continue
                if root.tag == "addon" and root.attrib.get("id") == expected_id:
                    return text, root.attrib.get("version", "")
    except Exception as exc:
        print(f"Skipping unreadable ZIP {zip_path}: {exc}")
    return None, None


def latest_video_entries():
    entries = []

    for addon_id in sorted(ALLOWED_VIDEO_IDS):
        addon_dir = os.path.join(ZIPS_DIR, addon_id)
        if not os.path.isdir(addon_dir):
            raise RuntimeError(f"Required repository folder missing: {addon_dir}")

        candidates = []
        for fn in os.listdir(addon_dir):
            if not fn.endswith(".zip"):
                continue
            zip_path = os.path.join(addon_dir, fn)
            text, version = addon_xml_from_zip(zip_path, addon_id)
            if text and version:
                candidates.append((version_key(version), version, fn, text))

        if not candidates:
            raise RuntimeError(f"No valid ZIP found for {addon_id}")

        candidates.sort(key=lambda item: item[0])
        _, version, fn, text = candidates[-1]
        print(f"Publishing {addon_id} {version} from {fn}")
        entries.append(text)

    return entries


def gather_entries():
    entries = []

    # Repository metadata itself is required so Kodi can update the repository add-on.
    repo_xml = os.path.join(ADDONS_DIR, "repository.barclay", "addon.xml")
    if not os.path.exists(repo_xml):
        raise RuntimeError("repository.barclay/addon.xml is missing")
    with open(repo_xml, "r", encoding="utf-8") as f:
        entries.append(f.read().lstrip("\ufeff"))

    # Video section is intentionally restricted to xShip + YouTube.
    entries.extend(latest_video_entries())
    return entries


def write_addons_xml(entries):
    txt = "<addons>\n" + "\n".join(entries) + "\n</addons>\n"
    with open(os.path.join(ZIPS_DIR, "addons.xml"), "w", encoding="utf-8") as f:
        f.write(txt)
    with open(os.path.join(ZIPS_DIR, "addons.xml.md5"), "w", encoding="utf-8") as f:
        f.write(md5_for_text(txt))


def zip_repo():
    repo_id = "repository.barclay"
    repo_dir = os.path.join(ADDONS_DIR, repo_id)
    tree = ET.parse(os.path.join(repo_dir, "addon.xml"))
    root = tree.getroot()
    ver = root.attrib.get("version", "1.0.0")
    out = os.path.join(ZIPS_DIR, repo_id)
    os.makedirs(out, exist_ok=True)

    out_zip = os.path.join(out, f"{repo_id}-{ver}.zip")
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for rr, _, files in os.walk(repo_dir):
            for fn in files:
                ap = os.path.join(rr, fn)
                rel = os.path.relpath(ap, os.path.dirname(repo_dir))
                zf.write(ap, rel)


def main():
    write_addons_xml(gather_entries())
    zip_repo()
    print("Repository built: only xShip and YouTube are published as video add-ons.")


if __name__ == "__main__":
    main()
