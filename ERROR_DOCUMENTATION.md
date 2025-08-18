# Error Documentation for the Geo-Adaptive Energy Assistant

This document provides a detailed breakdown of the errors encountered while setting up and running the Geo-Adaptive Energy Assistant. It is intended to serve as a guide for future developers to avoid these pitfalls and to provide a clear understanding of the system's dependencies and configuration.

## 1. Mock Data Issue

### Symptom

The application consistently returns mock data, including `example.com` URLs, instead of real data from the backend services.

### Root Cause

The `QueryOrchestrator` in the `Gateway` service is designed to fall back to a mock data provider if it cannot connect to a healthy `Retriever` service. The `Retriever` service, in turn, depends on a healthy database connection. The problem is that the database was not set up. Because of this, the `Retriever` service was reporting itself as "unhealthy," which is causing the `QueryOrchestrator` to fall back to using mock data.

### Solution

The solution is to set up the database and ensure that all services are running with the correct configuration. This involves the following steps:

1.  **Set up the database.** Execute the `scripts/setup-database.py` script to create the necessary tables and seed them with initial data.
2.  **Restart all services.** Restart all the backend services to ensure that they are all running with the newly configured database.
3.  **Restart the frontend application.** Restart the frontend application to ensure that it is communicating with the newly updated backend.
4.  **Verify the fix.** Test the application to confirm that it is using real data from the database.

## 2. Database Connection Issues

### Symptom

The `scripts/setup-database.py` script fails with a "connection refused" error.

### Root Cause

The script is attempting to connect to a PostgreSQL database on `localhost`, but there is no database server running to accept the connection.

### Solution

The solution is to use the application's built-in SQLite fallback mechanism. This allows the application to run with a local SQLite database, which is created automatically and does not require a separate database server. To enable the SQLite fallback, the `services/database/connection_manager.py` file was modified to force the use of the SQLite fallback.

## 3. Dependency Issues

### Symptom

The `scripts/start-services.py` script fails with `ModuleNotFoundError` for various packages, including `asyncpg`, `pydantic_settings`, `google.cloud.aiplatform`, `psycopg`, and `psycopg_pool`.

### Root Cause

The project's Python dependencies are not fully installed in the virtual environment.

### Solution

The solution is to install the missing dependencies using `pip`. The following commands were used to resolve the dependency issues:

```bash
pip install asyncpg
pip install pydantic_settings
pip install google-cloud-aiplatform --upgrade
pip install psycopg
pip install psycopg_pool
pip install psycopg-binary
```

## 4. `start-services.py` Script Issues

### Symptom

The `scripts/start-services.py` script fails to start the backend services, and the services do not remain active.

### Root Cause

The script has two issues:

1.  It does not correctly load the `.env` file, which means that the `ENABLE_REAL_APIS` environment variable is not being set.
2.  It is designed to shut down all services when it receives a `KeyboardInterrupt` signal.

### Solution

The solution is to modify the script to correctly load the `.env` file and to remove the signal handler. This will allow the services to continue running in the background. The following changes were made to the script:

*   The `dotenv` module was used to load the `.env` file.
*   The `signal.signal(signal.SIGINT, signal_handler)` line was commented out.
*   The `except KeyboardInterrupt:` block was changed to `except KeyboardInterrupt: pass`.
