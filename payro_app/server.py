"""`make payro`: the fictional PayRo app on http://127.0.0.1:8001, reading the sandbox repository of the demo state.

No login, local only. It never writes to the repository and does not touch the coLEX database.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from colex import settings
from payro_app import views
from payro_app.runner import PayroRepo

HOST = "127.0.0.1"


def create_app(repo: PayroRepo) -> FastAPI:
    app = FastAPI(title="PayRo demo app (fictional)", docs_url=None, redoc_url=None)

    @app.get("/")
    def home(request: Request):
        return HTMLResponse(views.page(repo, dict(request.query_params)))

    return app


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PAYRO_PORT", "8001"))
    repo = PayroRepo(settings.var_dir() / "repo", settings.ROOT / "var" / "payro_cache")
    print(f"PayRo demo app (FICTIONAL): http://{HOST}:{port}  ·  repository: {repo.repo}", flush=True)
    uvicorn.run(create_app(repo), host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
