"""
bootstrap_tree -- Directory tree walking and high-signal file detection for
bin/git-memory-bootstrap.py.

Split out of git-memory-bootstrap.py (was 953 LOC, never divided in 10
rounds) to keep the CLI entrypoint under the 500 LOC project limit. This
module owns the "what does the directory structure look like, and which
files are recognizable ecosystem signals" concern — no git, no dependency
parsing, no classification/output formatting (those live in
bootstrap_deps.py, bootstrap_commits.py, and bootstrap_report.py).
"""

import os

# ── Config ────────────────────────────────────────────────────────────────
MAX_TREE_DEPTH = 2

# Directories to skip during tree scan
SKIP_DIRS = {
    "node_modules", ".git", "vendor", "dist", "build", ".next", "__pycache__",
    ".venv", "venv", "env", ".env", ".tox", ".mypy_cache", ".pytest_cache",
    "coverage", ".coverage", ".nyc_output", "target", "out", ".turbo",
    ".cache", ".parcel-cache", "bower_components", ".gradle", ".idea",
    ".vscode", ".claude", "eggs", "*.egg-info",
}

# High-signal files and what they indicate
SIGNAL_FILES = {
    # JavaScript/TypeScript ecosystem
    "package.json":       ("npm/node project", "js"),
    "pnpm-lock.yaml":     ("pnpm package manager", "js"),
    "yarn.lock":          ("yarn package manager", "js"),
    "package-lock.json":  ("npm package manager", "js"),
    "bun.lockb":          ("bun runtime", "js"),
    "tsconfig.json":      ("TypeScript", "js"),
    "jsconfig.json":      ("JavaScript (with config)", "js"),
    "next.config.js":     ("Next.js", "js"),
    "next.config.mjs":    ("Next.js", "js"),
    "next.config.ts":     ("Next.js", "js"),
    "nuxt.config.ts":     ("Nuxt.js", "js"),
    "vite.config.ts":     ("Vite", "js"),
    "vite.config.js":     ("Vite", "js"),
    "svelte.config.js":   ("SvelteKit", "js"),
    "astro.config.mjs":   ("Astro", "js"),
    "remix.config.js":    ("Remix", "js"),
    "angular.json":       ("Angular", "js"),
    "vue.config.js":      ("Vue CLI", "js"),
    "webpack.config.js":  ("Webpack", "js"),
    "rollup.config.js":   ("Rollup", "js"),
    "esbuild.config.js":  ("esbuild", "js"),
    "tailwind.config.js": ("Tailwind CSS", "js"),
    "tailwind.config.ts": ("Tailwind CSS", "js"),
    "postcss.config.js":  ("PostCSS", "js"),
    ".eslintrc":          ("ESLint", "js"),
    ".eslintrc.js":       ("ESLint", "js"),
    ".eslintrc.json":     ("ESLint", "js"),
    "eslint.config.js":   ("ESLint (flat config)", "js"),
    ".prettierrc":        ("Prettier", "js"),
    "prettier.config.js": ("Prettier", "js"),
    "biome.json":         ("Biome", "js"),
    "jest.config.js":     ("Jest", "js"),
    "jest.config.ts":     ("Jest", "js"),
    "vitest.config.ts":   ("Vitest", "js"),
    "playwright.config.ts": ("Playwright", "js"),
    "cypress.config.ts":  ("Cypress", "js"),
    ".storybook":         ("Storybook", "js"),
    "turbo.json":         ("Turborepo", "js"),
    "lerna.json":         ("Lerna (monorepo)", "js"),
    "nx.json":            ("Nx (monorepo)", "js"),

    # Python ecosystem
    "requirements.txt":   ("Python (pip)", "py"),
    "pyproject.toml":     ("Python (modern)", "py"),
    "setup.py":           ("Python (setuptools)", "py"),
    "setup.cfg":          ("Python (setuptools)", "py"),
    "Pipfile":            ("Python (pipenv)", "py"),
    "poetry.lock":        ("Python (poetry)", "py"),
    "uv.lock":            ("Python (uv)", "py"),
    "tox.ini":            ("Python (tox)", "py"),
    "pytest.ini":         ("Python (pytest)", "py"),
    ".flake8":            ("Python (flake8)", "py"),
    "ruff.toml":          ("Python (ruff)", "py"),
    "mypy.ini":           ("Python (mypy)", "py"),
    "manage.py":          ("Django", "py"),
    "app.py":             ("Flask/FastAPI candidate", "py"),

    # Rust
    "Cargo.toml":         ("Rust", "rust"),
    "Cargo.lock":         ("Rust (locked deps)", "rust"),

    # Go
    "go.mod":             ("Go", "go"),
    "go.sum":             ("Go (locked deps)", "go"),

    # Java/JVM
    "pom.xml":            ("Java (Maven)", "jvm"),
    "build.gradle":       ("Java/Kotlin (Gradle)", "jvm"),
    "build.gradle.kts":   ("Kotlin (Gradle KTS)", "jvm"),

    # Ruby
    "Gemfile":            ("Ruby", "ruby"),
    "Gemfile.lock":       ("Ruby (locked deps)", "ruby"),
    "Rakefile":           ("Ruby (Rake)", "ruby"),
    "config.ru":          ("Ruby (Rack app)", "ruby"),

    # PHP
    "composer.json":      ("PHP (Composer)", "php"),
    "artisan":            ("Laravel", "php"),

    # Elixir
    "mix.exs":            ("Elixir", "elixir"),

    # .NET
    "*.csproj":           (".NET (C#)", "dotnet"),
    "*.fsproj":           (".NET (F#)", "dotnet"),

    # Infrastructure / DevOps
    "Dockerfile":         ("Docker", "infra"),
    "docker-compose.yml": ("Docker Compose", "infra"),
    "docker-compose.yaml": ("Docker Compose", "infra"),
    "Makefile":           ("Make", "infra"),
    "Justfile":           ("Just", "infra"),
    "Taskfile.yml":       ("Task", "infra"),
    "Procfile":           ("Heroku/Procfile", "infra"),
    "fly.toml":           ("Fly.io", "infra"),
    "vercel.json":        ("Vercel", "infra"),
    "netlify.toml":       ("Netlify", "infra"),
    "railway.json":       ("Railway", "infra"),
    "terraform":          ("Terraform", "infra"),
    "pulumi":             ("Pulumi", "infra"),
    "serverless.yml":     ("Serverless Framework", "infra"),

    # CI/CD
    ".github/workflows":  ("GitHub Actions", "ci"),
    ".gitlab-ci.yml":     ("GitLab CI", "ci"),
    ".circleci":          ("CircleCI", "ci"),
    "Jenkinsfile":        ("Jenkins", "ci"),
    ".travis.yml":        ("Travis CI", "ci"),

    # Config / Quality
    ".editorconfig":      ("EditorConfig", "config"),
    ".gitignore":         ("Git ignore rules", "config"),
    "CLAUDE.md":          ("Claude Code config", "config"),
    ".cursorrules":       ("Cursor AI config", "config"),
    "README.md":          ("Documentation", "config"),
    "CHANGELOG.md":       ("Changelog", "config"),
    "LICENSE":            ("License file", "config"),
    # Monorepo tools
    "rush.json":          ("Rush (monorepo)", "js"),
    ".moon/workspace.yml": ("Moon (monorepo)", "js"),

    "commitlint.config.js": ("commitlint", "ci"),
    ".commitlintrc":      ("commitlint", "ci"),
    ".husky":             ("Husky (git hooks)", "ci"),
    "lint-staged.config.js": ("lint-staged", "ci"),
    ".pre-commit-config.yaml": ("pre-commit", "ci"),
}


