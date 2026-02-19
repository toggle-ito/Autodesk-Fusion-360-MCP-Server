"""
Fix Protrusion Embedding - Fusion 360 Standalone Script

Fixes the zero-thickness junction problem where protrusions (cylinders, rectangles)
sit on top of the base surface without any overlap. This causes delamination
during SLA/DLP 3D printing.

The fix changes identified extrude features from one-sided to two-sided extent,
making protrusions extend into the base body for a solid mechanical connection.

Usage:
    1. Open the target model in Fusion 360
    2. Run this script via Scripts and Add-Ins dialog (Shift+S)
    3. Review the identified protrusion features
    4. Confirm to apply the embedding fix

Author: Generated with Claude Code
"""
import adsk.core
import adsk.fusion
import traceback


def analyze_extrude_features(design):
    """
    Analyze timeline to find extrude features that are embedding candidates.

    Returns a list of dicts with feature info. A feature is considered an
    embedding candidate if it uses JoinFeatureOperation and has a one-sided
    distance extent (meaning it was extruded in one direction from a sketch plane).
    """
    timeline = design.timeline
    features = []

    for i in range(timeline.count):
        item = timeline.item(i)
        entity = item.entity

        if not isinstance(entity, adsk.fusion.ExtrudeFeature):
            continue

        ext = entity
        info = {
            "index": i,
            "name": ext.name,
            "timeline_name": item.name,
            "operation": ext.operation,
            "has_two_extents": ext.hasTwoExtents,
            "is_suppressed": item.isSuppressed,
        }

        # Get extent distance
        try:
            e1 = ext.extentOne
            if isinstance(e1, adsk.fusion.DistanceExtentDefinition):
                info["distance_cm"] = e1.distance.value
                info["extent_type"] = "Distance"
            else:
                info["extent_type"] = type(e1).__name__
        except Exception:
            info["extent_type"] = "Unknown"

        # Get sketch plane info
        try:
            profiles = ext.profile
            sketch = None
            if isinstance(profiles, adsk.fusion.Profile):
                sketch = profiles.parentSketch
            elif hasattr(profiles, 'item') and profiles.count > 0:
                sketch = profiles.item(0).parentSketch

            if sketch:
                info["sketch_name"] = sketch.name
                try:
                    ref = sketch.referencePlane
                    if hasattr(ref, 'geometry') and ref.geometry:
                        geo = ref.geometry
                        info["plane_origin"] = (
                            round(geo.origin.x, 4),
                            round(geo.origin.y, 4),
                            round(geo.origin.z, 4),
                        )
                except Exception:
                    pass
        except Exception:
            pass

        # Determine if this is an embedding candidate
        is_candidate = (
            ext.operation == adsk.fusion.FeatureOperations.JoinFeatureOperation
            and not ext.hasTwoExtents
            and info.get("extent_type") == "Distance"
            and not item.isSuppressed
        )
        info["is_embed_candidate"] = is_candidate

        features.append(info)

    return features


def embed_feature(ext_feature, embed_depth_cm):
    """
    Modify an extrude feature to use two-sided extent.

    Side one: keeps the original extrusion distance (positive direction).
    Side two: adds embed_depth_cm in the opposite direction (into the base).
    """
    e1 = ext_feature.extentOne
    if not isinstance(e1, adsk.fusion.DistanceExtentDefinition):
        return False

    current_distance = e1.distance.value

    dist_one = adsk.fusion.DistanceExtentDefinition.create(
        adsk.core.ValueInput.createByReal(current_distance))
    dist_two = adsk.fusion.DistanceExtentDefinition.create(
        adsk.core.ValueInput.createByReal(embed_depth_cm))

    taper_one = adsk.core.ValueInput.createByString("0 deg")
    taper_two = adsk.core.ValueInput.createByString("0 deg")

    return ext_feature.setTwoSidesExtent(dist_one, dist_two, taper_one, taper_two)


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)

        if design is None:
            ui.messageBox("No active design. Please open a model first.")
            return

        # Analyze the timeline
        features = analyze_extrude_features(design)
        candidates = [f for f in features if f["is_embed_candidate"]]

        if not candidates:
            # Show all extrude features for reference
            extrude_info = []
            for f in features:
                status = "two-sided" if f["has_two_extents"] else "one-sided"
                dist = f.get("distance_cm", "?")
                extrude_info.append(
                    f"  [{f['index']}] {f['name']} - {status}, dist={dist}cm"
                )
            msg = (
                "No embedding candidates found.\n\n"
                "Candidates must be Join-operation extrudes with one-sided distance extent.\n\n"
                f"All extrude features ({len(features)}):\n"
                + "\n".join(extrude_info)
            )
            ui.messageBox(msg)
            return

        # Build summary of candidates
        summary_lines = []
        for f in candidates:
            dist = f.get("distance_cm", "?")
            origin = f.get("plane_origin", "?")
            summary_lines.append(
                f"  [{f['index']}] {f['name']}: "
                f"distance={dist}cm, plane_origin={origin}"
            )

        msg = (
            f"Found {len(candidates)} embedding candidate(s):\n\n"
            + "\n".join(summary_lines)
            + "\n\nDefault embed depth: 0.05cm (0.5mm)\n\n"
            "Apply embedding fix to all candidates?"
        )

        result = ui.messageBox(
            msg,
            "Fix Protrusion Embedding",
            adsk.core.MessageBoxButtonTypes.YesNoButtonType,
            adsk.core.MessageBoxIconTypes.QuestionIconType,
        )

        if result != adsk.core.DialogResults.DialogYes:
            ui.messageBox("Operation cancelled.")
            return

        # Ask for embed depth
        ret_val, cancelled = ui.inputBox(
            "Enter embed depth in cm (e.g. 0.05 = 0.5mm, 0.1 = 1mm):",
            "Embed Depth",
            "0.05",
        )
        if cancelled:
            ui.messageBox("Operation cancelled.")
            return

        try:
            embed_depth = float(ret_val)
        except ValueError:
            ui.messageBox(f"Invalid number: {ret_val}")
            return

        if embed_depth <= 0:
            ui.messageBox("Embed depth must be positive.")
            return

        # Apply the fix
        timeline = design.timeline
        success_count = 0
        fail_count = 0
        results = []

        for f in candidates:
            idx = f["index"]
            entity = timeline.item(idx).entity

            if not isinstance(entity, adsk.fusion.ExtrudeFeature):
                results.append(f"  [{idx}] {f['name']}: SKIP (not an extrude)")
                fail_count += 1
                continue

            ok = embed_feature(entity, embed_depth)
            if ok:
                results.append(
                    f"  [{idx}] {f['name']}: OK "
                    f"(original={f.get('distance_cm', '?')}cm + embed={embed_depth}cm)"
                )
                success_count += 1
            else:
                results.append(f"  [{idx}] {f['name']}: FAILED")
                fail_count += 1

        ui.messageBox(
            f"Embedding complete!\n\n"
            f"Success: {success_count}, Failed: {fail_count}\n\n"
            + "\n".join(results)
            + "\n\nPlease verify the model visually and re-export STL."
        )

    except Exception:
        if ui:
            ui.messageBox(
                'Script failed:\n{}'.format(traceback.format_exc())
            )
