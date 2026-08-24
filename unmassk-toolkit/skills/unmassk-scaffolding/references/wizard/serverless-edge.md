## Serverless & Edge

### AWS Lambda

#### Runtime
- Node.js 24 *recommended*
- Python 3.14
- Go
- Rust (custom runtime)

#### Framework
- SST *recommended*
- Serverless Framework
- SAM
- CDK

#### Features
- API Gateway
- DynamoDB
- S3 triggers
- EventBridge

### Cloudflare Workers

#### Framework
- Hono *recommended*
- Itty Router
- None (Fetch API)

#### Features
- KV storage
- D1 (SQLite)
- R2 (object storage)
- Durable Objects

### Vercel Functions

#### Runtime
- Node.js *default*
- Edge Runtime

#### Features
- Next.js API routes
- Edge middleware
- Cron jobs

### Supabase Functions

#### Runtime
- Deno *default*

#### Features
- Database access
- Auth integration
- Edge deployment
