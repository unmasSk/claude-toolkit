---
name: design-flutter
description: >
  Use when the user asks to "design a Flutter screen", "build Flutter UI",
  "animate in Flutter", "add a Flutter transition", "Material 3 theme",
  "Cupertino widgets", "Flutter layout", "responsive Flutter", "Hero
  animation", "page transition in GoRouter", "CustomPainter", "Flutter dark
  mode", or mentions any of: AnimatedContainer, AnimationController, Hero
  widget, ColorScheme, TextTheme, ThemeExtension, LayoutBuilder, Slivers,
  RepaintBoundary, CustomPainter, Riverpod UI, mobile app UI, Material
  widgets, Cupertino widgets. Covers Flutter UI composition (layout, theme,
  Material 3 / Cupertino), animation (implicit, explicit, Hero, physics,
  page transitions), and rendering (CustomPaint, performance-safe widgets).
  Use when NOT: the request is about Flutter state-management architecture
  (Riverpod/Provider/BLoC internals, dependency wiring), backend/API
  integration, or app packaging/build/release -- those are outside this
  skill's design/UI scope. Adapted from claude-flutter-ui-skills by
  Naimehossein77 (community source, condensed into unmassk-design's voice).
version: 1.0.0
---

# Flutter UI Design -- mobile screens, widgets, and motion

Design and build Flutter UI: layout composition, Material 3 / Cupertino
theming, and GPU-safe animation. This is the mobile counterpart to
`unmassk-design`'s web references -- same design discipline (intentional
motion, theme-driven values, no magic numbers), applied to Flutter's widget
tree instead of CSS/DOM.

This `SKILL.md` is a thin router. Read the specific reference for the task
in front of you; do not try to hold both files in memory at once for a
small change.

## Method

1. **Context first, not memorized defaults.** Before reaching for a widget,
   ask: what is this screen's primary purpose, what does the animation
   communicate (if anything), and does this need to be a `Container` or
   would `SizedBox`/`Padding`/`Align` say the same thing with less?
2. **Theme-driven, never hardcoded.** Colors come from
   `Theme.of(context).colorScheme`, text styles from `.textTheme`. A
   hardcoded `Color(0xFF...)` or literal `fontSize` is the Flutter
   equivalent of a magic number in CSS -- it breaks dark mode and the
   design system's single source of truth.
3. **Route to the reference that matches the task:**

| Task | Reference |
|---|---|
| Screen layout, responsive breakpoints, Slivers, Material 3 theme, ColorScheme/TextTheme, dark mode, CustomPainter/Canvas | `references/flutter-ui-patterns.md` |
| Implicit/explicit animations, Hero transitions, page transitions, physics-based motion, curves/duration, animation performance (RepaintBoundary, GPU-safe properties) | `references/flutter-animations.md` |

4. **Const-first, GPU-safe.** Every `StatelessWidget` gets a `const`
   constructor; every animation touches `Transform`/`Opacity`, never
   `width`/`height`/`margin` directly (layout properties force a full
   relayout pass -- jank, not a style choice).
5. **Ask before assuming** state manager, navigation package, or design
   system (Material 3 vs Cupertino vs custom) if not already evident from
   the codebase's imports -- this skill does not own that decision, it
   only needs the answer to pick the right UI pattern.

## Scripts

Scripts are tools, not optional helpers. Run them via Bash. Do not
replicate their logic manually.

| Script | Qué hace | Uso |
|---|---|---|
| `flutter_ui_audit.py` | Scans a Flutter project's `lib/` tree for UI/state/navigation/animation anti-patterns (missing `dispose()`, deprecated `WillPopScope`, layout-property animation, `ListView` without `.builder`, hardcoded colors/fontSize, missing `const` constructors, Riverpod/Provider misuse) and reports findings as RED/YELLOW/GREEN with a fix suggestion each. Self-contained, stdlib only. | `python ${CLAUDE_PLUGIN_ROOT}/skills/design-flutter/scripts/flutter_ui_audit.py <project_path> [--all] [--only red\|yellow\|green]` |

Exit code is `1` if any RED (critical) finding exists, `0` otherwise --
usable as a CI gate. Note that `${CLAUDE_PLUGIN_ROOT}` is auto-resolved by
Claude Code; use it as written.

## Out of scope (route elsewhere)

- Riverpod/Provider/BLoC provider wiring, `ChangeNotifier` architecture,
  dependency graphs -- this is state-management architecture, not UI design.
- GoRouter route guards, deep-link auth redirects, route tree structure --
  this is navigation architecture. (Page *transition animations* within
  GoRouter are in scope; the routing logic around them is not.)
- Build, signing, store release -- packaging, not design.

## Attribution

Patterns condensed from `flutter-ui` in
[claude-flutter-ui-skills](https://github.com/Naimehossein77/claude-flutter-ui-skills)
by Naimehossein77. Content re-expressed in unmassk-design's voice and
narrowed to the UI/animation scope this plugin owns; state-management and
navigation-architecture material from the source was intentionally left out.
