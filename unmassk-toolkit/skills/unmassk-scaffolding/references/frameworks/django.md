### Django

#### Recommended Stack
```
Version:        5.1+
API:            Django REST Framework
Database:       PostgreSQL
Auth:           Django Allauth (social)
Background:     Celery + Redis
Testing:        pytest-django
```

#### Project Structure
```
my-django-project/
├── config/                  # Project settings
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── core/               # Shared utilities
│   ├── users/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   └── tests/
│   └── api/
├── static/
├── media/
├── templates/
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── manage.py
└── docker-compose.yml
```

#### Custom User Model (Always Do This)

```python
# apps/users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
```

```python
# config/settings/base.py
AUTH_USER_MODEL = 'users.User'
```
