#!/usr/bin/env python3
'''Offline checks for the independent positive R-016 witness.

The checks use only generated witness artifacts and Python or Node standard
libraries. No browser, network, verifier, oracle, cache, receipt, or judge is
used.
'''

from __future__ import annotations

import csv
import json
import math
import re
import subprocess
from decimal import Decimal, getcontext, localcontext
from pathlib import Path

import reference

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "temoins" / "pos-03-solution.md"
getcontext().prec = 140


def rows(name: str) -> list[dict[str, object]]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))["events"]


def D(value: object) -> Decimal:
    return Decimal(str(value))


def state(rows_in: list[dict[str, object]], t: Decimal, precision: int) -> tuple[Decimal, Decimal]:
    with localcontext() as ctx:
        ctx.prec = precision
        t0 = Decimal(0)
        p = (Decimal("0.10"), Decimal("0.30"))
        v = (Decimal("1.70"), Decimal("0"))
        for row in rows_in:
            te = D(row["t"])
            if t < te:
                break
            t0 = te
            p = D(row["px"]), D(row["py"])
            v = D(row["vx"]), D(row["vy"])
        return reference.free_position(t0, p, v, t)


def assert_pair(value: object, label: str) -> None:
    if not isinstance(value, list) or len(value) != 2:
        raise AssertionError(f"{label}: expected a two-number array")
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x)) for x in value):
        raise AssertionError(f"{label}: non-finite or non-numeric output")


def invoke_html(times: list[float]) -> dict[str, object]:
    js = r'''
const fs = require("fs"), vm = require("vm");
const html = fs.readFileSync("temoins/pos-03-solution.md", "utf8");
const match = html.match(/<script>([\s\S]*)<\/script>/);
if (!match) throw new Error("script missing");
const c = { clearRect(){}, beginPath(){}, closePath(){}, moveTo(){}, lineTo(){}, fill(){}, stroke(){}, arc(){} };
const sandbox = { document: { getElementById(){ return { getContext(){ return c; } }; } } };
vm.runInNewContext(match[1], sandbox, { timeout: 20000 });
if (typeof sandbox.simulate !== "function") throw new Error("simulate missing");
if (!Array.isArray(sandbox.__r016_events)) throw new Error("event table missing");
function pair(value, label) {
  if (!Array.isArray(value) || value.length !== 2) throw new Error(label + ": shape");
  if (!value.every(x => typeof x === "number" && Number.isFinite(x))) throw new Error(label + ": finite");
}
function same(a, b, label) {
  pair(a, label + ".a"); pair(b, label + ".b");
  if (!Object.is(a[0], b[0]) || !Object.is(a[1], b[1])) throw new Error(label + ": mismatch");
}
const direct = TIMES.map((t, i) => { const value = sandbox.simulate(t); pair(value, "direct[" + i + "]"); return value; });
const reverseTimes = TIMES.slice().reverse();
const reverse = reverseTimes.map((t, i) => { const value = sandbox.simulate(t); pair(value, "reverse[" + i + "]"); return value; });
const repeated = TIMES.map((t, i) => { const value = sandbox.simulate(t); pair(value, "repeat[" + i + "]"); return value; });
for (let i = 0; i < TIMES.length; ++i) {
  same(direct[i], repeated[i], "repetition[" + i + "]");
  same(direct[i], reverse[TIMES.length - 1 - i], "order[" + i + "]");
}
process.stdout.write(JSON.stringify({direct, reverse, events: sandbox.__r016_events}));
'''
    js = "const TIMES = " + json.dumps(times) + ";\n" + js
    proc = subprocess.run(["node", "-e", js], cwd=ROOT, text=True, capture_output=True, check=False)
    if proc.returncode:
        raise RuntimeError(f"Node offline harness failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def run_html(times: list[float]) -> tuple[list[list[float]], list[dict[str, object]]]:
    first = invoke_html(times)
    second = invoke_html(times)
    if first["direct"] != second["direct"] or first["reverse"] != second["reverse"]:
        raise AssertionError("fresh execution mismatch")
    if first["events"] != second["events"]:
        raise AssertionError("fresh event table mismatch")
    return first["direct"], first["events"]


def compare_embedded_states(r110: list[dict[str, object]], tsv_rows: list[dict[str, str]], embedded: list[dict[str, object]]) -> None:
    if len(embedded) != len(r110) + 1:
        raise AssertionError(f"HTML/d110 state count mismatch: {len(embedded)} / {len(r110) + 1}")
    initial = embedded[0]
    for key, value in (("t", "0"), ("px", "0.10"), ("py", "0.30"), ("vx", "1.70"), ("vy", "0")):
        pair = initial[key]
        if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(x, (int, float)) and math.isfinite(float(x)) for x in pair):
            raise AssertionError(f"HTML initial pair {key}")
        if float(pair[0]) + float(pair[1]) != float(Decimal(value)):
            raise AssertionError(f"HTML initial state {key}")
    for i, row in enumerate(r110):
        tsv = tsv_rows[i]
        if int(tsv["index"]) != i or str(tsv["t"]) != str(row["t"]):
            raise AssertionError(f"TSV/JSON identity mismatch at {i}")
        for key in ("edge", "s", "px", "py"):
            if str(tsv[key]) != str(row[key]):
                raise AssertionError(f"TSV/JSON {key} mismatch at {i}")
        if str(tsv["vx_after"]) != str(row["vx"]) or str(tsv["vy_after"]) != str(row["vy"]):
            raise AssertionError(f"TSV/JSON velocity mismatch at {i}")
        state_row = embedded[i + 1]
        for key in ("t", "px", "py", "vx", "vy"):
            pair = state_row[key]
            if not isinstance(pair, list) or len(pair) != 2:
                raise AssertionError(f"HTML pair shape {key} at {i}")
            if not all(isinstance(x, (int, float)) and math.isfinite(float(x)) for x in pair):
                raise AssertionError(f"HTML pair finite {key} at {i}")
            actual = float(pair[0]) + float(pair[1])
            expected = float(Decimal(str(row[key])))
            if actual != expected:
                raise AssertionError(f"HTML/JSON {key} mismatch at {i}: {actual!r} != {expected!r}")


