#!/usr/bin/env python3
"""
Build 70-degree triangle multi-unit axon device via Fusion 360 MCP HTTP API.

3 wells in a 70° triangle, 2 independent needle channels for axon cutting.
Fusion 360 add-in processes tasks asynchronously (queue polled every 200ms),
so this script polls list_bodies to confirm each step before proceeding.

All values in cm (1 cm = 10 mm, 100 μm = 0.01 cm).
XZ plane: draw_box(height→Z, width→X, depth→Y), draw_cylinder(x→X, y→Z).
"""

import io
import json
import sys
import time

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

URL = "http://127.0.0.1:5002"
HDR = {"Content-Type": "application/json"}


# ─── Low-level helpers ───────────────────────────────────────────────

def _post(path, data=None):
    r = requests.post(f"{URL}{path}", json.dumps(data or {}), HDR, timeout=120)
    msg = r.json().get("message", "")
    print(f"    api: {msg}")
    return r.json()


def _get(path):
    return requests.get(f"{URL}{path}", timeout=120).json()


def body_count():
    try:
        return _get("/list_bodies").get("body_count", 0)
    except Exception:
        return -1


def wait_bodies(n, timeout=20):
    """Block until body_count >= n."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        c = body_count()
        if c >= n:
            return c
        time.sleep(0.5)
    c = body_count()
    print(f"    ⚠ timeout: bodies={c}, expected>={n}")
    return c


# ─── Building blocks ─────────────────────────────────────────────────

def cylinder(r, h, x, z):
    """Draw cylinder on XZ plane. y-param maps to sketch Y (= -WorldZ)."""
    _post("/draw_cylinder", {"radius": r, "height": h, "x": x, "y": z, "z": 0, "plane": "XZ"})


def box(hz, wx, dy, cx, cz):
    """Draw box on XZ plane. height=Z-size, width=X-size, depth=Y-size, centered at (cx, cz)."""
    _post("/Box", {"height": hz, "width": wx, "depth": dy, "x": cx, "y": cz, "z": 0, "plane": "XZ"})


def lines_then_extrude(pts, ext_h, label=""):
    """Draw closed polyline then extrude. Waits for sketch processing between."""
    _post("/draw_lines", {"points": pts, "plane": "XZ"})
    time.sleep(2.5)  # ensure Fusion processes sketch before extrude
    _post("/extrude_last_sketch", {"value": ext_h, "taperangle": 0})


# ─── Main build ──────────────────────────────────────────────────────

def build():
    N = 0  # running expected body count

    # ── 1. Clear ─────────────────────────────────────────────────────
    print("[1/24] delete_everything")
    _post("/delete_everything")
    time.sleep(3)

    # ── 2-4. Wells ───────────────────────────────────────────────────
    print("[2/24] W1 (0, +3500)")
    cylinder(0.03, 0.045, 0, 0.35)
    N += 1; wait_bodies(N)

    print("[3/24] W2 (0, 0)")
    cylinder(0.03, 0.045, 0, 0)
    N += 1; wait_bodies(N)

    print("[4/24] W3 (-3289, +1197)")
    cylinder(0.03, 0.045, -0.3289, 0.1197)
    N += 1; wait_bodies(N)

    # ── 5-7. Needle1 boxes ───────────────────────────────────────────
    print("[5/24] Seal1  170×1500×170μm  @(0, 1750)")
    box(0.017, 0.15, 0.017, 0, 0.175)
    N += 1; wait_bodies(N)

    print("[6/24] Guide1-ins  220×1000×240μm  @(1250, 1750)")
    box(0.022, 0.1, 0.024, 0.125, 0.175)
    N += 1; wait_bodies(N)

    print("[7/24] Guide1-non  220×300×240μm  @(-900, 1750)")
    box(0.022, 0.03, 0.024, -0.09, 0.175)
    N += 1; wait_bodies(N)

    # ── 8-9. Taper1 (trapezoid sketch + extrude) ─────────────────────
    print("[8-9/24] Taper1 sketch+extrude  400μm")
    lines_then_extrude([
        [0.175, 0.186], [0.325, 0.225],
        [0.325, 0.125], [0.175, 0.164],
    ], 0.04)
    N += 1; wait_bodies(N)

    # ── 10-11. Seal2 ─────────────────────────────────────────────────
    print("[10-11/24] Seal2 sketch+extrude  170μm")
    lines_then_extrude([
        [-0.14679, 0.13323], [-0.13081, 0.12742],
        [-0.18211, -0.01353], [-0.19809, -0.00772],
    ], 0.017)
    N += 1; wait_bodies(N)

    # ── 12-13. Guide2 insertion ──────────────────────────────────────
    print("[12-13/24] Guide2-ins sketch+extrude  240μm")
    lines_then_extrude([
        [-0.20044, -0.00686], [-0.17976, -0.01439],
        [-0.21397, -0.10836], [-0.23464, -0.10083],
    ], 0.024)
    N += 1; wait_bodies(N)

    # ── 14-15. Guide2 non-insertion ──────────────────────────────────
    print("[14-15/24] Guide2-non sketch+extrude  240μm")
    lines_then_extrude([
        [-0.13887, 0.16228], [-0.1182, 0.15476],
        [-0.12846, 0.12656], [-0.14914, 0.13409],
    ], 0.024)
    N += 1; wait_bodies(N)

    # ── 16-17. Taper2 ────────────────────────────────────────────────
    print("[16-17/24] Taper2 sketch+extrude  400μm")
    lines_then_extrude([
        [-0.23464, -0.10083], [-0.32259, -0.22845],
        [-0.22862, -0.26265], [-0.21397, -0.10836],
    ], 0.04)
    N += 1; wait_bodies(N)

    # ── 18-19. Axon Path1 (axis-aligned boxes) ───────────────────────
    print("[18/24] Path1a W1→Seal1  1390×75×50μm  @(0, 2520)")
    box(0.139, 0.0075, 0.005, 0, 0.252)
    N += 1; wait_bodies(N)

    print("[19/24] Path1b Seal1→W2  1390×75×50μm  @(0, 980)")
    box(0.139, 0.0075, 0.005, 0, 0.098)
    N += 1; wait_bodies(N)

    # ── 20-23. Axon Path2 (rotated, sketch+extrude) ──────────────────
    print("[20-21/24] Path2a W2→Seal2  sketch+extrude 50μm")
    lines_then_extrude([
        [-0.02785, 0.01413], [-0.15424, 0.06013],
        [-0.1568, 0.05308], [-0.03041, 0.00708],
    ], 0.005)
    N += 1; wait_bodies(N)

    print("[22-23/24] Path2b Seal2→W3  sketch+extrude 50μm")
    lines_then_extrude([
        [-0.17209, 0.06663], [-0.29848, 0.11263],
        [-0.30104, 0.10558], [-0.17466, 0.05958],
    ], 0.005)
    N += 1; wait_bodies(N)

    # ── 24. Join ─────────────────────────────────────────────────────
    print(f"\n  Pre-join: {body_count()} bodies (expect {N})")
    print("[24/24] join_all_bodies")
    _post("/join_all_bodies")
    time.sleep(5)

    # ── Verify ───────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    result = _get("/list_bodies")
    bc = result.get("body_count", "?")
    print(f"Final body count: {bc} (expected 1)")
    for b in result.get("bodies", []):
        print(f"  {b.get('name')}: vol={b.get('volume')}")
        print(f"  bbox={b.get('boundingBox')}")
    print("=" * 50)


if __name__ == "__main__":
    try:
        build()
    except requests.ConnectionError:
        print("ERROR: Fusion 360 MCP not running on port 5002")
        sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
