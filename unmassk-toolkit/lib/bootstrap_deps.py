"""
bootstrap_deps -- Dependency-manifest, monorepo, CI, and existing-install
detection for bin/git-memory-bootstrap.py.

Split out of git-memory-bootstrap.py (was 953 LOC). This module owns the
"what ecosystem/framework/monorepo/CI signals can we read out of specific
known files" concern, as opposed to bootstrap_tree.py (generic directory
walk + filename matching) or bootstrap_commits.py (git history).
"""

import json
import os
import re
from typing import Any

from git_helpers import open_no_follow_symlink, verify_path_within_project
from parsing import sanitize_trailer_value


def scan_package_json(root: str) -> dict[str, Any] | None:
    """Extract stack info from package.json (frameworks, deps, monorepo signals).

    Returns:
        Dict with detected info, or None if package.json is missing or invalid.
    """
    pkg_path = os.path.join(root, "package.json")
    if not os.path.isfile(pkg_path):
        return None

    try:
        # 7th audit round (BUG W): never follow a symlink planted at
        # package.json — the parsed content is copied verbatim into --json
        # output, so a followed symlink would leak an external file's content.
        with open_no_follow_symlink(pkg_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    info = {}

    # Name and version
    if "name" in data:
        info["name"] = data["name"]
    if "version" in data:
        info["version"] = data["version"]

    # Scripts (signals about tooling)
    if "scripts" in data:
        info["scripts"] = list(data["scripts"].keys())

    # Dependencies (major ones only)
    all_deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        if key in data:
            all_deps.update(data[key])
    info["dependency_count"] = len(all_deps)

    # Detect frameworks from deps
    frameworks = []
    framework_signals = {
        "next": "Next.js", "react": "React", "vue": "Vue",
        "svelte": "Svelte", "@angular/core": "Angular",
        "express": "Express", "fastify": "Fastify", "hono": "Hono",
        "remix": "Remix", "astro": "Astro", "nuxt": "Nuxt",
        "electron": "Electron", "react-native": "React Native",
        "expo": "Expo", "@nestjs/core": "NestJS",
        "prisma": "Prisma", "drizzle-orm": "Drizzle",
        "mongoose": "Mongoose", "typeorm": "TypeORM",
        "tailwindcss": "Tailwind CSS",
        "three": "Three.js", "d3": "D3.js",
    }
    for dep, label in framework_signals.items():
        if dep in all_deps:
            version = all_deps[dep].lstrip("^~>=<")
            frameworks.append(f"{label} {version}")
    info["frameworks"] = frameworks

    # Detect TypeScript version
    if "typescript" in all_deps:
        info["typescript"] = all_deps["typescript"].lstrip("^~>=<")

    # Detect monorepo signals
    if "workspaces" in data:
        info["monorepo_signal"] = "npm/yarn workspaces"
        workspaces = data["workspaces"]
        if isinstance(workspaces, list):
            info["workspace_patterns"] = workspaces
        elif isinstance(workspaces, dict) and "packages" in workspaces:
            info["workspace_patterns"] = workspaces["packages"]

    # Detect package manager
    if "packageManager" in data:
        info["package_manager"] = data["packageManager"]

    return info


def scan_pyproject(root: str) -> dict[str, Any] | None:
    """Extract stack info from pyproject.toml (build backend, frameworks, Python version).

    Returns:
        Dict with detected info, or None if pyproject.toml is missing or unreadable.
    """
    pyproject = os.path.join(root, "pyproject.toml")
    if not os.path.isfile(pyproject):
        return None

    try:
        # 7th audit round (BUG W): never follow a symlink planted at
        # pyproject.toml — same verbatim-leak concern as scan_package_json().
        with open_no_follow_symlink(pyproject, "r") as f:
            content = f.read()
    except OSError:
        return None

    info = {}

    # Project name
    m = re.search(r'^\s*name\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if m:
        info["name"] = m.group(1)

    # Python version requirement
    m = re.search(r'^\s*requires-python\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if m:
        info["python_requires"] = m.group(1)

    # Build system
    m = re.search(r'^\s*build-backend\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if m:
        info["build_backend"] = m.group(1)

    # Detect frameworks from dependencies
    frameworks = []
    framework_signals = {
        "django": "Django", "flask": "Flask", "fastapi": "FastAPI",
        "starlette": "Starlette", "celery": "Celery",
        "sqlalchemy": "SQLAlchemy", "alembic": "Alembic",
        "pydantic": "Pydantic", "pytest": "pytest",
        "torch": "PyTorch", "tensorflow": "TensorFlow",
        "transformers": "Hugging Face Transformers",
        "pandas": "Pandas", "numpy": "NumPy",
        "scikit-learn": "scikit-learn", "scipy": "SciPy",
        "matplotlib": "Matplotlib", "plotly": "Plotly",
        "streamlit": "Streamlit", "gradio": "Gradio",
        "langchain": "LangChain", "anthropic": "Anthropic SDK",
        "openai": "OpenAI SDK",
    }
    for dep, label in framework_signals.items():
        if dep in content.lower():
            frameworks.append(label)
    info["frameworks"] = frameworks

    return info


def detect_monorepo(root: str, tree: dict[str, list[str]]) -> dict[str, Any]:
    """Detect monorepo patterns and build scope map.

    Returns:
        {"signals": [...], "scope_map": {"apps/web": "web", ...}}
    """
    signals: list[str] = []
    scope_map: dict[str, str] = {}

    # Check for workspace config files
    workspace_files = [
        "pnpm-workspace.yaml", "turbo.json", "lerna.json",
        "nx.json", "rush.json", ".moon/workspace.yml",
    ]
    for wf in workspace_files:
        if os.path.isfile(os.path.join(root, wf)):
            signals.append(f"Found {wf}")

    # Check for packages/ or apps/ directories
    mono_dirs = ["packages", "apps", "libs", "modules", "services"]
    project_markers = ["package.json", "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml", "build.gradle"]
    for d in mono_dirs:
        full = os.path.join(root, d)
        if os.path.isdir(full):
            subs: list[str] = []
            try:
                entries = os.listdir(full)
            except OSError:
                continue
            for sub in entries:
                sub_path = os.path.join(full, sub)
                if os.path.isdir(sub_path):
                    for marker in project_markers:
                        if os.path.isfile(os.path.join(sub_path, marker)):
                            subs.append(sub)
                            scope_map[f"{d}/{sub}"] = sub
                            break
            if subs:
                signals.append(f"{d}/ has {len(subs)} sub-projects: {', '.join(subs[:5])}")

    # npm/yarn workspaces from package.json (already parsed by scan_package_json,
    # but we check here too for scope_map completeness)
    pkg_json = os.path.join(root, "package.json")
    if os.path.isfile(pkg_json) and not scope_map:
        try:
            # 7th audit round (BUG X): never follow a symlink planted at
            # package.json — a separate call site from scan_package_json().
            with open_no_follow_symlink(pkg_json, "r") as f:
                data = json.load(f)
            workspaces = data.get("workspaces", [])
            if isinstance(workspaces, dict):
                workspaces = workspaces.get("packages", [])
            if isinstance(workspaces, list):
                for pattern in workspaces:
                    # Resolve simple glob patterns like "packages/*"
                    base = pattern.rstrip("/*")
                    base_path = os.path.join(root, base)
                    if os.path.isdir(base_path):
                        for sub in os.listdir(base_path):
                            if os.path.isdir(os.path.join(base_path, sub)):
                                scope_map.setdefault(f"{base}/{sub}", sub)
        except (json.JSONDecodeError, OSError):
            pass

    return {"signals": signals, "scope_map": scope_map}


def detect_ci_commitlint(root: str) -> list[str]:
    """Detect commitlint, husky, or pre-commit hooks that might reject trailers.

    Returns:
        List of human-readable signal descriptions.
    """
    signals = []

    # commitlint
    commitlint_files = [
        "commitlint.config.js", "commitlint.config.ts",
        ".commitlintrc", ".commitlintrc.js", ".commitlintrc.json",
    ]
    for f in commitlint_files:
        if os.path.isfile(os.path.join(root, f)):
            signals.append(f"commitlint config: {f}")

    # Husky
    husky_dir = os.path.join(root, ".husky")
    if os.path.isdir(husky_dir):
        signals.append("Husky git hooks detected")
        # Check if commit-msg hook exists
        commit_msg = os.path.join(husky_dir, "commit-msg")
        if os.path.isfile(commit_msg):
            try:
                # 7th audit round (BUG X): never follow a symlink planted at
                # .husky/commit-msg.
                with open_no_follow_symlink(commit_msg, "r") as fh:
                    content = fh.read()
                if "commitlint" in content:
                    signals.append("Husky commit-msg runs commitlint")
            except OSError:
                pass

    # pre-commit
    if os.path.isfile(os.path.join(root, ".pre-commit-config.yaml")):
        signals.append("pre-commit hooks detected")

    return signals


def check_existing_memory(root: str) -> dict[str, Any]:
    """Check if git-memory is already installed by looking for CLAUDE.md block and manifest."""
    signals: dict[str, Any] = {}

    # Check CLAUDE.md for managed block
    claude_md = os.path.join(root, "CLAUDE.md")
    if os.path.isfile(claude_md):
        try:
            # barrido finding: never follow a symlink planted at CLAUDE.md —
            # treat it exactly like "no CLAUDE.md present".
            with open_no_follow_symlink(claude_md, "r") as f:
                content = f.read()
            signals["claude_md_exists"] = True
            signals["has_memory_block"] = "BEGIN unmassk-toolkit" in content
        except OSError:
            signals["claude_md_exists"] = False
    else:
        signals["claude_md_exists"] = False

    # Check manifest
    manifest = os.path.join(root, ".claude", ".unmassk", "manifest.json")
    if os.path.isfile(manifest):
        signals["already_installed"] = True
        try:
            # barrido finding (same class as SEC-LOW-NEW-05): never follow a
            # symlink planted at the manifest path — treat it exactly like a
            # corrupt manifest, never trust the victim file's content.
            # BUG AK: open_no_follow_symlink() only guards the FINAL
            # manifest.json component — if .claude ITSELF is a symlinked
            # parent pointing at a directory that already contains a REAL
            # (non-symlink) manifest.json, that guard has nothing to object
            # to. Verify the full resolved path stays inside root first;
            # UnsafePathError is an OSError subclass so it's caught below,
            # exactly like "corrupt manifest".
            verify_path_within_project(manifest, root)
            with open_no_follow_symlink(manifest, "r") as f:
                data = json.load(f)
            # SEC-MED-NEW-08: the manifest's "version" field is untrusted —
            # sanitize before it can ever reach a printed finding.
            signals["installed_version"] = sanitize_trailer_value(str(data.get("version", "unknown")))
        except (json.JSONDecodeError, OSError):
            signals["installed_version"] = "corrupt"
    else:
        signals["already_installed"] = False

    return signals
