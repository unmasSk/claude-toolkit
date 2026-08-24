### NestJS

#### Recommended Stack
```
Language:       TypeScript
ORM:            Prisma or TypeORM
Validation:     class-validator
Auth:           @nestjs/passport
Testing:        Jest
```

#### Project Structure
```
my-nestjs-app/
├── src/
│   ├── modules/
│   │   ├── users/
│   │   │   ├── users.module.ts
│   │   │   ├── users.controller.ts
│   │   │   ├── users.service.ts
│   │   │   ├── dto/
│   │   │   └── entities/
│   │   └── auth/
│   ├── common/
│   │   ├── decorators/
│   │   ├── filters/
│   │   ├── guards/
│   │   └── interceptors/
│   ├── config/
│   ├── app.module.ts
│   └── main.ts
├── test/
├── nest-cli.json
├── tsconfig.json
└── package.json
```
