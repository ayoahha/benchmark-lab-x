# /// script
# requires-python = ">=3.12,<3.13"
# ///
"""Restitution humaine V1, registre de panel abonnement et vérifications.

Interface figée :
- uv run tools/campagne_v1.py enregistrer [--registre <chemin>] --fichier <chemin>
- uv run tools/campagne_v1.py panel [--registre <chemin>]
- uv run tools/campagne_v1.py autorisations [--configuration <id>]
- uv run tools/campagne_v1.py acquerir --local --configuration <id>
- uv run tools/campagne_v1.py acquerir --officiel --configuration <id>
- uv run tools/campagne_v1.py preflight --configuration <id>
- uv run tools/campagne_v1.py verrouiller
- uv run tools/campagne_v1.py valider
- uv run tools/campagne_v1.py restituer
- uv run tools/campagne_v1.py verifier-restitution
"""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

VERSION_VUE = "restitution-humaine-v1/vue/1"

_RACINE_CAMPAGNE_V1 = Path("tasks/dev/pre-cadrage-entretien-client/campagne-v1")
CHEMIN_ETAT = _RACINE_CAMPAGNE_V1 / "etat-v1.json"
CHEMIN_PAGE = _RACINE_CAMPAGNE_V1 / "restitution-humaine-v1" / "index.html"

# Registre officiel de campagne V1 : le panel vit dans ces fichiers, jamais dans le code.
REGISTRE_OFFICIEL = _RACINE_CAMPAGNE_V1 / "registre-panel-v1"

# Configurations locales non officielles : seules cibles de 'acquerir --local'.
CONFIGURATIONS_LOCALES = _RACINE_CAMPAGNE_V1 / "configurations-locales"

SCHEMA_RECU = "campagne-v1-recu-abonnement/v1"
PROFIL_MESURE_RECU = "subscription"

# Sources citées telles quelles par le reçu, sans promotion ni approbation.
CHEMIN_CARTE = "tasks/dev/pre-cadrage-entretien-client/brief-proprietaire.md"
CHEMIN_PAQUET = "tasks/dev/pre-cadrage-entretien-client/manifeste-paquet.json"
CHEMIN_STIMULUS = "tasks/dev/pre-cadrage-entretien-client/stimulus.md"

# Vocabulaire incident fermé du profil abonnement V1.
INCIDENTS_V1 = (
    "PROVIDER_FAILURE",
    "HARNESS_ERROR",
    "IDENTITY_MISMATCH",
    "MISSING_OBSERVATION",
    "QUOTA_EXHAUSTED",
)
# Incidents exigeant un fait explicite et attribuable, jamais déduits d'une absence.
INCIDENTS_ATTRIBUABLES = ("PROVIDER_FAILURE", "IDENTITY_MISMATCH", "QUOTA_EXHAUSTED")

SCHEMA_CONFIGURATION = "campagne-v1-configuration-abonnement/v1"
INCONNU = "INCONNU"
TYPES_INTERFACE = ("cli", "ide", "application", "web")
# Jetons machine repris à l'identique du harnais V0.
JETON_FICHIER_PROMPT = "__PROMPT_FILE__"
JETON_ESPACE_ISOLE = "__ISOLATED_WORKSPACE__"

_MOTIF_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Sources autorisées de la restitution, avec la section qui fait autorité.
SOURCES_AUTORISEES = (
    ("docs/PRD.md", "section 14"),
    ("docs/ARD.md", "section 7"),
    ("docs/RULES.md", "document entier"),
    ("tasks/dev/pre-cadrage-entretien-client/manifeste-paquet.json", "instantané immuable"),
    (
        "tasks/dev/pre-cadrage-entretien-client/campagne-v0/rapport-decision-m10-2-v1/rapport-interne.md",
        "antériorité V0 séparée",
    ),
)

CLASSES_MSW = ("fait", "deduction", "planifie")

# La page produite est autonome : aucune de ces séquences n'y est tolérée.
SEQUENCES_DISTANTES = (
    "http://",
    "https://",
    "src=",
    "<script",
    "<link",
    "<img",
    "@import",
    "url(",
)

JETONS_NORMATIFS = ("INCONNU", "NON_DEFINI", "HARNESS_ERROR", "ABSTENTION")

# Étapes futures dérivées des sources normatives, toutes marquées à venir.
ETAPES_FUTURES = (
    (
        "panel-abonnement",
        "Alimenter le panel abonnement avec des identités complètes : "
        "produit, plan, quotas, resets, interface, harnais et intervention humaine.",
        "docs/PRD.md",
        "section 14",
    ),
    (
        "qualification-independante",
        "Qualifier le profil abonnement indépendamment des profils API et "
        "auto-hébergé, sans comparaison inter-profils sans contrat commun explicite.",
        "docs/ARD.md",
        "section 7",
    ),
    (
        "approbation-empreintes",
        "Faire approuver par un humain, via des empreintes, les objets versionnés "
        "nécessaires au profil abonnement.",
        "docs/RULES.md",
        "U-009",
    ),
    (
        "recus-immuables",
        "Écrire un reçu immuable pour chaque acquisition du profil abonnement.",
        "docs/RULES.md",
        "U-010",
    ),
    (
        "acceptabilite-officielle",
        "Établir chaque acceptabilité officielle par la formule PASS automatique "
        "plus ACCEPTABLE humain, sous revue humaine aveugle.",
        "docs/RULES.md",
        "U-013 et U-014",
    ),
    (
        "restitution-ou-abstention",
        "Restituer les mesures centrales avec leurs dénominateurs et leurs "
        "manquants, ou prononcer l'abstention correspondante.",
        "docs/RULES.md",
        "U-018 et U-019",
    ),
)


class ErreurRestitution(Exception):
    """Entrée absente, invalide ou hors du périmètre XS-01."""


class ErreurConfiguration(Exception):
    """Refus fail-closed d'une configuration, nommant le champ fautif."""


def _exiger_chaine(chemin_champ: str, valeur: object) -> None:
    if not isinstance(valeur, str) or not valeur.strip():
        raise ErreurConfiguration(f"champ '{chemin_champ}' : chaîne non vide attendue")


def _exiger_montant_ou_inconnu(chemin_champ: str, valeur: object) -> None:
    if valeur == INCONNU:
        return
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)) or valeur < 0:
        raise ErreurConfiguration(
            f"champ '{chemin_champ}' : nombre positif ou 'INCONNU' attendu"
        )


def _exiger_entier_ou_inconnu(chemin_champ: str, valeur: object) -> None:
    if valeur == INCONNU:
        return
    if isinstance(valeur, bool) or not isinstance(valeur, int) or valeur < 0:
        raise ErreurConfiguration(
            f"champ '{chemin_champ}' : entier positif ou 'INCONNU' attendu"
        )


def _exiger_type_interface(chemin_champ: str, valeur: object) -> None:
    if valeur not in TYPES_INTERFACE:
        raise ErreurConfiguration(
            f"champ '{chemin_champ}' hors vocabulaire "
            f"({' | '.join(TYPES_INTERFACE)})"
        )


def _exiger_liste_de_chaines(chemin_champ: str, valeur: object) -> None:
    if (
        not isinstance(valeur, list)
        or not valeur
        or any(not isinstance(element, str) or not element.strip() for element in valeur)
    ):
        raise ErreurConfiguration(
            f"champ '{chemin_champ}' : liste non vide de chaînes non vides attendue"
        )


def _exiger_stdin_fichier(chemin_champ: str, valeur: object) -> None:
    if valeur != JETON_FICHIER_PROMPT:
        raise ErreurConfiguration(
            f"champ '{chemin_champ}' : jeton machine '{JETON_FICHIER_PROMPT}' attendu"
        )


def _exiger_prompt_exactement_une_fois(harnais: dict) -> None:
    """Le prompt vit dans argv ou dans stdin_fichier, jamais zéro ni deux fois"""
    occurrences = sum(
        element.count(JETON_FICHIER_PROMPT) for element in harnais["argv"]
    )
    if "stdin_fichier" in harnais:
        occurrences += 1
    if occurrences != 1:
        raise ErreurConfiguration(
            "champs 'harnais.argv' et 'harnais.stdin_fichier' : le jeton machine "
            f"'{JETON_FICHIER_PROMPT}' doit apparaître exactement une fois dans "
            f"leur union ({occurrences} au lieu de 1)"
        )


def _exiger_espace_isole(chemin_champ: str, valeur: object) -> None:
    if valeur != JETON_ESPACE_ISOLE:
        raise ErreurConfiguration(
            f"champ '{chemin_champ}' : jeton machine '{JETON_ESPACE_ISOLE}' attendu"
        )


def _exiger_delai(chemin_champ: str, valeur: object) -> None:
    if isinstance(valeur, bool) or not isinstance(valeur, int) or valeur < 0:
        raise ErreurConfiguration(
            f"champ '{chemin_champ}' : entier de secondes (>= 0) attendu"
        )


_CHAMPS_QUOTA = {
    "unite": _exiger_chaine,
    "valeur": _exiger_entier_ou_inconnu,
    "portee": _exiger_chaine,
    "reset_fenetre": _exiger_chaine,
    "reset_ancrage": _exiger_chaine,
    "reset_au_depassement": _exiger_chaine,
}

_TABLES_CONFIGURATION = {
    "produit": {"nom": _exiger_chaine, "editeur": _exiger_chaine},
    "plan": {
        "nom": _exiger_chaine,
        "prix_montant": _exiger_montant_ou_inconnu,
        "prix_devise": _exiger_chaine,
        "periode": _exiger_chaine,
        "source_url": _exiger_chaine,
        "date_publication": _exiger_chaine,
        "date_consultation": _exiger_chaine,
    },
    "interface": {"type": _exiger_type_interface, "version": _exiger_chaine},
    "modele": {"demande": _exiger_chaine},
    "harnais": {
        "argv": _exiger_liste_de_chaines,
        "espace_de_travail": _exiger_espace_isole,
        "delai_secondes": _exiger_delai,
    },
    "intervention_humaine": {"etapes": _exiger_liste_de_chaines},
}

# Seul champ optionnel du contrat générique : la source stdin du prompt (XS-02)
_CHAMPS_OPTIONNELS = {"harnais": {"stdin_fichier": _exiger_stdin_fichier}}


def _valider_table(
    prefixe: str, table: object, champs: dict, optionnels: dict | None = None
) -> None:
    optionnels = optionnels or {}
    if not isinstance(table, dict):
        raise ErreurConfiguration(f"champ '{prefixe}' absent ou n'est pas une table")
    for cle in table:
        if cle not in champs and cle not in optionnels:
            raise ErreurConfiguration(f"champ '{prefixe}.{cle}' hors vocabulaire")
    for cle, exiger in champs.items():
        if cle not in table:
            raise ErreurConfiguration(f"champ '{prefixe}.{cle}' absent")
        exiger(f"{prefixe}.{cle}", table[cle])
    for cle, exiger in optionnels.items():
        if cle in table:
            exiger(f"{prefixe}.{cle}", table[cle])


def _valider_configuration(donnees: object) -> dict:
    if not isinstance(donnees, dict):
        raise ErreurConfiguration("champ 'schema_version' absent : table TOML attendue")
    cles_autorisees = {"schema_version", "configuration_id", "quota", *_TABLES_CONFIGURATION}
    for cle in donnees:
        if cle not in cles_autorisees:
            raise ErreurConfiguration(f"champ '{cle}' hors vocabulaire")
    if donnees.get("schema_version") != SCHEMA_CONFIGURATION:
        raise ErreurConfiguration(
            f"champ 'schema_version' : '{SCHEMA_CONFIGURATION}' attendu"
        )
    identifiant = donnees.get("configuration_id")
    if not isinstance(identifiant, str) or not _MOTIF_SLUG.match(identifiant):
        raise ErreurConfiguration(
            "champ 'configuration_id' : slug stable attendu (minuscules, chiffres, tirets)"
        )
    for nom, champs in _TABLES_CONFIGURATION.items():
        _valider_table(nom, donnees.get(nom), champs, _CHAMPS_OPTIONNELS.get(nom))
    _exiger_prompt_exactement_une_fois(donnees["harnais"])
    quotas = donnees.get("quota")
    if not isinstance(quotas, list) or not quotas:
        raise ErreurConfiguration("champ 'quota' : au moins une table [[quota]] attendue")
    for rang, quota in enumerate(quotas, start=1):
        _valider_table(f"quota[{rang}]", quota, _CHAMPS_QUOTA)
    return donnees


def _charger_configuration(chemin: Path) -> dict:
    try:
        donnees = tomllib.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as erreur:
        raise ErreurConfiguration(
            f"configuration illisible : {chemin} ({erreur})"
        ) from erreur
    return _valider_configuration(donnees)


class ErreurRecu(Exception):
    """Refus fail-closed d'un reçu V1 abonnement, nommant le fait fautif."""


def octets_canoniques(valeur: object) -> bytes:
    """Convention canonique reprise de tools/campaign_v0_shared_core_adapter.py."""
    return (
        json.dumps(
            valeur,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def adresse_canonique(valeur: object) -> str:
    return hashlib.sha256(octets_canoniques(valeur)).hexdigest()


_MOTIF_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _exiger_cles(nom: str, valeur: object, cles: set[str]) -> dict:
    if not isinstance(valeur, dict) or set(valeur) != cles:
        raise ErreurRecu(f"champ '{nom}' : clés exactes {sorted(cles)} attendues")
    return valeur


def _exiger_sha256_recu(nom: str, valeur: object) -> None:
    if not isinstance(valeur, str) or not _MOTIF_SHA256.match(valeur):
        raise ErreurRecu(f"champ '{nom}' : SHA-256 hexadécimal attendu")


def _valider_source_recu(nom: str, valeur: object, chemin_attendu: str) -> dict:
    source = _exiger_cles(nom, valeur, {"chemin", "sha256"})
    if source["chemin"] != chemin_attendu:
        raise ErreurRecu(f"champ '{nom}.chemin' : '{chemin_attendu}' attendu")
    _exiger_sha256_recu(f"{nom}.sha256", source["sha256"])
    return source


def _valider_execution_recu(valeur: object) -> None:
    if not isinstance(valeur, dict):
        raise ErreurRecu("champ 'execution' : table attendue")
    etat = valeur.get("etat")
    if etat == "OBSERVED":
        # La preuve locale d'OBSERVED est la capture elle-même : sortie,
        # code de sortie et latence mesurés par le processus local.
        observe = _exiger_cles(
            "execution", valeur, {"etat", "sortie", "code_sortie", "latence_ms"}
        )
        sortie = _exiger_cles("execution.sortie", observe["sortie"], {"stdout", "stderr"})
        if not isinstance(sortie["stdout"], str) or not isinstance(sortie["stderr"], str):
            raise ErreurRecu("champ 'execution.sortie' : textes capturés attendus")
        if isinstance(observe["code_sortie"], bool) or not isinstance(
            observe["code_sortie"], int
        ):
            raise ErreurRecu("champ 'execution.code_sortie' : entier observé attendu")
        latence = observe["latence_ms"]
        if isinstance(latence, bool) or not isinstance(latence, int) or latence < 0:
            raise ErreurRecu("champ 'execution.latence_ms' : entier positif attendu")
        return
    if etat == "INCIDENT":
        cles = {"etat", "incident", "fait"}
        if valeur.get("incident") in INCIDENTS_ATTRIBUABLES:
            cles.add("preuve_attribuable")
        incident = _exiger_cles("execution", valeur, cles)
        if incident["incident"] not in INCIDENTS_V1:
            raise ErreurRecu(
                f"champ 'execution.incident' : '{incident['incident']}' hors "
                f"vocabulaire ({' | '.join(INCIDENTS_V1)})"
            )
        if not isinstance(incident["fait"], str) or not incident["fait"].strip():
            raise ErreurRecu("champ 'execution.fait' : fait fautif nommé attendu")
        if incident["incident"] in INCIDENTS_ATTRIBUABLES:
            preuve = incident["preuve_attribuable"]
            if not isinstance(preuve, str) or not preuve.strip():
                raise ErreurRecu(
                    f"champ 'execution.preuve_attribuable' : l'incident "
                    f"'{incident['incident']}' exige un fait explicite et "
                    "attribuable, jamais une déduction d'absence"
                )
        return
    raise ErreurRecu(
        f"champ 'execution.etat' : '{etat}' hors vocabulaire (OBSERVED | INCIDENT)"
    )


def _valider_observable_sans_preuve(nom: str, valeur: object) -> None:
    """INCONNU reste INCONNU : OBSERVED exige une preuve locale dans le reçu."""
    if valeur == INCONNU:
        return
    if isinstance(valeur, dict) and valeur.get("etat") == "OBSERVED":
        observe = _exiger_cles(nom, valeur, {"etat", "valeur", "preuve"})
        preuve = observe["preuve"]
        if isinstance(preuve, str) and preuve.strip():
            return
        raise ErreurRecu(
            f"champ '{nom}' : OBSERVED sans preuve refusé, la valeur reste INCONNU"
        )
    raise ErreurRecu(
        f"champ '{nom}' : 'INCONNU' ou observation prouvée attendu"
    )


_CLES_CHARGE_RECU = {
    "measurement_profile",
    "creneau",
    "predecesseur_adresse_contenu",
    "carte",
    "paquet",
    "stimulus",
    "configuration",
    "plan_declare",
    "interface_declaree",
    "quota_observe",
    "requete",
    "execution",
    "provenance_servie",
}


def _valider_recu(enveloppe: object) -> dict:
    recu = _exiger_cles(
        "recu", enveloppe, {"schema_version", "content_address", "payload"}
    )
    if recu["schema_version"] != SCHEMA_RECU:
        raise ErreurRecu(f"champ 'schema_version' : '{SCHEMA_RECU}' attendu")
    adresse = _exiger_cles(
        "content_address", recu["content_address"], {"algorithm", "sha256"}
    )
    if adresse["algorithm"] != "SHA256":
        raise ErreurRecu("champ 'content_address.algorithm' : 'SHA256' attendu")
    charge = _exiger_cles("payload", recu["payload"], _CLES_CHARGE_RECU)
    if adresse["sha256"] != adresse_canonique(charge):
        raise ErreurRecu(
            "champ 'content_address.sha256' : adresse de contenu divergente du "
            "payload canonique"
        )
    if charge["measurement_profile"] != PROFIL_MESURE_RECU:
        raise ErreurRecu(
            f"champ 'measurement_profile' : '{PROFIL_MESURE_RECU}' attendu"
        )
    predecesseur = charge["predecesseur_adresse_contenu"]
    if predecesseur is not None:
        _exiger_sha256_recu("predecesseur_adresse_contenu", predecesseur)
    _valider_source_recu("carte", charge["carte"], CHEMIN_CARTE)
    _valider_source_recu("paquet", charge["paquet"], CHEMIN_PAQUET)
    stimulus = _valider_source_recu("stimulus", charge["stimulus"], CHEMIN_STIMULUS)
    configuration = _exiger_cles(
        "configuration", charge["configuration"], {"identifiant", "chemin", "sha256"}
    )
    if not isinstance(configuration["identifiant"], str) or not _MOTIF_SLUG.match(
        configuration["identifiant"]
    ):
        raise ErreurRecu("champ 'configuration.identifiant' : slug stable attendu")
    _exiger_sha256_recu("configuration.sha256", configuration["sha256"])
    creneau_attendu = f"{configuration['identifiant']}:{stimulus['sha256']}"
    if charge["creneau"] != creneau_attendu:
        raise ErreurRecu(
            "champ 'creneau' : dérivation exacte "
            "'<configuration_id>:<sha256 du stimulus>' attendue"
        )
    for nom in ("plan_declare", "interface_declaree"):
        declare = _exiger_cles(nom, charge[nom], {"etat", "champs"})
        if declare["etat"] != "DECLARE" or not isinstance(declare["champs"], dict):
            raise ErreurRecu(f"champ '{nom}' : état DECLARE et champs déclarés attendus")
    _valider_observable_sans_preuve("quota_observe", charge["quota_observe"])
    requete = _exiger_cles(
        "requete",
        charge["requete"],
        {"etat", "argv_resolu", "mode_stdin", "espace_de_travail"},
    )
    if (
        requete["etat"] != "REQUESTED"
        or not isinstance(requete["argv_resolu"], list)
        or not requete["argv_resolu"]
        or any(not isinstance(element, str) for element in requete["argv_resolu"])
        or requete["espace_de_travail"] != JETON_ESPACE_ISOLE
    ):
        raise ErreurRecu(
            "champ 'requete' : descripteur REQUESTED avec argv résolu et espace "
            "isolé attendu"
        )
    _valider_execution_recu(charge["execution"])
    _valider_observable_sans_preuve("provenance_servie", charge["provenance_servie"])
    return recu


def _charger_recus(repertoire: Path) -> list[tuple[Path, dict]]:
    """Reçus valides du répertoire, chaînés, dans l'ordre matériel du chaînage."""
    if not repertoire.is_dir():
        return []
    par_adresse: dict[str, tuple[Path, dict]] = {}
    for chemin in sorted(repertoire.iterdir()):
        try:
            enveloppe = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
            raise ErreurRecu(f"reçu illisible : {chemin.name} ({erreur})") from erreur
        recu = _valider_recu(enveloppe)
        adresse = recu["content_address"]["sha256"]
        if chemin.name != f"{adresse}.json":
            raise ErreurRecu(
                f"reçu '{chemin.name}' : nom de fichier divergent de l'adresse de "
                f"contenu {adresse}"
            )
        par_adresse[adresse] = (chemin, recu)
    if not par_adresse:
        return []
    predecesseurs = [
        recu["payload"]["predecesseur_adresse_contenu"]
        for _, recu in par_adresse.values()
    ]
    non_nuls = [adresse for adresse in predecesseurs if adresse is not None]
    if len(non_nuls) != len(set(non_nuls)) or predecesseurs.count(None) != 1:
        raise ErreurRecu("chaînage append-only divergent : prédécesseurs ambigus")
    for adresse in non_nuls:
        if adresse not in par_adresse:
            raise ErreurRecu(f"prédécesseur inconnu du répertoire : {adresse}")
    creneaux = [recu["payload"]["creneau"] for _, recu in par_adresse.values()]
    if len(creneaux) != len(set(creneaux)):
        raise ErreurRecu("collision append-only : deux reçus occupent le même créneau")
    # Reconstruction de l'ordre matériel par le chaînage, du premier au dernier.
    suivant = {
        recu["payload"]["predecesseur_adresse_contenu"]: adresse
        for adresse, (_, recu) in par_adresse.items()
    }
    ordonnes: list[tuple[Path, dict]] = []
    courant = suivant.get(None)
    while courant is not None:
        ordonnes.append(par_adresse[courant])
        courant = suivant.get(courant)
    if len(ordonnes) != len(par_adresse):
        raise ErreurRecu("chaînage append-only divergent : chaîne non linéaire")
    return ordonnes


def _executer_borne(
    argv: list[str], entree: bytes, espace: Path, delai_secondes: int
) -> dict:
    """Exécute argv dans une nouvelle session ; au délai, termine le groupe entier."""
    depart = time.monotonic()
    try:
        processus = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=espace,
            start_new_session=True,
        )
    except OSError as erreur:
        return {
            "etat": "INCIDENT",
            "incident": "HARNESS_ERROR",
            "fait": f"lancement local impossible : {erreur}",
        }
    try:
        stdout, stderr = processus.communicate(entree, timeout=delai_secondes)
    except subprocess.TimeoutExpired:
        # La nouvelle session fait du parent le chef de groupe : la terminaison
        # puis la mise à mort visent le groupe entier, descendants compris.
        groupe = processus.pid
        try:
            os.killpg(groupe, signal.SIGTERM)
            limite = time.monotonic() + 0.5
            while time.monotonic() < limite and processus.poll() is None:
                time.sleep(0.02)
            os.killpg(groupe, signal.SIGKILL)
        except ProcessLookupError:
            pass
        processus.wait()
        for tube in (processus.stdin, processus.stdout, processus.stderr):
            tube.close()
        return {
            "etat": "INCIDENT",
            "incident": "HARNESS_ERROR",
            "fait": (
                f"délai local de {delai_secondes} s dépassé : terminaison envoyée "
                "au groupe de processus entier, puis groupe tué et parent récolté"
            ),
        }
    latence_ms = int((time.monotonic() - depart) * 1000)
    return {
        "etat": "OBSERVED",
        "sortie": {
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        },
        "code_sortie": processus.returncode,
        "latence_ms": latence_ms,
    }


def acquerir_local(racine: Path, identifiant: str) -> int:
    # Confinement : le contrat de slug est vérifié avant toute construction ou
    # résolution de chemin ; traversée, séparateur et chemin absolu sont refusés
    # sans lecture de cible, sans exécution et sans écriture de reçu
    if not _MOTIF_SLUG.match(identifiant):
        print(
            f"ECHEC champ 'configuration_id' : '{identifiant}' n'est pas un slug "
            "stable (minuscules, chiffres, tirets) ; identifiant refusé avant "
            "toute résolution de chemin hors du répertoire local"
        )
        return 1
    chemin_configuration = racine / CONFIGURATIONS_LOCALES / f"{identifiant}.toml"
    if not chemin_configuration.is_file():
        print(
            f"ECHEC configuration locale absente : '{identifiant}' introuvable "
            f"dans {CONFIGURATIONS_LOCALES.as_posix()}"
        )
        return 1
    try:
        configuration = _charger_configuration(chemin_configuration)
    except ErreurConfiguration as erreur:
        print(f"ECHEC {erreur}")
        return 1
    if configuration["configuration_id"] != identifiant:
        print(
            f"ECHEC champ 'configuration_id' : "
            f"'{configuration['configuration_id']}' ne correspond pas à "
            f"'{identifiant}'"
        )
        return 1
    try:
        etat = _charger_etat(racine)
    except ErreurRestitution as erreur:
        print(f"ECHEC {erreur}")
        return 1
    sources: dict[str, dict] = {}
    for nom, relatif in (
        ("carte", CHEMIN_CARTE),
        ("paquet", CHEMIN_PAQUET),
        ("stimulus", CHEMIN_STIMULUS),
    ):
        chemin_source = racine / relatif
        if not chemin_source.is_file():
            print(f"ECHEC source du reçu absente : {relatif}")
            return 1
        sources[nom] = {"chemin": relatif, "sha256": _sha256_fichier(chemin_source)}
    creneau = f"{identifiant}:{sources['stimulus']['sha256']}"
    repertoire = _repertoire_recus(racine, etat)
    try:
        recus = _charger_recus(repertoire)
    except ErreurRecu as erreur:
        print(f"ECHEC {erreur}")
        return 1
    for _, existant in recus:
        if existant["payload"]["creneau"] == creneau:
            print(
                f"ECHEC collision append-only : le créneau '{creneau}' est déjà "
                "occupé, le reçu existant reste inchangé"
            )
            return 1
    predecesseur = recus[-1][1]["content_address"]["sha256"] if recus else None
    harnais = configuration["harnais"]
    stimulus_octets = (racine / CHEMIN_STIMULUS).read_bytes()
    with tempfile.TemporaryDirectory() as espace_texte:
        espace = Path(espace_texte)
        fichier_prompt = espace / "stimulus.md"
        fichier_prompt.write_bytes(stimulus_octets)
        argv_execute = [
            element.replace(JETON_ESPACE_ISOLE, str(espace)).replace(
                JETON_FICHIER_PROMPT, str(fichier_prompt)
            )
            for element in harnais["argv"]
        ]
        entree = stimulus_octets if "stdin_fichier" in harnais else b""
        execution = _executer_borne(
            argv_execute, entree, espace, harnais["delai_secondes"]
        )
        # L'argv consigné remplace les chemins volatils par leurs jetons machine.
        argv_resolu = [
            element.replace(str(fichier_prompt), JETON_FICHIER_PROMPT).replace(
                str(espace), JETON_ESPACE_ISOLE
            )
            for element in argv_execute
        ]
    charge = {
        "measurement_profile": PROFIL_MESURE_RECU,
        "creneau": creneau,
        "predecesseur_adresse_contenu": predecesseur,
        "carte": sources["carte"],
        "paquet": sources["paquet"],
        "stimulus": sources["stimulus"],
        "configuration": {
            "identifiant": identifiant,
            "chemin": (CONFIGURATIONS_LOCALES / f"{identifiant}.toml").as_posix(),
            "sha256": _sha256_fichier(chemin_configuration),
        },
        "plan_declare": {"etat": "DECLARE", "champs": configuration["plan"]},
        "interface_declaree": {"etat": "DECLARE", "champs": configuration["interface"]},
        "quota_observe": INCONNU,
        "requete": {
            "etat": "REQUESTED",
            "argv_resolu": argv_resolu,
            "mode_stdin": (
                JETON_FICHIER_PROMPT if "stdin_fichier" in harnais else "aucun"
            ),
            "espace_de_travail": JETON_ESPACE_ISOLE,
        },
        "execution": execution,
        "provenance_servie": INCONNU,
    }
    enveloppe = {
        "schema_version": SCHEMA_RECU,
        "content_address": {"algorithm": "SHA256", "sha256": adresse_canonique(charge)},
        "payload": charge,
    }
    try:
        _valider_recu(enveloppe)
    except ErreurRecu as erreur:
        print(f"ECHEC reçu incohérent, rien n'est écrit : {erreur}")
        return 1
    repertoire.mkdir(parents=True, exist_ok=True)
    adresse = enveloppe["content_address"]["sha256"]
    destination = repertoire / f"{adresse}.json"
    try:
        # Création exclusive : un reçu existant n'est jamais réécrit.
        with open(destination, "xb") as fichier:
            fichier.write(octets_canoniques(enveloppe))
    except FileExistsError:
        print(f"ECHEC collision append-only : le reçu {destination.name} existe déjà")
        return 1
    print(
        f"reçu V1 abonnement écrit : "
        f"{(destination.relative_to(racine)).as_posix()}"
    )
    print(f"créneau : {creneau}")
    print(f"adresse de contenu : {adresse}")
    print(f"prédécesseur : {predecesseur if predecesseur is not None else 'null'}")
    if execution["etat"] == "INCIDENT":
        print(f"incident : {execution['incident']} — {execution['fait']}")
    return 0


SCHEMA_RECU_QUALIFICATION = "campagne-v1-qualification-harnais/v1"
CHEMIN_RECU_QUALIFICATION = (
    _RACINE_CAMPAGNE_V1 / "qualification-harnais-v1" / "recu-qualification.json"
)
COMMANDE_QUALIFICATION = "uv run tools/campagne_v1.py qualifier"
# Suite standard du dépôt, rejouée telle quelle dans un sous-processus enraciné
# à la racine fournie ; la commande consignée au reçu est exactement celle-ci
ARGV_SUITE_QUALIFICATION = (
    "uv",
    "run",
    "--python",
    "3.12",
    "python",
    "-m",
    "unittest",
    "tests.test_validateur_pre_cadrage_v0",
)
COMMANDE_SUITE_QUALIFICATION = " ".join(ARGV_SUITE_QUALIFICATION)
CHEMIN_SUITE_QUALIFICATION = "tests/test_validateur_pre_cadrage_v0.py"
DELAI_SUITE_QUALIFICATION = 600
CHEMIN_VALIDATEUR = "tools/validateur_pre_cadrage_v0.py"
CHEMIN_TEMOINS = "tasks/dev/pre-cadrage-entretien-client/temoins-qualification.md"
# Pin exact : série mineure CPython 3.12, appliquée par l'en-tête PEP 723
# '>=3.12,<3.13' que l'invocation publique uv run lit ; jamais affaibli
PIN_INTERPRETEUR = "CPython 3.12"
# Empreinte du manifeste approuvée par Ayo (verdict APPROUVE), déjà versionnée
# dans docs/PRD.md, docs/ARD.md et tests/test_validateur_pre_cadrage_v0.py
EMPREINTE_MANIFESTE_APPROUVEE = (
    "8030128d159e4203483b19f0e37692a53f01baecc38fbccaa321541c23e71a10"
)
# Empreinte de la source approuvée des seize témoins, entrée figée du contrat
EMPREINTE_TEMOINS_APPROUVEE = (
    "8a419c5950127c8187119545237f32b0ecb9b0062116afc3421e0c96a00bd011"
)
# Empreinte du validateur consignée par le reçu V0 M8.1 (p3_instrument_sha256)
EMPREINTE_VALIDATEUR_APPROUVEE = (
    "e631184b84270c4b3dbf931910436ad65b7d08c02016c94d2dfe53e27ead2056"
)
# Entrées figées de la V1, jamais rejouées : aucune comparaison d'outillage
DECISIONS_FIGEES_V1 = {
    "route_evaluation_v0": "USE_MANUAL",
    "plateforme_specifique": "STOP_SPECIFIC_PLATFORM",
}

# Les seize témoins approuvés du paquet, dans l'ordre du document versionné.
# Les verdicts attendus vivent dans la suite immuable rejouée par qualifier,
# jamais dans une table dupliquée ici
NOMS_TEMOINS = (
    "WT-ACCEPTABLE",
    "WT-SCHEMA",
    "WT-ANCRE",
    "WT-VOCABULAIRE",
    "WT-HARNESS",
    "WT-FAIT-INVENTE",
    "WT-CONTRAINTE-OMISE",
    "WT-INCONNUE-RESOLUE",
    "WT-HYPOTHESE-INTERDITE",
    "WT-CONTRADICTION-MANQUEE",
    "WT-RISQUE-INADEQUAT",
    "WT-QUESTION-INADEQUATE",
    "WT-ACTION-INADEQUATE",
    "WT-CONFORMITE-AFFIRMEE",
    "WT-RECONSTRUCTION",
    "WT-HUMAIN-INDISPONIBLE",
)
CARDINALITE_TEMOINS = len(NOMS_TEMOINS)

# Index de diagnostic seulement : chaque texte reprend le point d'application du
# delta exact déclaré par temoins-qualification.md et doit apparaître exactement
# une fois dans la sortie canonique WT-ACCEPTABLE ; une divergence d'empreinte
# de la source est attribuée au premier témoin dont le delta ne s'applique plus
# (WT-RECONSTRUCTION partage le point d'application de WT-ACTION-INADEQUATE)
_DELTAS_DIAGNOSTIC = (
    ("WT-SCHEMA", "client_ready: false"),
    ("WT-ANCRE", "[sources: N-B]"),
    ("WT-VOCABULAIRE", "qualification: QUALIFIABLE"),
    ("WT-FAIT-INVENTE", "# Contraintes critiques"),
    (
        "WT-CONTRAINTE-OMISE",
        "- Aucun accès ni connecteur de production pendant le pré-cadrage. "
        "[sources: N-F]\n",
    ),
    (
        "WT-INCONNUE-RESOLUE",
        "- Règles approuvées d'hébergement, de conservation et d'outillage. "
        "[sources: N-F]",
    ),
    ("WT-HYPOTHESE-INTERDITE", "# Contradictions à arbitrer"),
    (
        "WT-CONTRADICTION-MANQUEE",
        "- L'affirmation de libre réutilisation de tous les contenus contredit "
        "l'existence possible de limites contractuelles. Arbitrage humain "
        "requis ; les droits restent inconnus. [sources: N-D, N-H]\n",
    ),
    (
        "WT-RISQUE-INADEQUAT",
        "- Accès de production trop large ou accordé avant arbitrage. "
        "[sources: N-D, N-E, N-F, N-G]",
    ),
    (
        "WT-QUESTION-INADEQUATE",
        "- Quelles données chaque source contient-elle, où résident-elles et "
        "qui en autorise l'usage ? [sources: N-C, N-E, N-G, N-H]",
    ),
    (
        "WT-ACTION-INADEQUATE",
        "Faire relire ce pré-cadrage par Camille Rive avant l'entretien, sans "
        "envoi au client ni action externe. [sources: N-A, N-L]",
    ),
    (
        "WT-CONFORMITE-AFFIRMEE",
        "Ce document n'est ni un conseil au client, ni une architecture de "
        "production, ni un verdict de conformité. [sources: N-A, N-B, N-I, N-J]",
    ),
)


def _interpreteur_observe() -> str:
    return f"{platform.python_implementation()} {platform.python_version()}"


def _interpreteur_compatible() -> bool:
    """Pin exact : CPython, série mineure 3.12, jamais affaibli"""
    version = platform.python_version_tuple()
    return (
        platform.python_implementation() == "CPython"
        and (int(version[0]), int(version[1])) == (3, 12)
    )


def _diagnostiquer_temoin_altere(texte: str) -> str | None:
    """Nomme le premier témoin dont le delta exact ne s'applique plus.

    Diagnostic seulement, après une divergence d'empreinte déjà établie : si le
    bloc canonique reste extractible, le témoin au delta cassé est nommé ;
    sinon la source elle-même est en cause et None est rendu.
    """
    if texte.count("```markdown\n") != 1:
        return None
    bloc = texte.split("```markdown\n", 1)[1].split("\n```", 1)[0] + "\n"
    for nom, attendu in _DELTAS_DIAGNOSTIC:
        if bloc.count(attendu) != 1:
            return nom
    return None


def _refus_qualification(fait: str) -> int:
    """Refus fail-closed du dispositif : HARNESS_ERROR nommé, jamais FAIL"""
    print(f"ECHEC {fait}")
    print("verdict : HARNESS_ERROR")
    return 1


def qualifier_harnais(racine: Path) -> int:
    observe = _interpreteur_observe()
    if not _interpreteur_compatible():
        # F-08 : un défaut du dispositif n'est jamais un échec candidat
        return _refus_qualification(
            f"incompatibilité d'interpréteur : pin '{PIN_INTERPRETEUR}', "
            f"observé '{observe}' ; le pin n'est pas affaibli"
        )
    # Source approuvée des seize témoins, vérifiée avant tout appel de suite
    chemin_temoins = racine / CHEMIN_TEMOINS
    if not chemin_temoins.is_file():
        return _refus_qualification(
            f"source des témoins approuvés absente : {CHEMIN_TEMOINS}"
        )
    sha_temoins = _sha256_fichier(chemin_temoins)
    if sha_temoins != EMPREINTE_TEMOINS_APPROUVEE:
        try:
            texte = chemin_temoins.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            texte = ""
        temoin = _diagnostiquer_temoin_altere(texte)
        if temoin is not None:
            return _refus_qualification(
                f"témoin '{temoin}' altéré : son delta exact ne s'applique "
                f"plus à la sortie canonique de {CHEMIN_TEMOINS}"
            )
        return _refus_qualification(
            f"source des témoins approuvés divergente : {CHEMIN_TEMOINS} "
            f"attendu {EMPREINTE_TEMOINS_APPROUVEE}, observé {sha_temoins}"
        )
    # Manifeste approuvé puis chaque fichier du paquet qu'il dénombre
    chemin_manifeste = racine / CHEMIN_PAQUET
    if not chemin_manifeste.is_file():
        return _refus_qualification(
            f"manifeste du paquet approuvé absent : {CHEMIN_PAQUET}"
        )
    if _sha256_fichier(chemin_manifeste) != EMPREINTE_MANIFESTE_APPROUVEE:
        return _refus_qualification(
            f"manifeste du paquet divergent de l'empreinte approuvée : "
            f"{CHEMIN_PAQUET}"
        )
    try:
        manifeste = json.loads(chemin_manifeste.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        return _refus_qualification(
            f"manifeste du paquet illisible : {CHEMIN_PAQUET} ({erreur})"
        )
    racine_paquet = Path(CHEMIN_PAQUET).parent
    for entree in manifeste.get("fichiers", []):
        relatif = (racine_paquet / entree["chemin"]).as_posix()
        chemin_fichier = racine / relatif
        if not chemin_fichier.is_file():
            return _refus_qualification(
                f"fichier du paquet approuvé absent : {relatif}"
            )
        if _sha256_fichier(chemin_fichier) != entree["sha256"]:
            return _refus_qualification(
                f"fichier du paquet approuvé divergent : {relatif}"
            )
    # Validateur résolu et haché depuis la racine fournie, jamais depuis le
    # dépôt de l'implémenteur
    chemin_validateur = racine / CHEMIN_VALIDATEUR
    if not chemin_validateur.is_file():
        return _refus_qualification(
            f"validateur absent de la racine : {CHEMIN_VALIDATEUR}"
        )
    sha_validateur = _sha256_fichier(chemin_validateur)
    if sha_validateur != EMPREINTE_VALIDATEUR_APPROUVEE:
        return _refus_qualification(
            f"validateur divergent de l'empreinte qualifiée : "
            f"{CHEMIN_VALIDATEUR} attendu {EMPREINTE_VALIDATEUR_APPROUVEE}, "
            f"observé {sha_validateur}"
        )
    chemin_suite = racine / CHEMIN_SUITE_QUALIFICATION
    if not chemin_suite.is_file():
        return _refus_qualification(
            f"suite de qualification absente : {CHEMIN_SUITE_QUALIFICATION}"
        )
    # Invocation standard de la suite immuable, enracinée à la racine fournie
    execution = _executer_borne(
        list(ARGV_SUITE_QUALIFICATION), b"", racine, DELAI_SUITE_QUALIFICATION
    )
    if execution["etat"] == "INCIDENT":
        return _refus_qualification(
            f"lancement de la suite de qualification impossible : "
            f"{execution['fait']}"
        )
    if execution["code_sortie"] != 0:
        lignes_erreur = execution["sortie"]["stderr"].strip().splitlines()
        queue = (
            " | ".join(lignes_erreur[-3:])
            if lignes_erreur
            else "aucune sortie d'erreur"
        )
        return _refus_qualification(
            f"suite de qualification en échec : {CHEMIN_SUITE_QUALIFICATION} "
            f"code {execution['code_sortie']} ({queue})"
        )
    date_qualification = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    recu = {
        "schema_version": SCHEMA_RECU_QUALIFICATION,
        "date_qualification": date_qualification,
        "verdict": "PASS",
        "commande_publique": COMMANDE_QUALIFICATION,
        "commande_suite": COMMANDE_SUITE_QUALIFICATION,
        "interpreteur": {"pin": PIN_INTERPRETEUR, "observe": observe},
        "validateur": {"chemin": CHEMIN_VALIDATEUR, "sha256": sha_validateur},
        "temoins": {
            "source": CHEMIN_TEMOINS,
            "sha256": sha_temoins,
            "cardinalite": CARDINALITE_TEMOINS,
            "noms": list(NOMS_TEMOINS),
        },
        "decisions_figees": dict(DECISIONS_FIGEES_V1),
    }
    destination = racine / CHEMIN_RECU_QUALIFICATION
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(recu, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"qualification du harnais V1 : suite '{COMMANDE_SUITE_QUALIFICATION}' "
        f"rejouée sur les {CARDINALITE_TEMOINS} témoins approuvés"
    )
    print(f"interpréteur : pin '{PIN_INTERPRETEUR}', observé '{observe}'")
    print("verdict : PASS")
    print(f"reçu écrit : {CHEMIN_RECU_QUALIFICATION.as_posix()}")
    return 0


SCHEMA_REGISTRE_VALIDATION = "campagne-v1-registre-validation/v1"
CHEMIN_REGISTRE_VALIDATION = (
    _RACINE_CAMPAGNE_V1
    / "validation-automatique-v1"
    / "registre-couverture-verdicts.json"
)
# Contrôles mécaniques exacts du paquet approuvé, sans ajout ni retrait
PORTES_PAQUET = ("G-001", "G-002", "G-003", "G-004", "G-005")
VERDICTS_CANDIDATS = ("PASS", "FAIL", "HARNESS_ERROR")
ORIGINES_ECHEC = ("CANDIDATE_ERROR", "HARNESS_ERROR")
ETATS_SORTIE_CANDIDATE = ("PRESENTE", "ABSENTE")
SECTION_REGISTRE_VALIDATION = "registre de couverture et de verdicts V1 versionné"


def _refus_validation(fait: str) -> int:
    """Refus fail-closed du dispositif de validation, fait fautif nommé."""
    print(f"ECHEC {fait}")
    return 1


def _charger_module_validateur(chemin: Path) -> object:
    """Charge le validateur qualifié depuis le fichier haché, jamais depuis
    le dépôt de l'implémenteur."""
    spec = importlib.util.spec_from_file_location(
        "validateur_pre_cadrage_v0_qualifie", chemin
    )
    if spec is None or spec.loader is None:
        raise ErreurRestitution(f"validateur non chargeable : {chemin}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def valider(racine: Path) -> int:
    """Applique G-001 à G-005 aux sorties candidates des reçus officiels V1.

    Seule une sortie candidate reçoit un verdict ; une acquisition sans
    sortie conserve la cause de son reçu, inchangée. Les reçus locaux de
    démonstration restent hors panel officiel et hors validation officielle.
    """
    # F-08 : une incompatibilité d'interpréteur n'est jamais un échec candidat
    if not _interpreteur_compatible():
        return _refus_validation(
            f"incompatibilité d'interpréteur : pin '{PIN_INTERPRETEUR}', "
            f"observé '{_interpreteur_observe()}' ; le pin n'est pas affaibli"
        )
    # Paquet approuvé byte-identique, vérifié avant toute validation
    chemin_manifeste = racine / CHEMIN_PAQUET
    if not chemin_manifeste.is_file():
        return _refus_validation(
            f"manifeste du paquet approuvé absent : {CHEMIN_PAQUET}"
        )
    sha_manifeste = _sha256_fichier(chemin_manifeste)
    if sha_manifeste != EMPREINTE_MANIFESTE_APPROUVEE:
        return _refus_validation(
            f"manifeste du paquet divergent de l'empreinte approuvée : "
            f"{CHEMIN_PAQUET} attendu {EMPREINTE_MANIFESTE_APPROUVEE}, "
            f"observé {sha_manifeste}"
        )
    # Validateur qualifié byte-identique, chargé depuis le fichier haché
    chemin_validateur = racine / CHEMIN_VALIDATEUR
    if not chemin_validateur.is_file():
        return _refus_validation(
            f"validateur absent de la racine : {CHEMIN_VALIDATEUR}"
        )
    sha_validateur = _sha256_fichier(chemin_validateur)
    if sha_validateur != EMPREINTE_VALIDATEUR_APPROUVEE:
        return _refus_validation(
            f"validateur divergent de l'empreinte qualifiée : "
            f"{CHEMIN_VALIDATEUR} attendu {EMPREINTE_VALIDATEUR_APPROUVEE}, "
            f"observé {sha_validateur}"
        )
    try:
        module_validateur = _charger_module_validateur(chemin_validateur)
    except ErreurRestitution as erreur:
        return _refus_validation(str(erreur))
    try:
        etat = _charger_etat(racine)
        _, recus_officiels = _partitionner_recus(racine, etat)
    except ErreurRestitution as erreur:
        return _refus_validation(f"reçus V1 illisibles : {erreur}")
    paquet = module_validateur.PaquetApprouveV0(
        manifeste=chemin_manifeste,
        empreinte_manifeste_approuvee=EMPREINTE_MANIFESTE_APPROUVEE,
        approbateur="Ayo",
        verdict_approbation="APPROUVE",
    )
    entrees: list[dict] = []
    for relatif, enveloppe, sha_recu in recus_officiels:
        charge = enveloppe["payload"]
        execution = charge["execution"]
        entree = {
            "recu": relatif,
            "recu_sha256": sha_recu,
            "configuration_id": charge["configuration"]["identifiant"],
            "creneau": charge["creneau"],
        }
        if execution["etat"] != "OBSERVED":
            # Aucune sortie candidate : aucun verdict candidat, cause du reçu
            # conservée à l'identique, jamais convertie
            entrees.append(
                {
                    **entree,
                    "sortie_candidate": "ABSENTE",
                    "cause_recue": execution["incident"],
                    "verdict": None,
                }
            )
            continue
        with tempfile.TemporaryDirectory() as dossier:
            sortie = Path(dossier) / "sortie-candidate.md"
            sortie.write_text(execution["sortie"]["stdout"], encoding="utf-8")
            # Empreinte des octets UTF-8 exacts du reçu, calculée avant
            # l'appel : elle reste disponible si le validateur signale une
            # erreur de lecture du harnais avant de renseigner la sienne
            empreinte_recue = hashlib.sha256(
                execution["sortie"]["stdout"].encode("utf-8")
            ).hexdigest()
            resultat = module_validateur.valider_pre_cadrage_v0(paquet, sortie)
        porte_en_cause = next(
            (nom for nom, franchie in resultat.gates if not franchie), None
        )
        if porte_en_cause is None and resultat.statut == "HARNESS_ERROR":
            # Défaillance du dispositif entre G-005 et G-001 (lecture de la
            # sortie) : la porte en cause est la dernière porte de harnais
            # évaluée, G-005 ; jamais attribuée à une porte candidate
            porte_en_cause = resultat.gates[-1][0] if resultat.gates else None
        entrees.append(
            {
                **entree,
                "sortie_candidate": "PRESENTE",
                "cause_recue": None,
                "verdict": {
                    "statut": resultat.statut,
                    "origine": resultat.origine,
                    "porte_en_cause": porte_en_cause,
                    "portes": [
                        [nom, franchie] for nom, franchie in resultat.gates
                    ],
                    "empreinte_candidate": (
                        resultat.preuve["empreinte_candidate"]
                        if resultat.preuve["empreinte_candidate"] is not None
                        else empreinte_recue
                    ),
                },
            }
        )
    comptes = {verdict: 0 for verdict in VERDICTS_CANDIDATS}
    for entree in entrees:
        if entree["verdict"] is not None:
            comptes[entree["verdict"]["statut"]] += 1
    registre = {
        "schema_version": SCHEMA_REGISTRE_VALIDATION,
        "interpreteur": {
            "pin": PIN_INTERPRETEUR,
            "observe": _interpreteur_observe(),
        },
        "paquet": {"chemin": CHEMIN_PAQUET, "sha256": sha_manifeste},
        "validateur": {"chemin": CHEMIN_VALIDATEUR, "sha256": sha_validateur},
        "portes": list(PORTES_PAQUET),
        "entrees": entrees,
        "couverture": {
            "acquisitions_officielles": len(entrees),
            "sorties_candidates": sum(comptes.values()),
            "verdicts": comptes,
        },
    }
    destination = racine / CHEMIN_REGISTRE_VALIDATION
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(registre, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for entree in entrees:
        verdict = entree["verdict"]
        if verdict is None:
            print(
                f"{entree['configuration_id']} : aucune sortie candidate, "
                f"aucun verdict candidat ; cause du reçu conservée "
                f"{entree['cause_recue']}"
            )
        elif verdict["statut"] == "PASS":
            print(f"{entree['configuration_id']} : verdict PASS")
        else:
            print(
                f"{entree['configuration_id']} : verdict "
                f"{verdict['statut']} — porte en cause "
                f"{verdict['porte_en_cause']} · origine {verdict['origine']}"
            )
    print(
        f"couverture : {len(entrees)} acquisition(s) officielle(s), "
        f"{sum(comptes.values())} sortie(s) candidate(s)"
    )
    print(f"registre écrit : {CHEMIN_REGISTRE_VALIDATION.as_posix()}")
    return 0


def _charger_registre_validation(
    racine: Path,
) -> tuple[str, dict, str] | None:
    """Registre de validation validé : (chemin relatif, registre, SHA-256 du
    fichier), ou None lorsque l'artefact n'existe pas."""
    chemin = racine / CHEMIN_REGISTRE_VALIDATION
    if not chemin.is_file():
        return None
    try:
        registre = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurRestitution(
            f"registre de validation illisible : {chemin} ({erreur})"
        ) from erreur
    if (
        not isinstance(registre, dict)
        or registre.get("schema_version") != SCHEMA_REGISTRE_VALIDATION
    ):
        raise ErreurRestitution(
            f"schéma de registre de validation inattendu : {chemin}"
        )
    if registre.get("portes") != list(PORTES_PAQUET):
        raise ErreurRestitution(
            f"champ 'portes' : exactement {list(PORTES_PAQUET)} attendu, "
            "sans ajout ni retrait"
        )
    paquet = registre.get("paquet")
    if not isinstance(paquet, dict) or paquet.get("chemin") != CHEMIN_PAQUET:
        raise ErreurRestitution(f"champ 'paquet.chemin' : '{CHEMIN_PAQUET}' attendu")
    if paquet.get("sha256") != EMPREINTE_MANIFESTE_APPROUVEE:
        raise ErreurRestitution(
            "champ 'paquet.sha256' : empreinte approuvée "
            f"{EMPREINTE_MANIFESTE_APPROUVEE} attendue"
        )
    validateur = registre.get("validateur")
    if (
        not isinstance(validateur, dict)
        or validateur.get("chemin") != CHEMIN_VALIDATEUR
    ):
        raise ErreurRestitution(
            f"champ 'validateur.chemin' : '{CHEMIN_VALIDATEUR}' attendu"
        )
    if validateur.get("sha256") != EMPREINTE_VALIDATEUR_APPROUVEE:
        raise ErreurRestitution(
            "champ 'validateur.sha256' : empreinte qualifiée "
            f"{EMPREINTE_VALIDATEUR_APPROUVEE} attendue"
        )
    entrees = registre.get("entrees")
    if not isinstance(entrees, list):
        raise ErreurRestitution("champ 'entrees' : liste attendue")
    for entree in entrees:
        _valider_entree_registre_validation(entree)
    couverture = registre.get("couverture")
    if not isinstance(couverture, dict) or set(couverture) != {
        "acquisitions_officielles",
        "sorties_candidates",
        "verdicts",
    }:
        raise ErreurRestitution(
            "champ 'couverture' : clés exactes acquisitions_officielles, "
            "sorties_candidates et verdicts attendues"
        )
    if couverture["acquisitions_officielles"] != len(entrees):
        raise ErreurRestitution(
            "champ 'couverture.acquisitions_officielles' : divergent du "
            "nombre d'entrées"
        )
    comptes = couverture["verdicts"]
    if not isinstance(comptes, dict) or set(comptes) != set(VERDICTS_CANDIDATS):
        raise ErreurRestitution(
            f"champ 'couverture.verdicts' : clés exactes "
            f"{sorted(VERDICTS_CANDIDATS)} attendues"
        )
    recompte = {verdict: 0 for verdict in VERDICTS_CANDIDATS}
    for entree in entrees:
        if entree["verdict"] is not None:
            recompte[entree["verdict"]["statut"]] += 1
    if comptes != recompte:
        raise ErreurRestitution(
            "champ 'couverture.verdicts' : divergent du recompte des entrées"
        )
    if couverture["sorties_candidates"] != sum(recompte.values()):
        raise ErreurRestitution(
            "champ 'couverture.sorties_candidates' : divergent du recompte"
        )
    return (
        CHEMIN_REGISTRE_VALIDATION.as_posix(),
        registre,
        _sha256_fichier(chemin),
    )


def _valider_entree_registre_validation(entree: object) -> None:
    if not isinstance(entree, dict) or set(entree) != {
        "recu",
        "recu_sha256",
        "configuration_id",
        "creneau",
        "sortie_candidate",
        "cause_recue",
        "verdict",
    }:
        raise ErreurRestitution(
            "entrée de registre de validation : clés exactes recu, "
            "recu_sha256, configuration_id, creneau, sortie_candidate, "
            "cause_recue et verdict attendues"
        )
    if not isinstance(entree["recu"], str) or not entree["recu"]:
        raise ErreurRestitution("entrée : champ 'recu' chaîne non vide attendu")
    if (
        not isinstance(entree["recu_sha256"], str)
        or not _MOTIF_SHA256.match(entree["recu_sha256"])
    ):
        raise ErreurRestitution(
            "entrée : champ 'recu_sha256' SHA-256 hexadécimal attendu"
        )
    if not isinstance(entree["configuration_id"], str) or not _MOTIF_SLUG.match(
        entree["configuration_id"]
    ):
        raise ErreurRestitution(
            "entrée : champ 'configuration_id' slug stable attendu"
        )
    if not isinstance(entree["creneau"], str) or not entree["creneau"]:
        raise ErreurRestitution("entrée : champ 'creneau' chaîne non vide attendu")
    if entree["sortie_candidate"] not in ETATS_SORTIE_CANDIDATE:
        raise ErreurRestitution(
            f"entrée : champ 'sortie_candidate' hors vocabulaire "
            f"({' | '.join(ETATS_SORTIE_CANDIDATE)})"
        )
    verdict = entree["verdict"]
    if entree["sortie_candidate"] == "ABSENTE":
        # Aucun verdict candidat sans sortie ; la cause du reçu est conservée
        # inchangée, dans le vocabulaire d'incident du profil abonnement
        if verdict is not None:
            raise ErreurRestitution(
                f"entrée '{entree['configuration_id']}' : verdict candidat "
                "attribué à une acquisition sans sortie candidate"
            )
        if entree["cause_recue"] not in INCIDENTS_V1:
            raise ErreurRestitution(
                f"entrée '{entree['configuration_id']}' : cause du reçu hors "
                f"vocabulaire ({' | '.join(INCIDENTS_V1)})"
            )
        return
    if entree["cause_recue"] is not None:
        raise ErreurRestitution(
            f"entrée '{entree['configuration_id']}' : cause de reçu présente "
            "sur une sortie candidate"
        )
    if not isinstance(verdict, dict) or set(verdict) != {
        "statut",
        "origine",
        "porte_en_cause",
        "portes",
        "empreinte_candidate",
    }:
        raise ErreurRestitution(
            f"entrée '{entree['configuration_id']}' : verdict avec clés "
            "exactes statut, origine, porte_en_cause, portes et "
            "empreinte_candidate attendu"
        )
    if verdict["statut"] not in VERDICTS_CANDIDATS:
        raise ErreurRestitution(
            f"entrée '{entree['configuration_id']}' : statut hors vocabulaire "
            f"({' | '.join(VERDICTS_CANDIDATS)})"
        )
    if verdict["statut"] == "PASS":
        if verdict["origine"] is not None or verdict["porte_en_cause"] is not None:
            raise ErreurRestitution(
                f"entrée '{entree['configuration_id']}' : PASS sans origine "
                "ni porte en cause attendu"
            )
    else:
        if verdict["origine"] not in ORIGINES_ECHEC:
            raise ErreurRestitution(
                f"entrée '{entree['configuration_id']}' : origine hors "
                f"vocabulaire ({' | '.join(ORIGINES_ECHEC)})"
            )
        if verdict["porte_en_cause"] not in PORTES_PAQUET:
            raise ErreurRestitution(
                f"entrée '{entree['configuration_id']}' : porte en cause "
                f"hors vocabulaire ({' | '.join(PORTES_PAQUET)})"
            )
        # HARNESS_ERROR n'existe que lorsque la preuve désigne le harnais
        if verdict["statut"] == "HARNESS_ERROR" and verdict["origine"] != (
            "HARNESS_ERROR"
        ):
            raise ErreurRestitution(
                f"entrée '{entree['configuration_id']}' : HARNESS_ERROR sans "
                "origine HARNESS_ERROR"
            )
    portes = verdict["portes"]
    if (
        not isinstance(portes, list)
        or not portes
        or any(
            not isinstance(porte, list)
            or len(porte) != 2
            or porte[0] not in PORTES_PAQUET
            or not isinstance(porte[1], bool)
            for porte in portes
        )
    ):
        raise ErreurRestitution(
            f"entrée '{entree['configuration_id']}' : portes [[porte, booléen]] "
            "attendues"
        )
    if not isinstance(verdict["empreinte_candidate"], str) or not (
        _MOTIF_SHA256.match(verdict["empreinte_candidate"])
    ):
        raise ErreurRestitution(
            f"entrée '{entree['configuration_id']}' : empreinte_candidate "
            "SHA-256 hexadécimal attendu"
        )


def _article_validation(
    entree: dict, relatif_registre: str, sha_registre: str
) -> str:
    """Article régénérable à l'identique depuis une entrée du registre."""
    lignes_communes = (
        f"<p><strong>{_echapper(entree['configuration_id'])}</strong> — "
        f"reçu <code>{_echapper(entree['recu'])}</code> · SHA-256 du fichier "
        f"<code>{entree['recu_sha256']}</code></p>"
        f"<p>créneau <code>{_echapper(entree['creneau'])}</code></p>"
    )
    verdict = entree["verdict"]
    if verdict is None:
        contenu = (
            lignes_communes
            + "<p>aucune sortie candidate : <strong>aucun verdict candidat</strong> "
            "n'est attribué ; la cause du reçu d'acquisition est conservée "
            f"inchangée : <code>{_echapper(entree['cause_recue'])}</code>.</p>"
            + _span_source(
                relatif_registre, sha_registre, SECTION_REGISTRE_VALIDATION
            )
            + _span_source(
                entree["recu"], entree["recu_sha256"], SECTION_RECU_OFFICIEL
            )
        )
    else:
        detail_portes = " · ".join(
            f"<code>{_echapper(nom)}</code> "
            + ("franchie" if franchie else "en échec")
            for nom, franchie in verdict["portes"]
        )
        if verdict["statut"] == "PASS":
            lignes_verdict = (
                f"<p>verdict <code>PASS</code> — les portes "
                f"<code>G-001</code> à <code>G-005</code> sont franchies, "
                "sans porte en cause ni origine d'échec.</p>"
            )
        else:
            lignes_verdict = (
                f"<p>verdict <code>{_echapper(verdict['statut'])}</code> — "
                f"porte en cause <code>{_echapper(verdict['porte_en_cause'])}"
                f"</code> · origine <code>{_echapper(verdict['origine'])}</code></p>"
            )
        contenu = (
            lignes_communes
            + lignes_verdict
            + f"<p>portes évaluées : {detail_portes}</p>"
            f"<p>empreinte de la sortie candidate "
            f"<code>{verdict['empreinte_candidate']}</code></p>"
            + _span_source(
                relatif_registre, sha_registre, SECTION_REGISTRE_VALIDATION
            )
            + _span_source(
                entree["recu"], entree["recu_sha256"], SECTION_RECU_OFFICIEL
            )
        )
    return _article(
        "fait",
        contenu,
        f' data-validation="{entree["configuration_id"]}"',
    )


def _article_couverture_validation(
    relatif: str, sha_fichier: str, registre: dict
) -> str:
    """Article de couverture régénérable à l'identique depuis le registre."""
    couverture = registre["couverture"]
    comptes = couverture["verdicts"]
    contenu = (
        "<p><strong>Couverture et verdicts</strong> — la validation applique "
        "exclusivement les contrôles mécaniques <code>G-001</code> à "
        "<code>G-005</code> du paquet approuvé, au moyen du validateur "
        "qualifié, sans modification du paquet et sans contrôle sémantique. "
        "Seule une sortie candidate reçoit un verdict ; une acquisition sans "
        "sortie candidate conserve la cause de son reçu, inchangée. Le reçu "
        "local de démonstration reste hors panel officiel et hors validation "
        "officielle.</p>"
        f"<p>acquisitions officielles : "
        f"<code>{couverture['acquisitions_officielles']}</code> · sorties "
        f"candidates : <code>{couverture['sorties_candidates']}</code></p>"
        f"<p>verdicts : <code>PASS</code> {comptes['PASS']} · "
        f"<code>FAIL</code> {comptes['FAIL']} · <code>HARNESS_ERROR</code> "
        f"{comptes['HARNESS_ERROR']}</p>"
        f"<p>paquet <code>{_echapper(registre['paquet']['chemin'])}</code> · "
        f"SHA-256 <code>{registre['paquet']['sha256']}</code></p>"
        f"<p>validateur <code>{_echapper(registre['validateur']['chemin'])}"
        f"</code> · SHA-256 <code>{registre['validateur']['sha256']}</code></p>"
        f"<p>interpréteur : pin "
        f"<code>{_echapper(registre['interpreteur']['pin'])}</code> · observé "
        f"<code>{_echapper(registre['interpreteur']['observe'])}</code></p>"
        + _span_source(relatif, sha_fichier, SECTION_REGISTRE_VALIDATION)
    )
    return _article("fait", contenu, ' data-registre-validation="couverture"')


SCHEMA_RECU_PREFLIGHT = "campagne-v1-preflight/v1"
REPERTOIRE_PREFLIGHTS = _RACINE_CAMPAGNE_V1 / "preflights-v1"
# Autorité groupée unique des préflights XS-06A à XS-06F, référencée une seule
# fois par reçu ; aucun GO distinct par modèle (RG-03)
AUTORITE_PREFLIGHT = "D-V1-03"
ADAPTATEUR_CLAUDE = "claude"
# Délai propre au préflight : le delai_secondes du TOML borne le harnais
# génératif, jamais une sonde non générative
DELAI_SONDE_PREFLIGHT = 120
# Le code de sortie suit le verdict, à l'identique dans XS-06A à XS-06F
CODES_SORTIE_PREFLIGHT = {"READY": 0, "UNAVAILABLE": 1, "HOLD": 2}
CAUSES_PREFLIGHT_HOLD = ("HARNESS_ERROR", "IDENTITY_MISMATCH", "MISSING_OBSERVATION")
CAUSES_PREFLIGHT_UNAVAILABLE = (
    "INTERFACE_UNAVAILABLE",
    "AUTHENTICATION_UNAVAILABLE",
    "MODEL_UNAVAILABLE",
    "PLAN_UNAVAILABLE",
    "PROVIDER_FAILURE",
    "QUOTA_EXHAUSTED",
)
# D-V1-01 : effort high quand exposé ; l'exposition reste à observer
EFFORT_DEMANDE_CLAUDE = "high"
# Sondes non génératives : jamais de -p, --print, --model, prompt positionnel,
# session interactive, --continue, --resume, --fork-session ni
# --dangerously-skip-permissions ; la liste blanche est exacte et fermée
SONDE_VERSION_CLAUDE = ("claude", "--version")
SONDE_AUTH_CLAUDE = ("claude", "auth", "status", "--json")
SONDES_AUTORISEES_PREFLIGHT = (SONDE_VERSION_CLAUDE, SONDE_AUTH_CLAUDE)
# Projection déterministe du statut d'authentification : seuls ces quatre
# champs sortent de la mémoire locale ; email, orgId et orgName ne sont
# jamais lus, affichés, écrits ni conservés, la sortie brute non plus
CHAMPS_PROJECTION_AUTH = ("loggedIn", "authMethod", "apiProvider", "subscriptionType")

ADAPTATEUR_CODEX = "codex"
# D-V1-01 : politique d'effort ferme de la configuration codex-gpt-5-6-sol
EFFORT_DEMANDE_CODEX = "high"
# Sondes non génératives Codex : jamais de exec, review, apply, resume,
# fork, prompt positionnel ni session interactive ; liste exacte et fermée
SONDE_VERSION_CODEX = ("codex", "--version")
SONDE_LOGIN_CODEX = ("codex", "login", "status")
SONDE_CATALOGUE_CODEX = ("codex", "debug", "models")
SONDES_AUTORISEES_PREFLIGHT_CODEX = (
    SONDE_VERSION_CODEX,
    SONDE_LOGIN_CODEX,
    SONDE_CATALOGUE_CODEX,
)
# Lignes de statut reconnues de 'codex login status', liste fermée : la
# sortie brute n'est jamais consignée, seule la méthode projetée sort
LIGNES_LOGIN_CODEX = {
    "Logged in using ChatGPT": "ChatGPT",
    "Logged in using an API key": "API key",
}
LIGNE_DECONNECTE_CODEX = "Not logged in"
CHAMPS_PROJECTION_LOGIN_CODEX = ("connecte", "methode")
CHAMPS_PROJECTION_CATALOGUE_CODEX = ("modele_demande_present", "efforts_annonces")


def _projeter_login_codex(stdout: str, stderr: str) -> dict | None:
    """Projection en mémoire du statut de connexion, jamais la sortie brute.

    Le client réel écrit son statut sur stderr : les deux flux sont lus.
    Seule une ligne de la liste fermée est reconnue ; toute autre forme rend
    None et le préflight reste fail-closed sans inventer de fait.
    """
    lignes = [
        ligne.strip()
        for ligne in (stdout.splitlines() + stderr.splitlines())
        if ligne.strip()
    ]
    connectees = [
        LIGNES_LOGIN_CODEX[ligne] for ligne in lignes if ligne in LIGNES_LOGIN_CODEX
    ]
    deconnectees = [
        ligne for ligne in lignes if ligne.startswith(LIGNE_DECONNECTE_CODEX)
    ]
    if len(connectees) == 1 and not deconnectees:
        return {"connecte": True, "methode": connectees[0]}
    if deconnectees and not connectees:
        return {"connecte": False, "methode": INCONNU}
    return None


def _projeter_catalogue_codex(
    stdout: str, stderr: str, modele_demande: str
) -> dict | None:
    """Projection du catalogue : présence du modèle demandé et efforts annoncés.

    Le catalogue complet, ses autres modèles et tout autre champ servi ne
    sont jamais conservés. None signale un JSON illisible ou une structure
    models absente : le préflight reste fail-closed sans inventer de fait.
    """
    modeles = None
    for flux in (stdout, stderr):
        try:
            donnees = json.loads(flux)
        except json.JSONDecodeError:
            continue
        if isinstance(donnees, dict) and isinstance(donnees.get("models"), list):
            modeles = donnees["models"]
            break
        if isinstance(donnees, list):
            modeles = donnees
            break
    if modeles is None:
        return None
    correspondances = [
        entree
        for entree in modeles
        if isinstance(entree, dict) and entree.get("slug") == modele_demande
    ]
    if not correspondances:
        return {"modele_demande_present": False, "efforts_annonces": []}
    niveaux = correspondances[0].get("supported_reasoning_levels")
    efforts = [
        niveau["effort"]
        for niveau in (niveaux if isinstance(niveaux, list) else [])
        if isinstance(niveau, dict)
        and isinstance(niveau.get("effort"), str)
        and niveau["effort"].strip()
    ]
    return {"modele_demande_present": True, "efforts_annonces": efforts}


def _observer_route_codex(
    modele_demande: str,
) -> tuple[list[dict], str, object, str, str, str, str, str | None, str]:
    """Sonde la route codex sans génération.

    Rend (sondes, version, authentification observée, plan observé, modèle
    exposé, effort exposé, verdict, cause, fait). MSW : version,
    authentification et catalogue sont observables par les trois sondes de
    la liste blanche ; une correspondance de catalogue exacte prouve le
    modèle exposé et les efforts explicitement annoncés, jamais le modèle
    réellement servi ; le plan du compte, le quota et l'identité servie
    restent INCONNU sans commande générative, donc READY n'est jamais
    prouvable dans cette tranche.
    """
    sondes: list[dict] = []
    commande_version = " ".join(SONDE_VERSION_CODEX)
    commande_login = " ".join(SONDE_LOGIN_CODEX)
    commande_catalogue = " ".join(SONDE_CATALOGUE_CODEX)
    if shutil.which(ADAPTATEUR_CODEX) is None:
        return (
            sondes,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "INTERFACE_UNAVAILABLE",
            f"client '{ADAPTATEUR_CODEX}' introuvable sur le PATH local ; "
            "aucune sonde lancée",
        )
    with tempfile.TemporaryDirectory() as espace_texte:
        execution = _executer_borne(
            list(SONDE_VERSION_CODEX),
            b"",
            Path(espace_texte),
            DELAI_SONDE_PREFLIGHT,
        )
    if execution["etat"] == "INCIDENT":
        return (
            sondes,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_version}' : {_expurger(execution['fait'])}",
        )
    sondes.append(
        {
            "commande": commande_version,
            "code_sortie": execution["code_sortie"],
            "stdout_expurge": _expurger(execution["sortie"]["stdout"]),
            "stderr_expurge": _expurger(execution["sortie"]["stderr"]),
        }
    )
    if execution["code_sortie"] != 0:
        return (
            sondes,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "INTERFACE_UNAVAILABLE",
            f"sonde '{commande_version}' en échec : code de sortie "
            f"{execution['code_sortie']}, le client n'est pas utilisable ; "
            "les sondes de connexion et de catalogue ne sont pas lancées",
        )
    texte_version = _expurger(execution["sortie"]["stdout"].strip())
    version = texte_version if texte_version else INCONNU
    with tempfile.TemporaryDirectory() as espace_texte:
        execution_login = _executer_borne(
            list(SONDE_LOGIN_CODEX),
            b"",
            Path(espace_texte),
            DELAI_SONDE_PREFLIGHT,
        )
    if execution_login["etat"] == "INCIDENT":
        return (
            sondes,
            version,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_login}' : {_expurger(execution_login['fait'])}",
        )
    projection_login = _projeter_login_codex(
        execution_login["sortie"]["stdout"], execution_login["sortie"]["stderr"]
    )
    if projection_login is None:
        # La sortie brute d'une sonde de connexion n'est jamais consignée
        sondes.append(
            {
                "commande": commande_login,
                "code_sortie": execution_login["code_sortie"],
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_login}' : statut hors liste fermée reconnue "
            f"(code de sortie {execution_login['code_sortie']}), statut de "
            "connexion inobservé ; la sortie brute n'est pas consignée",
        )
    sondes.append(
        {
            "commande": commande_login,
            "code_sortie": execution_login["code_sortie"],
            "projection": projection_login,
        }
    )
    if not projection_login["connecte"]:
        return (
            sondes,
            version,
            projection_login,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "AUTHENTICATION_UNAVAILABLE",
            "statut observé 'Not logged in' : aucune authentification "
            "active, la route n'est pas utilisable ; la sonde de catalogue "
            "n'est pas lancée",
        )
    with tempfile.TemporaryDirectory() as espace_texte:
        execution_catalogue = _executer_borne(
            list(SONDE_CATALOGUE_CODEX),
            b"",
            Path(espace_texte),
            DELAI_SONDE_PREFLIGHT,
        )
    if execution_catalogue["etat"] == "INCIDENT":
        return (
            sondes,
            version,
            projection_login,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_catalogue}' : "
            f"{_expurger(execution_catalogue['fait'])}",
        )
    if execution_catalogue["code_sortie"] != 0:
        # Le catalogue complet n'est jamais consigné, même en échec
        sondes.append(
            {
                "commande": commande_catalogue,
                "code_sortie": execution_catalogue["code_sortie"],
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            projection_login,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_catalogue}' en échec : code de sortie "
            f"{execution_catalogue['code_sortie']}, catalogue inobservé ; "
            "la sortie brute n'est pas consignée",
        )
    projection_catalogue = _projeter_catalogue_codex(
        execution_catalogue["sortie"]["stdout"],
        execution_catalogue["sortie"]["stderr"],
        modele_demande,
    )
    if projection_catalogue is None:
        sondes.append(
            {
                "commande": commande_catalogue,
                "code_sortie": 0,
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            projection_login,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_catalogue}' : JSON illisible ou structure "
            "models absente, catalogue inobservé ; la sortie brute n'est "
            "pas consignée",
        )
    sondes.append(
        {
            "commande": commande_catalogue,
            "code_sortie": 0,
            "projection": projection_catalogue,
        }
    )
    if not projection_catalogue["modele_demande_present"]:
        return (
            sondes,
            version,
            projection_login,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "MODEL_UNAVAILABLE",
            f"catalogue observé sans correspondance exacte pour "
            f"'{modele_demande}' : le modèle demandé n'est pas exposé par "
            "le client",
        )
    efforts = projection_catalogue["efforts_annonces"]
    if efforts and EFFORT_DEMANDE_CODEX not in efforts:
        return (
            sondes,
            version,
            projection_login,
            INCONNU,
            modele_demande,
            INCONNU,
            "UNAVAILABLE",
            "MODEL_UNAVAILABLE",
            f"catalogue observé : '{modele_demande}' est exposé mais "
            f"l'effort demandé '{EFFORT_DEMANDE_CODEX}' est absent des "
            f"efforts explicitement annoncés {efforts} ; aucune "
            "substitution d'effort n'est admise",
        )
    if not efforts:
        return (
            sondes,
            version,
            projection_login,
            INCONNU,
            modele_demande,
            INCONNU,
            "HOLD",
            "MISSING_OBSERVATION",
            "client, version, authentification et catalogue observés par "
            f"les sondes non génératives ; '{modele_demande}' est exposé "
            "mais le catalogue n'annonce explicitement aucun effort ; plan "
            "du compte, quota et identité réellement servie restent "
            "inobservables sans commande générative : la route n'est pas "
            "prouvée prête",
        )
    return (
        sondes,
        version,
        projection_login,
        INCONNU,
        modele_demande,
        EFFORT_DEMANDE_CODEX,
        "HOLD",
        "MISSING_OBSERVATION",
        "client, version, authentification et catalogue observés par les "
        f"sondes non génératives ; '{modele_demande}' et l'effort "
        f"'{EFFORT_DEMANDE_CODEX}' sont explicitement annoncés par la "
        "correspondance de catalogue exacte, qui ne prouve jamais le "
        "modèle réellement servi ; plan du compte, quota et identité "
        "réellement servie restent inobservables sans commande "
        "générative : la route n'est pas prouvée prête",
    )


ADAPTATEUR_GROK = "grok"
# D-V1-01 : politique d'effort demandée de la configuration grok-build-grok-4-6
EFFORT_DEMANDE_GROK = "high"
# Sondes non génératives Grok : jamais de login, logout, agent, -p,
# --prompt-file, prompt positionnel, session interactive ni commande
# portant --model ; liste exacte et fermée
SONDE_VERSION_GROK = ("grok", "version", "--json")
SONDE_AIDE_GROK = ("grok", "--help")
SONDE_CATALOGUE_GROK = ("grok", "models")
SONDES_AUTORISEES_PREFLIGHT_GROK = (
    SONDE_VERSION_GROK,
    SONDE_AIDE_GROK,
    SONDE_CATALOGUE_GROK,
)
CHAMPS_PROJECTION_VERSION_GROK = ("version",)
CHAMPS_PROJECTION_AIDE_GROK = ("option_modele_native", "option_effort_native")
CHAMPS_PROJECTION_CATALOGUE_GROK = ("modele_demande_present",)
# Détection textuelle des options natives dans l'aide : aucune commande
# portant --model n'est jamais lancée
_MOTIF_OPTION_MODELE_GROK = re.compile(r"(?<![\w-])--model(?![\w-])")
_MOTIF_OPTION_EFFORT_GROK = re.compile(r"(?<![\w-])--reasoning-effort(?![\w-])")
# Les flux du client réel portent des séquences ANSI ; elles sont retirées
# avant projection et jamais persistées
_MOTIF_ANSI = re.compile(r"\x1b\[[0-9;]*m")
ENTETE_CATALOGUE_GROK = "Available models:"
# Grok Build 1.0.5 n'a pas de commande de statut d'authentification ; le
# client documente ~/.grok/auth.json comme stockage de ses credentials.
# Projection minimale fermée : présence d'un credential, auth_mode = oidc et
# issuer normalisé https://auth.x.ai. La clé d'entrée, le jeton, le refresh
# token, l'expiration, l'utilisateur, l'e-mail, les identifiants
# d'organisation ou d'équipe et le document brut ne sortent jamais de la
# mémoire locale ; la présence de cette métadonnée ne prouve pas à elle
# seule la validité distante du credential.
CHEMIN_AUTH_GROK = Path(".grok") / "auth.json"
AUTH_MODE_OIDC_GROK = "oidc"
ISSUER_XAI_GROK = "https://auth.x.ai"
CHAMPS_PROJECTION_AUTH_GROK = ("credential_present", "auth_mode", "issuer")


def _projeter_version_grok(stdout: str, stderr: str) -> dict | None:
    """Projection de la seule version machine de 'grok version --json'.

    None signale un JSON illisible ou un champ currentVersion absent : le
    préflight reste fail-closed sans inventer de fait.
    """
    for flux in (stdout, stderr):
        try:
            donnees = json.loads(flux)
        except json.JSONDecodeError:
            continue
        version = (
            donnees.get("currentVersion") if isinstance(donnees, dict) else None
        )
        if isinstance(version, str) and version.strip():
            return {"version": version.strip()}
    return None


def _projeter_aide_grok(stdout: str, stderr: str) -> dict | None:
    """Projection de l'aide : présence des seules options natives de
    sélection explicite du modèle et d'effort.

    Le texte d'aide complet n'est jamais conservé. None signale une aide
    vide donc inobservée : fail-closed sans inventer de fait.
    """
    texte = _MOTIF_ANSI.sub("", stdout + "\n" + stderr)
    if not texte.strip():
        return None
    return {
        "option_modele_native": bool(_MOTIF_OPTION_MODELE_GROK.search(texte)),
        "option_effort_native": bool(_MOTIF_OPTION_EFFORT_GROK.search(texte)),
    }


def _projeter_catalogue_grok(
    stdout: str, stderr: str, modele_demande: str
) -> dict | None:
    """Projection du catalogue : présence ou absence de la correspondance
    exacte du modèle demandé, rien d'autre.

    Le catalogue complet, le modèle par défaut, les avertissements de
    configuration et les autres modèles ne sont jamais conservés. None
    signale une section de catalogue absente ou vide : le préflight reste
    fail-closed sans inventer de fait.
    """
    for flux in (stdout, stderr):
        noms: list[str] = []
        dans_section = False
        for ligne in _MOTIF_ANSI.sub("", flux).splitlines():
            depouillee = ligne.strip()
            if depouillee == ENTETE_CATALOGUE_GROK:
                dans_section = True
                continue
            if not dans_section or not depouillee:
                continue
            if depouillee[:2] in ("* ", "- "):
                jetons = depouillee[2:].split()
                if jetons:
                    noms.append(jetons[0])
            else:
                break
        if noms:
            return {"modele_demande_present": modele_demande in noms}
    return None


def _projeter_credential_grok() -> dict | None:
    """Projection locale minimale du credential documenté ~/.grok/auth.json.

    Lecture seule : le préflight ne renouvelle pas l'authentification et ne
    modifie aucun fichier Grok. Seuls trois faits sortent de la mémoire
    locale : la présence d'un credential, auth_mode s'il vaut exactement
    'oidc' et l'issuer s'il se normalise exactement en https://auth.x.ai ;
    toute valeur divergente est projetée INCONNU sans être conservée. None
    signale un document illisible ou une forme ambiguë (plusieurs
    credentials, champs documentés absents) : fail-closed.
    """
    chemin = Path.home() / CHEMIN_AUTH_GROK
    if not chemin.exists():
        return {
            "credential_present": False,
            "auth_mode": INCONNU,
            "issuer": INCONNU,
        }
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(donnees, dict):
        return None
    if not donnees:
        return {
            "credential_present": False,
            "auth_mode": INCONNU,
            "issuer": INCONNU,
        }
    if len(donnees) != 1:
        # Plusieurs credentials : credential actif indécidable, forme ambiguë
        return None
    credential = next(iter(donnees.values()))
    if not isinstance(credential, dict):
        return None
    auth_mode = credential.get("auth_mode")
    issuer = credential.get("oidc_issuer")
    if not isinstance(auth_mode, str) or not isinstance(issuer, str):
        return None
    issuer_normalise = issuer.strip().rstrip("/").lower()
    if (
        auth_mode.strip() != AUTH_MODE_OIDC_GROK
        or issuer_normalise != ISSUER_XAI_GROK
    ):
        # Forme documentée jointe non satisfaite : seule la présence est
        # projetée, aucune revendication partielle
        return {
            "credential_present": True,
            "auth_mode": INCONNU,
            "issuer": INCONNU,
        }
    return {
        "credential_present": True,
        "auth_mode": AUTH_MODE_OIDC_GROK,
        "issuer": ISSUER_XAI_GROK,
    }


def _observer_route_grok(
    modele_demande: str,
) -> tuple[list[dict], str, object, str, str, str, str, str | None, str]:
    """Sonde la route grok sans génération.

    Rend (sondes, version, authentification observée, plan observé, modèle
    exposé, effort exposé, verdict, cause, fait). MSW : version, options
    natives et correspondance exacte de catalogue sont observables par les
    trois sondes de la liste blanche ; le credential local n'est observé que
    par la projection minimale de ~/.grok/auth.json, qui ne prouve jamais sa
    validité distante ; la sélection explicite exige ensemble l'option
    native --model et la présence exacte du modèle au catalogue ; l'option
    --reasoning-effort seule ne prouve pas que l'effort demandé est exposé
    pour le modèle demandé ; plan du compte, quota et identité réellement
    servie restent INCONNU sans commande générative, donc READY n'est
    jamais prouvable dans cette tranche.
    """
    sondes: list[dict] = []
    commande_version = " ".join(SONDE_VERSION_GROK)
    commande_aide = " ".join(SONDE_AIDE_GROK)
    commande_catalogue = " ".join(SONDE_CATALOGUE_GROK)
    if shutil.which(ADAPTATEUR_GROK) is None:
        return (
            sondes,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "INTERFACE_UNAVAILABLE",
            f"client '{ADAPTATEUR_GROK}' introuvable sur le PATH local ; "
            "aucune sonde lancée",
        )
    with tempfile.TemporaryDirectory() as espace_texte:
        execution = _executer_borne(
            list(SONDE_VERSION_GROK),
            b"",
            Path(espace_texte),
            DELAI_SONDE_PREFLIGHT,
        )
    if execution["etat"] == "INCIDENT":
        return (
            sondes,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_version}' : {_expurger(execution['fait'])}",
        )
    if execution["code_sortie"] != 0:
        # La sortie brute d'une sonde en échec n'est jamais consignée
        sondes.append(
            {
                "commande": commande_version,
                "code_sortie": execution["code_sortie"],
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "INTERFACE_UNAVAILABLE",
            f"sonde '{commande_version}' en échec : code de sortie "
            f"{execution['code_sortie']}, le client n'est pas utilisable ; "
            "la projection du credential et les sondes d'aide et de "
            "catalogue ne sont pas lancées",
        )
    projection_version = _projeter_version_grok(
        execution["sortie"]["stdout"], execution["sortie"]["stderr"]
    )
    if projection_version is None:
        sondes.append(
            {
                "commande": commande_version,
                "code_sortie": 0,
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_version}' : JSON illisible ou champ "
            "currentVersion absent, version inobservée ; la sortie brute "
            "n'est pas consignée",
        )
    sondes.append(
        {
            "commande": commande_version,
            "code_sortie": 0,
            "projection": projection_version,
        }
    )
    version = projection_version["version"]
    projection_credential = _projeter_credential_grok()
    if projection_credential is None:
        return (
            sondes,
            version,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            "projection locale de ~/.grok/auth.json : document illisible ou "
            "forme de credential ambiguë ; le document brut n'est pas "
            "consigné ; les sondes d'aide et de catalogue ne sont pas "
            "lancées",
        )
    if not projection_credential["credential_present"]:
        return (
            sondes,
            version,
            projection_credential,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "AUTHENTICATION_UNAVAILABLE",
            "aucun credential dans ~/.grok/auth.json : aucun credential "
            "OAuth xAI configuré, la route n'est pas utilisable ; les "
            "sondes d'aide et de catalogue ne sont pas lancées",
        )
    if (
        projection_credential["auth_mode"] != AUTH_MODE_OIDC_GROK
        or projection_credential["issuer"] != ISSUER_XAI_GROK
    ):
        return (
            sondes,
            version,
            projection_credential,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "AUTHENTICATION_UNAVAILABLE",
            "credential présent dans ~/.grok/auth.json mais hors de la "
            "forme OAuth xAI documentée (auth_mode 'oidc' et issuer xAI "
            "normalisé, ensemble) : aucun credential OAuth xAI configuré ; "
            "les valeurs divergentes ne sont pas consignées ; les sondes "
            "d'aide et de catalogue ne sont pas lancées",
        )
    with tempfile.TemporaryDirectory() as espace_texte:
        execution_aide = _executer_borne(
            list(SONDE_AIDE_GROK),
            b"",
            Path(espace_texte),
            DELAI_SONDE_PREFLIGHT,
        )
    if execution_aide["etat"] == "INCIDENT":
        return (
            sondes,
            version,
            projection_credential,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_aide}' : {_expurger(execution_aide['fait'])}",
        )
    if execution_aide["code_sortie"] != 0:
        sondes.append(
            {
                "commande": commande_aide,
                "code_sortie": execution_aide["code_sortie"],
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            projection_credential,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_aide}' en échec : code de sortie "
            f"{execution_aide['code_sortie']}, options natives inobservées ; "
            "la sortie brute n'est pas consignée",
        )
    projection_aide = _projeter_aide_grok(
        execution_aide["sortie"]["stdout"], execution_aide["sortie"]["stderr"]
    )
    if projection_aide is None:
        sondes.append(
            {
                "commande": commande_aide,
                "code_sortie": 0,
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            projection_credential,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_aide}' : aide vide, options natives "
            "inobservées ; la sortie brute n'est pas consignée",
        )
    sondes.append(
        {
            "commande": commande_aide,
            "code_sortie": 0,
            "projection": projection_aide,
        }
    )
    if not projection_aide["option_modele_native"]:
        return (
            sondes,
            version,
            projection_credential,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "MODEL_UNAVAILABLE",
            "aide observée sans option native --model : la sélection "
            f"explicite de '{modele_demande}' est impossible et le modèle "
            "par défaut ne vaut jamais preuve du pin ; la sonde de "
            "catalogue n'est pas lancée",
        )
    with tempfile.TemporaryDirectory() as espace_texte:
        execution_catalogue = _executer_borne(
            list(SONDE_CATALOGUE_GROK),
            b"",
            Path(espace_texte),
            DELAI_SONDE_PREFLIGHT,
        )
    if execution_catalogue["etat"] == "INCIDENT":
        return (
            sondes,
            version,
            projection_credential,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_catalogue}' : "
            f"{_expurger(execution_catalogue['fait'])}",
        )
    if execution_catalogue["code_sortie"] != 0:
        # Le catalogue complet n'est jamais consigné, même en échec
        sondes.append(
            {
                "commande": commande_catalogue,
                "code_sortie": execution_catalogue["code_sortie"],
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            projection_credential,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_catalogue}' en échec : code de sortie "
            f"{execution_catalogue['code_sortie']}, catalogue inobservé ; "
            "la sortie brute n'est pas consignée",
        )
    projection_catalogue = _projeter_catalogue_grok(
        execution_catalogue["sortie"]["stdout"],
        execution_catalogue["sortie"]["stderr"],
        modele_demande,
    )
    if projection_catalogue is None:
        sondes.append(
            {
                "commande": commande_catalogue,
                "code_sortie": 0,
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            projection_credential,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_catalogue}' : section de catalogue absente "
            "ou illisible, catalogue inobservé ; la sortie brute n'est pas "
            "consignée",
        )
    sondes.append(
        {
            "commande": commande_catalogue,
            "code_sortie": 0,
            "projection": projection_catalogue,
        }
    )
    if not projection_catalogue["modele_demande_present"]:
        return (
            sondes,
            version,
            projection_credential,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "MODEL_UNAVAILABLE",
            f"catalogue observé sans correspondance exacte pour "
            f"'{modele_demande}' : le modèle demandé n'est pas exposé par "
            "le client ; aucun alias, préfixe approximatif ni modèle par "
            "défaut n'est admis",
        )
    return (
        sondes,
        version,
        projection_credential,
        INCONNU,
        modele_demande,
        INCONNU,
        "HOLD",
        "MISSING_OBSERVATION",
        "client, version, credential OAuth xAI configuré, option native "
        "--model et correspondance de catalogue exacte observés par les "
        "sondes non génératives et la projection locale du credential, qui "
        "ne prouve jamais la validité distante du credential ni le modèle "
        "réellement servi ; l'option --reasoning-effort seule ne prouve pas "
        f"que l'effort '{EFFORT_DEMANDE_GROK}' est exposé pour "
        f"'{modele_demande}' ; plan du compte, quota, effort exposé et "
        "identité réellement servie restent inobservables : la route n'est "
        "pas prouvée prête",
    )


ADAPTATEUR_CURSOR = "agent"
# D-V1-01 : politique d'effort demandée de la configuration cursor-kimi-k3
EFFORT_DEMANDE_CURSOR = "high"
# Identifiant Cursor exact attendu par la combinaison décidée
# « Kimi K3 + high » ; kimi-k3-low, kimi-k3-max, kimi-k2.7-code, tout
# alias, préfixe ou sous-chaîne sont des non-correspondances
CIBLE_CATALOGUE_CURSOR = "kimi-k3-high"
# Probes non génératives Cursor : jamais de -p, --print, agent, create-chat,
# resume, prompt positionnel, session interactive, --model, --force, --yolo,
# --auto-review, --approve-mcps, --api-key, --endpoint, login, logout,
# worker ni commande portant un modèle ; liste exacte et fermée
SONDE_VERSION_CURSOR = ("agent", "--version")
SONDE_AIDE_CURSOR = ("agent", "--help")
SONDE_STATUT_CURSOR = ("agent", "status", "--format", "json")
SONDE_COMPTE_CURSOR = ("agent", "about", "--format", "json")
SONDE_CATALOGUE_CURSOR = ("agent", "models")
SONDES_AUTORISEES_PREFLIGHT_CURSOR = (
    SONDE_VERSION_CURSOR,
    SONDE_AIDE_CURSOR,
    SONDE_STATUT_CURSOR,
    SONDE_COMPTE_CURSOR,
    SONDE_CATALOGUE_CURSOR,
)
CHAMPS_PROJECTION_VERSION_CURSOR = ("version",)
CHAMPS_PROJECTION_AIDE_CURSOR = ("option_modele_native", "syntaxe_effort_high")
# Projection fermée du statut : seuls status et isAuthenticated sortent de
# la mémoire locale ; userInfo, e-mail, identifiant, prénom, nom, date de
# création, access token et refresh token ne sont jamais lus ni conservés
CHAMPS_PROJECTION_STATUT_CURSOR = ("status", "isAuthenticated")
# Projection fermée du compte : seuls cliVersion et subscriptionTier sortent
# de la mémoire locale ; userEmail, lastRequestId, modèle par défaut,
# système, architecture, terminal et shell ne sont jamais lus ni conservés
CHAMPS_PROJECTION_COMPTE_CURSOR = ("cliVersion", "subscriptionTier")
CHAMPS_PROJECTION_CATALOGUE_CURSOR = ("cible_presente",)
# Détection textuelle des seules formes natives dans l'aide : aucune
# commande portant --model n'est jamais lancée
_MOTIF_OPTION_MODELE_CURSOR = re.compile(r"(?<![\w-])--model(?![\w-])")
_MOTIF_EFFORT_HIGH_CURSOR = re.compile(r"(?<![\w-])effort=high(?![\w-])")


def _projeter_version_cursor(stdout: str, stderr: str) -> dict | None:
    """Projection de la seule version non vide de 'agent --version'.

    None signale une sortie vide donc inobservée : le préflight reste
    fail-closed sans inventer de fait.
    """
    for flux in (stdout, stderr):
        for ligne in _MOTIF_ANSI.sub("", flux).splitlines():
            texte = ligne.strip()
            if texte:
                return {"version": texte}
    return None


def _projeter_aide_cursor(stdout: str, stderr: str) -> dict | None:
    """Projection de l'aide : présence de la seule option native --model et
    de la syntaxe d'override d'effort documentant effort=high.

    Le texte d'aide complet n'est jamais conservé. None signale une aide
    vide donc inobservée : fail-closed sans inventer de fait.
    """
    texte = _MOTIF_ANSI.sub("", stdout + "\n" + stderr)
    if not texte.strip():
        return None
    return {
        "option_modele_native": bool(_MOTIF_OPTION_MODELE_CURSOR.search(texte)),
        "syntaxe_effort_high": bool(_MOTIF_EFFORT_HIGH_CURSOR.search(texte)),
    }


def _projeter_statut_cursor(stdout: str, stderr: str) -> dict | None:
    """Projection en mémoire du statut : seuls status et isAuthenticated.

    Tout autre champ servi, notamment userInfo et les jetons, est ignoré
    sans être lu ni conservé. None signale un JSON illisible ou une
    structure attendue absente : fail-closed sans inventer de fait.
    """
    for flux in (stdout, stderr):
        try:
            donnees = json.loads(flux)
        except json.JSONDecodeError:
            continue
        if not isinstance(donnees, dict):
            continue
        statut = donnees.get("status")
        authentifie = donnees.get("isAuthenticated")
        if (
            isinstance(statut, str)
            and statut.strip()
            and isinstance(authentifie, bool)
        ):
            return {"status": statut.strip(), "isAuthenticated": authentifie}
    return None


def _projeter_compte_cursor(stdout: str, stderr: str) -> dict | None:
    """Projection en mémoire du compte : seuls cliVersion et subscriptionTier.

    Un champ absent est projeté INCONNU, jamais inventé. None signale un
    JSON illisible ou une valeur hors forme : fail-closed sans inventer de
    fait.
    """
    for flux in (stdout, stderr):
        try:
            donnees = json.loads(flux)
        except json.JSONDecodeError:
            continue
        if not isinstance(donnees, dict):
            continue
        projection: dict = {}
        for champ in CHAMPS_PROJECTION_COMPTE_CURSOR:
            valeur = donnees.get(champ)
            if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
                projection[champ] = INCONNU
            elif isinstance(valeur, str):
                projection[champ] = valeur.strip()
            else:
                return None
        return projection
    return None


def _projeter_catalogue_cursor(stdout: str, stderr: str, cible: str) -> dict | None:
    """Projection du catalogue : présence ou absence de la cible exacte,
    rien d'autre.

    Le catalogue complet, les autres modèles et le modèle par défaut ne sont
    jamais conservés. None signale une section illisible ou un catalogue
    ambigu (cible dupliquée) : fail-closed sans inventer de fait.
    """
    for flux in (stdout, stderr):
        identifiants: list[str] = []
        for ligne in _MOTIF_ANSI.sub("", flux).splitlines():
            depouillee = ligne.strip()
            if depouillee[:2] in ("* ", "- ", "• "):
                depouillee = depouillee[2:].strip()
            if " - " not in depouillee:
                continue
            identifiant = depouillee.split(" - ", 1)[0].strip()
            if identifiant and " " not in identifiant:
                identifiants.append(identifiant)
        if identifiants:
            if identifiants.count(cible) > 1:
                return None
            return {"cible_presente": cible in identifiants}
    return None


def _observer_route_cursor() -> tuple[
    list[dict], str, object, str, str, str, str, str | None, str
]:
    """Sonde la route agent (Cursor CLI) sans génération.

    Rend (sondes, version, authentification observée, plan observé, modèle
    exposé, effort exposé, verdict, cause, fait). MSW : version, sélection
    native exacte, statut d'authentification, tier du compte et
    correspondance de catalogue exacte sont observables par les cinq probes
    de la liste blanche ; la présence exacte de la cible projette le modèle
    exposé et l'effort high, jamais l'identité réellement servie ; le quota,
    sa consommation et l'identité réellement servie restent INCONNU sans
    commande générative, donc READY n'est jamais prouvable dans cette
    tranche.
    """
    sondes: list[dict] = []
    commande_version = " ".join(SONDE_VERSION_CURSOR)
    commande_aide = " ".join(SONDE_AIDE_CURSOR)
    commande_statut = " ".join(SONDE_STATUT_CURSOR)
    commande_compte = " ".join(SONDE_COMPTE_CURSOR)
    commande_catalogue = " ".join(SONDE_CATALOGUE_CURSOR)
    if shutil.which(ADAPTATEUR_CURSOR) is None:
        return (
            sondes,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "INTERFACE_UNAVAILABLE",
            f"client '{ADAPTATEUR_CURSOR}' introuvable sur le PATH local ; "
            "aucune probe lancée",
        )
    with tempfile.TemporaryDirectory() as espace_texte:
        execution = _executer_borne(
            list(SONDE_VERSION_CURSOR),
            b"",
            Path(espace_texte),
            DELAI_SONDE_PREFLIGHT,
        )
    if execution["etat"] == "INCIDENT":
        return (
            sondes,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_version}' : {_expurger(execution['fait'])}",
        )
    if execution["code_sortie"] != 0:
        # La sortie brute d'une probe en échec n'est jamais consignée
        sondes.append(
            {
                "commande": commande_version,
                "code_sortie": execution["code_sortie"],
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "INTERFACE_UNAVAILABLE",
            f"probe '{commande_version}' en échec : code de sortie "
            f"{execution['code_sortie']}, le client n'est pas utilisable ; "
            "les probes d'aide, de statut, de compte et de catalogue ne "
            "sont pas lancées",
        )
    projection_version = _projeter_version_cursor(
        execution["sortie"]["stdout"], execution["sortie"]["stderr"]
    )
    if projection_version is None:
        sondes.append(
            {
                "commande": commande_version,
                "code_sortie": 0,
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_version}' : sortie vide, version inobservée ; "
            "aucune valeur n'est inventée",
        )
    sondes.append(
        {
            "commande": commande_version,
            "code_sortie": 0,
            "projection": projection_version,
        }
    )
    version = projection_version["version"]
    with tempfile.TemporaryDirectory() as espace_texte:
        execution_aide = _executer_borne(
            list(SONDE_AIDE_CURSOR),
            b"",
            Path(espace_texte),
            DELAI_SONDE_PREFLIGHT,
        )
    if execution_aide["etat"] == "INCIDENT":
        return (
            sondes,
            version,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_aide}' : {_expurger(execution_aide['fait'])}",
        )
    if execution_aide["code_sortie"] != 0:
        sondes.append(
            {
                "commande": commande_aide,
                "code_sortie": execution_aide["code_sortie"],
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_aide}' en échec : code de sortie "
            f"{execution_aide['code_sortie']}, sélection native inobservée ; "
            "la sortie brute n'est pas consignée",
        )
    projection_aide = _projeter_aide_cursor(
        execution_aide["sortie"]["stdout"], execution_aide["sortie"]["stderr"]
    )
    if projection_aide is None:
        sondes.append(
            {
                "commande": commande_aide,
                "code_sortie": 0,
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_aide}' : aide vide, sélection native "
            "inobservée ; la sortie brute n'est pas consignée",
        )
    sondes.append(
        {
            "commande": commande_aide,
            "code_sortie": 0,
            "projection": projection_aide,
        }
    )
    if not projection_aide["option_modele_native"] or not projection_aide[
        "syntaxe_effort_high"
    ]:
        return (
            sondes,
            version,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            "aide observée sans sélection native exacte : l'option native "
            "--model et la syntaxe d'override effort=high sont exigées "
            "ensemble ; les probes de statut, de compte et de catalogue ne "
            "sont pas lancées",
        )
    with tempfile.TemporaryDirectory() as espace_texte:
        execution_statut = _executer_borne(
            list(SONDE_STATUT_CURSOR),
            b"",
            Path(espace_texte),
            DELAI_SONDE_PREFLIGHT,
        )
    if execution_statut["etat"] == "INCIDENT":
        return (
            sondes,
            version,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_statut}' : {_expurger(execution_statut['fait'])}",
        )
    projection_statut = _projeter_statut_cursor(
        execution_statut["sortie"]["stdout"], execution_statut["sortie"]["stderr"]
    )
    if projection_statut is None:
        # La sortie brute d'une probe de statut n'est jamais consignée
        sondes.append(
            {
                "commande": commande_statut,
                "code_sortie": execution_statut["code_sortie"],
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            INCONNU,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_statut}' : JSON illisible ou structure "
            f"attendue absente (code de sortie "
            f"{execution_statut['code_sortie']}), statut d'authentification "
            "inobservé ; la sortie brute n'est pas consignée",
        )
    sondes.append(
        {
            "commande": commande_statut,
            "code_sortie": execution_statut["code_sortie"],
            "projection": projection_statut,
        }
    )
    if not projection_statut["isAuthenticated"]:
        return (
            sondes,
            version,
            projection_statut,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "AUTHENTICATION_UNAVAILABLE",
            "statut observé isAuthenticated=false : aucune authentification "
            "active, la route n'est pas utilisable ; les probes de compte "
            "et de catalogue ne sont pas lancées",
        )
    with tempfile.TemporaryDirectory() as espace_texte:
        execution_compte = _executer_borne(
            list(SONDE_COMPTE_CURSOR),
            b"",
            Path(espace_texte),
            DELAI_SONDE_PREFLIGHT,
        )
    if execution_compte["etat"] == "INCIDENT":
        return (
            sondes,
            version,
            projection_statut,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_compte}' : {_expurger(execution_compte['fait'])}",
        )
    projection_compte = _projeter_compte_cursor(
        execution_compte["sortie"]["stdout"], execution_compte["sortie"]["stderr"]
    )
    if projection_compte is None:
        # La sortie brute d'une probe de compte n'est jamais consignée
        sondes.append(
            {
                "commande": commande_compte,
                "code_sortie": execution_compte["code_sortie"],
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            projection_statut,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_compte}' : JSON illisible ou valeur hors "
            f"forme (code de sortie {execution_compte['code_sortie']}), "
            "compte inobservé ; la sortie brute n'est pas consignée",
        )
    sondes.append(
        {
            "commande": commande_compte,
            "code_sortie": execution_compte["code_sortie"],
            "projection": projection_compte,
        }
    )
    if projection_compte["subscriptionTier"] == INCONNU:
        return (
            sondes,
            version,
            projection_statut,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "MISSING_OBSERVATION",
            "compte authentifié dont subscriptionTier est absent ou vide : "
            "le tier actif du compte reste inobservé, aucune valeur de "
            "remplacement n'est créée ; la probe de catalogue n'est pas "
            "lancée",
        )
    plan_observe = projection_compte["subscriptionTier"]
    with tempfile.TemporaryDirectory() as espace_texte:
        execution_catalogue = _executer_borne(
            list(SONDE_CATALOGUE_CURSOR),
            b"",
            Path(espace_texte),
            DELAI_SONDE_PREFLIGHT,
        )
    if execution_catalogue["etat"] == "INCIDENT":
        return (
            sondes,
            version,
            projection_statut,
            plan_observe,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_catalogue}' : "
            f"{_expurger(execution_catalogue['fait'])}",
        )
    if execution_catalogue["code_sortie"] != 0:
        # Le catalogue complet n'est jamais consigné, même en échec
        sondes.append(
            {
                "commande": commande_catalogue,
                "code_sortie": execution_catalogue["code_sortie"],
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            projection_statut,
            plan_observe,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_catalogue}' en échec : code de sortie "
            f"{execution_catalogue['code_sortie']}, catalogue inobservé ; "
            "la sortie brute n'est pas consignée",
        )
    projection_catalogue = _projeter_catalogue_cursor(
        execution_catalogue["sortie"]["stdout"],
        execution_catalogue["sortie"]["stderr"],
        CIBLE_CATALOGUE_CURSOR,
    )
    if projection_catalogue is None:
        sondes.append(
            {
                "commande": commande_catalogue,
                "code_sortie": 0,
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            projection_statut,
            plan_observe,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_catalogue}' : catalogue illisible ou ambigu, "
            "correspondance inobservée ; la sortie brute n'est pas "
            "consignée",
        )
    sondes.append(
        {
            "commande": commande_catalogue,
            "code_sortie": 0,
            "projection": projection_catalogue,
        }
    )
    if not projection_catalogue["cible_presente"]:
        return (
            sondes,
            version,
            projection_statut,
            plan_observe,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "MODEL_UNAVAILABLE",
            f"catalogue lisible sans correspondance exacte pour "
            f"'{CIBLE_CATALOGUE_CURSOR}' : la combinaison décidée n'est pas "
            "exposée par le client ; aucune variante low, max ou k2.7, "
            "aucun alias, préfixe ou sous-chaîne n'est admis",
        )
    return (
        sondes,
        version,
        projection_statut,
        plan_observe,
        CIBLE_CATALOGUE_CURSOR,
        EFFORT_DEMANDE_CURSOR,
        "HOLD",
        "MISSING_OBSERVATION",
        "client, version, sélection native exacte, authentification, tier "
        "du compte et correspondance de catalogue exacte observés par les "
        f"cinq probes non génératives ; la présence exacte de "
        f"'{CIBLE_CATALOGUE_CURSOR}' projette le modèle exposé et l'effort "
        f"'{EFFORT_DEMANDE_CURSOR}', jamais l'identité réellement servie ; "
        "quota, consommation de quota et identité réellement servie "
        "restent inobservables sans commande générative : la route n'est "
        "pas prouvée prête",
    )


ADAPTATEUR_OPENCODEX = "opencodex"
FOURNISSEUR_ZAI = "zai"
# Contrat de récupération scellé du 23 août 2026 : identité exacte de la
# route, toute divergence est un HOLD / IDENTITY_MISMATCH
ADAPTATEUR_FOURNISSEUR_ZAI = "openai-chat"
ENDPOINT_DECLARE_ZAI = "https://api.z.ai/api/coding/paas/v4"
SOURCE_QUOTA_ZAI = "zai:quota-limit"
# D-V1-01 : politique d'effort ferme de la configuration zai-glm-5-3
EFFORT_DEMANDE_ZAI = "high"
# Sondes non génératives OpenCodex : jamais codex exec, provider test,
# --refresh, sync, start, stop, login, logout, account use, account
# refresh, config set, config unset, models add, models edit, OpenCode,
# OpenCode Go, Zen, un prompt ni une commande générative ; liste exacte,
# fermée et ordonnée
SONDE_VERSION_OPENCODEX = ("opencodex", "--version")
SONDE_READY_OPENCODEX = ("opencodex", "ready", "--json")
SONDE_FOURNISSEUR_OPENCODEX = ("opencodex", "provider", "show", "zai", "--json")
SONDE_CATALOGUE_OPENCODEX = (
    "opencodex",
    "models",
    "live",
    "--provider",
    "zai",
    "--json",
)
SONDE_COMPTE_OPENCODEX = ("opencodex", "account", "current", "zai", "--json")
SONDE_QUOTA_OPENCODEX = ("opencodex", "provider", "quota", "--json")
SONDES_AUTORISEES_PREFLIGHT_OPENCODEX = (
    SONDE_VERSION_OPENCODEX,
    SONDE_READY_OPENCODEX,
    SONDE_FOURNISSEUR_OPENCODEX,
    SONDE_CATALOGUE_OPENCODEX,
    SONDE_COMPTE_OPENCODEX,
    SONDE_QUOTA_OPENCODEX,
)
CHAMPS_PROJECTION_VERSION_OPENCODEX = ("version",)
# Projection fermée de readiness : seuls ready et status sortent de la
# mémoire locale ; pid, port, uptime et identité HTTP brute ne sont jamais
# conservés
CHAMPS_PROJECTION_READY_OPENCODEX = ("ready", "status")
STATUTS_READY_OPENCODEX = ("ready", "pending", "failed", "unreachable")
# Projection fermée du fournisseur : apiKey, apiKeyPool, en-têtes, notes et
# document brut ne sont jamais lus ni conservés
CHAMPS_PROJECTION_FOURNISSEUR_OPENCODEX = (
    "nom",
    "adaptateur",
    "endpoint",
    "modele_defaut",
    "desactive",
    "modele_demande_present",
)
# Projection fermée du catalogue courant : le catalogue complet, les autres
# modèles, l'effort par défaut et les autres efforts ne sont jamais
# conservés
CHAMPS_PROJECTION_CATALOGUE_OPENCODEX = (
    "entree_presente",
    "desactivee",
    "effort_high_present",
)
# Projection fermée du compte : activeId, id, masked, label, priorité,
# fragments de clé et document brut ne sont jamais lus ni conservés
CHAMPS_PROJECTION_COMPTE_OPENCODEX = ("fournisseur", "type", "cle_active")
# Projection fermée du quota : les rapports des autres fournisseurs, le
# libellé du rapport et la réponse brute ne sont jamais conservés
CHAMPS_PROJECTION_QUOTA_OPENCODEX = (
    "rapport_zai_present",
    "source",
    "fenetres_reconnues",
)
# Fenêtres de quota reconnues du rapport zai:quota-limit, dans cet ordre :
# (nom projeté, champ pourcentage, champ reset)
FENETRES_QUOTA_ZAI = (
    ("cinq_heures", "fiveHourPercent", "fiveHourResetAt"),
    ("hebdomadaire", "weeklyPercent", "weeklyResetAt"),
    ("mensuelle", "monthlyPercent", "monthlyResetAt"),
)
NOMS_FENETRES_QUOTA_ZAI = tuple(nom for nom, _, _ in FENETRES_QUOTA_ZAI)


def _premier_json_opencodex(stdout: str, stderr: str) -> object:
    """Premier flux entièrement JSON, ou None si aucun ne l'est"""
    for flux in (stdout, stderr):
        try:
            return json.loads(flux)
        except json.JSONDecodeError:
            continue
    return None


def _projeter_version_opencodex(stdout: str, stderr: str) -> dict | None:
    """Projection de la seule version non vide de 'opencodex --version'.

    None signale une sortie vide donc inobservée : le préflight reste
    fail-closed sans inventer de fait.
    """
    for flux in (stdout, stderr):
        for ligne in _MOTIF_ANSI.sub("", flux).splitlines():
            texte = ligne.strip()
            if texte:
                return {"version": texte}
    return None


def _projeter_ready_opencodex(stdout: str, stderr: str) -> dict | None:
    """Projection en mémoire de la readiness : seuls ready et status.

    pid, port et tout autre champ servi sont ignorés sans être conservés.
    None signale un JSON illisible ou un statut hors vocabulaire fermé :
    fail-closed sans inventer de fait.
    """
    donnees = _premier_json_opencodex(stdout, stderr)
    if not isinstance(donnees, dict):
        return None
    pret = donnees.get("ready")
    statut = donnees.get("status")
    if not isinstance(pret, bool) or statut not in STATUTS_READY_OPENCODEX:
        return None
    return {"ready": pret, "status": statut}


def _projeter_fournisseur_opencodex(
    stdout: str, stderr: str, modele_demande: str
) -> dict | None:
    """Projection en mémoire du fournisseur configuré : nom, adaptateur,
    endpoint, modèle par défaut, état désactivé et présence du modèle
    demandé.

    apiKey, apiKeyPool, en-têtes et notes ne sont jamais lus ni conservés.
    None signale un JSON illisible ou une structure hors forme : fail-closed
    sans inventer de fait.
    """
    donnees = _premier_json_opencodex(stdout, stderr)
    if not isinstance(donnees, dict):
        return None
    nom = donnees.get("name")
    adaptateur = donnees.get("adapter")
    endpoint = donnees.get("baseUrl")
    if any(
        not isinstance(valeur, str) or not valeur.strip()
        for valeur in (nom, adaptateur, endpoint)
    ):
        return None
    modele_defaut = donnees.get("defaultModel")
    if modele_defaut is None:
        modele_defaut = INCONNU
    elif not isinstance(modele_defaut, str) or not modele_defaut.strip():
        return None
    desactive = donnees.get("disabled", False)
    if not isinstance(desactive, bool):
        return None
    modeles = donnees.get("models", [])
    if not isinstance(modeles, list) or any(
        not isinstance(entree, str) for entree in modeles
    ):
        return None
    return {
        "nom": nom.strip(),
        "adaptateur": adaptateur.strip(),
        "endpoint": endpoint.strip(),
        "modele_defaut": modele_defaut,
        "desactive": desactive,
        "modele_demande_present": (
            modele_defaut == modele_demande or modele_demande in modeles
        ),
    }


def _projeter_catalogue_opencodex(
    stdout: str, stderr: str, cible: str
) -> dict | None:
    """Projection du catalogue courant : présence de l'entrée exacte, son
    état désactivé et la présence de l'effort high, rien d'autre.

    Le catalogue complet, les autres modèles, l'effort par défaut et les
    autres efforts ne sont jamais conservés. None signale un JSON illisible,
    une ligne hors forme ou une entrée dupliquée donc ambiguë : fail-closed
    sans inventer de fait.
    """
    donnees = _premier_json_opencodex(stdout, stderr)
    if not isinstance(donnees, list):
        return None
    correspondances = []
    for ligne in donnees:
        if not isinstance(ligne, dict):
            return None
        if ligne.get("namespaced") == cible:
            correspondances.append(ligne)
    if not correspondances:
        return {
            "entree_presente": False,
            "desactivee": INCONNU,
            "effort_high_present": INCONNU,
        }
    if len(correspondances) > 1:
        return None
    entree = correspondances[0]
    desactivee = entree.get("disabled")
    if not isinstance(desactivee, bool):
        return None
    efforts = entree.get("reasoningEfforts", [])
    if not isinstance(efforts, list) or any(
        not isinstance(effort, str) for effort in efforts
    ):
        return None
    return {
        "entree_presente": True,
        "desactivee": desactivee,
        "effort_high_present": EFFORT_DEMANDE_ZAI in efforts,
    }


def _projeter_compte_opencodex(stdout: str, stderr: str) -> dict | None:
    """Projection en mémoire du compte : fournisseur, type et présence
    d'une clé active.

    activeId, id, masked, label, priorité et tout fragment de clé sont
    ignorés sans être conservés. None signale un JSON illisible, un
    fournisseur divergent ou une structure hors forme : fail-closed sans
    inventer de fait.
    """
    donnees = _premier_json_opencodex(stdout, stderr)
    if not isinstance(donnees, dict) or "account" not in donnees:
        return None
    fournisseur = donnees.get("provider")
    type_compte = donnees.get("type")
    if (
        fournisseur != FOURNISSEUR_ZAI
        or not isinstance(type_compte, str)
        or not type_compte.strip()
    ):
        return None
    return {
        "fournisseur": fournisseur,
        "type": type_compte.strip(),
        "cle_active": donnees["account"] is not None,
    }


def _projeter_quota_opencodex(
    stdout: str, stderr: str
) -> tuple[dict, object] | None:
    """Projection du quota : présence du rapport exact provider = zai, sa
    source et les fenêtres reconnues, plus le détail observé par fenêtre.

    Les rapports des autres fournisseurs, le libellé et la réponse brute ne
    sont jamais conservés. Les pourcentages et resets absents restent
    INCONNU, aucune valeur n'est reconstruite. None signale un JSON
    illisible, un rapport dupliqué donc ambigu ou une valeur hors forme :
    fail-closed sans inventer de fait.
    """
    donnees = _premier_json_opencodex(stdout, stderr)
    if not isinstance(donnees, dict) or not isinstance(
        donnees.get("reports"), list
    ):
        return None
    rapports = [
        rapport
        for rapport in donnees["reports"]
        if isinstance(rapport, dict)
        and rapport.get("provider") == FOURNISSEUR_ZAI
    ]
    if not rapports:
        return (
            {
                "rapport_zai_present": False,
                "source": INCONNU,
                "fenetres_reconnues": [],
            },
            INCONNU,
        )
    if len(rapports) > 1:
        return None
    rapport = rapports[0]
    source = rapport.get("source")
    if not isinstance(source, str) or not source.strip():
        return None
    quota = rapport.get("quota")
    if not isinstance(quota, dict):
        return None
    fenetres: dict[str, dict] = {}
    reconnues: list[str] = []
    for nom, champ_pourcentage, champ_reset in FENETRES_QUOTA_ZAI:
        pourcentage = quota.get(champ_pourcentage)
        reset = quota.get(champ_reset)
        if pourcentage is not None and (
            isinstance(pourcentage, bool)
            or not isinstance(pourcentage, (int, float))
        ):
            return None
        if reset is not None and (
            isinstance(reset, bool) or not isinstance(reset, (int, float))
        ):
            return None
        if pourcentage is not None:
            reconnues.append(nom)
        fenetres[nom] = {
            "pourcentage": pourcentage if pourcentage is not None else INCONNU,
            "reset": reset if reset is not None else INCONNU,
        }
    projection = {
        "rapport_zai_present": True,
        "source": source.strip(),
        "fenetres_reconnues": reconnues,
    }
    return projection, {"source": source.strip(), "fenetres": fenetres}


def _observer_route_zai(modele_demande: str) -> dict:
    """Sonde la route OpenCodex vers le Z.AI Coding Plan sans génération.

    Rend un état d'observation complet : sondes, version, authentification,
    plan observé, modèle exposé, effort exposé, quota observé, proxy
    OpenCodex, catalogue déclaré, verdict, cause et fait. MSW : les cinq
    contrôles de readiness (interface et proxy, authentification, activité
    du plan, modèle et effort exposés, quota disponible) sont observables
    par les six probes de la liste blanche, donc READY est prouvable dans
    cette tranche ; l'identité réellement servie reste INCONNU sans
    génération et ne devient jamais une conclusion.
    """
    cible = f"{FOURNISSEUR_ZAI}/{modele_demande}"
    etat: dict = {
        "sondes": [],
        "version": INCONNU,
        "authentification": INCONNU,
        "plan_observe": INCONNU,
        "modele_expose": INCONNU,
        "effort_expose": INCONNU,
        "quota_observe": INCONNU,
        "proxy_opencodex": {
            "version": INCONNU,
            "ready": INCONNU,
            "status": INCONNU,
        },
        "catalogue_declare": {
            "fournisseur": INCONNU,
            "adaptateur": INCONNU,
            "endpoint": INCONNU,
            "entree_exacte_presente": INCONNU,
            "effort_high_present": INCONNU,
        },
    }

    def stop(verdict: str, cause: str | None, fait: str) -> dict:
        etat.update({"verdict": verdict, "cause": cause, "fait": fait})
        return etat

    def sonder(sonde: tuple[str, ...]) -> dict:
        with tempfile.TemporaryDirectory() as espace_texte:
            return _executer_borne(
                list(sonde), b"", Path(espace_texte), DELAI_SONDE_PREFLIGHT
            )

    commande_version = " ".join(SONDE_VERSION_OPENCODEX)
    commande_ready = " ".join(SONDE_READY_OPENCODEX)
    commande_fournisseur = " ".join(SONDE_FOURNISSEUR_OPENCODEX)
    commande_catalogue = " ".join(SONDE_CATALOGUE_OPENCODEX)
    commande_compte = " ".join(SONDE_COMPTE_OPENCODEX)
    commande_quota = " ".join(SONDE_QUOTA_OPENCODEX)
    if shutil.which(ADAPTATEUR_OPENCODEX) is None:
        return stop(
            "UNAVAILABLE",
            "INTERFACE_UNAVAILABLE",
            f"client '{ADAPTATEUR_OPENCODEX}' introuvable sur le PATH local ; "
            "aucune probe lancée",
        )
    execution = sonder(SONDE_VERSION_OPENCODEX)
    if execution["etat"] == "INCIDENT":
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_version}' : {_expurger(execution['fait'])}",
        )
    if execution["code_sortie"] != 0:
        # La sortie brute d'une probe en échec n'est jamais consignée
        etat["sondes"].append(
            {
                "commande": commande_version,
                "code_sortie": execution["code_sortie"],
                "projection": INCONNU,
            }
        )
        return stop(
            "UNAVAILABLE",
            "INTERFACE_UNAVAILABLE",
            f"probe '{commande_version}' en échec : code de sortie "
            f"{execution['code_sortie']}, le client n'est pas utilisable ; "
            "les probes de readiness, de fournisseur, de catalogue, de "
            "compte et de quota ne sont pas lancées",
        )
    projection_version = _projeter_version_opencodex(
        execution["sortie"]["stdout"], execution["sortie"]["stderr"]
    )
    if projection_version is None:
        etat["sondes"].append(
            {"commande": commande_version, "code_sortie": 0, "projection": INCONNU}
        )
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_version}' : sortie vide, version inobservée ; "
            "aucune valeur n'est inventée",
        )
    etat["sondes"].append(
        {
            "commande": commande_version,
            "code_sortie": 0,
            "projection": projection_version,
        }
    )
    etat["version"] = projection_version["version"]
    etat["proxy_opencodex"]["version"] = projection_version["version"]
    execution_ready = sonder(SONDE_READY_OPENCODEX)
    if execution_ready["etat"] == "INCIDENT":
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_ready}' : {_expurger(execution_ready['fait'])}",
        )
    projection_ready = _projeter_ready_opencodex(
        execution_ready["sortie"]["stdout"], execution_ready["sortie"]["stderr"]
    )
    if projection_ready is None:
        # La sortie brute d'une probe de readiness n'est jamais consignée
        etat["sondes"].append(
            {
                "commande": commande_ready,
                "code_sortie": execution_ready["code_sortie"],
                "projection": INCONNU,
            }
        )
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_ready}' : JSON illisible ou statut hors "
            f"vocabulaire fermé (code de sortie "
            f"{execution_ready['code_sortie']}), readiness inobservée ; la "
            "sortie brute n'est pas consignée",
        )
    etat["sondes"].append(
        {
            "commande": commande_ready,
            "code_sortie": execution_ready["code_sortie"],
            "projection": projection_ready,
        }
    )
    etat["proxy_opencodex"]["ready"] = projection_ready["ready"]
    etat["proxy_opencodex"]["status"] = projection_ready["status"]
    if not projection_ready["ready"]:
        return stop(
            "UNAVAILABLE",
            "PROVIDER_FAILURE",
            f"proxy observé non prêt (status '{projection_ready['status']}') "
            "alors que la probe est bien formée : la route n'est pas "
            "utilisable ; les probes de fournisseur, de catalogue, de compte "
            "et de quota ne sont pas lancées",
        )
    execution_fournisseur = sonder(SONDE_FOURNISSEUR_OPENCODEX)
    if execution_fournisseur["etat"] == "INCIDENT":
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_fournisseur}' : "
            f"{_expurger(execution_fournisseur['fait'])}",
        )
    projection_fournisseur = None
    if execution_fournisseur["code_sortie"] == 0:
        projection_fournisseur = _projeter_fournisseur_opencodex(
            execution_fournisseur["sortie"]["stdout"],
            execution_fournisseur["sortie"]["stderr"],
            modele_demande,
        )
    if projection_fournisseur is None:
        # Le document du fournisseur n'est jamais consigné, même en échec
        etat["sondes"].append(
            {
                "commande": commande_fournisseur,
                "code_sortie": execution_fournisseur["code_sortie"],
                "projection": INCONNU,
            }
        )
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_fournisseur}' : JSON illisible, structure "
            f"hors forme ou probe en échec (code de sortie "
            f"{execution_fournisseur['code_sortie']}), fournisseur "
            "inobservé ; la sortie brute n'est pas consignée",
        )
    etat["sondes"].append(
        {
            "commande": commande_fournisseur,
            "code_sortie": 0,
            "projection": projection_fournisseur,
        }
    )
    etat["catalogue_declare"]["fournisseur"] = projection_fournisseur["nom"]
    etat["catalogue_declare"]["adaptateur"] = projection_fournisseur["adaptateur"]
    etat["catalogue_declare"]["endpoint"] = projection_fournisseur["endpoint"]
    if (
        projection_fournisseur["nom"] != FOURNISSEUR_ZAI
        or projection_fournisseur["adaptateur"] != ADAPTATEUR_FOURNISSEUR_ZAI
        or projection_fournisseur["endpoint"] != ENDPOINT_DECLARE_ZAI
    ):
        return stop(
            "HOLD",
            "IDENTITY_MISMATCH",
            "fournisseur, adaptateur ou endpoint observé divergent de "
            f"l'identité scellée ('{FOURNISSEUR_ZAI}', "
            f"'{ADAPTATEUR_FOURNISSEUR_ZAI}', endpoint déclaré du contrat de "
            "récupération) : aucune substitution n'est admise ; les probes "
            "de catalogue, de compte et de quota ne sont pas lancées",
        )
    execution_catalogue = sonder(SONDE_CATALOGUE_OPENCODEX)
    if execution_catalogue["etat"] == "INCIDENT":
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_catalogue}' : "
            f"{_expurger(execution_catalogue['fait'])}",
        )
    projection_catalogue = None
    if execution_catalogue["code_sortie"] == 0:
        projection_catalogue = _projeter_catalogue_opencodex(
            execution_catalogue["sortie"]["stdout"],
            execution_catalogue["sortie"]["stderr"],
            cible,
        )
    if projection_catalogue is None:
        # Le catalogue complet n'est jamais consigné, même en échec
        etat["sondes"].append(
            {
                "commande": commande_catalogue,
                "code_sortie": execution_catalogue["code_sortie"],
                "projection": INCONNU,
            }
        )
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_catalogue}' : JSON illisible, entrée ambiguë "
            f"ou probe en échec (code de sortie "
            f"{execution_catalogue['code_sortie']}), catalogue inobservé ; "
            "la sortie brute n'est pas consignée",
        )
    etat["sondes"].append(
        {
            "commande": commande_catalogue,
            "code_sortie": 0,
            "projection": projection_catalogue,
        }
    )
    etat["catalogue_declare"]["entree_exacte_presente"] = projection_catalogue[
        "entree_presente"
    ]
    etat["catalogue_declare"]["effort_high_present"] = projection_catalogue[
        "effort_high_present"
    ]
    if not projection_catalogue["entree_presente"] or projection_catalogue[
        "desactivee"
    ]:
        return stop(
            "UNAVAILABLE",
            "MODEL_UNAVAILABLE",
            f"catalogue courant lisible sans entrée exacte '{cible}' active : "
            "la combinaison décidée n'est pas exposée ; aucun alias, préfixe "
            "ou sous-chaîne n'est admis ; les probes de compte et de quota "
            "ne sont pas lancées",
        )
    if not projection_catalogue["effort_high_present"]:
        return stop(
            "UNAVAILABLE",
            "MODEL_UNAVAILABLE",
            f"entrée exacte '{cible}' présente sans effort "
            f"'{EFFORT_DEMANDE_ZAI}' annoncé : le harnais déclaré impose cet "
            "effort, aucun effort par défaut n'est sélectionné ; les probes "
            "de compte et de quota ne sont pas lancées",
        )
    etat["modele_expose"] = cible
    etat["effort_expose"] = EFFORT_DEMANDE_ZAI
    execution_compte = sonder(SONDE_COMPTE_OPENCODEX)
    if execution_compte["etat"] == "INCIDENT":
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_compte}' : {_expurger(execution_compte['fait'])}",
        )
    projection_compte = _projeter_compte_opencodex(
        execution_compte["sortie"]["stdout"],
        execution_compte["sortie"]["stderr"],
    )
    if projection_compte is None:
        # La sortie brute d'une probe de compte n'est jamais consignée
        etat["sondes"].append(
            {
                "commande": commande_compte,
                "code_sortie": execution_compte["code_sortie"],
                "projection": INCONNU,
            }
        )
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_compte}' : JSON illisible, fournisseur "
            f"divergent ou structure hors forme (code de sortie "
            f"{execution_compte['code_sortie']}), compte inobservé ; la "
            "sortie brute n'est pas consignée",
        )
    etat["sondes"].append(
        {
            "commande": commande_compte,
            "code_sortie": execution_compte["code_sortie"],
            "projection": projection_compte,
        }
    )
    etat["authentification"] = projection_compte
    if not projection_compte["cle_active"]:
        return stop(
            "UNAVAILABLE",
            "AUTHENTICATION_UNAVAILABLE",
            "aucune clé active observée pour le fournisseur "
            f"'{FOURNISSEUR_ZAI}' : la route n'est pas utilisable ; la probe "
            "de quota n'est pas lancée",
        )
    execution_quota = sonder(SONDE_QUOTA_OPENCODEX)
    if execution_quota["etat"] == "INCIDENT":
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_quota}' : {_expurger(execution_quota['fait'])}",
        )
    resultat_quota = None
    if execution_quota["code_sortie"] == 0:
        resultat_quota = _projeter_quota_opencodex(
            execution_quota["sortie"]["stdout"],
            execution_quota["sortie"]["stderr"],
        )
    if resultat_quota is None:
        # Les rapports bruts de quota ne sont jamais consignés
        etat["sondes"].append(
            {
                "commande": commande_quota,
                "code_sortie": execution_quota["code_sortie"],
                "projection": INCONNU,
            }
        )
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_quota}' : JSON illisible, rapport ambigu ou "
            f"probe en échec (code de sortie "
            f"{execution_quota['code_sortie']}), quota inobservé ; la sortie "
            "brute n'est pas consignée",
        )
    projection_quota, detail_quota = resultat_quota
    etat["sondes"].append(
        {
            "commande": commande_quota,
            "code_sortie": 0,
            "projection": projection_quota,
        }
    )
    if (
        not projection_quota["rapport_zai_present"]
        or projection_quota["source"] != SOURCE_QUOTA_ZAI
        or not projection_quota["fenetres_reconnues"]
    ):
        # plan.observe ne devient observé que si la réponse zai:quota-limit
        # est présente et exploitable ; aucune valeur n'est reconstruite
        return stop(
            "HOLD",
            "MISSING_OBSERVATION",
            "aucun rapport 'zai:quota-limit' exploitable : rapport absent, "
            "source divergente ou aucune fenêtre reconnue ; l'activité du "
            "plan reste inobservée, aucune valeur de remplacement n'est "
            "créée",
        )
    etat["quota_observe"] = detail_quota
    # Le libellé déclaré du plan reste distinct : seul le fait que
    # l'endpoint de quota du Coding Plan a répondu est observé
    etat["plan_observe"] = (
        "endpoint de quota du Coding Plan a répondu (source zai:quota-limit)"
    )
    fenetres_bloquantes = [
        nom
        for nom, fenetre in detail_quota["fenetres"].items()
        if fenetre["pourcentage"] != INCONNU and fenetre["pourcentage"] >= 100
    ]
    if fenetres_bloquantes:
        return stop(
            "UNAVAILABLE",
            "QUOTA_EXHAUSTED",
            "quota observé épuisé dans une fenêtre bloquante "
            f"({', '.join(sorted(fenetres_bloquantes))}) : la route n'est "
            "pas utilisable tant que la fenêtre n'est pas réinitialisée",
        )
    return stop(
        "READY",
        None,
        "interface et proxy, authentification, activité du plan, modèle et "
        "effort exposés et quota disponible observés par les six probes non "
        f"génératives ; la présence exacte de '{cible}' projette le modèle "
        f"exposé et l'effort '{EFFORT_DEMANDE_ZAI}', jamais l'identité "
        "réellement servie, qui reste INCONNU sans génération",
    )


ADAPTATEUR_ANTIGRAVITY = "agy"
# D-V1-01 : la variante d'effort est portée par le suffixe de l'identifiant
# natif exact ; aucune variante fast, priority, max ou ultra, aucun alias,
# préfixe ou sous-chaîne n'est admis
EFFORT_DEMANDE_ANTIGRAVITY = "high"
CIBLE_CATALOGUE_ANTIGRAVITY = "gemini-3.7-flash-high"
LIBELLE_CIBLE_ANTIGRAVITY = "Gemini 3.7 Flash (High)"
# Probes non génératives Antigravity : jamais agy en TUI, agy -i,
# --prompt-interactive, -p avec un argument autre que le littéral /usage,
# update, install, plugin, mcp, /model, /credits, /logout, une commande de
# connexion, une génération, un prompt, --dangerously-skip-permissions,
# --model, --effort, --agent, --continue, --conversation, --project,
# --mode, --sandbox ni un format d'entrée modèle ; liste exacte, fermée et
# ordonnée
SONDE_VERSION_ANTIGRAVITY = ("agy", "--version")
SONDE_CATALOGUE_ANTIGRAVITY = ("agy", "models")
# /usage est la commande interne documentée qui rafraîchit le quota depuis
# le backend, exécutée comme commande autonome : jamais un prompt candidat
SONDE_USAGE_ANTIGRAVITY = ("agy", "-p", "/usage")
SONDES_AUTORISEES_PREFLIGHT_ANTIGRAVITY = (
    SONDE_VERSION_ANTIGRAVITY,
    SONDE_CATALOGUE_ANTIGRAVITY,
    SONDE_USAGE_ANTIGRAVITY,
)
CHAMPS_PROJECTION_VERSION_ANTIGRAVITY = ("version",)
# Projection fermée du catalogue : présence de l'identifiant exact et
# concordance de son libellé exact ; les autres modèles et la sortie brute
# ne sont jamais conservés
CHAMPS_PROJECTION_CATALOGUE_ANTIGRAVITY = (
    "entree_exacte_presente",
    "libelle_concordant",
)
# Projection fermée de /usage : catégorie Gemini Models et fenêtres Gemini
# reconnues ; les lignes Claude/GPT et la sortie brute ne sont jamais
# conservées
CHAMPS_PROJECTION_USAGE_ANTIGRAVITY = (
    "categorie_gemini_presente",
    "fenetres_reconnues",
)
# Authentification de métadonnées : accessibilité observée du catalogue et
# du quota ; compte, email, jeton de keyring, chemin de profil et
# identifiant de conversation ne sont jamais lus ni conservés
CHAMPS_AUTH_ANTIGRAVITY = (
    "metadonnees_catalogue_accessibles",
    "metadonnees_quota_accessibles",
)
CATEGORIE_USAGE_ANTIGRAVITY = "Gemini Models"
SOURCE_QUOTA_ANTIGRAVITY = "agy:/usage"
# Fenêtres Gemini reconnues de /usage, dans cet ordre : (nom projeté,
# libellé exact de fenêtre) ; les fenêtres des autres familles ne
# compensent jamais une fenêtre Gemini absente ou épuisée
FENETRES_USAGE_ANTIGRAVITY = (
    ("cinq_heures", "Five Hour Limit Remaining"),
    ("hebdomadaire", "Weekly Limit Remaining"),
)
NOMS_FENETRES_USAGE_ANTIGRAVITY = tuple(
    nom for nom, _ in FENETRES_USAGE_ANTIGRAVITY
)
# La catégorie active de /usage prouve une catégorie de quota, jamais un
# palier tarifaire, un prix ou une facture
PLAN_OBSERVE_ANTIGRAVITY = (
    "catégorie 'Gemini Models' active dans /usage, palier commercial non "
    "observé"
)
# Messages explicites reconnus, listes fermées : seule la classe d'échec
# est projetée, la sortie brute n'est jamais consignée
_MOTIF_AUTH_REQUISE_ANTIGRAVITY = re.compile(
    r"(?i)\b(?:not (?:logged|signed) in|log ?in required|authentication "
    r"required|please (?:log|sign) in|no active session|session expired)\b"
)
_MOTIF_ERREUR_FOURNISSEUR_ANTIGRAVITY = re.compile(
    r"(?i)\b(?:server|backend|internal|api) error\b|\bservice unavailable\b"
)
_MOTIF_ENTREE_ANTIGRAVITY = re.compile(
    r"(?<![\w.-])" + re.escape(CIBLE_CATALOGUE_ANTIGRAVITY) + r"(?![\w.-])"
)
_MOTIF_POURCENTAGE_ANTIGRAVITY = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_MOTIF_RESET_ANTIGRAVITY = re.compile(r"(?i)\bresets?\b[\s:]*(.+?)\s*\)?\s*$")
# Forme réelle observée au diagnostic de lancement : le reset ISO 8601 est
# le dernier champ de la ligne de fenêtre, sans mot reset
_MOTIF_RESET_ISO_ANTIGRAVITY = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
)
_SEPARATEURS_LIBELLE_ANTIGRAVITY = " \t-–—:·|*•()[]"


def _projeter_version_antigravity(stdout: str, stderr: str) -> dict | None:
    """Projection de la seule version non vide de 'agy --version'.

    None signale une sortie vide donc inobservée : le préflight reste
    fail-closed sans inventer de fait.
    """
    for flux in (stdout, stderr):
        for ligne in _MOTIF_ANSI.sub("", flux).splitlines():
            texte = ligne.strip()
            if texte:
                return {"version": texte}
    return None


def _classer_echec_antigravity(stdout: str, stderr: str) -> str | None:
    """Classe d'un échec de probe : 'authentification' sur message explicite
    d'authentification requise ou de session absente, 'fournisseur' sur
    erreur explicite du backend ou du fournisseur, None sinon.

    Seule la classe sort de la mémoire locale, jamais le message brut.
    """
    texte = _MOTIF_ANSI.sub("", stdout + "\n" + stderr)
    if _MOTIF_AUTH_REQUISE_ANTIGRAVITY.search(texte):
        return "authentification"
    if _MOTIF_ERREUR_FOURNISSEUR_ANTIGRAVITY.search(texte):
        return "fournisseur"
    return None


def _projeter_catalogue_antigravity(stdout: str, stderr: str) -> dict | None:
    """Projection du catalogue : présence de l'identifiant exact et
    concordance de son libellé exact, rien d'autre.

    Le catalogue complet et les autres modèles ne sont jamais conservés.
    None signale une sortie vide ou un identifiant présent dont le libellé
    reste illisible : fail-closed sans inventer de fait.
    """
    for flux in (stdout, stderr):
        lignes = [
            ligne
            for ligne in _MOTIF_ANSI.sub("", flux).splitlines()
            if ligne.strip()
        ]
        if not lignes:
            continue
        lignes_cible = [
            ligne
            for ligne in lignes
            if _MOTIF_ENTREE_ANTIGRAVITY.search(ligne)
        ]
        if not lignes_cible:
            return {
                "entree_exacte_presente": False,
                "libelle_concordant": INCONNU,
            }
        if any(LIBELLE_CIBLE_ANTIGRAVITY in ligne for ligne in lignes_cible):
            return {"entree_exacte_presente": True, "libelle_concordant": True}
        restes = [
            _MOTIF_ENTREE_ANTIGRAVITY.sub("", ligne).strip(
                _SEPARATEURS_LIBELLE_ANTIGRAVITY
            )
            for ligne in lignes_cible
        ]
        if all(not reste for reste in restes):
            # Identifiant présent sans libellé lisible : la concordance
            # reste inobservée, aucune valeur n'est inventée
            return None
        return {"entree_exacte_presente": True, "libelle_concordant": False}
    return None


def _projeter_usage_antigravity(
    stdout: str, stderr: str
) -> tuple[dict, object] | None:
    """Projection de /usage : catégorie 'Gemini Models', fenêtres Gemini
    reconnues et leur détail pourcentage restant / reset.

    Le reset est reconnu sous deux formes : un champ introduit par le mot
    resets, ou la forme réelle du diagnostic de lancement où l'horodatage
    ISO 8601 est le dernier champ de la même ligne, sans mot reset. Les
    lignes Claude/GPT, les autres catégories et la sortie brute ne sont
    jamais conservées. Les pourcentages et resets absents restent INCONNU,
    aucune valeur n'est reconstruite. None signale une sortie sans forme
    d'usage reconnaissable ou une fenêtre Gemini dupliquée donc ambiguë :
    fail-closed sans inventer de fait.
    """
    for flux in (stdout, stderr):
        lignes = [
            ligne.strip()
            for ligne in _MOTIF_ANSI.sub("", flux).splitlines()
            if ligne.strip()
        ]
        if not lignes:
            continue
        if not any(
            ligne.rstrip(" :·-").endswith("Models")
            or "Limit Remaining" in ligne
            for ligne in lignes
        ):
            return None
        fenetres: dict[str, dict] = {
            nom: {"pourcentage_restant": INCONNU, "reset": INCONNU}
            for nom in NOMS_FENETRES_USAGE_ANTIGRAVITY
        }
        vues: set[str] = set()
        categorie_presente = False
        section_gemini = False
        for ligne in lignes:
            if ligne.rstrip(" :·-").endswith("Models"):
                section_gemini = CATEGORIE_USAGE_ANTIGRAVITY in ligne
                categorie_presente = categorie_presente or section_gemini
                continue
            gemini_inline = CATEGORIE_USAGE_ANTIGRAVITY in ligne
            if not section_gemini and not gemini_inline:
                continue
            for nom, libelle in FENETRES_USAGE_ANTIGRAVITY:
                if libelle not in ligne:
                    continue
                if gemini_inline:
                    categorie_presente = True
                if nom in vues:
                    return None
                vues.add(nom)
                pourcentage = _MOTIF_POURCENTAGE_ANTIGRAVITY.search(ligne)
                if pourcentage:
                    nombre = float(pourcentage.group(1))
                    fenetres[nom]["pourcentage_restant"] = (
                        int(nombre) if nombre.is_integer() else nombre
                    )
                reset = _MOTIF_RESET_ANTIGRAVITY.search(ligne)
                if reset and reset.group(1).strip():
                    fenetres[nom]["reset"] = reset.group(1).strip()
                else:
                    # Forme réelle du diagnostic : reset ISO 8601 en dernier
                    # champ de la même ligne, sans mot reset
                    horodatages = _MOTIF_RESET_ISO_ANTIGRAVITY.findall(ligne)
                    if horodatages:
                        fenetres[nom]["reset"] = horodatages[-1]
        if not categorie_presente:
            return (
                {"categorie_gemini_presente": False, "fenetres_reconnues": []},
                INCONNU,
            )
        reconnues = [
            nom
            for nom in NOMS_FENETRES_USAGE_ANTIGRAVITY
            if fenetres[nom]["pourcentage_restant"] != INCONNU
        ]
        return (
            {
                "categorie_gemini_presente": True,
                "fenetres_reconnues": reconnues,
            },
            {"source": SOURCE_QUOTA_ANTIGRAVITY, "fenetres": fenetres},
        )
    return None


def _observer_route_antigravity() -> dict:
    """Sonde la route Antigravity vers Gemini 3.7 Flash (High) sans
    génération.

    Rend un état d'observation complet : sondes, version, authentification,
    plan observé, modèle exposé, effort exposé, quota observé, verdict,
    cause et fait. MSW : les cinq contrôles de readiness (interface,
    authentification de métadonnées, activité de la catégorie Gemini du
    plan, identifiant exact avec variante high, quota Gemini non épuisé)
    sont couverts par les trois probes de la liste blanche ; que ces probes
    suffisent à établir READY sur la route réelle reste une hypothèse non
    vérifiée tant qu'une observation réelle ne l'a pas prouvé, jamais un
    fait acquis d'avance. L'identité réellement servie reste INCONNU sans
    génération et ne devient jamais une conclusion.
    """
    etat: dict = {
        "sondes": [],
        "version": INCONNU,
        "authentification": INCONNU,
        "plan_observe": INCONNU,
        "modele_expose": INCONNU,
        "effort_expose": INCONNU,
        "quota_observe": INCONNU,
    }

    def stop(verdict: str, cause: str | None, fait: str) -> dict:
        etat.update({"verdict": verdict, "cause": cause, "fait": fait})
        return etat

    def sonder(sonde: tuple[str, ...]) -> dict:
        with tempfile.TemporaryDirectory() as espace_texte:
            return _executer_borne(
                list(sonde), b"", Path(espace_texte), DELAI_SONDE_PREFLIGHT
            )

    commande_version = " ".join(SONDE_VERSION_ANTIGRAVITY)
    commande_catalogue = " ".join(SONDE_CATALOGUE_ANTIGRAVITY)
    commande_usage = " ".join(SONDE_USAGE_ANTIGRAVITY)
    if shutil.which(ADAPTATEUR_ANTIGRAVITY) is None:
        return stop(
            "UNAVAILABLE",
            "INTERFACE_UNAVAILABLE",
            f"client '{ADAPTATEUR_ANTIGRAVITY}' introuvable sur le PATH "
            "local ; aucune probe lancée",
        )
    execution = sonder(SONDE_VERSION_ANTIGRAVITY)
    if execution["etat"] == "INCIDENT":
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_version}' : {_expurger(execution['fait'])}",
        )
    if execution["code_sortie"] != 0:
        # La sortie brute d'une probe en échec n'est jamais consignée
        etat["sondes"].append(
            {
                "commande": commande_version,
                "code_sortie": execution["code_sortie"],
                "projection": INCONNU,
            }
        )
        return stop(
            "UNAVAILABLE",
            "INTERFACE_UNAVAILABLE",
            f"probe '{commande_version}' en échec : code de sortie "
            f"{execution['code_sortie']}, le client n'est pas utilisable ; "
            "les probes de catalogue et d'usage ne sont pas lancées",
        )
    projection_version = _projeter_version_antigravity(
        execution["sortie"]["stdout"], execution["sortie"]["stderr"]
    )
    if projection_version is None:
        etat["sondes"].append(
            {"commande": commande_version, "code_sortie": 0, "projection": INCONNU}
        )
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_version}' : sortie vide, version inobservée ; "
            "aucune valeur n'est inventée",
        )
    etat["sondes"].append(
        {
            "commande": commande_version,
            "code_sortie": 0,
            "projection": projection_version,
        }
    )
    etat["version"] = projection_version["version"]
    execution_catalogue = sonder(SONDE_CATALOGUE_ANTIGRAVITY)
    if execution_catalogue["etat"] == "INCIDENT":
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_catalogue}' : "
            f"{_expurger(execution_catalogue['fait'])}",
        )
    classe_catalogue = _classer_echec_antigravity(
        execution_catalogue["sortie"]["stdout"],
        execution_catalogue["sortie"]["stderr"],
    )
    if classe_catalogue == "authentification":
        etat["sondes"].append(
            {
                "commande": commande_catalogue,
                "code_sortie": execution_catalogue["code_sortie"],
                "projection": INCONNU,
            }
        )
        etat["authentification"] = {
            "metadonnees_catalogue_accessibles": False,
            "metadonnees_quota_accessibles": INCONNU,
        }
        return stop(
            "UNAVAILABLE",
            "AUTHENTICATION_UNAVAILABLE",
            f"probe '{commande_catalogue}' : message explicite "
            "d'authentification requise ou de session absente, aucune "
            "session de métadonnées utilisable ; la sortie brute n'est pas "
            "consignée ; la probe d'usage n'est pas lancée",
        )
    if execution_catalogue["code_sortie"] != 0:
        # Le catalogue complet n'est jamais consigné, même en échec
        etat["sondes"].append(
            {
                "commande": commande_catalogue,
                "code_sortie": execution_catalogue["code_sortie"],
                "projection": INCONNU,
            }
        )
        if classe_catalogue == "fournisseur":
            return stop(
                "UNAVAILABLE",
                "PROVIDER_FAILURE",
                f"probe '{commande_catalogue}' : erreur explicite du backend "
                f"ou du fournisseur (code de sortie "
                f"{execution_catalogue['code_sortie']}) ; la sortie brute "
                "n'est pas consignée ; la probe d'usage n'est pas lancée",
            )
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_catalogue}' en échec non attribuable : code "
            f"de sortie {execution_catalogue['code_sortie']}, catalogue "
            "inobservé ; la sortie brute n'est pas consignée",
        )
    projection_catalogue = _projeter_catalogue_antigravity(
        execution_catalogue["sortie"]["stdout"],
        execution_catalogue["sortie"]["stderr"],
    )
    if projection_catalogue is None:
        etat["sondes"].append(
            {
                "commande": commande_catalogue,
                "code_sortie": 0,
                "projection": INCONNU,
            }
        )
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_catalogue}' : catalogue vide, illisible ou "
            "au libellé inobservable, forme ambiguë ; la sortie brute n'est "
            "pas consignée",
        )
    etat["sondes"].append(
        {
            "commande": commande_catalogue,
            "code_sortie": 0,
            "projection": projection_catalogue,
        }
    )
    etat["authentification"] = {
        "metadonnees_catalogue_accessibles": True,
        "metadonnees_quota_accessibles": INCONNU,
    }
    if not projection_catalogue["entree_exacte_presente"]:
        return stop(
            "UNAVAILABLE",
            "MODEL_UNAVAILABLE",
            f"catalogue lisible sans entrée exacte "
            f"'{CIBLE_CATALOGUE_ANTIGRAVITY}' : --model échoue sans fallback "
            "quand l'identifiant n'est pas reconnu ; aucune variante fast, "
            "priority, max ou ultra, aucun alias, préfixe ou sous-chaîne "
            "n'est admis ; la probe d'usage n'est pas lancée",
        )
    if not projection_catalogue["libelle_concordant"]:
        return stop(
            "HOLD",
            "IDENTITY_MISMATCH",
            f"identifiant exact '{CIBLE_CATALOGUE_ANTIGRAVITY}' présent avec "
            f"un libellé contradictoire du libellé exact "
            f"'{LIBELLE_CIBLE_ANTIGRAVITY}' : l'identité du catalogue n'est "
            "pas établie, aucune substitution n'est admise ; la probe "
            "d'usage n'est pas lancée",
        )
    etat["modele_expose"] = CIBLE_CATALOGUE_ANTIGRAVITY
    etat["effort_expose"] = EFFORT_DEMANDE_ANTIGRAVITY
    execution_usage = sonder(SONDE_USAGE_ANTIGRAVITY)
    if execution_usage["etat"] == "INCIDENT":
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_usage}' : {_expurger(execution_usage['fait'])}",
        )
    classe_usage = _classer_echec_antigravity(
        execution_usage["sortie"]["stdout"],
        execution_usage["sortie"]["stderr"],
    )
    if classe_usage == "authentification":
        etat["sondes"].append(
            {
                "commande": commande_usage,
                "code_sortie": execution_usage["code_sortie"],
                "projection": INCONNU,
            }
        )
        etat["authentification"]["metadonnees_quota_accessibles"] = False
        return stop(
            "UNAVAILABLE",
            "AUTHENTICATION_UNAVAILABLE",
            f"probe '{commande_usage}' : message explicite "
            "d'authentification requise ou de session absente, le quota "
            "n'est pas accessible ; la sortie brute n'est pas consignée",
        )
    if execution_usage["code_sortie"] != 0:
        # Le rapport d'usage n'est jamais consigné, même en échec
        etat["sondes"].append(
            {
                "commande": commande_usage,
                "code_sortie": execution_usage["code_sortie"],
                "projection": INCONNU,
            }
        )
        if classe_usage == "fournisseur":
            return stop(
                "UNAVAILABLE",
                "PROVIDER_FAILURE",
                f"probe '{commande_usage}' : erreur explicite du backend ou "
                f"du fournisseur (code de sortie "
                f"{execution_usage['code_sortie']}) ; la sortie brute n'est "
                "pas consignée",
            )
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_usage}' en échec non attribuable : code de "
            f"sortie {execution_usage['code_sortie']}, quota inobservé ; la "
            "sortie brute n'est pas consignée",
        )
    resultat_usage = _projeter_usage_antigravity(
        execution_usage["sortie"]["stdout"],
        execution_usage["sortie"]["stderr"],
    )
    if resultat_usage is None:
        etat["sondes"].append(
            {"commande": commande_usage, "code_sortie": 0, "projection": INCONNU}
        )
        return stop(
            "HOLD",
            "HARNESS_ERROR",
            f"probe '{commande_usage}' : sortie illisible, sans forme "
            "d'usage reconnaissable ou fenêtre Gemini ambiguë ; la sortie "
            "brute n'est pas consignée",
        )
    projection_usage, detail_usage = resultat_usage
    etat["sondes"].append(
        {
            "commande": commande_usage,
            "code_sortie": 0,
            "projection": projection_usage,
        }
    )
    etat["authentification"]["metadonnees_quota_accessibles"] = True
    if not projection_usage["categorie_gemini_presente"]:
        # Les fenêtres des autres familles ne compensent jamais la
        # catégorie Gemini absente
        return stop(
            "UNAVAILABLE",
            "PLAN_UNAVAILABLE",
            "sortie /usage valide sans catégorie 'Gemini Models' : "
            "l'activité de la catégorie Gemini du plan n'est pas observée, "
            "aucune valeur de remplacement n'est créée",
        )
    etat["quota_observe"] = detail_usage
    etat["plan_observe"] = PLAN_OBSERVE_ANTIGRAVITY
    manquantes = [
        nom
        for nom in NOMS_FENETRES_USAGE_ANTIGRAVITY
        if detail_usage["fenetres"][nom]["pourcentage_restant"] == INCONNU
        or detail_usage["fenetres"][nom]["reset"] == INCONNU
    ]
    if manquantes:
        return stop(
            "HOLD",
            "MISSING_OBSERVATION",
            "fenêtre, pourcentage restant ou reset requis absent "
            f"({', '.join(sorted(manquantes))}) malgré une réponse /usage "
            "autrement reconnue : aucune valeur n'est reconstruite",
        )
    bloquantes = [
        nom
        for nom in NOMS_FENETRES_USAGE_ANTIGRAVITY
        if detail_usage["fenetres"][nom]["pourcentage_restant"] <= 0
    ]
    if bloquantes:
        return stop(
            "UNAVAILABLE",
            "QUOTA_EXHAUSTED",
            "pourcentage restant égal à zéro dans une fenêtre Gemini "
            f"bloquante ({', '.join(sorted(bloquantes))}) : la route n'est "
            "pas utilisable tant que la fenêtre n'est pas réinitialisée",
        )
    return stop(
        "READY",
        None,
        "interface, authentification de métadonnées, catégorie Gemini du "
        f"plan active, identifiant exact '{CIBLE_CATALOGUE_ANTIGRAVITY}' "
        f"avec variante '{EFFORT_DEMANDE_ANTIGRAVITY}' et deux fenêtres "
        "Gemini strictement positives observés par les trois probes non "
        "génératives ; le catalogue ne prouve pas l'accès à une génération "
        "et l'identité réellement servie reste INCONNU sans génération",
    )


def _expurger(texte: str) -> str:
    """Expurgation des captures : le chemin du compte local ne sort jamais"""
    return texte.replace(str(Path.home()), "~")


def _projeter_statut_auth(stdout: str) -> dict | None:
    """Projection en mémoire du statut d'authentification, jamais la sortie brute.

    Seuls loggedIn, authMethod, apiProvider et subscriptionType sortent d'ici ;
    tout autre champ servi par le client est ignoré sans être conservé. None
    signale un JSON illisible ou une structure attendue absente : le préflight
    reste fail-closed sans inventer de fait.
    """
    try:
        donnees = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(donnees, dict) or not isinstance(donnees.get("loggedIn"), bool):
        return None
    projection: dict = {"loggedIn": donnees["loggedIn"]}
    for champ in CHAMPS_PROJECTION_AUTH[1:]:
        valeur = donnees.get(champ)
        if valeur is None:
            projection[champ] = INCONNU
        elif isinstance(valeur, str) and valeur.strip():
            projection[champ] = valeur
        else:
            return None
    if projection["loggedIn"] and any(
        projection[champ] == INCONNU for champ in CHAMPS_PROJECTION_AUTH[1:]
    ):
        # Connecté mais structure attendue absente : observation refusée
        return None
    return projection


def _observer_route_claude() -> tuple[list[dict], str, object, str, str, str | None, str]:
    """Sonde la route claude sans génération.

    Rend (sondes, version, authentification observée, plan observé, verdict,
    cause, fait). MSW : version, authentification et plan sont observables par
    les deux sondes de la liste blanche ; l'identité du modèle servi, l'effort
    exposé et le quota restent INCONNU sans commande générative, donc READY
    n'est jamais prouvable dans cette tranche.
    """
    sondes: list[dict] = []
    commande_version = " ".join(SONDE_VERSION_CLAUDE)
    commande_auth = " ".join(SONDE_AUTH_CLAUDE)
    if shutil.which(ADAPTATEUR_CLAUDE) is None:
        return (
            sondes,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "INTERFACE_UNAVAILABLE",
            f"client '{ADAPTATEUR_CLAUDE}' introuvable sur le PATH local ; "
            "aucune sonde lancée",
        )
    with tempfile.TemporaryDirectory() as espace_texte:
        execution = _executer_borne(
            list(SONDE_VERSION_CLAUDE),
            b"",
            Path(espace_texte),
            DELAI_SONDE_PREFLIGHT,
        )
    if execution["etat"] == "INCIDENT":
        return (
            sondes,
            INCONNU,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_version}' : {_expurger(execution['fait'])}",
        )
    sondes.append(
        {
            "commande": commande_version,
            "code_sortie": execution["code_sortie"],
            "stdout_expurge": _expurger(execution["sortie"]["stdout"]),
            "stderr_expurge": _expurger(execution["sortie"]["stderr"]),
        }
    )
    if execution["code_sortie"] != 0:
        return (
            sondes,
            INCONNU,
            INCONNU,
            INCONNU,
            "UNAVAILABLE",
            "INTERFACE_UNAVAILABLE",
            f"sonde '{commande_version}' en échec : code de sortie "
            f"{execution['code_sortie']}, le client n'est pas utilisable ; la "
            "sonde d'authentification n'est pas lancée",
        )
    texte_version = _expurger(execution["sortie"]["stdout"].strip())
    version = texte_version if texte_version else INCONNU
    with tempfile.TemporaryDirectory() as espace_texte:
        execution_auth = _executer_borne(
            list(SONDE_AUTH_CLAUDE),
            b"",
            Path(espace_texte),
            DELAI_SONDE_PREFLIGHT,
        )
    if execution_auth["etat"] == "INCIDENT":
        return (
            sondes,
            version,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_auth}' : {_expurger(execution_auth['fait'])}",
        )
    if execution_auth["code_sortie"] != 0:
        # La sortie brute d'une sonde auth n'est jamais consignée
        sondes.append(
            {
                "commande": commande_auth,
                "code_sortie": execution_auth["code_sortie"],
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_auth}' en échec : code de sortie "
            f"{execution_auth['code_sortie']}, statut d'authentification "
            "inobservé ; la sortie brute n'est pas consignée",
        )
    projection = _projeter_statut_auth(execution_auth["sortie"]["stdout"])
    if projection is None:
        sondes.append(
            {
                "commande": commande_auth,
                "code_sortie": 0,
                "projection": INCONNU,
            }
        )
        return (
            sondes,
            version,
            INCONNU,
            INCONNU,
            "HOLD",
            "HARNESS_ERROR",
            f"sonde '{commande_auth}' : JSON illisible ou structure attendue "
            "absente, statut d'authentification inobservé ; la sortie brute "
            "n'est pas consignée",
        )
    sondes.append(
        {
            "commande": commande_auth,
            "code_sortie": 0,
            "projection": projection,
        }
    )
    authentification = {
        "loggedIn": projection["loggedIn"],
        "authMethod": projection["authMethod"],
        "apiProvider": projection["apiProvider"],
    }
    if not projection["loggedIn"]:
        return (
            sondes,
            version,
            authentification,
            INCONNU,
            "UNAVAILABLE",
            "AUTHENTICATION_UNAVAILABLE",
            "statut observé loggedIn=false : aucune authentification active, "
            "la route n'est pas utilisable",
        )
    return (
        sondes,
        version,
        authentification,
        projection["subscriptionType"],
        "HOLD",
        "MISSING_OBSERVATION",
        "client, version, authentification et plan observés par les sondes "
        "non génératives ; identité du modèle servi, exposition de l'effort "
        "et quota restent inobservables sans commande générative : la route "
        "n'est pas prouvée prête",
    )


def preflight_configuration(racine: Path, identifiant: str) -> int:
    registre = racine / REGISTRE_OFFICIEL
    try:
        entrees = _charger_registre(registre) if registre.is_dir() else []
    except ErreurConfiguration as erreur:
        print(f"ECHEC {erreur}")
        return 1
    correspondances = [
        donnees
        for _, donnees in entrees
        if donnees["configuration_id"] == identifiant
    ]
    if not correspondances:
        print(
            f"ECHEC option '--configuration' : '{identifiant}' absent du "
            f"registre officiel {REGISTRE_OFFICIEL.as_posix()}"
        )
        return 1
    configuration = correspondances[0]
    argv = configuration["harnais"]["argv"]
    # Le harnais génératif déclaré reste codex exec ; la route Z.AI est
    # identifiée par le préfixe fournisseur du modèle : son plan de contrôle
    # est le proxy OpenCodex, jamais l'agent codex lui-même
    valeurs_modele = [
        argv[indice + 1]
        for indice, argument in enumerate(argv[:-1])
        if argument == "--model"
    ]
    route_opencodex = any(
        valeur.startswith(f"{FOURNISSEUR_ZAI}/") for valeur in valeurs_modele
    )
    adaptateurs_couverts = (
        ADAPTATEUR_CLAUDE,
        ADAPTATEUR_CODEX,
        ADAPTATEUR_GROK,
        ADAPTATEUR_CURSOR,
        ADAPTATEUR_ANTIGRAVITY,
    )
    if configuration["interface"]["type"] != "cli" or (
        argv[0] not in adaptateurs_couverts and not route_opencodex
    ):
        print(
            f"ECHEC adaptateur non couvert : '{argv[0]}' ; V1-XS-06A à "
            f"V1-XS-06F couvrent les seuls adaptateurs '{ADAPTATEUR_CLAUDE}', "
            f"'{ADAPTATEUR_CODEX}', '{ADAPTATEUR_GROK}', "
            f"'{ADAPTATEUR_CURSOR}', '{ADAPTATEUR_OPENCODEX}' et "
            f"'{ADAPTATEUR_ANTIGRAVITY}' ; aucun autre client n'est sondé"
        )
        return 1
    supplement: dict = {}
    adaptateur = ADAPTATEUR_OPENCODEX if route_opencodex else argv[0]
    if adaptateur == ADAPTATEUR_OPENCODEX:
        observation = _observer_route_zai(configuration["modele"]["demande"])
        sondes = observation["sondes"]
        version = observation["version"]
        authentification = observation["authentification"]
        plan_observe = observation["plan_observe"]
        modele_expose = observation["modele_expose"]
        effort_expose = observation["effort_expose"]
        verdict = observation["verdict"]
        cause = observation["cause"]
        fait = observation["fait"]
        effort_demande = EFFORT_DEMANDE_ZAI
        # Quatre objets explicitement distincts : le catalogue déclaré ne
        # prouve ni l'accès réel ni l'identité servie, l'authentification ne
        # prouve pas le modèle, le quota ne prouve pas l'identité servie
        supplement = {
            "catalogue_declare": observation["catalogue_declare"],
            "proxy_opencodex": observation["proxy_opencodex"],
            "identite_reellement_servie": INCONNU,
            "quota": {
                "observe": observation["quota_observe"],
                "consommation_preflight": INCONNU,
            },
        }
    elif adaptateur == ADAPTATEUR_ANTIGRAVITY:
        observation = _observer_route_antigravity()
        sondes = observation["sondes"]
        version = observation["version"]
        authentification = observation["authentification"]
        plan_observe = observation["plan_observe"]
        modele_expose = observation["modele_expose"]
        effort_expose = observation["effort_expose"]
        verdict = observation["verdict"]
        cause = observation["cause"]
        fait = observation["fait"]
        effort_demande = EFFORT_DEMANDE_ANTIGRAVITY
        # Objets distincts : le catalogue ne prouve pas l'accès à une
        # génération, le quota ne prouve pas le modèle, l'identité
        # réellement servie reste INCONNU sans génération
        supplement = {
            "identite_reellement_servie": INCONNU,
            "quota": {
                "observe": observation["quota_observe"],
                "consommation_preflight": INCONNU,
            },
        }
    elif adaptateur == ADAPTATEUR_CURSOR:
        (
            sondes,
            version,
            authentification,
            plan_observe,
            modele_expose,
            effort_expose,
            verdict,
            cause,
            fait,
        ) = _observer_route_cursor()
        effort_demande = EFFORT_DEMANDE_CURSOR
    elif adaptateur == ADAPTATEUR_GROK:
        (
            sondes,
            version,
            authentification,
            plan_observe,
            modele_expose,
            effort_expose,
            verdict,
            cause,
            fait,
        ) = _observer_route_grok(configuration["modele"]["demande"])
        effort_demande = EFFORT_DEMANDE_GROK
    elif adaptateur == ADAPTATEUR_CODEX:
        (
            sondes,
            version,
            authentification,
            plan_observe,
            modele_expose,
            effort_expose,
            verdict,
            cause,
            fait,
        ) = _observer_route_codex(configuration["modele"]["demande"])
        effort_demande = EFFORT_DEMANDE_CODEX
    else:
        (
            sondes,
            version,
            authentification,
            plan_observe,
            verdict,
            cause,
            fait,
        ) = _observer_route_claude()
        modele_expose = INCONNU
        effort_expose = INCONNU
        effort_demande = EFFORT_DEMANDE_CLAUDE
    recu = {
        "schema_version": SCHEMA_RECU_PREFLIGHT,
        "configuration_id": identifiant,
        "date_preflight": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "autorite_preflight": AUTORITE_PREFLIGHT,
        "adaptateur": adaptateur,
        "commande_publique": (
            f"uv run tools/campagne_v1.py preflight --configuration {identifiant}"
        ),
        "sondes": sondes,
        "interface": {
            "type": configuration["interface"]["type"],
            "client": adaptateur,
            "version_observee": version,
        },
        "authentification": {"observee": authentification},
        "plan": {
            "declare": configuration["plan"]["nom"],
            "observe": plan_observe,
        },
        "modele": {
            "demande": configuration["modele"]["demande"],
            "expose": modele_expose,
        },
        "effort": {"demande": effort_demande, "expose": effort_expose},
        "quota": {"observe": INCONNU, "consommation_preflight": INCONNU},
        "verdict": verdict,
        "cause": cause,
        "fait": fait,
    }
    # Route OpenCodex : les quatre objets distincts et le quota observé
    # remplacent les valeurs par défaut
    recu.update(supplement)
    destination = racine / REPERTOIRE_PREFLIGHTS / f"{identifiant}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(recu, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"préflight '{identifiant}' : verdict {verdict} · cause {cause}")
    print(f"fait : {fait}")
    print(
        "reçu écrit : "
        f"{(REPERTOIRE_PREFLIGHTS / (identifiant + '.json')).as_posix()}"
    )
    return CODES_SORTIE_PREFLIGHT[verdict]


def _libelle_registre(registre: Path | None, cible: Path) -> str:
    if registre is None:
        return f"registre officiel {REGISTRE_OFFICIEL.as_posix()}"
    return f"registre isolé {cible}"


def _refus_registre_officiel(racine: Path, registre: Path) -> str | None:
    """Garde fail-closed commune : '--registre' ne vise jamais le registre officiel.

    La résolution des deux chemins couvre les liens symboliques ; le refus
    s'applique au registre officiel lui-même comme à tout descendant.
    """
    officiel = (racine / REGISTRE_OFFICIEL).resolve()
    fourni = registre.resolve()
    if fourni == officiel or officiel in fourni.parents:
        return (
            f"ECHEC option '--registre' : '{registre}' résout vers le registre "
            f"officiel '{REGISTRE_OFFICIEL.as_posix()}' ; l'option '--registre' "
            "n'accepte qu'un registre isolé, jamais le registre officiel"
        )
    return None


def enregistrer_configuration(
    racine: Path, fichier: Path, registre: Path | None = None
) -> int:
    if registre is not None:
        # Garde appliquée avant toute lecture ou écriture du chemin fourni
        refus = _refus_registre_officiel(racine, registre)
        if refus is not None:
            print(refus)
            return 1
    try:
        donnees = _charger_configuration(fichier)
    except ErreurConfiguration as erreur:
        print(f"ECHEC {erreur}")
        return 1
    if registre is None:
        cible = racine / REGISTRE_OFFICIEL
        cible.mkdir(parents=True, exist_ok=True)
    else:
        # Ciblage exclusif du registre isolé : l'officiel n'est ni lu ni écrit.
        cible = registre
        if not cible.is_dir():
            print(f"ECHEC registre isolé absent : {cible}")
            return 1
    identifiant = donnees["configuration_id"]
    destination = cible / f"{identifiant}.toml"
    if destination.exists():
        print(
            f"ECHEC champ 'configuration_id' : '{identifiant}' est déjà enregistré "
            f"dans le {_libelle_registre(registre, cible)}"
        )
        return 1
    destination.write_bytes(fichier.read_bytes())
    print(
        f"configuration '{identifiant}' enregistrée, déclarée et non mesurée, "
        f"dans le {_libelle_registre(registre, cible)}"
    )
    return 0


def _charger_registre(cible: Path) -> list[tuple[Path, dict]]:
    """Charge les entrées validées du registre, triées par identifiant."""
    entrees: list[tuple[Path, dict]] = []
    for chemin in sorted(cible.glob("*.toml")):
        donnees = _charger_configuration(chemin)
        if chemin.stem != donnees["configuration_id"]:
            raise ErreurConfiguration(
                f"champ 'configuration_id' : '{donnees['configuration_id']}' ne "
                f"correspond pas au nom du fichier de registre {chemin.name}"
            )
        entrees.append((chemin, donnees))
    return entrees


def _texte_quota(quota: dict) -> str:
    return " ".join(f"{cle}={quota[cle]}" for cle in _CHAMPS_QUOTA)


def _lignes_entree_panel(donnees: dict) -> list[str]:
    plan = donnees["plan"]
    harnais = donnees["harnais"]
    lignes = [
        f"- configuration : {donnees['configuration_id']} [DECLAREE, NON MESUREE]",
        f"  produit : {donnees['produit']['nom']} | éditeur : {donnees['produit']['editeur']}",
        (
            f"  plan : {plan['nom']} | prix : {plan['prix_montant']} {plan['prix_devise']} "
            f"| période : {plan['periode']} | source : {plan['source_url']} "
            f"| publication : {plan['date_publication']} "
            f"| consultation : {plan['date_consultation']}"
        ),
    ]
    lignes.extend(
        f"  quota {rang} : {_texte_quota(quota)}"
        for rang, quota in enumerate(donnees["quota"], start=1)
    )
    lignes.extend(
        [
            (
                f"  interface : {donnees['interface']['type']} "
                f"| version : {donnees['interface']['version']}"
            ),
            f"  modèle demandé [REQUESTED] : {donnees['modele']['demande']}",
            (
                f"  harnais : argv={harnais['argv']} "
                + (
                    f"| stdin={harnais['stdin_fichier']} "
                    if "stdin_fichier" in harnais
                    else ""
                )
                + f"| espace_de_travail={harnais['espace_de_travail']} "
                f"| delai_secondes={harnais['delai_secondes']}"
            ),
            (
                "  intervention humaine : "
                + " ; ".join(donnees["intervention_humaine"]["etapes"])
            ),
        ]
    )
    return lignes


def afficher_panel(racine: Path, registre: Path | None = None) -> int:
    if registre is None:
        cible = racine / REGISTRE_OFFICIEL
    else:
        # Garde appliquée avant toute lecture du chemin fourni
        refus = _refus_registre_officiel(racine, registre)
        if refus is not None:
            print(refus)
            return 1
        cible = registre
        if not cible.is_dir():
            print(f"ECHEC registre isolé absent : {cible}")
            return 1
    try:
        entrees = _charger_registre(cible) if cible.is_dir() else []
    except ErreurConfiguration as erreur:
        print(f"ECHEC {erreur}")
        return 1
    print(f"registre ciblé : {_libelle_registre(registre, cible)}")
    if not entrees:
        print("panel : vide (0 configuration déclarée)")
        return 0
    print(f"panel : {len(entrees)} configurations déclarées, non mesurées")
    for _, donnees in entrees:
        for ligne in _lignes_entree_panel(donnees):
            print(ligne)
    return 0


def _lignes_autorisations(donnees: dict) -> list[str]:
    """Aperçu des autorisations : faits déclarés des TOML, jamais des observations."""
    plan = donnees["plan"]
    lignes = [
        f"- configuration : {donnees['configuration_id']} [DECLAREE, NON MESUREE]",
        f"  compte concerné : {INCONNU}",
        f"  plan : {plan['nom']}",
        (
            "  authentification interactive exigée : "
            + " ; ".join(donnees["intervention_humaine"]["etapes"])
        ),
    ]
    lignes.extend(
        f"  quota engagé {rang} : {_texte_quota(quota)}"
        for rang, quota in enumerate(donnees["quota"], start=1)
    )
    lignes.append(
        f"  dépense engagée : prix_montant={plan['prix_montant']} "
        f"| prix_devise={plan['prix_devise']} | periode={plan['periode']}"
    )
    return lignes


def afficher_autorisations(racine: Path, identifiant: str | None = None) -> int:
    registre = racine / REGISTRE_OFFICIEL
    try:
        entrees = _charger_registre(registre) if registre.is_dir() else []
    except ErreurConfiguration as erreur:
        print(f"ECHEC {erreur}")
        return 1
    if identifiant is not None:
        entrees = [
            (chemin, donnees)
            for chemin, donnees in entrees
            if donnees["configuration_id"] == identifiant
        ]
        if not entrees:
            print(
                f"ECHEC option '--configuration' : '{identifiant}' absent du "
                f"registre officiel {REGISTRE_OFFICIEL.as_posix()}"
            )
            return 1
    print(
        f"autorisations : {len(entrees)} configurations déclarées, non mesurées "
        "— aperçu avant toute action distante, sans authentification, sans "
        "lecture de compte, sans inspection de facturation"
    )
    for _, donnees in entrees:
        for ligne in _lignes_autorisations(donnees):
            print(ligne)
    return 0


def _sha256_fichier(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def _charger_etat(racine: Path) -> dict:
    chemin = racine / CHEMIN_ETAT
    try:
        etat = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erreur:
        raise ErreurRestitution(f"état V1 illisible : {chemin} ({erreur})") from erreur
    if not isinstance(etat, dict) or etat.get("schema_etat") != "campagne-v1/etat-v1/1":
        raise ErreurRestitution(f"schéma d'état V1 inattendu : {chemin}")
    if not isinstance(etat.get("panel"), list):
        raise ErreurRestitution("le champ panel de l'état V1 doit être une liste")
    if not isinstance(etat.get("repertoire_recus"), str):
        raise ErreurRestitution("le champ repertoire_recus de l'état V1 doit être une chaîne")
    return etat


def _repertoire_recus(racine: Path, etat: dict) -> Path:
    return racine / _RACINE_CAMPAGNE_V1 / etat["repertoire_recus"]


def _compter_recus(repertoire: Path) -> int:
    if not repertoire.is_dir():
        raise ErreurRestitution(f"répertoire de reçus V1 absent : {repertoire}")
    return sum(1 for _ in repertoire.iterdir())


def _partitionner_recus(
    racine: Path, etat: dict
) -> tuple[list[tuple[str, dict, str]], list[tuple[str, dict, str]]]:
    """Reçus V1 valides du répertoire, partitionnés (locaux, officiels) :
    chaque élément est (chemin relatif, enveloppe, SHA-256 du fichier).

    Un reçu est officiel lorsque sa configuration vit dans le registre
    officiel versionné ; tout autre reçu reste une démonstration locale hors
    panel officiel. Tout fichier du répertoire doit être un reçu V1
    abonnement valide et chaîné ; sinon la restitution refuse fail-closed.
    """
    repertoire = _repertoire_recus(racine, etat)
    try:
        recus = _charger_recus(repertoire)
    except ErreurRecu as erreur:
        raise ErreurRestitution(f"reçu V1 local invalide : {erreur}") from erreur
    prefixe_officiel = REGISTRE_OFFICIEL.as_posix() + "/"
    locaux: list[tuple[str, dict, str]] = []
    officiels: list[tuple[str, dict, str]] = []
    for chemin, enveloppe in recus:
        element = (
            chemin.relative_to(racine).as_posix(),
            enveloppe,
            _sha256_fichier(chemin),
        )
        if enveloppe["payload"]["configuration"]["chemin"].startswith(
            prefixe_officiel
        ):
            officiels.append(element)
        else:
            locaux.append(element)
    return locaux, officiels


def _jetons_attendus(
    etat: dict, nombre_recus: int, nombre_configurations: int = 0
) -> tuple[str, str, str]:
    """Recalcule les trois jetons factuels depuis l'état, les acquisitions
    officielles et le registre. Les reçus locaux de démonstration, hors panel
    officiel, n'entrent pas dans ce décompte. La conclusion reste ABSTENTION
    tant qu'aucune acceptabilité officielle (PASS automatique plus ACCEPTABLE
    humain) n'est établie : une acquisition n'est jamais promue en mesure."""
    if etat["panel"]:
        raise ErreurRestitution(
            "le champ panel de l'état V1 doit rester vide : le panel déclaré vit "
            "dans le registre officiel versionné"
        )
    if nombre_configurations:
        jeton_panel = (
            f"panel: {nombre_configurations} configurations déclarées, non mesurées"
        )
    else:
        jeton_panel = "panel: vide"
    return jeton_panel, f"acquisitions: {nombre_recus}", "conclusion: ABSTENTION"


def _configurations_officielles(racine: Path) -> list[tuple[str, dict]]:
    """Entrées validées du registre officiel, chemins relatifs à la racine."""
    registre = racine / REGISTRE_OFFICIEL
    if not registre.is_dir():
        return []
    try:
        entrees = _charger_registre(registre)
    except ErreurConfiguration as erreur:
        raise ErreurRestitution(f"registre officiel invalide : {erreur}") from erreur
    return [
        ((REGISTRE_OFFICIEL / chemin.name).as_posix(), donnees)
        for chemin, donnees in entrees
    ]


SECTION_REGISTRE = "configuration déclarée du registre officiel"


def _empreintes_sources(
    racine: Path, etat_relatif: str, chemins_configurations: tuple[str, ...] = ()
) -> dict[str, str]:
    empreintes: dict[str, str] = {}
    for chemin, _ in SOURCES_AUTORISEES:
        empreintes[chemin] = _sha256_fichier(racine / chemin)
    for chemin in chemins_configurations:
        empreintes[chemin] = _sha256_fichier(racine / chemin)
    empreintes[etat_relatif] = _sha256_fichier(racine / etat_relatif)
    return empreintes


def _echapper(valeur: object) -> str:
    return (
        str(valeur)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _article_panel(relatif: str, sha256: str, donnees: dict) -> str:
    """Article de panel régénérable à l'identique depuis le fichier de registre."""
    plan = donnees["plan"]
    harnais = donnees["harnais"]
    quotas = "".join(
        f"<li>quota {rang} : "
        + " · ".join(f"{cle} <code>{_echapper(quota[cle])}</code>" for cle in _CHAMPS_QUOTA)
        + "</li>"
        for rang, quota in enumerate(donnees["quota"], start=1)
    )
    argv = " ".join(f"<code>{_echapper(element)}</code>" for element in harnais["argv"])
    stdin = (
        f" · stdin <code>{_echapper(harnais['stdin_fichier'])}</code>"
        if "stdin_fichier" in harnais
        else ""
    )
    etapes = " ; ".join(
        f"<code>{_echapper(etape)}</code>"
        for etape in donnees["intervention_humaine"]["etapes"]
    )
    contenu = (
        f"<p><strong>{_echapper(donnees['configuration_id'])}</strong> — entrée "
        "déclarée et non mesurée.</p>"
        f"<p>produit <code>{_echapper(donnees['produit']['nom'])}</code> · "
        f"éditeur <code>{_echapper(donnees['produit']['editeur'])}</code></p>"
        f"<p>plan <code>{_echapper(plan['nom'])}</code> · "
        f"prix <code>{_echapper(plan['prix_montant'])}</code> "
        f"<code>{_echapper(plan['prix_devise'])}</code> · "
        f"période <code>{_echapper(plan['periode'])}</code> · "
        f"source déclarée <code>{_echapper(plan['source_url'])}</code> · "
        f"publication <code>{_echapper(plan['date_publication'])}</code> · "
        f"consultation <code>{_echapper(plan['date_consultation'])}</code></p>"
        f"<ul>{quotas}</ul>"
        f"<p>interface <code>{_echapper(donnees['interface']['type'])}</code> · "
        f"version <code>{_echapper(donnees['interface']['version'])}</code></p>"
        f"<p>modèle demandé <code>REQUESTED</code> : "
        f"<code>{_echapper(donnees['modele']['demande'])}</code></p>"
        f"<p>harnais : argv {argv}{stdin} · espace de travail "
        f"<code>{_echapper(harnais['espace_de_travail'])}</code> · délai en secondes "
        f"<code>{_echapper(harnais['delai_secondes'])}</code></p>"
        f"<p>intervention humaine : {etapes}</p>"
        + _span_source(relatif, sha256, SECTION_REGISTRE)
    )
    return _article(
        "fait",
        contenu,
        f' data-configuration="{donnees["configuration_id"]}"'
        ' data-statut="declaree-non-mesuree"',
    )


def _article_autorisations(relatif: str, sha256: str, donnees: dict) -> str:
    """Article d'autorisations régénérable à l'identique depuis le registre."""
    plan = donnees["plan"]
    etapes = " ; ".join(
        f"<code>{_echapper(etape)}</code>"
        for etape in donnees["intervention_humaine"]["etapes"]
    )
    quotas = "".join(
        f"<li>quota engagé {rang} : "
        + " · ".join(f"{cle} <code>{_echapper(quota[cle])}</code>" for cle in _CHAMPS_QUOTA)
        + "</li>"
        for rang, quota in enumerate(donnees["quota"], start=1)
    )
    contenu = (
        f"<p><strong>{_echapper(donnees['configuration_id'])}</strong> — "
        "autorisations déclarées, non mesurées.</p>"
        f"<p>compte concerné : <code>{INCONNU}</code></p>"
        f"<p>plan : <code>{_echapper(plan['nom'])}</code></p>"
        f"<p>authentification interactive exigée : {etapes}</p>"
        f"<ul>{quotas}</ul>"
        f"<p>dépense engagée : prix_montant <code>{_echapper(plan['prix_montant'])}</code> · "
        f"prix_devise <code>{_echapper(plan['prix_devise'])}</code> · "
        f"periode <code>{_echapper(plan['periode'])}</code></p>"
        + _span_source(relatif, sha256, SECTION_REGISTRE)
    )
    return _article(
        "fait",
        contenu,
        f' data-autorisation="{donnees["configuration_id"]}"',
    )


SECTION_RECU_LOCAL = "reçu V1 local versionné, hors panel officiel"


def _article_acquisition_locale(relatif: str, sha_fichier: str, enveloppe: dict) -> str:
    """Article régénérable à l'identique depuis le fichier de reçu V1 local."""
    charge = enveloppe["payload"]
    execution = charge["execution"]
    if execution["etat"] == "OBSERVED":
        lignes_execution = (
            f"<p>exécution observée : code de sortie "
            f"<code>{_echapper(execution['code_sortie'])}</code> · latence "
            f"<code>{_echapper(execution['latence_ms'])}</code> ms</p>"
            f"<p>sortie capturée : <code>{_echapper(execution['sortie']['stdout'])}"
            "</code></p>"
        )
    else:
        lignes_execution = (
            f"<p>incident nommé : <code>{_echapper(execution['incident'])}</code> — "
            f"{_echapper(execution['fait'])}</p>"
        )
    predecesseur = charge["predecesseur_adresse_contenu"]
    contenu = (
        f"<p><strong>{_echapper(charge['configuration']['identifiant'])}</strong> — "
        "démonstration locale du harnais, hors panel officiel. Aucun modèle, aucun "
        "fournisseur, aucun compte et aucun réseau.</p>"
        f"<p>reçu <code>{relatif}</code> · SHA-256 du fichier "
        f"<code>{sha_fichier}</code></p>"
        f"<p>profil de mesure <code>{_echapper(charge['measurement_profile'])}</code> · "
        f"créneau <code>{_echapper(charge['creneau'])}</code></p>"
        f"<p>adresse de contenu <code>{enveloppe['content_address']['sha256']}</code> · "
        f"prédécesseur <code>{_echapper(predecesseur) if predecesseur is not None else 'null'}"
        "</code></p>"
        f"<p>configuration locale <code>{_echapper(charge['configuration']['chemin'])}"
        f"</code> · SHA-256 <code>{charge['configuration']['sha256']}</code></p>"
        f"<p>stimulus <code>{_echapper(charge['stimulus']['chemin'])}</code> · "
        f"SHA-256 <code>{charge['stimulus']['sha256']}</code></p>"
        + lignes_execution
        + f"<p>quota observé : <code>{_echapper(charge['quota_observe'])}</code> · "
        f"provenance servie : <code>{_echapper(charge['provenance_servie'])}</code></p>"
        + _span_source(relatif, sha_fichier, SECTION_RECU_LOCAL)
    )
    return _article(
        "fait",
        contenu,
        f' data-acquisition-locale="{charge["configuration"]["identifiant"]}"',
    )


SECTION_AUTORISATION_ACQUISITION = "autorisation d'acquisition D-V1-04 versionnée"
SECTION_RECU_OFFICIEL = "reçu V1 d'acquisition officielle versionné"


def _charger_autorisation_restitution(
    racine: Path,
) -> tuple[str, dict, str] | None:
    """Autorisation D-V1-04 pour le rendu : (chemin relatif, données,
    SHA-256 du fichier), ou None lorsque l'artefact n'existe pas."""
    chemin = racine / CHEMIN_AUTORISATION_ACQUISITION
    if not os.path.lexists(chemin):
        return None
    try:
        donnees = _charger_autorisation_acquisition(racine)
    except ErreurAutorisation as erreur:
        raise ErreurRestitution(
            f"autorisation d'acquisition invalide : {erreur}"
        ) from erreur
    return (
        CHEMIN_AUTORISATION_ACQUISITION.as_posix(),
        donnees,
        _sha256_fichier(chemin),
    )


def _article_autorisation_acquisition(
    relatif: str, sha_fichier: str, donnees: dict
) -> str:
    """Article régénérable à l'identique depuis l'artefact d'autorisation."""
    commentaire = donnees["commentaire"]
    portee = donnees["portee"]
    creneaux = "".join(
        f"<li><code>{_echapper(creneau['acquisition_id'])}</code> pour "
        f"<code>{_echapper(creneau['configuration_id'])}</code></li>"
        for creneau in portee["acquisitions"]
    )
    contenu = (
        f"<p><strong>{_echapper(donnees['autorite'])}</strong> — autorité "
        "propriétaire d'acquisition, distincte du verrou : le verrou versionné "
        "conserve inchangé son champ d'exécution <code>NOT_GRANTED</code>, et "
        "cet artefact séparé porte seul le GO.</p>"
        f"<p>jeton propriétaire : <code>{_echapper(donnees['jeton'])}</code> · "
        f"auteur <code>{_echapper(commentaire['auteur'])}</code> · association "
        f"<code>{_echapper(commentaire['association'])}</code> · date "
        f"<code>{_echapper(commentaire['date'])}</code></p>"
        f"<p>SHA-256 du corps du commentaire "
        f"<code>{_echapper(commentaire['sha256_corps'])}</code></p>"
        f"<p>verrou référencé <code>{_echapper(donnees['verrou']['chemin'])}"
        f"</code> · SHA-256 <code>{_echapper(donnees['verrou']['sha256'])}"
        "</code></p>"
        f"<p>stimulus référencé <code>{_echapper(donnees['stimulus']['chemin'])}"
        f"</code> · SHA-256 <code>{_echapper(donnees['stimulus']['sha256'])}"
        "</code></p>"
        f"<p>portée exacte : deux créneaux</p><ul>{creneaux}</ul>"
        f"<p>appels fournisseur au maximum : "
        f"<code>{_echapper(portee['appels_fournisseur_max'])}</code> · appels "
        f"par créneau : <code>{_echapper(portee['appels_par_creneau'])}</code> · "
        "quota : abonnements existants seuls · dépense incrémentale : "
        f"<code>{_echapper(portee['depense_incrementale'])}</code> · reprises "
        f"automatiques : <code>{_echapper(portee['reprises_automatiques'])}"
        "</code> · reprises manuelles : "
        f"<code>{_echapper(portee['reprises_manuelles'])}</code> · fallback : "
        f"<code>{_echapper(portee['fallback'])}</code></p>"
        + _span_source(relatif, sha_fichier, SECTION_AUTORISATION_ACQUISITION)
    )
    return _article(
        "fait",
        contenu,
        f' data-autorisation-acquisition="{donnees["autorite"]}"',
    )


def _article_acquisition_officielle(
    relatif: str, sha_fichier: str, enveloppe: dict
) -> str:
    """Article régénérable à l'identique depuis un reçu officiel D-V1-04."""
    charge = enveloppe["payload"]
    execution = charge["execution"]
    if execution["etat"] == "OBSERVED":
        lignes_execution = (
            f"<p>exécution observée : code de sortie "
            f"<code>{_echapper(execution['code_sortie'])}</code> · latence "
            f"monotone <code>{_echapper(execution['latence_ms'])}</code> ms</p>"
            f"<p>sortie capturée : <code>{_echapper(execution['sortie']['stdout'])}"
            "</code></p>"
        )
    else:
        preuve = (
            f"<p>preuve attribuable : "
            f"<code>{_echapper(execution['preuve_attribuable'])}</code></p>"
            if "preuve_attribuable" in execution
            else ""
        )
        lignes_execution = (
            f"<p>incident nommé : <code>{_echapper(execution['incident'])}</code> — "
            f"{_echapper(execution['fait'])}</p>" + preuve
        )
    predecesseur = charge["predecesseur_adresse_contenu"]
    contenu = (
        f"<p><strong>{_echapper(charge['configuration']['identifiant'])}</strong> — "
        "acquisition officielle exécutée une seule fois sous D-V1-04, sans "
        "retry ni fallback. Ce reçu restitue une exécution et ses faits ; il "
        "n'établit aucune acceptabilité officielle et aucune conclusion.</p>"
        f"<p>reçu <code>{relatif}</code> · SHA-256 du fichier "
        f"<code>{sha_fichier}</code></p>"
        f"<p>profil de mesure <code>{_echapper(charge['measurement_profile'])}</code> · "
        f"créneau <code>{_echapper(charge['creneau'])}</code></p>"
        f"<p>adresse de contenu <code>{enveloppe['content_address']['sha256']}</code> · "
        f"prédécesseur <code>{_echapper(predecesseur) if predecesseur is not None else 'null'}"
        "</code></p>"
        f"<p>configuration verrouillée <code>{_echapper(charge['configuration']['chemin'])}"
        f"</code> · SHA-256 <code>{charge['configuration']['sha256']}</code></p>"
        f"<p>stimulus <code>{_echapper(charge['stimulus']['chemin'])}</code> · "
        f"SHA-256 <code>{charge['stimulus']['sha256']}</code></p>"
        f"<p>requête expurgée : <code>{_echapper(' '.join(charge['requete']['argv_resolu']))}"
        "</code></p>"
        + lignes_execution
        + f"<p>quota observé : <code>{_echapper(charge['quota_observe'])}</code> · "
        f"identité servie : <code>{_echapper(charge['provenance_servie'])}</code></p>"
        + _span_source(relatif, sha_fichier, SECTION_RECU_OFFICIEL)
    )
    return _article(
        "fait",
        contenu,
        f' data-acquisition-officielle="{charge["configuration"]["identifiant"]}"',
    )


SECTION_QUALIFICATION = "reçu de qualification du harnais V1"
VERDICTS_QUALIFICATION = ("PASS", "FAIL", "HARNESS_ERROR")


def _exiger_table_qualification(nom: str, valeur: object, cles: set[str]) -> dict:
    if not isinstance(valeur, dict) or set(valeur) != cles:
        raise ErreurRestitution(
            f"champ '{nom}' du reçu de qualification : clés exactes "
            f"{sorted(cles)} attendues"
        )
    return valeur


def _charger_recu_qualification(racine: Path) -> tuple[str, dict, str] | None:
    """Reçu de qualification validé : (chemin relatif, reçu, SHA-256 du fichier)."""
    chemin = racine / CHEMIN_RECU_QUALIFICATION
    if not chemin.is_file():
        return None
    try:
        recu = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurRestitution(
            f"reçu de qualification illisible : {chemin} ({erreur})"
        ) from erreur
    if not isinstance(recu, dict) or recu.get("schema_version") != SCHEMA_RECU_QUALIFICATION:
        raise ErreurRestitution(
            f"schéma de reçu de qualification inattendu : {chemin}"
        )
    if recu.get("verdict") not in VERDICTS_QUALIFICATION:
        raise ErreurRestitution(
            "verdict de qualification hors vocabulaire "
            f"({' | '.join(VERDICTS_QUALIFICATION)}) : {recu.get('verdict')!r}"
        )
    for champ in ("date_qualification", "commande_publique", "commande_suite"):
        if not isinstance(recu.get(champ), str) or not recu[champ].strip():
            raise ErreurRestitution(
                f"champ '{champ}' du reçu de qualification : chaîne non vide attendue"
            )
    # Chaque valeur imbriquée servie par la restitution est validée fail-closed
    # contre les entrées figées ; toute divergence refuse le reçu entier
    if recu["commande_publique"] != COMMANDE_QUALIFICATION:
        raise ErreurRestitution(
            f"champ 'commande_publique' : '{COMMANDE_QUALIFICATION}' attendu"
        )
    if recu["commande_suite"] != COMMANDE_SUITE_QUALIFICATION:
        raise ErreurRestitution(
            f"champ 'commande_suite' : '{COMMANDE_SUITE_QUALIFICATION}' attendu"
        )
    interpreteur = _exiger_table_qualification(
        "interpreteur", recu.get("interpreteur"), {"pin", "observe"}
    )
    if interpreteur["pin"] != PIN_INTERPRETEUR:
        raise ErreurRestitution(
            f"champ 'interpreteur.pin' : '{PIN_INTERPRETEUR}' attendu, le pin "
            "n'est pas affaibli"
        )
    observe = interpreteur["observe"]
    if not isinstance(observe, str) or not observe.startswith("CPython 3.12."):
        raise ErreurRestitution(
            "champ 'interpreteur.observe' : identité exacte CPython 3.12 "
            "observée attendue"
        )
    validateur = _exiger_table_qualification(
        "validateur", recu.get("validateur"), {"chemin", "sha256"}
    )
    if validateur["chemin"] != CHEMIN_VALIDATEUR:
        raise ErreurRestitution(
            f"champ 'validateur.chemin' : '{CHEMIN_VALIDATEUR}' attendu"
        )
    if validateur["sha256"] != EMPREINTE_VALIDATEUR_APPROUVEE:
        raise ErreurRestitution(
            "champ 'validateur.sha256' : empreinte qualifiée "
            f"{EMPREINTE_VALIDATEUR_APPROUVEE} attendue"
        )
    temoins = _exiger_table_qualification(
        "temoins",
        recu.get("temoins"),
        {"source", "sha256", "cardinalite", "noms"},
    )
    if temoins["source"] != CHEMIN_TEMOINS:
        raise ErreurRestitution(
            f"champ 'temoins.source' : '{CHEMIN_TEMOINS}' attendu"
        )
    if temoins["sha256"] != EMPREINTE_TEMOINS_APPROUVEE:
        raise ErreurRestitution(
            "champ 'temoins.sha256' : empreinte approuvée "
            f"{EMPREINTE_TEMOINS_APPROUVEE} attendue"
        )
    if temoins["cardinalite"] != CARDINALITE_TEMOINS:
        raise ErreurRestitution(
            f"champ 'temoins.cardinalite' : {CARDINALITE_TEMOINS} attendu"
        )
    if temoins["noms"] != list(NOMS_TEMOINS):
        raise ErreurRestitution(
            "champ 'temoins.noms' : les seize témoins approuvés attendus dans "
            "l'ordre du document versionné"
        )
    if recu.get("decisions_figees") != DECISIONS_FIGEES_V1:
        raise ErreurRestitution(
            "champ 'decisions_figees' : exactement les entrées figées "
            "route_evaluation_v0 USE_MANUAL et plateforme_specifique "
            "STOP_SPECIFIC_PLATFORM attendues"
        )
    return (
        CHEMIN_RECU_QUALIFICATION.as_posix(),
        recu,
        _sha256_fichier(chemin),
    )


def _article_qualification(relatif: str, sha_fichier: str, recu: dict) -> str:
    """Article régénérable à l'identique depuis le reçu de qualification."""
    interpreteur = recu["interpreteur"]
    validateur = recu["validateur"]
    temoins = recu["temoins"]
    decisions = recu["decisions_figees"]
    contenu = (
        "<p><strong>Qualification du harnais V1</strong> — l'instrument est "
        "requalifié sur les témoins approuvés du paquet, sans comparaison "
        "d'outillage et sans appel distant.</p>"
        f"<p>date de qualification <code>{_echapper(recu['date_qualification'])}"
        f"</code> · verdict <code>{_echapper(recu['verdict'])}</code></p>"
        f"<p>commande exacte <code>{_echapper(recu['commande_publique'])}</code></p>"
        f"<p>suite de tests <code>{_echapper(recu['commande_suite'])}</code></p>"
        f"<p>interpréteur : pin <code>{_echapper(interpreteur.get('pin'))}</code> · "
        f"observé <code>{_echapper(interpreteur.get('observe'))}</code></p>"
        f"<p>validateur <code>{_echapper(validateur.get('chemin'))}</code> · "
        f"SHA-256 <code>{_echapper(validateur.get('sha256'))}</code></p>"
        f"<p>témoins approuvés : <code>{_echapper(temoins.get('cardinalite'))}"
        f"</code> · source <code>{_echapper(temoins.get('source'))}</code> · "
        f"SHA-256 <code>{_echapper(temoins.get('sha256'))}</code></p>"
        "<p>décisions figées en entrée : route d'évaluation V0 "
        f"<code>{_echapper(decisions.get('route_evaluation_v0'))}</code> · "
        "plateforme spécifique "
        f"<code>{_echapper(decisions.get('plateforme_specifique'))}</code></p>"
        + _span_source(relatif, sha_fichier, SECTION_QUALIFICATION)
    )
    return _article(
        "fait",
        contenu,
        f' data-qualification-harnais="{recu["verdict"]}"',
    )


SECTION_PREFLIGHT = "reçu de préflight V1 versionné"
_MOTIF_DATE_PREFLIGHT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_CLES_RECU_PREFLIGHT = {
    "schema_version",
    "configuration_id",
    "date_preflight",
    "autorite_preflight",
    "adaptateur",
    "commande_publique",
    "sondes",
    "interface",
    "authentification",
    "plan",
    "modele",
    "effort",
    "quota",
    "verdict",
    "cause",
    "fait",
}
_CLES_TABLES_PREFLIGHT = {
    "interface": {"type", "client", "version_observee"},
    "authentification": {"observee"},
    "plan": {"declare", "observe"},
    "modele": {"demande", "expose"},
    "effort": {"demande", "expose"},
    "quota": {"observe", "consommation_preflight"},
}
# Reçu opencodex : les quatre objets distincts s'ajoutent aux clés communes
# (authentification est déjà une table commune)
_CLES_RECU_PREFLIGHT_OPENCODEX = _CLES_RECU_PREFLIGHT | {
    "catalogue_declare",
    "proxy_opencodex",
    "identite_reellement_servie",
}
# Reçu agy : l'identité réellement servie reste un objet distinct explicite,
# jamais amputable ni déduit du catalogue ou du quota
_CLES_RECU_PREFLIGHT_ANTIGRAVITY = _CLES_RECU_PREFLIGHT | {
    "identite_reellement_servie",
}
_CLES_QUOTA_OBSERVE_ANTIGRAVITY = {"source", "fenetres"}
_CLES_FENETRE_QUOTA_ANTIGRAVITY = {"pourcentage_restant", "reset"}
_CLES_CATALOGUE_DECLARE_OPENCODEX = {
    "fournisseur",
    "adaptateur",
    "endpoint",
    "entree_exacte_presente",
    "effort_high_present",
}
_CLES_PROXY_OPENCODEX = {"version", "ready", "status"}
_CLES_QUOTA_OBSERVE_OPENCODEX = {"source", "fenetres"}
_CLES_FENETRE_QUOTA_OPENCODEX = {"pourcentage", "reset"}
# Causes admises par verdict de route ; READY ne porte aucune cause
_CAUSES_PAR_VERDICT_PREFLIGHT = {
    "READY": (None,),
    "HOLD": CAUSES_PREFLIGHT_HOLD,
    "UNAVAILABLE": CAUSES_PREFLIGHT_UNAVAILABLE,
}
# Champs dont READY exige l'observation : aucun ne peut rester INCONNU ni
# NON_DEFINI quand le verdict affirme une route prête
_CHAMPS_OBSERVES_READY = (
    ("authentification.observee", "authentification", "observee"),
    ("plan.observe", "plan", "observe"),
    ("modele.expose", "modele", "expose"),
    ("effort.expose", "effort", "expose"),
    ("quota.observe", "quota", "observe"),
)


def _projection_login_codex_valide(projection: object) -> bool:
    """Forme exacte de la projection de connexion codex : connecte, methode"""
    return (
        isinstance(projection, dict)
        and set(projection) == set(CHAMPS_PROJECTION_LOGIN_CODEX)
        and isinstance(projection["connecte"], bool)
        and isinstance(projection["methode"], str)
        and bool(projection["methode"].strip())
    )


def _projection_statut_cursor_valide(projection: object) -> bool:
    """Forme exacte de la projection de statut agent : status, isAuthenticated"""
    return (
        isinstance(projection, dict)
        and set(projection) == set(CHAMPS_PROJECTION_STATUT_CURSOR)
        and isinstance(projection["status"], str)
        and bool(projection["status"].strip())
        and isinstance(projection["isAuthenticated"], bool)
    )


def _projection_compte_opencodex_valide(projection: object) -> bool:
    """Forme exacte de la projection de compte opencodex : fournisseur zai,
    type non vide, présence de clé booléenne"""
    return (
        isinstance(projection, dict)
        and set(projection) == set(CHAMPS_PROJECTION_COMPTE_OPENCODEX)
        and projection["fournisseur"] == FOURNISSEUR_ZAI
        and isinstance(projection["type"], str)
        and bool(projection["type"].strip())
        and isinstance(projection["cle_active"], bool)
    )


def _pourcentage_ou_reset_valide(valeur: object) -> bool:
    """INCONNU ou nombre observé, jamais une valeur reconstruite"""
    return valeur == INCONNU or (
        not isinstance(valeur, bool) and isinstance(valeur, (int, float))
    )


# Liste blanche des sondes par adaptateur : une sonde d'un adaptateur ne
# vaut jamais pour un autre
_SONDES_PAR_ADAPTATEUR = {
    ADAPTATEUR_CLAUDE: SONDES_AUTORISEES_PREFLIGHT,
    ADAPTATEUR_CODEX: SONDES_AUTORISEES_PREFLIGHT_CODEX,
    ADAPTATEUR_GROK: SONDES_AUTORISEES_PREFLIGHT_GROK,
    ADAPTATEUR_CURSOR: SONDES_AUTORISEES_PREFLIGHT_CURSOR,
    ADAPTATEUR_OPENCODEX: SONDES_AUTORISEES_PREFLIGHT_OPENCODEX,
    ADAPTATEUR_ANTIGRAVITY: SONDES_AUTORISEES_PREFLIGHT_ANTIGRAVITY,
}
# Champs de projection par sonde à projection : la restitution ne rend que
# ces champs fermés, jamais une sortie brute
_CHAMPS_PROJECTION_PAR_SONDE = {
    SONDE_AUTH_CLAUDE: CHAMPS_PROJECTION_AUTH,
    SONDE_LOGIN_CODEX: CHAMPS_PROJECTION_LOGIN_CODEX,
    SONDE_CATALOGUE_CODEX: CHAMPS_PROJECTION_CATALOGUE_CODEX,
    SONDE_VERSION_GROK: CHAMPS_PROJECTION_VERSION_GROK,
    SONDE_AIDE_GROK: CHAMPS_PROJECTION_AIDE_GROK,
    SONDE_CATALOGUE_GROK: CHAMPS_PROJECTION_CATALOGUE_GROK,
    SONDE_VERSION_CURSOR: CHAMPS_PROJECTION_VERSION_CURSOR,
    SONDE_AIDE_CURSOR: CHAMPS_PROJECTION_AIDE_CURSOR,
    SONDE_STATUT_CURSOR: CHAMPS_PROJECTION_STATUT_CURSOR,
    SONDE_COMPTE_CURSOR: CHAMPS_PROJECTION_COMPTE_CURSOR,
    SONDE_CATALOGUE_CURSOR: CHAMPS_PROJECTION_CATALOGUE_CURSOR,
    SONDE_VERSION_OPENCODEX: CHAMPS_PROJECTION_VERSION_OPENCODEX,
    SONDE_READY_OPENCODEX: CHAMPS_PROJECTION_READY_OPENCODEX,
    SONDE_FOURNISSEUR_OPENCODEX: CHAMPS_PROJECTION_FOURNISSEUR_OPENCODEX,
    SONDE_CATALOGUE_OPENCODEX: CHAMPS_PROJECTION_CATALOGUE_OPENCODEX,
    SONDE_COMPTE_OPENCODEX: CHAMPS_PROJECTION_COMPTE_OPENCODEX,
    SONDE_QUOTA_OPENCODEX: CHAMPS_PROJECTION_QUOTA_OPENCODEX,
    SONDE_VERSION_ANTIGRAVITY: CHAMPS_PROJECTION_VERSION_ANTIGRAVITY,
    SONDE_CATALOGUE_ANTIGRAVITY: CHAMPS_PROJECTION_CATALOGUE_ANTIGRAVITY,
    SONDE_USAGE_ANTIGRAVITY: CHAMPS_PROJECTION_USAGE_ANTIGRAVITY,
}


def _exiger_sonde_autorisee(nom: str, commande: object, adaptateur: str) -> None:
    """Liste blanche exacte par adaptateur : toute autre forme est refusée,
    notamment -p, --print, --model, prompt positionnel, --continue,
    --resume, --fork-session, --dangerously-skip-permissions, exec, review,
    apply et resume"""
    if not isinstance(commande, str) or tuple(commande.split()) not in (
        _SONDES_PAR_ADAPTATEUR[adaptateur]
    ):
        raise ErreurRestitution(
            f"champ '{nom}' : sonde hors liste blanche de l'adaptateur "
            f"'{adaptateur}' refusée ({commande!r})"
        )


def _valider_recu_preflight(nom_fichier: str, recu: object) -> dict:
    # Le jeu de clés dépend de l'adaptateur : les reçus opencodex et agy
    # portent en plus leurs objets distincts, jamais amputables
    adaptateur_declare = recu.get("adaptateur") if isinstance(recu, dict) else None
    if adaptateur_declare == ADAPTATEUR_OPENCODEX:
        cles_attendues = _CLES_RECU_PREFLIGHT_OPENCODEX
    elif adaptateur_declare == ADAPTATEUR_ANTIGRAVITY:
        cles_attendues = _CLES_RECU_PREFLIGHT_ANTIGRAVITY
    else:
        cles_attendues = _CLES_RECU_PREFLIGHT
    if not isinstance(recu, dict) or set(recu) != cles_attendues:
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : clés exactes "
            f"{sorted(cles_attendues)} attendues"
        )
    if recu["schema_version"] != SCHEMA_RECU_PREFLIGHT:
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : schema_version "
            f"'{SCHEMA_RECU_PREFLIGHT}' attendu"
        )
    identifiant = recu["configuration_id"]
    if not isinstance(identifiant, str) or not _MOTIF_SLUG.match(identifiant):
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : configuration_id slug attendu"
        )
    if nom_fichier != f"{identifiant}.json":
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : nom de fichier divergent de "
            f"la configuration '{identifiant}'"
        )
    if not isinstance(recu["date_preflight"], str) or not _MOTIF_DATE_PREFLIGHT.match(
        recu["date_preflight"]
    ):
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : date UTC 'AAAA-MM-JJTHH:MM:SSZ' "
            "attendue"
        )
    if recu["autorite_preflight"] != AUTORITE_PREFLIGHT:
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : autorité unique "
            f"'{AUTORITE_PREFLIGHT}' attendue"
        )
    adaptateur = recu["adaptateur"]
    if adaptateur not in _SONDES_PAR_ADAPTATEUR:
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : adaptateur "
            f"'{ADAPTATEUR_CLAUDE}', '{ADAPTATEUR_CODEX}', "
            f"'{ADAPTATEUR_GROK}', '{ADAPTATEUR_CURSOR}', "
            f"'{ADAPTATEUR_OPENCODEX}' ou '{ADAPTATEUR_ANTIGRAVITY}' attendu"
        )
    for champ in ("commande_publique", "fait"):
        if not isinstance(recu[champ], str) or not recu[champ].strip():
            raise ErreurRestitution(
                f"reçu de préflight '{nom_fichier}' : champ '{champ}' non vide "
                "attendu"
            )
    verdict = recu["verdict"]
    if verdict not in _CAUSES_PAR_VERDICT_PREFLIGHT:
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : verdict '{verdict}' hors "
            "vocabulaire (READY | HOLD | UNAVAILABLE)"
        )
    if recu["cause"] not in _CAUSES_PAR_VERDICT_PREFLIGHT[verdict]:
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : cause '{recu['cause']}' "
            f"incohérente avec le verdict '{verdict}'"
        )
    if not isinstance(recu["sondes"], list):
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : liste de sondes attendue"
        )
    for rang, sonde in enumerate(recu["sondes"], start=1):
        if not isinstance(sonde, dict):
            raise ErreurRestitution(
                f"reçu de préflight '{nom_fichier}' : sonde {rang} : table "
                "attendue"
            )
        _exiger_sonde_autorisee(
            f"sondes[{rang}].commande", sonde.get("commande"), adaptateur
        )
        if isinstance(sonde.get("code_sortie"), bool) or not isinstance(
            sonde.get("code_sortie"), int
        ):
            raise ErreurRestitution(
                f"reçu de préflight '{nom_fichier}' : sonde {rang} sans code de "
                "sortie entier"
            )
        commande_sonde = tuple(sonde["commande"].split())
        if commande_sonde in _CHAMPS_PROJECTION_PAR_SONDE:
            # Ces sondes ne portent qu'une projection, jamais la sortie brute
            if set(sonde) != {"commande", "code_sortie", "projection"}:
                raise ErreurRestitution(
                    f"reçu de préflight '{nom_fichier}' : sonde {rang} aux clés "
                    "exactes commande, code_sortie, projection attendue"
                )
            projection = sonde["projection"]
            if commande_sonde == SONDE_AUTH_CLAUDE:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection) != set(CHAMPS_PROJECTION_AUTH)
                    or not isinstance(projection["loggedIn"], bool)
                    or any(
                        not isinstance(projection[champ], str)
                        or not projection[champ].strip()
                        for champ in CHAMPS_PROJECTION_AUTH[1:]
                    )
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou aux quatre champs exacts "
                        f"{sorted(CHAMPS_PROJECTION_AUTH)} attendue"
                    )
            elif commande_sonde == SONDE_LOGIN_CODEX:
                if projection != INCONNU and not _projection_login_codex_valide(
                    projection
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou aux deux champs exacts "
                        f"{sorted(CHAMPS_PROJECTION_LOGIN_CODEX)} attendue"
                    )
            elif commande_sonde == SONDE_CATALOGUE_CODEX:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection) != set(CHAMPS_PROJECTION_CATALOGUE_CODEX)
                    or not isinstance(projection["modele_demande_present"], bool)
                    or not isinstance(projection["efforts_annonces"], list)
                    or any(
                        not isinstance(effort, str) or not effort.strip()
                        for effort in projection["efforts_annonces"]
                    )
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou aux deux champs exacts "
                        f"{sorted(CHAMPS_PROJECTION_CATALOGUE_CODEX)} attendue"
                    )
            elif commande_sonde == SONDE_VERSION_GROK:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection) != set(CHAMPS_PROJECTION_VERSION_GROK)
                    or not isinstance(projection["version"], str)
                    or not projection["version"].strip()
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou au champ exact "
                        f"{sorted(CHAMPS_PROJECTION_VERSION_GROK)} attendue"
                    )
            elif commande_sonde == SONDE_AIDE_GROK:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection) != set(CHAMPS_PROJECTION_AIDE_GROK)
                    or any(
                        not isinstance(projection[champ], bool)
                        for champ in CHAMPS_PROJECTION_AIDE_GROK
                    )
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou aux deux champs exacts "
                        f"{sorted(CHAMPS_PROJECTION_AIDE_GROK)} attendue"
                    )
            elif commande_sonde == SONDE_VERSION_CURSOR:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection) != set(CHAMPS_PROJECTION_VERSION_CURSOR)
                    or not isinstance(projection["version"], str)
                    or not projection["version"].strip()
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou au champ exact "
                        f"{sorted(CHAMPS_PROJECTION_VERSION_CURSOR)} attendue"
                    )
            elif commande_sonde == SONDE_AIDE_CURSOR:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection) != set(CHAMPS_PROJECTION_AIDE_CURSOR)
                    or any(
                        not isinstance(projection[champ], bool)
                        for champ in CHAMPS_PROJECTION_AIDE_CURSOR
                    )
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou aux deux champs exacts "
                        f"{sorted(CHAMPS_PROJECTION_AIDE_CURSOR)} attendue"
                    )
            elif commande_sonde == SONDE_STATUT_CURSOR:
                if projection != INCONNU and not _projection_statut_cursor_valide(
                    projection
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou aux deux champs exacts "
                        f"{sorted(CHAMPS_PROJECTION_STATUT_CURSOR)} attendue"
                    )
            elif commande_sonde == SONDE_COMPTE_CURSOR:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection) != set(CHAMPS_PROJECTION_COMPTE_CURSOR)
                    or any(
                        not isinstance(projection[champ], str)
                        or not projection[champ].strip()
                        for champ in CHAMPS_PROJECTION_COMPTE_CURSOR
                    )
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou aux deux champs exacts "
                        f"{sorted(CHAMPS_PROJECTION_COMPTE_CURSOR)} attendue"
                    )
            elif commande_sonde == SONDE_CATALOGUE_CURSOR:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection) != set(CHAMPS_PROJECTION_CATALOGUE_CURSOR)
                    or not isinstance(projection["cible_presente"], bool)
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou au champ exact "
                        f"{sorted(CHAMPS_PROJECTION_CATALOGUE_CURSOR)} attendue"
                    )
            elif commande_sonde == SONDE_VERSION_OPENCODEX:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection) != set(CHAMPS_PROJECTION_VERSION_OPENCODEX)
                    or not isinstance(projection["version"], str)
                    or not projection["version"].strip()
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou au champ exact "
                        f"{sorted(CHAMPS_PROJECTION_VERSION_OPENCODEX)} attendue"
                    )
            elif commande_sonde == SONDE_READY_OPENCODEX:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection) != set(CHAMPS_PROJECTION_READY_OPENCODEX)
                    or not isinstance(projection["ready"], bool)
                    or projection["status"] not in STATUTS_READY_OPENCODEX
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou aux deux champs exacts "
                        f"{sorted(CHAMPS_PROJECTION_READY_OPENCODEX)} attendue"
                    )
            elif commande_sonde == SONDE_FOURNISSEUR_OPENCODEX:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection)
                    != set(CHAMPS_PROJECTION_FOURNISSEUR_OPENCODEX)
                    or any(
                        not isinstance(projection[champ], str)
                        or not projection[champ].strip()
                        for champ in ("nom", "adaptateur", "endpoint")
                    )
                    or not isinstance(projection["modele_defaut"], str)
                    or not projection["modele_defaut"].strip()
                    or not isinstance(projection["desactive"], bool)
                    or not isinstance(projection["modele_demande_present"], bool)
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou aux six champs exacts "
                        f"{sorted(CHAMPS_PROJECTION_FOURNISSEUR_OPENCODEX)} "
                        "attendue"
                    )
            elif commande_sonde == SONDE_CATALOGUE_OPENCODEX:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection)
                    != set(CHAMPS_PROJECTION_CATALOGUE_OPENCODEX)
                    or not isinstance(projection["entree_presente"], bool)
                    or not all(
                        projection[champ] == INCONNU
                        or isinstance(projection[champ], bool)
                        for champ in ("desactivee", "effort_high_present")
                    )
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou aux trois champs exacts "
                        f"{sorted(CHAMPS_PROJECTION_CATALOGUE_OPENCODEX)} "
                        "attendue"
                    )
            elif commande_sonde == SONDE_COMPTE_OPENCODEX:
                if projection != INCONNU and not _projection_compte_opencodex_valide(
                    projection
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou aux trois champs exacts "
                        f"{sorted(CHAMPS_PROJECTION_COMPTE_OPENCODEX)} attendue"
                    )
            elif commande_sonde == SONDE_QUOTA_OPENCODEX:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection) != set(CHAMPS_PROJECTION_QUOTA_OPENCODEX)
                    or not isinstance(projection["rapport_zai_present"], bool)
                    or not (
                        projection["source"] == INCONNU
                        or (
                            isinstance(projection["source"], str)
                            and projection["source"].strip()
                        )
                    )
                    or not isinstance(projection["fenetres_reconnues"], list)
                    or any(
                        fenetre not in NOMS_FENETRES_QUOTA_ZAI
                        for fenetre in projection["fenetres_reconnues"]
                    )
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou aux trois champs exacts "
                        f"{sorted(CHAMPS_PROJECTION_QUOTA_OPENCODEX)} attendue"
                    )
            elif commande_sonde == SONDE_VERSION_ANTIGRAVITY:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection)
                    != set(CHAMPS_PROJECTION_VERSION_ANTIGRAVITY)
                    or not isinstance(projection["version"], str)
                    or not projection["version"].strip()
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou au champ exact "
                        f"{sorted(CHAMPS_PROJECTION_VERSION_ANTIGRAVITY)} "
                        "attendue"
                    )
            elif commande_sonde == SONDE_CATALOGUE_ANTIGRAVITY:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection)
                    != set(CHAMPS_PROJECTION_CATALOGUE_ANTIGRAVITY)
                    or not isinstance(projection["entree_exacte_presente"], bool)
                    or not (
                        projection["libelle_concordant"] == INCONNU
                        or isinstance(projection["libelle_concordant"], bool)
                    )
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou aux deux champs exacts "
                        f"{sorted(CHAMPS_PROJECTION_CATALOGUE_ANTIGRAVITY)} "
                        "attendue"
                    )
            elif commande_sonde == SONDE_USAGE_ANTIGRAVITY:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection) != set(CHAMPS_PROJECTION_USAGE_ANTIGRAVITY)
                    or not isinstance(
                        projection["categorie_gemini_presente"], bool
                    )
                    or not isinstance(projection["fenetres_reconnues"], list)
                    or any(
                        fenetre not in NOMS_FENETRES_USAGE_ANTIGRAVITY
                        for fenetre in projection["fenetres_reconnues"]
                    )
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou aux deux champs exacts "
                        f"{sorted(CHAMPS_PROJECTION_USAGE_ANTIGRAVITY)} "
                        "attendue"
                    )
            else:
                if projection != INCONNU and (
                    not isinstance(projection, dict)
                    or set(projection) != set(CHAMPS_PROJECTION_CATALOGUE_GROK)
                    or not isinstance(projection["modele_demande_present"], bool)
                ):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} : "
                        "projection 'INCONNU' ou au champ exact "
                        f"{sorted(CHAMPS_PROJECTION_CATALOGUE_GROK)} attendue"
                    )
        else:
            if set(sonde) != {
                "commande",
                "code_sortie",
                "stdout_expurge",
                "stderr_expurge",
            }:
                raise ErreurRestitution(
                    f"reçu de préflight '{nom_fichier}' : sonde {rang} aux clés "
                    "exactes commande, code_sortie, stdout_expurge, "
                    "stderr_expurge attendue"
                )
            for champ in ("stdout_expurge", "stderr_expurge"):
                if not isinstance(sonde[champ], str):
                    raise ErreurRestitution(
                        f"reçu de préflight '{nom_fichier}' : sonde {rang} sans "
                        f"champ '{champ}' textuel"
                    )
    for table, cles in _CLES_TABLES_PREFLIGHT.items():
        if not isinstance(recu[table], dict) or set(recu[table]) != cles:
            raise ErreurRestitution(
                f"reçu de préflight '{nom_fichier}' : table '{table}' aux clés "
                f"exactes {sorted(cles)} attendue"
            )
    observee = recu["authentification"]["observee"]
    if adaptateur == ADAPTATEUR_CLAUDE:
        if observee != INCONNU and (
            not isinstance(observee, dict)
            or set(observee) != {"loggedIn", "authMethod", "apiProvider"}
            or not isinstance(observee["loggedIn"], bool)
            or any(
                not isinstance(observee[champ], str) or not observee[champ].strip()
                for champ in ("authMethod", "apiProvider")
            )
        ):
            raise ErreurRestitution(
                f"reçu de préflight '{nom_fichier}' : authentification.observee "
                "'INCONNU' ou aux clés exactes loggedIn, authMethod, apiProvider "
                "attendue"
            )
    elif adaptateur == ADAPTATEUR_CODEX:
        if observee != INCONNU and not _projection_login_codex_valide(observee):
            raise ErreurRestitution(
                f"reçu de préflight '{nom_fichier}' : authentification.observee "
                "'INCONNU' ou aux clés exactes connecte, methode attendue"
            )
    elif adaptateur == ADAPTATEUR_CURSOR:
        if observee != INCONNU and not _projection_statut_cursor_valide(observee):
            raise ErreurRestitution(
                f"reçu de préflight '{nom_fichier}' : authentification.observee "
                "'INCONNU' ou aux clés exactes status, isAuthenticated attendue"
            )
    elif adaptateur == ADAPTATEUR_OPENCODEX:
        if observee != INCONNU and not _projection_compte_opencodex_valide(
            observee
        ):
            raise ErreurRestitution(
                f"reçu de préflight '{nom_fichier}' : authentification.observee "
                "'INCONNU' ou aux clés exactes fournisseur, type, cle_active "
                "attendue"
            )
    elif adaptateur == ADAPTATEUR_ANTIGRAVITY:
        # Accessibilité des métadonnées, jamais une identité de compte
        if observee != INCONNU and (
            not isinstance(observee, dict)
            or set(observee) != set(CHAMPS_AUTH_ANTIGRAVITY)
            or any(
                observee[champ] != INCONNU
                and not isinstance(observee[champ], bool)
                for champ in CHAMPS_AUTH_ANTIGRAVITY
            )
        ):
            raise ErreurRestitution(
                f"reçu de préflight '{nom_fichier}' : authentification.observee "
                "'INCONNU' ou aux clés exactes "
                f"{sorted(CHAMPS_AUTH_ANTIGRAVITY)} attendue"
            )
    else:
        if observee != INCONNU and (
            not isinstance(observee, dict)
            or set(observee) != set(CHAMPS_PROJECTION_AUTH_GROK)
            or not isinstance(observee["credential_present"], bool)
            or any(
                not isinstance(observee[champ], str) or not observee[champ].strip()
                for champ in ("auth_mode", "issuer")
            )
        ):
            raise ErreurRestitution(
                f"reçu de préflight '{nom_fichier}' : authentification.observee "
                "'INCONNU' ou aux clés exactes auth_mode, credential_present, "
                "issuer attendue"
            )
    if adaptateur == ADAPTATEUR_OPENCODEX:
        _valider_objets_opencodex(nom_fichier, recu)
    if adaptateur == ADAPTATEUR_ANTIGRAVITY:
        _valider_objets_antigravity(nom_fichier, recu)
    if verdict == "READY":
        # READY exige les cinq contrôles établis : aucun champ observé ne
        # peut rester INCONNU ni NON_DEFINI
        for nom_champ, table, cle in _CHAMPS_OBSERVES_READY:
            if recu[table][cle] in (INCONNU, "NON_DEFINI"):
                raise ErreurRestitution(
                    f"reçu de préflight '{nom_fichier}' : verdict READY refusé, "
                    f"champ '{nom_champ}' non observé ({recu[table][cle]!r})"
                )
    return recu


def _valider_objets_opencodex(nom_fichier: str, recu: dict) -> None:
    """Quatre objets distincts du reçu opencodex : formes fermées, sans
    secret, et une identité réellement servie qui ne devient jamais une
    conclusion."""
    catalogue = recu["catalogue_declare"]
    if (
        not isinstance(catalogue, dict)
        or set(catalogue) != _CLES_CATALOGUE_DECLARE_OPENCODEX
        or any(
            catalogue[champ] != INCONNU
            and (
                not isinstance(catalogue[champ], str)
                or not catalogue[champ].strip()
            )
            for champ in ("fournisseur", "adaptateur", "endpoint")
        )
        or any(
            catalogue[champ] != INCONNU
            and not isinstance(catalogue[champ], bool)
            for champ in ("entree_exacte_presente", "effort_high_present")
        )
    ):
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : catalogue_declare aux clés "
            f"exactes {sorted(_CLES_CATALOGUE_DECLARE_OPENCODEX)} attendu"
        )
    proxy = recu["proxy_opencodex"]
    if (
        not isinstance(proxy, dict)
        or set(proxy) != _CLES_PROXY_OPENCODEX
        or (
            proxy["version"] != INCONNU
            and (
                not isinstance(proxy["version"], str)
                or not proxy["version"].strip()
            )
        )
        or (proxy["ready"] != INCONNU and not isinstance(proxy["ready"], bool))
        or (
            proxy["status"] != INCONNU
            and proxy["status"] not in STATUTS_READY_OPENCODEX
        )
    ):
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : proxy_opencodex aux clés "
            f"exactes {sorted(_CLES_PROXY_OPENCODEX)} attendu"
        )
    if recu["identite_reellement_servie"] != INCONNU:
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : identite_reellement_servie "
            f"'{INCONNU}' exigée dans cette tranche sans génération ; le "
            "catalogue déclaré ne vaut jamais identité servie"
        )
    observe = recu["quota"]["observe"]
    if observe != INCONNU and (
        not isinstance(observe, dict)
        or set(observe) != _CLES_QUOTA_OBSERVE_OPENCODEX
        or observe["source"] != SOURCE_QUOTA_ZAI
        or not isinstance(observe["fenetres"], dict)
        or set(observe["fenetres"]) != set(NOMS_FENETRES_QUOTA_ZAI)
        or any(
            not isinstance(fenetre, dict)
            or set(fenetre) != _CLES_FENETRE_QUOTA_OPENCODEX
            or not _pourcentage_ou_reset_valide(fenetre["pourcentage"])
            or not _pourcentage_ou_reset_valide(fenetre["reset"])
            for fenetre in observe["fenetres"].values()
        )
    ):
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : quota.observe '{INCONNU}' "
            f"ou table source '{SOURCE_QUOTA_ZAI}' et fenêtres "
            f"{sorted(NOMS_FENETRES_QUOTA_ZAI)} attendue"
        )


def _valider_objets_antigravity(nom_fichier: str, recu: dict) -> None:
    """Objets distincts du reçu agy : une identité réellement servie qui ne
    devient jamais une conclusion et des fenêtres Gemini fermées, sans
    reconstruction de valeur."""
    if recu["identite_reellement_servie"] != INCONNU:
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : identite_reellement_servie "
            f"'{INCONNU}' exigée dans cette tranche sans génération ; le "
            "catalogue ne vaut jamais identité servie"
        )
    observe = recu["quota"]["observe"]
    if observe != INCONNU and (
        not isinstance(observe, dict)
        or set(observe) != _CLES_QUOTA_OBSERVE_ANTIGRAVITY
        or observe["source"] != SOURCE_QUOTA_ANTIGRAVITY
        or not isinstance(observe["fenetres"], dict)
        or set(observe["fenetres"]) != set(NOMS_FENETRES_USAGE_ANTIGRAVITY)
        or any(
            not isinstance(fenetre, dict)
            or set(fenetre) != _CLES_FENETRE_QUOTA_ANTIGRAVITY
            or not _pourcentage_ou_reset_valide(fenetre["pourcentage_restant"])
            or not (
                fenetre["reset"] == INCONNU
                or (
                    isinstance(fenetre["reset"], str)
                    and fenetre["reset"].strip()
                )
            )
            for fenetre in observe["fenetres"].values()
        )
    ):
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : quota.observe '{INCONNU}' "
            f"ou table source '{SOURCE_QUOTA_ANTIGRAVITY}' et fenêtres "
            f"{sorted(NOMS_FENETRES_USAGE_ANTIGRAVITY)} attendue"
        )
    if recu["verdict"] == "READY":
        # READY exige chaque fenêtre Gemini pleinement observée : un
        # pourcentage ou un reset INCONNU ou NON_DEFINI est refusé
        if not isinstance(observe, dict):
            raise ErreurRestitution(
                f"reçu de préflight '{nom_fichier}' : verdict READY refusé, "
                "quota.observe sans fenêtres Gemini observées"
            )
        for nom, fenetre in observe["fenetres"].items():
            if fenetre["pourcentage_restant"] in (INCONNU, "NON_DEFINI") or (
                fenetre["reset"] in (INCONNU, "NON_DEFINI")
            ):
                raise ErreurRestitution(
                    f"reçu de préflight '{nom_fichier}' : verdict READY "
                    f"refusé, fenêtre Gemini '{nom}' au pourcentage ou au "
                    "reset non observé"
                )


def _charger_recus_preflight(racine: Path) -> list[tuple[str, dict, str]]:
    """Reçus de préflight validés : (chemin relatif, reçu, SHA-256 du fichier)."""
    repertoire = racine / REPERTOIRE_PREFLIGHTS
    if not repertoire.is_dir():
        return []
    charges: list[tuple[str, dict, str]] = []
    for chemin in sorted(repertoire.iterdir()):
        try:
            recu = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
            raise ErreurRestitution(
                f"reçu de préflight illisible : {chemin.name} ({erreur})"
            ) from erreur
        _valider_recu_preflight(chemin.name, recu)
        charges.append(
            (
                (REPERTOIRE_PREFLIGHTS / chemin.name).as_posix(),
                recu,
                _sha256_fichier(chemin),
            )
        )
    return charges


def _texte_sonde_preflight(sonde: dict) -> str:
    if "projection" in sonde:
        projection = sonde["projection"]
        if projection == INCONNU:
            texte = f"projection <code>{INCONNU}</code>"
        else:
            commande_sonde = tuple(sonde["commande"].split())
            champs = _CHAMPS_PROJECTION_PAR_SONDE[commande_sonde]
            # La page autonome ne porte jamais la séquence d'un schéma
            # distant : un endpoint projeté est neutralisé, jamais omis
            texte = "projection " + " · ".join(
                f"{champ} <code>{_neutraliser_schema(_echapper(projection[champ]))}</code>"
                for champ in champs
            )
    else:
        texte = (
            "sortie expurgée "
            f"<code>{_echapper(sonde['stdout_expurge'].strip())}</code>"
        )
    return (
        f"<li>sonde <code>{_echapper(sonde['commande'])}</code> · code de sortie "
        f"<code>{_echapper(sonde['code_sortie'])}</code> · {texte}</li>"
    )


def _texte_auth_preflight(observee: object) -> str:
    if observee == INCONNU:
        return f"<code>{INCONNU}</code>"
    if set(observee) == set(CHAMPS_PROJECTION_LOGIN_CODEX):
        champs = CHAMPS_PROJECTION_LOGIN_CODEX
    elif set(observee) == set(CHAMPS_PROJECTION_AUTH_GROK):
        champs = CHAMPS_PROJECTION_AUTH_GROK
    elif set(observee) == set(CHAMPS_PROJECTION_STATUT_CURSOR):
        champs = CHAMPS_PROJECTION_STATUT_CURSOR
    elif set(observee) == set(CHAMPS_PROJECTION_COMPTE_OPENCODEX):
        champs = CHAMPS_PROJECTION_COMPTE_OPENCODEX
    elif set(observee) == set(CHAMPS_AUTH_ANTIGRAVITY):
        champs = CHAMPS_AUTH_ANTIGRAVITY
    else:
        champs = ("loggedIn", "authMethod", "apiProvider")
    return " · ".join(
        f"{champ} <code>{_neutraliser_schema(_echapper(observee[champ]))}</code>"
        for champ in champs
    )


def _neutraliser_schema(texte: str) -> str:
    """La page autonome ne porte jamais la séquence d'un schéma distant :
    le deux-points d'un issuer projeté est rendu par entité HTML ; la
    valeur du reçu reste canonique, le texte affiché est identique."""
    return texte.replace("://", "&#58;//")


def _article_preflight(relatif: str, sha_fichier: str, recu: dict) -> str:
    """Article régénérable à l'identique depuis le reçu de préflight."""
    sondes = "".join(
        _texte_sonde_preflight(sonde) for sonde in recu["sondes"]
    )
    liste_sondes = (
        f"<ul>{sondes}</ul>"
        if sondes
        else "<p>aucune sonde lancée</p>"
    )
    cause = recu["cause"] if recu["cause"] is not None else "aucune"
    contenu = (
        f"<p><strong>{_echapper(recu['configuration_id'])}</strong> — préflight "
        "de disponibilité, sans génération, sans acquisition et sans score.</p>"
        f"<p>date <code>{_echapper(recu['date_preflight'])}</code> · autorité "
        f"unique <code>{_echapper(recu['autorite_preflight'])}</code></p>"
        f"<p>verdict de route <code>{_echapper(recu['verdict'])}</code> · cause "
        f"<code>{_echapper(cause)}</code></p>"
        f"<p>fait : {_echapper(recu['fait'])}</p>"
        f"<p>commande exacte <code>{_echapper(recu['commande_publique'])}</code></p>"
        + liste_sondes
        + f"<p>interface <code>{_echapper(recu['interface']['type'])}</code> · "
        f"client <code>{_echapper(recu['interface']['client'])}</code> · version "
        f"observée <code>{_echapper(recu['interface']['version_observee'])}</code></p>"
        "<p>authentification observée : "
        f"{_texte_auth_preflight(recu['authentification']['observee'])}</p>"
        f"<p>plan déclaré <code>{_echapper(recu['plan']['declare'])}</code> · plan "
        f"observé <code>{_echapper(recu['plan']['observe'])}</code></p>"
        f"<p>modèle demandé <code>{_echapper(recu['modele']['demande'])}</code> · "
        f"modèle exposé <code>{_echapper(recu['modele']['expose'])}</code></p>"
        f"<p>effort demandé <code>{_echapper(recu['effort']['demande'])}</code> · "
        f"effort exposé <code>{_echapper(recu['effort']['expose'])}</code></p>"
        f"<p>quota observé {_texte_quota_preflight(recu['quota']['observe'])} · "
        "consommation du préflight "
        f"<code>{_echapper(recu['quota']['consommation_preflight'])}</code></p>"
        + _objets_distincts_preflight(recu)
        + _span_source(relatif, sha_fichier, SECTION_PREFLIGHT)
    )
    return _article(
        "fait",
        contenu,
        f' data-preflight="{recu["configuration_id"]}"',
    )


def _texte_quota_preflight(observe: object) -> str:
    """Quota observé : INCONNU littéral ou détail des fenêtres reconnues,
    sans reconstruction de valeur. Les fenêtres et leurs champs fermés
    viennent du reçu validé, rendus en ordre déterministe."""
    if not isinstance(observe, dict):
        return f"<code>{_echapper(observe)}</code>"
    fenetres = " · ".join(
        f"{nom} "
        + " ".join(
            f"{champ} <code>{_echapper(observe['fenetres'][nom][champ])}</code>"
            for champ in sorted(observe["fenetres"][nom])
        )
        for nom in sorted(observe["fenetres"])
    )
    return f"source <code>{_echapper(observe['source'])}</code> · {fenetres}"


def _objets_distincts_preflight(recu: dict) -> str:
    """Rendu séparé des objets distincts des reçus opencodex et agy : le
    catalogue, le proxy et l'identité réellement servie ne se substituent
    jamais l'un à l'autre ; l'authentification est déjà rendue plus haut."""
    if "identite_reellement_servie" not in recu:
        return ""
    contenu = ""
    if "catalogue_declare" in recu:
        catalogue = recu["catalogue_declare"]
        proxy = recu["proxy_opencodex"]
        contenu = (
            "<p>catalogue déclaré : fournisseur "
            f"<code>{_echapper(catalogue['fournisseur'])}</code> · adaptateur "
            f"<code>{_echapper(catalogue['adaptateur'])}</code> · endpoint "
            f"<code>{_neutraliser_schema(_echapper(catalogue['endpoint']))}</code> · "
            "entrée exacte présente "
            f"<code>{_echapper(catalogue['entree_exacte_presente'])}</code> · "
            "effort high présent "
            f"<code>{_echapper(catalogue['effort_high_present'])}</code> — le "
            "catalogue déclaré ne prouve ni l'accès à une génération, ni le "
            "modèle réellement servi.</p>"
            "<p>proxy OpenCodex : version "
            f"<code>{_echapper(proxy['version'])}</code> · ready "
            f"<code>{_echapper(proxy['ready'])}</code> · status "
            f"<code>{_echapper(proxy['status'])}</code></p>"
        )
    return contenu + (
        "<p>identité réellement servie : "
        f"<code>{_echapper(recu['identite_reellement_servie'])}</code> — "
        "jamais déduite du catalogue déclaré, de l'authentification ni du "
        "rapport de quota.</p>"
    )


# ---------------------------------------------------------------------------
# V1-XS-07 : verrou de campagne abonnement
# Autorités : V1_XS_07 = LAUNCH, V1_XS_07_PLAN_CONTRACT = VALIDATE (Issue #107)

SCHEMA_SOURCES_PLANS = "campagne-v1-sources-plans/v1"
CHEMIN_SOURCES_PLANS = _RACINE_CAMPAGNE_V1 / "sources-plans-v1.toml"
SEMANTIQUE_PRIX_PLANS = (
    "CATALOGUE_STANDARD_MENSUEL_USD_HORS_TAXE_REMISE_ET_FACTURATION_LOCALE"
)
CLASSE_PLAN_FAIT = "FAIT_ETABLI"
CLASSE_PLAN_DEDUCTION = "DEDUCTION_RAISONNEE"
# Seule la correspondance Codex Pro 20x est une déduction raisonnée validée
CONFIGURATION_PLAN_DEDUIT = "codex-gpt-5-6-sol"
ATTESTATION_PANEL = "D-V1-01"
DATE_ATTESTATION_PANEL = "2026-08-22"

SCHEMA_VERROU = "campagne-v1-verrou-abonnement/v1"
CHEMIN_VERROU = _RACINE_CAMPAGNE_V1 / "verrou-campagne-v1" / "verrou.json"
ISSUE_VERROU = "https://github.com/ayoahha/benchmark-lab-x/issues/107"

# Racine privée obligatoire : aucun drapeau CLI, variable d'environnement ni
# fallback ne permet d'en choisir une autre ; le paramètre Python racine_privee
# de principal existe pour les seuls tests
RACINE_PRIVEE_PRODUCTION = Path(
    "/Users/ayo/Library/Application Support/Benchmark Lab-X/private"
)
RELATIF_MATERIEL_VERROU = Path("v1-execution") / "xs-07" / "material"
NOM_SEL_VERROU = "sel.bin"
NOM_MANIFESTE_ORDRE = "manifeste-ordre.json"
TAILLE_SEL_VERROU = 32

# Méthode d'engagement d'ordre aveugle reprise à l'identique de la V0
METHODE_ORDRE_VERROU = "SHA256_SALT_CAMPAIGN_ID_ACQUISITION_ID_SORT"
CAMPAGNE_ID_VERROU = "benchmark-lab-x-v1-abonnement"

# Engagement masqué du manifeste privé : avec deux créneaux, une empreinte
# directe révélerait la permutation par énumération ; le commitment est un
# HMAC-SHA256 à clé secrète (le sel) avec séparation de domaine
METHODE_ENGAGEMENT_MANIFESTE = "HMAC_SHA256_KEY_SALT_DOMAIN_SEPARATED_V1"
DOMAINE_ENGAGEMENT_MANIFESTE = b"benchmark-lab-x/campagne-v1/manifeste-ordre/v1\x00"

DISPOSITION_ELIGIBLE = "ELIGIBLE"
DISPOSITION_EXCLUE = "EXCLUDED_WAITING"

REGLE_FRAICHEUR_VERROU = "EXACT_LOCK_EVENT_BASED_NO_TTL"
EFFET_FRAICHEUR_VERROU = "HOLD_STOP_NO_CROSS_EVENT_COMPARISON"
EVENEMENTS_FRAICHEUR_VERROU = (
    "LOCKED_ARTIFACT_CHANGED",
    "CONFIGURATION_CHANGED",
    "HARNESS_CHANGED",
    "ADAPTER_CHANGED",
    "ROUTE_CHANGED",
    "SERVED_IDENTITY_CHANGED",
    "BILLING_REGIME_CHANGED",
    "APPLICABLE_PRICE_FACT_CHANGED",
)

_MOTIF_DATE_PLAN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_CLES_PLAN_SOURCES = {
    "configuration_id",
    "nom",
    "prix_montant",
    "prix_devise",
    "periode",
    "source_url",
    "date_publication",
    "date_consultation",
    "classe_msw",
    "attestation_reference",
}


class ErreurSourcesPlans(Exception):
    """Refus fail-closed de la source de plans, avant toute écriture (code 1)."""


class ErreurVerrou(Exception):
    """HOLD du verrou de campagne, sans réparation ni écrasement (code 2)."""


def _exiger_plan_chaine(nom: str, valeur: object) -> str:
    if not isinstance(valeur, str) or not valeur:
        raise ErreurSourcesPlans(f"champ '{nom}' : chaîne non vide attendue")
    return valeur


def _valider_plan_sources(
    rang: int, entree: object, identifiants: tuple[str, ...]
) -> dict:
    nom_table = f"plan[{rang}]"
    if not isinstance(entree, dict):
        raise ErreurSourcesPlans(f"'{nom_table}' : table attendue")
    identifiant = entree.get("configuration_id")
    if not isinstance(identifiant, str) or identifiant not in identifiants:
        raise ErreurSourcesPlans(
            f"champ '{nom_table}.configuration_id' : identifiant hors panel "
            f"déclaré : {identifiant!r}"
        )
    cles_attendues = set(_CLES_PLAN_SOURCES)
    if identifiant == CONFIGURATION_PLAN_DEDUIT:
        cles_attendues.add("premisses")
    if set(entree) != cles_attendues:
        raise ErreurSourcesPlans(
            f"'{nom_table}' ({identifiant}) : clés exactes "
            f"{sorted(cles_attendues)} attendues, hors vocabulaire refusé"
        )
    _exiger_plan_chaine(f"{nom_table}.nom", entree["nom"])
    montant = entree["prix_montant"]
    if (
        isinstance(montant, bool)
        or not isinstance(montant, (int, float))
        or not montant > 0
    ):
        raise ErreurSourcesPlans(
            f"champ '{nom_table}.prix_montant' : montant numérique strictement "
            "positif attendu"
        )
    if entree["prix_devise"] != "USD":
        raise ErreurSourcesPlans(f"champ '{nom_table}.prix_devise' : 'USD' attendu")
    if entree["periode"] != "MONTH":
        raise ErreurSourcesPlans(f"champ '{nom_table}.periode' : 'MONTH' attendu")
    source_url = _exiger_plan_chaine(f"{nom_table}.source_url", entree["source_url"])
    if not source_url.startswith("https://"):
        raise ErreurSourcesPlans(
            f"champ '{nom_table}.source_url' : URL officielle https attendue"
        )
    publication = entree["date_publication"]
    if publication != "NON_DEFINI" and (
        not isinstance(publication, str) or not _MOTIF_DATE_PLAN.match(publication)
    ):
        raise ErreurSourcesPlans(
            f"champ '{nom_table}.date_publication' : date AAAA-MM-JJ ou "
            "'NON_DEFINI' attendue"
        )
    consultation = entree["date_consultation"]
    if not isinstance(consultation, str) or not _MOTIF_DATE_PLAN.match(consultation):
        raise ErreurSourcesPlans(
            f"champ '{nom_table}.date_consultation' : date AAAA-MM-JJ attendue"
        )
    classe_attendue = (
        CLASSE_PLAN_DEDUCTION
        if identifiant == CONFIGURATION_PLAN_DEDUIT
        else CLASSE_PLAN_FAIT
    )
    if entree["classe_msw"] != classe_attendue:
        raise ErreurSourcesPlans(
            f"champ '{nom_table}.classe_msw' : '{classe_attendue}' attendu pour "
            f"'{identifiant}'"
        )
    if entree["attestation_reference"] != ATTESTATION_PANEL:
        raise ErreurSourcesPlans(
            f"champ '{nom_table}.attestation_reference' : "
            f"'{ATTESTATION_PANEL}' attendu"
        )
    if identifiant == CONFIGURATION_PLAN_DEDUIT:
        premisses = entree["premisses"]
        if (
            not isinstance(premisses, list)
            or not premisses
            or not all(isinstance(p, str) and p for p in premisses)
        ):
            raise ErreurSourcesPlans(
                f"champ '{nom_table}.premisses' : liste non vide de prémisses "
                "explicites attendue pour la déduction raisonnée"
            )
    return entree


def _charger_sources_plans(
    racine: Path, identifiants: tuple[str, ...]
) -> tuple[dict[str, dict], str]:
    """Plans validés par configuration_id et SHA-256 du fichier source."""
    chemin = racine / CHEMIN_SOURCES_PLANS
    try:
        donnees = tomllib.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as erreur:
        raise ErreurSourcesPlans(
            f"source de plans illisible : {CHEMIN_SOURCES_PLANS.as_posix()} "
            f"({erreur})"
        ) from erreur
    if set(donnees) != {"schema_version", "semantique_prix", "plan"}:
        raise ErreurSourcesPlans(
            "source de plans : clés exactes ['plan', 'schema_version', "
            "'semantique_prix'] attendues, hors vocabulaire refusé"
        )
    if donnees["schema_version"] != SCHEMA_SOURCES_PLANS:
        raise ErreurSourcesPlans(
            f"champ 'schema_version' : '{SCHEMA_SOURCES_PLANS}' attendu"
        )
    if donnees["semantique_prix"] != SEMANTIQUE_PRIX_PLANS:
        raise ErreurSourcesPlans(
            f"champ 'semantique_prix' : '{SEMANTIQUE_PRIX_PLANS}' attendu"
        )
    tables = donnees["plan"]
    if not isinstance(tables, list):
        raise ErreurSourcesPlans("champ 'plan' : liste de tables attendue")
    plans: dict[str, dict] = {}
    for rang, entree in enumerate(tables):
        valide = _valider_plan_sources(rang, entree, identifiants)
        identifiant = valide["configuration_id"]
        if identifiant in plans:
            raise ErreurSourcesPlans(
                f"champ 'plan' : entrée dupliquée pour '{identifiant}'"
            )
        plans[identifiant] = valide
    manquants = [i for i in identifiants if i not in plans]
    if manquants:
        raise ErreurSourcesPlans(
            "champ 'plan' : source incomplète, provenance de prix absente pour "
            + ", ".join(f"'{i}'" for i in manquants)
        )
    return plans, _sha256_fichier(chemin)


def _identifiant_creneau(configuration_id: str) -> str:
    return f"ACQ-V1-{configuration_id.upper()}-001"


def _entrees_verrou(racine: Path) -> tuple[list[dict], list[dict], str]:
    """Panel dérivé, créneaux et SHA-256 de la source de plans.

    L'éligibilité est dérivée uniquement des reçus de préflight versionnés :
    seul un verdict READY rend une configuration ELIGIBLE, toute autre reste
    EXCLUDED_WAITING avec sa cause exacte.
    """
    try:
        configurations = _configurations_officielles(racine)
        preflights = _charger_recus_preflight(racine)
    except ErreurRestitution as erreur:
        raise ErreurVerrou(str(erreur)) from erreur
    if not configurations:
        raise ErreurVerrou("panel déclaré vide : aucun verrou dérivable")
    identifiants = tuple(donnees["configuration_id"] for _, donnees in configurations)
    par_identifiant = {
        recu["configuration_id"]: (relatif, recu, sha)
        for relatif, recu, sha in preflights
    }
    manquants = [i for i in identifiants if i not in par_identifiant]
    if manquants:
        raise ErreurVerrou("reçu de préflight absent pour : " + ", ".join(manquants))
    hors_panel = sorted(set(par_identifiant) - set(identifiants))
    if hors_panel:
        raise ErreurVerrou(
            "reçu de préflight hors panel déclaré : " + ", ".join(hors_panel)
        )
    plans, sha_sources = _charger_sources_plans(racine, identifiants)
    panel: list[dict] = []
    for chemin, donnees in configurations:
        identifiant = donnees["configuration_id"]
        relatif_preflight, recu, sha_preflight = par_identifiant[identifiant]
        verdict = recu["verdict"]
        disposition = (
            DISPOSITION_ELIGIBLE if verdict == "READY" else DISPOSITION_EXCLUE
        )
        plan = plans[identifiant]
        plan_verrou = {cle: plan[cle] for cle in plan if cle != "configuration_id"}
        panel.append(
            {
                "configuration_id": identifiant,
                "configuration": {
                    "chemin": chemin,
                    "sha256": _sha256_fichier(racine / chemin),
                },
                "attestation": {
                    "reference": ATTESTATION_PANEL,
                    "date": DATE_ATTESTATION_PANEL,
                },
                "preflight": {
                    "chemin": relatif_preflight,
                    "sha256": sha_preflight,
                },
                "verdict": verdict,
                "cause": recu["cause"],
                "disposition": disposition,
                "plan": plan_verrou,
            }
        )
    eligibles = sorted(
        entree["configuration_id"]
        for entree in panel
        if entree["disposition"] == DISPOSITION_ELIGIBLE
    )
    creneaux = [
        {
            "acquisition_id": _identifiant_creneau(identifiant),
            "configuration_id": identifiant,
        }
        for identifiant in eligibles
    ]
    return panel, creneaux, sha_sources


def _construire_verrou(
    panel: list[dict], creneaux: list[dict], engagements: list[dict], sha_sources: str
) -> dict:
    """Verrou public fermé : jamais de sel, d'ordre, de chemin privé ni de
    self-hash ; l'engagement du sel porte kind, mode, size et sha256, celui
    du manifeste porte kind, mode, size, commitment_method et commitment,
    sans empreinte directe."""
    return {
        "schema_version": SCHEMA_VERROU,
        "portee": {
            "product_version": "V1",
            "measurement_profile": "abonnement",
            "issue": ISSUE_VERROU,
        },
        "autorites": {
            "attestation_panel": ATTESTATION_PANEL,
            "lancement": "V1_XS_07 = LAUNCH",
            "contrat_plans": "V1_XS_07_PLAN_CONTRACT = VALIDATE",
            "preflight": AUTORITE_PREFLIGHT,
        },
        "cardinalite_declaree": len(panel),
        "panel": panel,
        "cardinalite_eligible": len(creneaux),
        "creneaux": creneaux,
        "creneaux_par_configuration_eligible": 1,
        "reprises": {"automatiques": 0, "manuelles": 0},
        "fallbacks": "NONE",
        "autorite_execution": {
            "autorite_acquisition_d_v1_04": "NOT_GRANTED",
            "acquisition": "NOT_GRANTED",
            "appel_fournisseur": "NOT_GRANTED",
            "consommation_quota": "NOT_GRANTED",
            "depense": "NOT_GRANTED",
        },
        "preuve_zero_execution": {
            "commandes_fournisseur_lancees": 0,
            "creneaux_executes": 0,
            "reprises_executees": 0,
        },
        "fraicheur": {
            "regle": REGLE_FRAICHEUR_VERROU,
            "evenements_materiels": list(EVENEMENTS_FRAICHEUR_VERROU),
            "effet": EFFET_FRAICHEUR_VERROU,
        },
        "engagement_ordre": {
            "methode": METHODE_ORDRE_VERROU,
            "campaign_id": CAMPAGNE_ID_VERROU,
            "items": [
                f"ITEM-{position:03d}" for position in range(1, len(creneaux) + 1)
            ],
            "positions": list(range(1, len(creneaux) + 1)),
            "publication": "AVEUGLE",
        },
        "engagements_prives": engagements,
        "sources_plans": {
            "chemin": CHEMIN_SOURCES_PLANS.as_posix(),
            "sha256": sha_sources,
        },
    }


def _octets_manifeste_ordre(sel: bytes, creneaux: list[dict]) -> bytes:
    """Manifeste privé : les identifiants de créneau, les positions contiguës
    et les identifiants opaques, ordonnés par la méthode V0."""

    def cle(entree: dict) -> tuple[bytes, bytes]:
        acquisition_id = entree["acquisition_id"]
        empreinte = hashlib.sha256(
            sel + CAMPAGNE_ID_VERROU.encode("utf-8") + acquisition_id.encode("utf-8")
        ).digest()
        return (empreinte, acquisition_id.encode("utf-8"))

    ordre = sorted(creneaux, key=cle)
    return octets_canoniques(
        [
            {
                "acquisition_id": entree["acquisition_id"],
                "item": f"ITEM-{position:03d}",
                "position": position,
            }
            for position, entree in enumerate(ordre, start=1)
        ]
    )


def _engagement_prive(chemin: Path, genre: str) -> dict:
    infos = os.lstat(chemin)
    return {
        "kind": genre,
        "mode": f"{stat.S_IMODE(infos.st_mode):04o}",
        "sha256": _sha256_fichier(chemin),
        "size": infos.st_size,
    }


def _engagement_manifeste(chemin_manifeste: Path, sel: bytes) -> dict:
    """Engagement masqué du manifeste : jamais d'empreinte directe publiée,
    le commitment n'est vérifiable qu'avec le sel privé lors de la révélation."""
    infos = os.lstat(chemin_manifeste)
    commitment = hmac.new(
        sel,
        DOMAINE_ENGAGEMENT_MANIFESTE + chemin_manifeste.read_bytes(),
        hashlib.sha256,
    ).hexdigest()
    return {
        "commitment": commitment,
        "commitment_method": METHODE_ENGAGEMENT_MANIFESTE,
        "kind": "manifeste-ordre",
        "mode": f"{stat.S_IMODE(infos.st_mode):04o}",
        "size": infos.st_size,
    }


def _ecrire_prive(chemin: Path, octets: bytes) -> None:
    descripteur = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descripteur, "wb") as flux:
        flux.write(octets)
    os.chmod(chemin, 0o600)


def _verifier_materiel_prive(
    repertoire: Path, chemin_sel: Path, chemin_manifeste: Path
) -> list[dict]:
    """Types, modes, tailles et empreintes du matériel privé, sans jamais
    exposer de contenu dans les erreurs."""
    infos_repertoire = os.lstat(repertoire)
    if stat.S_ISLNK(infos_repertoire.st_mode) or not stat.S_ISDIR(
        infos_repertoire.st_mode
    ):
        raise ErreurVerrou(
            "répertoire de matériel privé : répertoire régulier attendu"
        )
    if stat.S_IMODE(infos_repertoire.st_mode) != 0o700:
        raise ErreurVerrou("répertoire de matériel privé : mode 0700 attendu")
    noms = sorted(entree.name for entree in repertoire.iterdir())
    if noms != sorted((NOM_SEL_VERROU, NOM_MANIFESTE_ORDRE)):
        raise ErreurVerrou(
            "répertoire de matériel privé : exactement deux objets attendus, "
            "objet inattendu présent"
        )
    for chemin in (chemin_sel, chemin_manifeste):
        infos = os.lstat(chemin)
        if stat.S_ISLNK(infos.st_mode) or not stat.S_ISREG(infos.st_mode):
            raise ErreurVerrou(
                f"objet privé '{chemin.name}' : fichier régulier non "
                "symbolique attendu"
            )
        if stat.S_IMODE(infos.st_mode) != 0o600:
            raise ErreurVerrou(f"objet privé '{chemin.name}' : mode 0600 attendu")
    if os.lstat(chemin_sel).st_size != TAILLE_SEL_VERROU:
        raise ErreurVerrou(
            f"objet privé '{NOM_SEL_VERROU}' : {TAILLE_SEL_VERROU} octets attendus"
        )
    return [
        _engagement_prive(chemin_sel, "sel"),
        _engagement_manifeste(chemin_manifeste, chemin_sel.read_bytes()),
    ]


def _verifier_ordre_prive(
    chemin_sel: Path, chemin_manifeste: Path, creneaux: list[dict]
) -> None:
    sel = chemin_sel.read_bytes()
    if chemin_manifeste.read_bytes() != _octets_manifeste_ordre(sel, creneaux):
        raise ErreurVerrou(
            "manifeste d'ordre incohérent avec le sel et les créneaux verrouillés"
        )


def _verifier_verrou_public(
    chemin_verrou: Path, octets_attendus: bytes, panel: list[dict]
) -> None:
    infos = os.lstat(chemin_verrou)
    if stat.S_ISLNK(infos.st_mode) or not stat.S_ISREG(infos.st_mode):
        raise ErreurVerrou("verrou public : fichier régulier non symbolique attendu")
    octets = chemin_verrou.read_bytes()
    if octets == octets_attendus:
        return
    # Divergence : nommer la cause exacte sans réparation ni écrasement
    verdicts = {entree["configuration_id"]: entree["verdict"] for entree in panel}
    try:
        existant = json.loads(octets.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        existant = None
    if isinstance(existant, dict) and isinstance(existant.get("panel"), list):
        for entree in existant["panel"]:
            if not isinstance(entree, dict):
                continue
            if entree.get("disposition") != DISPOSITION_ELIGIBLE:
                continue
            identifiant = entree.get("configuration_id")
            if (
                entree.get("verdict") != "READY"
                or verdicts.get(identifiant) != "READY"
            ):
                raise ErreurVerrou(
                    "configuration non READY marquée éligible dans le verrou "
                    f"existant : {identifiant}"
                )
    attendu = json.loads(octets_attendus.decode("utf-8"))
    if isinstance(existant, dict):
        if existant.get("sources_plans") != attendu["sources_plans"]:
            raise ErreurVerrou(
                "fait de plan applicable changé après verrou "
                "(APPLICABLE_PRICE_FACT_CHANGED) : aucune réécriture"
            )
        if existant.get("panel") != attendu["panel"]:
            raise ErreurVerrou(
                "entrée verrouillée changée après verrou (CONFIGURATION_CHANGED "
                "ou ROUTE_CHANGED) : aucune réécriture"
            )
        if existant.get("engagements_prives") != attendu["engagements_prives"]:
            raise ErreurVerrou(
                "engagement privé divergent du matériel présent : aucune réparation"
            )
    raise ErreurVerrou(
        "verrou public divergent des entrées courantes (LOCKED_ARTIFACT_CHANGED) : "
        "aucune réécriture"
    )


def _materialiser_verrou(
    chemin_verrou: Path,
    repertoire_materiel: Path,
    chemin_sel: Path,
    chemin_manifeste: Path,
    panel: list[dict],
    creneaux: list[dict],
    sha_sources: str,
) -> None:
    """Matérialise une seule fois, sans écraser aucun fichier existant."""
    repertoire_materiel.mkdir(parents=True, exist_ok=False)
    os.chmod(repertoire_materiel, 0o700)
    sel = os.urandom(TAILLE_SEL_VERROU)
    _ecrire_prive(chemin_sel, sel)
    _ecrire_prive(chemin_manifeste, _octets_manifeste_ordre(sel, creneaux))
    engagements = [
        _engagement_prive(chemin_sel, "sel"),
        _engagement_manifeste(chemin_manifeste, sel),
    ]
    verrou = _construire_verrou(panel, creneaux, engagements, sha_sources)
    chemin_verrou.parent.mkdir(parents=True, exist_ok=True)
    descripteur = os.open(chemin_verrou, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descripteur, "wb") as flux:
        flux.write(octets_canoniques(verrou))


def verrouiller(racine: Path, racine_privee: Path | None = None) -> int:
    """Valide les entrées, matérialise une seule fois le verrou et les deux
    objets privés, puis vérifie l'ensemble dans la même invocation. N'exécute
    aucune commande externe de fournisseur, de modèle ou de harnais."""
    if racine_privee is None:
        racine_privee = RACINE_PRIVEE_PRODUCTION
    chemin_verrou = racine / CHEMIN_VERROU
    repertoire_materiel = racine_privee / RELATIF_MATERIEL_VERROU
    chemin_sel = repertoire_materiel / NOM_SEL_VERROU
    chemin_manifeste = repertoire_materiel / NOM_MANIFESTE_ORDRE
    try:
        panel, creneaux, sha_sources = _entrees_verrou(racine)
    except ErreurSourcesPlans as erreur:
        print(f"ECHEC {erreur}")
        return 1
    except ErreurVerrou as erreur:
        print(f"ECHEC {erreur}")
        return 2
    sorties = (chemin_verrou, repertoire_materiel, chemin_sel, chemin_manifeste)
    presentes = [chemin for chemin in sorties if os.path.lexists(chemin)]
    try:
        if not presentes:
            _materialiser_verrou(
                chemin_verrou,
                repertoire_materiel,
                chemin_sel,
                chemin_manifeste,
                panel,
                creneaux,
                sha_sources,
            )
        elif len(presentes) != len(sorties):
            raise ErreurVerrou(
                "sortie partielle : verrou et matériel privé incomplets, aucune "
                "réparation ni écrasement"
            )
        engagements = _verifier_materiel_prive(
            repertoire_materiel, chemin_sel, chemin_manifeste
        )
        _verifier_ordre_prive(chemin_sel, chemin_manifeste, creneaux)
        verrou_attendu = _construire_verrou(panel, creneaux, engagements, sha_sources)
        _verifier_verrou_public(chemin_verrou, octets_canoniques(verrou_attendu), panel)
    except ErreurVerrou as erreur:
        print(f"ECHEC {erreur}")
        return 2
    except OSError as erreur:
        # Cause fail-closed nommée, sans traceback ni chemin privé complet
        nom = Path(erreur.filename).name if erreur.filename else "inconnu"
        print(
            f"ECHEC artefact du verrou inaccessible : '{nom}' ({erreur.strerror})"
        )
        return 2
    exclusions = len(panel) - len(creneaux)
    print(f"verrou vérifié : {CHEMIN_VERROU.as_posix()}")
    print(
        f"panel déclaré : {len(panel)} · éligibles : {len(creneaux)} · "
        f"exclusions : {exclusions} · créneaux : {len(creneaux)} · "
        "reprises : 0 · fallbacks : NONE"
    )
    for engagement in engagements:
        if "commitment" in engagement:
            print(
                f"engagement privé {engagement['kind']} : mode "
                f"{engagement['mode']} · {engagement['size']} octets · "
                f"méthode {engagement['commitment_method']} · commitment "
                f"{engagement['commitment']}"
            )
        else:
            print(
                f"engagement privé {engagement['kind']} : mode "
                f"{engagement['mode']} · {engagement['size']} octets · "
                f"SHA-256 {engagement['sha256']}"
            )
    return 0


SECTION_VERROU = "verrou de campagne abonnement versionné"
SECTION_SOURCES_PLANS = "sources de plans validées versionnées"

_CLES_VERROU_PUBLIC = {
    "schema_version",
    "portee",
    "autorites",
    "cardinalite_declaree",
    "panel",
    "cardinalite_eligible",
    "creneaux",
    "creneaux_par_configuration_eligible",
    "reprises",
    "fallbacks",
    "autorite_execution",
    "preuve_zero_execution",
    "fraicheur",
    "engagement_ordre",
    "engagements_prives",
    "sources_plans",
}
_CLES_ENTREE_PANEL_VERROU = {
    "configuration_id",
    "configuration",
    "attestation",
    "preflight",
    "verdict",
    "cause",
    "disposition",
    "plan",
}


# ---------------------------------------------------------------------------
# Acquisition officielle V1-XS-08 sous l'autorité propriétaire D-V1-04

SCHEMA_AUTORISATION_ACQUISITION = "campagne-v1-autorisation-acquisition/v1"
CHEMIN_AUTORISATION_ACQUISITION = (
    _RACINE_CAMPAGNE_V1 / "autorisation-acquisition-v1.json"
)
AUTORITE_ACQUISITION = "D-V1-04"
JETON_AUTORITE_ACQUISITION = "Donc Go D-V1-04, V1-XS-08"
URL_COMMENTAIRE_ACQUISITION = (
    "https://github.com/ayoahha/benchmark-lab-x/issues/108"
    "#issuecomment-5434400855"
)
AUTEUR_COMMENTAIRE_ACQUISITION = "ayoahha"
ASSOCIATION_COMMENTAIRE_ACQUISITION = "OWNER"
DATE_COMMENTAIRE_ACQUISITION = "2026-08-27"
SHA256_COMMENTAIRE_ACQUISITION = (
    "5a405a72b31a80b32d89e4db59e0d39f7d3f140b79c5ae3e595af9e05cd06c4f"
)

# Plafond effectif par tentative, décision technique fermée de XS-08 : les
# fichiers verrouillés gardent delai_secondes = 0 (aucune surcharge) et la
# couche officielle applique 600 s, plafond existant de la qualification V1
# qui couvre l'observation V0 de 382 217 ms sur le même stimulus
DELAI_ACQUISITION_OFFICIELLE = 600

RELATIF_EXECUTION_XS08 = Path("v1-execution") / "xs-08"
NOM_RUNTIME_XS08 = "runtime"
NOM_JOURNAL_EXECUTION = "execution-journal.json"
SCHEMA_JOURNAL_EXECUTION = "campagne-v1-execution-journal/v1"

# Jeton machine du reçu : la requête consignée reste expurgée, le texte du
# stimulus n'entre jamais dans le reçu, seule son empreinte le lie
JETON_STIMULUS_UTF8 = "__STIMULUS_UTF8__"

CONFIGURATION_ACQUISITION_ANTIGRAVITY = "antigravity-gemini-3-7-flash"
CONFIGURATION_ACQUISITION_ZAI = "zai-glm-5-3"
MODELE_ACQUISITION_ANTIGRAVITY = "gemini-3.7-flash-high"
EFFORT_ACQUISITION_ANTIGRAVITY = "high"
ARGV_DECLARE_ANTIGRAVITY = ("agy", JETON_FICHIER_PROMPT)
# Flags exacts du `agy --help` local (version observée 1.1.21), verrouillés
# par les tests avant tout appel : impression non interactive, sélection
# explicite du modèle sans défaut implicite, effort, sandbox, mode plan non
# mutateur et désactivation des slash commands en mode print
FLAGS_ACQUISITION_ANTIGRAVITY = (
    "--print",
    "--model",
    MODELE_ACQUISITION_ANTIGRAVITY,
    "--effort",
    EFFORT_ACQUISITION_ANTIGRAVITY,
    "--sandbox",
    "--mode",
    "plan",
    "--disable-slash-commands",
)
# Descripteur exact conservé du verrou : Codex CLI agent, OpenCodex proxy,
# Z.AI Coding Plan fournisseur, stimulus exact sur stdin
ARGV_DECLARE_ZAI = (
    "codex",
    "exec",
    "--model",
    "zai/glm-5.3",
    "--cd",
    JETON_ESPACE_ISOLE,
    "--config",
    'model_reasoning_effort="high"',
    "-",
)
MODELES_ATTENDUS_ZAI = ("zai/glm-5.3", "glm-5.3")
# Aucun de ces éléments n'entre jamais dans un argv d'acquisition : session,
# reprise, projet, agent, interactivité, vitesse payante, fallback, mise à
# jour, installation ou connexion
FLAGS_INTERDITS_ACQUISITION = (
    "--continue",
    "-c",
    "--conversation",
    "--agent",
    "--project",
    "--new-project",
    "--prompt-interactive",
    "-i",
    "--dangerously-skip-permissions",
    "fast",
    "priority",
    "max",
    "ultra",
    "fallback",
    "update",
    "install",
    "login",
)

# Métadonnée explicite d'identité servie : seule une ligne de la forme
# 'model: <valeur>' émise par l'appel est attribuable ; un écho de la
# configuration demandée ne promeut jamais REQUESTED en OBSERVED
_MOTIF_IDENTITE_SERVIE = re.compile(
    r"^\s*(?:--\s*)?model\s*:\s*(\S+)\s*$", re.MULTILINE
)

_CLES_AUTORISATION = {
    "schema_version",
    "autorite",
    "jeton",
    "commentaire",
    "verrou",
    "stimulus",
    "portee",
}
_CLES_COMMENTAIRE_AUTORISATION = {
    "url",
    "auteur",
    "association",
    "date",
    "sha256_corps",
}
_CLES_PORTEE_AUTORISATION = {
    "acquisitions",
    "appels_fournisseur_max",
    "appels_par_creneau",
    "consommation_quota",
    "depense_incrementale",
    "reprises_automatiques",
    "reprises_manuelles",
    "fallback",
}
_CLES_ENTREE_JOURNAL = {
    "acquisition_id",
    "configuration_id",
    "invocation_publique",
    "code",
    "recu",
    "etat_terminal",
    "latence_ms",
    "retry",
    "descendants",
}


class ErreurAutorisation(Exception):
    """Autorisation D-V1-04 absente ou divergente : refus code 2 avant tout
    processus fournisseur et sans reçu."""


class ErreurJournal(Exception):
    """Journal d'exécution privé illisible ou hors schéma fermé : HOLD."""


def _charger_autorisation_acquisition(racine: Path) -> dict:
    """Autorisation D-V1-04 validée fail-closed contre les valeurs figées du
    contrat et les empreintes courantes du verrou et du stimulus."""
    chemin = racine / CHEMIN_AUTORISATION_ACQUISITION
    if not chemin.is_file():
        raise ErreurAutorisation(
            f"artefact absent : {CHEMIN_AUTORISATION_ACQUISITION.as_posix()}"
        )
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurAutorisation(f"artefact illisible : {erreur}") from erreur
    if not isinstance(donnees, dict) or set(donnees) != _CLES_AUTORISATION:
        raise ErreurAutorisation("clés hors schéma fermé")
    if donnees["schema_version"] != SCHEMA_AUTORISATION_ACQUISITION:
        raise ErreurAutorisation(
            f"schéma '{SCHEMA_AUTORISATION_ACQUISITION}' attendu"
        )
    if donnees["autorite"] != AUTORITE_ACQUISITION:
        raise ErreurAutorisation(f"autorité '{AUTORITE_ACQUISITION}' attendue")
    if donnees["jeton"] != JETON_AUTORITE_ACQUISITION:
        raise ErreurAutorisation("jeton propriétaire divergent")
    commentaire = donnees["commentaire"]
    if (
        not isinstance(commentaire, dict)
        or set(commentaire) != _CLES_COMMENTAIRE_AUTORISATION
        or commentaire["url"] != URL_COMMENTAIRE_ACQUISITION
        or commentaire["auteur"] != AUTEUR_COMMENTAIRE_ACQUISITION
        or commentaire["association"] != ASSOCIATION_COMMENTAIRE_ACQUISITION
        or commentaire["date"] != DATE_COMMENTAIRE_ACQUISITION
        or commentaire["sha256_corps"] != SHA256_COMMENTAIRE_ACQUISITION
    ):
        raise ErreurAutorisation("référence de commentaire divergente")
    for nom, chemin_attendu in (
        ("verrou", CHEMIN_VERROU),
        ("stimulus", Path(CHEMIN_STIMULUS)),
    ):
        reference = donnees[nom]
        if (
            not isinstance(reference, dict)
            or set(reference) != {"chemin", "sha256"}
            or reference["chemin"] != chemin_attendu.as_posix()
        ):
            raise ErreurAutorisation(f"référence '{nom}' hors schéma fermé")
        cible = racine / chemin_attendu
        if not cible.is_file():
            raise ErreurAutorisation(f"cible de '{nom}' absente")
        if reference["sha256"] != _sha256_fichier(cible):
            raise ErreurAutorisation(
                f"empreinte de '{nom}' divergente du fichier courant"
            )
    portee = donnees["portee"]
    if not isinstance(portee, dict) or set(portee) != _CLES_PORTEE_AUTORISATION:
        raise ErreurAutorisation("portée hors schéma fermé")
    acquisitions = portee["acquisitions"]
    if (
        not isinstance(acquisitions, list)
        or len(acquisitions) != 2
        or any(
            not isinstance(creneau, dict)
            or set(creneau) != {"acquisition_id", "configuration_id"}
            for creneau in acquisitions
        )
    ):
        raise ErreurAutorisation(
            "portée : exactement deux créneaux fermés attendus"
        )
    if (
        portee["appels_fournisseur_max"] != 2
        or portee["appels_par_creneau"] != 1
        or portee["consommation_quota"] != "ABONNEMENTS_EXISTANTS"
        or portee["depense_incrementale"] != 0
        or portee["reprises_automatiques"] != 0
        or portee["reprises_manuelles"] != 0
        or portee["fallback"] != "NONE"
    ):
        raise ErreurAutorisation("portée divergente du contrat D-V1-04")
    return donnees


def _charger_journal_execution(chemin: Path) -> dict | None:
    """Journal privé validé, ou None lorsqu'aucune tentative n'existe."""
    if not os.path.lexists(chemin):
        return None
    infos = os.lstat(chemin)
    if stat.S_ISLNK(infos.st_mode) or not stat.S_ISREG(infos.st_mode):
        raise ErreurJournal("fichier régulier non symbolique attendu")
    try:
        journal = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurJournal(f"journal illisible : {erreur}") from erreur
    if (
        not isinstance(journal, dict)
        or set(journal) != {"schema_version", "entrees"}
        or journal["schema_version"] != SCHEMA_JOURNAL_EXECUTION
        or not isinstance(journal["entrees"], list)
    ):
        raise ErreurJournal("journal hors schéma fermé")
    for entree in journal["entrees"]:
        if not isinstance(entree, dict) or set(entree) != _CLES_ENTREE_JOURNAL:
            raise ErreurJournal("entrée de journal hors schéma fermé")
    return journal


def _ecrire_journal_execution(chemin: Path, journal: dict) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    descripteur = os.open(
        chemin, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
    )
    with os.fdopen(descripteur, "wb") as flux:
        flux.write(octets_canoniques(journal))
    os.chmod(chemin, 0o600)


def _controler_groupe(groupe: int) -> int:
    """Contrôle post-tentative du groupe de processus : le chef est récolté,
    tout membre restant est un descendant survivant ; il est alors tué et
    signalé, jamais laissé vivant."""
    try:
        os.killpg(groupe, 0)
    except ProcessLookupError:
        return 0
    except PermissionError:
        # Membre vivant appartenant à un autre utilisateur : signalé sans kill
        return 1
    try:
        os.killpg(groupe, signal.SIGKILL)
    except ProcessLookupError:
        return 0
    return 1


def _executer_acquisition(
    argv: list[str], entree: bytes, espace: Path, delai_secondes: int
) -> tuple[dict, int]:
    """Exécution bornée d'une tentative officielle : nouvelle session, délai
    officiel appliqué au groupe entier, contrôle des descendants après la
    tentative. Rend (execution, descendants)."""
    depart = time.monotonic()
    try:
        processus = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=espace,
            start_new_session=True,
        )
    except OSError as erreur:
        return (
            {
                "etat": "INCIDENT",
                "incident": "HARNESS_ERROR",
                "fait": f"lancement local impossible : {erreur}",
            },
            0,
        )
    try:
        stdout, stderr = processus.communicate(entree, timeout=delai_secondes)
    except subprocess.TimeoutExpired:
        groupe = processus.pid
        try:
            os.killpg(groupe, signal.SIGTERM)
            limite = time.monotonic() + 0.5
            while time.monotonic() < limite and processus.poll() is None:
                time.sleep(0.02)
            os.killpg(groupe, signal.SIGKILL)
        except ProcessLookupError:
            pass
        processus.wait()
        for tube in (processus.stdin, processus.stdout, processus.stderr):
            tube.close()
        return (
            {
                "etat": "INCIDENT",
                "incident": "HARNESS_ERROR",
                "fait": (
                    f"délai officiel de {delai_secondes} s dépassé : "
                    "terminaison envoyée au groupe de processus entier, puis "
                    "groupe tué et parent récolté ; aucun retry"
                ),
            },
            _controler_groupe(processus.pid),
        )
    latence_ms = int((time.monotonic() - depart) * 1000)
    descendants = _controler_groupe(processus.pid)
    return (
        {
            "etat": "OBSERVED",
            "sortie": {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            },
            "code_sortie": processus.returncode,
            "latence_ms": latence_ms,
        },
        descendants,
    )


def _projeter_identite_servie(
    stdout: str, stderr: str, attendus: tuple[str, ...]
) -> dict | None:
    """Divergence explicite d'identité servie : la première métadonnée
    'model:' dont la valeur ne correspond à aucune forme attendue, avec sa
    ligne exacte comme preuve attribuable. None sans métadonnée divergente ;
    une valeur concordante reste un écho, jamais une preuve d'identité."""
    for texte in (stdout, stderr):
        for correspondance in _MOTIF_IDENTITE_SERVIE.finditer(texte):
            valeur = correspondance.group(1)
            if valeur not in attendus:
                return {
                    "valeur": valeur,
                    "ligne": correspondance.group(0).strip(),
                }
    return None


def _refus_acquisition(fait: str) -> int:
    print(f"ECHEC {fait}")
    return 2


def acquerir_officiel(
    racine: Path, identifiant: str, racine_privee: Path | None = None
) -> int:
    """Exécute une seule fois le créneau autorisé de la configuration donnée.

    Fail-closed : toute divergence d'autorisation, de verrou, de
    configuration, de journal ou de créneau rend 2 avant tout processus
    fournisseur et sans reçu. Aucun retry, aucun fallback, aucune reprise.
    """
    if racine_privee is None:
        racine_privee = RACINE_PRIVEE_PRODUCTION
    if not _MOTIF_SLUG.match(identifiant):
        return _refus_acquisition(
            f"champ 'configuration_id' : '{identifiant}' n'est pas un slug "
            "stable ; identifiant refusé avant toute résolution de chemin"
        )
    try:
        autorisation = _charger_autorisation_acquisition(racine)
    except ErreurAutorisation as erreur:
        return _refus_acquisition(
            f"autorisation D-V1-04 absente ou divergente : {erreur} ; aucun "
            "processus fournisseur créé, aucun reçu écrit"
        )
    creneau_autorise = next(
        (
            creneau
            for creneau in autorisation["portee"]["acquisitions"]
            if creneau["configuration_id"] == identifiant
        ),
        None,
    )
    if creneau_autorise is None:
        return _refus_acquisition(
            f"configuration '{identifiant}' hors de la portée D-V1-04 : "
            "aucune autre configuration du panel n'est autorisée à acquérir"
        )
    acquisition_id = creneau_autorise["acquisition_id"]
    try:
        verrou = json.loads(
            (racine / CHEMIN_VERROU).read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        return _refus_acquisition(f"verrou de campagne illisible : {erreur}")
    if creneau_autorise not in verrou.get("creneaux", []):
        return _refus_acquisition(
            f"créneau '{acquisition_id}' absent du verrou de campagne"
        )
    entree_panel = next(
        (
            entree
            for entree in verrou.get("panel", [])
            if isinstance(entree, dict)
            and entree.get("configuration_id") == identifiant
        ),
        None,
    )
    if (
        entree_panel is None
        or entree_panel.get("disposition") != DISPOSITION_ELIGIBLE
        or entree_panel.get("verdict") != "READY"
    ):
        return _refus_acquisition(
            f"configuration '{identifiant}' non ELIGIBLE/READY dans le verrou"
        )
    chemin_configuration = racine / REGISTRE_OFFICIEL / f"{identifiant}.toml"
    if not chemin_configuration.is_file():
        return _refus_acquisition(
            f"configuration verrouillée absente : '{identifiant}'"
        )
    if _sha256_fichier(chemin_configuration) != entree_panel["configuration"].get(
        "sha256"
    ):
        return _refus_acquisition(
            f"configuration '{identifiant}' divergente du verrou "
            "(CONFIGURATION_CHANGED) : aucun appel"
        )
    try:
        configuration = _charger_configuration(chemin_configuration)
    except ErreurConfiguration as erreur:
        return _refus_acquisition(str(erreur))
    if configuration["configuration_id"] != identifiant:
        return _refus_acquisition(
            "champ 'configuration_id' divergent du fichier verrouillé"
        )
    harnais = configuration["harnais"]
    if harnais["delai_secondes"] != 0:
        return _refus_acquisition(
            "champ 'harnais.delai_secondes' : 0 attendu (aucune surcharge de "
            f"configuration), la couche officielle applique "
            f"{DELAI_ACQUISITION_OFFICIELLE} s par tentative"
        )
    if identifiant == CONFIGURATION_ACQUISITION_ANTIGRAVITY:
        if tuple(harnais["argv"]) != ARGV_DECLARE_ANTIGRAVITY or (
            "stdin_fichier" in harnais
        ):
            return _refus_acquisition(
                "descripteur Antigravity divergent du descripteur déclaré "
                "verrouillé : aucun appel"
            )
        if configuration["modele"]["demande"] != MODELE_ACQUISITION_ANTIGRAVITY:
            return _refus_acquisition(
                "modèle demandé divergent : sélection Antigravity explicite "
                f"'{MODELE_ACQUISITION_ANTIGRAVITY}' attendue, sans défaut "
                "implicite"
            )
    elif identifiant == CONFIGURATION_ACQUISITION_ZAI:
        if (
            tuple(harnais["argv"]) != ARGV_DECLARE_ZAI
            or harnais.get("stdin_fichier") != JETON_FICHIER_PROMPT
        ):
            return _refus_acquisition(
                "descripteur Z.AI divergent du descripteur exact conservé : "
                "aucun appel"
            )
    else:
        return _refus_acquisition(
            f"aucun adaptateur officiel pour '{identifiant}'"
        )
    sources: dict[str, dict] = {}
    for nom, relatif in (
        ("carte", CHEMIN_CARTE),
        ("paquet", CHEMIN_PAQUET),
        ("stimulus", CHEMIN_STIMULUS),
    ):
        chemin_source = racine / relatif
        if not chemin_source.is_file():
            return _refus_acquisition(f"source du reçu absente : {relatif}")
        sources[nom] = {"chemin": relatif, "sha256": _sha256_fichier(chemin_source)}
    if sources["stimulus"]["sha256"] != autorisation["stimulus"]["sha256"]:
        return _refus_acquisition(
            "stimulus divergent de l'autorisation D-V1-04 : aucun appel"
        )
    try:
        etat = _charger_etat(racine)
    except ErreurRestitution as erreur:
        return _refus_acquisition(str(erreur))
    creneau = f"{identifiant}:{sources['stimulus']['sha256']}"
    repertoire = _repertoire_recus(racine, etat)
    try:
        recus = _charger_recus(repertoire)
    except ErreurRecu as erreur:
        return _refus_acquisition(str(erreur))
    for _, existant in recus:
        if existant["payload"]["creneau"] == creneau:
            return _refus_acquisition(
                f"collision append-only : le créneau '{creneau}' est déjà "
                "occupé, aucun retry et aucune réécriture"
            )
    chemin_journal = (
        racine_privee / RELATIF_EXECUTION_XS08 / NOM_JOURNAL_EXECUTION
    )
    try:
        journal = _charger_journal_execution(chemin_journal)
    except ErreurJournal as erreur:
        return _refus_acquisition(f"journal d'exécution : {erreur} ; HOLD")
    if journal is None:
        journal = {"schema_version": SCHEMA_JOURNAL_EXECUTION, "entrees": []}
    for entree in journal["entrees"]:
        if entree["acquisition_id"] == acquisition_id:
            return _refus_acquisition(
                f"créneau '{acquisition_id}' déjà consommé selon le journal : "
                "aucun second enregistrement du même créneau, aucun retry"
            )
        if entree["etat_terminal"] == "IDENTITY_MISMATCH":
            return _refus_acquisition(
                "HOLD : une identité servie divergente est journalisée, "
                "aucun appel suivant avant arbitrage propriétaire"
            )
        if entree["descendants"]:
            return _refus_acquisition(
                "HOLD : un descendant survivant est journalisé, aucun appel "
                "suivant avant arbitrage propriétaire"
            )
        if entree["recu"] is None:
            return _refus_acquisition(
                "HOLD : une tentative sans reçu est journalisée, aucun appel "
                "suivant avant arbitrage propriétaire"
            )
    espace_tentative = (
        racine_privee / RELATIF_EXECUTION_XS08 / NOM_RUNTIME_XS08 / acquisition_id
    )
    if os.path.lexists(espace_tentative):
        return _refus_acquisition(
            f"espace réel de tentative déjà présent pour '{acquisition_id}' : "
            "le créneau est consommé, aucun retry et aucun nettoyage"
        )
    stimulus_octets = (racine / CHEMIN_STIMULUS).read_bytes()
    if identifiant == CONFIGURATION_ACQUISITION_ANTIGRAVITY:
        prefixe = ["agy", *FLAGS_ACQUISITION_ANTIGRAVITY]
        argv_execute = [*prefixe, stimulus_octets.decode("utf-8")]
        argv_resolu = [*prefixe, JETON_STIMULUS_UTF8]
        entree_stdin = b""
        mode_stdin = "aucun"
    else:
        argv_resolu = list(ARGV_DECLARE_ZAI)
        entree_stdin = stimulus_octets
        mode_stdin = JETON_FICHIER_PROMPT
    if any(element in FLAGS_INTERDITS_ACQUISITION for element in argv_resolu):
        return _refus_acquisition(
            "flag interdit présent dans le descripteur résolu : aucun appel"
        )
    espace = espace_tentative / "espace"
    espace.mkdir(parents=True, exist_ok=False)
    if identifiant == CONFIGURATION_ACQUISITION_ZAI:
        argv_execute = [
            element.replace(JETON_ESPACE_ISOLE, str(espace))
            for element in ARGV_DECLARE_ZAI
        ]
    depart_tentative = time.monotonic()
    execution, descendants = _executer_acquisition(
        argv_execute, entree_stdin, espace, DELAI_ACQUISITION_OFFICIELLE
    )
    latence_tentative_ms = int((time.monotonic() - depart_tentative) * 1000)
    if execution["etat"] == "OBSERVED":
        # La sortie texte candidate est conservée dans l'espace réel privé
        (espace_tentative / "sortie-stdout.txt").write_text(
            execution["sortie"]["stdout"], encoding="utf-8"
        )
        (espace_tentative / "sortie-stderr.txt").write_text(
            execution["sortie"]["stderr"], encoding="utf-8"
        )
        attendus = (
            (MODELE_ACQUISITION_ANTIGRAVITY,)
            if identifiant == CONFIGURATION_ACQUISITION_ANTIGRAVITY
            else MODELES_ATTENDUS_ZAI
        )
        divergence = _projeter_identite_servie(
            execution["sortie"]["stdout"],
            execution["sortie"]["stderr"],
            attendus,
        )
        if divergence is not None:
            execution = {
                "etat": "INCIDENT",
                "incident": "IDENTITY_MISMATCH",
                "fait": (
                    "métadonnée explicite d'identité servie divergente du "
                    "modèle demandé : le créneau est consommé, HOLD avant "
                    "tout appel suivant"
                ),
                "preuve_attribuable": divergence["ligne"],
            }
        elif execution["code_sortie"] != 0 and execution["sortie"]["stdout"] == "":
            # Erreur locale ou wrapper défaillant : sans sortie candidate, le
            # code client non nul ne prouve aucune observation du fournisseur
            execution = {
                "etat": "INCIDENT",
                "incident": "HARNESS_ERROR",
                "fait": (
                    f"code client {execution['code_sortie']} sans sortie "
                    "candidate : erreur du harnais local, stderr conservée "
                    "dans l'espace réel privé, créneau consommé sans retry"
                ),
            }
    latence_journal = (
        execution["latence_ms"]
        if execution["etat"] == "OBSERVED"
        else latence_tentative_ms
    )
    charge = {
        "measurement_profile": PROFIL_MESURE_RECU,
        "creneau": creneau,
        "predecesseur_adresse_contenu": (
            recus[-1][1]["content_address"]["sha256"] if recus else None
        ),
        "carte": sources["carte"],
        "paquet": sources["paquet"],
        "stimulus": sources["stimulus"],
        "configuration": {
            "identifiant": identifiant,
            "chemin": (REGISTRE_OFFICIEL / f"{identifiant}.toml").as_posix(),
            "sha256": _sha256_fichier(chemin_configuration),
        },
        "plan_declare": {"etat": "DECLARE", "champs": configuration["plan"]},
        "interface_declaree": {
            "etat": "DECLARE",
            "champs": configuration["interface"],
        },
        "quota_observe": INCONNU,
        "requete": {
            "etat": "REQUESTED",
            "argv_resolu": argv_resolu,
            "mode_stdin": mode_stdin,
            "espace_de_travail": JETON_ESPACE_ISOLE,
        },
        "execution": execution,
        "provenance_servie": INCONNU,
    }
    enveloppe = {
        "schema_version": SCHEMA_RECU,
        "content_address": {
            "algorithm": "SHA256",
            "sha256": adresse_canonique(charge),
        },
        "payload": charge,
    }
    adresse: str | None = enveloppe["content_address"]["sha256"]
    etat_terminal = (
        "OBSERVED" if execution["etat"] == "OBSERVED" else execution["incident"]
    )
    try:
        _valider_recu(enveloppe)
        destination = repertoire / f"{adresse}.json"
        with open(destination, "xb") as fichier:
            fichier.write(octets_canoniques(enveloppe))
    except (ErreurRecu, OSError) as erreur:
        # Tentative sans reçu : journalisée telle quelle, HOLD obligatoire
        print(f"ECHEC reçu non écrit après tentative : {erreur} ; HOLD")
        adresse = None
        destination = None
    code_commande = 0 if adresse is not None and descendants == 0 else 1
    journal["entrees"].append(
        {
            "acquisition_id": acquisition_id,
            "configuration_id": identifiant,
            "invocation_publique": (
                "uv run tools/campagne_v1.py acquerir --officiel "
                f"--configuration {identifiant}"
            ),
            "code": code_commande,
            "recu": adresse,
            "etat_terminal": etat_terminal,
            "latence_ms": latence_journal,
            "retry": 0,
            "descendants": descendants,
        }
    )
    _ecrire_journal_execution(chemin_journal, journal)
    if destination is not None:
        print(
            "reçu V1 abonnement écrit : "
            f"{destination.relative_to(racine).as_posix()}"
        )
        print(f"créneau : {creneau}")
        print(f"adresse de contenu : {adresse}")
    print(f"état terminal : {etat_terminal}")
    if execution["etat"] == "INCIDENT":
        print(
            f"incident : {execution['incident']} — {execution['fait']}"
        )
    print(f"descendants survivants : {descendants}")
    if descendants:
        print(
            "ECHEC descendant survivant détecté après la tentative : groupe "
            "tué, HOLD avant tout appel suivant"
        )
    return code_commande


def _charger_verrou_restitution(racine: Path) -> tuple[str, dict, str] | None:
    """Verrou public validé pour le rendu : (chemin relatif, verrou, SHA-256),
    ou None lorsque le verrou n'est pas matérialisé."""
    chemin = racine / CHEMIN_VERROU
    if not os.path.lexists(chemin):
        return None
    infos = os.lstat(chemin)
    if stat.S_ISLNK(infos.st_mode) or not stat.S_ISREG(infos.st_mode):
        raise ErreurRestitution(
            "verrou de campagne : fichier régulier non symbolique attendu"
        )
    try:
        verrou = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurRestitution(f"verrou de campagne illisible : {erreur}") from erreur
    if not isinstance(verrou, dict) or set(verrou) != _CLES_VERROU_PUBLIC:
        raise ErreurRestitution("verrou de campagne : clés hors schéma fermé")
    if verrou["schema_version"] != SCHEMA_VERROU:
        raise ErreurRestitution(
            f"verrou de campagne : schéma '{SCHEMA_VERROU}' attendu"
        )
    panel = verrou["panel"]
    if not isinstance(panel, list) or verrou["cardinalite_declaree"] != len(panel):
        raise ErreurRestitution(
            "verrou de campagne : cardinalité déclarée incohérente"
        )
    for entree in panel:
        if not isinstance(entree, dict) or set(entree) != _CLES_ENTREE_PANEL_VERROU:
            raise ErreurRestitution(
                "verrou de campagne : entrée de panel hors schéma fermé"
            )
    creneaux = verrou["creneaux"]
    if not isinstance(creneaux, list) or verrou["cardinalite_eligible"] != len(
        creneaux
    ):
        raise ErreurRestitution(
            "verrou de campagne : cardinalité éligible incohérente"
        )
    sources = verrou["sources_plans"]
    if (
        not isinstance(sources, dict)
        or sources.get("chemin") != CHEMIN_SOURCES_PLANS.as_posix()
        or not isinstance(sources.get("sha256"), str)
        or not _MOTIF_SHA256.match(sources["sha256"])
    ):
        raise ErreurRestitution(
            "verrou de campagne : référence de sources de plans invalide"
        )
    engagements = verrou["engagements_prives"]
    if not isinstance(engagements, list) or any(
        not isinstance(engagement, dict) for engagement in engagements
    ):
        raise ErreurRestitution(
            "verrou de campagne : engagements privés hors schéma fermé"
        )
    for engagement in engagements:
        if engagement.get("kind") == "manifeste-ordre":
            # jamais d'empreinte directe du manifeste : commitment masqué seul
            if set(engagement) != {
                "kind",
                "mode",
                "size",
                "commitment_method",
                "commitment",
            } or engagement["commitment_method"] != METHODE_ENGAGEMENT_MANIFESTE:
                raise ErreurRestitution(
                    "verrou de campagne : engagement du manifeste hors schéma "
                    "masqué fermé"
                )
        elif set(engagement) != {"kind", "mode", "sha256", "size"}:
            raise ErreurRestitution(
                "verrou de campagne : engagements privés hors schéma fermé"
            )
    return CHEMIN_VERROU.as_posix(), verrou, _sha256_fichier(chemin)


def _articles_verrou(relatif_verrou: str, sha_verrou: str, verrou: dict) -> list[str]:
    """Articles régénérables à l'identique depuis le verrou public."""
    src_verrou = _span_source(relatif_verrou, sha_verrou, SECTION_VERROU)
    sources = verrou["sources_plans"]
    src_sources = _span_source(
        sources["chemin"], sources["sha256"], SECTION_SOURCES_PLANS
    )
    creneaux = verrou["creneaux"]
    reprises = verrou["reprises"]
    autorite = verrou["autorite_execution"]
    zero = verrou["preuve_zero_execution"]
    fraicheur = verrou["fraicheur"]
    ordre = verrou["engagement_ordre"]
    exclusions = verrou["cardinalite_declaree"] - verrou["cardinalite_eligible"]
    liste_creneaux = " · ".join(
        f"<code>{_echapper(creneau['acquisition_id'])}</code> pour "
        f"<code>{_echapper(creneau['configuration_id'])}</code>"
        for creneau in creneaux
    )
    articles = [
        _article(
            "fait",
            "<p><strong>Verrou de campagne abonnement matérialisé et vérifié"
            f"</strong> — schéma <code>{_echapper(verrou['schema_version'])}"
            "</code> · panel fermé : cardinalité déclarée "
            f"<code>{_echapper(verrou['cardinalite_declaree'])}</code> · "
            f"éligibles <code>{_echapper(verrou['cardinalite_eligible'])}</code> · "
            f"exclusions <code>{exclusions}</code>.</p>"
            f"<p>créneaux planifiés <code>{len(creneaux)}</code> : {liste_creneaux} "
            "· créneaux par configuration éligible "
            f"<code>{_echapper(verrou['creneaux_par_configuration_eligible'])}</code> "
            f"· reprises automatiques <code>{_echapper(reprises['automatiques'])}"
            "</code> · reprises manuelles "
            f"<code>{_echapper(reprises['manuelles'])}</code> · fallbacks "
            f"<code>{_echapper(verrou['fallbacks'])}</code> — aucun créneau n'est "
            "exécuté par le verrou.</p>"
            "<p>autorité d'acquisition D-V1-04 "
            f"<code>{_echapper(autorite['autorite_acquisition_d_v1_04'])}</code> · "
            f"acquisition <code>{_echapper(autorite['acquisition'])}</code> · appel "
            f"fournisseur <code>{_echapper(autorite['appel_fournisseur'])}</code> · "
            "consommation de quota "
            f"<code>{_echapper(autorite['consommation_quota'])}</code> · dépense "
            f"<code>{_echapper(autorite['depense'])}</code> — commandes fournisseur "
            f"lancées <code>{_echapper(zero['commandes_fournisseur_lancees'])}</code>, "
            f"créneaux exécutés <code>{_echapper(zero['creneaux_executes'])}</code>, "
            f"reprises exécutées <code>{_echapper(zero['reprises_executees'])}</code>."
            "</p>" + src_verrou,
            ' data-verrou="campagne"',
        )
    ]
    for entree in verrou["panel"]:
        plan = entree["plan"]
        cause = entree["cause"] if entree["cause"] is not None else "aucune"
        attestation = entree["attestation"]
        contenu = (
            f"<p><strong>{_echapper(entree['configuration_id'])}</strong> — verdict "
            f"de préflight <code>{_echapper(entree['verdict'])}</code> · cause "
            f"<code>{_echapper(cause)}</code> · disposition "
            f"<code>{_echapper(entree['disposition'])}</code>. Une disposition "
            "éligible désigne une route prouvée disponible, jamais un modèle servi "
            "ni un résultat ; l'identité réellement servie reste "
            "<code>INCONNU</code>.</p>"
            f"<p>attestation <code>{_echapper(attestation['reference'])}</code> du "
            f"<code>{_echapper(attestation['date'])}</code> : détention déclarée de "
            "l'abonnement, ni observation d'identité servie, ni facture, ni preuve "
            "de disponibilité.</p>"
            f"<p>plan validé <code>{_echapper(plan['nom'])}</code> · tarif catalogue "
            f"<code>{_echapper(plan['prix_montant'])}</code> "
            f"<code>{_echapper(plan['prix_devise'])}</code> par période "
            f"<code>{_echapper(plan['periode'])}</code> · publication "
            f"<code>{_echapper(plan['date_publication'])}</code> · consultation "
            f"<code>{_echapper(plan['date_consultation'])}</code> · classe "
            f"<code>{_echapper(plan['classe_msw'])}</code> · source officielle "
            f"<code>{_neutraliser_schema(_echapper(plan['source_url']))}</code></p>"
            + _span_source(
                entree["configuration"]["chemin"],
                entree["configuration"]["sha256"],
                SECTION_REGISTRE,
            )
            + _span_source(
                entree["preflight"]["chemin"],
                entree["preflight"]["sha256"],
                SECTION_PREFLIGHT,
            )
            + src_sources
            + src_verrou
        )
        if plan["classe_msw"] == CLASSE_PLAN_DEDUCTION:
            premisses = " ; ".join(plan["premisses"])
            articles.append(
                _article(
                    "deduction",
                    contenu,
                    f' data-verrou-panel="{entree["configuration_id"]}"'
                    f' data-premisses="{premisses}"',
                )
            )
        else:
            articles.append(
                _article(
                    "fait",
                    contenu,
                    f' data-verrou-panel="{entree["configuration_id"]}"',
                )
            )
    evenements = " · ".join(
        f"<code>{_echapper(evenement)}</code>"
        for evenement in fraicheur["evenements_materiels"]
    )
    articles.append(
        _article(
            "fait",
            f"<p>règle de fraîcheur <code>{_echapper(fraicheur['regle'])}</code> — "
            "le temps écoulé seul n'invalide aucune preuve du verrou. Événements "
            f"matériels fermés : {evenements}. Effet "
            f"<code>{_echapper(fraicheur['effet'])}</code> : toute observation "
            "impossible reste <code>INCONNU</code> et entraîne l'abstention "
            "correspondante.</p>" + src_verrou,
        )
    )
    items = " ".join(f"<code>{_echapper(item)}</code>" for item in ordre["items"])
    positions = " ".join(
        f"<code>{_echapper(position)}</code>" for position in ordre["positions"]
    )
    fragments_engagements = []
    for engagement in verrou["engagements_prives"]:
        if engagement["kind"] == "manifeste-ordre":
            fragments_engagements.append(
                f"<p>engagement privé <code>{_echapper(engagement['kind'])}"
                "</code> : mode "
                f"<code>{_echapper(engagement['mode'])}</code> · "
                f"<code>{_echapper(engagement['size'])}</code> octets · méthode "
                f"<code>{_echapper(engagement['commitment_method'])}</code> · "
                "commitment "
                f"<code>{_echapper(engagement['commitment'])}</code> — engagement "
                "masqué : aucune empreinte directe du manifeste n'est publiée, le "
                "commitment n'est vérifiable qu'avec le sel privé lors de la "
                "révélation ; contenu et chemin jamais publiés.</p>"
            )
        else:
            fragments_engagements.append(
                f"<p>engagement privé <code>{_echapper(engagement['kind'])}"
                "</code> : mode "
                f"<code>{_echapper(engagement['mode'])}</code> · "
                f"<code>{_echapper(engagement['size'])}</code> octets · SHA-256 "
                f"<code>{_echapper(engagement['sha256'])}</code> — empreinte "
                "seule, contenu et chemin jamais publiés.</p>"
            )
    engagements = "".join(fragments_engagements)
    articles.append(
        _article(
            "fait",
            f"<p>engagement d'ordre aveugle — méthode "
            f"<code>{_echapper(ordre['methode'])}</code> · campagne "
            f"<code>{_echapper(ordre['campaign_id'])}</code> · items {items} · "
            f"positions {positions} · publication "
            f"<code>{_echapper(ordre['publication'])}</code> : la correspondance "
            "entre créneaux et items reste engagée dans le manifeste privé, "
            "jamais publiée.</p>" + engagements + src_verrou,
        )
    )
    articles.append(
        _article(
            "fait",
            f"<p>sémantique des prix <code>{SEMANTIQUE_PRIX_PLANS}</code> : chaque "
            "montant est un tarif catalogue standard mensuel en USD, hors taxe, "
            "remise et facturation locale ; il ne prouve pas le montant réellement "
            "facturé. Une page officielle actuelle non datée conserve son URL et "
            "porte <code>date_publication</code> <code>NON_DEFINI</code>.</p>"
            + src_sources
            + src_verrou,
        )
    )
    return articles


def _span_source(chemin: str, sha256: str, section: str) -> str:
    return (
        f'<span class="source" data-chemin="{chemin}" data-sha256="{sha256}">'
        f"source : <code>{chemin}</code> ({section}) · SHA-256 <code>{sha256}</code></span>"
    )


def _article(classe: str, contenu: str, attributs: str = "") -> str:
    return f'<article class="affirmation" data-classe="{classe}"{attributs}>{contenu}</article>'


def _rendre_page(racine: Path) -> bytes:
    etat = _charger_etat(racine)
    repertoire = _repertoire_recus(racine, etat)
    _compter_recus(repertoire)
    # Tout fichier du répertoire doit être un reçu V1 valide et chaîné ; les
    # acquisitions officielles D-V1-04 sont restituées sans jamais changer la
    # conclusion ABSTENTION du panel, faute d'acceptabilité officielle.
    recus_locaux, recus_officiels = _partitionner_recus(racine, etat)
    configurations = _configurations_officielles(racine)
    qualification = _charger_recu_qualification(racine)
    preflights = _charger_recus_preflight(racine)
    verrou_charge = _charger_verrou_restitution(racine)
    autorisation = _charger_autorisation_restitution(racine)
    registre_validation = _charger_registre_validation(racine)
    jeton_panel, jeton_acquisitions, jeton_conclusion = _jetons_attendus(
        etat, len(recus_officiels), len(configurations)
    )
    etat_relatif = CHEMIN_ETAT.as_posix()
    empreintes = _empreintes_sources(
        racine, etat_relatif, tuple(chemin for chemin, _ in configurations)
    )
    empreintes.update({relatif: sha for relatif, _, sha in recus_locaux})
    empreintes.update({relatif: sha for relatif, _, sha in recus_officiels})
    empreintes.update({relatif: sha for relatif, _, sha in preflights})
    if qualification is not None:
        empreintes[qualification[0]] = qualification[2]
    if autorisation is not None:
        empreintes[autorisation[0]] = autorisation[2]
    if registre_validation is not None:
        empreintes[registre_validation[0]] = registre_validation[2]
    relatif_sources_plans = CHEMIN_SOURCES_PLANS.as_posix()
    if verrou_charge is not None:
        empreintes[verrou_charge[0]] = verrou_charge[2]
        try:
            empreintes[relatif_sources_plans] = _sha256_fichier(
                racine / CHEMIN_SOURCES_PLANS
            )
        except OSError as erreur:
            raise ErreurRestitution(
                "sources de plans absentes alors que le verrou est "
                f"matérialisé : {erreur}"
            ) from erreur

    def src(chemin: str, section: str) -> str:
        return _span_source(chemin, empreintes[chemin], section)

    spans_registre = "".join(
        src(chemin, SECTION_REGISTRE) for chemin, _ in configurations
    )

    prd = "docs/PRD.md"
    ard = "docs/ARD.md"
    rules = "docs/RULES.md"
    manifeste = "tasks/dev/pre-cadrage-entretien-client/manifeste-paquet.json"
    rapport_v0 = (
        "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
        "rapport-decision-m10-2-v1/rapport-interne.md"
    )
    chemin_recus = (_RACINE_CAMPAGNE_V1 / etat["repertoire_recus"]).as_posix()

    sections: list[str] = []

    sections.append(
        "<section id=\"mesure-v1\"><h2>Ce que la V1 abonnement mesure</h2>"
        + _article(
            "fait",
            "<p>La V1 ajoute le profil de mesure abonnement, qui compare l'expérience "
            "réelle de produits par abonnement. L'identité comprend le produit, le plan, "
            "les quotas, les resets, l'interface, le harnais et l'intervention humaine. "
            "Un même modèle dans deux produits ou plans ne crée pas une identité "
            "commune.</p>" + src(prd, "section 14"),
        )
        + _article(
            "fait",
            "<p>Les versions produit sont cumulatives et les profils de mesure sont "
            "parallèles. Chaque profil est qualifié indépendamment. Aucune comparaison "
            "inter-profils n'est permise sans contrat commun explicite.</p>"
            + src(ard, "section 7"),
        )
        + "</section>"
    )

    sections.append(
        "<section id=\"question-decision\"><h2>Question et décision V1</h2>"
        + _article(
            "fait",
            "<p>Question V1 : quelle expérience réelle offrent les produits par "
            "abonnement du panel, sous les identités complètes du profil abonnement ? "
            "La décision servie est le choix d'une configuration abonnement, ou "
            "l'abstention correspondante lorsque les preuves manquent.</p>"
            + src(prd, "section 14")
            + src(rules, "U-018"),
        )
        + "</section>"
    )

    # Fidélité MSW : avec un reçu local présent, l'absence d'acquisition et de
    # reçu se dit uniquement à portée officielle qualifiée, jamais littéralement
    if recus_officiels:
        absence_acquisition = (
            f"{len(recus_officiels)} acquisition(s) officielle(s) sous "
            "D-V1-04 existent avec reçu, sans acceptabilité officielle "
            "établie ni notation"
        )
        premisse_recus = (
            f"{len(recus_officiels)} reçu(s) d'acquisition officielle et "
            f"{len(recus_locaux)} reçu(s) de démonstration locale hors panel "
            "officiel dans le répertoire de reçus V1, sans acceptabilité "
            "officielle établie"
        )
    elif recus_locaux:
        absence_acquisition = (
            "aucune acquisition officielle n'existe ; le reçu de démonstration "
            "locale, hors panel officiel, n'établit aucune mesure du panel"
        )
        premisse_recus = (
            f"{len(recus_locaux)} reçu(s) de démonstration locale hors panel "
            "officiel et aucun reçu rattaché au panel officiel dans le "
            "répertoire de reçus V1"
        )
    else:
        absence_acquisition = "aucune acquisition n'existe"
        premisse_recus = "zéro reçu dans le répertoire de reçus V1"

    if configurations:
        article_panel_courant = _article(
            "fait",
            f"<p><code id=\"jeton-panel\">{jeton_panel}</code> — le registre officiel "
            "versionné déclare ces configurations abonnement ; aucune n'est mesurée.</p>"
            + spans_registre,
        )
        article_conclusion = _article(
            "deduction",
            f"<p><code id=\"jeton-conclusion\">{jeton_conclusion}</code> — déduction "
            "raisonnée : des configurations sont déclarées mais aucune n'est mesurée "
            f"et {absence_acquisition} ; une absence de preuve n'est jamais "
            "transformée en résultat favorable, donc la seule conclusion dérivable "
            "est l'abstention. Aucune valeur de remplacement n'est créée.</p>"
            + src(rules, "U-018"),
            ' data-premisses="configurations déclarées et non mesurées selon le '
            f"registre officiel versionné ; {premisse_recus} ; "
            'règle U-018 de docs/RULES.md"',
        )
    else:
        article_panel_courant = _article(
            "fait",
            f"<p><code id=\"jeton-panel\">{jeton_panel}</code> — l'état V1 versionné ne "
            "déclare aucune configuration abonnement.</p>"
            + src(etat_relatif, "état V1 versionné"),
        )
        article_conclusion = _article(
            "deduction",
            f"<p><code id=\"jeton-conclusion\">{jeton_conclusion}</code> — déduction "
            f"raisonnée : le panel est vide et {absence_acquisition} ; une absence "
            "de preuve n'est jamais transformée en résultat favorable, donc la seule "
            "conclusion dérivable est l'abstention. Aucune valeur de remplacement n'est "
            "créée.</p>" + src(rules, "U-018"),
            " data-premisses=\"panel vide selon l'état V1 versionné ; "
            f'{premisse_recus} ; règle U-018 de docs/RULES.md"',
        )

    if recus_officiels:
        texte_recus = (
            f"répertoire de reçus V1 <code>{chemin_recus}</code> existe et contient "
            f"{len(recus_officiels)} reçu(s) d'acquisition officielle sous "
            f"D-V1-04 et {len(recus_locaux)} reçu(s) de démonstration locale "
            "hors panel officiel."
        )
    elif recus_locaux:
        texte_recus = (
            f"répertoire de reçus V1 <code>{chemin_recus}</code> existe et contient "
            f"{len(recus_locaux)} reçu(s) de démonstration locale hors panel "
            "officiel, et aucune acquisition officielle."
        )
    else:
        texte_recus = (
            f"répertoire de reçus V1 <code>{chemin_recus}</code> existe et ne "
            "contient aucun reçu."
        )
    sections.append(
        "<section id=\"etat-v1\"><h2>État V1 courant</h2>"
        + article_panel_courant
        + _article(
            "fait",
            f"<p><code id=\"jeton-acquisitions\">{jeton_acquisitions}</code> — le "
            + texte_recus
            + "</p>"
            + src(etat_relatif, "état V1 versionné"),
        )
        + article_conclusion
        + "</section>"
    )

    if configurations:
        sections.append(
            "<section id=\"panel-officiel\"><h2>Panel officiel déclaré</h2>"
            "<p>Chaque entrée reprend un fichier du registre officiel versionné. "
            "Elle est déclarée et non mesurée : tout champ non observé reste "
            "<code>INCONNU</code>, le modèle demandé est marqué REQUESTED, "
            "et aucune activité de compte, aucune authentification et aucune "
            "disponibilité n'en est déduite. "
            + (
                f"{len(preflights)} reçu(s) de préflight de disponibilité "
                "existent, restitués plus bas : ils sondent une route sans "
                "générer, sans acquérir et sans mesurer. "
                if preflights
                else "Aucun préflight n'existe. "
            )
            + (
                (
                    f"{len(recus_officiels)} acquisition(s) officielle(s) "
                    "sous D-V1-04 existent avec reçus, restituées plus bas ; "
                    "aucune acceptabilité officielle n'est établie et aucune "
                    "configuration n'est notée."
                )
                if recus_officiels
                else (
                    "Aucune acquisition officielle et aucune mesure du panel "
                    "n'existe ; le reçu de démonstration locale reste hors "
                    "panel officiel."
                    if recus_locaux
                    else "Aucune acquisition et aucune mesure n'existe."
                )
            )
            + "</p>"
            + "".join(
                _article_panel(chemin, empreintes[chemin], donnees)
                for chemin, donnees in configurations
            )
            + "</section>"
        )

    if configurations:
        sections.append(
            "<section id=\"autorisations\"><h2>Aperçu des autorisations</h2>"
            "<p>Faits déclarés issus des fichiers TOML du registre officiel "
            "versionné, rendus avant toute action distante. Aucune "
            "authentification, aucune lecture de compte et aucune inspection de "
            "facturation ou de quota réel n'a eu lieu : le compte concerné reste "
            "<code>INCONNU</code>, le quota engagé et la dépense engagée sont des "
            "engagements déclarés, jamais une consommation observée ni une "
            "disponibilité.</p>"
            + "".join(
                _article_autorisations(chemin, empreintes[chemin], donnees)
                for chemin, donnees in configurations
            )
            + "</section>"
        )

    if recus_locaux:
        sections.append(
            "<section id=\"acquisition-locale\"><h2>Acquisition locale de "
            "démonstration, hors panel officiel</h2>"
            "<p>Chaque entrée reprend un reçu V1 abonnement local versionné, "
            "adressé par contenu et append-only. Cette démonstration du harnais "
            "est hors panel officiel : elle ne classe aucune configuration, ne "
            "modifie aucune conclusion relative au panel abonnement et sa "
            "lisibilité n'améliore aucune preuve.</p>"
            + "".join(
                _article_acquisition_locale(relatif, sha, enveloppe)
                for relatif, enveloppe, sha in recus_locaux
            )
            + "</section>"
        )

    if qualification is not None:
        relatif_qualification, recu_qualification, sha_qualification = qualification
        sections.append(
            "<section id=\"qualification-harnais\"><h2>Qualification du harnais "
            "V1</h2>"
            "<p>Cette entrée reprend le reçu de qualification versionné. La "
            "qualification rejoue les témoins approuvés du paquet contre le "
            "harnais V1 et le validateur du paquet ; elle ne mesure aucune "
            "configuration, ne produit aucun classement et ne compare aucun "
            "outillage.</p>"
            + _article_qualification(
                relatif_qualification, sha_qualification, recu_qualification
            )
            + "</section>"
        )

    if preflights:
        sections.append(
            "<section id=\"preflights\"><h2>Préflights de disponibilité</h2>"
            "<p>Chaque entrée reprend un reçu de préflight versionné, sous "
            "l'autorité groupée unique des préflights abonnement. Un préflight "
            "sonde la disponibilité d'une route par des commandes non "
            "génératives : il n'acquiert rien, ne mesure rien, ne note rien et "
            "ne consomme aucun créneau d'acquisition. Tout champ non observé "
            "reste <code>INCONNU</code> ; une aide de syntaxe ne prouve ni le "
            "plan ni l'exposition d'un modèle.</p>"
            + "".join(
                _article_preflight(relatif, sha, recu)
                for relatif, recu, sha in preflights
            )
            + "</section>"
        )

    if verrou_charge is not None:
        relatif_verrou, verrou, sha_verrou = verrou_charge
        sections.append(
            "<section id=\"verrou-campagne\"><h2>Verrou de campagne "
            "abonnement</h2>"
            "<p>Le verrou versionné fige le panel, les plans validés et leurs "
            "provenances, les créneaux, les reprises, les règles de fraîcheur "
            "et l'engagement d'ordre aveugle. Il ne confère aucune autorité "
            "d'acquisition, n'exécute aucun créneau et ne publie aucun contenu "
            "privé : seules les empreintes des engagements privés sont "
            "publiées.</p>"
            + "".join(_articles_verrou(relatif_verrou, sha_verrou, verrou))
            + "</section>"
        )

    if autorisation is not None:
        relatif_autorisation, donnees_autorisation, sha_autorisation = autorisation
        sections.append(
            "<section id=\"autorite-acquisition\"><h2>Autorité d'acquisition "
            "D-V1-04</h2>"
            "<p>Le verrou de campagne versionné conserve, inchangé, son champ "
            "d'exécution historique <code>NOT_GRANTED</code> : le verrou ne "
            "confère aucune autorité. L'autorité d'acquisition vit dans "
            "l'artefact séparé restitué ici, qui référence le commentaire "
            "propriétaire, le verrou et le stimulus par empreintes. Cette "
            "autorité couvre exactement deux créneaux, sans reprise, sans "
            "fallback et sans dépense incrémentale.</p>"
            + _article_autorisation_acquisition(
                relatif_autorisation, sha_autorisation, donnees_autorisation
            )
            + "</section>"
        )

    if recus_officiels:
        sections.append(
            "<section id=\"acquisitions-officielles\"><h2>Acquisitions "
            "officielles sous D-V1-04</h2>"
            "<p>Chaque entrée reprend un reçu V1 abonnement versionné, adressé "
            "par contenu et append-only, produit par une exécution unique de "
            "son créneau autorisé. Les exécutions et incidents sont restitués "
            "tels quels : quota consommé et identité servie restent "
            "<code>INCONNU</code> sans observation prouvée, aucune "
            "acceptabilité officielle n'est établie et aucune conclusion "
            "n'en est tirée.</p>"
            + "".join(
                _article_acquisition_officielle(relatif, sha, enveloppe)
                for relatif, enveloppe, sha in recus_officiels
            )
            + "</section>"
        )

    if registre_validation is not None:
        relatif_registre, registre, sha_registre = registre_validation
        sections.append(
            '<section id="validation-automatique"><h2>Validation automatique '
            "des sorties candidates</h2>"
            "<p>Cette section reprend le registre de couverture et de "
            "verdicts versionné, produit par <code>valider</code> : chaque "
            "sortie candidate, et elle seule, reçoit un verdict "
            "<code>PASS</code>, <code>FAIL</code> ou "
            "<code>HARNESS_ERROR</code> ; un échec porte la porte en cause et "
            "l'origine <code>CANDIDATE_ERROR</code> ou "
            "<code>HARNESS_ERROR</code>. Une acquisition sans sortie "
            "candidate ne reçoit aucun verdict candidat et la cause de son "
            "reçu reste inchangée. Ces verdicts automatiques n'établissent "
            "aucune acceptabilité officielle : celle-ci exige la revue "
            "humaine aveugle, à venir.</p>"
            + _article_couverture_validation(
                relatif_registre, sha_registre, registre
            )
            + "".join(
                _article_validation(entree, relatif_registre, sha_registre)
                for entree in registre["entrees"]
            )
            + "</section>"
        )

    if configurations:
        article_identites_inconnues = _article(
            "fait",
            "<p>Les identités du panel sont déclarées, jamais mesurées : prix, "
            "devise, période, quotas, resets, versions d'interface et étapes "
            "non observés restent <code>INCONNU</code> champ par champ jusqu'à une "
            "observation autorisée.</p>" + spans_registre,
        )
    else:
        article_identites_inconnues = _article(
            "fait",
            "<p>Aucune identité abonnement n'est déclarée : produit, plan, quotas, "
            "resets, interface, harnais et intervention humaine restent "
            "<code>INCONNU</code> pour tout candidat futur.</p>"
            + src(etat_relatif, "état V1 versionné"),
        )

    sections.append(
        "<section id=\"inconnues\"><h2>Ce qui reste inconnu</h2>"
        + article_identites_inconnues
        + _article(
            "fait",
            (
                (
                    f"<p>{len(recus_officiels)} reçu(s) V1 rattachés au panel "
                    "officiel existent : leurs exécutions et incidents sont "
                    "restitués tels quels. L'acceptabilité officielle, la "
                    "couverture de mesure et toute conclusion restent non "
                    "établies ; les quotas consommés et l'identité servie "
                    "restent <code>INCONNU</code> sans observation prouvée. "
                    "Aucune sortie officiellement acceptable n'étant établie, "
                    "tout coût par sortie officiellement acceptable serait "
                    "<code>NON_DEFINI</code>.</p>"
                    + "".join(
                        src(relatif, SECTION_RECU_OFFICIEL)
                        for relatif, _, _ in recus_officiels
                    )
                )
                if recus_officiels
                else (
                    "<p>Aucun reçu V1 rattaché au panel officiel n'existe : "
                    "expérience réelle, coûts, latences et couverture du panel "
                    "restent <code>INCONNU</code> ; le reçu de démonstration locale, "
                    "hors panel officiel, n'établit aucune de ces mesures. Aucune "
                    "sortie officiellement acceptable n'existant, tout coût par "
                    "sortie officiellement acceptable serait <code>NON_DEFINI</code>.</p>"
                    if recus_locaux
                    else "<p>Aucun reçu V1 n'existe : expérience réelle, coûts, "
                    "latences et couverture restent <code>INCONNU</code>. Aucune "
                    "sortie acceptable n'existant, tout coût par sortie "
                    "officiellement acceptable serait <code>NON_DEFINI</code>.</p>"
                )
            )
            + src(etat_relatif, "état V1 versionné")
            + src(rules, "U-020"),
        )
        + _article(
            "fait",
            "<p>Les contrats et politiques versionnés propres au profil abonnement ne "
            "sont pas encore déclarés dans l'état V1.</p>"
            + src(etat_relatif, "état V1 versionné")
            + src(ard, "section 7"),
        )
        + "</section>"
    )

    sections.append(
        "<section id=\"revue-humaine\"><h2>Réponses à la revue humaine</h2>"
        + _article(
            "fait",
            "<p>Commentaire <code>c_ce85ad851f47</code> — <code>INCONNU</code> "
            "signifie qu'aucune preuve admissible n'est ingérée dans l'état "
            "V1 courant pour le champ concerné, pas qu'il serait impossible "
            "en général de trouver la donnée. Certaines valeurs déclaratives "
            "sont recherchables dans des sources publiques ou locales ; "
            "d'autres champs sont des observations qui exigent une étape du "
            "parcours officiel. Une valeur recherchée n'entre dans le panel "
            "qu'une fois ingérée comme preuve admissible et sourcée.</p>"
            + src(etat_relatif, "état V1 versionné")
            + src(rules, "U-018"),
            ' data-commentaire="c_ce85ad851f47"',
        )
        + _article(
            "fait",
            "<p>Une autorisation de rechercher des valeurs accessibles est "
            "une décision de pilotage, distincte des observations : elle ne "
            "constitue pas une observation, n'améliore et ne remplace aucune "
            "preuve. Un champ <code>INCONNU</code> ne change qu'à l'ingestion "
            "d'une observation autorisée produite par sa tranche porteuse ; "
            "la présente restitution n'en ingère aucune et aucune valeur ne "
            "change. Une absence de preuve n'est jamais transformée en "
            "résultat favorable.</p>"
            + src(etat_relatif, "état V1 versionné")
            + src(rules, "U-018"),
        )
        + _article(
            "fait",
            "<p>Commentaire <code>c_3f78b813dc60</code> — les inconnues "
            "d'expérience réelle, de coûts, de latences et de couverture ne "
            "se résolvent que par les preuves produites par le parcours "
            "officiel : chaque acquisition exige un reçu immuable et chaque "
            "restitution exige ses preuves, ou l'abstention correspondante. "
            "Les collectes appartiennent aux étapes à venir, décrites avec "
            "leurs sources dans la section "
            '<a href="#etapes-futures">Six étapes futures</a> de cette '
            "page.</p>" + src(rules, "U-010 et U-018"),
            ' data-commentaire="c_3f78b813dc60"',
        )
        + _article(
            "fait",
            "<p><code>NON_DEFINI</code> est un état calculé par la règle de "
            "coût par sortie officiellement acceptable, pas une donnée "
            "publique à rechercher : aucune recherche ne peut le résoudre, "
            "seule l'existence de sorties officiellement acceptables le "
            "remplace par une mesure.</p>" + src(rules, "U-020"),
        )
        + "</section>"
    )

    lignes_etapes = "".join(
        _article(
            "planifie",
            f"<p>Étape {rang} — {texte} <strong>à venir</strong></p>"
            + src(chemin, section),
            f' data-marqueur="a-venir" data-etape="{nom}"',
        )
        for rang, (nom, texte, chemin, section) in enumerate(ETAPES_FUTURES, start=1)
    )
    sections.append(
        "<section id=\"etapes-futures\"><h2>Six étapes futures</h2>"
        "<p>Éléments planifiés, tous marqués à venir. Aucun n'est commencé ni "
        "prouvé.</p>" + lignes_etapes + "</section>"
    )

    recus_observes = [
        relatif
        for relatif, enveloppe, _ in recus_locaux
        if enveloppe["payload"]["execution"]["etat"] == "OBSERVED"
    ]
    officiels_observes = [
        relatif
        for relatif, enveloppe, _ in recus_officiels
        if enveloppe["payload"]["execution"]["etat"] == "OBSERVED"
    ]
    if recus_officiels:
        if officiels_observes:
            texte_observation = (
                "<p>Les reçus V1 officiels cités en source prouvent des "
                "exécutions <code>OBSERVED</code> de créneaux autorisés. Une "
                "exécution observée n'est ni une acceptabilité officielle ni "
                "une notation : le panel officiel demeure sans conclusion.</p>"
                + "".join(
                    src(relatif, SECTION_RECU_OFFICIEL)
                    for relatif in officiels_observes
                )
            )
        else:
            texte_observation = (
                "<p>Chaque reçu V1 officiel cité en source consigne un "
                "incident nommé, sans exécution <code>OBSERVED</code> : le "
                "panel officiel demeure sans conclusion.</p>"
                + "".join(
                    src(relatif, SECTION_RECU_OFFICIEL)
                    for relatif, _, _ in recus_officiels
                )
            )
        article_observation_v1 = _article("fait", texte_observation)
    elif recus_observes:
        article_observation_v1 = _article(
            "fait",
            "<p>Le reçu V1 local versionné cité en source prouve une exécution "
            "<code>OBSERVED</code> sans incident. Ce reçu reste hors panel "
            "officiel : le panel officiel demeure non mesuré.</p>"
            + "".join(
                src(relatif, SECTION_RECU_LOCAL) for relatif in recus_observes
            ),
        )
    else:
        article_observation_v1 = _article(
            "fait",
            "<p>Aucune exécution V1 <code>OBSERVED</code> n'est enregistrée dans "
            "le répertoire de reçus V1 : le panel officiel demeure non "
            "mesuré.</p>" + src(etat_relatif, "état V1 versionné"),
        )

    sections.append(
        "<section id=\"vocabulaire\"><h2>Vocabulaire normatif</h2>"
        "<p>Ces jetons appartiennent au vocabulaire normatif du dépôt.</p>"
        + article_observation_v1
        + _article(
            "fait",
            "<p><code>INCONNU</code> : valeur littérale d'une observation absente. "
            "Elle reste littérale et n'est jamais remplacée par une valeur "
            "inventée.</p>"
            + src(rapport_v0, "antériorité V0 séparée")
            + src(rules, "U-018"),
        )
        + _article(
            "fait",
            "<p><code>NON_DEFINI</code> : en l'absence de sortie acceptable, la mesure "
            "de coût par sortie officiellement acceptable est signalée comme non "
            "définie, les coûts engagés restant visibles.</p>" + src(rules, "U-020"),
        )
        + _article(
            "fait",
            "<p><code>HARNESS_ERROR</code> : défaut du harnais. Il ne pénalise pas la "
            "configuration, réduit la couverture, reste visible et empêche toute "
            "conclusion dépendant de la mesure manquante.</p>" + src(rules, "U-017"),
        )
        + _article(
            "fait",
            "<p><code>ABSTENTION</code> : une identité, une provenance, une fraîcheur, "
            "une comparabilité ou une préférence insuffisante impose l'abstention "
            "correspondante.</p>" + src(rules, "U-018"),
        )
        + "</section>"
    )

    sections.append(
        "<section id=\"anteriorite-v0\"><h2>Antériorité V0 séparée</h2>"
        + _article(
            "fait",
            "<p>Le rapport interne V0 M10.2, produit sous le profil API, s'est conclu "
            "par une abstention. Cette antériorité V0 reste séparée : une preuve "
            "historique établit seulement les propriétés de son propre contrat et ne "
            "constitue jamais un fait V1.</p>"
            + src(rapport_v0, "antériorité V0 séparée")
            + src(rules, "U-011"),
        )
        + _article(
            "fait",
            "<p>Le manifeste du paquet V0 porte les valeurs d'instantané "
            "<code>qualification_status: en attente d'approbation</code> et "
            "<code>approbation.statut: absente</code>, immuables depuis sa création. "
            "L'état courant de qualification relève d'une approbation humaine externe "
            "liée aux empreintes, qui seule fait autorité. Ces deux autorités sont "
            "distinctes et ne se contredisent pas.</p>"
            + src(manifeste, "instantané immuable")
            + src(rules, "U-009"),
        )
        + "</section>"
    )

    sections.append(
        "<section id=\"limites\"><h2>Limites</h2>"
        + _article(
            "fait",
            "<p>Cette page est une vue régénérable. Sa lisibilité n'améliore aucune "
            "preuve. Elle ne produit aucun appel candidat, aucune acquisition, aucune "
            "dépense, aucun classement, aucun gagnant et aucune recommandation. Aucune "
            "hypothèse non vérifiée n'est présente : aucune n'était nécessaire, et "
            "aucune n'est créée pour remplir une catégorie.</p>"
            + src(rules, "U-010 et U-026"),
        )
        + "</section>"
    )

    corps = "".join(sections)
    provenance = "".join(
        f"<li><code>{chemin}</code> ({section}) · SHA-256 "
        f"<code>{empreintes[chemin]}</code></li>"
        for chemin, section in (
            *SOURCES_AUTORISEES,
            *((chemin, SECTION_REGISTRE) for chemin, _ in configurations),
            *((relatif, SECTION_RECU_LOCAL) for relatif, _, _ in recus_locaux),
            *(
                (relatif, SECTION_RECU_OFFICIEL)
                for relatif, _, _ in recus_officiels
            ),
            *(
                ((autorisation[0], SECTION_AUTORISATION_ACQUISITION),)
                if autorisation is not None
                else ()
            ),
            *(
                ((registre_validation[0], SECTION_REGISTRE_VALIDATION),)
                if registre_validation is not None
                else ()
            ),
            *(
                ((qualification[0], SECTION_QUALIFICATION),)
                if qualification is not None
                else ()
            ),
            *((relatif, SECTION_PREFLIGHT) for relatif, _, _ in preflights),
            *(
                (
                    (relatif_sources_plans, SECTION_SOURCES_PLANS),
                    (verrou_charge[0], SECTION_VERROU),
                )
                if verrou_charge is not None
                else ()
            ),
            (etat_relatif, "état V1 versionné"),
        )
    )
    if configurations:
        titre = (
            "Restitution humaine V1 — profil abonnement — panel déclaré, aucune mesure"
        )
    else:
        titre = "Restitution humaine V1 — profil abonnement — état vide"
    page = (
        "<!DOCTYPE html>\n"
        '<html lang="fr">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{titre}</title>\n"
        "<style>\n"
        "body{font-family:Georgia,serif;max-width:52rem;margin:2rem auto;"
        "padding:0 1rem;line-height:1.5;color:#1a1a1a;background:#fdfdfb}\n"
        "h1{font-size:1.5rem}h2{font-size:1.15rem;margin-top:1.6rem;"
        "border-bottom:1px solid #ccc}\n"
        "article.affirmation{margin:0.7rem 0;padding:0.5rem 0.8rem;"
        "border-left:4px solid #999;background:#f6f6f2}\n"
        'article.affirmation[data-classe="fait"]{border-left-color:#2e6e3e}\n'
        'article.affirmation[data-classe="deduction"]{border-left-color:#2e4e7e}\n'
        'article.affirmation[data-classe="planifie"]{border-left-color:#8a6d1a}\n'
        "article.affirmation::before{display:block;font-size:0.75rem;"
        "letter-spacing:0.05em;color:#555;text-transform:uppercase}\n"
        'article.affirmation[data-classe="fait"]::before{content:"fait établi"}\n'
        'article.affirmation[data-classe="deduction"]::before'
        '{content:"déduction raisonnée"}\n'
        'article.affirmation[data-classe="planifie"]::before'
        '{content:"planifié — à venir"}\n'
        "span.source{display:block;font-size:0.8rem;color:#555;"
        "overflow-wrap:anywhere}\n"
        "code{background:#eee;padding:0 0.2rem}\n"
        "footer{margin-top:2rem;font-size:0.8rem;color:#555}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"<h1>{titre}</h1>\n"
        f"<p>Vue <code>{VERSION_VUE}</code>, autonome et hors ligne, régénérée de "
        "façon déterministe depuis les seules sources listées en pied de page. Chaque "
        "affirmation porte sa classe : fait établi, déduction raisonnée ou élément "
        "planifié à venir.</p>\n"
        f"{corps}\n"
        "<footer><p>Sources exactes de cette vue :</p>"
        f"<ul>{provenance}</ul></footer>\n"
        "</body>\n"
        "</html>\n"
    )
    return page.encode("utf-8")


def restituer(racine: Path) -> int:
    etat = _charger_etat(racine)
    repertoire = _repertoire_recus(racine, etat)
    repertoire.mkdir(parents=True, exist_ok=True)
    contenu = _rendre_page(racine)
    chemin_page = racine / CHEMIN_PAGE
    chemin_page.parent.mkdir(parents=True, exist_ok=True)
    chemin_page.write_bytes(contenu)
    print(f"page écrite : {CHEMIN_PAGE.as_posix()} ({len(contenu)} octets)")
    print(
        f"répertoire de reçus V1 : {repertoire.relative_to(racine).as_posix()} "
        f"({_compter_recus(repertoire)} reçu)"
    )
    return 0


_MOTIF_ARTICLE = re.compile(
    r'<article class="affirmation"([^>]*)>(.*?)</article>', re.DOTALL
)
_MOTIF_CLASSE = re.compile(r' data-classe="([^"]*)"')
_MOTIF_SOURCE = re.compile(r'<span class="source" data-chemin="([^"]+)" data-sha256="([a-f0-9]{64})">')
_MOTIF_PREMISSES = re.compile(r' data-premisses="([^"]+)"')
_MOTIF_ETAPE = re.compile(r' data-etape="([^"]+)"')


def verifier_restitution(racine: Path) -> int:
    echecs: list[str] = []
    chemin_page = racine / CHEMIN_PAGE
    try:
        page = chemin_page.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as erreur:
        print(f"ECHEC page illisible : {erreur}")
        return 1

    # Attendus recalculés depuis les entrées, indépendamment du rendu.
    etat = _charger_etat(racine)
    repertoire = _repertoire_recus(racine, etat)
    _compter_recus(repertoire)
    recus_locaux, recus_officiels = _partitionner_recus(racine, etat)
    configurations = _configurations_officielles(racine)
    qualification = _charger_recu_qualification(racine)
    preflights = _charger_recus_preflight(racine)
    verrou_charge = _charger_verrou_restitution(racine)
    autorisation = _charger_autorisation_restitution(racine)
    registre_validation = _charger_registre_validation(racine)
    jetons_factuels = _jetons_attendus(
        etat, len(recus_officiels), len(configurations)
    )
    etat_relatif = CHEMIN_ETAT.as_posix()
    empreintes = _empreintes_sources(
        racine, etat_relatif, tuple(chemin for chemin, _ in configurations)
    )
    empreintes.update({relatif: sha for relatif, _, sha in recus_locaux})
    empreintes.update({relatif: sha for relatif, _, sha in recus_officiels})
    empreintes.update({relatif: sha for relatif, _, sha in preflights})
    if qualification is not None:
        empreintes[qualification[0]] = qualification[2]
    if autorisation is not None:
        empreintes[autorisation[0]] = autorisation[2]
    if registre_validation is not None:
        empreintes[registre_validation[0]] = registre_validation[2]
    if verrou_charge is not None:
        empreintes[verrou_charge[0]] = verrou_charge[2]
        try:
            empreintes[CHEMIN_SOURCES_PLANS.as_posix()] = _sha256_fichier(
                racine / CHEMIN_SOURCES_PLANS
            )
        except OSError as erreur:
            raise ErreurRestitution(
                "sources de plans absentes alors que le verrou est "
                f"matérialisé : {erreur}"
            ) from erreur
        for attendu in _articles_verrou(
            verrou_charge[0], verrou_charge[2], verrou_charge[1]
        ):
            if attendu not in page:
                echecs.append("entrée de verrou infidèle ou absente")
    nombre_entrees_verrou = page.count(' data-verrou-panel="')
    attendu_entrees_verrou = (
        len(verrou_charge[1]["panel"]) if verrou_charge is not None else 0
    )
    if nombre_entrees_verrou != attendu_entrees_verrou:
        echecs.append(
            f"{attendu_entrees_verrou} entrées de panel verrouillé attendues "
            f"dans la page, {nombre_entrees_verrou} trouvées"
        )
    nombre_verrous = page.count(' data-verrou="campagne"')
    attendu_verrous = 0 if verrou_charge is None else 1
    if nombre_verrous != attendu_verrous:
        echecs.append(
            f"{attendu_verrous} article de verrou attendu dans la page, "
            f"{nombre_verrous} trouvé"
        )

    for relatif, recu, sha in preflights:
        attendu = _article_preflight(relatif, sha, recu)
        if attendu not in page:
            echecs.append(
                "entrée de préflight infidèle ou absente : "
                f"{recu['configuration_id']}"
            )
    nombre_preflights = page.count(' data-preflight="')
    if nombre_preflights != len(preflights):
        echecs.append(
            f"{len(preflights)} entrées de préflight attendues dans la page, "
            f"{nombre_preflights} trouvées"
        )

    if qualification is not None:
        attendu = _article_qualification(
            qualification[0], qualification[2], qualification[1]
        )
        if attendu not in page:
            echecs.append(
                "entrée de qualification du harnais infidèle ou absente : "
                f"verdict {qualification[1]['verdict']}"
            )
    nombre_qualifications = page.count(' data-qualification-harnais="')
    attendu_qualifications = 0 if qualification is None else 1
    if nombre_qualifications != attendu_qualifications:
        echecs.append(
            f"{attendu_qualifications} entrée de qualification attendue dans la "
            f"page, {nombre_qualifications} trouvée"
        )

    for relatif, enveloppe, sha in recus_locaux:
        attendu = _article_acquisition_locale(relatif, sha, enveloppe)
        if attendu not in page:
            echecs.append(
                "entrée d'acquisition locale infidèle ou absente : "
                f"{enveloppe['payload']['configuration']['identifiant']}"
            )
    nombre_locales = page.count(' data-acquisition-locale="')
    if nombre_locales != len(recus_locaux):
        echecs.append(
            f"{len(recus_locaux)} entrées d'acquisition locale attendues dans la "
            f"page, {nombre_locales} trouvées"
        )

    if autorisation is not None:
        attendu = _article_autorisation_acquisition(
            autorisation[0], autorisation[2], autorisation[1]
        )
        if attendu not in page:
            echecs.append(
                "entrée d'autorisation d'acquisition D-V1-04 infidèle ou absente"
            )
    nombre_autorisations_acquisition = page.count(
        ' data-autorisation-acquisition="'
    )
    attendu_autorisations_acquisition = 0 if autorisation is None else 1
    if nombre_autorisations_acquisition != attendu_autorisations_acquisition:
        echecs.append(
            f"{attendu_autorisations_acquisition} entrée d'autorisation "
            "d'acquisition attendue dans la page, "
            f"{nombre_autorisations_acquisition} trouvée"
        )

    if registre_validation is not None:
        relatif_registre, registre, _ = registre_validation
        # Le registre couvre exactement les acquisitions officielles, dans
        # l'ordre matériel du chaînage, sans jamais inclure un reçu local
        recus_registre = [entree["recu"] for entree in registre["entrees"]]
        recus_attendus = [relatif for relatif, _, _ in recus_officiels]
        if recus_registre != recus_attendus:
            echecs.append(
                "registre de validation non aligné sur les acquisitions "
                f"officielles : {recus_attendus} attendus, "
                f"{recus_registre} trouvés"
            )
        attendu_couverture = _article_couverture_validation(
            relatif_registre, registre_validation[2], registre
        )
        if attendu_couverture not in page:
            echecs.append(
                "entrée de couverture de validation infidèle ou absente"
            )
        for entree in registre["entrees"]:
            attendu = _article_validation(
                entree, relatif_registre, registre_validation[2]
            )
            if attendu not in page:
                echecs.append(
                    "entrée de validation infidèle ou absente : "
                    f"{entree['configuration_id']}"
                )
    nombre_validations = page.count(' data-validation="')
    attendu_validations = (
        len(registre_validation[1]["entrees"])
        if registre_validation is not None
        else 0
    )
    if nombre_validations != attendu_validations:
        echecs.append(
            f"{attendu_validations} entrées de validation attendues dans la "
            f"page, {nombre_validations} trouvées"
        )
    nombre_couvertures = page.count(' data-registre-validation="couverture"')
    attendu_couvertures = 0 if registre_validation is None else 1
    if nombre_couvertures != attendu_couvertures:
        echecs.append(
            f"{attendu_couvertures} entrée de couverture de validation "
            f"attendue dans la page, {nombre_couvertures} trouvée"
        )

    for relatif, enveloppe, sha in recus_officiels:
        attendu = _article_acquisition_officielle(relatif, sha, enveloppe)
        if attendu not in page:
            echecs.append(
                "entrée d'acquisition officielle infidèle ou absente : "
                f"{enveloppe['payload']['configuration']['identifiant']}"
            )
    nombre_officielles = page.count(' data-acquisition-officielle="')
    if nombre_officielles != len(recus_officiels):
        echecs.append(
            f"{len(recus_officiels)} entrées d'acquisition officielle attendues "
            f"dans la page, {nombre_officielles} trouvées"
        )

    for chemin, donnees in configurations:
        attendu = _article_panel(chemin, empreintes[chemin], donnees)
        if attendu not in page:
            echecs.append(
                "entrée de panel infidèle ou absente : "
                f"{donnees['configuration_id']}"
            )
    nombre_affiche = page.count(' data-configuration="')
    if nombre_affiche != len(configurations):
        echecs.append(
            f"{len(configurations)} entrées de panel attendues dans la page, "
            f"{nombre_affiche} trouvées"
        )

    for chemin, donnees in configurations:
        attendu = _article_autorisations(chemin, empreintes[chemin], donnees)
        if attendu not in page:
            echecs.append(
                "entrée d'autorisations infidèle ou absente : "
                f"{donnees['configuration_id']}"
            )
    nombre_autorisations = page.count(' data-autorisation="')
    if nombre_autorisations != len(configurations):
        echecs.append(
            f"{len(configurations)} entrées d'autorisations attendues dans la "
            f"page, {nombre_autorisations} trouvées"
        )

    page_basse = page.lower()
    for sequence in SEQUENCES_DISTANTES:
        if sequence in page_basse:
            echecs.append(f"ressource distante interdite présente : {sequence!r}")

    for jeton in (*jetons_factuels, *JETONS_NORMATIFS):
        if jeton not in page:
            echecs.append(f"jeton attendu absent : {jeton!r}")

    for chemin, sha256 in empreintes.items():
        if f'data-chemin="{chemin}" data-sha256="{sha256}"' not in page:
            echecs.append(
                f"source infidèle ou absente : {chemin} attendu avec SHA-256 {sha256}"
            )

    articles = _MOTIF_ARTICLE.findall(page)
    if page.count('<article class="affirmation"') != len(articles):
        echecs.append("article d'affirmation mal formé")
    etapes: list[str] = []
    for attributs, contenu in articles:
        classe = _MOTIF_CLASSE.search(attributs)
        if classe is None or classe.group(1) not in CLASSES_MSW:
            echecs.append(f"affirmation sans classe MSW valide : {contenu[:60]!r}")
            continue
        sources = _MOTIF_SOURCE.findall(contenu)
        if classe.group(1) in {"fait", "deduction"} and not sources:
            echecs.append(
                f"affirmation {classe.group(1)} sans chemin ni empreinte de source : "
                f"{contenu[:60]!r}"
            )
        for chemin, sha256 in sources:
            if empreintes.get(chemin) != sha256:
                echecs.append(f"empreinte citée divergente pour {chemin}")
        if classe.group(1) == "deduction" and not _MOTIF_PREMISSES.search(attributs):
            echecs.append(f"déduction sans prémisses visibles : {contenu[:60]!r}")
        if classe.group(1) == "planifie":
            etape = _MOTIF_ETAPE.search(attributs)
            if (
                etape is None
                or ' data-marqueur="a-venir"' not in attributs
                or "à venir" not in contenu
            ):
                echecs.append(f"étape planifiée sans marqueur à venir : {contenu[:60]!r}")
            else:
                etapes.append(etape.group(1))

    noms_attendus = [nom for nom, _, _, _ in ETAPES_FUTURES]
    if etapes != noms_attendus:
        echecs.append(
            f"six étapes futures attendues {noms_attendus}, trouvées {etapes}"
        )

    if echecs:
        for echec in echecs:
            print(f"ECHEC {echec}")
        return 1
    print("verification-restitution : conforme")
    return 0


def _analyser_options(
    arguments: list[str], noms_autorises: tuple[str, ...]
) -> dict[str, str] | None:
    """Rend les paires option/valeur, ou None sur toute forme hors contrat."""
    valeurs: dict[str, str] = {}
    rang = 0
    while rang < len(arguments):
        nom = arguments[rang]
        if nom not in noms_autorises or nom in valeurs or rang + 1 >= len(arguments):
            return None
        valeurs[nom] = arguments[rang + 1]
        rang += 2
    return valeurs


_USAGE = (
    "usage : campagne_v1.py enregistrer [--registre <chemin>] --fichier <chemin> "
    "| panel [--registre <chemin>] | autorisations [--configuration <id>] "
    "| acquerir --local --configuration <id> "
    "| acquerir --officiel --configuration <id> "
    "| preflight --configuration <id> "
    "| qualifier | verrouiller | valider | restituer | verifier-restitution"
)


def principal(
    arguments: list[str],
    racine: Path | None = None,
    racine_privee: Path | None = None,
) -> int:
    if racine is None:
        racine = Path(__file__).resolve().parent.parent
    if arguments == ["qualifier"]:
        return qualifier_harnais(racine)
    if arguments == ["verrouiller"]:
        # racine_privee n'existe que pour les tests Python : la CLI de
        # production conserve la racine privée obligatoire exacte
        return verrouiller(racine, racine_privee)
    if arguments == ["valider"]:
        return valider(racine)
    if arguments == ["restituer"]:
        try:
            return restituer(racine)
        except ErreurRestitution as erreur:
            print(f"ECHEC {erreur}")
            return 1
    if arguments == ["verifier-restitution"]:
        try:
            return verifier_restitution(racine)
        except ErreurRestitution as erreur:
            print(f"ECHEC {erreur}")
            return 1
    if arguments[:1] == ["enregistrer"]:
        options = _analyser_options(arguments[1:], ("--registre", "--fichier"))
        if options is None or "--fichier" not in options:
            print(_USAGE)
            return 2
        registre = Path(options["--registre"]) if "--registre" in options else None
        return enregistrer_configuration(racine, Path(options["--fichier"]), registre)
    if arguments[:1] == ["autorisations"]:
        options = _analyser_options(arguments[1:], ("--configuration",))
        if options is None:
            print(_USAGE)
            return 2
        return afficher_autorisations(racine, options.get("--configuration"))
    if arguments[:1] == ["acquerir"]:
        # Deux formes figées : locale de démonstration, officielle D-V1-04.
        if len(arguments) != 4 or arguments[2] != "--configuration":
            print(_USAGE)
            return 2
        if arguments[1] == "--local":
            return acquerir_local(racine, arguments[3])
        if arguments[1] == "--officiel":
            # racine_privee n'existe que pour les tests Python : la CLI de
            # production conserve la racine privée obligatoire exacte
            return acquerir_officiel(racine, arguments[3], racine_privee)
        print(_USAGE)
        return 2
    if arguments[:1] == ["preflight"]:
        options = _analyser_options(arguments[1:], ("--configuration",))
        if options is None:
            print(_USAGE)
            return 2
        if "--configuration" not in options:
            # Refus fail-closed : le préflight de panel entier exige
            # l'adaptateur de la tranche V1-XS-06F, non couverte ici
            print(
                "ECHEC option '--configuration' requise : V1-XS-06A à "
                f"V1-XS-06E couvrent les seuls adaptateurs "
                f"'{ADAPTATEUR_CLAUDE}', '{ADAPTATEUR_CODEX}', "
                f"'{ADAPTATEUR_GROK}', '{ADAPTATEUR_CURSOR}' et "
                f"'{ADAPTATEUR_OPENCODEX}' ; le préflight sans option "
                "relève de la tranche V1-XS-06F"
            )
            return 1
        return preflight_configuration(racine, options["--configuration"])
    if arguments[:1] == ["panel"]:
        options = _analyser_options(arguments[1:], ("--registre",))
        if options is None:
            print(_USAGE)
            return 2
        registre = Path(options["--registre"]) if "--registre" in options else None
        return afficher_panel(racine, registre)
    print(_USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
