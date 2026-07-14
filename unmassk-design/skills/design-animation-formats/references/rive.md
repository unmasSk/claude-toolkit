# Rive -- State-Machine Interactive Vector Animation

Source: `rive-interactive` (claudedesignskills by freshtechbro, Apache 2.0).

## What it is

Rive is a state-machine animation platform: designers build vector
animations in the Rive editor with states, transitions, and inputs, and the
runtime lets application code drive those inputs and read events back. This
is the key difference from Lottie (`references/lottie.md`) -- Lottie plays a
fixed timeline; Rive has real branching logic and two-way data binding.

**Use for:** interactive buttons/toggles/loaders with hover/press/loading
states, game-like UI with state-driven animation, dashboards where live app
data (a price, a score, a name) should visually update inside the animation,
animations that need to emit events back into app code.

## Core concepts

- **State machine** -- states (idle/hover/pressed) + transitions between
  them, defined in the Rive editor.
- **Inputs** -- three types drive transitions: **boolean** (`input.value =
  true/false`), **number** (`input.value = 50`), **trigger** (one-shot,
  `input.fire()`).
- **ViewModel** -- a data-binding layer for properties (string, number,
  color, enum, trigger) that the app sets and the animation reads live.
- **Events** -- custom events the animation emits (e.g. a rating submitted
  inside the artboard) that app code listens for.

## Setup

```bash
npm install rive-react
```

```jsx
// Pattern 1: basic playback, no interactivity
import Rive from 'rive-react';
<Rive src="animation.riv" artboard="Main" animations="idle"
      layout={{ fit: 'contain', alignment: 'center' }} />
```

```jsx
// Pattern 2: state machine driven by boolean/trigger inputs
import { useRive, useStateMachineInput } from 'rive-react';

const { rive, RiveComponent } = useRive({
  src: 'button.riv', stateMachines: 'Button State Machine', autoplay: true,
});
const hoverInput = useStateMachineInput(rive, 'Button State Machine', 'isHovered', false);
const clickInput = useStateMachineInput(rive, 'Button State Machine', 'isClicked', false);

<div onMouseEnter={() => hoverInput && (hoverInput.value = true)}
     onMouseLeave={() => hoverInput && (hoverInput.value = false)}
     onClick={() => clickInput && clickInput.fire()}>
  <RiveComponent />
</div>
```

```jsx
// Pattern 3: ViewModel data binding -- live app data into the animation
const { rive, RiveComponent } = useRive({
  src: 'dashboard.riv', autoplay: true, autoBind: false, // manual binding required
});
const viewModel = useViewModel(rive, { name: 'Dashboard' });
const viewModelInstance = useViewModelInstance(viewModel, { rive });
const { setValue: setPrice } = useViewModelInstanceNumber('stockPrice', viewModelInstance);

useEffect(() => { if (setPrice) setPrice(stockPrice); }, [setPrice, stockPrice]);
```

ViewModel property hooks: `useViewModelInstanceString/Number/Color/Enum/Trigger`.

```jsx
// Pattern 4: listening to events emitted from the animation
const { rive, RiveComponent } = useRive({
  src: 'rating.riv', stateMachines: 'State Machine 1',
  autoplay: true, automaticallyHandleEvents: true, // required for events to fire
});
useEffect(() => {
  if (!rive) return;
  const onEvent = (event) => {
    if (event.data.type === RiveEventType.General) {
      const { rating, message } = event.data.properties;
    }
  };
  rive.on(EventType.RiveEvent, onEvent);
  return () => rive.off(EventType.RiveEvent, onEvent);
}, [rive]);
```

## Pitfalls

- **`useStateMachineInput` returns `null`.** The input name must match the
  Rive editor exactly (case-sensitive) -- always guard with `if (input)`
  before setting `.value` or calling `.fire()`.
- **ViewModel property doesn't update the animation.** `autoBind` defaults
  to `true`, which conflicts with manual ViewModel control -- set `autoBind:
  false` when using `useViewModel`/`useViewModelInstance*`.
- **Events never fire.** Requires `automaticallyHandleEvents: true` in the
  `useRive` config; it is not implied by passing `stateMachines`.
- **Not cleaning up event listeners.** Same as any emitter --
  `rive.off(...)` in the `useEffect` cleanup.

## Performance

- `useOffscreenRenderer={true}` on `<Rive>` for better rendering performance.
- Preload large files with `useRiveFile({ src })` during app init, then pass
  the resulting `riveFile` into `useRive` instead of `src`.
- Disable `automaticallyHandleEvents` when events aren't needed -- manual
  control avoids unnecessary listener overhead.
- In the Rive editor: keep artboards under 2MB, prefer vector shapes over
  raster images, minimize bone count and state machine complexity.

## Related

`lottie.md` for the same "designer animation" problem without state/logic
needs. `design-scroll`'s GSAP reference to fire a Rive trigger on scroll
(`ScrollTrigger.create({ onEnter: () => trigger.fire() })`).
