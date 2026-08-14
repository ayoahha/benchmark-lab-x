from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import stat


@dataclass(frozen=True)
class PaquetApprouveV0:
    nom: str
    version: str
    registre_verite: Path
    stimulus: Path
    temoins_qualification: Path
    empreintes_approuvees: tuple[tuple[str, str], ...]
    provenance_origine: str
    provenance_processus: str
    approbateur: str
    verdict_approbation: str
    paquet_approuve_nom: str
    paquet_approuve_version: str
    empreintes_liees: tuple[tuple[str, str], ...]
    criteres_lies: tuple[str, ...]


@dataclass(frozen=True)
class ResultatAutomatiqueV0:
    statut: str
    origine: str | None
    gates: list[tuple[str, bool]]
    preuve: dict[str, object]


_NOM = "PRECADRAGE-ENTRETIEN-CLIENT-V0"
_VERSION = "V0"
_CRITERES = ("G-001", "G-002", "G-003", "G-004", "G-005", "HR-001")
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
    provenance = json.dumps(
        {
            "origine": paquet.provenance_origine,
            "processus": paquet.provenance_processus,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "identite_paquet": (paquet.nom, paquet.version),
        "empreintes_approuvees": paquet.empreintes_approuvees,
        "empreintes_observees": (),
        "empreinte_candidate": None,
        "empreinte_provenance": _sha256(provenance),
    }


def _evaluer_g005(
    paquet: PaquetApprouveV0, preuve: dict[str, object]
) -> bool:
    chemins = (
        paquet.registre_verite,
        paquet.stimulus,
        paquet.temoins_qualification,
    )
    attendus = tuple(
        (chemin.name, empreinte)
        for chemin, (_, empreinte) in zip(
            chemins, paquet.empreintes_approuvees, strict=False
        )
    )
    try:
        observes = tuple(
            (chemin.name, _sha256(chemin.read_bytes()))
            for chemin in chemins
            if chemin.is_file()
        )
    except OSError:
        return False
    preuve["empreintes_observees"] = observes
    return (
        paquet.nom == _NOM
        and paquet.version == _VERSION
        and len(paquet.empreintes_approuvees) == 3
        and len(observes) == 3
        and tuple(paquet.empreintes_approuvees) == attendus
        and observes == attendus
        and bool(paquet.provenance_origine)
        and bool(paquet.provenance_processus)
        and bool(paquet.approbateur)
        and paquet.verdict_approbation == "APPROUVE"
        and paquet.paquet_approuve_nom == paquet.nom
        and paquet.paquet_approuve_version == paquet.version
        and paquet.empreintes_liees == paquet.empreintes_approuvees
        and paquet.criteres_lies == _CRITERES
    )


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
    if not _evaluer_g003(texte, paquet.stimulus, paquet.registre_verite):
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