# ── Scanners ──────────────────────────────────────────────────────────────

def scan_tree(root: str, max_depth: int = MAX_TREE_DEPTH) -> dict[str, list[str]]:
    """Walk the directory tree up to max_depth, skipping noisy directories.

    Returns:
        Dict with "dirs" and "files" keys, each a list of relative paths.
    """
    tree: dict[str, list[str]] = {"dirs": [], "files": []}

    for dirpath, dirnames, filenames in os.walk(root):
        # Calculate depth relative to root
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1

        if depth > max_depth:
            dirnames.clear()
            continue

        # Filter out skip dirs
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]

        for d in dirnames:
            tree["dirs"].append(os.path.relpath(os.path.join(dirpath, d), root))

        for f in filenames:
            tree["files"].append(os.path.relpath(os.path.join(dirpath, f), root))

    return tree


def scan_signal_files(root: str, tree_files: list[str]) -> list[dict[str, str]]:
    """Match tree files against SIGNAL_FILES to detect ecosystem indicators.

    Returns:
        List of dicts with "file", "signal", and "ecosystem" keys.
    """
    found = []

    for filepath in tree_files:
        basename = os.path.basename(filepath)

        # Check basename against signal files
        if basename in SIGNAL_FILES:
            label, ecosystem = SIGNAL_FILES[basename]
            found.append({
                "file": filepath,
                "signal": label,
                "ecosystem": ecosystem,
            })

        # Check for directory-based signals
        if filepath in SIGNAL_FILES:
            label, ecosystem = SIGNAL_FILES[filepath]
            found.append({
                "file": filepath,
                "signal": label,
                "ecosystem": ecosystem,
            })

    # Check directory-based signals separately
    for signal_path, (label, ecosystem) in SIGNAL_FILES.items():
        full = os.path.join(root, signal_path)
        if os.path.isdir(full) and signal_path not in [f["file"] for f in found]:
            found.append({
                "file": signal_path,
                "signal": label,
                "ecosystem": ecosystem,
            })

    return found
