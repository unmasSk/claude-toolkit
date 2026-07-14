# Flutter UI Patterns -- layout, theme, rendering

Condensed from `claude-flutter-ui-skills` (Naimehossein77). Covers the
non-animation half of Flutter UI design: what widget to reach for, how to
theme it, how to make it responsive, and how to paint it when no built-in
widget fits.

## 1. Question the default before writing the widget

Flutter has a widget for everything, which means it's easy to reach for the
wrong one out of habit. Before coding, decide:

- **Sizing/spacing without decoration** -- `SizedBox`/`Padding`/`Align`, not
  `Container`. Reach for `Container` only once you actually need color,
  border, or shadow -- at that point it's justified, not a default.
- **List item** -- does it need elevation? Often a plain `ListTile` reads
  better than `Card` wrapping everything.
- **Ripple feedback** -- `InkWell`/`Ink`, not `GestureDetector` wrapping a
  `Column` (loses the Material ripple).
- **Widget type** -- pure display with no state → `StatelessWidget`. Needs
  an `AnimationController` or `FocusNode` → `StatefulWidget`. Reads a
  Riverpod provider only → `ConsumerWidget`.

Ask before assuming: what's the design system (Material 3 / Cupertino /
custom)? Mobile-only or tablet/desktop adaptive too?

## 2. Theming -- Material 3, ColorScheme, TextTheme

```dart
MaterialApp(
  theme: ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF6750A4)),
  ),
  darkTheme: ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(
      seedColor: const Color(0xFF6750A4),
      brightness: Brightness.dark,
    ),
  ),
  themeMode: ThemeMode.system,
)
```

Read colors and text styles from theme, always -- this is the Flutter
equivalent of using design tokens instead of magic numbers:

```dart
final scheme = Theme.of(context).colorScheme;
Text('Title', style: Theme.of(context).textTheme.headlineMedium)
```

Key `ColorScheme` roles: `primary`/`onPrimary` (brand, key buttons),
`secondary`/`tertiary` (accents), `error`, `surface`/`onSurface` (cards,
dialogs, sheets), `outline`/`outlineVariant` (borders/dividers),
`surfaceContainerHighest` (input fills).

`TextTheme` scale (largest to smallest): `displayLarge/Medium/Small` (hero,
marketing), `headlineLarge/Medium/Small` (screen/card/subsection titles),
`titleLarge/Medium/Small` (AppBar, list tile, tabs), `bodyLarge/Medium/Small`
(primary/secondary text, captions), `labelLarge/Medium/Small` (buttons,
chips, overlines).

**Dark mode:** `Theme.of(context).colorScheme.surface`, never
`Colors.white` or a literal hex -- literal colors silently break dark mode.

**Custom design tokens** beyond the built-in roles (brand colors, spacing
scale) go in a `ThemeExtension`:

```dart
@immutable
class AppSpacing extends ThemeExtension<AppSpacing> {
  const AppSpacing({this.xs = 4.0, this.sm = 8.0, this.md = 16.0, this.lg = 24.0});
  final double xs, sm, md, lg;
  @override
  AppSpacing copyWith({...}) => AppSpacing(...);
  @override
  AppSpacing lerp(AppSpacing? other, double t) => this;
}
// Theme.of(context).extension<AppSpacing>()!.md
```

Component-level overrides (`filledButtonTheme`, `inputDecorationTheme`,
`cardTheme`, `appBarTheme`) live on `ThemeData` so every instance of that
component matches without repeating style code.

## 3. Responsive layout

```dart
class Breakpoints {
  static const double mobile = 600;
  static const double tablet = 900;
  static const double desktop = 1200;
}
```

- `LayoutBuilder` -- responds to the *parent's* constraints; use inside
  reusable widgets that need to adapt to whatever container they're in.
- `MediaQuery.sizeOf(context)` -- full screen dimensions; use for
  screen-level layout decisions (not `.size`, which rebuilds more broadly).

Adaptive shell pattern (rail on wide, bottom nav on narrow):

```dart
LayoutBuilder(builder: (context, constraints) {
  final isWide = constraints.maxWidth >= 600;
  return Scaffold(
    body: isWide
      ? Row(children: [NavigationRail(...), const Expanded(child: content)])
      : content,
    bottomNavigationBar: isWide ? null : NavigationBar(...),
  );
})
```

