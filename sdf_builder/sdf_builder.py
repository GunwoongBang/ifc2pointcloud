"""Lightweight IFC to SDF pipeline entrypoint.

This module converts an IFC file into an SDF world by exporting selected IFC
elements as OBJ meshes and wiring them as visual models in the generated world.
"""

from __future__ import annotations


import argparse
import importlib.util
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom

import ifcopenshell
import numpy as np


def _import_extract_mesh():
    try:
        from geometry import extract_mesh_from_shape as extractor
        return extractor
    except ModuleNotFoundError:
        # Fallback: load geometry.py from the same folder explicitly.
        geometry_path = Path(__file__).resolve().with_name("geometry.py")
        spec = importlib.util.spec_from_file_location(
            "sdf_builder_local_geometry",
            geometry_path,
        )
        if spec is None or spec.loader is None:
            raise ModuleNotFoundError("Could not load local geometry.py")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.extract_mesh_from_shape


# Allow running this file directly from sdf_builder/ while importing geometry.py
# from the repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

extract_mesh_from_shape = _import_extract_mesh()


SUPPORTED_TYPES = ["IfcWall", "IfcSlab"]


def _safe_name(text: str | None, fallback: str) -> str:
    if not text:
        return fallback
    cleaned = "".join(ch if ch.isalnum() or ch in (
        "_", "-") else "_" for ch in text)
    return cleaned[:120] if cleaned else fallback


def _pretty_xml(element: ET.Element) -> str:
    rough = ET.tostring(element, encoding="utf-8")
    parsed = minidom.parseString(rough)
    return parsed.toprettyxml(indent="  ")


def _write_obj(mesh_path: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    """Write triangle mesh vertices/faces to OBJ format."""
    lines = []
    for v in vertices:
        lines.append(f"v {v[0]:.9f} {v[1]:.9f} {v[2]:.9f}")

    # OBJ uses 1-based indexing.
    for f in faces:
        lines.append(f"f {int(f[0]) + 1} {int(f[1]) + 1} {int(f[2]) + 1}")

    mesh_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def convert_ifc_to_sdf(ifc_path: str, output_dir: str = "world") -> dict:
    """Convert IFC walls/slabs into an SDF world and OBJ meshes.

    Args:
            ifc_path: Path to IFC model.
            output_dir: Directory for SDF and mesh outputs.

    Returns:
            Summary dictionary with output paths and export counts.
    """
    ifc_file = Path(ifc_path)
    model_name = ifc_file.stem

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sdf_path = out_dir / f"{model_name}.sdf"
    mesh_dir = out_dir / f"{model_name}_meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    model = ifcopenshell.open(str(ifc_file))

    sdf = ET.Element("sdf", version="1.6")
    world = ET.SubElement(sdf, "world", name=f"{model_name}_world")

    # Ensure there is always a physical ground in Gazebo.
    include_ground = ET.SubElement(world, "include")
    ET.SubElement(include_ground, "uri").text = "model://ground_plane"

    include_sun = ET.SubElement(world, "include")
    ET.SubElement(include_sun, "uri").text = "model://sun"

    total_exported = 0
    per_type: dict[str, int] = {}

    for ifc_type in SUPPORTED_TYPES:
        elements = model.by_type(ifc_type)
        if not elements:
            continue

        exported_count = 0
        for element in elements:
            try:
                vertices, faces, _ = extract_mesh_from_shape(element)
            except Exception:
                continue

            if vertices.size == 0 or faces.size == 0:
                continue
            if len(vertices) < 3 or len(faces) < 1:
                continue

            global_id = getattr(element, "GlobalId", "unknown")
            model_id = _safe_name(global_id, f"{ifc_type}_{exported_count}")
            model_name_for_sdf = f"{ifc_type}_{model_id}"

            mesh_name = f"{model_name_for_sdf}.obj"
            mesh_path = mesh_dir / mesh_name
            _write_obj(mesh_path, vertices, faces)
            mesh_uri = mesh_path.resolve().as_uri()

            model_node = ET.SubElement(world, "model", name=model_name_for_sdf)
            ET.SubElement(model_node, "static").text = "true"
            ET.SubElement(model_node, "pose").text = "0 0 0 0 0 0"

            link = ET.SubElement(model_node, "link", name="link")

            # Collision is required for Gazebo physics. Without this the robot
            # can pass through IFC geometry and appear to fall underground.
            collision = ET.SubElement(link, "collision", name="collision")
            collision_geometry = ET.SubElement(collision, "geometry")
            collision_mesh = ET.SubElement(collision_geometry, "mesh")
            ET.SubElement(collision_mesh, "uri").text = mesh_uri
            ET.SubElement(collision_mesh, "scale").text = "1 1 1"

            visual = ET.SubElement(link, "visual", name="visual")
            geometry = ET.SubElement(visual, "geometry")
            mesh = ET.SubElement(geometry, "mesh")
            ET.SubElement(mesh, "uri").text = mesh_uri
            ET.SubElement(mesh, "scale").text = "1 1 1"

            material = ET.SubElement(visual, "material")
            if ifc_type == "IfcWall":
                ET.SubElement(material, "ambient").text = "0.70 0.70 0.70 1"
                ET.SubElement(material, "diffuse").text = "0.75 0.75 0.75 1"
            else:
                ET.SubElement(material, "ambient").text = "0.60 0.60 0.65 1"
                ET.SubElement(material, "diffuse").text = "0.65 0.65 0.70 1"

            exported_count += 1
            total_exported += 1

        if exported_count:
            per_type[ifc_type] = exported_count

    sdf_path.write_text(_pretty_xml(sdf), encoding="utf-8")

    return {
        "ifc": str(ifc_file),
        "sdf": str(sdf_path),
        "mesh_dir": str(mesh_dir),
        "total_exported": total_exported,
        "per_type": per_type,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert IFC to SDF world")
    parser.add_argument("--ifc", required=True, help="Path to IFC file")
    parser.add_argument("--output-dir", default="world",
                        help="Output directory")
    args = parser.parse_args()

    stats = convert_ifc_to_sdf(args.ifc, output_dir=args.output_dir)
    print("=== IFC to SDF conversion complete ===")
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
