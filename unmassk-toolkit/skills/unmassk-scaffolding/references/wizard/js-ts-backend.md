## JavaScript/TypeScript Backend

### Express

#### Features
- TypeScript *recommended*
- ESLint + Prettier

#### Project Structure
- Simple (single file)
- Standard (routes/, controllers/, services/) *recommended*
- Domain-driven

#### Database/ORM
- None
- Prisma *recommended*
- Drizzle
- TypeORM
- Sequelize

#### Authentication
- None
- Passport.js *recommended*
- Custom JWT

#### Validation
- Zod *recommended*
- Joi
- express-validator

### NestJS

#### Features
- TypeScript *default*
- Strict mode *default*

#### Database/ORM
- Prisma *recommended*
- TypeORM
- Sequelize
- Mongoose (MongoDB)

#### Authentication
- @nestjs/passport *recommended*
- Custom guards

#### API Style
- REST *default*
- GraphQL (@nestjs/graphql)
- gRPC

#### Microservices
- None (monolith)
- @nestjs/microservices

### Fastify

#### Features
- TypeScript *recommended*
- Schema validation (JSON Schema)

#### Plugins
- @fastify/cors
- @fastify/jwt
- @fastify/swagger

### Hono

#### Runtime
- Node.js
- Bun *recommended*
- Cloudflare Workers
- Deno

#### Features
- TypeScript *default*
- Zod validation
- JWT middleware

### Elysia

#### Runtime
- Bun *required*

#### Features
- TypeScript *default*
- End-to-end type safety
- Swagger/OpenAPI

### tRPC

#### Framework Integration
- Next.js *recommended*
- Express
- Fastify
- Standalone

#### Features
- Zod validation *default*
- React Query integration
- Subscriptions (WebSocket)

### Koa

#### Features
- TypeScript *recommended*
- Middleware-based

#### Common Middleware
- koa-router
- koa-bodyparser
- koa-jwt
