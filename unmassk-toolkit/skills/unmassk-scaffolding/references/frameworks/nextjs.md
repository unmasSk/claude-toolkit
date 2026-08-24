### Next.js

#### Recommended Stack
```
Version:        16+ with App Router
Language:       TypeScript (strict)
Styling:        Tailwind CSS
Database:       Prisma or Drizzle
Auth:           NextAuth.js v5 (Auth.js)
Validation:     Zod
Testing:        Vitest + Playwright
```

#### Project Structure (App Router)
```
my-nextjs-app/
├── src/
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── (dashboard)/
│   │   │   └── dashboard/page.tsx
│   │   ├── api/
│   │   │   ├── auth/[...nextauth]/route.ts
│   │   │   └── users/route.ts
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── ui/
│   │   └── features/
│   ├── lib/
│   │   ├── auth.ts
│   │   ├── db.ts
│   │   └── utils.ts
│   ├── hooks/
│   └── types/
├── prisma/
│   ├── schema.prisma
│   └── migrations/
├── public/
├── tests/
├── next.config.ts
└── package.json
```

#### Server Components vs Client Components

```typescript
// Server Component (default) - runs on server
// app/users/page.tsx
import { prisma } from '@/lib/db';

export default async function UsersPage() {
  const users = await prisma.user.findMany();
  return <UserList users={users} />;
}

// Client Component - runs on client
// components/features/UserForm.tsx
'use client';

import { useState } from 'react';

export function UserForm() {
  const [name, setName] = useState('');
  // Client-side interactivity
}
```

#### Server Actions

```typescript
// app/actions.ts
'use server';

import { prisma } from '@/lib/db';
import { revalidatePath } from 'next/cache';

export async function createUser(formData: FormData) {
  const name = formData.get('name') as string;

  await prisma.user.create({
    data: { name },
  });

  revalidatePath('/users');
}
```