def main() -> int:
    if reference.CONFIGS["d110"].max_iter < 300:
        raise AssertionError("d110 max_iter is below 300")
    if any(path.is_dir() and path.name == "__pycache__" for path in ROOT.rglob("*")):
        raise AssertionError("__pycache__ present")
    r80 = rows("d80.json")
    r110 = rows("d110.json")
    if len(r80) != len(r110) or len(r110) != 240:
        raise AssertionError(f"event count mismatch: {len(r80)} / {len(r110)}")
    if [r["edge"] for r in r80] != [r["edge"] for r in r110]:
        raise AssertionError("event edge sequence mismatch")
    max_dt = max(abs(D(a["t"]) - D(b["t"])) for a, b in zip(r80, r110))
    max_dp = max(
        ((D(a["px"]) - D(b["px"])) ** 2 + (D(a["py"]) - D(b["py"])) ** 2).sqrt()
        for a, b in zip(r80, r110)
    )

    with (ROOT / "events.tsv").open(encoding="utf-8", newline="") as handle:
        tsv_rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(tsv_rows) != len(r110):
        raise AssertionError("events.tsv/json count mismatch")
    times = [0.0, 0.1, 2.0, 10.0, 20.0, 24.0, 35.0, 55.0, 75.0, 90.0]
    _quick_outputs, embedded = run_html(times)
    compare_embedded_states(r110, tsv_rows, embedded)

    residual_limit = Decimal("1e-55")
    max_line = Decimal(0)
    min_h_event = Decimal("Infinity")
    for i, row in enumerate(r110):
        tsv = tsv_rows[i]
        if Decimal(tsv["approach"]) >= 0:
            raise AssertionError(f"non-approaching collision at {i}")
        t = D(row["t"])
        p = D(row["px"]), D(row["py"])
        hs = reference.halfspaces(p, t)
        min_h_event = min(min_h_event, min(hs))
        edge = reference.EDGES[int(row["edge"])]
        q = reference._rotate_minus(p, reference.OMEGA * t)
        line = reference._cross(edge["e"], (q[0] - edge["a"][0], q[1] - edge["a"][1]))
        max_line = max(max_line, abs(line))
        if abs(Decimal(tsv["line_residual"])) > residual_limit or abs(Decimal(tsv["min_halfspace"])) > residual_limit:
            raise AssertionError(f"serialized collision residual at {i}")
        if min(hs) < -residual_limit or abs(line) > residual_limit:
            raise AssertionError(f"collision residual at {i}")

    min_h = min_h_event
    for i, row in enumerate(r110):
        left = D(row["t"])
        right = D(r110[i + 1]["t"]) if i + 1 < len(r110) else Decimal(90)
        for t in ((left + right) / 2, left):
            p = state(r110, t, 110)
            min_h = min(min_h, min(reference.halfspaces(p, t)))
    for j in range(9001):
        t = Decimal(j) / Decimal(100)
        p = state(r110, t, 110)
        min_h = min(min_h, min(reference.halfspaces(p, t)))
    if min_h < -residual_limit:
        raise AssertionError(f"out of bounds: {min_h}")

    html_text = HTML.read_text(encoding="utf-8")
    if html_text.count("<html>") != 1 or html_text.count("</html>") != 1 or html_text.count("<script>") != 1 or html_text.count("<canvas") != 1:
        raise AssertionError("HTML wrapper count")
    if not re.search(r'<canvas[^>]*width="800"[^>]*height="500"', html_text):
        raise AssertionError("canvas dimensions missing")
    for forbidden in ("fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "Math.random", "Date(", "performance.", "setTimeout", "setInterval", "localStorage", "sessionStorage", "http://", "https://", "import "):
        if forbidden in html_text:
            raise AssertionError(f"forbidden HTML token: {forbidden}")

    got, _embedded = run_html(times)
    by_time = dict(zip(times, got))
    with localcontext() as ctx:
        ctx.prec = 110
        ref24 = state(r110, Decimal(24), 110)
        out24 = by_time[24.0]
        out24d = Decimal.from_float(out24[0]), Decimal.from_float(out24[1])
        d24 = ((out24d[0] - ref24[0]) ** 2 + (out24d[1] - ref24[1]) ** 2).sqrt()
        if d24 > Decimal("1e-16"):
            raise AssertionError(f"24 s distance {d24}")
        for k in (0, 1):
            err = abs(out24d[k] - ref24[k])
            prev = Decimal.from_float(math.nextafter(out24[k], -math.inf))
            nxt = Decimal.from_float(math.nextafter(out24[k], math.inf))
            if err > abs(prev - ref24[k]) or err > abs(nxt - ref24[k]):
                raise AssertionError(f"24 s neighbour is closer on coordinate {k}")
        long_errors = {}
        for t in (35, 55, 75):
            p = state(r110, Decimal(t), 110)
            g = by_time[float(t)]
            gd = Decimal.from_float(g[0]), Decimal.from_float(g[1])
            long_errors[str(t)] = ((gd[0] - p[0]) ** 2 + (gd[1] - p[1]) ** 2).sqrt()
            if long_errors[str(t)] > Decimal("0.01"):
                raise AssertionError(f"long horizon {t} s: {long_errors[str(t)]}")

    print(json.dumps({
        "status": "PASS",
        "events": len(r110),
        "same_edge_sequence": True,
        "d110_max_iter": reference.CONFIGS["d110"].max_iter,
        "max_event_time_delta": str(max_dt),
        "max_event_position_delta": str(max_dp),
        "min_halfspace": str(min_h),
        "max_line_residual": str(max_line),
        "t24_euclidean": str(d24),
        "t24_neighbors": "checked",
        "long_horizon_errors": {k: str(v) for k, v in long_errors.items()},
        "api_shape_finite": "checked",
        "api_repetition": "checked",
        "api_order_direct_reverse": "checked",
        "api_fresh_execution": "checked",
        "html_json_tsv_linewise": "checked",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
