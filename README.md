# CoLogi

CoLogi is a Django REST Framework backend for collaborative delivery-demand
management.

This repository currently contains the Django backend, PostgreSQL development
database configuration, automated tests, health endpoints, and API documentation.

## 1. Technology Stack

| Component | Version / Technology |
|---|---|
| Python | 3.14.2 (validated development runtime) |
| Django | 5.2.19 |
| Django REST Framework | 3.17.2 |
| PostgreSQL | 17.11 |
| Psycopg | 3.3.8 |
| drf-spectacular | 0.30.0 |
| pytest | 9.2.0 |
| pytest-django | 4.14.0 |

Dependencies are pinned in `requirements.txt`.

## 2. Repository Structure

```text
cologi/
├── backend/
│   ├── accounts/          # Authentication, users, roles and access scopes
│   ├── demands/           # Delivery Demand APIs and business services
│   ├── masterdata/        # Master data models
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── dev.py
│   │   │   └── prod.py
│   │   ├── health.py
│   │   └── urls.py
│   └── manage.py
├── docs/
│   └── source/
│       └── CoLogi_Dataset_v7.xlsx
├── .env.example
├── compose.yaml
├── pytest.ini
├── requirements.txt
└── README.md
```

The current Docker Compose configuration starts PostgreSQL only.
The Django backend runs directly in the development environment.

## 3. Prerequisites

Install or provide:

- Python compatible with the pinned dependencies.
- Docker and Docker Compose.
- Git.

The development environment has been validated with Python 3.14.2.

## 4. Local Environment Setup

Run commands from the repository root.

Create and activate a virtual environment:

```bash
python --version
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Create the local environment file:

```bash
cp .env.example .env
```

Generate a strong Django secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Copy the generated value into `DJANGO_SECRET_KEY` in `.env`.
Do not commit `.env` or share its contents.

### Environment Variables

| Variable | Purpose | Development example |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django secret key | Generate a unique random value |
| `DJANGO_DEBUG` | Development debug mode | `True` |
| `DJANGO_ALLOWED_HOSTS` | Allowed host names | `localhost,127.0.0.1` |
| `DJANGO_LOG_LEVEL` | Console logging level | `INFO` |
| `POSTGRES_DB` | PostgreSQL database name | `cologi` |
| `POSTGRES_USER` | PostgreSQL username | `cologi` |
| `POSTGRES_PASSWORD` | PostgreSQL password | Set a local secure password |
| `POSTGRES_HOST` | PostgreSQL hostname | `localhost` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |

The Django settings load the root `.env` file. Environment variables already
defined by the process take precedence over values in `.env`.

For Codespaces, add the forwarded application hostname to
`DJANGO_ALLOWED_HOSTS` when necessary. Specify the hostname only, without
the URL scheme. Do not use `*` as a workaround.

## 5. Start PostgreSQL

The Compose file defines one service: `db`.

Start it:

```bash
docker compose up -d db
```

Check container status:

```bash
docker compose ps
```

Inspect PostgreSQL logs:

```bash
docker compose logs -f db
```

Wait until the database healthcheck reports `healthy`.

The database container uses the named volume `cologi_postgres_data` to
persist PostgreSQL data.

To stop the database without deleting its persisted data:

```bash
docker compose down
```

Do not use `docker compose down -v` unless intentionally deleting the
database volume and its data.

### Database Host

The Django backend currently runs on the host environment, not inside Compose.
Therefore, the development `.env` uses:

```text
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

If the backend is later containerized, its database hostname and network
configuration must be updated accordingly.

## 6. Database Migrations

Run Django management commands from `backend/`:

```bash
cd backend
source ../.venv/bin/activate
python manage.py showmigrations
```

Apply migrations when initializing or updating a development database:

```bash
python manage.py migrate
```

Check for model changes that do not have migrations:

```bash
python manage.py makemigrations --check --dry-run
```

Check whether unapplied migrations remain:

```bash
python manage.py migrate --check
```

Review migration status before applying changes to any shared or production
database. Do not use migrations as a substitute for importing or validating
business master data.

## 7. Run the Django Backend

From `backend/` with the virtual environment activated:

```bash
python manage.py runserver 0.0.0.0:8000
```

`manage.py` defaults to `config.settings.dev`.

The server listens on port `8000`. In Codespaces, open or forward that port
through the Codespaces Ports interface.

The Django development server is for local development only. Do not use
`runserver` as the production application server.

## 8. Django Technical Superuser

When a technical Django administrator is required:

```bash
cd backend
python manage.py createsuperuser
```

Follow the prompts for the custom user model.

A Django superuser is a technical administrative identity. It is not equivalent
to assigning a CoLogi business role, outlet scope, Supplier identity, or
Transport Provider identity. Those business relationships must be managed
through their respective application models and authorized workflows.

## 9. Run Automated Tests

Run pytest from the repository root:

```bash
cd /workspaces/cologi
source .venv/bin/activate
pytest -q
```

The root `pytest.ini` configures:

- `DJANGO_SETTINGS_MODULE=config.settings.dev`
- `backend` as the Python import path
- Test file patterns `tests.py`, `test_*.py`, and `*_tests.py`

Run individual configuration tests:

```bash
pytest -q backend/config/test_health.py
pytest -q backend/config/test_logging.py
pytest -q backend/config/test_api_docs.py
```

## 10. Django Checks and OpenAPI Validation

Run the development system check:

