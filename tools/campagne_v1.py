# /// script
# requires-python = ">=3.12,<3.13"
# ///
"""Restitution humaine V1, registre de panel abonnement et vérifications.

Interface figée :
- uv run tools/campagne_v1.py enregistrer [--registre <chemin>] --fichier <chemin>
- uv run tools/campagne_v1.py panel [--registre <chemin>]
- uv run tools/campagne_v1.py autorisations [--configuration <id>]
- uv run tools/campagne_v1.py acquerir --local --configuration <id>
- uv run tools/campagne_v1.py preflight --configuration <id>
- uv run tools/campagne_v1.py restituer
- uv run tools/campagne_v1.py verifier-restitution
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import signal
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
    if configuration["interface"]["type"] != "cli" or argv[0] != ADAPTATEUR_CLAUDE:
        print(
            f"ECHEC adaptateur non couvert : '{argv[0]}' ; V1-XS-06A couvre le "
            f"seul adaptateur '{ADAPTATEUR_CLAUDE}', les autres configurations "
            "relèvent des tranches V1-XS-06B à V1-XS-06F"
        )
        return 1
    (
        sondes,
        version,
        authentification,
        plan_observe,
        verdict,
        cause,
        fait,
    ) = _observer_route_claude()
    recu = {
        "schema_version": SCHEMA_RECU_PREFLIGHT,
        "configuration_id": identifiant,
        "date_preflight": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "autorite_preflight": AUTORITE_PREFLIGHT,
        "adaptateur": ADAPTATEUR_CLAUDE,
        "commande_publique": (
            f"uv run tools/campagne_v1.py preflight --configuration {identifiant}"
        ),
        "sondes": sondes,
        "interface": {
            "type": configuration["interface"]["type"],
            "client": ADAPTATEUR_CLAUDE,
            "version_observee": version,
        },
        "authentification": {"observee": authentification},
        "plan": {
            "declare": configuration["plan"]["nom"],
            "observe": plan_observe,
        },
        "modele": {
            "demande": configuration["modele"]["demande"],
            "expose": INCONNU,
        },
        "effort": {"demande": EFFORT_DEMANDE_CLAUDE, "expose": INCONNU},
        "quota": {"observe": INCONNU, "consommation_preflight": INCONNU},
        "verdict": verdict,
        "cause": cause,
        "fait": fait,
    }
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


def _recus_locaux(racine: Path, etat: dict) -> list[tuple[str, dict, str]]:
    """Reçus V1 locaux valides : (chemin relatif, enveloppe, SHA-256 du fichier).

    Tout fichier du répertoire doit être un reçu V1 abonnement valide et
    chaîné ; sinon la restitution refuse fail-closed.
    """
    repertoire = _repertoire_recus(racine, etat)
    try:
        recus = _charger_recus(repertoire)
    except ErreurRecu as erreur:
        raise ErreurRestitution(f"reçu V1 local invalide : {erreur}") from erreur
    return [
        (
            chemin.relative_to(racine).as_posix(),
            enveloppe,
            _sha256_fichier(chemin),
        )
        for chemin, enveloppe in recus
    ]


def _jetons_attendus(
    etat: dict, nombre_recus: int, nombre_configurations: int = 0
) -> tuple[str, str, str]:
    """Recalcule les trois jetons factuels depuis l'état, les acquisitions
    officielles et le registre. Les reçus locaux de démonstration, hors panel
    officiel, n'entrent pas dans ce décompte."""
    if etat["panel"]:
        raise ErreurRestitution(
            "le champ panel de l'état V1 doit rester vide : le panel déclaré vit "
            "dans le registre officiel versionné"
        )
    if nombre_recus:
        raise ErreurRestitution(
            "état hors périmètre : la conclusion n'est dérivable que de zéro "
            "acquisition, toute acquisition relève d'une tranche ultérieure"
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


def _exiger_sonde_autorisee(nom: str, commande: object) -> None:
    """Liste blanche exacte : toute autre forme est refusée, notamment
    -p, --print, --model, prompt positionnel, --continue, --resume,
    --fork-session et --dangerously-skip-permissions"""
    if not isinstance(commande, str) or tuple(commande.split()) not in (
        SONDES_AUTORISEES_PREFLIGHT
    ):
        raise ErreurRestitution(
            f"champ '{nom}' : sonde hors liste blanche refusée ({commande!r})"
        )


def _valider_recu_preflight(nom_fichier: str, recu: object) -> dict:
    if not isinstance(recu, dict) or set(recu) != _CLES_RECU_PREFLIGHT:
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : clés exactes "
            f"{sorted(_CLES_RECU_PREFLIGHT)} attendues"
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
    if recu["adaptateur"] != ADAPTATEUR_CLAUDE:
        raise ErreurRestitution(
            f"reçu de préflight '{nom_fichier}' : adaptateur "
            f"'{ADAPTATEUR_CLAUDE}' attendu"
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
        _exiger_sonde_autorisee(f"sondes[{rang}].commande", sonde.get("commande"))
        if isinstance(sonde.get("code_sortie"), bool) or not isinstance(
            sonde.get("code_sortie"), int
        ):
            raise ErreurRestitution(
                f"reçu de préflight '{nom_fichier}' : sonde {rang} sans code de "
                "sortie entier"
            )
        if sonde["commande"] == " ".join(SONDE_AUTH_CLAUDE):
            # La sonde auth ne porte qu'une projection, jamais la sortie brute
            if set(sonde) != {"commande", "code_sortie", "projection"}:
                raise ErreurRestitution(
                    f"reçu de préflight '{nom_fichier}' : sonde {rang} aux clés "
                    "exactes commande, code_sortie, projection attendue"
                )
            projection = sonde["projection"]
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
            texte = "projection " + " · ".join(
                f"{champ} <code>{_echapper(projection[champ])}</code>"
                for champ in CHAMPS_PROJECTION_AUTH
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
    return " · ".join(
        f"{champ} <code>{_echapper(observee[champ])}</code>"
        for champ in ("loggedIn", "authMethod", "apiProvider")
    )


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
        f"<p>quota observé <code>{_echapper(recu['quota']['observe'])}</code> · "
        "consommation du préflight "
        f"<code>{_echapper(recu['quota']['consommation_preflight'])}</code></p>"
        + _span_source(relatif, sha_fichier, SECTION_PREFLIGHT)
    )
    return _article(
        "fait",
        contenu,
        f' data-preflight="{recu["configuration_id"]}"',
    )


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
    # Tout fichier du répertoire doit être un reçu local valide ; aucune
    # acquisition officielle n'existe, la conclusion du panel reste inchangée.
    recus_locaux = _recus_locaux(racine, etat)
    configurations = _configurations_officielles(racine)
    qualification = _charger_recu_qualification(racine)
    preflights = _charger_recus_preflight(racine)
    jeton_panel, jeton_acquisitions, jeton_conclusion = _jetons_attendus(
        etat, 0, len(configurations)
    )
    etat_relatif = CHEMIN_ETAT.as_posix()
    empreintes = _empreintes_sources(
        racine, etat_relatif, tuple(chemin for chemin, _ in configurations)
    )
    empreintes.update({relatif: sha for relatif, _, sha in recus_locaux})
    empreintes.update({relatif: sha for relatif, _, sha in preflights})
    if qualification is not None:
        empreintes[qualification[0]] = qualification[2]

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
    if recus_locaux:
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

    if recus_locaux:
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
                "Aucune acquisition officielle et aucune mesure du panel "
                "n'existe ; le reçu de démonstration locale reste hors panel "
                "officiel."
                if recus_locaux
                else "Aucune acquisition et aucune mesure n'existe."
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
    if recus_observes:
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
                ((qualification[0], SECTION_QUALIFICATION),)
                if qualification is not None
                else ()
            ),
            *((relatif, SECTION_PREFLIGHT) for relatif, _, _ in preflights),
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
    recus_locaux = _recus_locaux(racine, etat)
    configurations = _configurations_officielles(racine)
    qualification = _charger_recu_qualification(racine)
    preflights = _charger_recus_preflight(racine)
    jetons_factuels = _jetons_attendus(etat, 0, len(configurations))
    etat_relatif = CHEMIN_ETAT.as_posix()
    empreintes = _empreintes_sources(
        racine, etat_relatif, tuple(chemin for chemin, _ in configurations)
    )
    empreintes.update({relatif: sha for relatif, _, sha in recus_locaux})
    empreintes.update({relatif: sha for relatif, _, sha in preflights})
    if qualification is not None:
        empreintes[qualification[0]] = qualification[2]

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
    "| preflight --configuration <id> "
    "| qualifier | restituer | verifier-restitution"
)


def principal(arguments: list[str], racine: Path | None = None) -> int:
    if racine is None:
        racine = Path(__file__).resolve().parent.parent
    if arguments == ["qualifier"]:
        return qualifier_harnais(racine)
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
        # Forme figée : seule l'acquisition locale non officielle existe.
        if (
            len(arguments) != 4
            or arguments[1] != "--local"
            or arguments[2] != "--configuration"
        ):
            print(_USAGE)
            return 2
        return acquerir_local(racine, arguments[3])
    if arguments[:1] == ["preflight"]:
        options = _analyser_options(arguments[1:], ("--configuration",))
        if options is None:
            print(_USAGE)
            return 2
        if "--configuration" not in options:
            # Refus fail-closed : le préflight de panel entier exige les
            # adaptateurs des tranches V1-XS-06B à V1-XS-06F, non couvertes ici
            print(
                "ECHEC option '--configuration' requise : V1-XS-06A couvre le "
                f"seul adaptateur '{ADAPTATEUR_CLAUDE}' ; le préflight sans "
                "option relève des tranches V1-XS-06B à V1-XS-06F"
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
