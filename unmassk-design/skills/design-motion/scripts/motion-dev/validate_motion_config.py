#!/usr/bin/env python3
"""
Motion.dev Animation Configuration Validator

Validates Motion.dev animation configurations against JSON schema.

Usage:
    python validate_motion_config.py config.json
    python validate_motion_config.py --all examples/

Requirements:
    pip install jsonschema
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def load_schema() -> Dict:
    """Load JSON schema from schema directory"""
    # scripts/motion-dev/validate_motion_config.py -> skill root is two levels up
    schema_path = Path(__file__).parent.parent.parent / "schema" / "motion-config.schema.json"

    if not schema_path.exists():
        print(f"❌ Schema not found: {schema_path}")
        sys.exit(1)

    with open(schema_path) as f:
        return json.load(f)


def validate_config(config_path: Path, schema: Dict) -> Tuple[bool, List[str]]:
    """
    Validate animation config against schema

    Returns:
        (is_valid, warnings) tuple
    """
    try:
        import jsonschema
    except ImportError:
        print("❌ jsonschema not installed. Run: pip install jsonschema")
        sys.exit(1)

    # Load config
    try:
        with open(config_path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    except Exception as e:
        return False, [f"Error reading file: {e}"]

    # Validate against schema
    warnings = []

    try:
        jsonschema.validate(instance=config, schema=schema)
    except jsonschema.ValidationError as e:
        return False, [f"Schema validation failed: {e.message}"]

    # Additional performance checks
    if "performance" in config:
        perf = config["performance"]

        if perf.get("fps", 60) < 60:
            warnings.append(f"⚠️  FPS ({perf['fps']}) below 60 (recommended minimum)")

        if perf.get("bundleSize", 0) > 51200:
            warnings.append(f"⚠️  Bundle size ({perf['bundleSize']} bytes) exceeds 50KB")

    # Accessibility checks
    if "accessibility" in config:
        acc = config["accessibility"]

        if not acc.get("reducedMotion"):
            warnings.append("⚠️  No reduced motion support (accessibility concern)")

        if not acc.get("keyboardNav"):
            warnings.append("⚠️  Not keyboard navigable (accessibility concern)")

        if not acc.get("focusVisible"):
            warnings.append("⚠️  No visible focus indicator (accessibility concern)")
    else:
        warnings.append("⚠️  Missing accessibility configuration")

    # GPU acceleration check
    if config.get("performance", {}).get("gpuAccelerated") is False:
        warnings.append("⚠️  Not GPU-accelerated (may cause performance issues)")

    return True, warnings


def main():
    """Main validation function"""
    if len(sys.argv) < 2:
        print("Usage: python validate_motion_config.py <config.json>")
        print("       python validate_motion_config.py --all <directory>")
        sys.exit(1)

    schema = load_schema()

    # Handle --all flag
    if sys.argv[1] == "--all":
        if len(sys.argv) < 3:
            print("❌ Please specify directory for --all")
            sys.exit(1)

        directory = Path(sys.argv[2])
        if not directory.is_dir():
            print(f"❌ Not a directory: {directory}")
            sys.exit(1)

        config_files = list(directory.glob("**/*.json"))

        if not config_files:
            print(f"❌ No JSON files found in {directory}")
            sys.exit(1)

        print(f"📁 Validating {len(config_files)} config files...\n")

        total_valid = 0
        total_invalid = 0

        for config_path in config_files:
            is_valid, warnings = validate_config(config_path, schema)

            if is_valid:
                total_valid += 1
                status = "✅"
            else:
                total_invalid += 1
                status = "❌"

            print(f"{status} {config_path.name}")

            for warning in warnings:
                print(f"   {warning}")

        print(f"\n📊 Summary: {total_valid} valid, {total_invalid} invalid")
        sys.exit(0 if total_invalid == 0 else 1)

    # Single file validation
    config_path = Path(sys.argv[1])

    if not config_path.exists():
        print(f"❌ File not found: {config_path}")
        sys.exit(1)

    is_valid, warnings = validate_config(config_path, schema)

    if is_valid:
        print(f"✅ Configuration valid: {config_path}")

        if warnings:
            print("\n⚠️  Warnings:")
            for warning in warnings:
                print(f"   {warning}")
        else:
            print("   No warnings - excellent configuration!")

        sys.exit(0)
    else:
        print(f"❌ Configuration invalid: {config_path}")
        for error in warnings:
            print(f"   {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
