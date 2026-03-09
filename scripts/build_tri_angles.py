#!/usr/bin/env python3
"""
3-angle (70°/90°/110°) × 2 = 6 axon-severing device tray.

v5 spec: sprout-type Path2, embed 50μm, rim with air gaps.
XZ plane: sketch Y = -WorldZ, extrusion = +WorldY.
"""

import io
import json
import math
import sys
import time

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Config ───────────────────────────────────────────────────────────
URL = "http://127.0.0.1:5002"
HDR = {"Content-Type": "application/json"}

N_COLS = 3
N_ROWS = 2
ANGLES = [70, 90, 110]  # degrees per column

GAP = 0.08        # 0.8mm between devices
RIM_W = 0.2       # 2mm rim
BASE_THICK = 0.5  # 5mm base
EMBED = 0.005     # 50μm embed
RIM_PAD = 0.04    # 400μm clearance between features and rim inner wall

# Heights (造形高 = embed + effective protrusion)
WELL_H = 0.055    # 550μm (500μm effective)
RIM_H = 0.045     # 450μm (400μm effective)
TAPER_H = 0.035   # 350μm (300μm effective)
GUIDE_H = 0.035   # 350μm
SEAL_H = 0.022    # 220μm (170μm effective)
PATH_H = 0.022    # 220μm

# Well
WELL_R = 0.03     # 300μm radius

# Device geometry
W1_Z = 0.35       # W1 sketch Y
W2_Z = 0.0        # W2 sketch Y
BRANCH_Z = WELL_R + 0.02  # 0.05 = branch point on Path1, 200μm from W2 edge
D = 0.35          # Path2 length = 3500μm
N1_Z = 0.175      # Needle1 center (midpoint W1–W2)

# Needle dimensions
SEAL_LEN = 0.15   # 1.5mm along needle axis
SEAL_HW = 0.0085  # half-width 85μm (170μm total)
GUIDE_INS_LEN = 0.10
GUIDE_NOINS_LEN = 0.03
GUIDE_HW = 0.011  # half-width 110μm (220μm total)
TAPER_LEN = 0.15
TAPER_HW_NARROW = 0.011
TAPER_HW_WIDE = 0.05

# Path width
PATH_HW = 0.00375  # half-width 37.5μm (75μm total)

# Air gap dimensions
AIR_GAP_LR = 0.25  # 2.5mm for left/right
AIR_GAP_TB = 0.2   # 2.0mm for top/bottom


# ── HTTP helpers ─────────────────────────────────────────────────────

def _post(p, d=None, timeout=30):
    try:
        r = requests.post(f"{URL}{p}", json.dumps(d or {}), HDR, timeout=timeout)
        return r.json()
    except requests.exceptions.ReadTimeout:
        # Server accepted request but processing is slow; continue
        print(f"  (timeout on {p}, continuing)")
        return {}

def _get(p):
    return requests.get(f"{URL}{p}", timeout=30).json()

def bodies():
    try: return _get("/list_bodies").get("body_count", 0)
    except: return -1

def wait(n, t=30):
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


# ── Geometry helpers ─────────────────────────────────────────────────

def rotated_rect(cx, cz, dx, dz, px, pz, hw, start_l, end_l):
    """4 vertices of a rotated rectangle.
    (dx,dz) = length direction, (px,pz) = width direction,
    hw = half-width, start_l/end_l = distance along length from (cx,cz).
    """
    sx, sz = cx + dx*start_l, cz + dz*start_l
    ex, ez = cx + dx*end_l,   cz + dz*end_l
    return [
        [sx + px*hw, sz + pz*hw],
        [ex + px*hw, ez + pz*hw],
        [ex - px*hw, ez - pz*hw],
        [sx - px*hw, sz - pz*hw],
    ]

def rotated_trap(cx, cz, dx, dz, px, pz, hw_s, hw_e, start_l, end_l):
    """4 vertices of a rotated trapezoid.
    hw_s = half-width at start, hw_e = half-width at end.
    """
    sx, sz = cx + dx*start_l, cz + dz*start_l
    ex, ez = cx + dx*end_l,   cz + dz*end_l
    return [
        [sx + px*hw_s, sz + pz*hw_s],
        [ex + px*hw_e, ez + pz*hw_e],
        [ex - px*hw_e, ez - pz*hw_e],
        [sx - px*hw_s, sz - pz*hw_s],
    ]


# ── Device extent ────────────────────────────────────────────────────

def compute_w3(angle_deg):
    theta = math.radians(angle_deg)
    return -D * math.sin(theta), BRANCH_Z + D * math.cos(theta)

