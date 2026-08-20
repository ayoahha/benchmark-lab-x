from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Iterator


RACINE = Path(__file__).resolve().parents[1]
PANEL_PAR_DEFAUT = (
    RACINE
    / "tasks/dev/pre-cadrage-entretien-client/campagne-v0/panel-identites-v1/panel-identites.json"
)
EMPREINTE_PANEL_ATTENDUE = (
    "c6d31dbc7953f3c21d9f5e3b5ff42d38b8171eab2e5dee52ecfb10920cc849d0"
)

ETATS_VALEURS = ("DECIDED", "REQUESTED", "EXPECTED", "OBSERVED", "INCONNU")

AUTORITES_ATTENDUES = {
    "panel_issue": {
        "author": "ayoahha",
        "issue_number": 66,
        "node_id": "I_kwDOTswBxM8AAAABNcKKmw",
        "url": "https://github.com/ayoahha/benchmark-lab-x/issues/66",
        "created_at": "2026-08-19T20:34:32Z",
        "updated_at": "2026-08-20T09:12:31Z",
        "title": "[M6.3] Figer le panel et les identités complètes",
        "body_sha256": "e48a10102af460a2050fea9d563c7945164149c799bee233e34a04e27b302026",
    },
    "recommended_bundle": {
        "author": "ayoahha",
        "comment_id": 5353760791,
        "node_id": "IC_kwDOTswBxM8AAAABPxvoFw",
        "url": "https://github.com/ayoahha/benchmark-lab-x/issues/66#issuecomment-5353760791",
        "created_at": "2026-08-20T09:04:28Z",
        "updated_at": "2026-08-20T09:04:28Z",
        "body_sha256": "4a7f08736841212484f75cf2c5e267608b3a2a1fc3ee8663d5e4666fc0ff4594",
    },
    "corrected_owner_decision": {
        "author": "ayoahha",
        "comment_id": 5353852348,
        "node_id": "IC_kwDOTswBxM8AAAABPx1NvA",
        "url": "https://github.com/ayoahha/benchmark-lab-x/issues/66#issuecomment-5353852348",
        "created_at": "2026-08-20T09:12:31Z",
        "updated_at": "2026-08-20T09:12:31Z",
        "authority_value": "M6_3_OWNER_DECISION = ACCEPT_RECOMMENDED_BUNDLE",
        "body_sha256": "3f824c3772c29fb866bd293265616e9113d4c9ea5f7a6da6a469eb69e47f8271",
    },
}

PREDECESSEURS_ATTENDUS = {
    "m6_1_authorities": {
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/autorites-v1/autorites.json",
        "sha256": "d551362f35a9e650d78330e79b757bb3e63c892b92fcaa08b48f86599d951d82",
    },
    "m6_2_version_contracts": {
        "path": "tasks/dev/pre-cadrage-entretien-client/campagne-v0/contrats-versionnes-v1/contrats-versionnes.json",
        "sha256": "cf4c2784039edb5cb2be43911d7f3fbc52ff66612c4a4436094602a3dd8d1fcd",
    },
}

SOURCES_P3_ATTENDUES = [
    {
        "path": "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p3-v1/adapters/manual-acquire.py",
        "sha256": "e8d67f5bf6aeff40eb4c3fac569209c589ff0a366e964914a50ab28ab25faefa",
    },
    {
        "path": "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p3-v1/adapters/shared_acquisition.py",
        "sha256": "47fb1ca6a777215f0564c847cae9cbe7bb78313f83c806de3173d30439532da3",
    },
    {
        "path": "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p3-v1/configs/manual/procedure.md",
        "sha256": "12c20bd794e16d7f3e15ed1e93db9571ffbeea6abac4eac8b073fc37001a1baa",
    },
]

