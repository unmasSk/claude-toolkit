## Python Backend

### FastAPI

#### Project Structure
- Simple (single main.py)
- Standard (app/ directory) *recommended*
- Large-scale (domain-driven)

#### Database
- None
- SQLite (development)
- PostgreSQL *recommended*
- MySQL
- MongoDB

#### ORM
- SQLAlchemy 2.0 *recommended*
- SQLModel
- Tortoise ORM
- Beanie (MongoDB)

#### Authentication
- None
- JWT with python-jose *recommended*
- OAuth2 with authlib
- Session-based

#### Additional Features
- Background tasks (Celery/ARQ)
- WebSocket support
- GraphQL (Strawberry)
- Redis caching

### Django

#### API Framework
- Django REST Framework *recommended*
- Django Ninja

#### Features
- Custom User model *recommended*
- Celery for background tasks
- Channels (WebSocket)

#### Database
- PostgreSQL *recommended*
- MySQL
- SQLite (dev)

#### Authentication
- Django Allauth *recommended*
- Simple JWT
- Session-based

### Flask

#### Extensions
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-JWT-Extended
- Flask-CORS

### Litestar

#### Features
- Async-first
- Msgspec/Pydantic validation
- SQLAlchemy integration