def device_extent(angle_deg):
    """Bounding box [x_min, x_max, z_min, z_max] of one device at origin."""
    w3x, w3z = compute_w3(angle_deg)
    theta = math.radians(angle_deg)
    sin_t, cos_t = math.sin(theta), math.cos(theta)
    n2x, n2z = -cos_t, -sin_t
    p2x, p2z = -sin_t, cos_t

    mid_x = 0.5 * w3x
    mid_z = 0.5 * (BRANCH_Z + w3z)

    xs, zs = [], []

    # Wells
    xs.extend([-WELL_R, WELL_R, w3x - WELL_R, w3x + WELL_R])
    zs.extend([W1_Z + WELL_R, W2_Z - WELL_R, w3z - WELL_R, w3z + WELL_R])

    # Taper1 right end
    xs.append(0.325)
    zs.extend([N1_Z - TAPER_HW_WIDE, N1_Z + TAPER_HW_WIDE])

    # Guide1 non-insertion left end
    xs.append(-0.105)

    # Taper2 outer end (0.325 along N2 from midpoint)
    t2x = mid_x + n2x * 0.325
    t2z = mid_z + n2z * 0.325
    xs.extend([t2x + p2x*0.05, t2x - p2x*0.05])
    zs.extend([t2z + p2z*0.05, t2z - p2z*0.05])

    # Guide2 non-insertion end (-0.105 along N2)
    g2x = mid_x - n2x * 0.105
    g2z = mid_z - n2z * 0.105
    xs.extend([g2x + p2x*0.011, g2x - p2x*0.011])
    zs.extend([g2z + p2z*0.011, g2z - p2z*0.011])

    return min(xs), max(xs), min(zs), max(zs)


# ── Single device ───────────────────────────────────────────────────

def device(xo, syo, angle_deg, n):
    """Build one device at offset (xo, syo) with given angle."""
    theta = math.radians(angle_deg)
    sin_t, cos_t = math.sin(theta), math.cos(theta)

    w3x, w3z = compute_w3(angle_deg)
    p2x, p2z = -sin_t, cos_t      # Path2 direction
    n2x, n2z = -cos_t, -sin_t     # N2 outward (away from W1)

    mid_x = 0.5 * w3x
    mid_z = 0.5 * (BRANCH_Z + w3z)

    print(f"  θ={angle_deg}°, W3=({w3x:.4f}, {w3z:.4f})")

    # ── Wells ──
    cyl(WELL_R, WELL_H, 0+xo, W1_Z+syo);  n[0]+=1; wait(n[0])
    cyl(WELL_R, WELL_H, 0+xo, W2_Z+syo);  n[0]+=1; wait(n[0])
    cyl(WELL_R, WELL_H, w3x+xo, w3z+syo); n[0]+=1; wait(n[0])

    # ── Needle1 (horizontal, common to all angles) ──
    # Seal1
    box(SEAL_HW*2, SEAL_LEN, SEAL_H, 0+xo, N1_Z+syo)
    n[0]+=1; wait(n[0])
    # Guide1 insertion (right)
    box(GUIDE_HW*2, GUIDE_INS_LEN, GUIDE_H, 0.125+xo, N1_Z+syo)
    n[0]+=1; wait(n[0])
    # Guide1 non-insertion (left)
    box(GUIDE_HW*2, GUIDE_NOINS_LEN, GUIDE_H, -0.09+xo, N1_Z+syo)
    n[0]+=1; wait(n[0])

    # Taper1 (trapezoid, rightward)
    t1 = [
        [0.175, N1_Z + GUIDE_HW],
        [0.325, N1_Z + TAPER_HW_WIDE],
        [0.325, N1_Z - TAPER_HW_WIDE],
        [0.175, N1_Z - GUIDE_HW],
    ]
    poly(sp(t1, xo, syo), TAPER_H)
    n[0]+=1; wait(n[0])

    # ── Needle2 (angle-dependent, rotated) ──
    # Seal2: length 0.15 along N2 (±0.075), width 0.017 along P2 (±0.0085)
    seal2 = rotated_rect(mid_x, mid_z, n2x, n2z, p2x, p2z, SEAL_HW, -0.075, 0.075)
    poly(sp(seal2, xo, syo), SEAL_H)
    n[0]+=1; wait(n[0])

    # Guide2 insertion (outward along N2: 0.075 → 0.175)
    g2i = rotated_rect(mid_x, mid_z, n2x, n2z, p2x, p2z, GUIDE_HW, 0.075, 0.175)
    poly(sp(g2i, xo, syo), GUIDE_H)
    n[0]+=1; wait(n[0])

    # Guide2 non-insertion (inward along N2: -0.105 → -0.075)
    g2n = rotated_rect(mid_x, mid_z, n2x, n2z, p2x, p2z, GUIDE_HW, -0.105, -0.075)
    poly(sp(g2n, xo, syo), GUIDE_H)
    n[0]+=1; wait(n[0])

    # Taper2 (trapezoid, outward along N2: 0.175 → 0.325)
    t2 = rotated_trap(mid_x, mid_z, n2x, n2z, p2x, p2z,
                       TAPER_HW_NARROW, TAPER_HW_WIDE, 0.175, 0.325)
    poly(sp(t2, xo, syo), TAPER_H)
    n[0]+=1; wait(n[0])

    # ── Path1 (vertical, two segments) ──
    # Path1a: W1 bottom edge → Seal1 top edge
    p1a_top = W1_Z - WELL_R          # 0.32
    p1a_bot = N1_Z + SEAL_HW         # 0.1835
    p1a_len = p1a_top - p1a_bot
    p1a_ctr = (p1a_top + p1a_bot) / 2
    box(p1a_len, PATH_HW*2, PATH_H, 0+xo, p1a_ctr+syo)
    n[0]+=1; wait(n[0])

    # Path1b: Seal1 bottom edge → W2 well top edge
    p1b_top = N1_Z - SEAL_HW         # 0.1665
    p1b_bot = W2_Z + WELL_R          # 0.03 (W2 well top edge)
    p1b_len = p1b_top - p1b_bot
    p1b_ctr = (p1b_top + p1b_bot) / 2
    box(p1b_len, PATH_HW*2, PATH_H, 0+xo, p1b_ctr+syo)
    n[0]+=1; wait(n[0])

    # ── Path2 (rotated, two segments) ──
    # Path2 branches from Path1 at BRANCH_Z (200μm from W2 edge)
    # Origin = (0, BRANCH_Z), midpoint at D/2 = 0.175

    # Path2a: branch point → near edge of Seal2
    p2a_start = 0.0  # starts right at branch point (overlaps Path1 for clean join)
    p2a_end = 0.175 - SEAL_HW  # 0.1665
    p2a = rotated_rect(0, BRANCH_Z, p2x, p2z, n2x, n2z, PATH_HW, p2a_start, p2a_end)
    poly(sp(p2a, xo, syo), PATH_H)
    n[0]+=1; wait(n[0])

    # Path2b: far edge of Seal2 → W3 edge
    p2b_start = 0.175 + SEAL_HW  # 0.1835
    p2b_end = D - WELL_R         # 0.32
    p2b = rotated_rect(0, BRANCH_Z, p2x, p2z, n2x, n2z, PATH_HW, p2b_start, p2b_end)
    poly(sp(p2b, xo, syo), PATH_H)
    n[0]+=1; wait(n[0])


