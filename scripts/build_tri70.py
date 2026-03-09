#!/usr/bin/env python3
"""
70° triangle axon device — 6 units (3x2) on base plate.

30x20mm printer limit → 3 cols × 2 rows = 6 devices on 24.5 × 15.9 mm base.
Device features embed 50μm into the base plate for solid 3D print adhesion.

XZ plane: sketch Y = -WorldZ, extrusion = +WorldY.
"""

import io
import json
import sys
import time

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Config ───────────────────────────────────────────────────────────
N_COLS = 3
N_ROWS = 2
GAP = 0.1              # 1mm gap between devices
BORDER = 0.1            # 1mm border
BASE_THICK = 0.05       # 500μm base below Y=0
EMBED = 0.005           # 50μm — features dig into base (base extends above Y=0)

URL = "http://127.0.0.1:5002"
HDR = {"Content-Type": "application/json"}

# Single device extent
DEV_X_MIN, DEV_X_MAX = -0.3589, 0.3250
DEV_SY_MIN, DEV_SY_MAX = -0.2626, 0.38   # sketch Y range
X_STEP = (DEV_X_MAX - DEV_X_MIN) + GAP    # 0.7839
SY_STEP = (DEV_SY_MAX - DEV_SY_MIN) + GAP  # 0.7426


def _post(p, d=None):
    r = requests.post(f"{URL}{p}", json.dumps(d or {}), HDR, timeout=120)
    return r.json()

def _get(p):
    return requests.get(f"{URL}{p}", timeout=120).json()

def bodies():
    try: return _get("/list_bodies").get("body_count", 0)
    except: return -1

def wait(n, t=20):
    t0 = time.time()
    while time.time() - t0 < t:
        if bodies() >= n: return
        time.sleep(0.5)


# ── Primitives ───────────────────────────────────────────────────────

def cyl(r, h, x, sy):
    _post("/draw_cylinder", {"radius": r, "height": h, "x": x, "y": sy, "z": 0, "plane": "XZ"})

def box(hz, wx, dy, cx, csy, z_off=0):
    _post("/Box", {"height": hz, "width": wx, "depth": dy, "x": cx, "y": csy, "z": z_off, "plane": "XZ"})

def poly(pts, h):
    _post("/draw_lines", {"points": pts, "plane": "XZ"})
    time.sleep(2.5)
    _post("/extrude_last_sketch", {"value": h, "taperangle": 0})

def sp(pts, xo, syo):
    """Shift points by (xo, syo)."""
    return [[p[0]+xo, p[1]+syo] for p in pts]


# ── Single device ───────────────────────────────────────────────────

def device(xo, syo, n):
    """Build one device at offset (xo=X, syo=sketchY). n[0]=body counter."""

    # Wells
    cyl(0.03, 0.045, 0+xo, 0.35+syo);        n[0]+=1; wait(n[0])
    cyl(0.03, 0.045, 0+xo, 0+syo);            n[0]+=1; wait(n[0])
    cyl(0.03, 0.045, -0.3289+xo, 0.1197+syo); n[0]+=1; wait(n[0])

    # Needle1
    box(0.017, 0.15, 0.017, 0+xo, 0.175+syo);      n[0]+=1; wait(n[0])
    box(0.022, 0.1, 0.024, 0.125+xo, 0.175+syo);    n[0]+=1; wait(n[0])
    box(0.022, 0.03, 0.024, -0.09+xo, 0.175+syo);   n[0]+=1; wait(n[0])

    poly(sp([[0.175,0.186],[0.325,0.225],[0.325,0.125],[0.175,0.164]], xo, syo), 0.04)
    n[0]+=1; wait(n[0])

    # Needle2
    poly(sp([[-0.14679,0.13323],[-0.13081,0.12742],[-0.18211,-0.01353],[-0.19809,-0.00772]], xo, syo), 0.017)
    n[0]+=1; wait(n[0])

    poly(sp([[-0.20044,-0.00686],[-0.17976,-0.01439],[-0.21397,-0.10836],[-0.23464,-0.10083]], xo, syo), 0.024)
    n[0]+=1; wait(n[0])

    poly(sp([[-0.13887,0.16228],[-0.1182,0.15476],[-0.12846,0.12656],[-0.14914,0.13409]], xo, syo), 0.024)
    n[0]+=1; wait(n[0])

    poly(sp([[-0.23464,-0.10083],[-0.32259,-0.22845],[-0.22862,-0.26265],[-0.21397,-0.10836]], xo, syo), 0.04)
    n[0]+=1; wait(n[0])

    # Path1 (height = EMBED + 50μm so it protrudes above base)
    box(0.139, 0.0075, 0.01, 0+xo, 0.252+syo); n[0]+=1; wait(n[0])
    box(0.139, 0.0075, 0.01, 0+xo, 0.098+syo); n[0]+=1; wait(n[0])

    # Path2 (height = EMBED + 50μm so it protrudes above base)
    poly(sp([[-0.02785,0.01413],[-0.15424,0.06013],[-0.1568,0.05308],[-0.03041,0.00708]], xo, syo), 0.01)
    n[0]+=1; wait(n[0])

    poly(sp([[-0.17209,0.06663],[-0.29848,0.11263],[-0.30104,0.10558],[-0.17466,0.05958]], xo, syo), 0.01)
    n[0]+=1; wait(n[0])


# ── Main ─────────────────────────────────────────────────────────────

def build():
    total = N_COLS * N_ROWS

    # Base plate extents
    bp_x_min = DEV_X_MIN - BORDER
    bp_x_max = DEV_X_MAX + (N_COLS - 1) * X_STEP + BORDER
    bp_sy_min = DEV_SY_MIN - BORDER
    bp_sy_max = DEV_SY_MAX + (N_ROWS - 1) * SY_STEP + BORDER

    bp_wx = bp_x_max - bp_x_min
    bp_hz = bp_sy_max - bp_sy_min
    bp_cx = (bp_x_min + bp_x_max) / 2
    bp_csy = (bp_sy_min + bp_sy_max) / 2

    print(f"=== {total} devices ({N_COLS}x{N_ROWS}) ===")
    print(f"Base: {bp_wx*10:.1f} x {bp_hz*10:.1f} mm, thick {BASE_THICK*10000:.0f}+{EMBED*10000:.0f}μm embed")
    print(f"Printer limit: 30x20 mm")
    print()

    n = [0]

    # 1. Clear
    print("delete_everything")
    _post("/delete_everything")
    time.sleep(3)

    # 2. Base plate (Y = -BASE_THICK to +EMBED, features dig in)
    print(f"Base plate {bp_wx*10:.1f}x{bp_hz*10:.1f}mm")
    box(bp_hz, bp_wx, BASE_THICK + EMBED, bp_cx, bp_csy, z_off=-BASE_THICK)
    n[0] += 1; wait(n[0])

    # 3. Devices
    for row in range(N_ROWS):
        for col in range(N_COLS):
            idx = row * N_COLS + col + 1
            xo = col * X_STEP
            syo = row * SY_STEP
            print(f"\n--- Device {idx}/{total} (col={col} row={row}) ---")
            device(xo, syo, n)

    print(f"\nDone. {bodies()} bodies (expect {n[0]}).")


if __name__ == "__main__":
    try:
        build()
    except requests.ConnectionError:
        print("ERROR: Fusion 360 MCP not running")
        sys.exit(1)
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
