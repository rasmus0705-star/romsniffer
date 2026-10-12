#!/usr/bin/env python3
"""
ret_fejl.py — lokal editor til fejlliste.xlsx (RomSniffer). Samme arbejdsgang som på BeerSniffer.
Start med start_Fejlrettelse.bat. Åbner http://localhost:5112 og gemmer direkte i fejlliste.xlsx.

Læser:  fejl_snapshot.json (skrives af hvert build: hvad mangler, hvilke par skal gennemgås)
        fejlliste.xlsx     (dine tidligere rettelser)
Skriver: fejlliste.xlsx    (dit facit; gælder ved næste build, FØR matchning)
"""
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from rom_overrides import FEJLLISTE, SNAPSHOT, _num, load_fejlliste, pair_key, save_fejlliste

PORT = 5112
TEMPLATE = "_fejl_template.html"
HIDDEN = ("IGNORERET", "SAET", "ROM")


def load_snapshot():
    if not os.path.isfile(SNAPSHOT):
        raise SystemExit("Mangler %s. Kør først et build (opdater_rom.bat, eller: $env:ROM_NO_PUSH=1; python build_rom_data.py)." % SNAPSHOT)
    with open(SNAPSHOT, encoding="utf-8") as f:
        return json.load(f)


def build_view():
    snap, facit = load_snapshot(), load_fejlliste(FEJLLISTE)
    fejl, ok = [], []
    for r in snap["items"]:
        f = facit["items"].get(r["url"])
        if f and f.get("status") in HIDDEN:
            continue
        brand = (f or {}).get("brand") or r["brand"]
        vol = f["volume"] if f and f.get("volume") is not None else r["volume"]
        abv = f["abv"] if f and f.get("abv") is not None else r["abv"]
        mangler = []
        if not brand:
            mangler.append("bryggeri")          # (nøglen hedder 'bryggeri' i siden; vises som 'brand')
        if vol in (None, ""):
            mangler.append("volumen")
        if abv in (None, ""):
            mangler.append("abv")
        forslag = ""
        if r.get("abv_mistaenkelig") and not (f and f.get("abv") is not None):
            if "abv" not in mangler:
                mangler.append("abv")
            forslag = "ABV %s virker forkert (flaskestørrelse eller tal fra teksten?)" % abv
        row = {"url": r["url"], "butik": r["butik"], "navn": r["navn"], "bryggeri": brand or "", "volume": vol,
               "abv": abv, "mangler": ", ".join(mangler), "forslag": forslag}
        if mangler:
            row["status"] = "MANGLER" if f else "IKKE SET"
            fejl.append(row)
        elif f:
            row["status"] = "OK"
            ok.append(row)

    def pair_done(m):
        if m["url_b"] and pair_key(m["url_a"], m["url_b"]) in facit["pairs"]:
            return True
        f = facit["items"].get(m["url_a"])
        return bool(f and f.get("status") in HIDDEN)

    match = [m for m in snap["match"] if not pair_done(m)]
    branded = {u for u, f in facit["items"].items() if f.get("brand")}
    forslag = [x for x in snap["forslag"] if x["url"] not in branded]
    return snap, fejl, forslag, match, ok


def render():
    snap, fejl, forslag, match, ok = build_view()
    with open(TEMPLATE, encoding="utf-8") as f:
        t = f.read()
    n_m = sum(1 for r in fejl if r["status"] == "MANGLER")
    n_i = sum(1 for r in fejl if r["status"] == "IKKE SET")
    cnt = lambda typ: sum(1 for m in match if m["type"] == typ)
    rep = {
        "TIDSPUNKT": snap.get("tidspunkt", ""), "N_TOTAL": len(fejl), "N_MANGLER": n_m, "N_IKKE_SET": n_i,
        "N_FORSLAG": len(forslag), "N_FORSLAG_HOJ": sum(1 for x in forslag if x["sikkerhed"] == "HOEJ"),
        "N_FORSLAG_LAV": sum(1 for x in forslag if x["sikkerhed"] == "LAV"), "N_MATCH": len(match),
        "N_IKKE_OL": cnt("IKKE-ROM?"), "N_PRIS": cnt("PRIS-SPREDNING"), "N_OPSPLIT": cnt("OPSPLITTET"), "N_OK": len(ok),
    }
    js = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")
    jrep = {"FEJL_JSON": fejl, "FORSLAG_JSON": forslag, "MATCH_JSON": match, "OK_JSON": ok,
            "BUTIKKER_JSON": sorted({r["butik"] for r in snap["items"] if r["butik"]}), "BREWERIES_JSON": snap["brands"]}
    for k, v in rep.items():
        t = t.replace("%%" + k + "%%", str(v))
    for k, v in jrep.items():
        t = t.replace("%%" + k + "%%", js(v))
    return t