**Flex primitives:** `Expanded` (take all remaining space), `Flexible`
(take up to its share, won't overflow), `Spacer` (empty flex space),
`FractionallySizedBox` (child as % of parent).

**Common overflow fixes:** `Row` overflow → wrap the long child in
`Flexible`. `ListView` inside `Column` overflow → wrap the `ListView` in
`Expanded` (unbounded height is the cause). Long text → `overflow:
TextOverflow.ellipsis, maxLines: 1`. Avoid `IntrinsicHeight`/`IntrinsicWidth`
in lists -- they're O(N²); use fixed heights or `SliverFixedExtentList`
instead.

**Safe area / edge-to-edge:**

```dart
Scaffold(body: SafeArea(child: content))
// or, extending under the status bar deliberately:
Scaffold(extendBodyBehindAppBar: true, appBar: AppBar(backgroundColor: Colors.transparent, elevation: 0))
```

**Slivers** for complex scroll UIs (collapsing header + mixed content):
`SliverAppBar` (collapsing header), `SliverToBoxAdapter` (one-off block),
`SliverList.builder`/`SliverGrid.builder` (lazy lists/grids),
`SliverFixedExtentList` (most performant -- skips per-item layout
measurement when every item is the same height).

## 4. CustomPaint / Canvas -- when no widget fits

Use `CustomPainter` for shapes, charts, or effects no built-in widget
covers. Rules that keep it correct and fast:

- **Pair every `save()` with a `restore()`.** An unmatched save leaks the
  canvas transform/clip into whatever paints next.
- **`shouldRepaint` must compare fields, not return `true` unconditionally**
  -- `true` forces a repaint every frame regardless of whether anything
  changed.
- **Wrap in `RepaintBoundary`** so the painter's repaints don't force the
  surrounding tree to repaint too.
- **Animate via the `repaint` listenable**, not `setState`: pass an
  `Animation<double>` as `super(repaint: repaint)` so the painter repaints
  on tick without going through `build()`.
- **Add a `Semantics` label** for anything conveying information (a chart,
  a progress ring) -- `CustomPaint` has no accessibility tree by default.

```dart
class MyPainter extends CustomPainter {
  const MyPainter({required this.value, required this.color});
  final double value;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color..strokeWidth = 2..style = PaintingStyle.stroke;
    canvas.drawLine(Offset.zero, Offset(size.width * value, 0), paint);
  }

  @override
  bool shouldRepaint(MyPainter old) => value != old.value || color != old.color;
}
```

## 5. General performance (non-animation)

- **`const` everywhere** it's valid -- every `StatelessWidget` constructor,
  every widget with compile-time args, every `EdgeInsets`/`SizedBox`
  literal. This is the single most impactful, lowest-effort performance
  habit in Flutter. `flutter analyze` finds the misses.
- **`ListView.builder`/`GridView.builder`**, never a `ListView` built from
  a mapped list of children -- the non-lazy form renders every item
  up front regardless of what's visible.
- **Targeted rebuilds:** narrow `ref.watch(provider.select((s) => s.field))`
  (Riverpod) or `Selector<T, R>` (Provider) instead of watching/consuming
  the whole state object, so unrelated field changes don't rebuild the
  whole subtree.
- **Images:** set `cacheWidth`/`cacheHeight` (or `memCacheWidth` with
  `CachedNetworkImage`) so decode size matches display size, not the
  source resolution.
- **`build()` must stay pure and fast** -- no async ops, no heavy
  computation, no creating controllers/notifiers inline (that recreates
  them every rebuild; hoist to a `late final` field instead).
- **Stable list keys:** `ValueKey(item.id)` from real data identity, never
  `ValueKey(index)` (breaks on reorder) or `UniqueKey()` (breaks
  animations/state by generating a new key every build).

## 6. Design-intent checklist (ask every time)

- What happens while data is loading? What happens if it fails (+ retry)?
- What happens at 320dp width? At 200% text scale?
- Does back navigation behave correctly from every screen this reaches?
- Is this animation communicating something, or decorative? (If
  decorative and unjustified, cut it.)
- Touch targets ≥ 48dp (Material) / 44pt (iOS)?
