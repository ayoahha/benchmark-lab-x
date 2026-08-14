from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import stat


@dataclass(frozen=True)
class PaquetApprouveV0:
    manifeste: Path
    empreinte_manifeste_approuvee: str
    approbateur: str
    verdict_approbation: str


@dataclass(frozen=True)
class ResultatAutomatiqueV0:
    statut: str
    origine: str | None
    gates: list[tuple[str, bool]]
    preuve: dict[str, object]


_NOM = "PRECADRAGE-ENTRETIEN-CLIENT-V0"
_VERSION = "V0"
_FICHIERS_PAQUET = (
    "brief-proprietaire.md",
    "registre-verite.md",
    "stimulus.md",
    "temoins-qualification.md",
)
_CHAMPS = (
    "artifact_type",
    "version",
    "scenario",
    "client_ready",
    "qualification",
    "conformite",
)
_SECTIONS = (
    "Périmètre",
    "Faits établis",
    "Contraintes critiques",
    "Inconnues",
    "Hypothèses conditionnelles",
    "Contradictions à arbitrer",
    "Risques prioritaires",
    "Questions prioritaires pour l'entretien",
    "Prochaine action",
    "Exclusions",
)
_ANCRE_STIMULUS = re.compile(r"`\[(N-[A-Z]+)\]`")
_SOURCES = re.compile(r"\[sources: (N-[A-Z]+(?:, N-[A-Z]+)*)\]$")
_ID_REGISTRE = re.compile(r"^- ID: ([A-Z][A-Z0-9-]*-\d+)$", re.MULTILINE)
_ID_VISIBLE = re.compile(r"(?<![A-Z0-9-])([A-Z][A-Z0-9-]*-\d+)(?![A-Z0-9-])")
_ELEMENT_LISTE = re.compile(r"^(?:[-*] |\d+\. )")


