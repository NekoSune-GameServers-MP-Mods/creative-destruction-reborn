"""Update Reborn Android APK discovery configuration, without game-code claims.

Replaces the two known existing assets:
  assets/nonpatch_user_data.dat
  assets/Documents/nonpatch_user_data.dat
Both must be present and valid JSON. It does NOT modify encrypted patch
configuration, game binaries, Steam authentication or gameplay protocol.

Original APK signatures are invalid after changing assets. This script removes
old signature blocks and requires external apksigner/signing as a second step.
It intentionally never copies passwords, bearer tokens, or signing keys into APK.
"""
import argparse
import ipaddress
import json
import re
import zipfile
from pathlib import Path

ASSETS = (
    "assets/nonpatch_user_data.dat",
    "assets/Documents/nonpatch_user_data.dat",
)
GAME_HOST = "game-cdr.nekosunevr.co.uk"


def validate_hostname(host):
    if not isinstance(host, str) or len(host) > 253 or not host:
        raise ValueError("Host name required")
    if "://" in host or "/" in host or ":" in host or "@" in host:
        raise ValueError("Enter host name only; do not include port or scheme")
    host = host.lower().strip().rstrip(".")
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        if len(host.split(".")) < 2 or not all(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in host.split(".")
        ):
            raise ValueError("Invalid hostname")
    else:
        if addr.is_loopback or addr.is_unspecified or addr.is_multicast:
            raise ValueError("Refusing localhost/unspecified/multicast addresses")
    return host


def patch_apk(source, destination, host=GAME_HOST):
    host = validate_hostname(host)
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("Use a different output file; preserve the original APK")
    if not zipfile.is_zipfile(source):
        raise ValueError("Input is not a valid ZIP/APK")
    target_url = "http://%s:8000/" % host
    updated = []
    with zipfile.ZipFile(source, "r") as apk:
        members = set(apk.namelist())
        if not set(ASSETS).issubset(members):
            raise ValueError("This APK lacks the known Reborn Android endpoint config assets")
        with zipfile.ZipFile(destination, "w", allowZip64=True) as output:
            output.comment = apk.comment
            for item in apk.infolist():
                path = item.filename
                # Do not accidentally retain now-invalid JAR/APK V1 signatures.
                if path.upper().startswith("META-INF/") and path.upper().endswith(
                    (".RSA", ".DSA", ".EC", ".SF", "MANIFEST.MF")
                ):
                    continue
                data = apk.read(item)
                if path in ASSETS:
                    config = json.loads(data)
                    if not isinstance(config, dict) or "http_url_prefix" not in config:
                        raise ValueError("Unexpected Android Reborn endpoint schema")
                    config["http_url_prefix"] = target_url
                    data = (json.dumps(config, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
                    updated.append(path)
                output.writestr(item, data)
    if sorted(updated) != sorted(ASSETS):
        destination.unlink(missing_ok=True)
        raise ValueError("Expected both Android Reborn endpoint assets to be patched")
    return target_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Existing experimental APK file")
    parser.add_argument("output", help="Unsigned experimental output APK")
    parser.add_argument("--game-host", default=GAME_HOST)
    args = parser.parse_args()
    url = patch_apk(args.input, args.output, args.game_host)
    print("Patched discovery endpoint: %s" % url)
    print("Output is UNSIGNED. Sign independently with Android apksigner, "
          "then verify installation and network behavior on a test device.")
    print("This is not proof of Android login or Steam crossplay.")


if __name__ == "__main__":
    main()
