from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import init_db
from app.routers.bookings import router as bookings_router
from app.routers.slots import router as slots_router
from app.routers.ui import router as ui_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENVIRONMENT.lower() != "production":
        init_db()
    yield


app = FastAPI(
    title="Koya Clinic Booking API",
    version="1.0.0",
    description="Clinic appointment booking service with slot management, bookings, idempotency, pagination, and rate limiting.",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    message = exc.errors()[0].get("msg", "Invalid request") if exc.errors() else "Invalid request"
    return JSONResponse(status_code=400, content={"error": message})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        message = detail.get("error", "Request failed")
    elif isinstance(detail, list):
        message = detail[0].get("msg", "Request failed") if detail and isinstance(detail[0], dict) else "Request failed"
    else:
        message = str(detail) if detail else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": message},
        headers=getattr(exc, "headers", None) or {},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


app.include_router(slots_router)
app.include_router(bookings_router)
app.include_router(ui_router)

static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(str(static_dir / "index.html"))

