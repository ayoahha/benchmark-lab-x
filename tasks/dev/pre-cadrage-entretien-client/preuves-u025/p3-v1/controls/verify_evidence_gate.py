#!/usr/bin/env python3
"""Offline owner-authority gate. Account settings stay outside the project lock"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
ISSUE_COMMENTS = "https://api.github.com/repos/ayoahha/benchmark-lab-x/issues/59/comments"
REQUIRED_AUTHOR = "ayoahha"
REQUIRED_FIELDS = (
    "id",
    "node_id",
    "created_at",
    "updated_at",
    "url",
    "html_url",
    "issue_url",
    "user",
    "body",
)


class Hold(RuntimeError):
    pass


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Hold("HARNESS_ERROR: objet JSON attendu")
    return value


def fetch_comments() -> list[dict[str, Any]]:
    request = urllib.request.Request(
        ISSUE_COMMENTS,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "benchmark-lab-x-p3-lock"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise Hold("INCONNU: API GitHub indisponible") from error
    if not isinstance(payload, list):
        raise Hold("INCONNU: API GitHub non rejouable")
    return payload


def authenticate_recorded(gate: dict[str, Any], live: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recorded = gate.get("comments")
    if not isinstance(recorded, list) or not recorded:
        raise Hold("INCONNU: autorites GitHub absentes")
    by_id = {item.get("id"): item for item in live if isinstance(item, dict)}
    proofs = []
    for item in recorded:
        if not isinstance(item, dict):
            raise Hold("INCONNU: autorite GitHub illisible")
        comment_id = item.get("id")
        live_item = by_id.get(comment_id)
        if not isinstance(live_item, dict):
            raise Hold("INCONNU: commentaire GitHub absent")
        missing = [field for field in REQUIRED_FIELDS if live_item.get(field) in (None, "")]
        if missing:
            raise Hold("INCONNU: champs GitHub manquants")
        user = live_item.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        if login != REQUIRED_AUTHOR or item.get("author") != REQUIRED_AUTHOR:
            raise Hold("INCONNU: auteur GitHub non proprio")
        body = live_item.get("body")
        if not isinstance(body, str):
            raise Hold("INCONNU: corps GitHub absent")
        body_sha = sha256_text(body)
        if body_sha != item.get("body_sha256"):
            raise Hold("INCONNU: empreinte GitHub divergente")
        if live_item.get("node_id") != item.get("node_id"):
            raise Hold("INCONNU: node_id GitHub divergent")
        if live_item.get("created_at") != item.get("created_at"):
            raise Hold("INCONNU: created_at GitHub divergent")
        if live_item.get("updated_at") != item.get("updated_at"):
            raise Hold("INCONNU: updated_at GitHub divergent")
        if live_item.get("url") != item.get("api_url"):
            raise Hold("INCONNU: URL API GitHub divergente")
        if live_item.get("html_url") != item.get("html_url"):
            raise Hold("INCONNU: URL HTML GitHub divergente")
        proofs.append({
            "id": comment_id,
            "author": login,
            "authenticated": True,
            "body_published": False,
        })
    return proofs


def main() -> int:
    authorities = load_json(ROOT / "github-authorities.json")
    gate = load_json(ROOT / "evidence-gate.json")
    account_scope = gate.get("account_settings_scope", {})
    if account_scope.get("disposition") != "OWNER_RESPONSIBILITY_OUTSIDE_PROJECT_LOCK":
        raise Hold("HARNESS_ERROR: périmètre propriétaire divergent")
    if account_scope.get("project_verification") is not False:
        raise Hold("HARNESS_ERROR: contrôle de compte réintroduit")
    if account_scope.get("execution_gate") is not False:
        raise Hold("HARNESS_ERROR: porte de compte réintroduite")
    if gate.get("requested_expected_observed") != "SEPARATED":
        raise Hold("HARNESS_ERROR: attendu demande observe non separes")
    live = fetch_comments()
    proofs = authenticate_recorded(authorities, live)
    print(json.dumps({
        "status": "PASS",
        "future_gos": "GITHUB_API_AUTHENTICATED",
        "authenticated_comments": len(proofs),
        "account_settings_scope": "OWNER_RESPONSIBILITY_OUTSIDE_PROJECT_LOCK",
        "account_settings_project_gate": False,
        "requested_expected_observed": "SEPARATED",
        "provider_contacted": False,
        "bodies_published": False,
    }, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Hold as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(78)
