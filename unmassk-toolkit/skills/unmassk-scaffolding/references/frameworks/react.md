### React (with Vite)

#### Recommended Stack
```
Build Tool:     Vite (fast HMR, ESM-native)
Language:       TypeScript (strict mode)
Styling:        Tailwind CSS
State:          Zustand or TanStack Query
Routing:        React Router v7 or TanStack Router
Forms:          React Hook Form + Zod
Testing:        Vitest + React Testing Library
```

#### Project Structure
```
my-react-app/
├── src/
│   ├── components/
│   │   ├── ui/              # Reusable UI (Button, Card, Modal)
│   │   └── features/        # Feature-specific components
│   ├── hooks/               # Custom React hooks
│   ├── lib/                 # Utilities, API clients
│   ├── stores/              # State management
│   ├── types/               # TypeScript types
│   ├── styles/              # Global styles
│   ├── App.tsx
│   └── main.tsx
├── public/
├── tests/
│   ├── unit/
│   └── e2e/
├── eslint.config.js
├── .prettierrc
├── tsconfig.json
├── vite.config.ts
└── package.json
```

#### Key Configuration Files

**vite.config.ts**
```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
  },
});
```

**tsconfig.json**
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["DOM", "DOM.Iterable", "ES2022"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
```

#### State Management Options

| Library | Best For | Bundle Size |
|---------|----------|-------------|
| Zustand | Simple global state | ~1KB |
| Jotai | Atomic state | ~2KB |
| Redux Toolkit | Complex apps, time-travel | ~11KB |
| TanStack Query | Server state | ~12KB |

#### Data Fetching Patterns

```typescript
// TanStack Query (recommended)
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: () => fetch('/api/users').then(r => r.json()),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (user: User) =>
      fetch('/api/users', { method: 'POST', body: JSON.stringify(user) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
}
```
