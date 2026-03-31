#!/usr/bin/env python3
"""
Reverse geocode null addresses in 'db data/places.csv' using the Nominatim API
(OpenStreetMap, free, no API key required).

Usage:
    # Dry-run: preview what addresses would be filled in
    python scripts/geocode_places.py --dry-run

    # Fill in null addresses and write back to CSV
    python scripts/geocode_places.py

    # Validate all lat/lng values (check if they match expected city/country)
    python scripts/geocode_places.py --validate

    # Both fill addresses and validate
    python scripts/geocode_places.py --validate

Options:
    --dry-run    Show what would be changed without writing to CSV
    --validate   Also validate each row's lat/lng against its country/city
    --csv PATH   Path to the CSV file (default: 'db data/places.csv')
"""

import argparse
import csv
import os
import sys
import time

import requests
from data.country_aliases import COUNTRY_ALIASES

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"

# Respect Nominatim's usage policy: max 1 request/second
REQUEST_DELAY = 1.1

HEADERS = {"User-Agent": "artmap-geocoder/1.0 (https://github.com/artmap)"}


def reverse_geocode(lat: float, lon: float) -> dict | None:
    """Call Nominatim reverse geocoding; returns parsed JSON or None on error."""
    params = {
        "lat": lat,
        "lon": lon,
        "format": "jsonv2",
        "addressdetails": 1,
        "zoom": 18,
    }
    try:
        resp = requests.get(NOMINATIM_REVERSE_URL, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"  [ERROR] Nominatim request failed: {e}", file=sys.stderr)
        return None


def build_display_address(result: dict) -> str:
    """
    Build a clean display address from Nominatim response.
    Tries to produce: '<road/amenity>, <city>, <country>'
    Falls back to the full display_name.
    """
    addr = result.get("address", {})
    parts = []

    # Street-level component
    road = addr.get("road") or addr.get("pedestrian") or addr.get("footway") or addr.get("amenity")
    house_number = addr.get("house_number", "")
    if road:
        parts.append(f"{road} {house_number}".strip() if house_number else road)

    # City-level component
    city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality")
    if city:
        parts.append(city)

    # Country
    country = addr.get("country", "")
    if country:
        parts.append(country)

    return ", ".join(parts) if parts else result.get("display_name", "")


def validate_location(result: dict, expected_country: str, expected_city: str) -> dict:
    """
    Compare Nominatim result against the expected country/city from the CSV.
    Returns a dict with:
        ok        – True if both country and city loosely match
        country_ok
        city_ok
        got_country
        got_city
        note      – human-readable verdict
    """
    addr = result.get("address", {})

    got_country = addr.get("country", "").lower()
    got_city = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("municipality")
        or ""
    ).lower()

    aliases = COUNTRY_ALIASES.get(expected_country.upper(), [expected_country.lower()])
    country_ok = any(a in got_country for a in aliases)

    city_ok = expected_city.lower() in got_city or got_city in expected_city.lower()

    # special: "Washington, D.C." vs "washington"
    if not city_ok:
        city_ok = expected_city.lower().replace(",", "").replace(".", "").replace(
            " ", ""
        ) in got_city.replace(" ", "")

    ok = country_ok and city_ok
    note_parts = []
    if not country_ok:
        note_parts.append(f"country mismatch: expected={expected_country} got='{got_country}'")
    if not city_ok:
        note_parts.append(f"city mismatch: expected='{expected_city}' got='{got_city}'")
    note = "; ".join(note_parts) if note_parts else "OK"

    return {
        "ok": ok,
        "country_ok": country_ok,
        "city_ok": city_ok,
        "got_country": got_country,
        "got_city": got_city,
        "note": note,
    }


