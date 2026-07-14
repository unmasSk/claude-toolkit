# Flutter Animations -- implicit, explicit, Hero, transitions, physics

Condensed from `claude-flutter-ui-skills` (Naimehossein77). Covers motion
design in Flutter: which animation type fits the change, GPU-safe
properties, Hero/page transitions, and the performance rules specific to
animated widgets.

## 1. Pick the animation type by what's changing

```
Simple property change (size, color, opacity, position)
  -> IMPLICIT: AnimatedContainer, AnimatedOpacity, TweenAnimationBuilder

Complex sequence, stagger, or precise control
  -> EXPLICIT: AnimationController + CurvedAnimation + AnimatedBuilder

Shared element across screens   -> Hero widget + unique tag
Page enter/exit                 -> CustomTransitionPage / pageBuilder
Spring / bounce / friction      -> SpringSimulation, FrictionSimulation
Complex vector/sprite           -> Rive or Lottie package
```

## 2. GPU-safe vs CPU-bound properties

```
GPU-ACCELERATED (smooth):      CPU-BOUND (jank):
- Transform.translate           - width, height
- Transform.scale               - margin, padding
- Transform.rotate              - top, left (Positioned)
- Opacity                       - border, decoration changes
```

Rule: if the change affects layout (`width`, `height`, `margin`,
`Positioned` offsets), animate a `Transform` instead of the layout property
directly -- layout properties force a full relayout pass every frame.

## 3. Implicit animations

For a single property that just needs to ease from A to B:

```dart
AnimatedContainer(
  duration: const Duration(milliseconds: 250),
  curve: Curves.easeInOut,
  width: isExpanded ? 200 : 100,
  color: isActive ? Colors.blue : Colors.grey,
  child: child,
)

AnimatedOpacity(
  opacity: isVisible ? 1.0 : 0.0,
  duration: const Duration(milliseconds: 200),
  child: child,
)

TweenAnimationBuilder<double>(
  tween: Tween(begin: 0.0, end: targetValue),
  duration: const Duration(milliseconds: 300),
  curve: Curves.easeOut,
  builder: (context, value, child) => Transform.scale(scale: value, child: child),
  child: const ExpensiveWidget(), // built once via `child`, not rebuilt per frame
)
```

## 4. Explicit animations

For multi-step sequences or when you need direct control over playback:

```dart
class _MyWidgetState extends State<MyWidget> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _scaleAnim;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 300));
    _scaleAnim = Tween<double>(begin: 0.8, end: 1.0)
      .animate(CurvedAnimation(parent: _controller, curve: Curves.elasticOut));
    _controller.forward();
  }

  @override
  void dispose() {
    _controller.dispose(); // mandatory -- leaked controllers leak tickers
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: _scaleAnim,
    builder: (context, child) => Transform.scale(scale: _scaleAnim.value, child: child),
    child: const MyContent(), // static subtree, built once
  );
}
```

**Staggering** multiple properties off one controller: give each `Tween` a
`CurvedAnimation` with a different `Interval` (e.g. `Interval(0.0, 0.4, ...)`,
`Interval(0.3, 0.7, ...)`, `Interval(0.6, 1.0, ...)`) so they overlap and
cascade instead of firing in lockstep.

**AnimationController checklist:** created in `initState()` · `vsync: this`
· disposed in `dispose()` · never recreated inside `build()` · driven
through `AnimatedBuilder` (never `addListener(() => setState(() {}))`) ·
`child` param used for any non-animating subtree.

## 5. Hero animations (shared element across screens)

```dart
Hero(tag: 'product-image-${product.id}', child: Image.network(product.imageUrl))
```

- Tag must be unique across every simultaneously visible Hero -- a
  collision produces a broken/duplicated flight.
- Custom flight path via `flightShuttleBuilder` when the default
  cross-fade/scale isn't the right motion.
- Wrap complex Hero children in `RepaintBoundary`.

## 6. Page transitions

```dart
CustomTransitionPage(
  key: state.pageKey,
  child: DetailsScreen(id: id),
  transitionDuration: const Duration(milliseconds: 300),
  transitionsBuilder: (context, animation, secondaryAnimation, child) => FadeTransition(
    opacity: CurveTween(curve: Curves.easeInOut).animate(animation),
    child: child,
  ),
)

// Slide from right
transitionsBuilder: (context, animation, secondaryAnimation, child) => SlideTransition(
  position: Tween<Offset>(begin: const Offset(1.0, 0.0), end: Offset.zero)
    .animate(CurvedAnimation(parent: animation, curve: Curves.easeInOut)),
  child: child,
),
```

On iOS, prefer a native-feeling page (e.g. `CupertinoPage`) when the route
needs to preserve the swipe-back gesture -- a custom `transitionsBuilder`
combined with a `GestureDetector` on the same route tends to conflict with
swipe-back.

The routing/guard logic around *which* page builder runs is navigation
architecture, out of this skill's scope -- only the transition's motion is.

## 7. Physics-based motion

```dart
final spring = SpringDescription(mass: 1, stiffness: 100, damping: 10);
_controller.animateWith(SpringSimulation(spring, 0, 1, 0));

_controller.animateWith(FrictionSimulation(0.135, position, velocity));
```

Use for momentum/bounce/drag-release feel that a fixed-duration curve can't
express -- the simulation's next frame depends on velocity, not a clock.

## 8. Lottie / Rive (vector/sprite animation)

```dart
Lottie.asset('assets/animations/loading.json', onLoaded: (c) {
  _controller.duration = c.duration;
  _controller.repeat();
})

RiveAnimation.asset('assets/animations/character.riv', stateMachines: const ['State Machine 1'])
```

Reach for these when the motion is genuinely vector/sprite work (a
designed character, a complex loading mark) -- not as a substitute for a
two-line `AnimatedContainer`.

## 9. Curves and duration

| Curve | Use case |
|---|---|
| `Curves.easeInOut` | Most transitions (default, safe choice) |
| `Curves.easeOut` | Elements entering |
| `Curves.easeIn` | Elements leaving |
| `Curves.elasticOut` | Bouncy/playful entrances (use sparingly -- reads as unpolished outside playful products) |
| `Curves.fastOutSlowIn` | Material page transitions |
| `Curves.bounceOut` | Game-like feedback |

**Duration:** 100-150ms micro-interactions · 200-300ms standard transitions
· 350-500ms large/complex moves · never exceed ~500ms for anything the user
is waiting on. Linear (no curve) reads as robotic -- `easeInOut` is the
floor, not an upgrade.

Always ask what the animation communicates (feedback, delight, orientation,
branding) before choosing duration/curve -- an animation that isn't
communicating anything should be cut, not tuned.

## 10. Animation-specific performance

- **`RepaintBoundary`** around any animated subtree next to static
  content, and around complex `CustomPainter`s -- isolates the animation to
  its own compositing layer so it doesn't force the whole screen to
  repaint every frame. Don't wrap *every* widget -- each boundary adds a
  compositing layer of its own.
- **`AnimatedBuilder`/`ValueListenableBuilder`**, never
  `addListener(() => setState(() {}))` -- the latter rebuilds the entire
  widget (and its whole subtree) every tick instead of just the animated
  part.
- **Dispose every `AnimationController`.** An undisposed controller keeps
  its ticker alive after the widget is gone -- a real memory/CPU leak, not
  a style nitpick.
- **Shader warmup** for animations that stutter only on first play (a
  first-run jank from shader compilation): call
  `DefaultShaderWarmUp().execute()` before `runApp()`, or bundle SkSL via
  `--bundle-sksl-path`.