# ── Rim builder helpers ──────────────────────────────────────────────

def build_x_rim_segments(z_center, x_start, x_end, gap_centers, gap_w, n):
    """Build rim segments along X, splitting at air gaps."""
    gaps = sorted(gap_centers)
    segs = []
    cur = x_start
    for gc in gaps:
        gs, ge = gc - gap_w/2, gc + gap_w/2
        if gs > cur + 0.001:
            segs.append((cur, gs))
        cur = ge
    if cur < x_end - 0.001:
        segs.append((cur, x_end))
    for sx, ex in segs:
        w = ex - sx
        cx = (sx + ex) / 2
        box(RIM_W, w, RIM_H, cx, z_center)
        n[0] += 1; wait(n[0])

def build_z_rim_segments(x_center, z_start, z_end, gap_centers, gap_w, n):
    """Build rim segments along Z, splitting at air gaps."""
    gaps = sorted(gap_centers)
    segs = []
    cur = z_start
    for gc in gaps:
        gs, ge = gc - gap_w/2, gc + gap_w/2
        if gs > cur + 0.001:
            segs.append((cur, gs))
        cur = ge
    if cur < z_end - 0.001:
        segs.append((cur, z_end))
    for sz, ez in segs:
        h = ez - sz
        cz = (sz + ez) / 2
        box(h, RIM_W, RIM_H, x_center, cz)
        n[0] += 1; wait(n[0])


# ── Main ─────────────────────────────────────────────────────────────

