### FastAPI

#### Recommended Stack
```
Python:         3.14+
Async:          Full async/await
Database:       PostgreSQL + asyncpg
ORM:            SQLAlchemy 2.0 (async)
Migrations:     Alembic
Validation:     Pydantic v2
Auth:           python-jose (JWT)
Testing:        pytest-asyncio + httpx
```

#### Project Structure (Large-Scale)
```
my-fastapi-app/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── users.py
│   │   │   │   └── items.py
│   │   │   └── __init__.py
│   │   └── deps.py          # Dependencies
│   ├── core/
│   │   ├── config.py        # Pydantic Settings
│   │   ├── security.py      # JWT, hashing
│   │   └── exceptions.py
│   ├── db/
│   │   ├── session.py       # Database session
│   │   ├── base.py          # SQLAlchemy Base
│   │   └── models/
│   ├── schemas/             # Pydantic models
│   ├── services/            # Business logic
│   ├── crud/                # Database operations
│   └── main.py
├── alembic/
│   ├── versions/
│   └── env.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── alembic.ini
├── pyproject.toml
├── requirements.txt
└── Dockerfile
```

#### Configuration with Pydantic Settings

```python
# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # App
    PROJECT_NAME: str = "My API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]


settings = Settings()
```

#### Async SQLAlchemy 2.0

```python
# app/db/session.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

#### Dependency Injection Pattern

```python
# app/api/deps.py
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security import decode_token
from app.crud import user as user_crud

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str, Depends(oauth2_scheme)],
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    user = await user_crud.get_by_id(db, id=payload.sub)
    if user is None:
        raise credentials_exception

    return user
```
