#!/usr/bin/env python3
"""
Build Triangle Device (70° multi-unit) - Fusion 360 model generation via MCP HTTP API.

3-well triangular layout with 70° angle at W2, two independent needle channels
for axon cutting experiments. Needle2 inserts from outside the triangle.

Units: 1 unit = 1 cm = 10 mm. All coordinates in cm.
Coordinate system (XZ plane): height→Z, width→X, depth→Y.
"""

import io
import json
import sys
import time

import requests

# Fix Windows console encoding for German umlauts in Fusion 360 responses
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:5002"
HEADERS = {"Content-Type": "application/json"}


def post(endpoint: str, data: dict | None = None) -> dict:
    """Send POST request to Fusion 360 add-in."""
    url = f"{BASE_URL}{endpoint}"
    payload = json.dumps(data or {})
    resp = requests.post(url, payload, HEADERS, timeout=120)
    result = resp.json()
    print(f"  -> {result.get('message', result)}")
    return result


def get(endpoint: str) -> dict:
    """Send GET request to Fusion 360 add-in."""
    url = f"{BASE_URL}{endpoint}"
    resp = requests.get(url, timeout=120)
    return resp.json()


def get_body_count() -> int:
    """Get current body count from Fusion 360."""
    try:
        data = get("/list_bodies")
        return data.get("body_count", 0)
    except Exception:
        return -1


