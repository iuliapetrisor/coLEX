"""Console page: the Company Map as one picture, with the path of one run on request."""
from __future__ import annotations

import json
from html import escape as e
from typing import Any

from colex import db
from colex.api import map_data
from colex.api.html import page
from colex.api.map_svg import KINDS, SOURCES, svg
from colex.map import store as map_store
from colex.runtime import audit

MEANING = {"implements": "code or configuration implements a published document",
           "governed_by": "code that uses a provider → that provider's contract",
           "references": "a document mentions a ticket or a code file",
           "depends_on": "code imports code or reads a configuration file"}


def _key(colours: dict[str, str], text: dict[str, str] | None = None) -> str:
    return "".join(f"<i style='background:{c}'></i>{e(name.replace('_', ' '))}"
                   + (f" <span class='muted'>({e(text[name])})</span>" if text else "") for name, c in colours.items())


def _run_box(path: dict[str, Any]) -> str:
    m, used = path["metrics"], audit.usage(path["run_id"])
    lines = [f"<b>Path of run {e(path['run_id'])}</b> (act <a href='/law/{e(path['law'])}'>{e(path['law'])}</a>): "
             f"the Impact Analyst reached {len(path['visited'])} place(s) of the map, numbered in the order it first "
             f"reached them, and reported findings under {len(path['found'])} topic(s), shown in green."]
    if m:
        lines.append(f"It made {m['tool_calls']} map calls and opened {m['fragments_read']:,} of "
                     f"{m['fragments_total']:,} sections. Text the map returned to it: {m['context_tokens_used']:,} "
                     f"tokens. All {m['resources_total']:,} resources together: "
                     f"{m['baseline_a_whole_corpus_tokens']:,} tokens.")
    lines.append(f"Model tokens billed for the whole run: {used['tokens']:,}. This is much more than the text read, "
                 "because every step sends the conversation so far to the model again.")
    if not path["same_map"]:
        lines.append(f"This run used map version {e(str(path['run_map']))}; the picture shows the current map.")
    return "<div class='box warn'>" + "<br>".join(lines) + "</div>"


def picture(run_id: str | None) -> str:
    mv = map_store.active()
    if not mv:
        return page("Map picture", "<p>No map has been built yet.</p>")
    data = map_data.hierarchy(mv)
    path = map_data.run_path(run_id, mv) if run_id else None
    con = db.connect()
    stats = json.loads(con.execute("select stats_json from map_versions where version_id=?",
                                   (mv,)).fetchone()["stats_json"])
    topics = sum(n["level"] == "L3" for n in data["nodes"])
    sources = {s for by in data["counts"].values() for s in by}
    head = (f"<p><b>{stats['resources']:,}</b> resources from <b>{len(sources)}</b> source systems, filed under "
            f"<b>{topics}</b> topics. {stats['unclassified']:,} could not be placed and wait for a person. "
            f"Map version <code>{e(mv)}</code>. The agent never receives all documents: it walks this map from "
            "left to right and opens only the sections it asks for.</p>")
    runs = con.execute("select r.run_id, r.law_id from runs r join steps s on s.run_id=r.run_id and "
                       "s.step_key='main:IMPACT' and s.output_ref is not null order by r.created_ts").fetchall()
    links = " ".join(f"<a href='/map/picture?run={e(r['run_id'])}'>{e(r['law_id'])}</a>" for r in runs)
    chooser = (f"<p>Show the path the agent walked for: {links} · <a href='/map/picture'>none</a></p>" if runs
               else "<p class='muted'>No act has been analysed in this state yet, so there is no path to show.</p>")
    key = (f"<p class='key'>Sources:{_key(SOURCES)}</p><p class='key'>Links:{_key(KINDS, MEANING)}</p>"
           "<p class='muted'>Links by shared owner or shared contractor are not drawn. Click a box to list its "
           "resources.</p>")
    return page("Map picture", head + chooser + (_run_box(path) if path else "") + svg(data, path) + key, wide=True)