CONFIGURATION_GROK = {
    "configuration_id": "grok46_xai_build_oauth",
    "model": {"state": "REQUESTED", "value": "grok-4.6"},
    "revision": {"state": "INCONNU", "value": "INCONNU"},
    "provider": {"state": "DECIDED", "value": "XAI_FIRST_PARTY"},
    "route": {"state": "DECIDED", "value": "GROK_BUILD_OAUTH_PROXY"},
    "endpoint": {
        "state": "EXPECTED",
        "value": "https://cli-chat-proxy.grok.com/v1/responses",
    },
    "parameters": {
        "reasoning": {"state": "DECIDED", "value": "xhigh"},
        "context_tokens": {"state": "DECIDED", "value": 500000},
        "max_output_tokens": {"state": "DECIDED", "value": "INCONNU_STOP_ON_TRUNCATION"},
        "temperature": {"state": "DECIDED", "value": "OMITTED"},
        "top_p": {"state": "DECIDED", "value": "OMITTED"},
        "seed": {"state": "DECIDED", "value": "OMITTED"},
        "stream": {"state": "DECIDED", "value": False},
        "tools": {"state": "DECIDED", "value": "NONE"},
        "web_search": {"state": "DECIDED", "value": False},
        "automatic_retries": {"state": "DECIDED", "value": 0},
    },
    "observed": {
        "served_model": {"state": "OBSERVED", "value": "INCONNU"},
        "served_provider": {"state": "OBSERVED", "value": "INCONNU"},
        "served_route": {"state": "OBSERVED", "value": "INCONNU"},
        "served_parameters": {"state": "OBSERVED", "value": "INCONNU"},
    },
}

CONFIGURATION_KIMI = {
    "configuration_id": "kimi_k3_cursor_cli",
    "model_family": {"state": "REQUESTED", "value": "kimi-k3"},
    "requested_alias": {
        "state": "REQUESTED",
        "value": "cursor-kimi-k3",
        "executable": False,
        "note": "owner wording only; the live Cursor CLI catalog does not expose it",
    },
    "executable_slug": {"state": "DECIDED", "value": "kimi-k3-max"},
    "revision": {"state": "INCONNU", "value": "INCONNU"},
    "provider": {"state": "DECIDED", "value": "CURSOR_CLI"},
    "route": {"state": "DECIDED", "value": "CURSOR_AGENT"},
    "endpoint": {"state": "EXPECTED", "value": "CURSOR_MANAGED_NON_EXPOSED_INCONNU"},
    "parameters": {
        "reasoning": {"state": "DECIDED", "value": "max"},
        "context_tokens": {"state": "INCONNU", "value": "INCONNU"},
        "max_output_tokens": {"state": "INCONNU", "value": "INCONNU"},
        "temperature": {"state": "DECIDED", "value": "OMITTED"},
        "top_p": {"state": "DECIDED", "value": "OMITTED"},
        "seed": {"state": "DECIDED", "value": "OMITTED"},
        "stream": {"state": "DECIDED", "value": False},
        "tools": {"state": "DECIDED", "value": "NONE"},
        "web_search": {"state": "DECIDED", "value": False},
        "automatic_retries": {"state": "DECIDED", "value": 0},
    },
    "observed": {
        "served_model": {"state": "OBSERVED", "value": "INCONNU"},
        "served_provider": {"state": "OBSERVED", "value": "INCONNU"},
        "served_route": {"state": "OBSERVED", "value": "INCONNU"},
        "served_parameters": {"state": "OBSERVED", "value": "INCONNU"},
    },
}

CONFIGURATIONS_ATTENDUES = {
    "grok46_xai_build_oauth": CONFIGURATION_GROK,
    "kimi_k3_cursor_cli": CONFIGURATION_KIMI,
}

EXCLUSIONS_ATTENDUES = {
    "auto_router": "EXCLUDED",
    "openrouter_configurations": "NONE",
    "openrouter_canary": "NOT_APPLICABLE",
    "opencode_zen": "EXCLUDED_FROM_M6_V0",
    "unlisted_configurations": "EXCLUDED_FROM_M6_V0",
}