def _sha256(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def _preuve_initiale(paquet: PaquetApprouveV0) -> dict[str, object]:
    approbation = json.dumps(
        {
            "approbateur": paquet.approbateur,
            "empreinte_manifeste": paquet.empreinte_manifeste_approuvee,
            "verdict": paquet.verdict_approbation,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "identite_paquet": None,
        "empreinte_manifeste_approuvee": paquet.empreinte_manifeste_approuvee,
        "empreinte_manifeste_observee": None,
        "empreintes_approuvees": (),
        "empreintes_observees": (),
        "empreinte_candidate": None,
        "empreinte_provenance": _sha256(approbation),
    }


def _evaluer_g005(
    paquet: PaquetApprouveV0, preuve: dict[str, object]
) -> bool:
    if (
        paquet.manifeste is None
        or not paquet.empreinte_manifeste_approuvee
        or not paquet.approbateur
        or paquet.verdict_approbation != "APPROUVE"
    ):
        return False
    try:
        contenu_manifeste = paquet.manifeste.read_bytes()
        empreinte_manifeste = _sha256(contenu_manifeste)
        preuve["empreinte_manifeste_observee"] = empreinte_manifeste
        if empreinte_manifeste != paquet.empreinte_manifeste_approuvee:
            return False
        manifeste = json.loads(contenu_manifeste)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False

    if not isinstance(manifeste, dict):
        return False
    fichiers = manifeste.get("fichiers")
    if (
        manifeste.get("paquet") != _NOM
        or manifeste.get("product_version") != _VERSION
        or not isinstance(fichiers, list)
        or tuple(
            entree.get("chemin") if isinstance(entree, dict) else None
            for entree in fichiers
        )
        != _FICHIERS_PAQUET
    ):
        return False

    chemins = tuple(paquet.manifeste.parent / nom for nom in _FICHIERS_PAQUET)
    attendus = tuple(
        (nom, entree.get("sha256"))
        for nom, entree in zip(_FICHIERS_PAQUET, fichiers, strict=True)
    )
    preuve["identite_paquet"] = (
        manifeste["paquet"],
        manifeste["product_version"],
    )
    preuve["empreintes_approuvees"] = attendus
    try:
        observes = tuple(
            (chemin.name, _sha256(chemin.read_bytes())) for chemin in chemins
        )
    except OSError:
        return False
    preuve["empreintes_observees"] = observes
    return observes == attendus


def _lire_candidate(
    sortie_candidate: Path, preuve: dict[str, object]
) -> str | None:
    try:
        if not stat.S_ISREG(sortie_candidate.stat().st_mode):
            return None
    except OSError:
        return None
    contenu = sortie_candidate.read_bytes()
    preuve["empreinte_candidate"] = _sha256(contenu)
    try:
        return contenu.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _parser_g001(texte: str) -> dict[str, str] | None:
    lignes = texte.splitlines()
    if not lignes or lignes[0] != "---":
        return None
    try:
        fin_frontmatter = lignes.index("---", 1)
    except ValueError:
        return None
    champs: dict[str, str] = {}
    for ligne in lignes[1:fin_frontmatter]:
        if ":" not in ligne:
            return None
        cle, valeur = ligne.split(":", 1)
        if cle not in _CHAMPS or cle in champs:
            return None
        champs[cle] = valeur[1:] if valeur.startswith(" ") else valeur
    if tuple(champs) != _CHAMPS:
        return None
    titres = [
        ligne[2:]
        for ligne in lignes[fin_frontmatter + 1 :]
        if ligne.startswith("# ")
    ]
    if tuple(titres) != _SECTIONS:
        return None
    return champs


def _evaluer_g003(texte: str, stimulus: Path, registre_verite: Path) -> bool:
    ancres_autorisees = set(_ANCRE_STIMULUS.findall(stimulus.read_text(encoding="utf-8")))
    identifiants_internes = set(
        _ID_REGISTRE.findall(registre_verite.read_text(encoding="utf-8"))
    )
    lignes = texte.splitlines()
    fin_frontmatter = lignes.index("---", 1)
    blocs: list[str] = []
    courant: list[str] = []
    for ligne in lignes[fin_frontmatter + 1 :]:
        if not ligne or ligne.startswith("# "):
            if courant:
                blocs.append(" ".join(courant))
                courant = []
            continue
        if _ELEMENT_LISTE.match(ligne) and courant:
            blocs.append(" ".join(courant))
            courant = []
        courant.append(ligne)
    if courant:
        blocs.append(" ".join(courant))
    for bloc in blocs:
        correspondance = _SOURCES.search(bloc)
        if correspondance is None:
            return False
        ancres = correspondance.group(1).split(", ")
        if any(ancre not in ancres_autorisees for ancre in ancres):
            return False
        if identifiants_internes.intersection(_ID_VISIBLE.findall(bloc)):
            return False
    return bool(blocs)


def valider_pre_cadrage_v0(
    paquet: PaquetApprouveV0, sortie_candidate: Path
) -> ResultatAutomatiqueV0:
    preuve = _preuve_initiale(paquet)
    if not _evaluer_g005(paquet, preuve):
        return ResultatAutomatiqueV0(
            statut="HARNESS_ERROR",
            origine="HARNESS_ERROR",
            gates=[("G-005", False)],
            preuve=preuve,
        )
    try:
        texte = _lire_candidate(sortie_candidate, preuve)
    except OSError:
        return ResultatAutomatiqueV0(
            statut="HARNESS_ERROR",
            origine="HARNESS_ERROR",
            gates=[("G-005", True)],
            preuve=preuve,
        )
    champs = _parser_g001(texte) if texte is not None else None
    if champs is None:
        return ResultatAutomatiqueV0(
            statut="FAIL",
            origine="CANDIDATE_ERROR",
            gates=[("G-005", True), ("G-001", False)],
            preuve=preuve,
        )
    if (
        champs["client_ready"] != "false"
        or champs["conformite"] != "NON_EVALUEE"
    ):
        return ResultatAutomatiqueV0(
            statut="FAIL",
            origine="CANDIDATE_ERROR",
            gates=[("G-005", True), ("G-001", True), ("G-002", False)],
            preuve=preuve,
        )
    gates = [
        ("G-005", True),
        ("G-001", True),
        ("G-002", True),
    ]
    racine_paquet = paquet.manifeste.parent
    if not _evaluer_g003(
        texte,
        racine_paquet / "stimulus.md",
        racine_paquet / "registre-verite.md",
    ):
        return ResultatAutomatiqueV0(
            statut="FAIL",
            origine="CANDIDATE_ERROR",
            gates=[*gates, ("G-003", False)],
            preuve=preuve,
        )
    gates.append(("G-003", True))
    if (
        champs["artifact_type"] != "pre_cadrage_entretien_client"
        or champs["version"] != "V0"
        or champs["scenario"] != "synthetique"
        or champs["qualification"] not in {"QUALIFIABLE", "NON_QUALIFIABLE"}
    ):
        return ResultatAutomatiqueV0(
            statut="FAIL",
            origine="CANDIDATE_ERROR",
            gates=[*gates, ("G-004", False)],
            preuve=preuve,
        )
    return ResultatAutomatiqueV0(
        statut="PASS",
        origine=None,
        gates=[*gates, ("G-004", True)],
        preuve=preuve,
    )
