#!/usr/bin/env python3
"""Independent event-driven reproducer for the public pentagon instance.

The module intentionally has no imports outside Python's standard library. It
can regenerate ``events.tsv`` and is also used by ``selfcheck.py``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, getcontext, localcontext
from pathlib import Path


ROOT = Path(__file__).resolve().parent
getcontext().prec = 180
T_END = Decimal("90")
OMEGA = Decimal("0.7")
G = Decimal("-9.81")
PI = Decimal(
    "3.141592653589793238462643383279502884197169399375105820974944592307816406286208998628034825342117067982148086513282306647093844609550582231725359408128481"
)
TAU = PI * 2
HALF_PI = PI / 2
SRC_HASHES = {
    "task-v3.md": "7acfb34a2e4e68d5fe8b75d2972cc97bb949f99d36e92b12e80de1339e9a77bf",
    "donnees.md": "2f4dd0872b4377ea61df278396898f4cd7354d1bfa2a105ef6bfe1cdd3c77045",
}


@dataclass(frozen=True)
class Config:
    name: str
    precision: int
    scan: str
    root_tol: str
    # 320 iterations leave material margin below the d110 root tolerance
    max_iter: int = 320


CONFIGS = {
    "d80": Config("d80", 80, "0.001", "1e-58"),
    "d110": Config("d110", 110, "0.0005", "1e-82"),
}


def _dec(value: str | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(value)


def _sincos(x: Decimal) -> tuple[Decimal, Decimal]:
    """High precision sin/cos, with deterministic argument reduction."""
    with localcontext() as ctx:
        ctx.prec += 12
        turns = (x / TAU).to_integral_value(rounding=ROUND_FLOOR)
        y = x - turns * TAU
        if y > PI:
            y -= TAU
        if y < -PI:
            y += TAU
        csign = Decimal(1)
        if y > HALF_PI:
            y = PI - y
            csign = Decimal(-1)
        elif y < -HALF_PI:
            y = -PI - y
            csign = Decimal(-1)
        y2 = y * y
        st = y
        s = y
        k = 1
        while True:
            st *= -y2 / Decimal((2 * k) * (2 * k + 1))
            s_next = s + st
            if abs(st) <= Decimal(10) ** (-(ctx.prec - 5)):
                s = s_next
                break
            s = s_next
            k += 1
        ct = Decimal(1)
        c = Decimal(1)
        k = 1
        while True:
            ct *= -y2 / Decimal((2 * k - 1) * (2 * k))
            c_next = c + ct
            if abs(ct) <= Decimal(10) ** (-(ctx.prec - 5)):
                c = c_next
                break
            c = c_next
            k += 1
        return +s, +(c * csign)


def _rotate(v: tuple[Decimal, Decimal], theta: Decimal) -> tuple[Decimal, Decimal]:
    s, c = _sincos(theta)
    x, y = v
    return c * x - s * y, s * x + c * y


def _rotate_minus(v: tuple[Decimal, Decimal], theta: Decimal) -> tuple[Decimal, Decimal]:
    s, c = _sincos(theta)
    x, y = v
    return c * x + s * y, -s * x + c * y


def _cross(a: tuple[Decimal, Decimal], b: tuple[Decimal, Decimal]) -> Decimal:
    return a[0] * b[1] - a[1] * b[0]


def _dot(a: tuple[Decimal, Decimal], b: tuple[Decimal, Decimal]) -> Decimal:
    return a[0] * b[0] + a[1] * b[1]


VERTICES = tuple(
    (Decimal(x), Decimal(y))
    for x, y in (
        ("1.00", "0.00"),
        ("0.25", "0.95"),
        ("-0.85", "0.52"),
        ("-0.78", "-0.62"),
        ("0.40", "-0.88"),
    )
)
_edge_values: list[dict[str, object]] = []
for _i, _a in enumerate(VERTICES):
    _b = VERTICES[(_i + 1) % len(VERTICES)]
    _e = (_b[0] - _a[0], _b[1] - _a[1])
    _len2 = _dot(_e, _e)
    _length = _len2.sqrt()
    _n = (-_e[1] / _length, _e[0] / _length)
    _edge_values.append({"a": _a, "b": _b, "e": _e, "len2": _len2, "n": _n})
EDGES = tuple(_edge_values)


@dataclass
class Event:
    index: int
    t: Decimal
    edge: int
    s: Decimal
    p: tuple[Decimal, Decimal]
    v_before: tuple[Decimal, Decimal]
    v_after: tuple[Decimal, Decimal]
    line_residual: Decimal
    min_halfspace: Decimal
    approach: Decimal


def free_position(t0: Decimal, p0: tuple[Decimal, Decimal], v0: tuple[Decimal, Decimal], t: Decimal) -> tuple[Decimal, Decimal]:
    dt = t - t0
    return p0[0] + v0[0] * dt, p0[1] + v0[1] * dt + G * dt * dt / 2


def free_velocity(t0: Decimal, v0: tuple[Decimal, Decimal], t: Decimal) -> tuple[Decimal, Decimal]:
    dt = t - t0
    return v0[0], v0[1] + G * dt


def halfspaces(p: tuple[Decimal, Decimal], t: Decimal) -> list[Decimal]:
    q = _rotate_minus(p, OMEGA * t)
    out: list[Decimal] = []
    for edge in EDGES:
        out.append(_cross(edge["e"], (q[0] - edge["a"][0], q[1] - edge["a"][1])))
    return out


def _h_at(edge_index: int, t: Decimal, t0: Decimal, p0: tuple[Decimal, Decimal], v0: tuple[Decimal, Decimal]) -> Decimal:
    p = free_position(t0, p0, v0, t)
    q = _rotate_minus(p, OMEGA * t)
    edge = EDGES[edge_index]
    return _cross(edge["e"], (q[0] - edge["a"][0], q[1] - edge["a"][1]))


def _segment_at(edge_index: int, t: Decimal, t0: Decimal, p0: tuple[Decimal, Decimal], v0: tuple[Decimal, Decimal]) -> tuple[Decimal, tuple[Decimal, Decimal]]:
    p = free_position(t0, p0, v0, t)
    q = _rotate_minus(p, OMEGA * t)
    edge = EDGES[edge_index]
    qa = (q[0] - edge["a"][0], q[1] - edge["a"][1])
    s = _dot(qa, edge["e"]) / edge["len2"]
    return s, q


def _bisect_root(edge_index: int, lo: Decimal, hi: Decimal, t0: Decimal, p0: tuple[Decimal, Decimal], v0: tuple[Decimal, Decimal], cfg: Config) -> Decimal:
    tol = Decimal(cfg.root_tol)
    flo = _h_at(edge_index, lo, t0, p0, v0)
    if flo <= 0:
        return lo
    for _ in range(cfg.max_iter):
        mid = (lo + hi) / 2
        fm = _h_at(edge_index, mid, t0, p0, v0)
        if fm > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo <= tol:
            break
    return (lo + hi) / 2


def find_event(t0: Decimal, p0: tuple[Decimal, Decimal], v0: tuple[Decimal, Decimal], horizon: Decimal, cfg: Config) -> tuple[Decimal, int, Decimal] | None:
    scan = Decimal(cfg.scan)
    probe = scan / 100
    cursor = t0 + probe
    if cursor >= horizon:
        return None
    previous = [_h_at(i, cursor, t0, p0, v0) for i in range(len(EDGES))]
    while cursor < horizon:
        nxt = min(cursor + scan, horizon)
        values = [_h_at(i, nxt, t0, p0, v0) for i in range(len(EDGES))]
        candidates: list[tuple[Decimal, int, Decimal]] = []
        for i in range(len(EDGES)):
            if previous[i] > 0 and values[i] <= 0:
                root = _bisect_root(i, cursor, nxt, t0, p0, v0, cfg)
                s, _q = _segment_at(i, root, t0, p0, v0)
                seg_tol = Decimal("1e-35")
                if -seg_tol <= s <= Decimal(1) + seg_tol:
                    delta = min(scan / 1000, (root - cursor) / 4)
                    if delta > 0:
                        before = _h_at(i, root - delta, t0, p0, v0)
                        after = _h_at(i, root + delta, t0, p0, v0)
                        if before >= 0 and after <= 0:
                            candidates.append((root, i, s))
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1]))
            return candidates[0]
        previous = values
        cursor = nxt
    return None


def _reflect(t: Decimal, p: tuple[Decimal, Decimal], v: tuple[Decimal, Decimal], edge_index: int, s: Decimal) -> tuple[tuple[Decimal, Decimal], tuple[Decimal, Decimal], Decimal, Decimal]:
    edge = EDGES[edge_index]
    q = edge["a"][0] + s * edge["e"][0], edge["a"][1] + s * edge["e"][1]
    p_contact = _rotate(q, OMEGA * t)
    n = _rotate(edge["n"], OMEGA * t)
    u = OMEGA * (-p_contact[1]), OMEGA * p_contact[0]
    rel = v[0] - u[0], v[1] - u[1]
    approach = _dot(rel, n)
    v_after = v[0] - Decimal(2) * approach * n[0], v[1] - Decimal(2) * approach * n[1]
    line_residual = _cross(edge["e"], (q[0] - edge["a"][0], q[1] - edge["a"][1]))
    return p_contact, v_after, approach, line_residual


def integrate(cfg: Config | str = "d110", t_end: Decimal | str = T_END) -> tuple[list[Event], dict[str, object]]:
    if isinstance(cfg, str):
        cfg = CONFIGS[cfg]
    t_end = _dec(t_end)
    with localcontext() as ctx:
        ctx.prec = cfg.precision
        t = Decimal(0)
        p = Decimal("0.10"), Decimal("0.30")
        v = Decimal("1.70"), Decimal("0")
        events: list[Event] = []
        rejected = 0
        while t < t_end:
            found = find_event(t, p, v, t_end, cfg)
            if found is None:
                break
            te, edge, s = found
            p_free = free_position(t, p, v, te)
            v_before = free_velocity(t, v, te)
            p_contact, v_after, approach, line_residual = _reflect(te, p_free, v_before, edge, s)
            hs = halfspaces(p_contact, te)
            events.append(Event(len(events), +te, edge, +s, (+p_contact[0], +p_contact[1]), (+v_before[0], +v_before[1]), (+v_after[0], +v_after[1]), +line_residual, +min(hs), +approach))
            if te <= t:
                rejected += 1
                t = t + Decimal(cfg.root_tol) * 10
            else:
                t = te
            p, v = p_contact, v_after
            if len(events) > 200000:
                raise RuntimeError("event count guard reached")
        meta = {"config": cfg.name, "precision": cfg.precision, "scan": cfg.scan, "root_tol": cfg.root_tol, "t_end": format(t_end, "f"), "events": len(events), "rejected": rejected, "final_t": format(t, "f"), "source_hashes": SRC_HASHES}
        return events, meta


def state_at(events: list[Event], t: Decimal | str, cfg: Config | str = "d110") -> tuple[Decimal, Decimal]:
    if isinstance(cfg, str):
        cfg = CONFIGS[cfg]
    t = _dec(t)
    with localcontext() as ctx:
        ctx.prec = cfg.precision
        t0 = Decimal(0)
        p0 = Decimal("0.10"), Decimal("0.30")
        v0 = Decimal("1.70"), Decimal("0")
        for event in events:
            if t < event.t:
                break
            t0, p0, v0 = event.t, event.p, event.v_after
        p = free_position(t0, p0, v0, t)
        return +p[0], +p[1]


def _fmt(d: Decimal, places: int = 70) -> str:
    s = format(d, f".{places}f").rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def write_events(events: list[Event], path: Path) -> None:
    fields = ["index", "t", "edge", "s", "px", "py", "vx_before", "vy_before", "vx_after", "vy_after", "line_residual", "min_halfspace", "approach"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(fields)
        for e in events:
            writer.writerow([e.index, _fmt(e.t), e.edge, _fmt(e.s), _fmt(e.p[0]), _fmt(e.p[1]), _fmt(e.v_before[0]), _fmt(e.v_before[1]), _fmt(e.v_after[0]), _fmt(e.v_after[1]), _fmt(e.line_residual), _fmt(e.min_halfspace), _fmt(e.approach)])


def events_json(events: list[Event]) -> list[dict[str, str | int]]:
    return [{"i": e.index, "t": _fmt(e.t), "edge": e.edge, "s": _fmt(e.s), "px": _fmt(e.p[0]), "py": _fmt(e.p[1]), "vx": _fmt(e.v_after[0]), "vy": _fmt(e.v_after[1])} for e in events]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", choices=tuple(CONFIGS), default="d110")
    parser.add_argument("--end", default="90")
    parser.add_argument("--events", type=Path, default=ROOT / "events.tsv")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    events, meta = integrate(args.config, args.end)
    write_events(events, args.events)
    if args.json:
        args.json.write_text(json.dumps({"meta": meta, "events": events_json(events)}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
