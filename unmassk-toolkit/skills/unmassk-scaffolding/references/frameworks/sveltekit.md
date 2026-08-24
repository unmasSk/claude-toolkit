### SvelteKit

#### Recommended Stack
```
Version:        2.x
Language:       TypeScript
Styling:        Tailwind CSS
State:          Svelte stores
```

#### Project Structure
```
my-sveltekit-app/
├── src/
│   ├── lib/
│   │   ├── components/
│   │   ├── stores/
│   │   └── utils/
│   ├── routes/
│   │   ├── +layout.svelte
│   │   ├── +page.svelte
│   │   └── api/
│   └── app.html
├── static/
├── tests/
├── svelte.config.js
├── vite.config.ts
└── package.json
```

#### SvelteKit Routing

```
routes/
├── +page.svelte              → /
├── +layout.svelte            → Layout for all pages
├── about/+page.svelte        → /about
├── blog/
│   ├── +page.svelte          → /blog
│   └── [slug]/+page.svelte   → /blog/:slug
└── api/
    └── users/+server.ts      → /api/users
```
