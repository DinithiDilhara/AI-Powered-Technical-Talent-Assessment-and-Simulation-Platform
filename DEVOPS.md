
# TalentForge - DevOps Setup

## Technology Stack
- Frontend: React + Vite
- Backend: FastAPI
- Database: PostgreSQL 17
- Containerization: Docker Compose
- CI: GitHub Actions

## Prerequisites
- Git
- Docker Desktop
- Docker Compose

## Local Setup

1. Clone the repository.
2. Create a `.env` file in the project root.
3. Configure a secure `JWT_SECRET_KEY`.
4. Start the application:

```powershell
docker compose -f compose.yaml up -d --build
```

## Application URLs

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Verify Services

```powershell
docker compose -f compose.yaml ps
```

## Backend Health Check

```powershell
Invoke-RestMethod http://localhost:8000/health
```

## Database Connection Check

```powershell
Invoke-RestMethod http://localhost:8000/db-test
```

## Important Database Note

The current database schema references the `users` table.

The official `users` table creation SQL must be included before
fresh PostgreSQL initialization can work reliably.

Existing PostgreSQL volumes are not automatically reinitialized.

Do not use `docker compose down -v` unless database data deletion
is explicitly intended.
