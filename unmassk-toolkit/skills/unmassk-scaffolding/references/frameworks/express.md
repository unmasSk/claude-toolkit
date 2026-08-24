### Express.js

#### Recommended Stack
```
Language:       TypeScript
Runtime:        Node.js 24+
ORM:            Prisma or Drizzle
Validation:     Zod
Auth:           Passport.js or custom JWT
Testing:        Vitest + Supertest
```

#### Project Structure
```
my-express-api/
├── src/
│   ├── routes/
│   │   ├── index.ts
│   │   ├── users.ts
│   │   └── auth.ts
│   ├── controllers/
│   ├── middleware/
│   │   ├── auth.ts
│   │   ├── validate.ts
│   │   └── errorHandler.ts
│   ├── services/
│   ├── models/
│   ├── schemas/            # Zod schemas
│   ├── utils/
│   ├── config/
│   ├── app.ts
│   └── index.ts
├── prisma/
├── tests/
├── tsconfig.json
└── package.json
```

#### Middleware Pattern

```typescript
// src/middleware/validate.ts
import { Request, Response, NextFunction } from 'express';
import { ZodSchema } from 'zod';

export const validate = (schema: ZodSchema) => {
  return (req: Request, res: Response, next: NextFunction) => {
    try {
      schema.parse({
        body: req.body,
        query: req.query,
        params: req.params,
      });
      next();
    } catch (error) {
      res.status(400).json({ error: 'Validation failed', details: error });
    }
  };
};
```