def process_csv(csv_path: str, dry_run: bool, validate: bool):
    if not os.path.exists(csv_path):
        print(f"[ERROR] File not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if "address" not in fieldnames:
        print("[ERROR] CSV has no 'address' column.", file=sys.stderr)
        sys.exit(1)

    needs_geocode = [r for r in rows if not r["address"] or r["address"].strip() in ("", "null")]
    has_address = [r for r in rows if r["address"] and r["address"].strip() not in ("", "null")]

    print(f"Total rows        : {len(rows)}")
    print(f"Null/empty address: {len(needs_geocode)}")
    print(f"Already has address: {len(has_address)}")
    if dry_run:
        print("[DRY-RUN mode – no file will be written]\n")

    # --- Validation report header ---
    if validate:
        print("\n" + "=" * 70)
        print("LAT/LNG VALIDATION REPORT")
        print("=" * 70)

    changed = 0
    validation_errors = []

    for row in rows:
        name = row.get("name_en") or row.get("name_ko") or row.get("id")
        lat_str = row.get("latitude", "").strip()
        lon_str = row.get("longitude", "").strip()

        if not lat_str or not lon_str:
            print(f"  [SKIP] {name}: missing lat/lon")
            continue

        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except ValueError:
            print(f"  [SKIP] {name}: invalid lat/lon values ({lat_str}, {lon_str})")
            continue

        address_empty = not row["address"] or row["address"].strip() in ("", "null")

        if not address_empty and not validate:
            continue  # nothing to do for this row

        time.sleep(REQUEST_DELAY)
        result = reverse_geocode(lat, lon)
        if result is None:
            print(f"  [FAIL] {name}: no result from Nominatim")
            continue

        # ---------- Fill address ----------
        if address_empty:
            new_address = build_display_address(result)
            print(f"  [GEOCODE] {name}")
            print(f"    lat={lat}, lon={lon}")
            print(f"    → {new_address}")
            if not dry_run:
                row["address"] = new_address
            changed += 1

        # ---------- Validate lat/lng ----------
        if validate:
            expected_country = row.get("country", "").strip()
            expected_city = row.get("city", "").strip()
            verdict = validate_location(result, expected_country, expected_city)
            status = "✓" if verdict["ok"] else "✗"
            print(f"  [{status}] {name} ({lat}, {lon})")
            if not verdict["ok"]:
                print(f"      ⚠ {verdict['note']}")
                validation_errors.append(
                    {
                        "name": name,
                        "lat": lat,
                        "lon": lon,
                        "note": verdict["note"],
                    }
                )

    # --- Summary ---
    print("\n" + "=" * 70)
    if not dry_run and changed > 0:
        # Write back to CSV preserving original column order
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"✅  Updated {changed} address(es) written to: {csv_path}")
    elif dry_run and changed > 0:
        print(f"[DRY-RUN] Would update {changed} address(es). Run without --dry-run to apply.")
    else:
        print("No address changes needed.")

    if validate:
        print(
            f"\nValidation: {len(rows) - len([r for r in rows if not r.get('latitude')])} rows checked"
        )
        if validation_errors:
            print(f"⚠  {len(validation_errors)} potential lat/lng issue(s) found:")
            for err in validation_errors:
                print(f"   • {err['name']} ({err['lat']}, {err['lon']}): {err['note']}")
        else:
            print("✅  All lat/lng values match their expected country/city.")


def main():
    parser = argparse.ArgumentParser(
        description="Reverse-geocode null addresses in places.csv and/or validate lat/lng data."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without writing to the CSV."
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate lat/lng values against the expected country and city.",
    )
    parser.add_argument(
        "--csv",
        default="db data/places.csv",
        help="Path to the CSV file (default: 'db data/places.csv').",
    )
    args = parser.parse_args()

    # Resolve path relative to the project root (one level up from scripts/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    csv_path = os.path.join(project_root, args.csv) if not os.path.isabs(args.csv) else args.csv

    process_csv(csv_path, dry_run=args.dry_run, validate=args.validate)


if __name__ == "__main__":
    main()
