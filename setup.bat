@echo off
setlocal
title Clinic Booking API - Project Setup

REM Run this script from any location; all paths are relative to this file.
cd /d "%~dp0"

echo.
echo ==========================================
echo   Clinic Booking API - Project Structure
echo ==========================================
echo.

REM Create application directories
for %%D in (
    "app"
    "app\routers"
    "app\services"
    "static"
    "tests"
) do (
    if not exist "%%~D" mkdir "%%~D"
)

REM Create Python package markers
for %%F in (
    "app\__init__.py"
    "app\routers\__init__.py"
    "app\services\__init__.py"
) do (
    if not exist "%%~F" type nul > "%%~F"
)

REM Create application modules
for %%F in (
    "app\main.py"
    "app\config.py"
    "app\database.py"
    "app\models.py"
    "app\schemas.py"
    "app\dependencies.py"
    "app\routers\slots.py"
    "app\routers\bookings.py"
    "app\services\booking_service.py"
    "app\services\idempotency.py"
    "app\services\rate_limiter.py"
) do (
    if not exist "%%~F" type nul > "%%~F"
)

REM Create frontend files
for %%F in (
    "static\index.html"
    "static\styles.css"
    "static\app.js"
) do (
    if not exist "%%~F" type nul > "%%~F"
)

REM Create test files
for %%F in (
    "tests\__init__.py"
    "tests\conftest.py"
    "tests\test_slots.py"
    "tests\test_bookings.py"
    "tests\test_concurrency.py"
    "tests\test_idempotency.py"
    "tests\test_rate_limiting.py"
) do (
    if not exist "%%~F" type nul > "%%~F"
)

REM Create root configuration/documentation files without overwriting existing files
for %%F in (
    "requirements.txt"
    ".env.example"
    "README.md"
    "render.yaml"
) do (
    if not exist "%%~F" type nul > "%%~F"
)

echo Project structure created successfully.
echo Existing files were left unchanged.
echo.
echo Next steps:
echo   1. Open this folder in VS Code.
echo   2. Create a virtual environment: py -m venv .venv
echo   3. Activate it: .venv\Scripts\activate
echo   4. Install dependencies after requirements.txt is populated:
echo      pip install -r requirements.txt
echo.
pause
endlocal
