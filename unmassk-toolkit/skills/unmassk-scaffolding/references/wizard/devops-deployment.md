## DevOps & Deployment

### Version Control
- Initialize Git repository *default*
- Add .gitignore *default*
- Create initial commit *default*

### CI/CD
- GitHub Actions *recommended*
- GitLab CI
- None

### Containerization
- Dockerfile (multi-stage) *recommended*
- docker-compose.yml *recommended*
- None

### Deployment Targets

| Target | Best For |
|--------|----------|
| GitHub Pages | Static HTML/CSS |
| Netlify | Static/JAMstack |
| Vercel | Next.js, frontend |
| Railway | Full-stack, databases |
| Fly.io | Containers, edge |
| AWS (ECS/Lambda) | Enterprise |
| Google Cloud Run | Containers |
| Self-hosted | Full control |

### Environment Management
- .env.example template *default*
- Config validation (Zod/Pydantic) *recommended*

### Monitoring
- Structured logging
- Error tracking (Sentry)
- None