IDENTITE_PARTAGEE_ATTENDUE = {
    "harness_family": "USE_MANUAL",
    "manual_harness": {
        "identity": "campaign-v0-manual-harness/v1",
        "implementation_state": "DECLARED_IDENTITY_ONLY",
        "implementation_scope": "OUTSIDE_ISSUE_66",
    },
    "shared_core_adapter": {
        "identity": "campaign-v0-shared-core-adapter/v1",
        "implementation_state": "DECLARED_IDENTITY_ONLY",
        "implementation_scope": "OUTSIDE_ISSUE_66",
    },
    "reviewed_source_basis": {
        "role": "REVIEWED_SOURCE_BASIS_ONLY",
        "promotion_to_m6_implementation_or_authority": "FORBIDDEN",
        "sources": SOURCES_P3_ATTENDUES,
    },
    "data_policy": {
        "inputs": "SYNTHETIC_ONLY",
        "account_settings": "NOT_INSPECTED_NOT_ASSERTED",
        "published_provider_policy_references": [
            {
                "provider": "XAI_FIRST_PARTY",
                "url": "https://docs.x.ai/developers/faq/security",
            },
            {
                "provider": "CURSOR_CLI",
                "url": "https://cursor.com/data-use",
            },
        ],
    },
}

LIMITES_ZEN_OPENCODE = {"context_tokens": 1048576, "max_output_tokens": 131072}


class ErreurPanelIdentites(ValueError):
    pass