_INFO = {}


def item_info(url):
    if not _INFO:
        for r in load_snapshot()["items"]:
            _INFO[r["url"]] = r
    return _INFO.get(url, {})


def facit_row(facit, url):
    row = facit["items"].get(url)
    if row is None:
        info = item_info(url)
        row = {"butik": info.get("butik", ""), "navn": info.get("navn", ""), "brand": None, "volume": None, "abv": None, "status": ""}
        facit["items"][url] = row
    return row


def apply_corrections(corrections):
    facit = load_fejlliste(FEJLLISTE)
    applied = 0
    for c in corrections:
        url = c.get("url")
        if not url:
            continue
        row = facit_row(facit, url)
        changed = False
        if str(c.get("bryggeri", "")).strip():
            row["brand"] = str(c["bryggeri"]).strip()
            changed = True
        for src, dst in (("volume", "volume"), ("abv", "abv")):
            raw = str(c.get(src, "")).strip()
            if raw:
                val = _num(raw)
                if val is None:
                    return {"error": "Kan ikke læse tallet '%s'" % raw}
                row[dst] = val
                changed = True
        applied += 1 if changed else 0
    save_fejlliste(facit, FEJLLISTE)
    return {"status": "ok", "applied": applied}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/stop":
            self._send(200, json.dumps({"status": "ok"}))
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        elif self.path in ("/", "/index.html"):
            try:
                self._send(200, render(), "text/html; charset=utf-8")
            except SystemExit as e:
                self._send(500, str(e), "text/plain; charset=utf-8")
        else:
            self._send(404, "ikke fundet", "text/plain; charset=utf-8")

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"null")
            self._send(200, json.dumps(self.route(self.path, body), ensure_ascii=False))
        except SystemExit as e:
            self._send(200, json.dumps({"error": str(e)}, ensure_ascii=False))
        except RuntimeError as e:                   # fx fejlliste.xlsx er åben i Excel
            self._send(200, json.dumps({"error": str(e)}, ensure_ascii=False))
        except Exception as e:                      # vis fejlen i siden i stedet for at dø tavst
            self._send(200, json.dumps({"error": "%s: %s" % (type(e).__name__, e)}, ensure_ascii=False))

    def route(self, path, body):
        if path in ("/save", "/save_ok"):
            return apply_corrections(body or [])
        facit = load_fejlliste(FEJLLISTE)
        if path == "/set_status":
            if body.get("status") not in ("SAET", "IGNORERET"):
                return {"error": "ukendt status"}
            facit_row(facit, body["url"])["status"] = body["status"]
        elif path == "/remove_ikke_set":
            return {"status": "ok", "removed": 0}
        elif path == "/approve_brewery":
            facit_row(facit, body["url"])["brand"] = str(body["bryggeri"]).strip()
        elif path == "/approve_all_high":
            for x in body or []:
                facit_row(facit, x["url"])["brand"] = x["forslag"]
            save_fejlliste(facit, FEJLLISTE)
            return {"status": "ok", "updated": len(body or [])}
        elif path == "/set_par":
            dec = body.get("beslutning")
            if dec == "rom":                         # "IKKE-ROM?"-flag afvist: det ER rom
                facit_row(facit, body["url_a"])["status"] = "ROM"
            elif dec in ("sammen", "adskilt"):
                k = pair_key(body["url_a"], body["url_b"])
                facit["pairs"][k] = dec
                facit["pair_info"][k] = {"navn_a": body.get("navn_a", ""), "butik_a": body.get("butik_a", ""), "url_a": body["url_a"],
                                         "navn_b": body.get("navn_b", ""), "butik_b": body.get("butik_b", ""), "url_b": body["url_b"], "note": ""}
            else:
                return {"error": "ukendt beslutning"}
        else:
            return {"error": "ukendt adresse"}
        save_fejlliste(facit, FEJLLISTE)
        return {"status": "ok"}


def main():
    if not os.path.isfile(TEMPLATE):
        raise SystemExit("Mangler %s i denne mappe." % TEMPLATE)
    load_snapshot()
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    url = "http://localhost:%d" % PORT
    print("RomSniffer fejlrettelse: %s  (Stop-knappen i siden, eller Ctrl+C)" % url)
    if "--ingen-browser" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