def wait_for_bodies(expected: int, timeout: float = 15.0):
    """Poll until body count reaches expected value or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        count = get_body_count()
        if count >= expected:
            print(f"  [OK] bodies={count}")
            return count
        time.sleep(0.5)
    count = get_body_count()
    print(f"  [WARN] timeout, bodies={count} (expected {expected})")
    return count


def step(num: int, total: int, description: str):
    """Print step header."""
    print(f"\n[{num}/{total}] {description}")


def draw_box(height, width, depth, x, y, z, plane="XZ"):
    return post("/Box", {
        "height": height, "width": width, "depth": depth,
        "x": x, "y": y, "z": z, "plane": plane,
    })


def draw_cylinder(radius, height, x, y, z, plane="XZ"):
    return post("/draw_cylinder", {
        "radius": radius, "height": height,
        "x": x, "y": y, "z": z, "plane": plane,
    })


def draw_lines(points, plane="XZ"):
    return post("/draw_lines", {"points": points, "plane": plane})


def extrude(value, taperangle=0):
    return post("/extrude_last_sketch", {"value": value, "taperangle": taperangle})


def build():
    """Build the 70° triangle multi-unit axon device."""
    TOTAL = 24
    body_target = 0  # running count of expected bodies

    # ── Phase 0: Initialize ──────────────────────────────────────────
    step(1, TOTAL, "delete_all()")
    post("/delete_everything")
    time.sleep(2)  # give Fusion time to clear
    wait_for_bodies(0, timeout=10)

    # ── Phase 1: Wells (3x) ──────────────────────────────────────────
    step(2, TOTAL, "W1 (0, +3500μm)")
    draw_cylinder(0.03, 0.045, 0, 0, 0.35, "XZ")
    body_target += 1
    wait_for_bodies(body_target)

    step(3, TOTAL, "W2 (0, 0)")
    draw_cylinder(0.03, 0.045, 0, 0, 0, "XZ")
    body_target += 1
    wait_for_bodies(body_target)

    step(4, TOTAL, "W3 (-3289μm, +1197μm)")
    draw_cylinder(0.03, 0.045, -0.3289, 0, 0.1197, "XZ")
    body_target += 1
    wait_for_bodies(body_target)

    # ── Phase 2: Needle1 (axis-aligned, X direction) ─────────────────
    step(5, TOTAL, "Seal1 (1.5mm×170μm, center 0,0.175)")
    draw_box(0.017, 0.15, 0.017, 0, 0.175, 0, "XZ")
    body_target += 1
    wait_for_bodies(body_target)

    step(6, TOTAL, "Guide1 insertion side (1mm×220μm)")
    draw_box(0.022, 0.1, 0.024, 0.125, 0.175, 0, "XZ")
    body_target += 1
    wait_for_bodies(body_target)

    step(7, TOTAL, "Guide1 non-insertion side (0.3mm×220μm)")
    draw_box(0.022, 0.03, 0.024, -0.09, 0.175, 0, "XZ")
    body_target += 1
    wait_for_bodies(body_target)

    # Taper1: draw_lines (sketch only, no body yet) -> extrude
    step(8, TOTAL, "Taper1 sketch (trapezoid, 1mm→220μm)")
    draw_lines([
        [0.175, 0.186], [0.325, 0.225],
        [0.325, 0.125], [0.175, 0.164],
    ], "XZ")
    time.sleep(2)  # wait for sketch creation

    step(9, TOTAL, "Extrude Taper1 (400μm)")
    extrude(0.04, 0)
    body_target += 1
    wait_for_bodies(body_target)

    # ── Phase 3: Needle2 (rotated 70°, draw_lines, outside insertion) ─
    step(10, TOTAL, "Seal2 sketch (rotated 1.5mm×170μm)")
    draw_lines([
        [-0.14679, 0.13323], [-0.13081, 0.12742],
        [-0.18211, -0.01353], [-0.19809, -0.00772],
    ], "XZ")
    time.sleep(2)

    step(11, TOTAL, "Extrude Seal2 (170μm)")
    extrude(0.017, 0)
    body_target += 1
    wait_for_bodies(body_target)

    step(12, TOTAL, "Guide2 insertion side sketch (rotated 1mm×220μm)")
    draw_lines([
        [-0.20044, -0.00686], [-0.17976, -0.01439],
        [-0.21397, -0.10836], [-0.23464, -0.10083],
    ], "XZ")
    time.sleep(2)

    step(13, TOTAL, "Extrude Guide2 insertion (240μm)")
    extrude(0.024, 0)
    body_target += 1
    wait_for_bodies(body_target)

    step(14, TOTAL, "Guide2 non-insertion side sketch (rotated 0.3mm×220μm)")
    draw_lines([
        [-0.13887, 0.16228], [-0.1182, 0.15476],
        [-0.12846, 0.12656], [-0.14914, 0.13409],
    ], "XZ")
    time.sleep(2)

    step(15, TOTAL, "Extrude Guide2 non-insertion (240μm)")
    extrude(0.024, 0)
    body_target += 1
    wait_for_bodies(body_target)

    step(16, TOTAL, "Taper2 sketch (rotated trapezoid)")
    draw_lines([
        [-0.23464, -0.10083], [-0.32259, -0.22845],
        [-0.22862, -0.26265], [-0.21397, -0.10836],
    ], "XZ")
    time.sleep(2)

    step(17, TOTAL, "Extrude Taper2 (400μm)")
    extrude(0.04, 0)
    body_target += 1
    wait_for_bodies(body_target)

    # ── Phase 4: Axon Channel Path1 (axis-aligned, Z direction) ──────
    step(18, TOTAL, "Axon Path1a: W1→Seal1 (1390μm×75μm)")
    draw_box(0.139, 0.0075, 0.005, 0, 0.252, 0, "XZ")
    body_target += 1
    wait_for_bodies(body_target)

    step(19, TOTAL, "Axon Path1b: Seal1→W2 (1390μm×75μm)")
    draw_box(0.139, 0.0075, 0.005, 0, 0.098, 0, "XZ")
    body_target += 1
    wait_for_bodies(body_target)

    # ── Phase 5: Axon Channel Path2 (rotated, draw_lines) ────────────
    step(20, TOTAL, "Axon Path2a sketch: W2→Seal2 (rotated 75μm channel)")
    draw_lines([
        [-0.02785, 0.01413], [-0.15424, 0.06013],
        [-0.1568, 0.05308], [-0.03041, 0.00708],
    ], "XZ")
    time.sleep(2)

    step(21, TOTAL, "Extrude Path2a (50μm)")
    extrude(0.005, 0)
    body_target += 1
    wait_for_bodies(body_target)

    step(22, TOTAL, "Axon Path2b sketch: Seal2→W3 (rotated 75μm channel)")
    draw_lines([
        [-0.17209, 0.06663], [-0.29848, 0.11263],
        [-0.30104, 0.10558], [-0.17466, 0.05958],
    ], "XZ")
    time.sleep(2)

    step(23, TOTAL, "Extrude Path2b (50μm)")
    extrude(0.005, 0)
    body_target += 1
    wait_for_bodies(body_target)

    # ── Phase 6: Join ────────────────────────────────────────────────
    print(f"\nPre-join body count: {get_body_count()} (expected {body_target})")

    step(24, TOTAL, "join_all_bodies()")
    post("/join_all_bodies")
    time.sleep(3)  # join takes time
    wait_for_bodies(1, timeout=20)

    # ── Verification ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Build complete! Final verification:")
    bodies = get("/list_bodies")
    body_count = bodies.get("body_count", "?")
    print(f"Body count: {body_count} (expected: 1)")

    for b in bodies.get("bodies", []):
        bb = b.get("boundingBox", {})
        print(f"  {b.get('name')}: volume={b.get('volume')}")
        print(f"  boundingBox: {bb}")

    print("=" * 60)


if __name__ == "__main__":
    try:
        build()
    except requests.ConnectionError:
        print("ERROR: Cannot connect to Fusion 360 MCP server at port 5002.")
        print("Make sure Fusion 360 is running with the MCP add-in enabled.")
        sys.exit(1)
    except Exception as e:
        print(f"Build failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