def _sha256(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def _exiger_champs(
    valeur: object, champs: tuple[str, ...], emplacement: str
) -> dict[str, object]:
    if not isinstance(valeur, dict) or set(valeur) != set(champs):
        raise ErreurPanelIdentites(f"schéma fermé divergent: {emplacement}")
    return valeur


def _exiger_egal(observe: object, attendu: object, emplacement: str) -> None:
    if observe != attendu:
        raise ErreurPanelIdentites(f"valeur divergente: {emplacement}")


def _textes(valeur: object) -> Iterator[str]:
    if isinstance(valeur, str):
        yield valeur
    elif isinstance(valeur, dict):
        for enfant in valeur.values():
            yield from _textes(enfant)
    elif isinstance(valeur, list):
        for enfant in valeur:
            yield from _textes(enfant)


def _valider_reference_fichier(reference: dict[str, object], racine: Path) -> None:
    chemin_brut = reference["path"]
    empreinte = reference["sha256"]
    if not isinstance(chemin_brut, str) or not isinstance(empreinte, str):
        raise ErreurPanelIdentites("référence de fichier non textuelle")
    chemin_relatif = PurePosixPath(chemin_brut)
    if chemin_relatif.is_absolute() or ".." in chemin_relatif.parts:
        raise ErreurPanelIdentites(f"référence de fichier non sûre: {chemin_brut}")
    chemin = racine.joinpath(*chemin_relatif.parts)
    try:
        chemin.resolve(strict=True).relative_to(racine.resolve(strict=True))
        contenu = chemin.read_bytes()
    except (OSError, ValueError) as exc:
        raise ErreurPanelIdentites(
            f"référence de fichier inaccessible: {chemin_brut}"
        ) from exc
    if _sha256(contenu) != empreinte:
        raise ErreurPanelIdentites(f"empreinte de fichier divergente: {chemin_brut}")


def _gardes_configuration(configuration: dict[str, object], emplacement: str) -> None:
    for texte in _textes(configuration):
        normalise = texte.lower().replace("-", "_").replace(" ", "_")
        if "auto_router" in normalise or "autorouter" in normalise:
            raise ErreurPanelIdentites(f"Auto Router dans le panel: {emplacement}")
        if "openrouter" in normalise:
            raise ErreurPanelIdentites(f"OpenRouter dans le panel: {emplacement}")
        if "opencode" in normalise:
            raise ErreurPanelIdentites(f"OpenCode Zen dans le panel: {emplacement}")
    observe = configuration.get("observed")
    if isinstance(observe, dict):
        for cle, entree in observe.items():
            if isinstance(entree, dict) and entree.get("value") != "INCONNU":
                raise ErreurPanelIdentites(
                    f"valeur demandée ou attendue promue en observation: "
                    f"{emplacement}.observed.{cle}"
                )


def _gardes_kimi(configuration: dict[str, object], emplacement: str) -> None:
    slug = configuration.get("executable_slug")
    if not isinstance(slug, dict) or slug.get("value") != "kimi-k3-max":
        raise ErreurPanelIdentites(f"slug Cursor exécutable divergent: {emplacement}")
    alias = configuration.get("requested_alias")
    if not isinstance(alias, dict) or alias.get("executable") is not False:
        raise ErreurPanelIdentites(
            f"alias demandé traité comme exécutable: {emplacement}"
        )
    parametres = configuration.get("parameters")
    if isinstance(parametres, dict):
        for cle, limite in LIMITES_ZEN_OPENCODE.items():
            entree = parametres.get(cle)
            if isinstance(entree, dict) and entree.get("value") == limite:
                raise ErreurPanelIdentites(
                    f"héritage silencieux des limites OpenCode Zen: "
                    f"{emplacement}.parameters.{cle}"
                )


def _gardes_etats(configuration: dict[str, object], emplacement: str) -> None:
    for cle, entree in configuration.items():
        if isinstance(entree, dict) and set(entree) >= {"state", "value"}:
            if entree["state"] not in ETATS_VALEURS:
                raise ErreurPanelIdentites(
                    f"état de valeur inconnu: {emplacement}.{cle}"
                )
        if cle in ("parameters", "observed") and isinstance(entree, dict):
            for sous_cle, sous_entree in entree.items():
                if isinstance(sous_entree, dict) and sous_entree.get(
                    "state"
                ) not in ETATS_VALEURS:
                    raise ErreurPanelIdentites(
                        f"état de valeur inconnu: {emplacement}.{cle}.{sous_cle}"
                    )


def valider_panel_identites_campagne_v0(
    panel: Path = PANEL_PAR_DEFAUT, racine: Path = RACINE
) -> dict[str, object]:
    try:
        contenu = panel.read_bytes()
        document = json.loads(contenu)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErreurPanelIdentites("panel illisible ou JSON invalide") from exc

    racine_document = _exiger_champs(
        document,
        (
            "schema_version",
            "scope",
            "hash_conventions",
            "value_states",
            "owner_authorities",
            "predecessor_artifacts",
            "panel",
            "exclusions",
            "shared_identity",
        ),
        "racine",
    )
    _exiger_egal(
        racine_document["schema_version"],
        "campaign-v0-panel-identities/v1",
        "schema_version",
    )
    _exiger_egal(
        _exiger_champs(
            racine_document["scope"],
            (
                "issue_number",
                "issue_url",
                "parent_issue_number",
                "parent_issue_url",
                "product_version",
            ),
            "scope",
        ),
        {
            "issue_number": 66,
            "issue_url": "https://github.com/ayoahha/benchmark-lab-x/issues/66",
            "parent_issue_number": 19,
            "parent_issue_url": "https://github.com/ayoahha/benchmark-lab-x/issues/19",
            "product_version": "V0",
        },
        "scope",
    )
    _exiger_egal(
        _exiger_champs(
            racine_document["hash_conventions"],
            ("file_sha256", "github_body_sha256"),
            "hash_conventions",
        ),
        {
            "file_sha256": "sha256 of exact file bytes",
            "github_body_sha256": (
                "sha256 of the exact UTF-8 body returned by the GitHub API, "
                "with exactly one trailing newline appended"
            ),
        },
        "hash_conventions",
    )
    _exiger_egal(
        _exiger_champs(
            racine_document["value_states"], ETATS_VALEURS, "value_states"
        ),
        {
            "DECIDED": "fixed by the M6.3 owner decision; never an observation",
            "REQUESTED": "sent as a request; never promoted to an observation",
            "EXPECTED": "anticipated before acquisition; never promoted to an observation",
            "OBSERVED": "actually served value; future observation, INCONNU at this stage",
            "INCONNU": "not published or not exposed; never invented",
        },
        "value_states",
    )

    autorites = _exiger_champs(
        racine_document["owner_authorities"],
        tuple(AUTORITES_ATTENDUES),
        "owner_authorities",
    )
    for identifiant, attendu in AUTORITES_ATTENDUES.items():
        citation = _exiger_champs(
            autorites[identifiant], tuple(attendu), f"owner_authorities.{identifiant}"
        )
        _exiger_egal(citation, attendu, f"owner_authorities.{identifiant}")

    predecesseurs = _exiger_champs(
        racine_document["predecessor_artifacts"],
        tuple(PREDECESSEURS_ATTENDUS),
        "predecessor_artifacts",
    )
    for identifiant, attendu in PREDECESSEURS_ATTENDUS.items():
        reference = _exiger_champs(
            predecesseurs[identifiant],
            ("path", "sha256"),
            f"predecessor_artifacts.{identifiant}",
        )
        _exiger_egal(reference, attendu, f"predecessor_artifacts.{identifiant}")
        _valider_reference_fichier(reference, racine)

    panneau = _exiger_champs(
        racine_document["panel"],
        ("panel_id", "closed", "cardinality", "configurations"),
        "panel",
    )
    _exiger_egal(panneau["panel_id"], "PANEL_GROK46_KIMIK3_FIXED_FIRST_PARTY", "panel.panel_id")
    _exiger_egal(panneau["closed"], True, "panel.closed")
    _exiger_egal(panneau["cardinality"], 2, "panel.cardinality")
    configurations = panneau["configurations"]
    if not isinstance(configurations, list) or len(configurations) != 2:
        raise ErreurPanelIdentites("configurations manquantes ou supplémentaires")
    identifiants = set()
    for index, configuration in enumerate(configurations):
        if not isinstance(configuration, dict):
            raise ErreurPanelIdentites(f"configuration non structurée: [{index}]")
        identifiant = configuration.get("configuration_id")
        if not isinstance(identifiant, str):
            raise ErreurPanelIdentites(f"configuration sans identifiant: [{index}]")
        identifiants.add(identifiant)
    if identifiants != set(CONFIGURATIONS_ATTENDUES):
        raise ErreurPanelIdentites(
            f"configurations manquantes ou supplémentaires: {sorted(identifiants)}"
        )
    for configuration in configurations:
        identifiant = configuration["configuration_id"]
        emplacement = f"panel.configurations[{identifiant}]"
        _gardes_configuration(configuration, emplacement)
        _gardes_etats(configuration, emplacement)
        if identifiant == "kimi_k3_cursor_cli":
            _gardes_kimi(configuration, emplacement)
        _exiger_egal(
            configuration, CONFIGURATIONS_ATTENDUES[identifiant], emplacement
        )

    _exiger_egal(
        _exiger_champs(
            racine_document["exclusions"],
            tuple(EXCLUSIONS_ATTENDUES),
            "exclusions",
        ),
        EXCLUSIONS_ATTENDUES,
        "exclusions",
    )

    identite = _exiger_champs(
        racine_document["shared_identity"],
        tuple(IDENTITE_PARTAGEE_ATTENDUE),
        "shared_identity",
    )
    for cle in ("manual_harness", "shared_core_adapter"):
        composant = identite[cle]
        if isinstance(composant, dict):
            etat = composant.get("implementation_state")
            if etat != "DECLARED_IDENTITY_ONLY":
                raise ErreurPanelIdentites(
                    f"implémentation {cle} promue indûment: {etat}"
                )
            for texte in _textes(composant):
                if "p3-v1" in texte or "preuves-u025" in texte:
                    raise ErreurPanelIdentites(
                        f"héritage P3 silencieux: shared_identity.{cle}"
                    )
    base_revisee = identite.get("reviewed_source_basis")
    if isinstance(base_revisee, dict) and base_revisee.get(
        "promotion_to_m6_implementation_or_authority"
    ) != "FORBIDDEN":
        raise ErreurPanelIdentites("héritage P3 silencieux: reviewed_source_basis")
    _exiger_egal(identite, IDENTITE_PARTAGEE_ATTENDUE, "shared_identity")
    for reference in identite["reviewed_source_basis"]["sources"]:
        _valider_reference_fichier(reference, racine)

    empreinte_panel = _sha256(contenu)
    if empreinte_panel != EMPREINTE_PANEL_ATTENDUE:
        raise ErreurPanelIdentites("panel ou citations divergents")
    return {
        "status": "PANEL_IDENTITES_CAMPAGNE_V0_OK",
        "schema_version": racine_document["schema_version"],
        "panel_sha256": empreinte_panel,
        "configuration_count": len(configurations),
        "harness_family": identite["harness_family"],
    }


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser()
    analyseur.add_argument("panel", nargs="?", type=Path, default=PANEL_PAR_DEFAUT)
    arguments = analyseur.parse_args(argv)
    try:
        recu = valider_panel_identites_campagne_v0(arguments.panel)
    except ErreurPanelIdentites as exc:
        print(f"HOLD_CAMPAIGN_LOCK: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(recu, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
