# Koya Clinic Booking API

A production-minded FastAPI clinic booking system that stores data in PostgreSQL, protects endpoints with API keys, prevents double-booking with database constraints, supports idempotent retries, rate limits booking attempts per email, and serves a responsive frontend.

## Local setup

1. Create and activate a virtual environment:
   - Windows PowerShell:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   - macOS/Linux:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a local environment file:
   ```bash
   copy .env.example .env
   ```
   or on Linux/macOS:
   ```bash
   cp .env.example .env
   ```
4. Update `.env` with your secrets and database URL.

## Environment variables

Use the following values in `.env`:

```env
ENVIRONMENT=development
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/clinic_booking_db
API_KEY=replace_with_a_long_random_secret
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

Do not commit `.env` to GitHub.

## Neon PostgreSQL setup

1. Create a Neon project and database.
2. Copy the connection string from the Neon dashboard.
3. Set `DATABASE_URL` in `.env` to that Postgres URL.
4. Ensure the database user has permission to create tables and run migrations.

## Database migrations

```bash
alembic upgrade head
```

If you need to create a revision:

```bash
alembic revision --autogenerate -m "describe change"
```

## Start the application

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Run tests

```bash
pytest -q
```

## API usage

The API requires an `X-API-Key` header on every protected endpoint.

```bash
curl -H "X-API-Key: replace_with_a_long_random_secret" http://localhost:8000/slots
```

### Protected endpoints

- `POST /reset`
- `GET /slots`
- `POST /bookings`
- `GET /bookings`
- `GET /bookings/{id}`
- `DELETE /bookings/{id}`

### Optional idempotency

Send the `Idempotency-Key` header to safely retry identical booking requests.

```bash
curl -X POST http://localhost:8000/bookings \
  -H "X-API-Key: replace_with_a_long_random_secret" \
  -H "Idempotency-Key: booking-123" \
  -H "Content-Type: application/json" \
  -d '{"slot_id":"slot-001","name":"Ada Obi","email":"ada@example.com"}'
```

### Booking history

```bash
curl "http://localhost:8000/bookings?email=ada@example.com&limit=10" \
  -H "X-API-Key: replace_with_a_long_random_secret"
```

## Frontend

The frontend is served at the root URL `/` and uses same-origin server routes under `/api/ui/*` that call the shared application services without exposing the API key in JavaScript.

## Render deployment

1. Push the repository to GitHub.
2. Create a new Render Web Service.
3. Connect the repository.
4. Select the service type `Web Service` and use the project root.
5. Add environment variables in Render:
   - `DATABASE_URL`
   - `API_KEY`
   - `ENVIRONMENT=production`
   - `ALLOWED_ORIGINS=https://your-render-domain.onrender.com`
6. Render will use the included `render.yaml` file.
7. The deploy step runs `pip install -r requirements.txt` and `alembic upgrade head` before starting the app.
8. Start command:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

## API documentation

Open the Swagger UI at:

```text
http://localhost:8000/docs
```

The OpenAPI JSON is available at:

```text
http://localhost:8000/openapi.json
```

## Deployment URL

After deployment, the public base URL is the Render service URL, for example:

```text
https://clinic-booking-api.onrender.com
```

## Security notes

- Never hardcode or expose the API key in browser code.
- Never commit `.env` or production secrets.
- All official API endpoints require `X-API-Key`.
- `/reset` is not exposed in the public UI.
