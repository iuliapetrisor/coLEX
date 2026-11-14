"""Console web app: pages plus a small JSON API.

The Console has NO authentication: anyone who can reach it can answer questions and approve changes.
The server binds to 127.0.0.1 only. Do not expose it on a network.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from colex import db
from colex.api import actions, pages_admin, pages_map, pages_picture, pages_registers, pages_run, pages_runs
from colex.api.html import page
from colex.map import registers
from colex.map import store as map_store
from colex.runtime import audit


def create_app(engine, deps) -> FastAPI:
    app = FastAPI(title="coLEX Console", docs_url=None, redoc_url=None)

    def drive(run_id: str) -> None:
        """Continue a run: in the background when the engine has a worker, inline otherwise (tests)."""
        if engine._pool:
            engine.kick(run_id)
        else:
            engine.drive(run_id)

    def html(fn, *args) -> HTMLResponse:
        try:
            return HTMLResponse(fn(*args))
        except KeyError as exc:
            return HTMLResponse(page("Not found", f"<p>Unknown: {exc}</p>"), status_code=404)

    @app.get("/")
    def index():
        return html(pages_runs.index)

    @app.get("/runs/{run_id}")
    def run(run_id: str):
        return html(pages_run.run, run_id)

    @app.get("/changes/{wait_id:path}")
    def change(wait_id: str):
        return html(pages_runs.change, wait_id)

    @app.get("/feed")
    def feed():
        return html(pages_admin.feed)

    @app.get("/slack")
    def slack():
        return html(pages_admin.slack)

    @app.get("/settings")
    def settings_page():
        return html(pages_admin.settings_page)

    @app.get("/map")
    def explorer(path: str | None = None):
        return html(pages_map.explorer, path)

    @app.get("/map/picture")
    def map_picture(run: str | None = None):
        return html(pages_picture.picture, run)

    @app.get("/evidence")
    def evidence(uri: str, start: int = 1, end: int = 1):
        return html(pages_map.evidence_page, uri, start, end)

    @app.get("/law/{celex}")
    def law(celex: str):
        return html(pages_registers.law_page, celex)

    @app.get("/registers")
    def registers_page():
        return html(pages_registers.registers_page)

    @app.get("/registers/dora.csv")
    def dora_csv():
        return PlainTextResponse(registers.dora_csv(map_store.active()), media_type="text/csv")

    @app.get("/api/runs")
    def api_runs():
        rows = db.connect().execute("select run_id, law_id, status, paused from runs order by created_ts")
        return JSONResponse([dict(r) for r in rows])

    @app.get("/api/runs/{run_id}/events")
    def api_events(run_id: str, after: int = 0):
        return JSONResponse(audit.events(run_id, after))

    @app.get("/checkpoints/{cid}/export")
    def export(cid: str):
        try:
            bundle = deps.rt.export_checkpoint(cid)
        except KeyError:
            return HTMLResponse("unknown checkpoint", status_code=404)
        return Response(bundle, media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{cid}.json"'})

    actions.register(app, engine, deps, drive)
    return app