```bash
cd backend
python manage.py check --settings=config.settings.dev
```

Validate the generated OpenAPI schema:

```bash
python manage.py spectacular \
  --validate \
  --file /tmp/cologi-openapi.yaml
```

Check migration drift:

```bash
python manage.py makemigrations --check --dry-run
```

For production settings, configure a strong `DJANGO_SECRET_KEY` and explicit
`DJANGO_ALLOWED_HOSTS` before running:

```bash
python manage.py check --deploy --settings=config.settings.prod
```

Production checks must be reviewed in the context of the actual HTTPS and
reverse-proxy deployment. Do not enable HSTS or HTTPS redirect blindly in a
development environment.

## 11. Health Endpoints

These endpoints are public and do not require an authentication token.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health/live/` | Application liveness; does not query the database |
| GET | `/api/health/ready/` | Database readiness; executes `SELECT 1` |

Example checks:

```bash
curl -i http://127.0.0.1:8000/api/health/live/
curl -i http://127.0.0.1:8000/api/health/ready/
```

Readiness returns HTTP `200` when the database query succeeds and HTTP `503`
when the database is unavailable. The response does not expose connection
details or exception messages.

## 12. API Documentation

The API documentation routes are public.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/schema/` | OpenAPI schema |
| GET | `/api/docs/swagger/` | Swagger UI |
| GET | `/api/docs/redoc/` | Redoc |

Open the Swagger UI or Redoc page in a browser after starting Django.

The current OpenAPI schema describes the Authentication and Demand API
operations. It does not imply that every model or future module has a
published API.

## 13. Current API Routes

### Authentication

| Method | Endpoint | Authentication |
|---|---|---|
| POST | `/api/auth/login/` | Public |
| POST | `/api/auth/logout/` | Token required |
| GET | `/api/auth/me/` | Token required |

Login accepts an email and password. A successful login returns a token.
Pass that token on authenticated requests using:

```text
Authorization: Token <token>
```

Logout revokes the authenticated token.

### Delivery Demands

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/demands/` | List accessible demands |
| POST | `/api/demands/` | Create a draft demand |
| GET | `/api/demands/{id}/` | Retrieve a demand |
| PATCH | `/api/demands/{id}/` | Update an editable draft |
| GET | `/api/demands/{id}/status/` | Retrieve demand status |
| POST | `/api/demands/{id}/submit` | Submit a demand |
| POST | `/api/demands/{id}/select-supplier` | Explicit supplier selection |

All Demand endpoints require token authentication and apply the relevant
business-role and outlet-scope permissions.

The submit and select-supplier routes intentionally have no trailing slash
in the current URL configuration.

Master data models exist, but this README does not imply that a complete
Master Data management API is available.

## 14. Logging

Application logs are written to standard output.

| Setting | Default |
|---|---|
| Development log level | `INFO` |
| Production log level | `WARNING` |
| Override | `DJANGO_LOG_LEVEL` |

The application logger is named `cologi`.

Do not log passwords, authentication tokens, secret keys, database credentials,
or sensitive request bodies. SQL debug logging is not enabled by default.

## 15. Production Deployment Notes

The production settings module is `config.settings.prod`.

It enforces:

- `DEBUG=False`.
- A configured, non-insecure `DJANGO_SECRET_KEY`.
- Explicit `DJANGO_ALLOWED_HOSTS` values; wildcard hosts are rejected.

The current repository is not, by itself, a complete production deployment
solution. Before production release, review and implement the deployment
requirements appropriate to the target infrastructure, including:

- HTTPS termination and reverse-proxy configuration.
- HSTS and secure cookie settings after HTTPS is correctly deployed.
- Production application server and process management.
- Static asset serving.
- Secret and database credential management.
- Database backup, restore, monitoring, and operational procedures.
- Production `check --deploy` results.

The Compose configuration currently starts PostgreSQL only; it does not
provide a production Django application service.

## 16. Troubleshooting

### Django cannot connect to PostgreSQL

1. Check `docker compose ps`.
2. Confirm the database container is healthy.
3. Check `POSTGRES_HOST`, `POSTGRES_PORT`, database name, username, and password
   in the local environment.
4. Confirm that the host port is not already occupied.

### PostgreSQL reports password authentication failure

The credentials used by Django must match the credentials used to initialize
the PostgreSQL database volume. Changing `.env` does not automatically change
the password of an already initialized database volume.

### Django reports DisallowedHost

Add the actual request hostname to `DJANGO_ALLOWED_HOSTS`. Do not use `*` to
disable host validation.

### `spectacular` command is unavailable

Confirm that the virtual environment is active, `drf-spectacular` is installed,
and `drf_spectacular` is registered in `INSTALLED_APPS`.

### Tests cannot import project modules

Run pytest from the repository root and activate `.venv`. The root
`pytest.ini` supplies the `backend` Python path.

### Port 5432 or 8000 is already in use

Identify the process using the port or change the local port configuration
consistently. When changing PostgreSQL's host port, update `POSTGRES_PORT`
for Django as well.

## 17. Development Safety Rules

- Keep `.env`, credentials, tokens, and private keys out of Git.
- Do not commit generated local database files or virtual environments.
- Do not run destructive database commands without reviewing their impact.
- Do not import demo or fixture data into a shared database without approval.
- Keep business rules in application services and validate API behavior with
  automated tests.
- Treat passing unit tests, HTTP runtime verification, and production
  deployment verification as separate evidence levels.
