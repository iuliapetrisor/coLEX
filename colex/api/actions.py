"""Console actions (POST). Human decisions made here use the same `Runtime.deliver_human_answer`
path as a Slack click."""
from __future__ import annotations

import shutil
from urllib.parse import parse_qs

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from colex import db, settings
from colex.api import pages_admin
from colex.config import ConfigError, ConfigStore
from colex.runtime import audit, store
from colex.runtime.transfer import BundleError

ACTOR = "console-user"


async def form_of(request: Request) -> dict[str, str]:
    data = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    return {k: v[0] for k, v in data.items()}


def back(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def register(app: FastAPI, engine, deps, drive) -> None:
    @app.post("/act/{wait_id:path}")
    async def act(wait_id: str, request: Request):
        form, wait = await form_of(request), store.wait(wait_id)
        if wait is None:
            return HTMLResponse("unknown request", status_code=404)
        answer = {k: v.strip() for k, v in form.items() if k in ("decision", "text") and v.strip()}
        if answer and deps.rt.deliver_human_answer(wait_id, answer, ACTOR):
            if ":ask:budget-" in wait_id:
                engine.apply_budget_answer(wait["run_id"], {**answer, "actor": ACTOR})
            drive(wait["run_id"])
        return back(f"/runs/{wait['run_id']}")

    @app.post("/runs/{run_id}/pause")
    def pause(run_id: str):
        deps.rt.pause(run_id, ACTOR)
        return back(f"/runs/{run_id}")

    @app.post("/runs/{run_id}/resume")
    def resume(run_id: str):
        deps.rt.resume(run_id, ACTOR)
        drive(run_id)
        return back(f"/runs/{run_id}")

    @app.post("/checkpoints/{cid}/fork")
    def fork(cid: str):
        run = deps.rt.fork(cid)
        drive(run.run_id)
        return back(f"/runs/{run.run_id}")

    @app.post("/checkpoints/import")
    async def import_bundle(request: Request):
        try:
            run = deps.rt.import_checkpoint(await request.body())
        except BundleError as exc:
            return HTMLResponse(f"Import refused: {exc}", status_code=400)
        drive(run.run_id)
        return back(f"/runs/{run.run_id}")

    @app.post("/feed/publish")
    async def publish(request: Request):
        celex = (await form_of(request)).get("celex", "")
        source = settings.FEED / f"{celex}.md"
        if celex.isalnum() and source.is_file():
            shutil.copy(source, settings.inbox() / source.name)
            for run_id in engine.poll_feed(settings.inbox()).get("runs", []):
                drive(run_id)
        return back("/feed")

    @app.post("/settings")
    async def save_settings(request: Request):
        form = await form_of(request)
        try:
            payload = yaml.safe_load(form.get("yaml", ""))
            if not isinstance(payload, dict):
                raise ConfigError("Invalid configuration:\nthe document must be a YAML mapping")
            ConfigStore().save(payload, form.get("author") or ACTOR)
        except (ConfigError, yaml.YAMLError) as exc:   # readable error; the active config is unchanged
            return HTMLResponse(pages_admin.settings_page(str(exc), form.get("yaml", "")), status_code=400)
        return back("/settings")

    @app.post("/settings/rollback/{version_id}")
    def rollback(version_id: str):
        ConfigStore().rollback(version_id, ACTOR)
        return back("/settings")

    @app.post("/map/assign")
    async def assign(request: Request):
        form = await form_of(request)
        if form.get("uri") and form.get("node_path"):   # a human decision becomes a rule, then the map is rebuilt
            db.connect().execute("insert or replace into learned_rules values(?,?,?,?)",
                                 (form["uri"], form["node_path"], ACTOR, audit.now()))
            engine.ensure_map(rebuild=True)
        return back("/map")

    @app.post("/map/rebuild")
    def rebuild():
        engine.ensure_map(rebuild=True)
        return back("/map")