def build():
    # Compute device extents per angle
    extents = [device_extent(a) for a in ANGLES]
    for i, (a, ext) in enumerate(zip(ANGLES, extents)):
        xmin, xmax, zmin, zmax = ext
        print(f"  {a}°: X[{xmin:.4f}, {xmax:.4f}] Z[{zmin:.4f}, {zmax:.4f}]"
              f"  span {(xmax-xmin)*10:.2f}×{(zmax-zmin)*10:.2f} mm")

    # Uniform cell = global bounding box across all angles
    dev_x_min = min(e[0] for e in extents)
    dev_x_max = max(e[1] for e in extents)
    dev_z_min = min(e[2] for e in extents)
    dev_z_max = max(e[3] for e in extents)

    x_span = dev_x_max - dev_x_min
    z_span = dev_z_max - dev_z_min
    x_step = x_span + GAP
    z_step = z_span + GAP

    # Base plate bounds
    bp_x_min = dev_x_min - RIM_PAD - RIM_W
    bp_x_max = dev_x_max + (N_COLS - 1) * x_step + RIM_PAD + RIM_W
    bp_z_min = dev_z_min - RIM_PAD - RIM_W
    bp_z_max = dev_z_max + (N_ROWS - 1) * z_step + RIM_PAD + RIM_W

    bp_wx = bp_x_max - bp_x_min
    bp_hz = bp_z_max - bp_z_min
    bp_cx = (bp_x_min + bp_x_max) / 2
    bp_cz = (bp_z_min + bp_z_max) / 2

    print(f"\n=== 6 devices ({N_COLS}x{N_ROWS}), angles {ANGLES} ===")
    print(f"Cell: {x_span*10:.2f} x {z_span*10:.2f} mm")
    print(f"Tray: {bp_wx*10:.2f} x {bp_hz*10:.2f} mm")
    print(f"Printer limit: 30 x 20 mm")
    if bp_wx*10 > 30 or bp_hz*10 > 20:
        print("WARNING: Exceeds printer limit!")
    print()

    n = [0]

    # ── Step 0: Clear ──
    print("delete_everything")
    _post("/delete_everything")
    time.sleep(8)

    # ── Step 1: Base plate ──
    print(f"Base plate {bp_wx*10:.1f}x{bp_hz*10:.1f} mm")
    box(bp_hz, bp_wx, BASE_THICK + EMBED, bp_cx, bp_cz, z_off=-BASE_THICK)
    n[0] += 1; wait(n[0])

    # ── Step 2: Rim with air gaps ──
    print("Building rim...")

    inner_left  = bp_x_min + RIM_W
    inner_right = bp_x_max - RIM_W
    inner_bot   = bp_z_min + RIM_W   # = dev_z_min
    inner_top   = bp_z_max - RIM_W   # = dev_z_max + (N_ROWS-1)*z_step
    inner_h = inner_top - inner_bot

    # Column boundary centers (for top/bottom air gaps)
    col_gap_xs = [dev_x_max + GAP/2 + i * x_step for i in range(N_COLS - 1)]

    # Left/right air gaps at ~1/3 and ~2/3 of inner height
    lr_gap_zs = [
        inner_bot + inner_h * 0.30,
        inner_bot + inner_h * 0.70,
    ]

    # Top rim (full width including corners)
    top_rim_cz = bp_z_max - RIM_W / 2
    build_x_rim_segments(top_rim_cz, bp_x_min, bp_x_max, col_gap_xs, AIR_GAP_TB, n)

    # Bottom rim
    bot_rim_cz = bp_z_min + RIM_W / 2
    build_x_rim_segments(bot_rim_cz, bp_x_min, bp_x_max, col_gap_xs, AIR_GAP_TB, n)

    # Left rim (excluding corners)
    left_rim_cx = bp_x_min + RIM_W / 2
    build_z_rim_segments(left_rim_cx, inner_bot, inner_top, lr_gap_zs, AIR_GAP_LR, n)

    # Right rim (excluding corners)
    right_rim_cx = bp_x_max - RIM_W / 2
    build_z_rim_segments(right_rim_cx, inner_bot, inner_top, lr_gap_zs, AIR_GAP_LR, n)

    # ── Step 3: 6 devices ──
    total = N_COLS * N_ROWS
    for row in range(N_ROWS):
        for col in range(N_COLS):
            idx = row * N_COLS + col + 1
            xo = col * x_step
            syo = row * z_step
            angle = ANGLES[col]
            print(f"\n--- Device {idx}/{total} (col={col} row={row}, {angle}°) ---")
            device(xo, syo, angle, n)

    # ── Step 4: Join all bodies (batch) ──
    bc = bodies()
    print(f"\nBodies before join: {bc}")
    if bc > 1:
        print("Joining all bodies (batch mode)...")
        _post("/join_all_bodies", timeout=120)
        time.sleep(30)
        print(f"Bodies after join: {bodies()} (expect 1)")
    print("Done!")


if __name__ == "__main__":
    try:
        build()
    except requests.ConnectionError:
        print("ERROR: Fusion 360 MCP not running on " + URL)
        sys.exit(1)
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
