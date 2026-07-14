# Barba.js

Page transitions for traditional multi-page sites: intercepts navigation,
fetches the next page over AJAX, and animates the swap so a plain MPA feels
like an SPA. This is orthogonal to the other three libraries in this family
-- it solves *page-to-page* navigation, not in-page scroll. It's commonly
paired with GSAP for the actual leave/enter tween.

Condensed from claudedesignskills' `barba-js` skill (Apache 2.0,
freshtechbro).

## Required markup

Three roles, one DOM:

```html
<body data-barba="wrapper">
  <header><nav>...</nav></header>              <!-- persists, outside container -->
  <main data-barba="container" data-barba-namespace="home">
    <!-- this is what gets replaced on navigation -->
  </main>
  <footer>...</footer>                          <!-- persists -->
</body>
```

- **wrapper** -- outermost, everything outside the container inside it persists (nav, footer).
- **container** -- the only thing that swaps. Must exist, with this exact attribute, on every page.
- **namespace** -- identifies page type (`home`, `product`, `blog-post`); transitions and views key off this.

## Lifecycle -- the one thing to internalize

```
Initial load:     beforeOnce → once → afterOnce
Every navigation: before → beforeLeave → leave → afterLeave →
                  beforeEnter → enter → afterEnter → after
```

`leave`/`enter` are where the actual animation lives; the `before*`/`after*`
pairs are for setup/cleanup around them. **`sync: true` on a transition**
changes the order so leave and enter play *simultaneously* (crossfade) instead
of sequentially (leave completes, then swap, then enter).

## The one rule that breaks transitions if skipped

Every `leave`/`enter` hook **must return a promise or be `async`**, or Barba
swaps containers before the animation finishes:

```javascript
// wrong -- animation starts, Barba doesn't wait, page jumps instantly
leave({ current }) { gsap.to(current.container, { opacity: 0 }); }

// correct
async leave({ current }) { await gsap.to(current.container, { opacity: 0, duration: 0.5 }); }
```

## Minimal transition (fade)

```javascript
import barba from "@barba/core";
import gsap from "gsap";

barba.init({
  transitions: [{
    name: "fade",
    async leave({ current }) {
      await gsap.to(current.container, { opacity: 0, duration: 0.5, ease: "power2.inOut" });
    },
    async enter({ next }) {
      gsap.set(next.container, { opacity: 0 }); // avoid flash of visible content
      await gsap.to(next.container, { opacity: 1, duration: 0.5, ease: "power2.inOut" });
    }
  }]
});
```

## Conditional transitions by namespace

Different navigations can use different transitions -- rule priority is
`custom` > `route` (needs `@barba/router`) > `namespace`:

```javascript
barba.init({
  transitions: [
    { name: "product-to-product", from: { namespace: "product" }, to: { namespace: "product" },
      sync: true,
      leave: ({ current }) => gsap.to(current.container, { x: "-100%", duration: 0.6 }),
      enter: ({ next }) => { gsap.set(next.container, { x: "100%" }); return gsap.to(next.container, { x: "0%", duration: 0.6 }); } },
    { name: "default", /* fallback, always matches -- keep one of these last */
      leave: ({ current }) => gsap.to(current.container, { opacity: 0, duration: 0.4 }),
      enter: ({ next }) => gsap.from(next.container, { opacity: 0, duration: 0.4 }) }
  ]
});
```

## Views -- page-specific init/cleanup, separate from the transition itself

```javascript
barba.init({
  views: [{
    namespace: "home",
    afterEnter() { initHomeSlider(); },
    beforeLeave() { destroyHomeSlider(); } // clean up before leaving, not after
  }]
});
```

## Global hooks -- for behavior that applies to every navigation

```javascript
barba.hooks.beforeEnter(() => window.scrollTo(0, 0)); // reset scroll every time
barba.hooks.after(({ next }) => gtag("config", "GA_ID", { page_path: next.url.path })); // analytics
```

## Pitfalls that actually bite

- **Not returning a promise** -- covered above, the #1 issue.
- **Flash of unstyled/visible content on enter** -- set the initial state
  (`opacity: 0` etc.) in `beforeEnter`, not inside `enter` itself, or the
  new container flashes visible for a frame before the animation starts.
- **Sync transitions without absolute positioning** -- during a crossfade
  both containers exist in the DOM simultaneously; without
  `position: absolute` on `[data-barba="container"]` they stack and shift
  layout. Add the CSS or position them in `beforeLeave`.
- **ScrollTrigger instances surviving navigation** -- if this site also
  uses GSAP ScrollTrigger in-page, kill triggers in `beforeLeave`:
  `ScrollTrigger.getAll().forEach(t => t.kill())`. Otherwise triggers from
  the old page keep firing against the new page's DOM.
- **Third-party widgets not re-initializing** -- anything that runs once on
  `DOMContentLoaded` (syntax highlighting, social embeds) needs to be
  re-run in `barba.hooks.afterEnter`, since Barba never reloads the page.

## Integration

Pair with GSAP for the leave/enter animation itself (see
`gsap-scrolltrigger.md` for timeline/stagger patterns -- the same timeline
techniques apply here, just triggered by Barba's hooks instead of scroll
position). Can be combined with Locomotive Scroll for smooth in-page scroll
that also gets page-transition treatment on navigation.
