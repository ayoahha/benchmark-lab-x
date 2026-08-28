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
- uv run tools/campagne_v1.py acquerir --recuperation --configuration <id>
- uv run tools/campagne_v1.py preflight --configuration <id>
- uv run tools/campagne_v1.py verrouiller
- uv run tools/campagne_v1.py valider
- uv run tools/campagne_v1.py metriques
- uv run tools/campagne_v1.py cout
- uv run tools/campagne_v1.py restituer
- uv run tools/campagne_v1.py verifier-restitution
- uv run tools/campagne_v1.py preparer-recuperation
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
from fractions import Fraction
from pathlib import Path

VERSION_VUE = "restitution-humaine-v1/vue/1"

_RACINE_CAMPAGNE_V1 = Path("tasks/dev/pre-cadrage-entretien-client/campagne-v1")
CHEMIN_ETAT = _RACINE_CAMPAGNE_V1 / "etat-v1.json"
CHEMIN_PAGE = _RACINE_CAMPAGNE_V1 / "restitution-humaine-v1" / "index.html"
CHEMIN_TABLE_METRIQUES = _RACINE_CAMPAGNE_V1 / "metriques-v1.json"

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

# Retours propriétaires V1-XS-14 : statuts du parcours dérivés des preuves
# versionnées présentes ; a-venir reste la valeur sans preuve
LIBELLES_PARCOURS = {
    "realise": "RÉALISÉ",
    "partiel": "PARTIEL",
    "bloque": "BLOQUÉ",
}
CHEMIN_REGISTRE_VERITE = (
    "tasks/dev/pre-cadrage-entretien-client/registre-verite.md"
)
SECTION_VERROU_COMPLETION = "verrou de complétion du panel versionné"
SECTION_REGISTRE_VERITE = (
    "registre de vérité du paquet, portes G-001 à G-005"
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
# Table additive des seuls reçus de récupération V1-R2 : présente uniquement
# sur les créneaux -002, jamais sur les reçus historiques
_CLES_RECUPERATION_RECU = {
    "tranche",
    "autorite",
    "acquisition_id",
    "identite_servie",
}
_CLES_IDENTITE_SERVIE_RECU = {
    "statut",
    "disposition",
    "incident",
    "champs_divergents",
    "cause",
}


def _valider_recuperation_recu(valeur: object, configuration_id: str) -> dict:
    """Valide la table additive de récupération d'un reçu -002 et rend la
    table ; toute divergence du contrat fermé V1-R2 est refusée."""
    table = _exiger_cles("recuperation", valeur, _CLES_RECUPERATION_RECU)
    if table["tranche"] != TRANCHE_RECUPERATION_EXECUTION:
        raise ErreurRecu(
            f"champ 'recuperation.tranche' : '{TRANCHE_RECUPERATION_EXECUTION}' attendu"
        )
    if table["autorite"] != AUTORITE_RECUPERATION:
        raise ErreurRecu(
            f"champ 'recuperation.autorite' : '{AUTORITE_RECUPERATION}' attendu"
        )
    creneaux = {
        CONFIGURATION_ANTIGRAVITY_RECUPERATION: CRENEAU_ANTIGRAVITY_RECUPERATION,
        CONFIGURATION_ZAI_RECUPERATION: CRENEAU_ZAI_RECUPERATION,
    }
    attendu = creneaux.get(configuration_id)
    if attendu is None or table["acquisition_id"] != attendu:
        raise ErreurRecu(
            "champ 'recuperation.acquisition_id' : créneau -002 exact de la "
            f"configuration '{configuration_id}' attendu"
        )
    identite = _exiger_cles(
        "recuperation.identite_servie",
        table["identite_servie"],
        _CLES_IDENTITE_SERVIE_RECU,
    )
    if identite["statut"] not in ("OBSERVED", INCONNU):
        raise ErreurRecu(
            "champ 'recuperation.identite_servie.statut' : OBSERVED ou "
            "INCONNU attendu"
        )
    disposition_attendue = (
        "OBSERVED" if identite["statut"] == "OBSERVED" else "HOLD"
    )
    if identite["disposition"] != disposition_attendue:
        raise ErreurRecu(
            "champ 'recuperation.identite_servie.disposition' : "
            f"'{disposition_attendue}' attendu pour le statut "
            f"'{identite['statut']}'"
        )
    if identite["incident"] is not None and identite["incident"] not in INCIDENTS_V1:
        raise ErreurRecu(
            "champ 'recuperation.identite_servie.incident' : None ou "
            f"vocabulaire fermé ({' | '.join(INCIDENTS_V1)}) attendu"
        )
    if not isinstance(identite["champs_divergents"], list) or any(
        not isinstance(champ, str) for champ in identite["champs_divergents"]
    ):
        raise ErreurRecu(
            "champ 'recuperation.identite_servie.champs_divergents' : liste "
            "de chaînes attendue"
        )
    if identite["cause"] is not None and not isinstance(identite["cause"], str):
        raise ErreurRecu(
            "champ 'recuperation.identite_servie.cause' : None ou chaîne "
            "attendue"
        )
    return table


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
    charge = recu["payload"]
    if not isinstance(charge, dict) or set(charge) not in (
        _CLES_CHARGE_RECU,
        _CLES_CHARGE_RECU | {"recuperation"},
    ):
        raise ErreurRecu(
            f"champ 'payload' : clés exactes {sorted(_CLES_CHARGE_RECU)} "
            "attendues, plus la seule table additive 'recuperation' des "
            "créneaux -002"
        )
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
    recuperation = charge.get("recuperation")
    if recuperation is not None:
        table_recuperation = _valider_recuperation_recu(
            recuperation, configuration["identifiant"]
        )
        creneau_attendu = (
            f"{configuration['identifiant']}:{stimulus['sha256']}:"
            f"{table_recuperation['acquisition_id']}"
        )
        derivation = (
            "'<configuration_id>:<sha256 du stimulus>:<acquisition_id -002>'"
        )
    else:
        creneau_attendu = f"{configuration['identifiant']}:{stimulus['sha256']}"
        derivation = "'<configuration_id>:<sha256 du stimulus>'"
    if charge["creneau"] != creneau_attendu:
        raise ErreurRecu(
            f"champ 'creneau' : dérivation exacte {derivation} attendue"
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
    if recuperation is not None:
        statut = recuperation["identite_servie"]["statut"]
        provenance_observee = isinstance(charge["provenance_servie"], dict)
        if (statut == "OBSERVED") != provenance_observee:
            raise ErreurRecu(
                "champ 'recuperation.identite_servie.statut' : incohérent "
                "avec 'provenance_servie' ; une identité OBSERVED exige une "
                "provenance prouvée et réciproquement"
            )
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
    canon = _canon_panel(etat.get("couverture"))
    if nombre_configurations:
        if canon is not None:
            jeton_panel = canon
        else:
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


def _verifier_triplets_configuration(
    racine: Path,
    recus_officiels: list[tuple[str, dict, str]],
    configurations: list[tuple[str, dict]],
) -> None:
    """Recoupement fail-closed du triplet configuration embarqué dans chaque
    reçu officiel avec le fichier courant du registre officiel.

    Toute substitution de configuration entre l'acquisition et la lecture
    est refusée nommément, aucune réparation."""
    chemins_declares = {
        chemin for chemin, _ in configurations
    }
    identifiants_declares = {
        chemin: donnees["configuration_id"]
        for chemin, donnees in configurations
    }
    empreintes_declares = {
        chemin: _sha256_fichier(racine / chemin)
        for chemin, _ in configurations
    }
    for relatif, enveloppe, _ in recus_officiels:
        configuration = enveloppe["payload"]["configuration"]
        if configuration["chemin"] not in chemins_declares:
            raise ErreurRestitution(
                f"reçu officiel {relatif} : chemin de configuration "
                "divergent du registre officiel courant : "
                f"{configuration['chemin']}"
            )
        if configuration["identifiant"] != identifiants_declares[
            configuration["chemin"]
        ]:
            raise ErreurRestitution(
                f"reçu officiel {relatif} : identifiant de configuration "
                "divergent du registre officiel courant : "
                f"{configuration['identifiant']}"
            )
        if configuration["sha256"] != empreintes_declares[
            configuration["chemin"]
        ]:
            raise ErreurRestitution(
                f"reçu officiel {relatif} : SHA-256 de configuration "
                "divergent du fichier courant du registre officiel : "
                f"{configuration['chemin']}"
            )


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
    recuperation = charge.get("recuperation")
    if recuperation is None:
        entete = (
            "acquisition officielle exécutée une seule fois sous D-V1-04, "
            "sans retry ni fallback."
        )
        lignes_recuperation = ""
    else:
        identite = recuperation["identite_servie"]
        entete = (
            "acquisition de récupération "
            f"<code>{_echapper(recuperation['acquisition_id'])}</code> "
            "exécutée une seule fois sous "
            f"{_echapper(recuperation['autorite'])} (tranche "
            f"{_echapper(recuperation['tranche'])}), sans retry ni fallback."
        )
        complements = ""
        if identite["incident"] is not None:
            complements += (
                f" · incident <code>{_echapper(identite['incident'])}</code>"
            )
        if identite["champs_divergents"]:
            complements += (
                " · champs divergents <code>"
                f"{_echapper(', '.join(identite['champs_divergents']))}</code>"
            )
        if identite["cause"] is not None:
            complements += f" · cause {_echapper(identite['cause'])}"
        lignes_recuperation = (
            "<p>identité servie de récupération : statut "
            f"<code>{_echapper(identite['statut'])}</code> · disposition "
            f"<code>{_echapper(identite['disposition'])}</code>"
            f"{complements}</p>"
        )
    provenance = charge["provenance_servie"]
    if isinstance(provenance, dict):
        texte_provenance = (
            "OBSERVED — "
            + " · ".join(
                f"{_echapper(cle)} <code>{_echapper(valeur)}</code>"
                for cle, valeur in sorted(provenance["valeur"].items())
            )
            + f" · preuve <code>{_echapper(provenance['preuve'])}</code>"
        )
    else:
        texte_provenance = f"<code>{_echapper(provenance)}</code>"
    contenu = (
        f"<p><strong>{_echapper(charge['configuration']['identifiant'])}</strong> — "
        f"{entete} Ce reçu restitue une exécution et ses faits ; il "
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
        + lignes_recuperation
        + f"<p>quota observé : <code>{_echapper(charge['quota_observe'])}</code> · "
        f"identité servie : {texte_provenance}</p>"
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


class ErreurRecuperation(Exception):
    """Divergence nommée du contrat de récupération V1-R1."""


# Contrat fermé de l'Issue #131 : récupération verrouillée des harnais
# Antigravity et Z.AI, sans autorité d'exécution dans cette tranche.
SCHEMA_VERROU_RECUPERATION = "campagne-v1-verrou-recuperation/v1"
CHEMIN_VERROU_RECUPERATION = (
    _RACINE_CAMPAGNE_V1 / "recuperation-harnais-v1" / "verrou-recuperation.json"
)
SECTION_VERROU_RECUPERATION = "verrou de récupération des harnais versionné"
ISSUE_RECUPERATION = "https://github.com/ayoahha/benchmark-lab-x/issues/131"
TRANCHE_RECUPERATION = "V1-R1"
CONFIGURATION_ANTIGRAVITY_RECUPERATION = "antigravity-gemini-3-7-flash"
CONFIGURATION_ZAI_RECUPERATION = "zai-glm-5-3"
CRENEAU_ANTIGRAVITY_RECUPERATION = "ACQ-V1-ANTIGRAVITY-GEMINI-3-7-FLASH-002"
CRENEAU_ZAI_RECUPERATION = "ACQ-V1-ZAI-GLM-5-3-002"

# Descripteurs fermés par le contrat : aucune dérivation, aucune variante.
DESCRIPTEUR_ANTIGRAVITY_RECUPERATION = (
    "agy",
    "--model",
    "gemini-3.7-flash-high",
    "--effort",
    "high",
    "--sandbox",
    "--disable-slash-commands",
    "--print=__STIMULUS_UTF8__",
)
DESCRIPTEUR_ZAI_RECUPERATION = (
    "codex",
    "exec",
    "--skip-git-repo-check",
    "--sandbox",
    "read-only",
    "--model",
    "zai/glm-5.3",
    "--cd",
    "__ISOLATED_WORKSPACE__",
    "--config",
    'model_reasoning_effort="high"',
    "-",
)
MODE_STIMULUS_ARGUMENT = "argument"
MODE_STIMULUS_STDIN = "stdin"
VARIANTES_INTERDITES_RECUPERATION = (
    "fallback",
    "retry",
    "fast",
    "priority",
    "max",
    "ultra",
)
CONDITION_OBSERVED_ZAI = (
    "trace OpenCodex attribuable à la tentative : fournisseur zai, "
    "modèle glm-5.3, effort effectif high, une tentative, aucun fallback"
)
CONDITION_OBSERVED_ANTIGRAVITY = (
    "métadonnée attribuable à la tentative portant gemini-3.7-flash-high"
)
SINON_PROVENANCE_RECUPERATION = "provenance servie INCONNU et HOLD"
JAMAIS_PREUVE_RECUPERATION = ("argv demandé", "code de sortie 0")

# Jeton du stimulus UTF-8 dans le descripteur Antigravity.
JETON_STIMULUS_UTF8 = "__STIMULUS_UTF8__"

# Les sept sources historiques de la récupération, dans l'ordre figé du
# verrou : chaque empreinte courante est croisée avec la constante figée et
# avec son épinglage existant lorsqu'il existe.
CHEMINS_SOURCES_HISTORIQUES_RECUPERATION = (
    CHEMIN_AUTORISATION_ACQUISITION.as_posix(),
    CHEMIN_VERROU.as_posix(),
    CHEMIN_STIMULUS,
    (
        REGISTRE_OFFICIEL / f"{CONFIGURATION_ANTIGRAVITY_RECUPERATION}.toml"
    ).as_posix(),
    (REGISTRE_OFFICIEL / f"{CONFIGURATION_ZAI_RECUPERATION}.toml").as_posix(),
    (
        _RACINE_CAMPAGNE_V1
        / "recus-v1"
        / "80046afee6e56ab9dcbdbbda4d5a4190d0d77cad2449b900ae16861e14cad839.json"
    ).as_posix(),
    (
        _RACINE_CAMPAGNE_V1
        / "recus-v1"
        / "0964422c4970ed527846e5dce3f7f9fcc9640897424044aad3f7cbc146695f40.json"
    ).as_posix(),
)

# Constantes figées par le contrat : toute divergence de l'octet courant
# rend 2 en nommant le chemin, sans réécriture.
EMPREINTES_SOURCES_HISTORIQUES_RECUPERATION = {
    CHEMIN_AUTORISATION_ACQUISITION.as_posix(): (
        "40df1597765f57b3df00a02c4c47134df1af9d9c512183efeadaf6c3cdc63acf"
    ),
    CHEMIN_VERROU.as_posix(): (
        "651f4eaee740e54e70b449b92d23be11a61ecdfea9443b875213cc563b50a17c"
    ),
    CHEMIN_STIMULUS: (
        "20f0be450640704b0c467eee57ca2ea58a4d629e63eba3efccbc6f68440e07e4"
    ),
    (
        REGISTRE_OFFICIEL / f"{CONFIGURATION_ANTIGRAVITY_RECUPERATION}.toml"
    ).as_posix(): (
        "3a84083be8a6a25e850fc2daf8ab2438cccd951df8f5c0167757e0f97dc01e99"
    ),
    (REGISTRE_OFFICIEL / f"{CONFIGURATION_ZAI_RECUPERATION}.toml").as_posix(): (
        "6d009539b6aa704e442d69f3dc272d48cef153e73003243033239c0bbb5642a2"
    ),
    (
        _RACINE_CAMPAGNE_V1
        / "recus-v1"
        / "80046afee6e56ab9dcbdbbda4d5a4190d0d77cad2449b900ae16861e14cad839.json"
    ).as_posix(): (
        "6772a92c52dcb6affeb0a55af743609833bb4f4d12068e8149f74d84675bee41"
    ),
    (
        _RACINE_CAMPAGNE_V1
        / "recus-v1"
        / "0964422c4970ed527846e5dce3f7f9fcc9640897424044aad3f7cbc146695f40.json"
    ).as_posix(): (
        "0f081930b493ae9b990d7422b15763fff9337ae99a1344362835c39cbf0c6481"
    ),
}

# Sentinelles de diagnostic reliées à l'Issue #109 : jamais des preuves
# candidates, exclues fermement des reçus et verdicts V1.
ISSUE_SENTINELLES_RECUPERATION = (
    "https://github.com/ayoahha/benchmark-lab-x/issues/109"
)
SENTINELLE_DIAGNOSTIC_NON_CANDIDAT = "DIAGNOSTIC_NON_CANDIDAT"
EXCLUSION_FERMEE_SENTINELLE = ["recus-v1", "verdicts-v1"]

_CLES_VERROU_RECUPERATION = {
    "schema_version",
    "portee",
    "configurations",
    "autorite_execution",
    "creneaux_executes",
    "reprises_executees",
    "fallback",
    "variantes_interdites",
    "preuves_identite_futures",
    "jamais_preuve",
    "sources_historiques",
    "sentinelles",
}
_CLES_PORTEE_RECUPERATION = {"issue", "product_version", "tranche"}
_CLES_CONFIGURATION_RECUPERATION = {
    "configuration_id",
    "acquisition_id",
    "descripteur",
}
_CLES_DESCRIPTEUR_RECUPERATION = {"argv", "stimulus_utf8"}
_CLES_PREUVE_IDENTITE_RECUPERATION = {
    "configuration_id",
    "observe_uniquement_par",
    "sinon",
}
_CLES_SOURCE_HISTORIQUE_RECUPERATION = {"chemin", "sha256"}
_CLES_SENTINELLE_RECUPERATION = {
    "configuration_id",
    "lien",
    "marqueur",
    "exclusion_fermee",
}


def _structure_verrou_recuperation(sources: list[dict]) -> dict:
    """Parties fermées du verrou : seules les sources varient."""
    return {
        "schema_version": SCHEMA_VERROU_RECUPERATION,
        "portee": {
            "issue": ISSUE_RECUPERATION,
            "product_version": "V1",
            "tranche": TRANCHE_RECUPERATION,
        },
        "configurations": [
            {
                "configuration_id": CONFIGURATION_ANTIGRAVITY_RECUPERATION,
                "acquisition_id": CRENEAU_ANTIGRAVITY_RECUPERATION,
                "descripteur": {
                    "argv": list(DESCRIPTEUR_ANTIGRAVITY_RECUPERATION),
                    "stimulus_utf8": MODE_STIMULUS_ARGUMENT,
                },
            },
            {
                "configuration_id": CONFIGURATION_ZAI_RECUPERATION,
                "acquisition_id": CRENEAU_ZAI_RECUPERATION,
                "descripteur": {
                    "argv": list(DESCRIPTEUR_ZAI_RECUPERATION),
                    "stimulus_utf8": MODE_STIMULUS_STDIN,
                },
            },
        ],
        "autorite_execution": "NOT_GRANTED",
        "creneaux_executes": 0,
        "reprises_executees": 0,
        "fallback": "NONE",
        "variantes_interdites": list(VARIANTES_INTERDITES_RECUPERATION),
        "preuves_identite_futures": [
            {
                "configuration_id": CONFIGURATION_ZAI_RECUPERATION,
                "observe_uniquement_par": CONDITION_OBSERVED_ZAI,
                "sinon": SINON_PROVENANCE_RECUPERATION,
            },
            {
                "configuration_id": CONFIGURATION_ANTIGRAVITY_RECUPERATION,
                "observe_uniquement_par": CONDITION_OBSERVED_ANTIGRAVITY,
                "sinon": SINON_PROVENANCE_RECUPERATION,
            },
        ],
        "jamais_preuve": list(JAMAIS_PREUVE_RECUPERATION),
        "sources_historiques": sources,
        "sentinelles": [
            {
                "configuration_id": CONFIGURATION_ANTIGRAVITY_RECUPERATION,
                "lien": ISSUE_SENTINELLES_RECUPERATION,
                "marqueur": SENTINELLE_DIAGNOSTIC_NON_CANDIDAT,
                "exclusion_fermee": list(EXCLUSION_FERMEE_SENTINELLE),
            },
            {
                "configuration_id": CONFIGURATION_ZAI_RECUPERATION,
                "lien": ISSUE_SENTINELLES_RECUPERATION,
                "marqueur": SENTINELLE_DIAGNOSTIC_NON_CANDIDAT,
                "exclusion_fermee": list(EXCLUSION_FERMEE_SENTINELLE),
            },
        ],
    }


def _construire_verrou_recuperation(racine: Path) -> dict:
    """Verrou additif exact : chaque octet courant de source historique est
    croisé avec la constante figée du contrat et avec son épinglage existant
    (autorisation, verrou de campagne, registre de validation) lorsqu'il
    existe. N'exécute aucune commande."""
    try:
        autorisation = _charger_autorisation_acquisition(racine)
    except ErreurAutorisation as erreur:
        raise ErreurRecuperation(
            "champ 'sources_historiques' : autorisation D-V1-04 absente ou "
            f"divergente : {erreur}"
        ) from erreur
    try:
        verrou_campagne = json.loads(
            (racine / CHEMIN_VERROU).read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurRecuperation(
            "champ 'sources_historiques' : verrou de campagne illisible : "
            f"{erreur}"
        ) from erreur
    panel = (
        verrou_campagne.get("panel")
        if isinstance(verrou_campagne, dict)
        else None
    )
    references_panel: dict[str, dict] = {}
    if isinstance(panel, list):
        for entree in panel:
            if isinstance(entree, dict):
                references_panel[entree.get("configuration_id")] = (
                    entree.get("configuration")
                )
    try:
        registre_charge = _charger_registre_validation(racine)
    except ErreurRestitution as erreur:
        raise ErreurRecuperation(
            "champ 'sources_historiques' : registre de validation "
            f"divergent : {erreur}"
        ) from erreur
    if registre_charge is None:
        raise ErreurRecuperation(
            "champ 'sources_historiques' : registre de validation absent, "
            "reçus HARNESS_ERROR requis"
        )
    references_recus: dict[str, tuple[str, str]] = {}
    for entree in registre_charge[1]["entrees"]:
        # Seules les entrées -001 (créneau à deux segments) épinglent la
        # chaîne historique : les entrées de récupération -002 portent un
        # créneau à trois segments et ne réécrivent jamais ces épingles
        if entree["creneau"].count(":") == 1 and entree["configuration_id"] in (
            CONFIGURATION_ANTIGRAVITY_RECUPERATION,
            CONFIGURATION_ZAI_RECUPERATION,
        ):
            references_recus[entree["configuration_id"]] = (
                entree["recu"],
                entree["recu_sha256"],
            )
    # Épinglages existants : la fonction de chargement de l'autorisation a
    # déjà vérifié le verrou et le stimulus contre les siens.
    epingles: dict[str, str] = {
        autorisation["verrou"]["chemin"]: autorisation["verrou"]["sha256"],
        autorisation["stimulus"]["chemin"]: autorisation["stimulus"]["sha256"],
    }
    for identifiant in (
        CONFIGURATION_ANTIGRAVITY_RECUPERATION,
        CONFIGURATION_ZAI_RECUPERATION,
    ):
        reference = references_panel.get(identifiant)
        if not isinstance(reference, dict):
            raise ErreurRecuperation(
                "champ 'sources_historiques' : entrée de panel absente pour "
                f"'{identifiant}'"
            )
        epingles[reference["chemin"]] = reference["sha256"]
        recu = references_recus.get(identifiant)
        if recu is None:
            raise ErreurRecuperation(
                "champ 'sources_historiques' : reçu HARNESS_ERROR absent du "
                f"registre pour '{identifiant}'"
            )
        epingles[recu[0]] = recu[1]
    for chemin_epingle in epingles:
        if chemin_epingle not in CHEMINS_SOURCES_HISTORIQUES_RECUPERATION:
            raise ErreurRecuperation(
                "champ 'sources_historiques' : épinglage hors de la chaîne "
                f"historique figée pour '{chemin_epingle}'"
            )
    sources: list[dict] = []
    for chemin in CHEMINS_SOURCES_HISTORIQUES_RECUPERATION:
        constante = EMPREINTES_SOURCES_HISTORIQUES_RECUPERATION[chemin]
        try:
            sha_obtenu = _sha256_fichier(racine / chemin)
        except OSError as erreur:
            raise ErreurRecuperation(
                "champ 'sources_historiques' : fichier illisible "
                f"'{chemin}' : {erreur}"
            ) from erreur
        if sha_obtenu != constante:
            raise ErreurRecuperation(
                "champ 'sources_historiques' : constante figée divergente "
                f"pour '{chemin}' : {constante} attendu, {sha_obtenu} obtenu"
            )
        if chemin in epingles and sha_obtenu != epingles[chemin]:
            raise ErreurRecuperation(
                "champ 'sources_historiques' : épinglage existant divergent "
                f"pour '{chemin}' : {epingles[chemin]} attendu, "
                f"{sha_obtenu} obtenu"
            )
        sources.append({"chemin": chemin, "sha256": sha_obtenu})
    return _structure_verrou_recuperation(sources)


def _nommer_divergence_entrees(
    existant: object, attendu: list, cle: str, cle_identifiant: str
) -> str:
    attendues = {
        entree.get(cle_identifiant): entree
        for entree in attendu
        if isinstance(entree, dict)
    }
    presentes = existant if isinstance(existant, list) else []
    vues = set()
    for entree in presentes:
        if not isinstance(entree, dict):
            return f"{cle}[entree_sans_{cle_identifiant}]"
        identifiant = entree.get(cle_identifiant)
        vues.add(identifiant)
        attendue = attendues.get(identifiant)
        if attendue is None:
            return f"{cle}[{identifiant}]"
        for sous_cle in sorted(set(entree) | set(attendue)):
            if entree.get(sous_cle) == attendue.get(sous_cle):
                continue
            if isinstance(attendue.get(sous_cle), dict) and isinstance(
                entree.get(sous_cle), dict
            ):
                for sous_sous_cle in sorted(
                    set(entree[sous_cle]) | set(attendue[sous_cle])
                ):
                    if (
                        entree[sous_cle].get(sous_sous_cle)
                        != attendue[sous_cle].get(sous_sous_cle)
                    ):
                        return f"{cle}[{identifiant}].{sous_cle}.{sous_sous_cle}"
            return f"{cle}[{identifiant}].{sous_cle}"
    for identifiant in attendues:
        if identifiant not in vues:
            return f"{cle}[{identifiant}]"
    return cle


def _nommer_divergence_recuperation(existant: object, attendu: dict) -> str:
    """Champ fautif exact d'un verrou de récupération divergent."""
    if not isinstance(existant, dict):
        return "schema_version"
    for cle in sorted(set(attendu) | set(existant)):
        if existant.get(cle) == attendu.get(cle):
            continue
        if cle in (
            "configurations",
            "preuves_identite_futures",
            "sentinelles",
        ):
            return _nommer_divergence_entrees(
                existant.get(cle), attendu[cle], cle, "configuration_id"
            )
        if cle == "sources_historiques":
            return _nommer_divergence_entrees(
                existant.get(cle), attendu[cle], cle, "chemin"
            )
        return cle
    return "schema_version"


def _verifier_verrou_recuperation(
    chemin: Path, octets_attendus: bytes
) -> None:
    """Vérifie l'octet existant sans réécriture ; toute divergence nomme le
    champ fautif."""
    infos = os.lstat(chemin)
    if stat.S_ISLNK(infos.st_mode) or not stat.S_ISREG(infos.st_mode):
        raise ErreurRecuperation(
            "verrou de récupération : fichier régulier non symbolique attendu"
        )
    octets = chemin.read_bytes()
    if octets == octets_attendus:
        return
    try:
        existant = json.loads(octets.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        existant = None
    champ = _nommer_divergence_recuperation(
        existant, json.loads(octets_attendus.decode("utf-8"))
    )
    raise ErreurRecuperation(
        "verrou de récupération divergent : champ fautif "
        f"'{champ}' (LOCKED_ARTIFACT_CHANGED) : aucune réécriture"
    )


# Contrat fermé de l'Issue #133 : exécution des acquisitions de récupération
# sous l'autorité propriétaire additive D-V1-05 ; le verrou R1 reste
# byte-identique et conserve NOT_GRANTED, cet artefact séparé porte seul le GO
SCHEMA_AUTORISATION_RECUPERATION = "campagne-v1-autorisation-recuperation/v1"
CHEMIN_AUTORISATION_RECUPERATION = (
    _RACINE_CAMPAGNE_V1
    / "recuperation-harnais-v1"
    / "autorisation-recuperation-v1.json"
)
SECTION_AUTORISATION_RECUPERATION = (
    "autorisation de récupération D-V1-05 versionnée"
)
ISSUE_RECUPERATION_EXECUTION = (
    "https://github.com/ayoahha/benchmark-lab-x/issues/133"
)
TRANCHE_RECUPERATION_EXECUTION = "V1-R2"
AUTORITE_RECUPERATION = "D-V1-05"
JETON_AUTORITE_RECUPERATION = (
    "D_V1_05 = AUTHORIZE:CANDIDATES_HIGH_COMMON; AGENTS_MEDIUM"
)
URL_COMMENTAIRE_RECUPERATION = (
    "https://github.com/ayoahha/benchmark-lab-x/issues/133"
    "#issuecomment-5439130978"
)
AUTEUR_COMMENTAIRE_RECUPERATION = "ayoahha"
ASSOCIATION_COMMENTAIRE_RECUPERATION = "OWNER"
DATE_COMMENTAIRE_RECUPERATION = "2026-08-27"
SHA256_COMMENTAIRE_RECUPERATION = (
    "fca4d1d29b406e969613a269a46866b59f34364c5fb121db728fe6a61fff347f"
)
EMPREINTE_VERROU_RECUPERATION = (
    "d9d68f69a29826d9caa9db70d567df99c9e971ad8eaded6f15501dc71994f233"
)
EFFORT_CANDIDAT_RECUPERATION = "high"
RELATIF_EXECUTION_R2 = Path("v1-execution") / "r2"
# Sonde read-only du plan de contrôle OpenCodex, seule source de trace
# attribuable Z.AI : jamais générative, jamais mutatrice
SONDE_TRACE_ZAI = ("opencodex", "observe", "usage")
_CLES_EFFORT_TRACE_ZAI = (
    "effort_effectif",
    "reasoning_effort",
    "model_reasoning_effort",
    "reasoningEffort",
    "effort",
)


def _structure_autorisation_recuperation() -> dict:
    """Contenu canonique fermé de l'autorisation additive D-V1-05."""
    return {
        "schema_version": SCHEMA_AUTORISATION_RECUPERATION,
        "autorite": AUTORITE_RECUPERATION,
        "jeton": JETON_AUTORITE_RECUPERATION,
        "commentaire": {
            "url": URL_COMMENTAIRE_RECUPERATION,
            "auteur": AUTEUR_COMMENTAIRE_RECUPERATION,
            "association": ASSOCIATION_COMMENTAIRE_RECUPERATION,
            "date": DATE_COMMENTAIRE_RECUPERATION,
            "sha256_corps": SHA256_COMMENTAIRE_RECUPERATION,
        },
        "verrou_recuperation": {
            "chemin": CHEMIN_VERROU_RECUPERATION.as_posix(),
            "sha256": EMPREINTE_VERROU_RECUPERATION,
        },
        "stimulus": {
            "chemin": CHEMIN_STIMULUS,
            "sha256": EMPREINTES_SOURCES_HISTORIQUES_RECUPERATION[
                CHEMIN_STIMULUS
            ],
        },
        "portee": {
            "issue": ISSUE_RECUPERATION_EXECUTION,
            "tranche": TRANCHE_RECUPERATION_EXECUTION,
            "acquisitions": [
                {
                    "acquisition_id": CRENEAU_ANTIGRAVITY_RECUPERATION,
                    "configuration_id": CONFIGURATION_ANTIGRAVITY_RECUPERATION,
                },
                {
                    "acquisition_id": CRENEAU_ZAI_RECUPERATION,
                    "configuration_id": CONFIGURATION_ZAI_RECUPERATION,
                },
            ],
            "appels_fournisseur_max": 2,
            "appels_par_creneau": 1,
            "consommation_quota": "ABONNEMENTS_EXISTANTS",
            "depense_incrementale": 0,
            "reprises_automatiques": 0,
            "reprises_manuelles": 0,
            "fallback": "NONE",
            "effort_candidat": EFFORT_CANDIDAT_RECUPERATION,
        },
    }


def _nommer_divergence_autorisation(
    existant: object, attendu: dict, prefixe: str = ""
) -> str:
    """Champ fautif exact d'une autorisation de récupération divergente."""
    if not isinstance(existant, dict):
        return prefixe.rstrip(".") or "schema_version"
    for cle in sorted(set(attendu) | set(existant)):
        if existant.get(cle) == attendu.get(cle):
            continue
        chemin = f"{prefixe}{cle}"
        if cle == "acquisitions":
            return _nommer_divergence_entrees(
                existant.get(cle), attendu[cle], chemin, "configuration_id"
            )
        if isinstance(attendu.get(cle), dict) and isinstance(
            existant.get(cle), dict
        ):
            return _nommer_divergence_autorisation(
                existant[cle], attendu[cle], f"{chemin}."
            )
        return chemin
    return prefixe.rstrip(".") or "schema_version"


def _verifier_autorisation_recuperation(
    chemin: Path, octets_attendus: bytes
) -> None:
    """Vérifie l'octet existant de l'autorisation sans réécriture ; toute
    divergence nomme le champ fautif."""
    infos = os.lstat(chemin)
    if stat.S_ISLNK(infos.st_mode) or not stat.S_ISREG(infos.st_mode):
        raise ErreurRecuperation(
            "autorisation de récupération : fichier régulier non symbolique "
            "attendu"
        )
    octets = chemin.read_bytes()
    if octets == octets_attendus:
        return
    try:
        existant = json.loads(octets.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        existant = None
    champ = _nommer_divergence_autorisation(
        existant, json.loads(octets_attendus.decode("utf-8"))
    )
    raise ErreurRecuperation(
        "autorisation de récupération divergente : champ fautif "
        f"'{champ}' (LOCKED_ARTIFACT_CHANGED) : aucune réécriture"
    )


def _charger_autorisation_recuperation(racine: Path) -> dict:
    """Autorisation D-V1-05 validée fail-closed : octets canoniques exacts,
    verrou R1 byte-identique à l'empreinte figée d9d68f69."""
    chemin = racine / CHEMIN_AUTORISATION_RECUPERATION
    if not os.path.lexists(chemin):
        raise ErreurRecuperation(
            "AUTORITE_ABSENTE : autorisation D-V1-05 non matérialisée "
            f"({CHEMIN_AUTORISATION_RECUPERATION.as_posix()})"
        )
    attendu = _structure_autorisation_recuperation()
    _verifier_autorisation_recuperation(chemin, octets_canoniques(attendu))
    verrou = racine / CHEMIN_VERROU_RECUPERATION
    if not verrou.is_file() or _sha256_fichier(verrou) != (
        EMPREINTE_VERROU_RECUPERATION
    ):
        raise ErreurRecuperation(
            "verrou R1 absent ou divergent de l'empreinte autorisée "
            f"{EMPREINTE_VERROU_RECUPERATION} (LOCKED_ARTIFACT_CHANGED)"
        )
    return attendu


def preparer_recuperation(racine: Path) -> int:
    """Matérialise une seule fois le verrou additif de récupération V1-R1
    puis l'autorisation additive D-V1-05, ou vérifie les octets existants
    sans les réécrire. N'exécute aucune commande externe de fournisseur, de
    modèle ou de harnais."""
    try:
        attendu = _construire_verrou_recuperation(racine)
    except ErreurRecuperation as erreur:
        print(f"ECHEC {erreur}")
        return 2
    except OSError as erreur:
        print(
            "ECHEC construction du verrou de récupération : erreur "
            f"d'accès nommée : {erreur}"
        )
        return 2
    octets_attendus = octets_canoniques(attendu)
    autorisation_attendue = octets_canoniques(
        _structure_autorisation_recuperation()
    )
    chemin = racine / CHEMIN_VERROU_RECUPERATION
    chemin_autorisation = racine / CHEMIN_AUTORISATION_RECUPERATION
    try:
        for cible, octets, verifier, nom_artefact in (
            (chemin, octets_attendus, _verifier_verrou_recuperation, "verrou"),
            (
                chemin_autorisation,
                autorisation_attendue,
                _verifier_autorisation_recuperation,
                "autorisation",
            ),
        ):
            if os.path.lexists(cible):
                verifier(cible, octets)
                continue
            cible.parent.mkdir(parents=True, exist_ok=True)
            try:
                descripteur = os.open(
                    cible, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644
                )
            except FileExistsError as erreur:
                # Course de création distincte : aucune réparation ni
                # réécriture dans la même invocation ; l'invocation
                # suivante vérifiera l'octet existant.
                raise ErreurRecuperation(
                    f"création concurrente détectée : le {nom_artefact} de "
                    "récupération existe déjà (LOCKED_ARTIFACT_CHANGED) : "
                    "aucune réécriture, une nouvelle invocation vérifiera "
                    "l'octet existant"
                ) from erreur
            with os.fdopen(descripteur, "wb") as flux:
                flux.write(octets)
    except ErreurRecuperation as erreur:
        print(f"ECHEC {erreur}")
        return 2
    except OSError as erreur:
        nom = Path(erreur.filename).name if erreur.filename else "inconnu"
        print(
            "ECHEC artefact de récupération inaccessible : "
            f"'{nom}' ({erreur.strerror})"
        )
        return 2
    empreinte = hashlib.sha256(octets_attendus).hexdigest()
    empreinte_autorisation = hashlib.sha256(autorisation_attendue).hexdigest()
    print(
        "verrou de récupération vérifié : "
        f"{CHEMIN_VERROU_RECUPERATION.as_posix()}"
    )
    print(
        "créneaux : 2 · autorite_execution : NOT_GRANTED · "
        "creneaux_executes : 0 · reprises_executees : 0 · fallback : NONE"
    )
    print(
        "autorisation additive vérifiée : "
        f"{CHEMIN_AUTORISATION_RECUPERATION.as_posix()}"
    )
    print(
        f"AUTORITE_EXECUTION : {AUTORITE_RECUPERATION} (additive, verrou "
        "NOT_GRANTED byte-identique) · créneaux "
        f"{CRENEAU_ANTIGRAVITY_RECUPERATION} et {CRENEAU_ZAI_RECUPERATION} · "
        f"effort candidat commun {EFFORT_CANDIDAT_RECUPERATION} · reprises "
        "0 · fallback NONE · dépense incrémentale 0"
    )
    print(f"empreinte SHA-256 : {empreinte}")
    print(f"empreinte SHA-256 de l'autorisation : {empreinte_autorisation}")
    return 0


def _refus_recuperation(fait: str) -> int:
    print(f"ECHEC {fait}")
    return 2


def _enregistrements_usage_opencodex(texte: str) -> list[dict] | None:
    """Enregistrements fournisseur/modèle lisibles de la sonde d'usage
    OpenCodex : None quand aucun JSON n'est lisible, liste sinon.

    Projection fermée : seuls les objets portant à la fois 'model' et
    'provider' (ou 'fournisseur') sont retenus ; tout le reste est ignoré
    sans invention de valeur."""
    documents: list[object] = []
    try:
        documents.append(json.loads(texte))
    except json.JSONDecodeError:
        for ligne in texte.splitlines():
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                documents.append(json.loads(ligne))
            except json.JSONDecodeError:
                continue
    if not documents:
        return None
    enregistrements: list[dict] = []

    def visiter(valeur: object) -> None:
        if isinstance(valeur, dict):
            if "model" in valeur and (
                "provider" in valeur or "fournisseur" in valeur
            ):
                enregistrements.append(valeur)
            for sous_valeur in valeur.values():
                visiter(sous_valeur)
        elif isinstance(valeur, list):
            for element in valeur:
                visiter(element)

    for document in documents:
        visiter(document)
    return enregistrements


def _trace_zai_recuperation(
    acquisition_id: str,
    avant: list[dict] | None,
    apres: list[dict] | None,
) -> tuple[dict | None, str | None]:
    """Trace OpenCodex attribuable à la tentative unique par différence
    stricte avant/après : seuls les enregistrements nouveaux comptent.

    Rend (trace, preuve) ou (None, None) sans délta attribuable. Le nombre
    de tentatives est le compte exact des enregistrements nouveaux ; un
    enregistrement nouveau hors du couple zai/glm-5.3 rend le fallback
    observé divergent au lieu de NONE. Aucun champ absent n'est inventé."""
    if apres is None:
        return None, None
    connus: dict[str, int] = {}
    for enregistrement in avant or []:
        adresse = adresse_canonique(enregistrement)
        connus[adresse] = connus.get(adresse, 0) + 1
    nouveaux: list[dict] = []
    vus: dict[str, int] = {}
    for enregistrement in apres:
        adresse = adresse_canonique(enregistrement)
        vus[adresse] = vus.get(adresse, 0) + 1
        if vus[adresse] > connus.get(adresse, 0):
            nouveaux.append(enregistrement)
    if not nouveaux:
        return None, None

    def _modele(enregistrement: dict) -> str:
        valeur = str(enregistrement.get("model"))
        prefixe = f"{FOURNISSEUR_ZAI}/"
        return valeur[len(prefixe):] if valeur.startswith(prefixe) else valeur

    def _fournisseur(enregistrement: dict) -> str:
        return str(
            enregistrement.get("provider", enregistrement.get("fournisseur"))
        )

    correspondants = [
        enregistrement
        for enregistrement in nouveaux
        if _modele(enregistrement) == "glm-5.3"
        and _fournisseur(enregistrement) == FOURNISSEUR_ZAI
    ]
    reference = correspondants[0] if correspondants else nouveaux[0]
    trace: dict = {
        "tentative_id": acquisition_id,
        "fournisseur": _fournisseur(reference),
        "modele": _modele(reference),
        "tentatives": len(nouveaux),
        "fallback": (
            "NONE" if len(nouveaux) == len(correspondants) else "OBSERVE"
        ),
    }
    for cle in _CLES_EFFORT_TRACE_ZAI:
        if cle in reference:
            trace["effort_effectif"] = str(reference[cle])
            break
    # Preuve projetée sur les seuls champs fermés : la sortie brute des
    # sondes reste dans l'espace réel privé, jamais dans le reçu public
    projection = [
        {
            "fournisseur": _fournisseur(enregistrement),
            "modele": _modele(enregistrement),
            **{
                "effort": str(enregistrement[cle])
                for cle in _CLES_EFFORT_TRACE_ZAI
                if cle in enregistrement
            },
        }
        for enregistrement in nouveaux
    ]
    preuve = (
        "délta d'usage OpenCodex après la tentative unique : "
        + octets_canoniques(projection).decode("utf-8").strip()
    )
    return trace, preuve


def _trace_antigravity_recuperation(
    acquisition_id: str, stdout: str, stderr: str
) -> tuple[dict | None, str | None]:
    """Métadonnée d'identité servie émise par la tentative Antigravity :
    première ligne 'model:' de la sortie capturée, ou (None, None)."""
    for texte in (stdout, stderr):
        correspondance = _MOTIF_IDENTITE_SERVIE.search(texte)
        if correspondance is not None:
            return (
                {
                    "tentative_id": acquisition_id,
                    "modele": correspondance.group(1),
                },
                correspondance.group(0).strip(),
            )
    return None, None


def acquerir_recuperation(
    racine: Path, identifiant: str, racine_privee: Path | None = None
) -> int:
    """Exécute une seule fois le créneau -002 autorisé par D-V1-05.

    Fail-closed : autorisation additive, verrou R1, sources historiques,
    reçus, journal R2 et espace de tentative sont vérifiés avant toute
    résolution d'exécutable ; le préflight non génératif de la route doit
    rendre READY avant l'unique appel candidat. Aucun retry, aucun
    fallback, aucune reprise.
    """
    if racine_privee is None:
        racine_privee = RACINE_PRIVEE_PRODUCTION
    if not _MOTIF_SLUG.match(identifiant):
        return _refus_recuperation(
            f"champ 'configuration_id' : '{identifiant}' n'est pas un slug "
            "stable ; identifiant refusé avant toute résolution de chemin"
        )
    try:
        # L'autorité additive d'abord : son absence rend AUTORITE_ABSENTE
        # avant toute autre vérification, puis le verrou R1 et les sept
        # sources historiques sont revérifiés byte-identiques
        autorisation = _charger_autorisation_recuperation(racine)
        attendu_verrou = _construire_verrou_recuperation(racine)
        _verifier_verrou_recuperation(
            racine / CHEMIN_VERROU_RECUPERATION,
            octets_canoniques(attendu_verrou),
        )
    except ErreurRecuperation as erreur:
        return _refus_recuperation(
            f"{erreur} ; aucun processus fournisseur créé, aucun espace de "
            "tentative, aucun journal, aucun reçu"
        )
    except OSError as erreur:
        return _refus_recuperation(
            f"artefact de récupération illisible : {erreur} ; aucun "
            "processus fournisseur créé, aucun espace de tentative, aucun "
            "journal, aucun reçu"
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
        return _refus_recuperation(
            f"configuration '{identifiant}' hors de la portée D-V1-05 : "
            "seuls les deux créneaux -002 sont autorisés à acquérir"
        )
    acquisition_id = creneau_autorise["acquisition_id"]
    stimulus_sha = autorisation["stimulus"]["sha256"]
    creneau = f"{identifiant}:{stimulus_sha}:{acquisition_id}"
    chemin_configuration = racine / REGISTRE_OFFICIEL / f"{identifiant}.toml"
    try:
        configuration = _charger_configuration(chemin_configuration)
    except ErreurConfiguration as erreur:
        return _refus_recuperation(str(erreur))
    sources: dict[str, dict] = {}
    for nom, relatif in (
        ("carte", CHEMIN_CARTE),
        ("paquet", CHEMIN_PAQUET),
        ("stimulus", CHEMIN_STIMULUS),
    ):
        chemin_source = racine / relatif
        if not chemin_source.is_file():
            return _refus_recuperation(f"source du reçu absente : {relatif}")
        sources[nom] = {
            "chemin": relatif,
            "sha256": _sha256_fichier(chemin_source),
        }
    if sources["stimulus"]["sha256"] != stimulus_sha:
        return _refus_recuperation(
            "stimulus divergent de l'autorisation D-V1-05 : aucun appel"
        )
    try:
        etat = _charger_etat(racine)
    except ErreurRestitution as erreur:
        return _refus_recuperation(str(erreur))
    repertoire = _repertoire_recus(racine, etat)
    try:
        recus = _charger_recus(repertoire)
    except ErreurRecu as erreur:
        return _refus_recuperation(str(erreur))
    for _, existant in recus:
        if existant["payload"]["creneau"] == creneau:
            return _refus_recuperation(
                f"collision append-only : le créneau '{creneau}' est déjà "
                "occupé, aucun retry et aucune réécriture"
            )
    chemin_journal = (
        racine_privee / RELATIF_EXECUTION_R2 / NOM_JOURNAL_EXECUTION
    )
    try:
        journal = _charger_journal_execution(chemin_journal)
    except ErreurJournal as erreur:
        return _refus_recuperation(f"journal d'exécution R2 : {erreur} ; HOLD")
    if journal is None:
        journal = {"schema_version": SCHEMA_JOURNAL_EXECUTION, "entrees": []}
    for entree in journal["entrees"]:
        if entree["acquisition_id"] == acquisition_id:
            return _refus_recuperation(
                f"créneau '{acquisition_id}' déjà consommé selon le journal "
                "R2 : aucun second appel du même créneau, aucun retry"
            )
        if entree["etat_terminal"] == "IDENTITY_MISMATCH":
            return _refus_recuperation(
                "HOLD : une identité servie divergente est journalisée en "
                "R2, aucun appel suivant avant arbitrage propriétaire"
            )
        if entree["descendants"]:
            return _refus_recuperation(
                "HOLD : un descendant survivant est journalisé en R2, aucun "
                "appel suivant avant arbitrage propriétaire"
            )
        if entree["recu"] is None:
            return _refus_recuperation(
                "HOLD : une tentative sans reçu est journalisée en R2, "
                "aucun appel suivant avant arbitrage propriétaire"
            )
    espace_tentative = (
        racine_privee / RELATIF_EXECUTION_R2 / NOM_RUNTIME_XS08 / acquisition_id
    )
    if os.path.lexists(espace_tentative):
        return _refus_recuperation(
            f"espace réel de tentative déjà présent pour '{acquisition_id}' : "
            "le créneau est consommé, aucun retry et aucun nettoyage"
        )
    # Préflight non génératif de la route, exécuté une fois par invocation :
    # tout verdict différent de READY bloque ce seul créneau avant l'appel
    # candidat ; l'autre créneau indépendant reste vérifiable
    if identifiant == CONFIGURATION_ANTIGRAVITY_RECUPERATION:
        observation = _observer_route_antigravity()
        descripteur_declare = DESCRIPTEUR_ANTIGRAVITY_RECUPERATION
    else:
        # Demande canonique non préfixée de la configuration validée :
        # _observer_route_zai préfixe lui-même 'zai/', extraire '--model'
        # du descripteur produirait la cible fausse 'zai/zai/glm-5.3'
        observation = _observer_route_zai(configuration["modele"]["demande"])
        descripteur_declare = DESCRIPTEUR_ZAI_RECUPERATION
    if observation["verdict"] != "READY":
        return _refus_recuperation(
            f"PREFLIGHT_NON_READY : créneau '{acquisition_id}' bloqué avant "
            f"tout appel candidat : verdict {observation['verdict']} · "
            f"cause {observation['cause']} — {observation['fait']} ; aucun "
            "processus candidat créé"
        )
    stimulus_octets = (racine / CHEMIN_STIMULUS).read_bytes()
    espace = espace_tentative / "espace"
    try:
        tentative = construire_tentative_recuperation(
            identifiant, stimulus_octets, str(espace)
        )
    except ErreurRecuperation as erreur:
        return _refus_recuperation(str(erreur))
    argv_execute = tentative["argv"]
    if any(element in FLAGS_INTERDITS_ACQUISITION for element in argv_execute):
        return _refus_recuperation(
            "flag interdit présent dans le descripteur résolu : aucun appel"
        )
    espace.mkdir(parents=True, exist_ok=False)
    sonde_avant = sonde_apres = None
    if identifiant == CONFIGURATION_ZAI_RECUPERATION:
        sonde_avant = _executer_borne(
            list(SONDE_TRACE_ZAI), b"", espace, DELAI_SONDE_PREFLIGHT
        )
    entree_stdin = tentative["stdin"] if tentative["stdin"] is not None else b""
    depart_tentative = time.monotonic()
    execution, descendants = _executer_acquisition(
        argv_execute, entree_stdin, espace, DELAI_ACQUISITION_OFFICIELLE
    )
    latence_tentative_ms = int((time.monotonic() - depart_tentative) * 1000)
    trace = preuve_trace = None
    if execution["etat"] == "OBSERVED":
        # La sortie texte candidate est conservée dans l'espace réel privé
        (espace_tentative / "sortie-stdout.txt").write_text(
            execution["sortie"]["stdout"], encoding="utf-8"
        )
        (espace_tentative / "sortie-stderr.txt").write_text(
            execution["sortie"]["stderr"], encoding="utf-8"
        )
        if identifiant == CONFIGURATION_ZAI_RECUPERATION:
            sonde_apres = _executer_borne(
                list(SONDE_TRACE_ZAI), b"", espace, DELAI_SONDE_PREFLIGHT
            )
            for nom, sonde in (
                ("avant", sonde_avant),
                ("apres", sonde_apres),
            ):
                if sonde is not None and sonde["etat"] == "OBSERVED":
                    (espace_tentative / f"trace-usage-{nom}.txt").write_text(
                        sonde["sortie"]["stdout"]
                        + sonde["sortie"]["stderr"],
                        encoding="utf-8",
                    )
            avant = (
                _enregistrements_usage_opencodex(
                    sonde_avant["sortie"]["stdout"]
                )
                if sonde_avant is not None
                and sonde_avant["etat"] == "OBSERVED"
                else None
            )
            apres = (
                _enregistrements_usage_opencodex(
                    sonde_apres["sortie"]["stdout"]
                )
                if sonde_apres is not None
                and sonde_apres["etat"] == "OBSERVED"
                else None
            )
            trace, preuve_trace = _trace_zai_recuperation(
                acquisition_id, avant, apres
            )
        else:
            trace, preuve_trace = _trace_antigravity_recuperation(
                acquisition_id,
                execution["sortie"]["stdout"],
                execution["sortie"]["stderr"],
            )
    identite = evaluer_identite_servie_recuperation(
        identifiant, trace if execution["etat"] == "OBSERVED" else None
    )
    if (
        execution["etat"] == "OBSERVED"
        and identite["incident"] == "IDENTITY_MISMATCH"
    ):
        execution = {
            "etat": "INCIDENT",
            "incident": "IDENTITY_MISMATCH",
            "fait": (
                "identité servie divergente de la trace attribuable : "
                "champs " + ", ".join(identite["champs_divergents"]) + " ; "
                "le créneau est consommé, HOLD avant tout appel suivant"
            ),
            "preuve_attribuable": (
                preuve_trace
                if preuve_trace is not None
                else "trace attribuable divergente"
            ),
        }
    elif (
        execution["etat"] == "OBSERVED"
        and execution["code_sortie"] != 0
        and execution["sortie"]["stdout"] == ""
    ):
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
    if identite["statut"] == "OBSERVED" and execution["etat"] == "OBSERVED":
        provenance: object = {
            "etat": "OBSERVED",
            "valeur": dict(
                _IDENTITE_EXACTE_ANTIGRAVITY
                if identifiant == CONFIGURATION_ANTIGRAVITY_RECUPERATION
                else _IDENTITE_EXACTE_ZAI
            ),
            "preuve": preuve_trace,
        }
    else:
        provenance = INCONNU
        if identite["statut"] == "OBSERVED":
            # Trace exacte mais exécution reclassée en incident : la
            # provenance reste INCONNU, jamais promue sans sortie candidate
            identite = {
                "statut": INCONNU,
                "disposition": "HOLD",
                "incident": None,
                "champs_divergents": [],
                "cause": (
                    "trace exacte sans sortie candidate observée : aucune "
                    "promotion"
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
            "argv_resolu": list(descripteur_declare),
            "mode_stdin": (
                MODE_STIMULUS_STDIN
                if identifiant == CONFIGURATION_ZAI_RECUPERATION
                else MODE_STIMULUS_ARGUMENT
            ),
            "espace_de_travail": JETON_ESPACE_ISOLE,
        },
        "execution": execution,
        "provenance_servie": provenance,
        "recuperation": {
            "tranche": TRANCHE_RECUPERATION_EXECUTION,
            "autorite": AUTORITE_RECUPERATION,
            "acquisition_id": acquisition_id,
            "identite_servie": identite,
        },
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
                "uv run tools/campagne_v1.py acquerir --recuperation "
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
            "reçu V1 de récupération écrit : "
            f"{destination.relative_to(racine).as_posix()}"
        )
        print(f"créneau : {creneau}")
        print(f"adresse de contenu : {adresse}")
    print(f"état terminal : {etat_terminal}")
    if execution["etat"] == "INCIDENT":
        print(f"incident : {execution['incident']} — {execution['fait']}")
    print(
        f"identité servie : {identite['statut']} · disposition "
        f"{identite['disposition']}"
    )
    if identite["cause"]:
        print(f"cause d'identité : {identite['cause']}")
    if identite["disposition"] == "HOLD":
        print(
            "HOLD : provenance servie non attribuable ou divergente pour "
            f"'{acquisition_id}' ; aucun appel suivant sans arbitrage "
            "propriétaire"
        )
    print(f"descendants survivants : {descendants}")
    if descendants:
        print(
            "ECHEC descendant survivant détecté après la tentative : groupe "
            "tué, HOLD avant tout appel suivant"
        )
    return code_commande


_IDENTITE_EXACTE_ZAI = {
    "fournisseur": "zai",
    "modele": "glm-5.3",
    "effort_effectif": "high",
    "tentatives": 1,
    "fallback": "NONE",
}
_IDENTITE_EXACTE_ANTIGRAVITY = {"modele": "gemini-3.7-flash-high"}
_MARQUEUR_DEMANDE = "REQUESTED"


def construire_tentative_recuperation(
    identifiant: str, stimulus_utf8: bytes, espace_isole: str
) -> dict:
    """Adaptateur pur : construit la tentative de récupération fermée sans
    résoudre d'exécutable, sans processus et sans écriture.

    Antigravity reçoit le stimulus UTF-8 substitué dans l'argument --print,
    sans stdin ; Z.AI reçoit l'argv exact avec --cd remplacé par l'espace
    isolé et le stimulus UTF-8 sur stdin. Tout identifiant hors des deux
    créneaux est refusé."""
    if identifiant == CONFIGURATION_ANTIGRAVITY_RECUPERATION:
        try:
            stimulus = stimulus_utf8.decode("utf-8")
        except UnicodeDecodeError as erreur:
            raise ErreurRecuperation(
                "champ 'stimulus_utf8' : octets UTF-8 attendus pour "
                f"'{identifiant}' : {erreur}"
            ) from erreur
        argv = [
            f"--print={stimulus}"
            if argument == f"--print={JETON_STIMULUS_UTF8}"
            else argument
            for argument in DESCRIPTEUR_ANTIGRAVITY_RECUPERATION
        ]
        return {"argv": argv, "stdin": None, "cwd": espace_isole}
    if identifiant == CONFIGURATION_ZAI_RECUPERATION:
        argv = [
            espace_isole if argument == JETON_ESPACE_ISOLE else argument
            for argument in DESCRIPTEUR_ZAI_RECUPERATION
        ]
        return {"argv": argv, "stdin": stimulus_utf8, "cwd": espace_isole}
    raise ErreurRecuperation(
        "champ 'configuration_id' : "
        f"'{identifiant}' hors des deux créneaux de récupération "
        f"'{CRENEAU_ANTIGRAVITY_RECUPERATION}' et "
        f"'{CRENEAU_ZAI_RECUPERATION}'"
    )


def evaluer_identite_servie_recuperation(identifiant: str, trace: object) -> dict:
    """Évaluation pure de l'identité servie, alimentée seulement par une
    trace locale fournie en argument. Ne crée aucun verdict candidat.

    Une absence de trace, une trace non attribuable, ou une trace qui ne
    porte qu'un modèle REQUESTED ou un code de sortie 0 rend INCONNU et
    HOLD ; une divergence attribuable rend INCONNU, HOLD, incident
    IDENTITY_MISMATCH et nomme les champs divergents ; seules les traces
    exactes rendent OBSERVED."""
    if identifiant == CONFIGURATION_ZAI_RECUPERATION:
        exacte = _IDENTITE_EXACTE_ZAI
        creneau = CRENEAU_ZAI_RECUPERATION
    elif identifiant == CONFIGURATION_ANTIGRAVITY_RECUPERATION:
        exacte = _IDENTITE_EXACTE_ANTIGRAVITY
        creneau = CRENEAU_ANTIGRAVITY_RECUPERATION
    else:
        raise ErreurRecuperation(
            "champ 'configuration_id' : "
            f"'{identifiant}' hors des deux créneaux de récupération"
        )
    if not isinstance(trace, dict):
        return {
            "statut": INCONNU,
            "disposition": "HOLD",
            "incident": None,
            "champs_divergents": [],
            "cause": "absence de trace attribuable",
        }
    if trace.get("tentative_id") != creneau:
        return {
            "statut": INCONNU,
            "disposition": "HOLD",
            "incident": None,
            "champs_divergents": [],
            "cause": "trace non attribuable à la tentative",
        }
    # Un modèle REQUESTED ou un code de sortie 0 n'est jamais une
    # observation servie : ce sont des échos de la demande.
    observe = {
        cle: trace[cle]
        for cle in exacte
        if cle in trace and trace[cle] != _MARQUEUR_DEMANDE
    }
    if not observe:
        return {
            "statut": INCONNU,
            "disposition": "HOLD",
            "incident": None,
            "champs_divergents": [],
            "cause": (
                "aucune observation servie : un modèle REQUESTED ou un code "
                "de sortie 0 ne constitue jamais une preuve"
            ),
        }
    divergents = sorted(
        cle for cle in observe if observe[cle] != exacte[cle]
    )
    if divergents:
        return {
            "statut": INCONNU,
            "disposition": "HOLD",
            "incident": "IDENTITY_MISMATCH",
            "champs_divergents": divergents,
            "cause": "divergence attribuable : " + ", ".join(divergents),
        }
    manquants = sorted(cle for cle in exacte if cle not in observe)
    if manquants:
        return {
            "statut": INCONNU,
            "disposition": "HOLD",
            "incident": None,
            "champs_divergents": [],
            "cause": "observation incomplète : " + ", ".join(manquants),
        }
    return {
        "statut": "OBSERVED",
        "disposition": "OBSERVED",
        "incident": None,
        "champs_divergents": [],
        "cause": None,
    }


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


# V1-R4 : préparation additive de la complétion du panel (#139). Paquet
# local pour les cinq configurations MISSING_OBSERVATION : verrou additif
# citant les sources historiques sans les réécrire, cinq créneaux -001
# réservés non consommés, verdicts locaux d'aptitude statique et garde
# d'autorité absente avant tout processus fournisseur.


class ErreurCompletion(Exception):
    """Divergence nommée du contrat de complétion V1-R4."""


SCHEMA_VERROU_COMPLETION = "campagne-v1-verrou-completion/v1"
CHEMIN_VERROU_COMPLETION = (
    _RACINE_CAMPAGNE_V1 / "completion-panel-v1" / "verrou-completion.json"
)
ISSUE_COMPLETION = "https://github.com/ayoahha/benchmark-lab-x/issues/139"
TRANCHE_COMPLETION = "V1-R4"
# Version issue de V1-R3 (#138) : base fusionnée exacte de cette tranche,
# citée comme fait immuable. L'état et la restitution restent des artefacts
# vivants réécrits par leurs commandes : ils ne sont jamais scellés ici,
# afin que le verrou reste re-dérivable byte-identique après toute
# exécution future autorisée.
ISSUE_V1_R3 = "https://github.com/ayoahha/benchmark-lab-x/issues/138"
COMMIT_V1_R3 = "ede86a2c9475c3186aa57b4a95b8754513e4f2ce"

# Les cinq configurations MISSING_OBSERVATION et leurs créneaux -001 figés
# par le contrat #139 ; identifiants exactement ceux de D-V1-01.
CRENEAUX_COMPLETION = (
    ("claude-code-fable-5", "ACQ-V1-CLAUDE-CODE-FABLE-5-001"),
    ("claude-code-opus-5", "ACQ-V1-CLAUDE-CODE-OPUS-5-001"),
    ("codex-gpt-5-6-sol", "ACQ-V1-CODEX-GPT-5-6-SOL-001"),
    ("cursor-kimi-k3", "ACQ-V1-CURSOR-KIMI-K3-001"),
    ("grok-build-grok-4-6", "ACQ-V1-GROK-BUILD-GROK-4-6-001"),
)


VERDICT_APTITUDE_STATIQUE_PRETE = "APTITUDE_STATIQUE_PRETE"
VERDICT_COMPLETION_UNAVAILABLE = "UNAVAILABLE"
VERDICT_COMPLETION_HOLD = "HOLD"
CAUSE_STATIQUE_COMPLETE = "STATIQUE_COMPLETE"
CAUSE_PANEL_DIVERGENT = "PANEL_DIVERGENT"
CAUSE_CONFIGURATION_ABSENTE = "CONFIGURATION_ABSENTE"
CAUSE_CONFIGURATION_INVALIDE = "CONFIGURATION_INVALIDE"
CAUSE_SCELLE_CONFIGURATION_DIVERGENT = "SCELLE_CONFIGURATION_DIVERGENT"
CAUSE_DESCRIPTEUR_NON_STANDARD = "DESCRIPTEUR_NON_STANDARD"
CAUSE_PREFLIGHT_ABSENT = "PREFLIGHT_ABSENT"
CAUSE_PREFLIGHT_ILLISIBLE = "PREFLIGHT_ILLISIBLE"
CAUSE_SCELLE_PREFLIGHT_DIVERGENT = "SCELLE_PREFLIGHT_DIVERGENT"
CAUSE_CRENEAU_CONSOMME = "CRENEAU_CONSOMME"
# Mode d'entrée standard du stimulus des cinq harnais D-V1-01 : un fichier
# de prompt matérialisé dans l'espace de travail isolé, jamais un argument
# inline ni stdin.
MODE_STIMULUS_FICHIER_PROMPT = "fichier-prompt"
# Faits dynamiques qui restent littéralement INCONNU jusqu'à un reçu
# attribuable : jamais promus, jamais dégradants pour l'aptitude statique.
FAITS_A_L_APPEL_COMPLETION = (
    "identite_servie",
    "effort_effectif",
    "disponibilite_distante",
    "quota_restant",
)
# Descripteurs standards fermés : exactement le harnais D-V1-01 du registre
# officiel, sans wrapper fournisseur, sans variante et sans flag ajouté ;
# toute divergence avec le TOML scellé rend HOLD.
DESCRIPTEURS_COMPLETION = {
    "claude-code-fable-5": ("claude", JETON_FICHIER_PROMPT),
    "claude-code-opus-5": ("claude", JETON_FICHIER_PROMPT),
    "codex-gpt-5-6-sol": ("codex", JETON_FICHIER_PROMPT),
    "cursor-kimi-k3": ("agent", JETON_FICHIER_PROMPT),
    "grok-build-grok-4-6": ("grok", JETON_FICHIER_PROMPT),
}
# Scellés figés partagés avec la chaîne historique V1-R1 : le verrou de
# campagne et le stimulus restent byte-identiques aux constantes du contrat.
EMPREINTE_VERROU_CAMPAGNE_COMPLETION = (
    EMPREINTES_SOURCES_HISTORIQUES_RECUPERATION[CHEMIN_VERROU.as_posix()]
)
EMPREINTE_STIMULUS_COMPLETION = EMPREINTES_SOURCES_HISTORIQUES_RECUPERATION[
    CHEMIN_STIMULUS
]
APTITUDE_STATIQUE_SIGNIFIE = (
    "configuration validée, descripteur standard, créneau réservé et "
    "scellés locaux complets"
)
APTITUDE_STATIQUE_NE_PROUVE_JAMAIS = (
    "READY de préflight",
    "disponibilité distante",
    "quota",
    "identité servie",
    "résultat candidat",
)


def _refus_completion(fait: str) -> int:
    print(f"ECHEC {fait}")
    return 2


def _panel_campagne_completion(racine: Path) -> dict[str, dict]:
    """Épingles du panel du verrou de campagne, vérifié byte-identique à la
    constante figée du contrat avant toute lecture de champ."""
    chemin = racine / CHEMIN_VERROU
    try:
        sha_obtenu = _sha256_fichier(chemin)
    except OSError as erreur:
        raise ErreurCompletion(
            "champ 'sources_historiques' : verrou de campagne illisible "
            f"'{CHEMIN_VERROU.as_posix()}' : {erreur}"
        ) from erreur
    if sha_obtenu != EMPREINTE_VERROU_CAMPAGNE_COMPLETION:
        raise ErreurCompletion(
            "champ 'sources_historiques' : constante figée divergente pour "
            f"'{CHEMIN_VERROU.as_posix()}' : "
            f"{EMPREINTE_VERROU_CAMPAGNE_COMPLETION} attendu, "
            f"{sha_obtenu} obtenu"
        )
    verrou = json.loads(chemin.read_text(encoding="utf-8"))
    return {
        entree["configuration_id"]: entree for entree in verrou["panel"]
    }


def _ligne_completion(
    racine: Path,
    configuration_id: str,
    acquisition_id: str,
    entree_panel: dict | None,
    creneaux_occupes: set[str],
) -> dict:
    """Une ligne du paquet de complétion : verdict local, cause nommée,
    faits dynamiques INCONNU et, en aptitude complète, les deux scellés de
    la ligne. N'exécute aucune commande et ne résout aucun exécutable."""
    ligne = {
        "configuration_id": configuration_id,
        "acquisition_id": acquisition_id,
        "descripteur": {
            "argv": list(DESCRIPTEURS_COMPLETION[configuration_id]),
            "stimulus_utf8": MODE_STIMULUS_FICHIER_PROMPT,
        },
        "faits_a_l_appel": {nom: INCONNU for nom in FAITS_A_L_APPEL_COMPLETION},
        "sources": None,
    }

    def _conclure(verdict: str, cause: str, fait: str) -> dict:
        return {**ligne, "verdict": verdict, "cause": cause, "fait": fait}

    if (
        not isinstance(entree_panel, dict)
        or entree_panel.get("cause") != "MISSING_OBSERVATION"
        or not isinstance(entree_panel.get("configuration"), dict)
        or not isinstance(entree_panel.get("preflight"), dict)
    ):
        return _conclure(
            VERDICT_COMPLETION_HOLD,
            CAUSE_PANEL_DIVERGENT,
            "entrée de panel absente ou hors MISSING_OBSERVATION dans "
            f"'{CHEMIN_VERROU.as_posix()}'",
        )
    relatif_configuration = entree_panel["configuration"]["chemin"]
    chemin_configuration = racine / relatif_configuration
    if not os.path.lexists(chemin_configuration):
        return _conclure(
            VERDICT_COMPLETION_UNAVAILABLE,
            CAUSE_CONFIGURATION_ABSENTE,
            f"configuration officielle absente : '{relatif_configuration}'",
        )
    try:
        sha_configuration = _sha256_fichier(chemin_configuration)
    except OSError as erreur:
        return _conclure(
            VERDICT_COMPLETION_HOLD,
            CAUSE_CONFIGURATION_INVALIDE,
            f"configuration illisible '{relatif_configuration}' : {erreur}",
        )
    if sha_configuration != entree_panel["configuration"]["sha256"]:
        return _conclure(
            VERDICT_COMPLETION_HOLD,
            CAUSE_SCELLE_CONFIGURATION_DIVERGENT,
            f"scellé divergent pour '{relatif_configuration}' : "
            f"{entree_panel['configuration']['sha256']} attendu, "
            f"{sha_configuration} obtenu",
        )
    try:
        configuration = _charger_configuration(chemin_configuration)
    except ErreurConfiguration as erreur:
        return _conclure(
            VERDICT_COMPLETION_HOLD, CAUSE_CONFIGURATION_INVALIDE, str(erreur)
        )
    if configuration["configuration_id"] != configuration_id:
        return _conclure(
            VERDICT_COMPLETION_HOLD,
            CAUSE_CONFIGURATION_INVALIDE,
            f"champ 'configuration_id' : '{configuration['configuration_id']}'"
            f" ne correspond pas à '{configuration_id}'",
        )
    harnais = configuration["harnais"]
    if harnais["argv"] != list(
        DESCRIPTEURS_COMPLETION[configuration_id]
    ) or "stdin_fichier" in harnais:
        return _conclure(
            VERDICT_COMPLETION_HOLD,
            CAUSE_DESCRIPTEUR_NON_STANDARD,
            "harnais divergent du descripteur standard D-V1-01 pour "
            f"'{configuration_id}'",
        )
    relatif_preflight = entree_panel["preflight"]["chemin"]
    chemin_preflight = racine / relatif_preflight
    if not os.path.lexists(chemin_preflight):
        return _conclure(
            VERDICT_COMPLETION_UNAVAILABLE,
            CAUSE_PREFLIGHT_ABSENT,
            f"reçu de préflight absent : '{relatif_preflight}'",
        )
    try:
        sha_preflight = _sha256_fichier(chemin_preflight)
    except OSError as erreur:
        return _conclure(
            VERDICT_COMPLETION_HOLD,
            CAUSE_PREFLIGHT_ILLISIBLE,
            f"reçu de préflight illisible '{relatif_preflight}' : {erreur}",
        )
    if sha_preflight != entree_panel["preflight"]["sha256"]:
        return _conclure(
            VERDICT_COMPLETION_HOLD,
            CAUSE_SCELLE_PREFLIGHT_DIVERGENT,
            f"scellé divergent pour '{relatif_preflight}' : "
            f"{entree_panel['preflight']['sha256']} attendu, "
            f"{sha_preflight} obtenu",
        )
    if configuration_id in creneaux_occupes:
        return _conclure(
            VERDICT_COMPLETION_HOLD,
            CAUSE_CRENEAU_CONSOMME,
            f"un reçu officiel occupe déjà un créneau de '{configuration_id}'"
            " : la réservation -001 non consommée est impossible",
        )
    ligne["sources"] = [
        {"chemin": relatif_configuration, "sha256": sha_configuration},
        {"chemin": relatif_preflight, "sha256": sha_preflight},
    ]
    return {
        **ligne,
        "verdict": VERDICT_APTITUDE_STATIQUE_PRETE,
        "cause": CAUSE_STATIQUE_COMPLETE,
        "fait": APTITUDE_STATIQUE_SIGNIFIE,
    }


def _lignes_completion(racine: Path) -> list[dict]:
    """Les cinq lignes du paquet de complétion dans l'ordre figé des
    créneaux. Les scellés partagés (verrou de campagne, stimulus) et la
    lisibilité des reçus sont vérifiés fail-closed avant toute ligne."""
    panel = _panel_campagne_completion(racine)
    chemin_stimulus = racine / CHEMIN_STIMULUS
    try:
        sha_stimulus = _sha256_fichier(chemin_stimulus)
    except OSError as erreur:
        raise ErreurCompletion(
            "champ 'sources_historiques' : stimulus illisible "
            f"'{CHEMIN_STIMULUS}' : {erreur}"
        ) from erreur
    if sha_stimulus != EMPREINTE_STIMULUS_COMPLETION:
        raise ErreurCompletion(
            "champ 'sources_historiques' : constante figée divergente pour "
            f"'{CHEMIN_STIMULUS}' : {EMPREINTE_STIMULUS_COMPLETION} attendu, "
            f"{sha_stimulus} obtenu"
        )
    try:
        etat = _charger_etat(racine)
        _, officiels = _partitionner_recus(racine, etat)
    except ErreurRestitution as erreur:
        raise ErreurCompletion(
            f"reçus officiels non vérifiables : {erreur}"
        ) from erreur
    creneaux_occupes = {
        enveloppe["payload"]["creneau"].split(":")[0]
        for _, enveloppe, _ in officiels
    }
    return [
        _ligne_completion(
            racine,
            configuration_id,
            acquisition_id,
            panel.get(configuration_id),
            creneaux_occupes,
        )
        for configuration_id, acquisition_id in CRENEAUX_COMPLETION
    ]


def _structure_verrou_completion(lignes: list[dict]) -> dict:
    """Contenu canonique du verrou additif : cinq lignes toutes en aptitude
    statique complète, sources historiques citées par chemin et SHA-256."""
    sources = [
        {
            "chemin": CHEMIN_VERROU.as_posix(),
            "sha256": EMPREINTE_VERROU_CAMPAGNE_COMPLETION,
        },
        {"chemin": CHEMIN_STIMULUS, "sha256": EMPREINTE_STIMULUS_COMPLETION},
    ]
    entrees = []
    for ligne in lignes:
        sources.extend(ligne["sources"])
        entrees.append(
            {
                "configuration_id": ligne["configuration_id"],
                "acquisition_id": ligne["acquisition_id"],
                "descripteur": ligne["descripteur"],
                "verdict": ligne["verdict"],
                "cause": ligne["cause"],
                "faits_a_l_appel": ligne["faits_a_l_appel"],
            }
        )
    return {
        "schema_version": SCHEMA_VERROU_COMPLETION,
        "portee": {
            "issue": ISSUE_COMPLETION,
            "product_version": "V1",
            "tranche": TRANCHE_COMPLETION,
        },
        "version_v1_r3": {"issue": ISSUE_V1_R3, "commit": COMMIT_V1_R3},
        "configurations": entrees,
        "autorite_execution": "NOT_GRANTED",
        "creneaux_executes": 0,
        "reprises_executees": 0,
        "fallback": "NONE",
        "variantes_interdites": list(VARIANTES_INTERDITES_RECUPERATION),
        "aptitude_statique": {
            "signifie": APTITUDE_STATIQUE_SIGNIFIE,
            "ne_prouve_jamais": list(APTITUDE_STATIQUE_NE_PROUVE_JAMAIS),
        },
        "jamais_preuve": list(JAMAIS_PREUVE_RECUPERATION),
        "sources_historiques": sources,
    }


def _nommer_divergence_completion(
    existant: object, attendu: dict, prefixe: str = ""
) -> str:
    """Champ fautif exact d'un verrou de complétion divergent."""
    if not isinstance(existant, dict):
        return prefixe.rstrip(".") or "schema_version"
    for cle in sorted(set(attendu) | set(existant)):
        if existant.get(cle) == attendu.get(cle):
            continue
        chemin = f"{prefixe}{cle}"
        if cle == "configurations":
            return _nommer_divergence_entrees(
                existant.get(cle), attendu[cle], chemin, "configuration_id"
            )
        if cle == "sources_historiques":
            return _nommer_divergence_entrees(
                existant.get(cle), attendu[cle], chemin, "chemin"
            )
        if isinstance(attendu.get(cle), dict) and isinstance(
            existant.get(cle), dict
        ):
            return _nommer_divergence_completion(
                existant[cle], attendu[cle], f"{chemin}."
            )
        return chemin
    return prefixe.rstrip(".") or "schema_version"


def _verifier_verrou_completion(chemin: Path, octets_attendus: bytes) -> None:
    """Vérifie l'octet existant sans réécriture ; toute divergence nomme le
    champ fautif."""
    infos = os.lstat(chemin)
    if stat.S_ISLNK(infos.st_mode) or not stat.S_ISREG(infos.st_mode):
        raise ErreurCompletion(
            "verrou de complétion : fichier régulier non symbolique attendu"
        )
    octets = chemin.read_bytes()
    if octets == octets_attendus:
        return
    try:
        existant = json.loads(octets.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        existant = None
    champ = _nommer_divergence_completion(
        existant, json.loads(octets_attendus.decode("utf-8"))
    )
    raise ErreurCompletion(
        "verrou de complétion divergent : champ fautif "
        f"'{champ}' (LOCKED_ARTIFACT_CHANGED) : aucune réécriture"
    )


def construire_tentative_completion(
    identifiant: str, stimulus_utf8: bytes, espace_isole: str
) -> dict:
    """Adaptateur pur de la future exécution de complétion : construit la
    tentative fermée sans résoudre d'exécutable, sans processus et sans
    écriture.

    Le stimulus entre par un fichier de prompt matérialisé dans l'espace de
    travail isolé (jamais par argument inline ni stdin) ; l'argv est le
    descripteur standard D-V1-01 avec le seul jeton de fichier de prompt
    substitué. Tout identifiant hors des cinq créneaux est refusé."""
    descripteur = DESCRIPTEURS_COMPLETION.get(identifiant)
    if descripteur is None:
        raise ErreurCompletion(
            "champ 'configuration_id' : "
            f"'{identifiant}' hors des cinq créneaux de complétion "
            f"{', '.join(creneau for _, creneau in CRENEAUX_COMPLETION)}"
        )
    fichier_prompt = str(Path(espace_isole) / "stimulus.md")
    argv = [
        element.replace(JETON_FICHIER_PROMPT, fichier_prompt).replace(
            JETON_ESPACE_ISOLE, espace_isole
        )
        for element in descripteur
    ]
    return {
        "argv": argv,
        "stdin": None,
        "cwd": espace_isole,
        "fichier_prompt": {
            "chemin": fichier_prompt,
            "stimulus_utf8": stimulus_utf8,
        },
    }


def _texte_ligne_completion(ligne: dict) -> str:
    faits = " · ".join(
        f"{nom}={valeur}" for nom, valeur in ligne["faits_a_l_appel"].items()
    )
    return (
        f"{ligne['acquisition_id']} · {ligne['configuration_id']} · "
        f"verdict {ligne['verdict']} · cause {ligne['cause']} · "
        f"faits à l'appel : {faits}"
    )


def preparer_completion(racine: Path) -> int:
    """Prépare ou vérifie le paquet additif de complétion des cinq
    configurations MISSING_OBSERVATION : verdicts locaux d'aptitude
    statique, cause nommée par ligne, faits dynamiques INCONNU, puis
    matérialisation unique du verrou additif. N'exécute aucune commande
    externe de fournisseur, de modèle ou de harnais."""
    try:
        lignes = _lignes_completion(racine)
    except ErreurCompletion as erreur:
        print(f"ECHEC {erreur}")
        return 2
    except OSError as erreur:
        print(
            "ECHEC construction du verrou de complétion : erreur d'accès "
            f"nommée : {erreur}"
        )
        return 2
    for ligne in lignes:
        print(_texte_ligne_completion(ligne))
    en_hold = [
        ligne for ligne in lignes if ligne["verdict"] == VERDICT_COMPLETION_HOLD
    ]
    indisponibles = [
        ligne
        for ligne in lignes
        if ligne["verdict"] == VERDICT_COMPLETION_UNAVAILABLE
    ]
    if en_hold:
        faits = " ; ".join(
            f"{ligne['configuration_id']} : {ligne['fait']}"
            for ligne in en_hold
        )
        print(
            f"ECHEC HOLD : manque local ambigu ou scellé divergent — {faits} "
            "; aucun verrou écrit, aucune réécriture"
        )
        return 2
    if indisponibles:
        faits = " ; ".join(
            f"{ligne['configuration_id']} : {ligne['fait']}"
            for ligne in indisponibles
        )
        print(
            f"ECHEC UNAVAILABLE : impossibilité locale explicite — {faits} ; "
            "aucun verrou écrit"
        )
        return 1
    octets_attendus = octets_canoniques(_structure_verrou_completion(lignes))
    chemin = racine / CHEMIN_VERROU_COMPLETION
    try:
        if os.path.lexists(chemin):
            _verifier_verrou_completion(chemin, octets_attendus)
        else:
            chemin.parent.mkdir(parents=True, exist_ok=True)
            try:
                descripteur = os.open(
                    chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644
                )
            except FileExistsError as erreur:
                # Course de création distincte : aucune réparation ni
                # réécriture dans la même invocation ; l'invocation
                # suivante vérifiera l'octet existant.
                raise ErreurCompletion(
                    "création concurrente détectée : le verrou de "
                    "complétion existe déjà (LOCKED_ARTIFACT_CHANGED) : "
                    "aucune réécriture, une nouvelle invocation vérifiera "
                    "l'octet existant"
                ) from erreur
            with os.fdopen(descripteur, "wb") as flux:
                flux.write(octets_attendus)
    except ErreurCompletion as erreur:
        print(f"ECHEC {erreur}")
        return 2
    except OSError as erreur:
        nom = Path(erreur.filename).name if erreur.filename else "inconnu"
        print(
            "ECHEC verrou de complétion inaccessible : "
            f"'{nom}' ({erreur.strerror})"
        )
        return 2
    print(
        "verrou de complétion vérifié : "
        f"{CHEMIN_VERROU_COMPLETION.as_posix()}"
    )
    print(
        "créneaux : 5 · autorite_execution : NOT_GRANTED · "
        "creneaux_executes : 0 · reprises_executees : 0 · fallback : NONE"
    )
    print(
        "APTITUDE_STATIQUE_PRETE reste distinct du READY de préflight : "
        "aucune disponibilité distante, aucun quota, aucune identité servie "
        "et aucun résultat candidat ne sont prouvés ; les faits dynamiques "
        "restent INCONNU jusqu'à un reçu attribuable"
    )
    print(
        "empreinte SHA-256 : "
        f"{hashlib.sha256(octets_attendus).hexdigest()}"
    )
    return 0


def acquerir_completion(identifiant: str) -> int:
    """Interface publique de la future exécution de complétion.

    Dans la tranche V1-R4, aucune autorité d'acquisition de complétion
    n'existe : la garde rend toujours 2 avec AUTORITE_ABSENTE, avant toute
    résolution d'exécutable, création de processus, espace de travail,
    journal ou reçu. Fonction pure : aucune lecture ni écriture."""
    if not _MOTIF_SLUG.match(identifiant):
        return _refus_completion(
            f"champ 'configuration_id' : '{identifiant}' n'est pas un slug "
            "stable ; identifiant refusé avant toute résolution de chemin"
        )
    acquisition_id = next(
        (
            creneau
            for configuration_id, creneau in CRENEAUX_COMPLETION
            if configuration_id == identifiant
        ),
        None,
    )
    if acquisition_id is None:
        return _refus_completion(
            f"configuration '{identifiant}' hors de la portée de la "
            "complétion V1-R4 : seuls les cinq créneaux -001 du verrou de "
            "complétion sont réservés"
        )
    return _refus_completion(
        "AUTORITE_ABSENTE : aucune autorité d'acquisition de complétion "
        f"n'est accordée dans la tranche V1-R4 pour le créneau "
        f"'{acquisition_id}' ; arrêt avant toute résolution d'exécutable : "
        "aucun exécutable résolu, aucun processus fournisseur créé, aucun "
        "espace de travail, aucun journal, aucun reçu, aucun appel candidat"
    )


# V1-XS-10 : dossiers de revue aveugle. Sélection des seules sorties au
# verdict automatique PASS, dossiers opaques embarquant la rubrique HR-001
# byte-identique, engagement d'ordre écrit avant tout dossier sans publier
# la correspondance, contrôle d'absence de fuite, puis restitution.

SCHEMA_ENGAGEMENT_ORDRE_REVUE = "campagne-v1-engagement-ordre-revue/v1"
SCHEMA_MANIFESTE_DOSSIERS = "campagne-v1-manifeste-dossiers-revue/v1"
SCHEMA_CONTROLE_FUITES = "campagne-v1-controle-fuites-dossiers/v2"
RESULTATS_CONTROLE_FUITES = ("CONFORME", "CONFORME_SUR_CATEGORIES_COUVERTES")
REPERTOIRE_DOSSIERS_REVUE = _RACINE_CAMPAGNE_V1 / "dossiers-revue-aveugle-v1"
CHEMIN_ENGAGEMENT_ORDRE_REVUE = REPERTOIRE_DOSSIERS_REVUE / "engagement-ordre.json"
CHEMIN_MANIFESTE_DOSSIERS = REPERTOIRE_DOSSIERS_REVUE / "manifeste-dossiers.json"
CHEMIN_CONTROLE_FUITES = REPERTOIRE_DOSSIERS_REVUE / "controle-fuites.json"
NOM_SOUS_REPERTOIRE_DOSSIERS = "dossiers"
ID_RUBRIQUE_REVUE = "HR-001"
ELIGIBILITE_REVUE = "AUTOMATIC_PASS_ONLY"
# Vocabulaire de révélation repris à l'identique de l'engagement V0 M9-1
REVELATION_CORRESPONDANCE = "AFTER_ALL_HUMAN_VERDICTS_FROZEN"
CORRESPONDANCE_SCELLEE = "SEALED"
_MOTIF_ITEM_REVUE = re.compile(r"^ITEM-\d{3}$")
# Racine des fichiers du paquet approuvé (le manifeste du paquet y vit)
_RACINE_PAQUET = Path("tasks/dev/pre-cadrage-entretien-client")

# Contrôle d'absence de fuite : jetons exacts extraits des sources
# versionnées, par catégorie interdite. Un jeton trop court ou du vocabulaire
# normatif n'identifie rien et n'est pas retenu.
TAILLE_MINIMALE_JETON_FUITE = 4
_JETONS_NORMATIFS_EXCLUS = frozenset({INCONNU, "NON_DEFINI"})
CATEGORIES_FUITES = (
    "configuration_id",
    "acquisition_id",
    "empreinte_candidate",
    "adresse_recu",
    "produit",
    "plan",
    "modele",
    "interface",
    "cout",
    "quota",
    "latence",
    "source_url",
    "materiel_prive",
)


def _cause_exclusion_revue(entree: dict) -> str:
    """Cause exacte d'exclusion de la revue, dérivée du registre de verdicts."""
    verdict = entree["verdict"]
    if verdict is None:
        return f"aucune sortie candidate — {entree['cause_recue']}"
    return (
        f"verdict {verdict['statut']} · porte {verdict['porte_en_cause']} · "
        f"origine {verdict['origine']}"
    )


_MOTIF_FICHIER_DOSSIER = re.compile(r"^ITEM-\d{3}\.md$")


def _fichiers_dossiers_generes(racine: Path) -> list[Path]:
    """Fichiers du sous-répertoire des dossiers générés, triés par nom.

    Seuls des fichiers réguliers ITEM-NNN.md y sont attendus : tout autre
    contenu est refusé, jamais supprimé silencieusement."""
    repertoire = (
        racine / REPERTOIRE_DOSSIERS_REVUE / NOM_SOUS_REPERTOIRE_DOSSIERS
    )
    if not os.path.lexists(repertoire):
        return []
    infos = os.lstat(repertoire)
    if stat.S_ISLNK(infos.st_mode) or not stat.S_ISDIR(infos.st_mode):
        raise ErreurRestitution(
            "répertoire des dossiers générés : répertoire réel non "
            "symbolique attendu"
        )
    presents = sorted(repertoire.iterdir(), key=lambda chemin: chemin.name)
    inattendus = []
    for present in presents:
        infos = os.lstat(present)
        if (
            stat.S_ISLNK(infos.st_mode)
            or not stat.S_ISREG(infos.st_mode)
            or not _MOTIF_FICHIER_DOSSIER.match(present.name)
        ):
            inattendus.append(present.name)
    if inattendus:
        raise ErreurRestitution(
            "fichier(s) inattendu(s) dans le répertoire des dossiers "
            "générés, aucune suppression : " + ", ".join(inattendus)
        )
    return presents


def _retenir_jeton(valeur: object) -> str | None:
    if not isinstance(valeur, str):
        return None
    if len(valeur) < TAILLE_MINIMALE_JETON_FUITE or valeur in (
        _JETONS_NORMATIFS_EXCLUS
    ):
        return None
    return valeur


def _jetons_fuites_interdits(
    racine: Path,
    verrou: dict,
    registre: dict,
    latences: list[str],
    sel: bytes,
    commitment: str,
) -> dict[str, list[str]]:
    """Jetons interdits par catégorie, extraits mécaniquement des sources :
    panel déclaré, plans validés, verrou, registre de verdicts, reçus et
    matériel privé. Le contrôle prouve l'absence de ces jetons exacts."""
    jetons: dict[str, set[str]] = {categorie: set() for categorie in CATEGORIES_FUITES}

    def ajouter(categorie: str, valeur: object) -> None:
        jeton = _retenir_jeton(valeur)
        if jeton is not None:
            jetons[categorie].add(jeton)

    configurations = _configurations_officielles(racine)
    identifiants = tuple(donnees["configuration_id"] for _, donnees in configurations)
    for _, donnees in configurations:
        ajouter("configuration_id", donnees["configuration_id"])
        ajouter("produit", donnees["produit"]["nom"])
        ajouter("produit", donnees["produit"]["editeur"])
        ajouter("plan", donnees["plan"]["nom"])
        ajouter("modele", donnees["modele"]["demande"])
        ajouter("interface", donnees["interface"]["version"])
        for quota in donnees["quota"]:
            if quota["valeur"] != INCONNU:
                ajouter("quota", f"{quota['valeur']} {quota['unite']}")
    plans, _ = _charger_sources_plans(racine, identifiants)
    for plan in plans.values():
        ajouter("plan", plan["nom"])
        ajouter("cout", f"{plan['prix_montant']} {plan['prix_devise']}")
        ajouter("source_url", plan["source_url"])
    for creneau in verrou["creneaux"]:
        ajouter("acquisition_id", creneau["acquisition_id"])
    for entree in registre["entrees"]:
        ajouter("adresse_recu", Path(entree["recu"]).stem)
        if entree["verdict"] is not None:
            ajouter("empreinte_candidate", entree["verdict"]["empreinte_candidate"])
    for latence in latences:
        ajouter("latence", latence)
    ajouter("materiel_prive", sel.hex())
    ajouter("materiel_prive", commitment)
    return {categorie: sorted(valeurs) for categorie, valeurs in jetons.items()}


def _refus_dossiers(fait: str) -> int:
    """Refus fail-closed de la construction des dossiers, fait nommé."""
    print(f"ECHEC {fait}")
    return 1


def _correspondance_ordre_privee(
    chemin_manifeste: Path, creneaux: list[dict]
) -> dict[str, dict]:
    """Correspondance privée acquisition_id -> {item, position}, lue du
    manifeste d'ordre scellé ; jamais publiée."""
    manifeste = json.loads(chemin_manifeste.read_bytes())
    correspondance = {
        entree["acquisition_id"]: {"item": entree["item"], "position": entree["position"]}
        for entree in manifeste
    }
    attendus = {creneau["acquisition_id"] for creneau in creneaux}
    if set(correspondance) != attendus:
        raise ErreurVerrou(
            "manifeste d'ordre privé non aligné sur les créneaux verrouillés"
        )
    return correspondance


def _charger_paquet_approuve(racine: Path) -> tuple[dict, str]:
    """Manifeste du paquet vérifié byte-identique à l'empreinte approuvée."""
    chemin = racine / CHEMIN_PAQUET
    if not chemin.is_file():
        raise ErreurRestitution(
            f"manifeste du paquet approuvé absent : {CHEMIN_PAQUET}"
        )
    sha = _sha256_fichier(chemin)
    if sha != EMPREINTE_MANIFESTE_APPROUVEE:
        raise ErreurRestitution(
            f"manifeste du paquet divergent de l'empreinte approuvée : "
            f"{CHEMIN_PAQUET} attendu {EMPREINTE_MANIFESTE_APPROUVEE}, "
            f"observé {sha}"
        )
    try:
        manifeste = json.loads(chemin.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurRestitution(
            f"manifeste du paquet illisible : {erreur}"
        ) from erreur
    return manifeste, sha


def _octets_fichier_paquet(
    racine: Path, manifeste: dict, nom: str
) -> tuple[bytes, str]:
    """Octets d'un fichier du paquet, vérifiés contre l'empreinte portée par
    le manifeste approuvé ; jamais relus sans cette chaîne."""
    fichiers = manifeste.get("fichiers")
    if not isinstance(fichiers, list):
        raise ErreurRestitution("manifeste du paquet : champ 'fichiers' absent")
    entrees = [f for f in fichiers if isinstance(f, dict) and f.get("chemin") == nom]
    if len(entrees) != 1:
        raise ErreurRestitution(
            f"manifeste du paquet : exactement une entrée '{nom}' attendue"
        )
    attendu = entrees[0].get("sha256")
    if not isinstance(attendu, str) or not _MOTIF_SHA256.match(attendu):
        raise ErreurRestitution(
            f"manifeste du paquet : empreinte SHA-256 attendue pour '{nom}'"
        )
    chemin = racine / _RACINE_PAQUET / nom
    try:
        octets = chemin.read_bytes()
    except OSError as erreur:
        raise ErreurRestitution(
            f"fichier du paquet illisible : {nom} ({erreur})"
        ) from erreur
    if hashlib.sha256(octets).hexdigest() != attendu:
        raise ErreurRestitution(
            f"fichier du paquet divergent de l'empreinte du manifeste : {nom}"
        )
    return octets, attendu


def _extraire_rubrique_hr001(octets_registre: bytes) -> bytes:
    """Bloc exact '- ID: HR-001' du registre de vérité, jusqu'à la première
    ligne vide suivante exclue ; exactement une occurrence exigée."""
    texte = octets_registre.decode("utf-8")
    lignes = texte.splitlines(keepends=True)
    indices = [
        rang
        for rang, ligne in enumerate(lignes)
        if ligne.startswith("- ID: HR-001")
    ]
    if len(indices) != 1:
        raise ErreurRestitution(
            "registre de vérité du paquet : exactement une rubrique "
            f"'- ID: HR-001' attendue, {len(indices)} trouvée(s)"
        )
    debut = indices[0]
    fin = debut
    while fin < len(lignes) and lignes[fin].strip() != "":
        fin += 1
    return "".join(lignes[debut:fin]).encode("utf-8")


def _contenu_dossier_revue(
    item: str, rubrique: bytes, stimulus: bytes, sortie: bytes
) -> bytes:
    """Dossier opaque : rubrique, stimulus et sortie candidate en octets
    exacts, sous un identifiant opaque, sans aucune identité."""
    return (
        f"# Dossier de revue aveugle — {item}\n\n"
        "## Rubrique HR-001\n\n"
    ).encode("utf-8") + rubrique + b"\n## Stimulus\n\n" + stimulus + (
        b"\n## Sortie candidate\n\n" + sortie
    )


def dossiers(racine: Path, racine_privee: Path | None = None) -> int:
    """Construit les dossiers de revue aveugle des seules sorties PASS.

    N'exécute aucune commande externe ; dérive tout des preuves versionnées
    et du matériel privé engagé au verrou, sans jamais publier la
    correspondance entre créneaux et items.
    """
    if racine_privee is None:
        racine_privee = RACINE_PRIVEE_PRODUCTION
    try:
        charge_registre = _charger_registre_validation(racine)
    except ErreurRestitution as erreur:
        return _refus_dossiers(f"registre de validation invalide : {erreur}")
    if charge_registre is None:
        return _refus_dossiers(
            "registre de validation absent : "
            f"{CHEMIN_REGISTRE_VALIDATION.as_posix()} — la sous-commande "
            "valider doit le produire avant dossiers"
        )
    _, registre, _ = charge_registre
    try:
        charge_verrou = _charger_verrou_restitution(racine)
    except ErreurRestitution as erreur:
        return _refus_dossiers(f"verrou de campagne invalide : {erreur}")
    if charge_verrou is None:
        return _refus_dossiers(
            f"verrou de campagne absent : {CHEMIN_VERROU.as_posix()} — la "
            "sous-commande verrouiller doit le matérialiser avant dossiers"
        )
    relatif_verrou, verrou, sha_verrou = charge_verrou
    repertoire_materiel = racine_privee / RELATIF_MATERIEL_VERROU
    chemin_sel = repertoire_materiel / NOM_SEL_VERROU
    chemin_manifeste_ordre = repertoire_materiel / NOM_MANIFESTE_ORDRE
    try:
        engagements = _verifier_materiel_prive(
            repertoire_materiel, chemin_sel, chemin_manifeste_ordre
        )
        _verifier_ordre_prive(
            chemin_sel, chemin_manifeste_ordre, verrou["creneaux"]
        )
        if engagements != verrou["engagements_prives"]:
            raise ErreurVerrou(
                "engagements privés recalculés divergents du verrou publié : "
                "aucune réparation"
            )
        correspondance = _correspondance_ordre_privee(
            chemin_manifeste_ordre, verrou["creneaux"]
        )
    except ErreurVerrou as erreur:
        print(f"ECHEC {erreur}")
        return 2
    except OSError as erreur:
        nom = Path(erreur.filename).name if erreur.filename else "inconnu"
        print(
            f"ECHEC matériel privé du verrou inaccessible : '{nom}' "
            f"({erreur.strerror})"
        )
        return 2
    try:
        paquet, _ = _charger_paquet_approuve(racine)
        octets_registre_verite, sha_registre_verite = _octets_fichier_paquet(
            racine, paquet, "registre-verite.md"
        )
        rubrique = _extraire_rubrique_hr001(octets_registre_verite)
        stimulus, _ = _octets_fichier_paquet(racine, paquet, "stimulus.md")
    except ErreurRestitution as erreur:
        return _refus_dossiers(str(erreur))
    selection: list[dict] = []
    exclusions: list[dict] = []
    latences: list[str] = []
    for entree in registre["entrees"]:
        verdict = entree["verdict"]
        chemin_recu = racine / entree["recu"]
        try:
            octets_recu = chemin_recu.read_bytes()
        except OSError as erreur:
            return _refus_dossiers(
                f"reçu du registre illisible : {entree['recu']} ({erreur})"
            )
        if hashlib.sha256(octets_recu).hexdigest() != entree["recu_sha256"]:
            return _refus_dossiers(
                f"reçu divergent de l'empreinte du registre : {entree['recu']}"
            )
        try:
            enveloppe = _valider_recu(json.loads(octets_recu.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError) as erreur:
            return _refus_dossiers(
                f"reçu du registre illisible : {entree['recu']} ({erreur})"
            )
        except ErreurRecu as erreur:
            return _refus_dossiers(
                f"reçu du registre invalide : {entree['recu']} ({erreur})"
            )
        execution = enveloppe["payload"]["execution"]
        if execution["etat"] == "OBSERVED":
            latences.append(str(execution["latence_ms"]))
        if verdict is None or verdict["statut"] != "PASS":
            exclusions.append(
                {
                    "configuration_id": entree["configuration_id"],
                    "cause": _cause_exclusion_revue(entree),
                }
            )
            continue
        acquisition_id = _identifiant_creneau(entree["configuration_id"])
        if acquisition_id not in correspondance:
            return _refus_dossiers(
                f"sortie PASS sans créneau verrouillé : {acquisition_id}"
            )
        sortie_candidate = execution["sortie"]["stdout"]
        if (
            hashlib.sha256(sortie_candidate.encode("utf-8")).hexdigest()
            != verdict["empreinte_candidate"]
        ):
            return _refus_dossiers(
                "sortie candidate divergente de l'empreinte validée : "
                f"{entree['recu']} — aucune réécriture de sortie"
            )
        selection.append(
            {
                "item": correspondance[acquisition_id]["item"],
                "position": correspondance[acquisition_id]["position"],
                "contenu": _contenu_dossier_revue(
                    correspondance[acquisition_id]["item"],
                    rubrique,
                    stimulus,
                    sortie_candidate.encode("utf-8"),
                ),
            }
        )
    selection.sort(key=lambda entree: entree["position"])
    # L'engagement d'ordre est écrit avant tout dossier : il porte les seuls
    # identifiants opaques des sorties retenues, chaînés au commitment masqué
    # du verrou ; la correspondance reste scellée dans le manifeste privé.
    engagement_verrou = next(
        engagement
        for engagement in verrou["engagements_prives"]
        if engagement["kind"] == "manifeste-ordre"
    )
    engagement_ordre = {
        "schema_version": SCHEMA_ENGAGEMENT_ORDRE_REVUE,
        "verrou": {"chemin": relatif_verrou, "sha256": sha_verrou},
        "engagement_manifeste_verrou": {
            "commitment": engagement_verrou["commitment"],
            "commitment_method": engagement_verrou["commitment_method"],
        },
        "methode": METHODE_ORDRE_VERROU,
        "campaign_id": CAMPAGNE_ID_VERROU,
        # L'ordre engagé couvre le lot verrouillé complet, indépendamment
        # des verdicts : il dérive du manifeste d'ordre engagé au verrou
        "ordre_revue": [
            {"item": entree["item"], "position": entree["position"]}
            for entree in sorted(
                correspondance.values(), key=lambda entree: entree["position"]
            )
        ],
        "cardinalite_revue": len(correspondance),
        "correspondance": CORRESPONDANCE_SCELLEE,
        "revelation": REVELATION_CORRESPONDANCE,
    }
    destination_engagement = racine / CHEMIN_ENGAGEMENT_ORDRE_REVUE
    destination_engagement.parent.mkdir(parents=True, exist_ok=True)
    destination_engagement.write_bytes(octets_canoniques(engagement_ordre))
    # Le sous-répertoire des dossiers générés doit correspondre exactement
    # au manifeste courant : tout contenu inattendu est refusé, jamais
    # supprimé silencieusement
    try:
        dossiers_presents = _fichiers_dossiers_generes(racine)
    except ErreurRestitution as erreur:
        return _refus_dossiers(str(erreur))
    # Contrôle d'absence de fuite sur les contenus construits, avant toute
    # écriture de dossier : une fuite refuse le lot sans réécrire la sortie
    try:
        jetons = _jetons_fuites_interdits(
            racine,
            verrou,
            registre,
            latences,
            chemin_sel.read_bytes(),
            engagement_verrou["commitment"],
        )
    except (ErreurRestitution, ErreurSourcesPlans) as erreur:
        return _refus_dossiers(f"jetons de contrôle indisponibles : {erreur}")
    for dossier in selection:
        for categorie, valeurs in jetons.items():
            if any(
                jeton.encode("utf-8") in dossier["contenu"] for jeton in valeurs
            ):
                # Aucun état antérieur ne reste présentable comme courant :
                # les dossiers générés sont purgés, l'ancien manifeste
                # devient incohérent et la restitution le refuse
                for ancien in dossiers_presents:
                    ancien.unlink()
                return _refus_dossiers(
                    f"fuite interdite détectée : catégorie '{categorie}' dans "
                    f"le dossier {dossier['item']} — aucun dossier écrit"
                )
    # Purge des seuls dossiers générés absents du lot courant
    items_courants = {dossier["item"] for dossier in selection}
    for ancien in dossiers_presents:
        if ancien.stem not in items_courants:
            ancien.unlink()
    entrees_manifeste: list[dict] = []
    for dossier in selection:
        relatif = (
            REPERTOIRE_DOSSIERS_REVUE
            / NOM_SOUS_REPERTOIRE_DOSSIERS
            / f"{dossier['item']}.md"
        )
        destination_dossier = racine / relatif
        destination_dossier.parent.mkdir(parents=True, exist_ok=True)
        destination_dossier.write_bytes(dossier["contenu"])
        entrees_manifeste.append(
            {
                "item": dossier["item"],
                "position": dossier["position"],
                "fichier": relatif.as_posix(),
                "sha256": hashlib.sha256(dossier["contenu"]).hexdigest(),
            }
        )
    # Chaque catégorie porte un état explicite : COUVERTE avec le nombre de
    # jetons recherchés, NON_COUVERTE lorsqu'aucune valeur exploitable
    # n'existe (INCONNU) — une absence de preuve n'est jamais annoncée
    # conforme. Les valeurs privées (sel, engagement du manifeste d'ordre)
    # sont recherchées en mémoire mais jamais sérialisées : seule une preuve
    # non réversible est publiée, la re-vérification exige la racine privée.
    categories_publiees: dict[str, dict] = {}
    for categorie in CATEGORIES_FUITES:
        valeurs = jetons[categorie]
        if not valeurs:
            categories_publiees[categorie] = {
                "statut": "NON_COUVERTE",
                "jetons_recherches": 0,
                "cause": (
                    "aucune valeur exploitable (INCONNU) — absence de "
                    "preuve conservée"
                ),
            }
        elif categorie == "materiel_prive":
            categories_publiees[categorie] = {
                "statut": "COUVERTE",
                "jetons_recherches": len(valeurs),
                "reverification": "RACINE_PRIVEE_REQUISE",
            }
        else:
            categories_publiees[categorie] = {
                "statut": "COUVERTE",
                "jetons_recherches": len(valeurs),
                "jetons": valeurs,
            }
    couverture_complete = all(
        entree["statut"] == "COUVERTE"
        for entree in categories_publiees.values()
    )
    controle_fuites = {
        "schema": SCHEMA_CONTROLE_FUITES,
        "resultat": (
            "CONFORME"
            if couverture_complete
            else "CONFORME_SUR_CATEGORIES_COUVERTES"
        ),
        "categories": categories_publiees,
        "dossiers": [
            {
                "item": dossier["item"],
                "jeton_inclus": {
                    categorie: (
                        False
                        if categories_publiees[categorie]["statut"]
                        == "COUVERTE"
                        else None
                    )
                    for categorie in CATEGORIES_FUITES
                },
            }
            for dossier in selection
        ],
    }
    (racine / CHEMIN_CONTROLE_FUITES).write_bytes(
        octets_canoniques(controle_fuites)
    )
    manifeste = {
        "schema_version": SCHEMA_MANIFESTE_DOSSIERS,
        "rubrique": {
            "id": ID_RUBRIQUE_REVUE,
            "sha256": hashlib.sha256(rubrique).hexdigest(),
            "source": {
                "chemin": (_RACINE_PAQUET / "registre-verite.md").as_posix(),
                "sha256": sha_registre_verite,
            },
        },
        "dossiers": entrees_manifeste,
    }
    if not selection:
        # Lot éligible vide : cause exacte dérivée du registre, sans aucun
        # verdict de qualité — les statuts automatiques sont des faits du
        # registre, pas une appréciation
        comptage: dict[str, int] = {}
        for entree in registre["entrees"]:
            statut = (
                entree["verdict"]["statut"]
                if entree["verdict"] is not None
                else "ABSENTE"
            )
            comptage[statut] = comptage.get(statut, 0) + 1
        manifeste["lot_vide"] = {
            "cause": "aucune_sortie_pass",
            "comptage_statuts": comptage,
        }
    destination = racine / CHEMIN_MANIFESTE_DOSSIERS
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(octets_canoniques(manifeste))
    print(f"manifeste de dossiers écrit : {CHEMIN_MANIFESTE_DOSSIERS.as_posix()}")
    # RG-07 : la sortie est lisible et nomme les exclusions avec leur cause
    print(
        f"dossiers de revue aveugle : {len(selection)} dossier(s), "
        f"{len(exclusions)} exclusion(s)"
    )
    for exclusion in exclusions:
        print(
            f"exclusion : {exclusion['configuration_id']} — "
            f"{exclusion['cause']}"
        )
    if not selection:
        print(
            "lot éligible vide : aucune sortie au verdict automatique PASS "
            f"({manifeste['lot_vide']['comptage_statuts']})"
        )
    return 0


# --- V1-XS-11 : gel des verdicts humains aveugles, puis révélation ---

SCHEMA_GEL_VERDICTS = "campagne-v1-gel-verdicts-humains/v1"
SCHEMA_SAISIE_VERDICT_HUMAIN = "campagne-v1-saisie-verdict-humain/v1"
SCHEMA_RECU_VERDICT_HUMAIN = "campagne-v1-recu-verdict-humain/v1"
SCHEMA_REVELATION_CORRESPONDANCE = "campagne-v1-revelation-correspondance/v1"
REPERTOIRE_VERDICTS_HUMAINS = _RACINE_CAMPAGNE_V1 / "verdicts-humains-v1"
REPERTOIRE_SAISIE_VERDICTS = REPERTOIRE_VERDICTS_HUMAINS / "saisie"
REPERTOIRE_RECUS_VERDICTS = REPERTOIRE_VERDICTS_HUMAINS / "recus"
CHEMIN_GEL_VERDICTS = REPERTOIRE_VERDICTS_HUMAINS / "gel-verdicts.json"
CHEMIN_REVELATION_CORRESPONDANCE = (
    REPERTOIRE_VERDICTS_HUMAINS / "revelation-correspondance.json"
)
# Les trois seuls verdicts humains de la rubrique HR-001, figés par l'Issue
VERDICTS_HUMAINS = ("ACCEPTABLE", "NOT_ACCEPTABLE", "UNABLE_TO_JUDGE")
# Décision propriétaire D-V1-06 : identité et disponibilité du relecteur
# humain aveugle, conservées comme provenance avec l'URL du commentaire
DECISION_RELECTEUR_ID = "D-V1-06"
RELECTEUR_AUTORISE = "ayoahha"
DISPONIBILITE_RELECTEUR = "OWNER_CHECKPOINT_IF_ELIGIBLE_DOSSIERS_EXIST"
URL_DECISION_RELECTEUR = (
    "https://github.com/ayoahha/benchmark-lab-x/issues/111"
    "#issuecomment-5441950621"
)
# Décision V0 héritée : aucun juge LLM fantôme n'intervient
STATUT_JUGE_FANTOME = "DISABLED"
# Lot éligible vide : aucune révélation ne prétend qu'une revue a eu lieu
REVELATION_LOT_VIDE = "NON_APPLICABLE_LOT_VIDE"
INTERVENTION_AUCUNE = "AUCUNE"
INTERVENTION_EFFECTUEE = "EFFECTUEE"
# États officiels du PRD section 8.1, dérivés par conjonction stricte
ETAT_OFFICIELLEMENT_ACCEPTABLE = "OFFICIALLY_ACCEPTABLE"
ETAT_CANDIDAT_NON_ACCEPTABLE = "CANDIDATE_NOT_ACCEPTABLE"
ETAT_INJUGEABLE = "UNABLE_TO_JUDGE"
ETAT_ERREUR_HARNAIS = "HARNESS_ERROR"


def _refus_gel(fait: str) -> int:
    """Refus fail-closed du gel des verdicts, fait nommé."""
    print(f"ECHEC {fait}")
    return 1


def _horodatage_utc() -> str:
    """Horodatage UTC à la microseconde : la chronologie relative gel puis
    révélation reste démontrable dans une même invocation."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _horodatage_strictement_apres(precedent: str) -> str:
    horodatage = _horodatage_utc()
    while horodatage <= precedent:
        horodatage = _horodatage_utc()
    return horodatage


def _etat_officiel(
    verdict_automatique: str | None, verdict_humain: str | None
) -> str:
    """Conjonction stricte du PRD : `OFFICIALLY_ACCEPTABLE` si et seulement
    si le verdict automatique est PASS et le verdict humain ACCEPTABLE."""
    if verdict_automatique == "PASS" and verdict_humain == "ACCEPTABLE":
        return ETAT_OFFICIELLEMENT_ACCEPTABLE
    if verdict_automatique is None or verdict_automatique == "HARNESS_ERROR":
        # aucune sortie candidate, ou verdict automatique HARNESS_ERROR :
        # défaut du dispositif, jamais une pénalité de configuration
        return ETAT_ERREUR_HARNAIS
    if verdict_automatique == "PASS" and verdict_humain == "UNABLE_TO_JUDGE":
        # la preuve humaine manque ; aucune pénalisation de la configuration
        return ETAT_INJUGEABLE
    return ETAT_CANDIDAT_NON_ACCEPTABLE


def geler(racine: Path, racine_privee: Path | None = None) -> int:
    """Gèle les verdicts humains aveugles du lot éligible, puis révèle la
    correspondance strictement après le gel complet.

    N'exécute aucune commande externe et ne fabrique aucun verdict : chaque
    verdict provient d'une saisie humaine versionnée. Un lot éligible vide
    produit zéro verdict, déclaré comme tel, sans fausse intervention humaine
    et sans révélation d'identité.
    """
    if racine_privee is None:
        racine_privee = RACINE_PRIVEE_PRODUCTION
    try:
        registre_validation = _charger_registre_validation(racine)
        verrou_charge = _charger_verrou_restitution(racine)
        artefacts = _charger_artefacts_dossiers(racine)
    except ErreurRestitution as erreur:
        return _refus_gel(f"entrées du gel invalides : {erreur}")
    if artefacts is None:
        return _refus_gel(
            "artefacts de revue aveugle absents : la sous-commande dossiers "
            "doit les produire avant geler"
        )
    try:
        _verifier_coherence_dossiers(
            racine, artefacts, registre_validation, verrou_charge
        )
    except ErreurRestitution as erreur:
        return _refus_gel(f"état de revue incohérent : {erreur}")
    (relatif_manifeste, manifeste, sha_manifeste) = artefacts[0]
    (relatif_engagement, engagement, sha_engagement) = artefacts[2]
    _, verrou, _ = verrou_charge
    # Matériel privé vérifié au moment du gel : l'engagement scellé au verrou
    # reste intact et vérifiable, sans jamais publier son contenu
    repertoire_materiel = racine_privee / RELATIF_MATERIEL_VERROU
    chemin_sel = repertoire_materiel / NOM_SEL_VERROU
    chemin_manifeste_ordre = repertoire_materiel / NOM_MANIFESTE_ORDRE
    try:
        engagements = _verifier_materiel_prive(
            repertoire_materiel, chemin_sel, chemin_manifeste_ordre
        )
        _verifier_ordre_prive(
            chemin_sel, chemin_manifeste_ordre, verrou["creneaux"]
        )
        if engagements != verrou["engagements_prives"]:
            raise ErreurVerrou(
                "engagements privés recalculés divergents du verrou publié : "
                "aucune réparation"
            )
        correspondance = _correspondance_ordre_privee(
            chemin_manifeste_ordre, verrou["creneaux"]
        )
    except ErreurVerrou as erreur:
        print(f"ECHEC {erreur}")
        return 2
    except OSError as erreur:
        nom = Path(erreur.filename).name if erreur.filename else "inconnu"
        print(
            f"ECHEC matériel privé du verrou inaccessible : '{nom}' "
            f"({erreur.strerror})"
        )
        return 2
    decision = {
        "id": DECISION_RELECTEUR_ID,
        "relecteur": RELECTEUR_AUTORISE,
        "disponibilite": DISPONIBILITE_RELECTEUR,
        "url": URL_DECISION_RELECTEUR,
    }
    requis = manifeste["dossiers"]
    if not requis:
        return _geler_lot_vide(racine, manifeste, decision, {
            "engagement_ordre": {
                "chemin": relatif_engagement,
                "sha256": sha_engagement,
            },
            "manifeste_dossiers": {
                "chemin": relatif_manifeste,
                "sha256": sha_manifeste,
            },
        })
    return _geler_lot_complet(
        racine,
        requis,
        decision,
        {
            "engagement_ordre": {
                "chemin": relatif_engagement,
                "sha256": sha_engagement,
            },
            "manifeste_dossiers": {
                "chemin": relatif_manifeste,
                "sha256": sha_manifeste,
            },
        },
        correspondance,
        verrou_charge,
        registre_validation[1],
        engagement,
    )


class ErreurSaisieVerdict(Exception):
    """Saisie de verdict humain hors contrat, fait nommé."""


def _charger_saisie_verdict(racine: Path, item: str) -> dict:
    """Saisie humaine d'un verdict : fichier versionné par item opaque.

    Toute forme hors contrat est refusée avec le fait exact : le gel n'écrit
    jamais un reçu depuis une saisie invalide."""
    chemin = racine / REPERTOIRE_SAISIE_VERDICTS / f"{item}.json"
    if not os.path.lexists(chemin):
        raise ErreurSaisieVerdict(
            f"verdict humain manquant pour {item} : "
            f"{(REPERTOIRE_SAISIE_VERDICTS / (item + '.json')).as_posix()} "
            "absent — aucun gel partiel, aucune révélation"
        )
    infos = os.lstat(chemin)
    if stat.S_ISLNK(infos.st_mode) or not stat.S_ISREG(infos.st_mode):
        raise ErreurSaisieVerdict(
            f"saisie de verdict pour {item} : fichier régulier non "
            "symbolique attendu"
        )
    try:
        saisie = json.loads(chemin.read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurSaisieVerdict(
            f"saisie de verdict illisible pour {item} : {erreur}"
        ) from erreur
    if not isinstance(saisie, dict) or sorted(saisie) != [
        "item",
        "justification",
        "schema_version",
        "verdict",
    ]:
        raise ErreurSaisieVerdict(
            f"saisie de verdict pour {item} : exactement les champs "
            "schema_version, item, verdict et justification attendus"
        )
    if saisie["schema_version"] != SCHEMA_SAISIE_VERDICT_HUMAIN:
        raise ErreurSaisieVerdict(
            f"saisie de verdict pour {item} : schéma "
            f"'{SCHEMA_SAISIE_VERDICT_HUMAIN}' attendu"
        )
    if saisie["item"] != item:
        raise ErreurSaisieVerdict(
            f"saisie de verdict pour {item} : champ item divergent du "
            "fichier"
        )
    if saisie["verdict"] not in VERDICTS_HUMAINS:
        raise ErreurSaisieVerdict(
            f"verdict hors vocabulaire pour {item} : l'un de "
            f"{', '.join(VERDICTS_HUMAINS)} attendu"
        )
    justification = saisie["justification"]
    if not isinstance(justification, str) or not justification.strip():
        raise ErreurSaisieVerdict(
            f"justification manquante pour {item} : une justification non "
            "vide liée à la sortie est obligatoire"
        )
    return saisie


_MOTIF_FICHIER_RECU_VERDICT = re.compile(r"^ITEM-\d{3}\.json$")


def _fichiers_recus_verdicts(racine: Path, items_requis: set[str]) -> None:
    """Refuse tout fichier inattendu du répertoire des reçus de verdicts :
    seuls les reçus des items requis y sont admis, jamais supprimés."""
    repertoire = racine / REPERTOIRE_RECUS_VERDICTS
    if not os.path.lexists(repertoire):
        return
    infos = os.lstat(repertoire)
    if stat.S_ISLNK(infos.st_mode) or not stat.S_ISDIR(infos.st_mode):
        raise ErreurSaisieVerdict(
            "répertoire des reçus de verdicts : répertoire réel non "
            "symbolique attendu"
        )
    inattendus = [
        present.name
        for present in sorted(repertoire.iterdir(), key=lambda c: c.name)
        if stat.S_ISLNK(os.lstat(present).st_mode)
        or not stat.S_ISREG(os.lstat(present).st_mode)
        or not _MOTIF_FICHIER_RECU_VERDICT.match(present.name)
        or present.stem not in items_requis
    ]
    if inattendus:
        raise ErreurSaisieVerdict(
            "fichier(s) inattendu(s) dans le répertoire des reçus de "
            "verdicts, aucune suppression : " + ", ".join(inattendus)
        )


def _stable_sans(contenu: dict, champs: tuple[str, ...]) -> dict:
    return {clef: valeur for clef, valeur in contenu.items() if clef not in champs}


def _geler_recu_verdict(
    racine: Path,
    entree_manifeste: dict,
    saisie: dict,
    decision: dict,
    liens: dict,
    sequence: int,
) -> tuple[str, str, dict]:
    """Gèle un verdict : reçu immuable écrit une seule fois, jamais réécrit.

    Un reçu déjà gelé reste l'autorité : toute divergence de la saisie ou du
    dossier est refusée, aucun écrasement silencieux."""
    item = entree_manifeste["item"]
    relatif = REPERTOIRE_RECUS_VERDICTS / f"{item}.json"
    chemin = racine / relatif
    stable = {
        "schema_version": SCHEMA_RECU_VERDICT_HUMAIN,
        "item": item,
        "position": entree_manifeste["position"],
        "dossier": {
            "fichier": entree_manifeste["fichier"],
            "sha256": entree_manifeste["sha256"],
        },
        "rubrique_id": ID_RUBRIQUE_REVUE,
        "verdict": saisie["verdict"],
        "justification": saisie["justification"],
        "relecteur": RELECTEUR_AUTORISE,
        "decision": {"id": decision["id"], "url": decision["url"]},
        "engagement_ordre": liens["engagement_ordre"],
        "sequence": sequence,
    }
    if os.path.lexists(chemin):
        try:
            existant = json.loads(chemin.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
            raise ErreurSaisieVerdict(
                f"reçu de verdict gelé illisible pour {item} : {erreur}"
            ) from erreur
        if not isinstance(existant, dict) or _stable_sans(
            existant, ("horodatage_utc",)
        ) != stable:
            raise ErreurSaisieVerdict(
                f"reçu de verdict gelé divergent pour {item} : un verdict "
                "gelé est immuable, aucune réécriture"
            )
        octets = chemin.read_bytes()
        return relatif.as_posix(), hashlib.sha256(octets).hexdigest(), existant
    recu = dict(stable)
    recu["horodatage_utc"] = _horodatage_utc()
    octets = octets_canoniques(recu)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    descripteur = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descripteur, "wb") as flux:
        flux.write(octets)
    return relatif.as_posix(), hashlib.sha256(octets).hexdigest(), recu


def _etats_officiels_reveles(
    registre: dict,
    correspondance: dict[str, dict],
    verdicts_humains: dict[str, str],
) -> list[dict]:
    """État officiel de chaque entrée du registre, par conjonction stricte.

    Une entrée sans sortie candidate reste un défaut du dispositif ; une
    sortie FAIL n'a jamais reçu de verdict humain et reste candidate non
    acceptable ; une sortie PASS combine son verdict humain gelé."""
    etats: list[dict] = []
    for entree in registre["entrees"]:
        verdict = entree["verdict"]
        statut = verdict["statut"] if verdict is not None else None
        item = None
        verdict_humain = None
        if statut == "PASS":
            acquisition_id = _identifiant_creneau(entree["configuration_id"])
            item = correspondance[acquisition_id]["item"]
            verdict_humain = verdicts_humains[item]
        etats.append(
            {
                "configuration_id": entree["configuration_id"],
                "recu": entree["recu"],
                "verdict_automatique": statut,
                "item": item,
                "verdict_humain": verdict_humain,
                "etat_officiel": _etat_officiel(statut, verdict_humain),
            }
        )
    return etats


def _geler_lot_complet(
    racine: Path,
    requis: list[dict],
    decision: dict,
    liens: dict,
    correspondance: dict[str, dict],
    verrou_charge: tuple[str, dict, str],
    registre: dict,
    engagement: dict,
) -> int:
    """Gel du lot éligible complet : un reçu immuable par verdict requis,
    puis révélation de la correspondance strictement après le gel."""
    items_requis = {entree["item"] for entree in requis}
    try:
        saisies = {
            entree["item"]: _charger_saisie_verdict(racine, entree["item"])
            for entree in requis
        }
        _fichiers_recus_verdicts(racine, items_requis)
        entrees_gel: list[dict] = []
        verdicts_humains: dict[str, str] = {}
        for sequence, entree_manifeste in enumerate(requis, start=1):
            item = entree_manifeste["item"]
            relatif, sha, recu = _geler_recu_verdict(
                racine,
                entree_manifeste,
                saisies[item],
                decision,
                liens,
                sequence,
            )
            entrees_gel.append({"item": item, "chemin": relatif, "sha256": sha})
            verdicts_humains[item] = recu["verdict"]
    except ErreurSaisieVerdict as erreur:
        return _refus_gel(str(erreur))
    gel_stable = {
        "schema_version": SCHEMA_GEL_VERDICTS,
        "campaign_id": CAMPAGNE_ID_VERROU,
        "decision": decision,
        **liens,
        "verdicts_requis": len(requis),
        "recus": entrees_gel,
        "intervention_relecteur": INTERVENTION_EFFECTUEE,
        "revelation": REVELATION_CORRESPONDANCE,
        "juge_fantome": STATUT_JUGE_FANTOME,
    }
    chemin_gel = racine / CHEMIN_GEL_VERDICTS
    if os.path.lexists(chemin_gel):
        try:
            gel_existant = json.loads(chemin_gel.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
            return _refus_gel(f"gel existant illisible : {erreur}")
        if not isinstance(gel_existant, dict) or _stable_sans(
            gel_existant, ("horodatage_gel_utc",)
        ) != gel_stable:
            return _refus_gel(
                "gel existant divergent de l'état courant : un gel est "
                "immuable, aucune réécriture"
            )
        gel = gel_existant
    else:
        gel = dict(gel_stable)
        gel["horodatage_gel_utc"] = _horodatage_utc()
        chemin_gel.parent.mkdir(parents=True, exist_ok=True)
        chemin_gel.write_bytes(octets_canoniques(gel))
    # Révélation strictement postérieure au gel complet : la correspondance
    # scellée devient publique, chaînée par empreinte au gel réellement écrit
    relatif_verrou, verrou, sha_verrou = verrou_charge
    engagement_verrou = next(
        entree
        for entree in verrou["engagements_prives"]
        if entree["kind"] == "manifeste-ordre"
    )
    creneaux_configurations = {
        creneau["acquisition_id"]: creneau["configuration_id"]
        for creneau in verrou["creneaux"]
    }
    correspondance_publique = sorted(
        (
            {
                "item": position["item"],
                "position": position["position"],
                "acquisition_id": acquisition_id,
                "configuration_id": creneaux_configurations[acquisition_id],
            }
            for acquisition_id, position in correspondance.items()
        ),
        key=lambda entree: entree["position"],
    )
    revelation_stable = {
        "schema_version": SCHEMA_REVELATION_CORRESPONDANCE,
        "campaign_id": CAMPAGNE_ID_VERROU,
        "verrou": {"chemin": relatif_verrou, "sha256": sha_verrou},
        "gel": {
            "chemin": CHEMIN_GEL_VERDICTS.as_posix(),
            "sha256": _sha256_fichier(chemin_gel),
        },
        "engagement_verifie": {
            "commitment": engagement_verrou["commitment"],
            "commitment_method": engagement_verrou["commitment_method"],
            "resultat": "CONFORME",
        },
        "correspondance": correspondance_publique,
        "etats_officiels": _etats_officiels_reveles(
            registre, correspondance, verdicts_humains
        ),
        "posterieure_au_gel": True,
    }
    chemin_revelation = racine / CHEMIN_REVELATION_CORRESPONDANCE
    if os.path.lexists(chemin_revelation):
        try:
            revelation_existante = json.loads(
                chemin_revelation.read_bytes().decode("utf-8")
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
            return _refus_gel(f"révélation existante illisible : {erreur}")
        if not isinstance(revelation_existante, dict) or _stable_sans(
            revelation_existante, ("horodatage_revelation_utc",)
        ) != revelation_stable:
            return _refus_gel(
                "révélation existante divergente de l'état gelé : aucune "
                "modification après révélation, aucune réécriture"
            )
        revelation = revelation_existante
    else:
        revelation = dict(revelation_stable)
        revelation["horodatage_revelation_utc"] = _horodatage_strictement_apres(
            gel["horodatage_gel_utc"]
        )
        chemin_revelation.write_bytes(octets_canoniques(revelation))
    print(f"gel écrit : {CHEMIN_GEL_VERDICTS.as_posix()}")
    print(
        f"révélation écrite : {CHEMIN_REVELATION_CORRESPONDANCE.as_posix()}"
    )
    # RG-07 : sortie lisible — verdicts gelés puis états officiels révélés
    print(
        f"{len(requis)} verdict(s) humain(s) gelé(s), révélation "
        "postérieure au gel"
    )
    for entree in gel["recus"]:
        print(f"verdict gelé : {entree['item']} — {verdicts_humains[entree['item']]}")
    for etat in revelation["etats_officiels"]:
        print(
            f"état officiel : {etat['configuration_id']} — "
            f"{etat['etat_officiel']}"
        )
    return 0


def _geler_lot_vide(
    racine: Path, manifeste: dict, decision: dict, liens: dict
) -> int:
    """Lot éligible vide : zéro verdict requis, fait déclaré tel quel.

    Aucun reçu n'est écrit, aucune intervention humaine n'est simulée et
    aucune correspondance n'est révélée : une révélation sur lot vide
    prétendrait qu'une revue a eu lieu. Aucune configuration n'est dégradée.
    """
    if os.path.lexists(racine / CHEMIN_REVELATION_CORRESPONDANCE):
        return _refus_gel(
            "révélation présente sur lot vide : aucune revue n'a eu lieu, "
            "aucune réparation"
        )
    if os.path.lexists(racine / REPERTOIRE_SAISIE_VERDICTS) or os.path.lexists(
        racine / REPERTOIRE_RECUS_VERDICTS
    ):
        return _refus_gel(
            "saisie ou reçu de verdict présent sur lot vide : aucun verdict "
            "n'est requis, aucun verdict fantôme n'est gelé"
        )
    gel_stable = {
        "schema_version": SCHEMA_GEL_VERDICTS,
        "campaign_id": CAMPAGNE_ID_VERROU,
        "decision": decision,
        **liens,
        "verdicts_requis": 0,
        "recus": [],
        "lot_vide": manifeste["lot_vide"],
        "intervention_relecteur": INTERVENTION_AUCUNE,
        "revelation": REVELATION_LOT_VIDE,
        "juge_fantome": STATUT_JUGE_FANTOME,
    }
    chemin_gel = racine / CHEMIN_GEL_VERDICTS
    if os.path.lexists(chemin_gel):
        try:
            gel_existant = json.loads(chemin_gel.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
            return _refus_gel(f"gel existant illisible : {erreur}")
        if not isinstance(gel_existant, dict) or _stable_sans(
            gel_existant, ("horodatage_gel_utc",)
        ) != gel_stable:
            return _refus_gel(
                "gel existant divergent de l'état courant : un gel est "
                "immuable, aucune réécriture"
            )
    else:
        gel = dict(gel_stable)
        gel["horodatage_gel_utc"] = _horodatage_utc()
        chemin_gel.parent.mkdir(parents=True, exist_ok=True)
        chemin_gel.write_bytes(octets_canoniques(gel))
    print(f"gel écrit : {CHEMIN_GEL_VERDICTS.as_posix()}")
    print(
        "lot éligible vide : 0 verdict requis, 0 reçu écrit — aucune "
        "intervention du relecteur humain, aucune configuration dégradée, "
        "aucune révélation d'identité "
        f"({json.dumps(manifeste['lot_vide']['comptage_statuts'], sort_keys=True)})"
    )
    return 0


# --- V1-XS-12A : état et couverture de la campagne, registre versionné ---

SCHEMA_COUVERTURE_ETAT = "campagne-v1/etat-v1/couverture/1"
SECTION_COUVERTURE_ETAT = "registre de couverture V1 versionné dans l'état"
CAUSE_PREUVE_MANQUANTE = "PREUVE_MANQUANTE"
REGLE_COUVERTURE_ETAT = (
    "PRD 8.5 : part du plan pour laquelle une décision officielle ou un "
    "échec fournisseur attribuable est disponible"
)
# Pannes fournisseur du dénominateur décidable lorsque l'attribution à la
# configuration est prouvée par le reçu validé (PRD 8.5)
_PANNES_FOURNISSEUR_ATTRIBUABLES = ("PROVIDER_FAILURE", "QUOTA_EXHAUSTED")
# Décisions qui couvrent un créneau du plan : états officiels tranchés et
# pannes fournisseur attribuables ; HARNESS_ERROR et UNABLE_TO_JUDGE
# restent hors couverture avec leur cause exacte
_DECISIONS_COUVRANTES = (
    ETAT_OFFICIELLEMENT_ACCEPTABLE,
    ETAT_CANDIDAT_NON_ACCEPTABLE,
    *_PANNES_FOURNISSEUR_ATTRIBUABLES,
)
_CAUSES_NON_COUVERTES = (
    ETAT_ERREUR_HARNAIS,
    ETAT_INJUGEABLE,
    "MISSING_OBSERVATION",
    "IDENTITY_MISMATCH",
    "INTERFACE_UNAVAILABLE",
    "AUTHENTICATION_UNAVAILABLE",
    "MODEL_UNAVAILABLE",
    "PLAN_UNAVAILABLE",
    CAUSE_PREUVE_MANQUANTE,
)
_ETATS_OFFICIELS_VOCABULAIRE = (
    ETAT_OFFICIELLEMENT_ACCEPTABLE,
    ETAT_CANDIDAT_NON_ACCEPTABLE,
    ETAT_INJUGEABLE,
    ETAT_ERREUR_HARNAIS,
)


def _croiser_registre_recus_etat(
    registre: dict | None,
    recus_officiels: list[tuple[str, dict, str]],
) -> dict[str, list[dict]]:
    """Entrées du registre par configuration, registre et reçus croisés.

    Le registre couvre exactement les acquisitions officielles dans l'ordre
    du chaînage ; chaque cause conservée est celle du reçu, jamais
    convertie ; toute divergence est refusée, aucune réparation."""
    if registre is None:
        return {}
    recus_par_chemin = {
        relatif: (enveloppe, sha) for relatif, enveloppe, sha in recus_officiels
    }
    entrees = registre["entrees"]
    if [entree["recu"] for entree in entrees] != [
        relatif for relatif, _, _ in recus_officiels
    ]:
        raise ErreurRestitution(
            "registre de validation non aligné sur les acquisitions "
            "officielles : aucune réparation"
        )
    for entree in entrees:
        enveloppe, sha = recus_par_chemin[entree["recu"]]
        if entree["recu_sha256"] != sha:
            raise ErreurRestitution(
                "empreinte du reçu divergente dans le registre de "
                f"validation : {entree['recu']}"
            )
        execution = enveloppe["payload"]["execution"]
        if entree["verdict"] is None:
            if (
                execution["etat"] != "INCIDENT"
                or execution["incident"] != entree["cause_recue"]
            ):
                raise ErreurRestitution(
                    "cause conservée du registre divergente du reçu, "
                    f"jamais convertie : {entree['recu']}"
                )
        elif execution["etat"] != "OBSERVED":
            raise ErreurRestitution(
                f"verdict candidat sans exécution observée : {entree['recu']}"
            )
    par_configuration: dict[str, list[dict]] = {}
    for entree in entrees:
        par_configuration.setdefault(entree["configuration_id"], []).append(
            entree
        )
    return par_configuration


def _etats_officiels_etat(
    registre: dict | None, artefacts_verdicts: dict | None
) -> dict[str, str]:
    """État officiel révélé par chemin de reçu, croisé avec le registre.

    Le gel du lot vide prouve l'absence de toute sortie PASS ; une
    révélation couvre exactement les entrées du registre, dans le
    vocabulaire officiel du PRD. Toute divergence est refusée."""
    if registre is None or artefacts_verdicts is None:
        return {}
    pass_present = any(
        entree["verdict"] is not None and entree["verdict"]["statut"] == "PASS"
        for entree in registre["entrees"]
    )
    gel = artefacts_verdicts["gel"][1]
    if "lot_vide" in gel:
        if pass_present:
            raise ErreurRestitution(
                "gel de lot vide divergent du registre : une sortie PASS "
                "exige un lot non vide"
            )
        comptage: dict[str, int] = {}
        for entree in registre["entrees"]:
            statut = (
                entree["verdict"]["statut"]
                if entree["verdict"] is not None
                else "ABSENTE"
            )
            comptage[statut] = comptage.get(statut, 0) + 1
        if gel["lot_vide"].get("comptage_statuts") != comptage:
            raise ErreurRestitution(
                "comptage de lot vide du gel divergent du registre de "
                "verdicts"
            )
        return {}
    revelation = artefacts_verdicts["revelation"][1]
    etats = revelation.get("etats_officiels")
    if not isinstance(etats, list) or [
        entree.get("recu") if isinstance(entree, dict) else None
        for entree in etats
    ] != [entree["recu"] for entree in registre["entrees"]]:
        raise ErreurRestitution(
            "états officiels de la révélation non alignés sur le registre "
            "de verdicts"
        )
    for entree in etats:
        if entree.get("etat_officiel") not in _ETATS_OFFICIELS_VOCABULAIRE:
            raise ErreurRestitution(
                "état officiel hors vocabulaire dans la révélation : "
                f"{entree.get('etat_officiel')}"
            )
    return {entree["recu"]: entree["etat_officiel"] for entree in etats}


def _disposition_creneau(
    configuration_id: str,
    entrees: list[dict],
    registre_charge: tuple[str, dict, str] | None,
    recus: list[tuple[str, dict, str]],
    artefacts_verdicts: dict | None,
    etats_officiels: dict[str, str],
    preflight: tuple[str, dict, str] | None,
) -> dict:
    """Disposition prouvée d'un créneau du plan : décision couvrante ou
    cause exacte non couverte, avec les preuves qui la fondent.

    Un créneau sans preuve reste une preuve manquante, jamais un échec
    candidat ; un échec fournisseur ne couvre que lorsque son attribution
    à la configuration est prouvée par le reçu validé."""
    preuves = [
        {"chemin": relatif, "sha256": sha} for relatif, _, sha in recus
    ]
    incidents: list[str] = []
    decision: str | None = None
    cause: str | None = None
    detail = ""
    if entrees:
        if registre_charge is not None:
            preuves.append(
                {"chemin": registre_charge[0], "sha256": registre_charge[2]}
            )
        incidents = [
            entree["cause_recue"]
            for entree in entrees
            if entree["verdict"] is None
        ]
        verdicts = [
            entree for entree in entrees if entree["verdict"] is not None
        ]
        if verdicts:
            dernier = verdicts[-1]
            statut = dernier["verdict"]["statut"]
            if statut == "FAIL":
                decision = ETAT_CANDIDAT_NON_ACCEPTABLE
                detail = (
                    "sortie candidate au verdict mécanique FAIL : candidate "
                    "non acceptable, aucun verdict humain requis"
                )
            elif statut == "HARNESS_ERROR":
                cause = ETAT_ERREUR_HARNAIS
                detail = (
                    "verdict mécanique HARNESS_ERROR : défaut du "
                    "dispositif, jamais une pénalité de configuration"
                )
            else:
                etat_officiel = etats_officiels.get(dernier["recu"])
                if etat_officiel is None:
                    cause = CAUSE_PREUVE_MANQUANTE
                    detail = (
                        "sortie candidate au verdict PASS sans verdict "
                        "humain gelé"
                    )
                else:
                    if artefacts_verdicts is not None:
                        preuves.append(
                            {
                                "chemin": artefacts_verdicts["gel"][0],
                                "sha256": artefacts_verdicts["gel"][2],
                            }
                        )
                        if artefacts_verdicts["revelation"] is not None:
                            preuves.append(
                                {
                                    "chemin": artefacts_verdicts[
                                        "revelation"
                                    ][0],
                                    "sha256": artefacts_verdicts[
                                        "revelation"
                                    ][2],
                                }
                            )
                    if etat_officiel == ETAT_INJUGEABLE:
                        cause = ETAT_INJUGEABLE
                        detail = (
                            "verdict humain UNABLE_TO_JUDGE gelé : la "
                            "preuve humaine manque, sans pénalité de "
                            "configuration"
                        )
                    elif etat_officiel == ETAT_OFFICIELLEMENT_ACCEPTABLE:
                        decision = etat_officiel
                        detail = (
                            "verdict mécanique PASS et verdict humain "
                            "ACCEPTABLE gelé : officiellement acceptable"
                        )
                    else:
                        decision = etat_officiel
                        detail = (
                            "verdict mécanique PASS et verdict humain "
                            "NOT_ACCEPTABLE gelé : candidate non acceptable"
                        )
        else:
            terminal = entrees[-1]["cause_recue"]
            if terminal in _PANNES_FOURNISSEUR_ATTRIBUABLES:
                decision = terminal
                detail = (
                    "échec fournisseur attribuable, attribution prouvée "
                    "par le reçu d'acquisition validé"
                )
            elif terminal == "HARNESS_ERROR":
                cause = terminal
                detail = (
                    "incident HARNESS_ERROR consigné : défaut du "
                    "dispositif, jamais une pénalité de configuration"
                )
            else:
                cause = terminal
                detail = (
                    f"incident {terminal} consigné, attribution prouvée "
                    "par le reçu d'acquisition validé"
                )
    elif recus:
        incidents = [
            enveloppe["payload"]["execution"]["incident"]
            for _, enveloppe, _ in recus
            if enveloppe["payload"]["execution"]["etat"] == "INCIDENT"
        ]
        cause = CAUSE_PREUVE_MANQUANTE
        detail = (
            "acquisition(s) sans registre de validation : la preuve de "
            "décision manque"
        )
    elif preflight is not None:
        relatif_preflight, recu_preflight, sha_preflight = preflight
        preuves.append(
            {"chemin": relatif_preflight, "sha256": sha_preflight}
        )
        verdict_preflight = recu_preflight["verdict"]
        cause_preflight = recu_preflight["cause"]
        fait_preflight = recu_preflight["fait"]
        if (
            verdict_preflight == "UNAVAILABLE"
            and cause_preflight in _PANNES_FOURNISSEUR_ATTRIBUABLES
        ):
            decision = cause_preflight
            detail = f"préflight UNAVAILABLE : {fait_preflight}"
        elif verdict_preflight in ("HOLD", "UNAVAILABLE"):
            cause = cause_preflight
            detail = f"préflight {verdict_preflight} : {fait_preflight}"
        else:
            cause = CAUSE_PREUVE_MANQUANTE
            detail = (
                "préflight READY sans acquisition : la preuve de décision "
                "manque"
            )
    else:
        cause = CAUSE_PREUVE_MANQUANTE
        detail = "aucun reçu d'acquisition ni reçu de préflight"
    return {
        "configuration_id": configuration_id,
        "couvert": decision is not None,
        "decision": decision,
        "cause": cause,
        "detail": detail,
        "incidents": incidents,
        "preuves": preuves,
    }


def _calculer_couverture(
    configurations: list[tuple[str, dict]],
    recus_officiels: list[tuple[str, dict, str]],
    registre_charge: tuple[str, dict, str] | None,
    artefacts_verdicts: dict | None,
    preflights: list[tuple[str, dict, str]],
) -> dict:
    """Couverture du plan déclaré : une entrée par configuration officielle,
    la fraction exacte et la cause prouvée de chaque créneau non couvert."""
    registre = registre_charge[1] if registre_charge is not None else None
    entrees_par_config = _croiser_registre_recus_etat(
        registre, recus_officiels
    )
    etats_officiels = _etats_officiels_etat(registre, artefacts_verdicts)
    recus_par_config: dict[str, list[tuple[str, dict, str]]] = {}
    for relatif, enveloppe, sha in recus_officiels:
        identifiant = enveloppe["payload"]["configuration"]["identifiant"]
        recus_par_config.setdefault(identifiant, []).append(
            (relatif, enveloppe, sha)
        )
    preflights_par_config = {
        recu["configuration_id"]: (relatif, recu, sha)
        for relatif, recu, sha in preflights
    }
    creneaux = [
        _disposition_creneau(
            donnees["configuration_id"],
            entrees_par_config.get(donnees["configuration_id"], []),
            registre_charge,
            recus_par_config.get(donnees["configuration_id"], []),
            artefacts_verdicts,
            etats_officiels,
            preflights_par_config.get(donnees["configuration_id"]),
        )
        for _, donnees in configurations
    ]
    numerateur = sum(1 for creneau in creneaux if creneau["couvert"])
    denominateur = len(creneaux)
    return {
        "schema_couverture": SCHEMA_COUVERTURE_ETAT,
        "regle": REGLE_COUVERTURE_ETAT,
        "numerateur": numerateur,
        "denominateur": denominateur,
        "fraction": f"{numerateur}/{denominateur}",
        "creneaux": creneaux,
    }


def _valider_couverture_etat(couverture: object) -> None:
    """Cohérence interne du registre de couverture : clés exactes, jetons
    du vocabulaire, fraction égale au comptage des créneaux. Refus
    fail-closed, aucune réparation."""
    if not isinstance(couverture, dict) or set(couverture) != {
        "schema_couverture",
        "regle",
        "numerateur",
        "denominateur",
        "fraction",
        "creneaux",
    }:
        raise ErreurRestitution(
            "couverture de l'état V1 : clés exactes ['creneaux', "
            "'denominateur', 'fraction', 'numerateur', 'regle', "
            "'schema_couverture'] attendues"
        )
    if couverture["schema_couverture"] != SCHEMA_COUVERTURE_ETAT:
        raise ErreurRestitution(
            f"couverture de l'état V1 : schéma '{SCHEMA_COUVERTURE_ETAT}' "
            "attendu"
        )
    if not isinstance(couverture["regle"], str) or not couverture[
        "regle"
    ].strip():
        raise ErreurRestitution(
            "couverture de l'état V1 : règle textuelle non vide attendue"
        )
    numerateur = couverture["numerateur"]
    denominateur = couverture["denominateur"]
    for nom, valeur in (
        ("numerateur", numerateur),
        ("denominateur", denominateur),
    ):
        if isinstance(valeur, bool) or not isinstance(valeur, int) or valeur < 0:
            raise ErreurRestitution(
                f"couverture de l'état V1 : '{nom}' entier positif attendu"
            )
    if numerateur > denominateur:
        raise ErreurRestitution(
            "couverture de l'état V1 : numérateur supérieur au dénominateur"
        )
    if couverture["fraction"] != f"{numerateur}/{denominateur}":
        raise ErreurRestitution(
            "couverture de l'état V1 : fraction divergente du numérateur "
            "et du dénominateur explicites"
        )
    creneaux = couverture["creneaux"]
    if not isinstance(creneaux, list):
        raise ErreurRestitution(
            "couverture de l'état V1 : créneaux liste attendue"
        )
    identifiants: set[str] = set()
    for creneau in creneaux:
        if not isinstance(creneau, dict) or set(creneau) != {
            "configuration_id",
            "couvert",
            "decision",
            "cause",
            "detail",
            "incidents",
            "preuves",
        }:
            raise ErreurRestitution(
                "couverture de l'état V1 : créneau aux clés exactes "
                "['cause', 'configuration_id', 'couvert', 'decision', "
                "'detail', 'incidents', 'preuves'] attendu"
            )
        identifiant = creneau["configuration_id"]
        if not isinstance(identifiant, str) or not _MOTIF_SLUG.match(
            identifiant
        ):
            raise ErreurRestitution(
                "couverture de l'état V1 : créneau sans identifiant slug"
            )
        if identifiant in identifiants:
            raise ErreurRestitution(
                f"couverture de l'état V1 : créneau dupliqué '{identifiant}'"
            )
        identifiants.add(identifiant)
        if not isinstance(creneau["couvert"], bool):
            raise ErreurRestitution(
                f"couverture de l'état V1 : créneau '{identifiant}' sans "
                "booléen 'couvert'"
            )
        if creneau["couvert"]:
            if (
                creneau["decision"] not in _DECISIONS_COUVRANTES
                or creneau["cause"] is not None
            ):
                raise ErreurRestitution(
                    f"couverture de l'état V1 : créneau couvert '{identifiant}' "
                    "sans décision du vocabulaire"
                )
        elif (
            creneau["decision"] is not None
            or creneau["cause"] not in _CAUSES_NON_COUVERTES
        ):
            raise ErreurRestitution(
                f"couverture de l'état V1 : créneau non couvert "
                f"'{identifiant}' sans cause du vocabulaire"
            )
        if not isinstance(creneau["detail"], str) or not creneau[
            "detail"
        ].strip():
            raise ErreurRestitution(
                f"couverture de l'état V1 : créneau '{identifiant}' sans "
                "détail textuel"
            )
        incidents = creneau["incidents"]
        if not isinstance(incidents, list) or any(
            incident not in INCIDENTS_V1 for incident in incidents
        ):
            raise ErreurRestitution(
                f"couverture de l'état V1 : créneau '{identifiant}' avec "
                "incident hors vocabulaire"
            )
        preuves = creneau["preuves"]
        if not isinstance(preuves, list) or any(
            not isinstance(preuve, dict)
            or set(preuve) != {"chemin", "sha256"}
            or not isinstance(preuve["chemin"], str)
            or not preuve["chemin"].strip()
            or not isinstance(preuve["sha256"], str)
            or not _MOTIF_SHA256.match(preuve["sha256"])
            for preuve in preuves
        ):
            raise ErreurRestitution(
                f"couverture de l'état V1 : créneau '{identifiant}' avec "
                "preuve invalide"
            )
    if numerateur != sum(1 for creneau in creneaux if creneau["couvert"]):
        raise ErreurRestitution(
            "couverture de l'état V1 : numérateur divergent du comptage "
            "des créneaux couverts"
        )
    if denominateur != len(creneaux):
        raise ErreurRestitution(
            "couverture de l'état V1 : dénominateur divergent du nombre "
            "de créneaux"
        )


def _canon_panel(couverture: object) -> str | None:
    """Canon exact de couverture du panel, dérivé du seul registre publié
    dans l'état V1 ; None quand aucune couverture n'est publiée.

    Le canon sépare explicitement décisions disponibles et acceptabilité ;
    une sortie officiellement acceptable rendrait sa seconde moitié fausse
    et exige une décision propriétaire, jamais une réécriture silencieuse."""
    if couverture is None:
        return None
    _valider_couverture_etat(couverture)
    if any(
        creneau["decision"] == ETAT_OFFICIELLEMENT_ACCEPTABLE
        for creneau in couverture["creneaux"]
    ):
        raise ErreurRestitution(
            "sortie officiellement acceptable présente dans la couverture "
            "publiée : le canon « aucune sortie officiellement acceptable » "
            "ne s'applique plus, décision propriétaire requise"
        )
    return (
        f"Panel abonnement : {couverture['numerateur']} décisions "
        f"disponibles sur {couverture['denominateur']} ; aucune sortie "
        "officiellement acceptable"
    )


def _rapport_etat(
    recus_locaux: list[tuple[str, dict, str]],
    recus_officiels: list[tuple[str, dict, str]],
    registre_charge: tuple[str, dict, str] | None,
    artefacts_verdicts: dict | None,
    couverture: dict,
) -> str:
    """Rapport français : acquisitions, incidents, observations ou preuves
    manquantes et couverture en fraction exacte, chaque affirmation adossée
    aux preuves versionnées lues."""
    lignes = [
        "état de la campagne V1 — lecture des seules preuves versionnées ; "
        "aucune acquisition, aucun appel candidat, aucune dépense",
        "",
        "Acquisitions",
        f"- {len(recus_officiels)} acquisition(s) officielle(s) et "
        f"{len(recus_locaux)} reçu(s) de démonstration locale hors panel "
        "officiel",
    ]
    verdicts_par_recu = {}
    if registre_charge is not None:
        for entree in registre_charge[1]["entrees"]:
            if entree["verdict"] is not None:
                verdicts_par_recu[entree["recu"]] = entree["verdict"]["statut"]
    recus_par_config: dict[str, list[tuple[str, dict]]] = {}
    for relatif, enveloppe, _ in recus_officiels:
        identifiant = enveloppe["payload"]["configuration"]["identifiant"]
        recus_par_config.setdefault(identifiant, []).append(
            (relatif, enveloppe)
        )
    for identifiant in sorted(recus_par_config):
        descriptions = []
        for relatif, enveloppe in recus_par_config[identifiant]:
            execution = enveloppe["payload"]["execution"]
            if execution["etat"] == "INCIDENT":
                descriptions.append(f"incident {execution['incident']}")
            else:
                statut = verdicts_par_recu.get(relatif)
                if statut is None:
                    descriptions.append(
                        "sortie candidate sans verdict automatique"
                    )
                else:
                    descriptions.append(
                        f"sortie candidate au verdict {statut}"
                    )
        lignes.append(
            f"- {identifiant} : {len(descriptions)} reçu(s) — "
            + " ; ".join(descriptions)
        )
    if artefacts_verdicts is None:
        lignes.append("- revue humaine : aucun gel de verdicts n'existe")
    elif "lot_vide" in artefacts_verdicts["gel"][1]:
        lignes.append(
            "- revue humaine : lot éligible vide — 0 verdict humain "
            "requis, aucune intervention du relecteur"
        )
    else:
        lignes.append(
            f"- revue humaine : {len(artefacts_verdicts['recus'])} "
            "verdict(s) humain(s) gelé(s), correspondance révélée"
        )
    lignes += ["", "Incidents"]
    lignes_incidents = []
    for _, enveloppe, _ in recus_officiels:
        execution = enveloppe["payload"]["execution"]
        if execution["etat"] == "INCIDENT":
            identifiant = enveloppe["payload"]["configuration"]["identifiant"]
            lignes_incidents.append(
                f"- {identifiant} : {execution['incident']} — "
                f"{execution['fait']}"
            )
    lignes += lignes_incidents or ["- aucun incident consigné"]
    lignes += ["", "Observations ou données manquantes"]
    lignes_manquantes = []
    for creneau in couverture["creneaux"]:
        if creneau["couvert"]:
            continue
        libelle = (
            "preuve manquante"
            if creneau["cause"] == CAUSE_PREUVE_MANQUANTE
            else creneau["cause"]
        )
        lignes_manquantes.append(
            f"- {creneau['configuration_id']} : {libelle} — "
            f"{creneau['detail']}"
        )
    lignes += lignes_manquantes or [
        "- aucune donnée manquante : tous les créneaux sont couverts"
    ]
    lignes += ["", f"Couverture du plan : {couverture['fraction']}"]
    lignes.append(
        f"- {couverture['numerateur']} créneau(x) couvert(s) par une "
        "décision officielle ou un échec fournisseur attribuable, sur "
        f"{couverture['denominateur']} configuration(s) déclarée(s) "
        "(règle PRD 8.5)"
    )
    for creneau in couverture["creneaux"]:
        if creneau["couvert"]:
            lignes.append(
                f"- {creneau['configuration_id']} : couvert — "
                f"{creneau['decision']} ({creneau['detail']})"
            )
        else:
            libelle = (
                "preuve manquante"
                if creneau["cause"] == CAUSE_PREUVE_MANQUANTE
                else creneau["cause"]
            )
            lignes.append(
                f"- {creneau['configuration_id']} : non couvert — {libelle}"
            )
    lignes.append(
        "- la couverture n'est ni un axe de comparaison, ni une métrique "
        "comparative, ni un score, ni un classement, ni un gagnant, ni "
        "une recommandation"
    )
    return "\n".join(lignes)


def etat(racine: Path) -> int:
    """État de la campagne V1 : acquisitions, incidents, observations ou
    preuves manquantes et couverture en fraction exacte, lus des preuves
    versionnées présentes.

    Le registre de couverture est écrit dans l'état V1 versionné, prolongé
    sans seconde source de vérité ; l'écriture est déterministe et
    idempotente. Aucune acquisition, aucun appel candidat, aucune dépense."""
    etat_v1 = _charger_etat(racine)
    repertoire = _repertoire_recus(racine, etat_v1)
    _compter_recus(repertoire)
    recus_locaux, recus_officiels = _partitionner_recus(racine, etat_v1)
    configurations = _configurations_officielles(racine)
    _verifier_triplets_configuration(
        racine, recus_officiels, configurations
    )
    registre_charge = _charger_registre_validation(racine)
    artefacts_dossiers = _charger_artefacts_dossiers(racine)
    verrou_charge = _charger_verrou_restitution(racine)
    artefacts_verdicts = _charger_artefacts_verdicts(racine)
    if artefacts_verdicts is not None:
        # Redérivation des états officiels depuis les preuves sous-jacentes
        # via _etat_officiel, comparée à la révélation stockée
        _verifier_coherence_verdicts(
            artefacts_verdicts,
            artefacts_dossiers,
            registre_charge,
            verrou_charge,
        )
    preflights = _charger_recus_preflight(racine)
    couverture = _calculer_couverture(
        configurations,
        recus_officiels,
        registre_charge,
        artefacts_verdicts,
        preflights,
    )
    _valider_couverture_etat(couverture)
    etat_v1["couverture"] = couverture
    chemin_etat = racine / CHEMIN_ETAT
    chemin_etat.write_bytes(
        (json.dumps(etat_v1, ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        )
    )
    print(
        _rapport_etat(
            recus_locaux,
            recus_officiels,
            registre_charge,
            artefacts_verdicts,
            couverture,
        )
    )
    print(f"registre de couverture écrit : {CHEMIN_ETAT.as_posix()}")
    return 0


# ---------------------------------------------------------------------------
# Métriques V1-XS-12B : table déterministe lue du registre de couverture
# versionné produit par etat (V1-XS-12A), des reçus sous-jacents et du
# verrou, jamais d'un recalcul de la couverture

SCHEMA_TABLE_METRIQUES = "campagne-v1/metriques-v1/1"
SECTION_TABLE_METRIQUES = "table de métriques V1 versionnée"

# Décisions du dénominateur décidable (PRD 8.2) : sorties officiellement
# acceptables, sorties candidat non acceptables et pannes fournisseur
# attribuables à la configuration ; HARNESS_ERROR et UNABLE_TO_JUDGE en
# sont exclus. Constante distincte de la couverture (PRD 8.5) : les deux
# règles partagent aujourd'hui leurs membres sans être la même règle
_DECISIONS_DECIDABLES = (
    ETAT_OFFICIELLEMENT_ACCEPTABLE,
    ETAT_CANDIDAT_NON_ACCEPTABLE,
    *_PANNES_FOURNISSEUR_ATTRIBUABLES,
)

# Sept composantes d'effort humain du contrat U-025, publiées séparément,
# sans conversion monétaire ; toute composante sans preuve reste INCONNU.
# Le vocabulaire figé est celui de la source locale versionnée citée
COMPOSANTES_EFFORT_HUMAIN = (
    "configuration",
    "integration",
    "execution",
    "human_review",
    "verification",
    "maintenance",
    "report_production",
)
CHEMIN_VOCABULAIRE_EFFORT = Path(
    "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p3-v1/README.md"
)
# Épingle figée de la source du vocabulaire d'effort : la provenance est
# documentée sans lecture du fichier à l'exécution ; le test de garde
# épingle cette empreinte à la source versionnée courante
EMPREINTE_VOCABULAIRE_EFFORT = (
    "85ac048784f3c16700bfd2397b481e8f69e49a211c2754333dcc635c8db48c85"
)

# Politique de latence (PRD 8.4) : le verrou courant ne déclare aucune
# statistique, la campagne publie donc la distribution complète des
# latences de configuration. La branche pure injectée reconnaît
# uniquement la politique LATENCY_MEDIAN_SUCCESS_E2E et valide le
# contrat exact de la source locale versionnée épinglée ci-dessous :
# médiane des seules durées E2E explicitement réussies, échecs rapportés
# séparément et exclus de la médiane, INDEFINIE sans succès ; toute
# politique ou tout contrat divergent est refusé de façon nommée
REGLE_LATENCE_DISTRIBUTION_COMPLETE = "DISTRIBUTION_COMPLETE"
POLITIQUE_LATENCE_MEDIAN_SUCCES_E2E = "LATENCY_MEDIAN_SUCCESS_E2E"
CHEMIN_CONTRAT_LATENCE = Path(
    "tasks/dev/pre-cadrage-entretien-client/preuves-u025/p3-v1/lock.json"
)
# Épingle figée de la source du contrat de latence : la provenance est
# documentée sans lecture du fichier à l'exécution ; le test de garde
# épingle cette empreinte à la source versionnée courante
EMPREINTE_CONTRAT_LATENCE = (
    "43a46d9bd4b4ad3cf1c5d2482544f6bc65422b812f66b43a7e0baae32edf7f52"
)
CONTRAT_LATENCE_EXACT = {
    "policy": POLITIQUE_LATENCE_MEDIAN_SUCCES_E2E,
    "start": "monotonic clock immediately before provider operation",
    "end": "complete candidate bytes or terminal provider error received",
    "successful_statistic": "median",
    "failed_attempts": "reported separately and excluded from success median",
    "no_success": "INDEFINIE",
    "segments": [
        "provider_and_wrapper",
        "automatic_controls",
        "human_review",
        "decision",
    ],
}


def _mediane_ms(valeurs: list[int]) -> int | float:
    """Médiane exacte d'une distribution non vide de latences."""
    triees = sorted(valeurs)
    milieu = len(triees) // 2
    if len(triees) % 2:
        return triees[milieu]
    bas, haut = triees[milieu - 1], triees[milieu]
    return (bas + haut) // 2 if (bas + haut) % 2 == 0 else (bas + haut) / 2


def _latence_configuration(
    succes_ms: list[int],
    politique: str | None,
    echecs_ms: list[int] | None = None,
    contrat: dict | None = None,
) -> dict:
    """Latence de la configuration : distribution complète tant qu'aucune
    politique n'est déclarée. La branche pure injectée
    LATENCY_MEDIAN_SUCCESS_E2E valide le contrat exact de la source
    versionnée, calcule la médiane des seules durées E2E explicitement
    réussies, rapporte les échecs séparément en les excluant de la
    médiane et retourne exactement INDEFINIE sans succès ; la
    distribution des succès et les échecs restent visibles."""
    if politique is None:
        return {
            "regle": REGLE_LATENCE_DISTRIBUTION_COMPLETE,
            "distribution_ms": succes_ms,
        }
    if politique != POLITIQUE_LATENCE_MEDIAN_SUCCES_E2E:
        raise ErreurRestitution(
            f"politique de latence inconnue : '{politique}' — seule "
            f"'{POLITIQUE_LATENCE_MEDIAN_SUCCES_E2E}' est reconnue"
        )
    if contrat != CONTRAT_LATENCE_EXACT:
        raise ErreurRestitution(
            "contrat de latence divergent de la source versionnée "
            f"{CHEMIN_CONTRAT_LATENCE.as_posix()} @ "
            f"{EMPREINTE_CONTRAT_LATENCE}"
        )
    return {
        "regle": politique,
        "valeur_ms": (
            _mediane_ms(succes_ms)
            if succes_ms
            else CONTRAT_LATENCE_EXACT["no_success"]
        ),
        "distribution_ms": list(succes_ms),
        "echecs_ms": list(echecs_ms or []),
    }


def _empreinte_ou_absente(racine: Path, relatif: str) -> str | None:
    """SHA-256 du fichier visé, ou None lorsqu'il est absent."""
    try:
        return _sha256_fichier(racine / relatif)
    except OSError:
        return None


def _motifs_divergence_comparabilite(
    racine: Path,
    creneau: dict,
    recus_config: list[tuple[str, dict, str]],
    entrees_config: list[dict] | None,
    entree_verrou: dict | None,
    descripteurs_recuperation: dict[tuple[str, str], dict] | None,
) -> list[str]:
    """Motifs exacts de divergence de comparabilité d'une configuration,
    axes dans l'ordre figé : carte, paquet, harnais, règles d'incident,
    fenêtre de fraîcheur. Liste vide : configuration comparable. Aucune
    réparation, aucune divergence masquée."""
    motifs: list[str] = []
    sha_carte = _empreinte_ou_absente(racine, CHEMIN_CARTE)
    for relatif, enveloppe, _ in recus_config:
        charge = enveloppe["payload"]
        carte = charge["carte"]
        if carte["chemin"] != CHEMIN_CARTE or carte["sha256"] != sha_carte:
            motifs.append(
                f"divergence de carte : le reçu {relatif} porte "
                f"{carte['chemin']} @ {carte['sha256']} au lieu de "
                f"{CHEMIN_CARTE} @ {sha_carte}"
            )
        paquet = charge["paquet"]
        if (
            paquet["chemin"] != CHEMIN_PAQUET
            or paquet["sha256"] != EMPREINTE_MANIFESTE_APPROUVEE
        ):
            motifs.append(
                f"divergence de paquet : le reçu {relatif} porte "
                f"{paquet['chemin']} @ {paquet['sha256']} au lieu du "
                f"paquet approuvé {CHEMIN_PAQUET} @ "
                f"{EMPREINTE_MANIFESTE_APPROUVEE}"
            )
        recuperation = charge.get("recuperation")
        if recuperation is not None:
            if descripteurs_recuperation is None:
                raise ErreurRestitution(
                    "verrou de récupération absent alors qu'un reçu de "
                    "récupération existe : l'identité du harnais n'est "
                    "pas vérifiable"
                )
            descripteur = descripteurs_recuperation.get(
                (creneau["configuration_id"], recuperation["acquisition_id"])
            )
            requete = charge["requete"]
            if (
                descripteur is None
                or requete["argv_resolu"] != descripteur["argv"]
                or requete["mode_stdin"] != descripteur["stimulus_utf8"]
            ):
                motifs.append(
                    f"divergence de harnais : la requête du reçu {relatif} "
                    "diverge du descripteur verrouillé de l'acquisition "
                    f"{recuperation['acquisition_id']}"
                )
    if entrees_config is not None:
        incidents_attendus = [
            entree["cause_recue"]
            for entree in entrees_config
            if entree["verdict"] is None
        ]
    else:
        incidents_attendus = [
            enveloppe["payload"]["execution"]["incident"]
            for _, enveloppe, _ in recus_config
            if enveloppe["payload"]["execution"]["etat"] == "INCIDENT"
        ]
    if creneau["incidents"] != incidents_attendus:
        motifs.append(
            "divergence des règles d'incident : le registre de couverture "
            f"porte {creneau['incidents']} mais les preuves portent "
            f"{incidents_attendus}"
        )
    if entree_verrou is None:
        motifs.append(
            "divergence de fenêtre de fraîcheur : configuration absente "
            "du panel verrouillé"
        )
    else:
        epingle = entree_verrou["configuration"]
        empreinte_configuration = _empreinte_ou_absente(
            racine, epingle["chemin"]
        )
        if (
            empreinte_configuration is None
            or empreinte_configuration != epingle["sha256"]
        ):
            motifs.append(
                "divergence de fenêtre de fraîcheur : CONFIGURATION_CHANGED "
                f"sur {epingle['chemin']} (règle {REGLE_FRAICHEUR_VERROU})"
            )
        preflight = entree_verrou["preflight"]
        empreinte_preflight = _empreinte_ou_absente(
            racine, preflight["chemin"]
        )
        if empreinte_preflight is None or empreinte_preflight != preflight[
            "sha256"
        ]:
            motifs.append(
                "divergence de fenêtre de fraîcheur : "
                f"LOCKED_ARTIFACT_CHANGED sur {preflight['chemin']} "
                f"(règle {REGLE_FRAICHEUR_VERROU})"
            )
    return motifs


def _ligne_metriques_creneau(creneau: dict) -> dict:
    """Numérateur et dénominateur décidable d'un créneau du registre de
    couverture publié : la décision portée par le créneau est lue, jamais
    recalculée."""
    decision = creneau["decision"]
    numerateur = 1 if decision == ETAT_OFFICIELLEMENT_ACCEPTABLE else 0
    denominateur = 1 if decision in _DECISIONS_DECIDABLES else 0
    return {
        "configuration_id": creneau["configuration_id"],
        "decision": decision,
        "numerateur": numerateur,
        "denominateur_decidable": denominateur,
        "taux": (
            f"{numerateur}/{denominateur}" if denominateur else "NON_DEFINI"
        ),
    }


def _construire_table_metriques(racine: Path) -> dict:
    """Table de métriques V1 construite depuis les sources versionnées :
    registre de couverture publié par etat (repris à l'identique, jamais
    recalculé), reçus officiels, verrou de campagne et verrou de
    récupération. Déterministe ; tout manquement est un refus nommé."""
    etat_v1 = _charger_etat(racine)
    couverture = etat_v1.get("couverture")
    if couverture is None:
        raise ErreurRestitution(
            "registre de couverture absent de l'état V1 : metriques lit la "
            "couverture publiée par etat (V1-XS-12A) et ne la recalcule pas"
        )
    _valider_couverture_etat(couverture)
    verrou_charge = _charger_verrou_restitution(racine)
    if verrou_charge is None:
        raise ErreurRestitution(
            "verrou de campagne absent : la fenêtre de fraîcheur déclarée "
            "au verrou n'est pas lisible"
        )
    verrou = verrou_charge[1]
    repertoire = _repertoire_recus(racine, etat_v1)
    _compter_recus(repertoire)
    _, recus_officiels = _partitionner_recus(racine, etat_v1)
    configurations = _configurations_officielles(racine)
    _verifier_triplets_configuration(racine, recus_officiels, configurations)
    registre_charge = _charger_registre_validation(racine)
    entrees_par_config: dict[str, list[dict]] = {}
    if registre_charge is not None:
        for entree in registre_charge[1]["entrees"]:
            entrees_par_config.setdefault(entree["configuration_id"], []).append(
                entree
            )
    recuperation = _charger_verrou_recuperation(racine)
    descripteurs_recuperation = (
        None
        if recuperation is None
        else {
            (entree["configuration_id"], entree["acquisition_id"]): entree[
                "descripteur"
            ]
            for entree in recuperation[1]["configurations"]
        }
    )
    panel_verrou = {
        entree["configuration_id"]: entree for entree in verrou["panel"]
    }
    recus_par_config: dict[str, list[tuple[str, dict, str]]] = {}
    latences_par_config: dict[str, list[int]] = {}
    for relatif, enveloppe, sha in recus_officiels:
        identifiant = enveloppe["payload"]["configuration"]["identifiant"]
        recus_par_config.setdefault(identifiant, []).append(
            (relatif, enveloppe, sha)
        )
        execution = enveloppe["payload"]["execution"]
        if execution["etat"] == "OBSERVED":
            latences_par_config.setdefault(identifiant, []).append(
                execution["latence_ms"]
            )
    lignes = []
    for creneau in couverture["creneaux"]:
        ligne = _ligne_metriques_creneau(creneau)
        # PRD 8.4 : la latence de la configuration, lue des reçus observés,
        # est distinguée du délai complet avant décision officielle ; ce
        # délai exige les temps de validation automatique et d'obtention
        # du verdict humain, que les preuves courantes n'établissent pas
        ligne["latence_configuration"] = _latence_configuration(
            latences_par_config.get(creneau["configuration_id"], []),
            None,
        )
        ligne["delai_avant_decision_officielle"] = INCONNU
        identifiant = creneau["configuration_id"]
        recus_config = recus_par_config.get(identifiant, [])
        if not creneau["couvert"] and not recus_config:
            # Aucun reçu d'acquisition : la configuration reste visible
            # avec sa cause réelle, ses cinq axes de comparabilité ne
            # sont pas évalués faute de preuve et elle n'entre pas dans
            # le front de comparaison
            ligne["comparabilite"] = {
                "statut": "SANS_OBSERVATION",
                "cause": creneau["cause"],
            }
        else:
            motifs = _motifs_divergence_comparabilite(
                racine,
                creneau,
                recus_config,
                (
                    entrees_par_config.get(identifiant, [])
                    if registre_charge is not None
                    else None
                ),
                panel_verrou.get(identifiant),
                descripteurs_recuperation,
            )
            ligne["comparabilite"] = (
                {"statut": "COMPARABLE"}
                if not motifs
                else {"statut": "RETIREE", "motif": " ; ".join(motifs)}
            )
        lignes.append(ligne)
    comparables = [
        ligne
        for ligne in lignes
        if ligne["comparabilite"]["statut"] == "COMPARABLE"
    ]
    numerateur = sum(ligne["numerateur"] for ligne in comparables)
    denominateur = sum(ligne["denominateur_decidable"] for ligne in comparables)
    table = {
        "schema_table": SCHEMA_TABLE_METRIQUES,
        "product_version": "V1",
        "measurement_profile": "abonnement",
        "couverture_reprise": {
            "source": {
                "chemin": CHEMIN_ETAT.as_posix(),
                "sha256": _sha256_fichier(racine / CHEMIN_ETAT),
            },
            "regle": couverture["regle"],
            "numerateur": couverture["numerateur"],
            "denominateur": couverture["denominateur"],
            "fraction": couverture["fraction"],
        },
        "regle_latence_configuration": REGLE_LATENCE_DISTRIBUTION_COMPLETE,
        "fraicheur": {
            "regle": verrou["fraicheur"]["regle"],
            "effet": verrou["fraicheur"]["effet"],
        },
        "effort_humain": {
            "provenance_vocabulaire": {
                "chemin": CHEMIN_VOCABULAIRE_EFFORT.as_posix(),
                "sha256": EMPREINTE_VOCABULAIRE_EFFORT,
            },
            "composantes": [
                {"composante": composante, "valeur": INCONNU}
                for composante in COMPOSANTES_EFFORT_HUMAIN
            ],
        },
        "configurations": lignes,
        "agregat": {
            "numerateur": numerateur,
            "denominateur_decidable": denominateur,
            "taux": f"{numerateur}/{denominateur}" if denominateur else "NON_DEFINI",
            "configurations_comparables": len(comparables),
            "configurations_retirees": sum(
                1
                for ligne in lignes
                if ligne["comparabilite"]["statut"] == "RETIREE"
            ),
            "configurations_sans_observation": sum(
                1
                for ligne in lignes
                if ligne["comparabilite"]["statut"] == "SANS_OBSERVATION"
            ),
        },
    }
    return table


def metriques(racine: Path) -> int:
    """Table de métriques V1 : numérateur OFFICIALLY_ACCEPTABLE et
    dénominateur décidable par configuration et pour l'agrégat, couverture
    reprise à l'identique du registre publié par etat.

    L'écriture est déterministe et idempotente. Aucune acquisition, aucun
    appel candidat, aucune dépense."""
    table = _construire_table_metriques(racine)
    chemin_table = racine / CHEMIN_TABLE_METRIQUES
    chemin_table.write_bytes(
        (json.dumps(table, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    print(f"table de métriques écrite : {CHEMIN_TABLE_METRIQUES.as_posix()}")
    return 0


_CLES_TABLE_METRIQUES = {
    "schema_table",
    "product_version",
    "measurement_profile",
    "couverture_reprise",
    "regle_latence_configuration",
    "fraicheur",
    "effort_humain",
    "configurations",
    "agregat",
}
_CLES_LIGNE_METRIQUES = {
    "configuration_id",
    "decision",
    "numerateur",
    "denominateur_decidable",
    "taux",
    "latence_configuration",
    "delai_avant_decision_officielle",
    "comparabilite",
}


def _valider_latence_metriques(latence: object, contexte: str) -> None:
    """Bloc de latence de configuration d'une ligne de métriques, schéma
    fermé."""
    if not isinstance(latence, dict) or "regle" not in latence:
        raise ErreurRestitution(
            f"table de métriques : latence de configuration hors schéma "
            f"fermé ({contexte})"
        )
    if latence["regle"] == REGLE_LATENCE_DISTRIBUTION_COMPLETE:
        attendues = {"regle", "distribution_ms"}
    elif latence["regle"] == POLITIQUE_LATENCE_MEDIAN_SUCCES_E2E:
        attendues = {"regle", "valeur_ms", "distribution_ms", "echecs_ms"}
    else:
        raise ErreurRestitution(
            f"table de métriques : règle de latence inconnue ({contexte})"
        )
    if set(latence) != attendues or not isinstance(
        latence["distribution_ms"], list
    ):
        raise ErreurRestitution(
            f"table de métriques : latence de configuration hors schéma "
            f"fermé ({contexte})"
        )


def _charger_table_metriques(racine: Path) -> tuple[str, dict, str] | None:
    """Table de métriques validée pour le rendu : (chemin relatif, table,
    SHA-256), ou None lorsqu'elle n'est pas matérialisée. Toute dérive de
    forme est un refus fail-closed, jamais une réparation."""
    chemin = racine / CHEMIN_TABLE_METRIQUES
    if not os.path.lexists(chemin):
        return None
    infos = os.lstat(chemin)
    if stat.S_ISLNK(infos.st_mode) or not stat.S_ISREG(infos.st_mode):
        raise ErreurRestitution(
            "table de métriques : fichier régulier non symbolique attendu"
        )
    try:
        table = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurRestitution(
            f"table de métriques illisible : {erreur}"
        ) from erreur
    if not isinstance(table, dict) or set(table) != _CLES_TABLE_METRIQUES:
        raise ErreurRestitution("table de métriques : clés hors schéma fermé")
    if table["schema_table"] != SCHEMA_TABLE_METRIQUES:
        raise ErreurRestitution(
            f"table de métriques : schéma '{SCHEMA_TABLE_METRIQUES}' attendu"
        )
    if (
        table["product_version"] != "V1"
        or table["measurement_profile"] != "abonnement"
    ):
        raise ErreurRestitution(
            "table de métriques : version produit ou profil de mesure "
            "hors contrat V1 abonnement"
        )
    reprise = table["couverture_reprise"]
    if not isinstance(reprise, dict) or set(reprise) != {
        "source",
        "regle",
        "numerateur",
        "denominateur",
        "fraction",
    }:
        raise ErreurRestitution(
            "table de métriques : couverture reprise hors schéma fermé"
        )
    source = reprise["source"]
    if not isinstance(source, dict) or set(source) != {"chemin", "sha256"}:
        raise ErreurRestitution(
            "table de métriques : source de couverture hors schéma fermé"
        )
    effort = table["effort_humain"]
    if not isinstance(effort, dict) or set(effort) != {
        "provenance_vocabulaire",
        "composantes",
    }:
        raise ErreurRestitution(
            "table de métriques : effort humain hors schéma fermé — "
            "provenance du vocabulaire et composantes attendues"
        )
    provenance = effort["provenance_vocabulaire"]
    if not isinstance(provenance, dict) or set(provenance) != {
        "chemin",
        "sha256",
    }:
        raise ErreurRestitution(
            "table de métriques : provenance du vocabulaire d'effort "
            "hors schéma fermé"
        )
    composantes = effort["composantes"]
    if (
        not isinstance(composantes, list)
        or [c.get("composante") for c in composantes if isinstance(c, dict)]
        != list(COMPOSANTES_EFFORT_HUMAIN)
        or any(
            not isinstance(c, dict)
            or set(c) != {"composante", "valeur"}
            or not isinstance(c["valeur"], str)
            for c in composantes
        )
    ):
        raise ErreurRestitution(
            "table de métriques : effort humain hors schéma fermé — les "
            "sept composantes du contrat U-025, séparées, sont attendues"
        )
    lignes = table["configurations"]
    if not isinstance(lignes, list):
        raise ErreurRestitution(
            "table de métriques : configurations hors schéma fermé"
        )
    for ligne in lignes:
        if not isinstance(ligne, dict) or set(ligne) != _CLES_LIGNE_METRIQUES:
            raise ErreurRestitution(
                "table de métriques : ligne de configuration hors schéma "
                "fermé"
            )
        _valider_latence_metriques(
            ligne["latence_configuration"], ligne["configuration_id"]
        )
        if ligne["delai_avant_decision_officielle"] != INCONNU:
            raise ErreurRestitution(
                "table de métriques : délai complet avant décision "
                "officielle hors contrat — INCONNU tant que les temps de "
                "validation et de verdict humain ne sont pas établis "
                f"({ligne['configuration_id']})"
            )
        comparabilite = ligne["comparabilite"]
        if not isinstance(comparabilite, dict) or (
            comparabilite.get("statut") == "COMPARABLE"
            and set(comparabilite) != {"statut"}
        ) or (
            comparabilite.get("statut") == "RETIREE"
            and (
                set(comparabilite) != {"statut", "motif"}
                or not isinstance(comparabilite["motif"], str)
            )
        ) or (
            comparabilite.get("statut") == "SANS_OBSERVATION"
            and (
                set(comparabilite) != {"statut", "cause"}
                or comparabilite["cause"] not in _CAUSES_NON_COUVERTES
            )
        ) or comparabilite.get("statut") not in (
            "COMPARABLE",
            "RETIREE",
            "SANS_OBSERVATION",
        ):
            raise ErreurRestitution(
                "table de métriques : comparabilité hors schéma fermé — "
                "une configuration retirée porte un motif exact, une "
                "configuration sans observation porte sa cause exacte"
            )
    agregat = table["agregat"]
    if not isinstance(agregat, dict) or set(agregat) != {
        "numerateur",
        "denominateur_decidable",
        "taux",
        "configurations_comparables",
        "configurations_retirees",
        "configurations_sans_observation",
    }:
        raise ErreurRestitution(
            "table de métriques : agrégat hors schéma fermé"
        )
    return CHEMIN_TABLE_METRIQUES.as_posix(), table, _sha256_fichier(chemin)


SECTION_VOCABULAIRE_EFFORT = "vocabulaire d'effort humain U-025 versionné"


def _texte_latence_metriques(latence: dict) -> str:
    """Latence de la configuration rendue selon la politique de latence,
    distribution toujours visible."""
    distribution = ", ".join(str(valeur) for valeur in latence["distribution_ms"])
    if latence["regle"] == REGLE_LATENCE_DISTRIBUTION_COMPLETE:
        return (
            "latence de la configuration — aucune statistique "
            "préenregistrée, distribution complète publiée : "
            f"<code>[{_echapper(distribution)}]</code> ms"
        )
    echecs = ", ".join(str(valeur) for valeur in latence["echecs_ms"])
    return (
        "latence de la configuration — politique "
        f"<code>{_echapper(latence['regle'])}</code> : médiane des durées "
        "E2E explicitement réussies "
        f"<code>{_echapper(str(latence['valeur_ms']))}</code> ms · "
        f"distribution des succès <code>[{_echapper(distribution)}]</code> "
        "ms · échecs rapportés séparément et exclus de la médiane "
        f"<code>[{_echapper(echecs)}]</code> ms"
    )


def _article_metriques_configuration(
    relatif: str, sha: str, ligne: dict
) -> str:
    """Ligne de métriques d'une configuration : numérateur, dénominateur
    décidable et taux sans masquage, latence de la configuration distinguée
    du délai complet avant décision officielle (PRD 8.4), statut de
    comparabilité et motif exact de tout retrait."""
    decision = (
        ligne["decision"] if ligne["decision"] is not None else "aucune"
    )
    comparabilite = ligne["comparabilite"]
    if comparabilite["statut"] == "COMPARABLE":
        texte_comparabilite = (
            "comparabilité <code>COMPARABLE</code> : aucune divergence de "
            "carte, paquet, harnais, règles d'incident ni fenêtre de "
            "fraîcheur"
        )
    elif comparabilite["statut"] == "SANS_OBSERVATION":
        texte_comparabilite = (
            "comparabilité <code>SANS_OBSERVATION</code> — cause exacte "
            f"<code>{_echapper(comparabilite['cause'])}</code> : aucune "
            "observation d'acquisition ; les cinq axes de comparabilité "
            "(carte, paquet, harnais, règles d'incident, fenêtre de "
            "fraîcheur) ne sont pas évalués faute de preuve et la "
            "configuration n'entre pas dans le front de comparaison"
        )
    else:
        texte_comparabilite = (
            "comparabilité <code>RETIREE</code> — la configuration est "
            "retirée du front de comparaison sans disparaître ; motif "
            f"exact : {_echapper(comparabilite['motif'])}"
        )
    return _article(
        "fait",
        f"<p><strong>{_echapper(ligne['configuration_id'])}</strong> — "
        "décision du registre de couverture "
        f"<code>{_echapper(decision)}</code> · numérateur "
        f"<code>{ligne['numerateur']}</code> sortie(s) officiellement "
        "acceptable(s) · dénominateur décidable "
        f"<code>{ligne['denominateur_decidable']}</code> · taux "
        f"<code>{_echapper(ligne['taux'])}</code>. "
        f"{_texte_latence_metriques(ligne['latence_configuration'])}. "
        "Délai complet avant décision officielle "
        f"<code>{_echapper(ligne['delai_avant_decision_officielle'])}</code>"
        " : distinct de la latence de configuration (PRD 8.4), il exige "
        "les temps de validation automatique et d'obtention du verdict "
        "humain, que les preuves courantes n'établissent pas. "
        f"{texte_comparabilite}.</p>"
        + _span_source(relatif, sha, SECTION_TABLE_METRIQUES),
        f' data-metriques-configuration="{ligne["configuration_id"]}"',
    )


def _section_table_metriques(relatif: str, sha: str, table: dict) -> str:
    """Section de la table de métriques V1 : couverture reprise à
    l'identique avec sa source, agrégat, effort humain en sept
    composantes, une ligne par configuration."""
    reprise = table["couverture_reprise"]
    agregat = table["agregat"]
    effort = table["effort_humain"]
    src_table = _span_source(relatif, sha, SECTION_TABLE_METRIQUES)
    src_couverture = _span_source(
        reprise["source"]["chemin"],
        reprise["source"]["sha256"],
        SECTION_COUVERTURE_ETAT,
    )
    src_vocabulaire = _span_source(
        effort["provenance_vocabulaire"]["chemin"],
        effort["provenance_vocabulaire"]["sha256"],
        SECTION_VOCABULAIRE_EFFORT,
    )
    composantes = " · ".join(
        f"<code>{_echapper(composante['composante'])}</code> "
        f"<code>{_echapper(composante['valeur'])}</code>"
        for composante in effort["composantes"]
    )
    return (
        '<section id="metriques-v1"><h2>Table de métriques V1</h2>'
        "<p>Table déterministe et régénérable produite par "
        "<code>metriques</code> : la couverture est reprise à l'identique "
        "du registre publié par <code>etat</code> (V1-XS-12A), jamais "
        "recalculée ; chaque configuration porte son numérateur de sorties "
        "officiellement acceptables et son dénominateur décidable "
        "explicite, sans masquage de la taille du dénominateur ; seules "
        "les configurations portant une preuve d'acquisition entrent dans "
        "le front de comparaison — une configuration divergente est "
        "retirée du front sans disparaître, avec le motif exact de son "
        "retrait, et une configuration sans observation reste visible "
        "avec sa cause exacte.</p>"
        + _article(
            "fait",
            "<p>Couverture reprise à l'identique : "
            f"<code>{_echapper(reprise['fraction'])}</code> "
            f"(règle <code>{_echapper(reprise['regle'])}</code>), lue "
            "dans le registre de couverture versionné cité ici avec son "
            "empreinte — aucune couverture n'est recalculée par "
            "<code>metriques</code>.</p>" + src_couverture + src_table,
            ' data-metriques-couverture="reprise"',
        )
        + _article(
            "fait",
            f"<p>Agrégat des configurations comparables : numérateur "
            f"<code>{agregat['numerateur']}</code> · dénominateur "
            f"décidable <code>{agregat['denominateur_decidable']}</code> · "
            f"taux <code>{_echapper(agregat['taux'])}</code> · "
            f"configurations comparables "
            f"<code>{agregat['configurations_comparables']}</code> · "
            f"retirées <code>{agregat['configurations_retirees']}</code> · "
            "sans observation "
            f"<code>{agregat['configurations_sans_observation']}</code>. "
            "Règle de latence de la configuration "
            f"<code>{_echapper(table['regle_latence_configuration'])}</code>"
            " · fenêtre de fraîcheur "
            f"<code>{_echapper(table['fraicheur']['regle'])}</code> "
            f"(effet <code>{_echapper(table['fraicheur']['effet'])}</code>"
            ").</p>" + src_table,
            ' data-metriques-agregat="front"',
        )
        + _article(
            "fait",
            "<p>Effort humain en sept composantes séparées, sans "
            "conversion monétaire ; le vocabulaire figé est celui de la "
            "source versionnée citée ici avec son empreinte ; toute "
            "composante sans preuve reste <code>INCONNU</code> : "
            f"{composantes}.</p>" + src_vocabulaire + src_table,
            ' data-metriques-effort="composantes"',
        )
        + "".join(
            _article_metriques_configuration(relatif, sha, ligne)
            for ligne in table["configurations"]
        )
        + "</section>"
    )


# ---------------------------------------------------------------------------
# V1-XS-13 : coût d'abonnement par sortie officiellement acceptable
# Autorité : D_V1_02 = NON_DEFINI_V1 (Issue #114, commentaire propriétaire
# du 28 août 2026) — aucune règle d'attribution n'est adoptée en V1

SCHEMA_COUT_ABONNEMENT = "campagne-v1/cout-abonnement-v1/1"
CHEMIN_COUT_ABONNEMENT = _RACINE_CAMPAGNE_V1 / "cout-abonnement-v1.json"
DECISION_COUT_REFERENCE = "D_V1_02"
DECISION_COUT_VALEUR = "NON_DEFINI_V1"
SOURCE_DECISION_COUT = (
    "https://github.com/ayoahha/benchmark-lab-x/issues/114"
    "#issuecomment-5447153001"
)
SECTION_COUT_ABONNEMENT = "coût d'abonnement V1 versionné"
# Ordre fixe des champs de quota : le document écrit est byte-déterministe
_CHAMPS_QUOTA_ORDRE = (
    "unite",
    "valeur",
    "portee",
    "reset_fenetre",
    "reset_ancrage",
    "reset_au_depassement",
)


def _construire_cout_abonnement(racine: Path) -> dict:
    """Document de coût d'abonnement V1 construit depuis les seules
    preuves versionnées locales : nombre de sorties officiellement
    acceptables repris de la table de métriques publiée (jamais
    recalculé), tarifs catalogue des sources de plans validées et quotas
    déclarés du registre officiel.

    D_V1_02 = NON_DEFINI_V1 : la métrique reste littéralement NON_DEFINI,
    que le nombre de sorties soit nul ou positif ; aucune division,
    allocation, valeur nulle ni valeur de remplacement n'est calculée.
    Aucun total n'est produit ; le quota n'est jamais converti en
    monnaie. Déterministe ; tout manquement est un refus nommé."""
    table_charge = _charger_table_metriques(racine)
    if table_charge is None:
        raise ErreurRestitution(
            "table de métriques absente : cout lit le nombre de sorties "
            "officiellement acceptables publié par metriques (V1-XS-12B) "
            "et ne le recalcule pas"
        )
    relatif_table, table, sha_table = table_charge
    configurations = _configurations_officielles(racine)
    identifiants = tuple(
        donnees["configuration_id"] for _, donnees in configurations
    )
    plans, sha_plans = _charger_sources_plans(racine, identifiants)
    sources = [
        {"chemin": relatif_table, "sha256": sha_table},
        {"chemin": CHEMIN_SOURCES_PLANS.as_posix(), "sha256": sha_plans},
    ]
    tarifs = []
    quotas = []
    for relatif, donnees in configurations:
        identifiant = donnees["configuration_id"]
        sha_configuration = _sha256_fichier(racine / relatif)
        sources.append({"chemin": relatif, "sha256": sha_configuration})
        plan = plans[identifiant]
        tarif = {
            "configuration_id": identifiant,
            "nom": plan["nom"],
            "prix_montant": plan["prix_montant"],
            "prix_devise": plan["prix_devise"],
            "periode": plan["periode"],
            "source_url": plan["source_url"],
            "date_publication": plan["date_publication"],
            "date_consultation": plan["date_consultation"],
            "classe_msw": plan["classe_msw"],
            "attestation_reference": plan["attestation_reference"],
        }
        if plan["classe_msw"] == CLASSE_PLAN_DEDUCTION:
            tarif["premisses"] = plan["premisses"]
        tarifs.append(tarif)
        quotas.append(
            {
                "configuration_id": identifiant,
                "source": {"chemin": relatif, "sha256": sha_configuration},
                "quotas": [
                    {cle: quota[cle] for cle in _CHAMPS_QUOTA_ORDRE}
                    for quota in donnees["quota"]
                ],
            }
        )
    return {
        "schema_cout": SCHEMA_COUT_ABONNEMENT,
        "product_version": "V1",
        "measurement_profile": "abonnement",
        "decision": {
            "reference": DECISION_COUT_REFERENCE,
            "valeur": DECISION_COUT_VALEUR,
            "commentaire": SOURCE_DECISION_COUT,
        },
        "metrique": {
            "nom": "cout_abonnement_par_sortie_officiellement_acceptable",
            "valeur": "NON_DEFINI",
        },
        "sorties_officiellement_acceptables": {
            "nombre": table["agregat"]["numerateur"],
            "source": {"chemin": relatif_table, "sha256": sha_table},
        },
        "tarifs_catalogue": {
            "semantique_prix": SEMANTIQUE_PRIX_PLANS,
            "source": {
                "chemin": CHEMIN_SOURCES_PLANS.as_posix(),
                "sha256": sha_plans,
            },
            "configurations": tarifs,
        },
        "quotas_declares": {"configurations": quotas},
        "sources": sources,
    }


def _ecrire_cout_abonnement(racine: Path) -> dict:
    """Écriture déterministe et idempotente du reçu de coût, depuis les
    seules sources courantes ; rend le document écrit."""
    document = _construire_cout_abonnement(racine)
    chemin_document = racine / CHEMIN_COUT_ABONNEMENT
    chemin_document.write_bytes(
        (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        )
    )
    return document


def cout(racine: Path) -> int:
    """Coût d'abonnement par sortie officiellement acceptable V1.

    D_V1_02 = NON_DEFINI_V1 : la métrique reste littéralement NON_DEFINI ;
    le nombre courant de sorties officiellement acceptables est lu de la
    table de métriques versionnée, les tarifs catalogue mensuels sont
    publiés comme tels sans total et les quotas déclarés sur un objet
    distinct, sans conversion en monnaie.

    L'écriture est déterministe et idempotente. Aucune acquisition, aucun
    appel candidat, aucune dépense."""
    document = _ecrire_cout_abonnement(racine)
    nombre = document["sorties_officiellement_acceptables"]["nombre"]
    print(f"coût d'abonnement écrit : {CHEMIN_COUT_ABONNEMENT.as_posix()}")
    print(
        f"décision {DECISION_COUT_REFERENCE} = {DECISION_COUT_VALEUR} : "
        "métrique cout_abonnement_par_sortie_officiellement_acceptable = "
        f"NON_DEFINI ({nombre} sortie(s) officiellement acceptable(s) ; "
        "aucune division, allocation ni valeur de remplacement)"
    )
    print(
        "tarifs catalogue mensuels : "
        f"{len(document['tarifs_catalogue']['configurations'])} "
        "configurations, sans total ; quotas déclarés sur un objet "
        "distinct, sans conversion en monnaie"
    )
    return 0


_CLES_COUT_ABONNEMENT = {
    "schema_cout",
    "product_version",
    "measurement_profile",
    "decision",
    "metrique",
    "sorties_officiellement_acceptables",
    "tarifs_catalogue",
    "quotas_declares",
    "sources",
}
_CLES_TARIF_COUT = {
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
_CLES_QUOTA_COUT = set(_CHAMPS_QUOTA_ORDRE)


def _valider_source_cout(nom: str, valeur: object) -> None:
    if not isinstance(valeur, dict) or set(valeur) != {"chemin", "sha256"}:
        raise ErreurRestitution(
            f"document de coût d'abonnement : source hors schéma fermé "
            f"({nom})"
        )


def _charger_cout_abonnement(racine: Path) -> tuple[str, dict, str] | None:
    """Document de coût d'abonnement validé pour le rendu : (chemin
    relatif, document, SHA-256), ou None lorsqu'il n'est pas
    matérialisé. Toute dérive de forme et toute substitution de
    NON_DEFINI sont un refus fail-closed, jamais une réparation."""
    chemin = racine / CHEMIN_COUT_ABONNEMENT
    if not os.path.lexists(chemin):
        return None
    infos = os.lstat(chemin)
    if stat.S_ISLNK(infos.st_mode) or not stat.S_ISREG(infos.st_mode):
        raise ErreurRestitution(
            "document de coût d'abonnement : fichier régulier non "
            "symbolique attendu"
        )
    try:
        document = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurRestitution(
            f"document de coût d'abonnement illisible : {erreur}"
        ) from erreur
    if not isinstance(document, dict) or set(document) != _CLES_COUT_ABONNEMENT:
        raise ErreurRestitution(
            "document de coût d'abonnement : clés hors schéma fermé"
        )
    if document["schema_cout"] != SCHEMA_COUT_ABONNEMENT:
        raise ErreurRestitution(
            f"document de coût d'abonnement : schéma "
            f"'{SCHEMA_COUT_ABONNEMENT}' attendu"
        )
    if (
        document["product_version"] != "V1"
        or document["measurement_profile"] != "abonnement"
    ):
        raise ErreurRestitution(
            "document de coût d'abonnement : version produit ou profil de "
            "mesure hors contrat V1 abonnement"
        )
    decision = document["decision"]
    if not isinstance(decision, dict) or set(decision) != {
        "reference",
        "valeur",
        "commentaire",
    }:
        raise ErreurRestitution(
            "document de coût d'abonnement : décision hors schéma fermé"
        )
    if (
        decision["reference"] != DECISION_COUT_REFERENCE
        or decision["valeur"] != DECISION_COUT_VALEUR
        or decision["commentaire"] != SOURCE_DECISION_COUT
    ):
        raise ErreurRestitution(
            f"document de coût d'abonnement : décision "
            f"{DECISION_COUT_REFERENCE} = {DECISION_COUT_VALEUR} attendue, "
            "sans substitution"
        )
    metrique = document["metrique"]
    if not isinstance(metrique, dict) or set(metrique) != {"nom", "valeur"}:
        raise ErreurRestitution(
            "document de coût d'abonnement : métrique hors schéma fermé"
        )
    if (
        metrique["nom"]
        != "cout_abonnement_par_sortie_officiellement_acceptable"
        or metrique["valeur"] != "NON_DEFINI"
    ):
        raise ErreurRestitution(
            "document de coût d'abonnement : la métrique reste "
            "littéralement NON_DEFINI sous D_V1_02 — toute valeur de "
            "remplacement est refusée"
        )
    sorties = document["sorties_officiellement_acceptables"]
    if not isinstance(sorties, dict) or set(sorties) != {"nombre", "source"}:
        raise ErreurRestitution(
            "document de coût d'abonnement : sorties officiellement "
            "acceptables hors schéma fermé"
        )
    if (
        isinstance(sorties["nombre"], bool)
        or not isinstance(sorties["nombre"], int)
        or sorties["nombre"] < 0
    ):
        raise ErreurRestitution(
            "document de coût d'abonnement : nombre de sorties "
            "officiellement acceptables entier positif ou nul attendu"
        )
    _valider_source_cout("sorties_officiellement_acceptables", sorties["source"])
    tarifs = document["tarifs_catalogue"]
    if not isinstance(tarifs, dict) or set(tarifs) != {
        "semantique_prix",
        "source",
        "configurations",
    }:
        raise ErreurRestitution(
            "document de coût d'abonnement : tarifs catalogue hors schéma "
            "fermé"
        )
    if tarifs["semantique_prix"] != SEMANTIQUE_PRIX_PLANS:
        raise ErreurRestitution(
            "document de coût d'abonnement : sémantique des prix "
            f"'{SEMANTIQUE_PRIX_PLANS}' attendue"
        )
    _valider_source_cout("tarifs_catalogue", tarifs["source"])
    if not isinstance(tarifs["configurations"], list):
        raise ErreurRestitution(
            "document de coût d'abonnement : configurations de tarifs "
            "hors schéma fermé"
        )
    for tarif in tarifs["configurations"]:
        if not isinstance(tarif, dict):
            raise ErreurRestitution(
                "document de coût d'abonnement : tarif hors schéma fermé"
            )
        cles_attendues = set(_CLES_TARIF_COUT)
        if tarif.get("classe_msw") == CLASSE_PLAN_DEDUCTION:
            cles_attendues.add("premisses")
        if set(tarif) != cles_attendues:
            raise ErreurRestitution(
                "document de coût d'abonnement : tarif hors schéma fermé "
                f"({tarif.get('configuration_id')})"
            )
        if tarif["prix_devise"] != "USD" or tarif["periode"] != "MONTH":
            raise ErreurRestitution(
                "document de coût d'abonnement : tarif catalogue mensuel "
                f"en USD attendu ({tarif['configuration_id']})"
            )
    quotas = document["quotas_declares"]
    if not isinstance(quotas, dict) or set(quotas) != {"configurations"}:
        raise ErreurRestitution(
            "document de coût d'abonnement : quotas déclarés hors schéma "
            "fermé — objet distinct de tout montant"
        )
    if not isinstance(quotas["configurations"], list):
        raise ErreurRestitution(
            "document de coût d'abonnement : configurations de quotas "
            "hors schéma fermé"
        )
    for entree in quotas["configurations"]:
        if not isinstance(entree, dict) or set(entree) != {
            "configuration_id",
            "source",
            "quotas",
        }:
            raise ErreurRestitution(
                "document de coût d'abonnement : entrée de quotas hors "
                "schéma fermé"
            )
        _valider_source_cout(
            f"quotas {entree['configuration_id']}", entree["source"]
        )
        if not isinstance(entree["quotas"], list) or any(
            not isinstance(quota, dict) or set(quota) != _CLES_QUOTA_COUT
            for quota in entree["quotas"]
        ):
            raise ErreurRestitution(
                "document de coût d'abonnement : quota hors schéma fermé "
                f"({entree['configuration_id']}) — aucune conversion en "
                "monnaie n'est admise"
            )
    sources = document["sources"]
    if not isinstance(sources, list) or not sources:
        raise ErreurRestitution(
            "document de coût d'abonnement : sources hors schéma fermé"
        )
    for source in sources:
        _valider_source_cout("sources", source)
    return CHEMIN_COUT_ABONNEMENT.as_posix(), document, _sha256_fichier(chemin)


def _section_cout_abonnement(relatif: str, sha: str, document: dict) -> str:
    """Section du coût d'abonnement V1 : métrique littéralement
    NON_DEFINI sous D_V1_02, tarifs catalogue mensuels comme tels sans
    total, quotas déclarés sur des lignes distinctes sans conversion."""
    decision = document["decision"]
    metrique = document["metrique"]
    sorties = document["sorties_officiellement_acceptables"]
    tarifs = document["tarifs_catalogue"]
    src_cout = _span_source(relatif, sha, SECTION_COUT_ABONNEMENT)
    src_metriques = _span_source(
        sorties["source"]["chemin"],
        sorties["source"]["sha256"],
        SECTION_TABLE_METRIQUES,
    )
    src_plans = _span_source(
        tarifs["source"]["chemin"],
        tarifs["source"]["sha256"],
        SECTION_SOURCES_PLANS,
    )
    articles = [
        _article(
            "fait",
            f"<p>Décision propriétaire <code>{decision['reference']}</code> "
            f"= <code>{decision['valeur']}</code> : aucune règle "
            "d'attribution du coût d'abonnement à une sortie "
            "officiellement acceptable n'est adoptée en V1. La métrique "
            f"<code>{_echapper(metrique['nom'])}</code> vaut littéralement "
            f"<code>{metrique['valeur']}</code>, que le nombre de sorties "
            "officiellement acceptables soit nul ou positif : aucune "
            "division, aucune allocation, aucune valeur nulle ni valeur "
            "de remplacement n'est calculée. Nombre courant de sorties "
            "officiellement acceptables, lu de la table de métriques "
            f"versionnée : <code>{sorties['nombre']}</code>.</p>"
            + src_cout
            + src_metriques,
            ' data-cout-metrique="non-defini"',
        )
    ]
    for tarif in tarifs["configurations"]:
        contenu = (
            f"<p><strong>{_echapper(tarif['configuration_id'])}</strong> — "
            f"tarif catalogue <code>{_echapper(tarif['nom'])}</code> : "
            f"<code>{_echapper(tarif['prix_montant'])}</code> "
            f"<code>{_echapper(tarif['prix_devise'])}</code> par période "
            f"<code>{_echapper(tarif['periode'])}</code> · publication "
            f"<code>{_echapper(tarif['date_publication'])}</code> · "
            "consultation "
            f"<code>{_echapper(tarif['date_consultation'])}</code> · "
            f"classe <code>{_echapper(tarif['classe_msw'])}</code> · "
            "source officielle "
            f"<code>{_neutraliser_schema(_echapper(tarif['source_url']))}"
            "</code>. Tarif catalogue standard mensuel, hors taxe, remise "
            "et facturation locale : il ne prouve pas le montant "
            "réellement facturé et n'entre dans aucun total.</p>"
            + src_plans
            + src_cout
        )
        if tarif["classe_msw"] == CLASSE_PLAN_DEDUCTION:
            premisses = " ; ".join(tarif["premisses"])
            articles.append(
                _article(
                    "deduction",
                    contenu,
                    f' data-cout-tarif="{tarif["configuration_id"]}"'
                    f' data-premisses="{premisses}"',
                )
            )
        else:
            articles.append(
                _article(
                    "fait",
                    contenu,
                    f' data-cout-tarif="{tarif["configuration_id"]}"',
                )
            )
    for entree in document["quotas_declares"]["configurations"]:
        lignes_quota = "".join(
            "<li>quota "
            + " · ".join(
                f"{cle} <code>{_echapper(quota[cle])}</code>"
                for cle in _CHAMPS_QUOTA_ORDRE
            )
            + "</li>"
            for quota in entree["quotas"]
        )
        articles.append(
            _article(
                "fait",
                f"<p><strong>{_echapper(entree['configuration_id'])}</strong>"
                " — quotas déclarés dans le registre officiel :"
                f"<ul>{lignes_quota}</ul>"
                "Objet distinct de tout montant : aucune conversion entre "
                "quota et monnaie n'est faite.</p>"
                + _span_source(
                    entree["source"]["chemin"],
                    entree["source"]["sha256"],
                    SECTION_REGISTRE,
                )
                + src_cout,
                f' data-cout-quota="{entree["configuration_id"]}"',
            )
        )
    return (
        '<section id="cout-abonnement-v1"><h2>'
        "Coût d'abonnement par sortie officiellement acceptable</h2>"
        "<p>Section produite par <code>cout</code> (V1-XS-13) sous la "
        "décision propriétaire <code>D_V1_02 = NON_DEFINI_V1</code> : la "
        "métrique reste littéralement <code>NON_DEFINI</code>, les tarifs "
        "catalogue mensuels sont présentés comme tels, sans total, et les "
        "quotas déclarés sur des lignes distinctes, sans conversion en "
        "monnaie. Cette section ne produit aucune recommandation, aucun "
        "classement et aucune comparaison de coût.</p>"
        + "".join(articles)
        + "</section>"
    )


SECTION_DOSSIERS_REVUE = "manifeste de dossiers de revue aveugle V1 versionné"
SECTION_ENGAGEMENT_ORDRE = "engagement d'ordre de revue aveugle V1 versionné"
SECTION_CONTROLE_FUITES = "contrôle d'absence de fuite des dossiers V1 versionné"

# Libellés lisibles des catégories de fuite, cités dans la restitution
_LIBELLES_CATEGORIES_FUITES = {
    "configuration_id": "identifiants de configuration",
    "acquisition_id": "identifiants d'acquisition",
    "empreinte_candidate": "empreintes candidates",
    "adresse_recu": "adresses de reçus",
    "produit": "produit",
    "plan": "plan",
    "modele": "modèle",
    "interface": "interface",
    "cout": "coût",
    "quota": "quota",
    "latence": "latence",
    "source_url": "sources",
    "materiel_prive": "matériel privé",
}


def _charger_json_artefact_dossiers(racine: Path, relatif: Path) -> tuple[str, dict, str]:
    """Artefact JSON de revue aveugle : (chemin relatif, contenu, SHA-256)."""
    chemin = racine / relatif
    infos = os.lstat(chemin)
    if stat.S_ISLNK(infos.st_mode) or not stat.S_ISREG(infos.st_mode):
        raise ErreurRestitution(
            f"artefact de revue aveugle : fichier régulier non symbolique "
            f"attendu : {relatif.as_posix()}"
        )
    try:
        octets = chemin.read_bytes()
        contenu = json.loads(octets.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurRestitution(
            f"artefact de revue aveugle illisible : {relatif.as_posix()} "
            f"({erreur})"
        ) from erreur
    if not isinstance(contenu, dict):
        raise ErreurRestitution(
            f"artefact de revue aveugle non objet : {relatif.as_posix()}"
        )
    return relatif.as_posix(), contenu, hashlib.sha256(octets).hexdigest()


def _charger_artefacts_dossiers(
    racine: Path,
) -> tuple[tuple[str, dict, str], tuple[str, dict, str], tuple[str, dict, str]] | None:
    """Manifeste, contrôle de fuites et engagement d'ordre pour le rendu.

    Les trois artefacts sont produits ensemble par `dossiers` : une présence
    partielle est une incohérence fail-closed, jamais réparée au rendu."""
    chemins = (
        CHEMIN_MANIFESTE_DOSSIERS,
        CHEMIN_CONTROLE_FUITES,
        CHEMIN_ENGAGEMENT_ORDRE_REVUE,
    )
    presents = [os.path.lexists(racine / chemin) for chemin in chemins]
    if not any(presents):
        return None
    if not all(presents):
        absents = [
            chemin.as_posix()
            for chemin, present in zip(chemins, presents)
            if not present
        ]
        raise ErreurRestitution(
            "artefacts de revue aveugle partiels, absents : "
            + ", ".join(absents)
        )
    manifeste = _charger_json_artefact_dossiers(racine, CHEMIN_MANIFESTE_DOSSIERS)
    controle = _charger_json_artefact_dossiers(racine, CHEMIN_CONTROLE_FUITES)
    engagement = _charger_json_artefact_dossiers(
        racine, CHEMIN_ENGAGEMENT_ORDRE_REVUE
    )
    if manifeste[1].get("schema_version") != SCHEMA_MANIFESTE_DOSSIERS:
        raise ErreurRestitution(
            f"manifeste de dossiers de schéma inattendu : {manifeste[0]}"
        )
    if controle[1].get("schema") != SCHEMA_CONTROLE_FUITES:
        raise ErreurRestitution(
            f"contrôle de fuites de schéma inattendu : {controle[0]}"
        )
    if engagement[1].get("schema_version") != SCHEMA_ENGAGEMENT_ORDRE_REVUE:
        raise ErreurRestitution(
            f"engagement d'ordre de schéma inattendu : {engagement[0]}"
        )
    return manifeste, controle, engagement


def _verifier_coherence_dossiers(
    racine: Path,
    artefacts: tuple[
        tuple[str, dict, str], tuple[str, dict, str], tuple[str, dict, str]
    ],
    registre_validation: tuple[str, dict, str] | None,
    verrou_charge: tuple[str, dict, str] | None,
) -> None:
    """Cohérence fail-closed des artefacts de revue avec le registre de
    verdicts, le verrou et les fichiers de dossiers effectivement écrits.
    Aucune divergence n'est réparée au rendu."""
    (_, manifeste, _), (_, controle, _), (_, engagement, _) = artefacts
    if registre_validation is None:
        raise ErreurRestitution(
            "artefacts de revue aveugle présents sans registre de verdicts"
        )
    if verrou_charge is None:
        raise ErreurRestitution(
            "artefacts de revue aveugle présents sans verrou de campagne"
        )
    registre = registre_validation[1]
    passes = [
        entree
        for entree in registre["entrees"]
        if entree["verdict"] is not None
        and entree["verdict"]["statut"] == "PASS"
    ]
    dossiers_manifeste = manifeste["dossiers"]
    if len(dossiers_manifeste) != len(passes):
        raise ErreurRestitution(
            "manifeste de dossiers non aligné sur les verdicts PASS du "
            f"registre : {len(passes)} attendu(s), "
            f"{len(dossiers_manifeste)} déclaré(s)"
        )
    items = [entree["item"] for entree in dossiers_manifeste]
    if len(set(items)) != len(items) or any(
        not _MOTIF_ITEM_REVUE.match(item) for item in items
    ):
        raise ErreurRestitution(
            "identifiants opaques invalides dans le manifeste de dossiers"
        )
    for entree in dossiers_manifeste:
        chemin = racine / entree["fichier"]
        try:
            octets = chemin.read_bytes()
        except OSError as erreur:
            raise ErreurRestitution(
                f"dossier déclaré illisible : {entree['fichier']} ({erreur})"
            ) from erreur
        if hashlib.sha256(octets).hexdigest() != entree["sha256"]:
            raise ErreurRestitution(
                f"dossier divergent de l'empreinte du manifeste : "
                f"{entree['fichier']}"
            )
    # Égalité exacte entre fichiers présents et fichiers déclarés : aucun
    # dossier périmé ou non déclaré n'est présentable comme courant
    fichiers_presents = {
        (
            REPERTOIRE_DOSSIERS_REVUE / NOM_SOUS_REPERTOIRE_DOSSIERS / nom
        ).as_posix()
        for nom in [present.name for present in _fichiers_dossiers_generes(racine)]
    }
    fichiers_declares = {entree["fichier"] for entree in dossiers_manifeste}
    if fichiers_presents != fichiers_declares:
        raise ErreurRestitution(
            "fichiers de dossiers présents non alignés sur le manifeste : "
            f"{sorted(fichiers_presents)} présents, "
            f"{sorted(fichiers_declares)} déclarés"
        )
    if not dossiers_manifeste:
        lot_vide = manifeste.get("lot_vide")
        if (
            not isinstance(lot_vide, dict)
            or lot_vide.get("cause") != "aucune_sortie_pass"
        ):
            raise ErreurRestitution(
                "manifeste à zéro dossier sans cause exacte de lot vide"
            )
        comptage: dict[str, int] = {}
        for entree in registre["entrees"]:
            statut = (
                entree["verdict"]["statut"]
                if entree["verdict"] is not None
                else "ABSENTE"
            )
            comptage[statut] = comptage.get(statut, 0) + 1
        if lot_vide.get("comptage_statuts") != comptage:
            raise ErreurRestitution(
                "comptage de lot vide divergent du registre de verdicts"
            )
    elif "lot_vide" in manifeste:
        raise ErreurRestitution(
            "manifeste avec dossiers et déclaration de lot vide simultanés"
        )
    creneaux = verrou_charge[1]["creneaux"]
    ordre = engagement["ordre_revue"]
    if engagement["cardinalite_revue"] != len(creneaux) or len(ordre) != len(
        creneaux
    ):
        raise ErreurRestitution(
            "engagement d'ordre non aligné sur les créneaux verrouillés"
        )
    positions = [entree["position"] for entree in ordre]
    if sorted(positions) != list(range(1, len(positions) + 1)):
        raise ErreurRestitution(
            "positions de l'engagement d'ordre non contiguës"
        )
    items_engagement = {entree["item"] for entree in ordre}
    if not set(items) <= items_engagement:
        raise ErreurRestitution(
            "dossiers produits hors de l'ordre engagé au verrou"
        )
    if controle["resultat"] not in RESULTATS_CONTROLE_FUITES:
        raise ErreurRestitution(
            "contrôle d'absence de fuite non conforme dans les artefacts"
        )
    if [entree["item"] for entree in controle["dossiers"]] != items:
        raise ErreurRestitution(
            "contrôle d'absence de fuite non aligné sur les dossiers"
        )


def _exclusions_revue(registre: dict) -> list[dict]:
    """Exclusions de la revue recalculées depuis le registre versionné."""
    return [
        {
            "configuration_id": entree["configuration_id"],
            "cause": _cause_exclusion_revue(entree),
        }
        for entree in registre["entrees"]
        if entree["verdict"] is None or entree["verdict"]["statut"] != "PASS"
    ]


def _section_dossiers_revue(
    manifeste: tuple[str, dict, str],
    controle: tuple[str, dict, str],
    engagement: tuple[str, dict, str],
    registre: tuple[str, dict, str],
) -> str:
    """Section de restitution des dossiers de revue aveugle : nombre de
    dossiers, nombre d'exclusions et leur cause, recalculés depuis les
    artefacts versionnés ; jamais la correspondance item ↔ acquisition."""
    relatif_manifeste, contenu_manifeste, sha_manifeste = manifeste
    relatif_controle, contenu_controle, sha_controle = controle
    relatif_engagement, contenu_engagement, sha_engagement = engagement
    relatif_registre, contenu_registre, _ = registre
    dossiers_manifeste = contenu_manifeste["dossiers"]
    exclusions = _exclusions_revue(contenu_registre)
    articles: list[str] = []
    if dossiers_manifeste:
        articles.append(
            _article(
                "fait",
                f"<p>{len(dossiers_manifeste)} dossier(s) de revue aveugle "
                f"produit(s) sous identifiants opaques, dans l'ordre engagé "
                "avant leur écriture ; la correspondance avec les "
                "acquisitions reste scellée jusqu'au gel des verdicts "
                "humains.</p>"
                + "<ul>"
                + "".join(
                    f'<li data-dossier-revue="{_echapper(entree["item"])}">'
                    f"<code>{_echapper(entree['item'])}</code> · fichier "
                    f"<code>{_echapper(entree['fichier'])}</code> · SHA-256 "
                    f"<code>{entree['sha256']}</code></li>"
                    for entree in dossiers_manifeste
                )
                + "</ul>"
                + _span_source(
                    relatif_manifeste, sha_manifeste, SECTION_DOSSIERS_REVUE
                )
                + _span_source(
                    relatif_engagement, sha_engagement, SECTION_ENGAGEMENT_ORDRE
                ),
            )
        )
    else:
        lot_vide = contenu_manifeste["lot_vide"]
        articles.append(
            _article(
                "fait",
                "<p>Lot éligible vide : aucun dossier de revue produit. "
                f"Cause exacte : <code>{_echapper(lot_vide['cause'])}</code> "
                f"(comptage des statuts automatiques : "
                f"{_echapper(json.dumps(lot_vide['comptage_statuts'], sort_keys=True))}"
                "). Aucun verdict de qualité n'est rendu.</p>"
                + _span_source(
                    relatif_manifeste, sha_manifeste, SECTION_DOSSIERS_REVUE
                )
                + _span_source(
                    relatif_engagement, sha_engagement, SECTION_ENGAGEMENT_ORDRE
                ),
            )
        )
    if exclusions:
        articles.append(
            _article(
                "fait",
                f"<p>{len(exclusions)} exclusion(s) de la revue, condition "
                "d'entrée <code>PASS</code> automatique non remplie :</p>"
                + "<ul>"
                + "".join(
                    f'<li data-exclusion-revue="{_echapper(exclusion["configuration_id"])}">'
                    f"<code>{_echapper(exclusion['configuration_id'])}</code> "
                    f"— {_echapper(exclusion['cause'])}</li>"
                    for exclusion in exclusions
                )
                + "</ul>"
                + _span_source(relatif_registre, registre[2], SECTION_REGISTRE_VALIDATION),
            )
        )
    else:
        articles.append(
            _article(
                "fait",
                "<p>0 exclusion : toutes les sorties candidates du registre "
                "sont au verdict automatique <code>PASS</code>.</p>"
                + _span_source(relatif_registre, registre[2], SECTION_REGISTRE_VALIDATION),
            )
        )
    categories_controle = contenu_controle["categories"]
    libelles_couverts = [
        _LIBELLES_CATEGORIES_FUITES[nom]
        for nom in CATEGORIES_FUITES
        if categories_controle[nom]["statut"] == "COUVERTE"
    ]
    noms_non_couverts = [
        nom
        for nom in CATEGORIES_FUITES
        if categories_controle[nom]["statut"] == "NON_COUVERTE"
    ]
    phrase_controle = (
        "<p>Contrôle d'absence de fuite : résultat "
        f"<code>{_echapper(contenu_controle['resultat'])}</code> — "
        "aucun jeton interdit des catégories couvertes ("
        + _echapper(", ".join(libelles_couverts))
        + ") n'apparaît dans aucun dossier."
    )
    if noms_non_couverts:
        phrase_controle += (
            " Catégories non couvertes, faute de valeurs exploitables "
            f"(<code>INCONNU</code>) : {_echapper(', '.join(noms_non_couverts))}"
            " — absence de preuve conservée, aucune conclusion favorable "
            "n'en est tirée."
        )
    phrase_controle += "</p>"
    articles.append(
        _article(
            "fait",
            phrase_controle
            + _span_source(relatif_controle, sha_controle, SECTION_CONTROLE_FUITES),
        )
    )
    return (
        '<section id="dossiers-revue-aveugle" data-dossiers-revue="section">'
        "<h2>Dossiers de revue aveugle</h2>"
        "<p>Cette section reprend les artefacts produits par "
        "<code>dossiers</code> : manifeste de dossiers, engagement d'ordre "
        "écrit avant tout dossier et contrôle d'absence de fuite. Les "
        "dossiers sont opaques ; la correspondance avec les acquisitions "
        "n'est pas publiée.</p>"
        + "".join(articles)
        + "</section>"
    )


SECTION_GEL_VERDICTS = "gel des verdicts humains V1 versionné"
SECTION_RECU_VERDICT = "reçu de verdict humain gelé V1 versionné"
SECTION_REVELATION = "révélation de correspondance V1 versionnée"


def _charger_artefacts_verdicts(racine: Path) -> dict | None:
    """Gel, reçus de verdicts et révélation pour le rendu.

    Le gel est produit par `geler` ; une révélation ou des reçus sans gel
    sont une divulgation hors contrat, refusée au rendu, jamais réparée. La
    saisie humaine est une entrée, pas une preuve : elle n'est pas rendue."""
    gel_present = os.path.lexists(racine / CHEMIN_GEL_VERDICTS)
    revelation_presente = os.path.lexists(
        racine / CHEMIN_REVELATION_CORRESPONDANCE
    )
    recus_presents = os.path.lexists(racine / REPERTOIRE_RECUS_VERDICTS)
    if not gel_present:
        if revelation_presente or recus_presents:
            raise ErreurRestitution(
                "révélation ou reçus de verdicts présents sans gel : "
                "divulgation hors contrat, aucune réparation"
            )
        return None
    charge_gel = _charger_json_artefact_dossiers(racine, CHEMIN_GEL_VERDICTS)
    _, gel, _ = charge_gel
    if gel.get("schema_version") != SCHEMA_GEL_VERDICTS:
        raise ErreurRestitution(
            f"gel de verdicts de schéma inattendu : {charge_gel[0]}"
        )
    lot_vide = "lot_vide" in gel
    if lot_vide:
        if revelation_presente or recus_presents:
            raise ErreurRestitution(
                "lot vide gelé avec révélation ou reçus de verdicts : "
                "aucune revue n'a eu lieu, aucune réparation"
            )
        if (
            gel.get("verdicts_requis") != 0
            or gel.get("recus") != []
            or gel.get("intervention_relecteur") != INTERVENTION_AUCUNE
            or gel.get("revelation") != REVELATION_LOT_VIDE
        ):
            raise ErreurRestitution(
                "gel de lot vide incohérent : zéro verdict, zéro reçu et "
                "aucune intervention attendus"
            )
        return {"gel": charge_gel, "recus": [], "revelation": None}
    if not revelation_presente:
        raise ErreurRestitution(
            "gel de lot non vide sans révélation : le gel complet révèle "
            "dans la même invocation, aucune réparation"
        )
    entrees_gel = gel.get("recus")
    if not isinstance(entrees_gel, list) or not entrees_gel:
        raise ErreurRestitution(
            "gel de lot non vide sans reçu déclaré : aucune réparation"
        )
    recus: list[tuple[str, dict, str]] = []
    for entree in entrees_gel:
        charge_recu = _charger_json_artefact_dossiers(
            racine, Path(entree["chemin"])
        )
        relatif_recu, recu, sha_recu = charge_recu
        if sha_recu != entree["sha256"]:
            raise ErreurRestitution(
                f"reçu de verdict divergent de l'empreinte du gel : "
                f"{relatif_recu} — un verdict gelé est immuable"
            )
        if recu.get("schema_version") != SCHEMA_RECU_VERDICT_HUMAIN:
            raise ErreurRestitution(
                f"reçu de verdict de schéma inattendu : {relatif_recu}"
            )
        if recu.get("item") != entree["item"]:
            raise ErreurRestitution(
                f"reçu de verdict d'item divergent du gel : {relatif_recu}"
            )
        if recu.get("verdict") not in VERDICTS_HUMAINS:
            raise ErreurRestitution(
                f"verdict hors vocabulaire dans le reçu gelé : {relatif_recu}"
            )
        justification = recu.get("justification")
        if not isinstance(justification, str) or not justification.strip():
            raise ErreurRestitution(
                f"justification vide dans le reçu gelé : {relatif_recu}"
            )
        if recu.get("relecteur") != RELECTEUR_AUTORISE:
            raise ErreurRestitution(
                f"relecteur hors décision D-V1-06 dans le reçu gelé : "
                f"{relatif_recu}"
            )
        recus.append(charge_recu)
    charge_revelation = _charger_json_artefact_dossiers(
        racine, CHEMIN_REVELATION_CORRESPONDANCE
    )
    if (
        charge_revelation[1].get("schema_version")
        != SCHEMA_REVELATION_CORRESPONDANCE
    ):
        raise ErreurRestitution(
            f"révélation de schéma inattendu : {charge_revelation[0]}"
        )
    return {"gel": charge_gel, "recus": recus, "revelation": charge_revelation}


def _verifier_coherence_verdicts(
    artefacts_verdicts: dict,
    artefacts_dossiers: tuple[
        tuple[str, dict, str], tuple[str, dict, str], tuple[str, dict, str]
    ] | None,
    registre_validation: tuple[str, dict, str] | None,
    verrou_charge: tuple[str, dict, str] | None,
) -> None:
    """Cohérence fail-closed du gel avec les dossiers, le registre, le
    verrou et la chronologie gel puis révélation. Aucune réparation."""
    if artefacts_dossiers is None:
        raise ErreurRestitution(
            "gel de verdicts présent sans artefacts de revue aveugle"
        )
    if registre_validation is None or verrou_charge is None:
        raise ErreurRestitution(
            "gel de verdicts présent sans registre de verdicts ou sans verrou"
        )
    (_, manifeste, sha_manifeste) = artefacts_dossiers[0]
    (relatif_engagement, engagement, sha_engagement) = artefacts_dossiers[2]
    relatif_gel, gel, sha_gel = artefacts_verdicts["gel"]
    if gel["engagement_ordre"] != {
        "chemin": relatif_engagement,
        "sha256": sha_engagement,
    } or gel["manifeste_dossiers"] != {
        "chemin": artefacts_dossiers[0][0],
        "sha256": sha_manifeste,
    }:
        raise ErreurRestitution(
            "gel de verdicts non chaîné aux artefacts de revue courants : "
            "aucune réparation"
        )
    decision_attendue = {
        "id": DECISION_RELECTEUR_ID,
        "relecteur": RELECTEUR_AUTORISE,
        "disponibilite": DISPONIBILITE_RELECTEUR,
        "url": URL_DECISION_RELECTEUR,
    }
    if gel.get("decision") != decision_attendue:
        raise ErreurRestitution(
            "décision D-V1-06 divergente dans le gel de verdicts"
        )
    if gel.get("juge_fantome") != STATUT_JUGE_FANTOME:
        raise ErreurRestitution(
            "statut de juge fantôme divergent de la décision héritée DISABLED"
        )
    items_manifeste = [entree["item"] for entree in manifeste["dossiers"]]
    items_gel = [entree["item"] for entree in gel["recus"]]
    if items_gel != items_manifeste or gel["verdicts_requis"] != len(
        items_manifeste
    ):
        raise ErreurRestitution(
            "gel de verdicts non aligné sur le lot éligible du manifeste"
        )
    if ("lot_vide" in gel) != (not items_manifeste):
        raise ErreurRestitution(
            "déclaration de lot vide du gel divergente du manifeste"
        )
    if "lot_vide" in gel:
        if gel["lot_vide"] != manifeste["lot_vide"]:
            raise ErreurRestitution(
                "fait de lot vide du gel divergent du manifeste de dossiers"
            )
        return
    # Lot gelé : chronologie stricte et états officiels recalculés
    charge_revelation = artefacts_verdicts["revelation"]
    _, revelation, _ = charge_revelation
    recus = {relatif: recu for relatif, recu, _ in artefacts_verdicts["recus"]}
    horodatage_gel = gel.get("horodatage_gel_utc")
    if not isinstance(horodatage_gel, str) or not horodatage_gel:
        raise ErreurRestitution("gel de verdicts sans horodatage")
    for relatif_recu, recu in recus.items():
        horodatage_recu = recu.get("horodatage_utc")
        if not isinstance(horodatage_recu, str) or horodatage_recu > horodatage_gel:
            raise ErreurRestitution(
                f"chronologie inversée : reçu {relatif_recu} postérieur au gel"
            )
    horodatage_revelation = revelation.get("horodatage_revelation_utc")
    if (
        not isinstance(horodatage_revelation, str)
        or horodatage_revelation <= horodatage_gel
        or revelation.get("posterieure_au_gel") is not True
    ):
        raise ErreurRestitution(
            "révélation non strictement postérieure au gel : la chronologie "
            "relative doit le prouver"
        )
    if revelation.get("gel") != {"chemin": relatif_gel, "sha256": sha_gel}:
        raise ErreurRestitution(
            "révélation non chaînée au gel réellement écrit : aucune "
            "modification après révélation"
        )
    relatif_verrou, verrou, sha_verrou = verrou_charge
    if revelation.get("verrou") != {
        "chemin": relatif_verrou,
        "sha256": sha_verrou,
    }:
        raise ErreurRestitution("révélation non chaînée au verrou courant")
    engagement_verrou = next(
        entree
        for entree in verrou["engagements_prives"]
        if entree["kind"] == "manifeste-ordre"
    )
    if revelation.get("engagement_verifie") != {
        "commitment": engagement_verrou["commitment"],
        "commitment_method": engagement_verrou["commitment_method"],
        "resultat": "CONFORME",
    }:
        raise ErreurRestitution(
            "engagement vérifié de la révélation divergent du verrou"
        )
    correspondance = revelation.get("correspondance")
    if not isinstance(correspondance, list):
        raise ErreurRestitution("révélation sans correspondance")
    items_ordre = {
        entree["item"]: entree["position"]
        for entree in engagement["ordre_revue"]
    }
    creneaux = {
        creneau["acquisition_id"]: creneau["configuration_id"]
        for creneau in verrou["creneaux"]
    }
    if len(correspondance) != len(items_ordre):
        raise ErreurRestitution(
            "correspondance révélée non alignée sur l'ordre engagé"
        )
    par_acquisition: dict[str, str] = {}
    for entree in correspondance:
        if (
            items_ordre.get(entree.get("item")) != entree.get("position")
            or creneaux.get(entree.get("acquisition_id"))
            != entree.get("configuration_id")
        ):
            raise ErreurRestitution(
                "entrée de correspondance révélée divergente de l'ordre "
                "engagé ou des créneaux verrouillés"
            )
        par_acquisition[entree["acquisition_id"]] = entree["item"]
    verdicts_humains = {
        recu["item"]: recu["verdict"] for recu in recus.values()
    }
    etats_attendus = []
    for entree in registre_validation[1]["entrees"]:
        verdict = entree["verdict"]
        statut = verdict["statut"] if verdict is not None else None
        item = None
        verdict_humain = None
        if statut == "PASS":
            item = par_acquisition.get(
                _identifiant_creneau(entree["configuration_id"])
            )
            verdict_humain = verdicts_humains.get(item)
        etats_attendus.append(
            {
                "configuration_id": entree["configuration_id"],
                "recu": entree["recu"],
                "verdict_automatique": statut,
                "item": item,
                "verdict_humain": verdict_humain,
                "etat_officiel": _etat_officiel(statut, verdict_humain),
            }
        )
    if revelation.get("etats_officiels") != etats_attendus:
        raise ErreurRestitution(
            "états officiels de la révélation divergents de la conjonction "
            "stricte recalculée : aucune réparation"
        )


def _sources_verdicts(artefacts_verdicts: dict) -> list[tuple[str, dict, str]]:
    """Sources citées de la section des verdicts : gel, reçus, révélation."""
    sources = [artefacts_verdicts["gel"], *artefacts_verdicts["recus"]]
    if artefacts_verdicts["revelation"] is not None:
        sources.append(artefacts_verdicts["revelation"])
    return sources


def _section_verdicts_humains(
    artefacts_verdicts: dict,
    sha_rules: str,
) -> str:
    """Section de restitution du gel des verdicts humains : décision
    D-V1-06 en provenance, reçus gelés, chronologie et états officiels
    révélés ; pour un lot vide, l'absence d'intervention est déclarée."""
    relatif_gel, gel, sha_gel = artefacts_verdicts["gel"]
    decision = gel["decision"]
    articles: list[str] = [
        _article(
            "fait",
            "<p>Décision propriétaire <code>"
            f"{_echapper(decision['id'])}</code> : relecteur humain aveugle "
            f"autorisé <code>{_echapper(decision['relecteur'])}</code>, "
            "disponibilité <code>"
            f"{_echapper(decision['disponibilite'])}</code>. Le juge LLM "
            f"fantôme reste <code>{_echapper(gel['juge_fantome'])}</code>, "
            "décision V0 héritée. Preuve : <code>"
            f"{_neutraliser_schema(_echapper(decision['url']))}</code>.</p>"
            + _span_source(relatif_gel, sha_gel, SECTION_GEL_VERDICTS),
        ),
        _article(
            "deduction",
            "<p>Pourquoi le juge LLM fantôme reste-t-il "
            f"<code>{_echapper(gel['juge_fantome'])}</code>, et pourquoi "
            "n'est-ce pas un blocage ? Déduction raisonnée : la règle "
            "U-015 n'autorise un juge LLM qu'après le gel du verdict "
            "humain, avec un avis séparé et sans effet officiel ; le gel "
            "versionné porte <code>juge_fantome</code> <code>"
            f"{_echapper(gel['juge_fantome'])}</code>, décision héritée "
            "de la V0. Un juge synthétique n'aurait donc jamais d'effet "
            "officiel et ne se substitue pas à la revue humaine aveugle : "
            "sa désactivation ne retire aucun effet officiel, ce n'est "
            "pas un blocage et rien n'est à lever ici.</p>"
            + _span_source(relatif_gel, sha_gel, SECTION_GEL_VERDICTS)
            + _span_source("docs/RULES.md", sha_rules, "U-015"),
            ' data-explication-verdicts="juge-fantome"'
            ' data-premisses="le gel versionné porte juge_fantome '
            f"{_echapper(gel['juge_fantome'])}, décision héritée de la"
            " V0 ; la règle U-015 n'autorise un juge LLM qu'après gel du"
            " verdict humain, avec un avis séparé et sans effet"
            ' officiel"',
        ),
    ]
    if "lot_vide" in gel:
        lot_vide = gel["lot_vide"]
        articles.append(
            _article(
                "fait",
                "<p>Gel du lot éligible vide : 0 verdict requis, 0 reçu "
                "écrit — aucune intervention du relecteur humain n'a eu "
                "lieu, aucune configuration n'est dégradée et aucune "
                "correspondance n'est révélée. Cause exacte : <code>"
                f"{_echapper(lot_vide['cause'])}</code> (comptage des "
                "statuts automatiques : "
                f"{_echapper(json.dumps(lot_vide['comptage_statuts'], sort_keys=True))}"
                "). Aucun état officiel n'existe.</p>"
                + _span_source(relatif_gel, sha_gel, SECTION_GEL_VERDICTS),
            )
        )
        if lot_vide["cause"] == "aucune_sortie_pass":
            articles.append(
                _article(
                    "fait",
                    "<p>Pourquoi le relecteur humain n'a-t-il pas été "
                    "sollicité ? La décision <code>"
                    f"{_echapper(decision['id'])}</code> ne l'autorise que "
                    "si un dossier éligible existe. Le comptage gelé "
                    "ci-dessus ne contient aucun <code>PASS</code> "
                    "automatique : zéro dossier éligible, zéro verdict "
                    "requis. Action immédiate du relecteur pour ce lot : "
                    "aucune. Une future revue humaine exige d'abord une "
                    "sortie automatique <code>PASS</code> dans un lot "
                    "autorisé ; la restitution ne peut pas la "
                    "fabriquer.</p>"
                    + _span_source(
                        relatif_gel, sha_gel, SECTION_GEL_VERDICTS
                    ),
                    ' data-explication-verdicts="relecteur-non-sollicite"',
                )
            )
    else:
        for relatif_recu, recu, sha_recu in artefacts_verdicts["recus"]:
            articles.append(
                _article(
                    "fait",
                    f'<p data-verdict-humain="{_echapper(recu["item"])}">'
                    f"<code>{_echapper(recu['item'])}</code> — verdict "
                    f"humain gelé <code>{_echapper(recu['verdict'])}</code> "
                    f"(séquence {recu['sequence']}, horodatage "
                    f"<code>{_echapper(recu['horodatage_utc'])}</code>) · "
                    "justification liée à la sortie : "
                    f"{_echapper(recu['justification'])} · dossier "
                    f"<code>{_echapper(recu['dossier']['fichier'])}</code> · "
                    f"SHA-256 <code>{recu['dossier']['sha256']}</code></p>"
                    + _span_source(relatif_recu, sha_recu, SECTION_RECU_VERDICT),
                )
            )
        relatif_revelation, revelation, sha_revelation = artefacts_verdicts[
            "revelation"
        ]
        articles.append(
            _article(
                "fait",
                '<p data-revelation="correspondance">Correspondance révélée '
                "strictement après le gel complet : gel à <code>"
                f"{_echapper(gel['horodatage_gel_utc'])}</code>, révélation "
                "à <code>"
                f"{_echapper(revelation['horodatage_revelation_utc'])}</code>. "
                "Engagement masqué du verrou vérifié : <code>"
                f"{_echapper(revelation['engagement_verifie']['resultat'])}"
                "</code>.</p>"
                + "<ul>"
                + "".join(
                    '<li data-correspondance-revelee="'
                    f'{_echapper(entree["item"])}"><code>'
                    f"{_echapper(entree['item'])}</code> (position "
                    f"{entree['position']}) ↔ <code>"
                    f"{_echapper(entree['configuration_id'])}</code> · "
                    f"<code>{_echapper(entree['acquisition_id'])}</code></li>"
                    for entree in revelation["correspondance"]
                )
                + "</ul>"
                + _span_source(
                    relatif_revelation, sha_revelation, SECTION_REVELATION
                ),
            )
        )
        articles.append(
            _article(
                "fait",
                "<p>États officiels par conjonction stricte — "
                "<code>OFFICIALLY_ACCEPTABLE</code> si et seulement si le "
                "verdict automatique est <code>PASS</code> et le verdict "
                "humain <code>ACCEPTABLE</code> :</p>"
                + "<ul>"
                + "".join(
                    '<li data-etat-officiel="'
                    f'{_echapper(entree["configuration_id"])}"><code>'
                    f"{_echapper(entree['configuration_id'])}</code> — "
                    f"automatique <code>"
                    f"{_echapper(entree['verdict_automatique'] or 'AUCUN')}"
                    "</code> · humain <code>"
                    f"{_echapper(entree['verdict_humain'] or 'AUCUN')}"
                    "</code> → état officiel <code>"
                    f"{_echapper(entree['etat_officiel'])}</code></li>"
                    for entree in revelation["etats_officiels"]
                )
                + "</ul>"
                + _span_source(
                    relatif_revelation, sha_revelation, SECTION_REVELATION
                ),
            )
        )
    return (
        '<section id="verdicts-humains" data-verdicts-humains="section">'
        "<h2>Verdicts humains aveugles gelés</h2>"
        "<p>Cette section reprend les artefacts produits par "
        "<code>geler</code> : le gel des verdicts humains, leurs reçus "
        "immuables et la révélation de correspondance postérieure au gel. "
        "La vue n'améliore aucune preuve.</p>"
        + "".join(articles)
        + "</section>"
    )


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


def _charger_verrou_recuperation(racine: Path) -> tuple[str, dict, str] | None:
    """Verrou de récupération validé pour le rendu : (chemin relatif,
    verrou, SHA-256), ou None lorsqu'il n'est pas matérialisé."""
    chemin = racine / CHEMIN_VERROU_RECUPERATION
    if not os.path.lexists(chemin):
        return None
    infos = os.lstat(chemin)
    if stat.S_ISLNK(infos.st_mode) or not stat.S_ISREG(infos.st_mode):
        raise ErreurRestitution(
            "verrou de récupération : fichier régulier non symbolique attendu"
        )
    try:
        verrou = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurRestitution(
            f"verrou de récupération illisible : {erreur}"
        ) from erreur
    if not isinstance(verrou, dict) or set(verrou) != _CLES_VERROU_RECUPERATION:
        raise ErreurRestitution(
            "verrou de récupération : clés hors schéma fermé"
        )
    if verrou["schema_version"] != SCHEMA_VERROU_RECUPERATION:
        raise ErreurRestitution(
            "verrou de récupération : schéma "
            f"'{SCHEMA_VERROU_RECUPERATION}' attendu"
        )
    if not isinstance(verrou["portee"], dict) or set(
        verrou["portee"]
    ) != _CLES_PORTEE_RECUPERATION:
        raise ErreurRestitution(
            "verrou de récupération : portée hors schéma fermé"
        )
    configurations = verrou["configurations"]
    if not isinstance(configurations, list) or len(configurations) != 2:
        raise ErreurRestitution(
            "verrou de récupération : exactement deux configurations fermées"
        )
    for configuration in configurations:
        if (
            not isinstance(configuration, dict)
            or set(configuration) != _CLES_CONFIGURATION_RECUPERATION
            or not isinstance(configuration["descripteur"], dict)
            or set(configuration["descripteur"])
            != _CLES_DESCRIPTEUR_RECUPERATION
        ):
            raise ErreurRestitution(
                "verrou de récupération : configuration hors schéma fermé"
            )
    for preuve in verrou["preuves_identite_futures"]:
        if (
            not isinstance(preuve, dict)
            or set(preuve) != _CLES_PREUVE_IDENTITE_RECUPERATION
        ):
            raise ErreurRestitution(
                "verrou de récupération : preuve d'identité hors schéma fermé"
            )
    sentinelles = verrou["sentinelles"]
    if not isinstance(sentinelles, list) or len(sentinelles) != 2:
        raise ErreurRestitution(
            "verrou de récupération : exactement deux sentinelles fermées"
        )
    for sentinelle in sentinelles:
        if (
            not isinstance(sentinelle, dict)
            or set(sentinelle) != _CLES_SENTINELLE_RECUPERATION
        ):
            raise ErreurRestitution(
                "verrou de récupération : sentinelle hors schéma fermé"
            )
    sources = verrou["sources_historiques"]
    if (
        not isinstance(sources, list)
        or len(sources) != len(CHEMINS_SOURCES_HISTORIQUES_RECUPERATION)
        or len({source.get("chemin") for source in sources}) != len(sources)
    ):
        raise ErreurRestitution(
            "verrou de récupération : sources historiques hors schéma fermé"
        )
    for source in sources:
        if (
            not isinstance(source, dict)
            or set(source) != _CLES_SOURCE_HISTORIQUE_RECUPERATION
            or source["chemin"]
            not in CHEMINS_SOURCES_HISTORIQUES_RECUPERATION
            or not isinstance(source["sha256"], str)
            or not _MOTIF_SHA256.match(source["sha256"])
        ):
            raise ErreurRestitution(
                "verrou de récupération : source historique hors schéma fermé"
            )
    attendu = _structure_verrou_recuperation(sources)
    for cle in (
        "portee",
        "configurations",
        "autorite_execution",
        "creneaux_executes",
        "reprises_executees",
        "fallback",
        "variantes_interdites",
        "preuves_identite_futures",
        "jamais_preuve",
        "sentinelles",
    ):
        if verrou[cle] != attendu[cle]:
            raise ErreurRestitution(
                f"verrou de récupération : champ '{cle}' divergent du "
                "contrat fermé"
            )
    return (
        CHEMIN_VERROU_RECUPERATION.as_posix(),
        verrou,
        _sha256_fichier(chemin),
    )


def _charger_autorisation_recuperation_restitution(
    racine: Path,
) -> tuple[str, dict, str] | None:
    """Autorisation D-V1-05 pour le rendu : (chemin relatif, données,
    SHA-256 du fichier), ou None lorsque l'artefact n'existe pas."""
    chemin = racine / CHEMIN_AUTORISATION_RECUPERATION
    if not os.path.lexists(chemin):
        return None
    try:
        donnees = _charger_autorisation_recuperation(racine)
    except ErreurRecuperation as erreur:
        raise ErreurRestitution(
            f"autorisation de récupération invalide : {erreur}"
        ) from erreur
    return (
        CHEMIN_AUTORISATION_RECUPERATION.as_posix(),
        donnees,
        _sha256_fichier(chemin),
    )


def _articles_recuperation(
    relatif: str,
    sha: str,
    verrou: dict,
    autorisation: tuple[str, dict, str] | None = None,
) -> list[str]:
    """État minimal de récupération, régénérable à l'identique."""
    creneaux = " et ".join(
        f"<code>{_echapper(configuration['acquisition_id'])}</code>"
        for configuration in verrou["configurations"]
    )
    etat = _article(
        "fait",
        "<p>Un verrou additif de récupération des harnais Antigravity et "
        f"Z.AI est matérialisé pour les créneaux {creneaux} : descripteurs "
        "fermés, autorite_execution "
        f"<code>{_echapper(verrou['autorite_execution'])}</code>, "
        f"creneaux_executes {verrou['creneaux_executes']}, reprises_executees "
        f"{verrou['reprises_executees']}, fallback "
        f"<code>{_echapper(verrou['fallback'])}</code>, sans variante "
        "fallback, retry, fast, priority, max ni ultra.</p>"
        + _span_source(relatif, sha, SECTION_VERROU_RECUPERATION),
        ' data-recuperation-harnais="etat"',
    )
    preuves = _article(
        "fait",
        "<p>Aucune identité servie ne peut devenir OBSERVED sans preuve "
        "attribuable à la tentative : pour Z.AI, une trace OpenCodex avec "
        "fournisseur zai, modèle glm-5.3, effort effectif high, une tentative "
        "et aucun fallback ; pour Antigravity, une métadonnée attribuable "
        "portant gemini-3.7-flash-high ; sinon la provenance servie reste "
        "INCONNU et HOLD. Un argv demandé ou un code de sortie 0 ne constitue "
        "jamais cette preuve.</p>"
        + _span_source(relatif, sha, SECTION_VERROU_RECUPERATION),
        ' data-recuperation-harnais="preuves-identite"',
    )
    articles = [etat, preuves]
    if autorisation is not None:
        relatif_autorisation, donnees, sha_autorisation = autorisation
        portee = donnees["portee"]
        creneaux_autorises = " et ".join(
            f"<code>{_echapper(creneau['acquisition_id'])}</code>"
            for creneau in portee["acquisitions"]
        )
        articles.append(
            _article(
                "fait",
                "<p>Une autorisation propriétaire additive "
                f"<strong>{_echapper(donnees['autorite'])}</strong> couvre "
                f"l'exécution des créneaux {creneaux_autorises} (tranche "
                f"<code>{_echapper(portee['tranche'])}</code>) : au plus "
                f"{_echapper(portee['appels_fournisseur_max'])} appels "
                f"fournisseur, {_echapper(portee['appels_par_creneau'])} par "
                "créneau, effort candidat commun "
                f"<code>{_echapper(portee['effort_candidat'])}</code>, "
                "reprises automatiques 0, reprises manuelles 0, dépense "
                "incrémentale 0, fallback <code>NONE</code>, quota des "
                "abonnements existants seuls. Jeton propriétaire "
                f"<code>{_echapper(donnees['jeton'])}</code>. Le verrou R1 "
                "reste <code>NOT_GRANTED</code> et byte-identique ; cet "
                "artefact séparé porte seul le GO d'exécution.</p>"
                + _span_source(
                    relatif_autorisation,
                    sha_autorisation,
                    SECTION_AUTORISATION_RECUPERATION,
                ),
                ' data-recuperation-harnais="autorisation-execution"',
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


def _section_couverture_etat(
    etat_relatif: str, sha_etat: str, couverture: dict
) -> str:
    """Section de restitution de l'état et de la couverture : reprise
    littérale du registre versionné produit par etat, jamais recalculée."""
    lignes = []
    for creneau in couverture["creneaux"]:
        identifiant = creneau["configuration_id"]
        if creneau["couvert"]:
            statut = (
                "couvert : décision "
                f"<code>{_echapper(creneau['decision'])}</code>"
            )
        elif creneau["cause"] == CAUSE_PREUVE_MANQUANTE:
            statut = "non couvert : preuve manquante"
        else:
            statut = (
                "non couvert : cause prouvée "
                f"<code>{_echapper(creneau['cause'])}</code>"
            )
        incidents = ""
        if creneau["incidents"]:
            consignes = ", ".join(
                f"<code>{_echapper(incident)}</code>"
                for incident in creneau["incidents"]
            )
            incidents = f" · incident(s) consigné(s) : {consignes}"
        lignes.append(
            f'<li data-couverture-creneau="{_echapper(identifiant)}">'
            f"<code>{_echapper(identifiant)}</code> — {statut} · "
            f"{_echapper(creneau['detail'])}{incidents}</li>"
        )
    return (
        '<section id="couverture-v1" data-couverture-v1="section">'
        "<h2>État et couverture de la campagne V1</h2>"
        "<p>Cette section reprend le registre de couverture versionné, "
        "produit par <code>etat</code> dans l'état V1 et consommé tel "
        "quel : une fraction exacte du plan, avec la décision ou la cause "
        "prouvée de chaque créneau. La couverture n'est ni un axe de "
        "comparaison, ni une métrique comparative, ni un score, ni un "
        "classement, ni un gagnant, ni une recommandation.</p>"
        + _article(
            "fait",
            "<p>Couverture du plan : "
            f"<code>{_echapper(couverture['fraction'])}</code> — "
            f"{couverture['numerateur']} créneau(x) couvert(s) par une "
            "décision officielle ou un échec fournisseur attribuable, sur "
            f"{couverture['denominateur']} configurations déclarées au "
            f"registre officiel ({_echapper(couverture['regle'])}). Les "
            "créneaux non couverts restent visibles avec leur cause "
            "prouvée ; un créneau sans preuve reste une preuve manquante, "
            "jamais un échec candidat.</p>"
            + _span_source(etat_relatif, sha_etat, SECTION_COUVERTURE_ETAT),
        )
        + _article(
            "fait",
            "<ul>" + "".join(lignes) + "</ul>"
            + _span_source(etat_relatif, sha_etat, SECTION_COUVERTURE_ETAT),
        )
        + "</section>"
    )


# ---------------------------------------------------------------------------
# V1-XS-14 : restitution complète — évaluation des déclencheurs d'abstention
# U-018 et comparaison située strictement intra-panel abonnement (Issue #115)

# Familles de déclencheurs U-018, toutes évaluées et publiées à chaque rendu
FAMILLES_DECLENCHEURS = (
    "identite",
    "provenance",
    "fraicheur",
    "comparabilite",
    "preference",
)
AXE_TAUX = "taux-acceptable"
AXE_COUT = "cout-par-sortie-acceptable"
AXE_LATENCE = "latence-preenregistree"
# Les trois axes figés de la comparaison située, jamais agrégés entre eux
AXES_COMPARAISON = (AXE_TAUX, AXE_COUT, AXE_LATENCE)
# Motifs refusés partout dans la page publiée, en minuscules : toute
# occurrence est une injection, jamais un contenu légitime de la vue
MOTIFS_RESTITUTION_INTERDITS = (
    "classement général",
    "vainqueur",
    "score agrégé",
    "score global",
    "meilleur produit",
    "meilleure configuration",
)
# Formes comparatives inter-profils refusées, en minuscules : la page
# légitime ne mentionne les autres profils qu'en séparation, jamais en
# comparaison (ARD section 7)
MOTIFS_INTER_PROFILS_INTERDITS = (
    "surpasse le profil",
    "dépasse le profil",
    "supérieur au profil",
    "inférieur au profil",
    "meilleur que le profil",
    "contre le profil",
)


def _evaluer_restitution_complete(
    racine: Path,
    configurations: list[tuple[str, dict]],
    couverture: dict | None,
    table_metriques: tuple[str, dict, str] | None,
    cout_abonnement: tuple[str, dict, str] | None,
    verrou_charge: tuple[str, dict, str] | None,
) -> dict:
    """Évaluation mécanique des cinq déclencheurs d'abstention U-018
    depuis les seuls artefacts versionnés chargés, puis décision de
    branche : comparaison située intra-panel ou abstention.

    Chaque déclencheur porte son constat ; sous déclenchement il nomme la
    preuve absente et l'action humaine possible. Aucune branche n'est
    présumée et aucune valeur de remplacement n'est créée. Le déclencheur
    preference porte sur l'agrégation inter-axes : il reste actif tant
    qu'aucune préférence propriétaire versionnée n'existe et n'empêche
    jamais la comparaison par axe, qui ne pondère rien."""
    declencheurs: list[dict] = []

    def _declencheur(
        famille: str,
        declenche: bool,
        constat: str,
        preuve_absente: str | None = None,
        action_humaine: str | None = None,
    ) -> None:
        declencheurs.append(
            {
                "famille": famille,
                "declenche": declenche,
                "constat": constat,
                "preuve_absente": preuve_absente,
                "action_humaine": action_humaine,
            }
        )

    ids_registre = [donnees["configuration_id"] for _, donnees in configurations]
    if verrou_charge is None:
        _declencheur(
            "identite",
            True,
            "aucun verrou de campagne ne fige les identités complètes du "
            "panel abonnement",
            "verrou de campagne versionné figeant produit, plan et "
            "configuration par empreintes",
            "produire le verrou par la commande verrouiller, sous décision "
            "propriétaire",
        )
    else:
        ids_verrou = [
            entree["configuration_id"] for entree in verrou_charge[1]["panel"]
        ]
        if ids_verrou != ids_registre:
            _declencheur(
                "identite",
                True,
                "les identités verrouillées divergent du registre officiel "
                "courant",
                "verrou de campagne aligné une à une sur le registre "
                "officiel courant",
                "reproduire le verrou sur le registre courant, sous "
                "décision propriétaire",
            )
        else:
            _declencheur(
                "identite",
                False,
                f"les {len(ids_registre)} identités verrouillées "
                "correspondent une à une au registre officiel versionné",
            )

    artefacts_manquants = []
    if couverture is None:
        artefacts_manquants.append(
            "registre de couverture publié par la commande etat"
        )
    if table_metriques is None:
        artefacts_manquants.append(
            "table de métriques produite par la commande metriques"
        )
    if cout_abonnement is None:
        artefacts_manquants.append(
            "document de coût d'abonnement produit par la commande cout"
        )
    if artefacts_manquants:
        _declencheur(
            "provenance",
            True,
            "la chaîne de provenance des mesures est incomplète",
            " ; ".join(artefacts_manquants),
            "produire chaque artefact absent par sa commande, depuis les "
            "seules preuves versionnées, sans valeur de remplacement",
        )
    else:
        _declencheur(
            "provenance",
            False,
            "couverture, table de métriques et coût d'abonnement "
            "versionnés sont présents et cités par empreintes",
        )

    if verrou_charge is None:
        _declencheur(
            "fraicheur",
            True,
            "aucune fenêtre de fraîcheur n'existe sans verrou de campagne",
            "verrou de campagne portant la règle de fraîcheur "
            "EXACT_LOCK_EVENT_BASED_NO_TTL",
            "produire le verrou par la commande verrouiller, sous décision "
            "propriétaire",
        )
    else:
        verrou = verrou_charge[1]
        references = [
            (
                verrou["sources_plans"]["chemin"],
                verrou["sources_plans"]["sha256"],
            )
        ] + [
            (
                entree["configuration"]["chemin"],
                entree["configuration"]["sha256"],
            )
            for entree in verrou["panel"]
        ]
        divergents = []
        for chemin, sha_verrouille in references:
            try:
                sha_courant = _sha256_fichier(racine / chemin)
            except OSError:
                sha_courant = None
            if sha_courant != sha_verrouille:
                divergents.append(chemin)
        if divergents:
            _declencheur(
                "fraicheur",
                True,
                "événement matériel LOCKED_ARTIFACT_CHANGED constaté sur "
                + ", ".join(divergents)
                + " — effet HOLD_STOP_NO_CROSS_EVENT_COMPARISON",
                "preuves reproduites sous un nouvel événement de verrou",
                "reproduire verrou et preuves sous un nouvel événement de "
                "verrou, sous décision propriétaire",
            )
        else:
            _declencheur(
                "fraicheur",
                False,
                "chaque artefact verrouillé porte encore son empreinte "
                "exacte : la règle EXACT_LOCK_EVENT_BASED_NO_TTL ne "
                "constate aucun événement matériel",
            )

    if table_metriques is None:
        comparables: list[dict] = []
        _declencheur(
            "comparabilite",
            True,
            "aucun front de comparaison n'existe sans table de métriques",
            "table de métriques versionnée portant les statuts de "
            "comparabilité",
            "produire la table par la commande metriques depuis les "
            "preuves versionnées",
        )
    else:
        comparables = [
            ligne
            for ligne in table_metriques[1]["configurations"]
            if ligne["comparabilite"]["statut"] == "COMPARABLE"
        ]
        if len(comparables) < 2:
            _declencheur(
                "comparabilite",
                True,
                "front de comparaison insuffisant : "
                f"{len(comparables)} configuration(s) comparable(s), "
                "2 au minimum",
                "observations d'acquisition supplémentaires portées par "
                "des reçus immuables",
                "autoriser de nouveaux créneaux d'acquisition par décision "
                "propriétaire, puis produire leurs reçus",
            )
        else:
            _declencheur(
                "comparabilite",
                False,
                f"{len(comparables)} configurations comparables partagent "
                "carte, paquet, harnais, règles d'incident et fenêtre de "
                "fraîcheur",
            )

    _declencheur(
        "preference",
        True,
        "aucune préférence propriétaire versionnée ne pondère les trois "
        "axes : tout ordre unique inter-axes reste impossible",
        "préférence propriétaire versionnée ordonnant les trois axes",
        "publier une préférence par décision propriétaire si un ordre "
        "unique inter-axes était voulu ; en son absence la comparaison "
        "reste strictement par axe",
    )

    bloquants = [
        entree["famille"]
        for entree in declencheurs
        if entree["declenche"] and entree["famille"] != "preference"
    ]
    return {
        "declencheurs": declencheurs,
        "bloquants": bloquants,
        "branche": "comparaison" if not bloquants else "abstention",
        "comparables": comparables,
    }


def _texte_abstention_axe(preuve_absente: str, action_humaine: str) -> str:
    """Formule unique de l'abstention d'un axe : jetons conservés
    littéraux, preuve absente et action humaine nommées, aucune valeur de
    remplacement."""
    return (
        f" Preuve absente : {preuve_absente}. Action humaine possible : "
        f"{action_humaine}. Aucune valeur de remplacement n'est créée."
    )


def _section_restitution_complete(
    etat_relatif: str,
    empreintes: dict[str, str],
    evaluation: dict,
    couverture: dict | None,
    table_metriques: tuple[str, dict, str] | None,
    cout_abonnement: tuple[str, dict, str] | None,
    verrou_charge: tuple[str, dict, str] | None,
) -> str:
    """Section de restitution complète V1-XS-14 : les cinq déclencheurs
    d'abstention évalués et publiés, puis la branche décidée par les
    preuves — abstention nommant preuve absente et action humaine, ou
    comparaison située strictement intra-panel abonnement sur les trois
    axes figés, sans ordre unique toutes dimensions ni total inter-axes."""
    rules = "docs/RULES.md"
    src_etat = _span_source(
        etat_relatif, empreintes[etat_relatif], "état V1 versionné"
    )
    src_rules = _span_source(rules, empreintes[rules], "U-018 et U-019")
    src_verrou = (
        _span_source(verrou_charge[0], verrou_charge[2], SECTION_VERROU)
        if verrou_charge is not None
        else ""
    )
    src_table = (
        _span_source(
            table_metriques[0], table_metriques[2], SECTION_TABLE_METRIQUES
        )
        if table_metriques is not None
        else ""
    )
    src_cout = (
        _span_source(
            cout_abonnement[0], cout_abonnement[2], SECTION_COUT_ABONNEMENT
        )
        if cout_abonnement is not None
        else ""
    )
    sources_par_famille = {
        "identite": src_etat + src_verrou + src_rules,
        "provenance": src_etat + src_table + src_cout + src_rules,
        "fraicheur": src_etat + src_verrou + src_rules,
        "comparabilite": src_etat + src_table + src_rules,
        "preference": src_etat + src_rules,
    }

    articles: list[str] = []
    for entree in evaluation["declencheurs"]:
        famille = entree["famille"]
        if entree["declenche"]:
            contenu = (
                f"<p>Déclencheur <code>{_echapper(famille)}</code> — "
                f"déclenché : {_echapper(entree['constat'])}. Preuve "
                f"absente : {_echapper(entree['preuve_absente'])}. Action "
                "humaine possible : "
                f"{_echapper(entree['action_humaine'])}. Aucune valeur de "
                "remplacement n'est créée.</p>"
            )
            jeton = "oui"
        else:
            contenu = (
                f"<p>Déclencheur <code>{_echapper(famille)}</code> — non "
                f"déclenché : {_echapper(entree['constat'])}.</p>"
            )
            jeton = "non"
        articles.append(
            _article(
                "deduction",
                contenu + sources_par_famille[famille],
                f' data-declencheur-abstention="{famille}"'
                f' data-declenche="{jeton}"'
                ' data-premisses="évaluation U-018 depuis les seuls'
                " artefacts versionnés cités en source de cet article,"
                ' sans nouvelle preuve"',
            )
        )

    if evaluation["branche"] == "abstention":
        bloquants = " ".join(
            f"<code>{_echapper(famille)}</code>"
            for famille in evaluation["bloquants"]
        )
        articles.append(
            _article(
                "deduction",
                "<p><code>ABSTENTION</code> — aucune comparaison "
                "intra-panel n'est rendue : déclencheur(s) bloquant(s) "
                f"actif(s) : {bloquants}. Chaque déclencheur actif nomme "
                "ci-dessus sa preuve absente et l'action humaine "
                "possible. Une absence de preuve n'est jamais transformée "
                "en résultat favorable et aucune valeur de remplacement "
                "n'est créée.</p>" + src_etat + src_rules,
                ' data-comparaison-situee="abstention"'
                ' data-premisses="déclencheurs U-018 évalués ci-dessus'
                ' depuis les seuls artefacts versionnés cités"',
            )
        )
    else:
        verrou = verrou_charge[1]
        dates = sorted(
            {entree["attestation"]["date"] for entree in verrou["panel"]}
        )
        dates_texte = " · ".join(
            f'<code data-comparaison-date="{_echapper(date)}">'
            f"{_echapper(date)}</code>"
            for date in dates
        )
        fraicheur = verrou["fraicheur"]
        comparables = evaluation["comparables"]
        absences = [
            ligne
            for ligne in table_metriques[1]["configurations"]
            if ligne["comparabilite"]["statut"] != "COMPARABLE"
        ]
        absences_textes = []
        for ligne in absences:
            comparabilite = ligne["comparabilite"]
            if comparabilite["statut"] == "SANS_OBSERVATION":
                detail = (
                    f"<code>{_echapper(comparabilite['statut'])}</code>, "
                    f"cause <code>{_echapper(comparabilite['cause'])}</code>"
                )
            else:
                detail = (
                    f"<code>{_echapper(comparabilite['statut'])}</code>, "
                    f"motif : {_echapper(comparabilite['motif'])}"
                )
            identifiant = _echapper(ligne["configuration_id"])
            absences_textes.append(
                f'<code data-comparaison-absence="{identifiant}">'
                f"{identifiant}</code> ({detail})"
            )
        canon = _canon_panel(couverture)
        articles.append(
            _article(
                "fait",
                "<p>Comparaison située strictement intra-panel "
                "abonnement — profil <code>abonnement</code> · date(s) "
                f"d'attestation du panel verrouillé : {dates_texte} · "
                "fenêtre de fraîcheur "
                f'<code data-comparaison-fenetre="{_echapper(fraicheur["regle"])}">'
                f"{_echapper(fraicheur['regle'])}</code> (effet "
                f"<code>{_echapper(fraicheur['effet'])}</code>) · panel "
                f"situé : {_echapper(canon)}. Absences hors du front de "
                f"comparaison, toutes publiées : "
                + " · ".join(absences_textes)
                + ". Cette comparaison ne rend aucun ordre unique toutes "
                "dimensions, aucun total inter-axes et aucune conclusion "
                "hors du profil abonnement.</p>"
                + src_verrou
                + src_etat
                + src_table,
                ' data-comparaison-situee="cadre"'
                ' data-comparaison-profil="abonnement"',
            )
        )

        taux_textes = " · ".join(
            f"<code>{_echapper(ligne['configuration_id'])}</code> "
            f"<code>{_echapper(ligne['taux'])}</code>"
            for ligne in comparables
        )
        # Une ligne comparable à dénominateur décidable nul porte un taux
        # littéralement NON_DEFINI : aucune fraction n'est construite et
        # l'axe s'abstient plutôt que d'inventer une valeur
        if any(
            ligne["denominateur_decidable"] == 0 for ligne in comparables
        ):
            articles.append(
                _article(
                    "deduction",
                    "<p>Axe <code>taux-acceptable</code> — taux de "
                    "sorties officiellement acceptables, maximisé — "
                    "<code>ABSTENTION</code> de cet axe : au moins une "
                    "configuration comparable porte un dénominateur "
                    "décidable nul et son taux reste littéralement "
                    "<code>NON_DEFINI</code>, hors de toute comparaison "
                    "numérique. Valeurs préenregistrées : "
                    f"{taux_textes}."
                    + _texte_abstention_axe(
                        "une décision officielle décidable pour chaque "
                        "configuration comparable",
                        "établir la décision officielle manquante par "
                        "validation automatique puis verdict humain, sous "
                        "le parcours officiel",
                    )
                    + "</p>"
                    + src_table
                    + src_rules,
                    f' data-axe-comparaison="{AXE_TAUX}"'
                    f' data-axe-abstention="{AXE_TAUX}"'
                    ' data-premisses="taux littéraux de la table de'
                    ' métriques versionnée citée en source, jetons'
                    ' conservés littéraux, aucune fraction construite sur'
                    ' un dénominateur nul"',
                )
            )
        else:
            fractions = {
                ligne["configuration_id"]: Fraction(
                    ligne["numerateur"], ligne["denominateur_decidable"]
                )
                for ligne in comparables
            }
            maximum = max(fractions.values())
            maximisantes = [
                identifiant
                for identifiant, fraction in fractions.items()
                if fraction == maximum
            ]
            if len(maximisantes) == 1:
                constat_taux = (
                    "La valeur maximale appartient à "
                    f"<code>{_echapper(maximisantes[0])}</code>, sur cet "
                    "axe seulement."
                )
            else:
                constat_taux = (
                    "Aucun maximum strict : les configurations "
                    "comparables portent des taux égaux ; aucune "
                    "configuration ne maximise cet axe."
                )
            articles.append(
                _article(
                    "deduction",
                    "<p>Axe <code>taux-acceptable</code> — taux de "
                    "sorties officiellement acceptables, maximisé. "
                    "Valeurs préenregistrées : "
                    f"{taux_textes}. {constat_taux}</p>"
                    + src_table
                    + src_rules,
                    f' data-axe-comparaison="{AXE_TAUX}"'
                    ' data-premisses="taux littéraux de la table de'
                    ' métriques versionnée citée en source, comparés sans'
                    ' arrondi ni pondération"',
                )
            )

        metrique_cout = cout_abonnement[1]["metrique"]["valeur"]
        articles.append(
            _article(
                "deduction",
                "<p>Axe <code>cout-par-sortie-acceptable</code> — coût "
                "d'abonnement par sortie officiellement acceptable, "
                "minimisé — <code>ABSTENTION</code> de cet axe : la "
                "métrique versionnée reste littéralement "
                f"<code>{_echapper(metrique_cout)}</code> et aucune "
                "conversion n'est admise."
                + _texte_abstention_axe(
                    "au moins une sortie officiellement acceptable, il en "
                    "existe zéro",
                    "autoriser de nouveaux créneaux d'acquisition par "
                    "décision propriétaire, puis établir l'acceptabilité "
                    "officielle par PASS automatique plus verdict humain "
                    "ACCEPTABLE",
                )
                + "</p>"
                + src_cout
                + src_rules,
                f' data-axe-comparaison="{AXE_COUT}"'
                f' data-axe-abstention="{AXE_COUT}"'
                ' data-premisses="métrique littérale du document de coût'
                " d'abonnement versionné cité en source, jetons conservés"
                ' littéraux"',
            )
        )

        latences = {
            ligne["configuration_id"]: ligne["latence_configuration"][
                "distribution_ms"
            ]
            for ligne in comparables
        }
        latences_textes = " · ".join(
            f"<code>{_echapper(identifiant)}</code> <code>"
            f"[{_echapper(', '.join(str(valeur) for valeur in distribution))}]"
            "</code> ms"
            for identifiant, distribution in latences.items()
        )
        if all(len(distribution) == 1 for distribution in latences.values()):
            minimum = min(
                distribution[0] for distribution in latences.values()
            )
            minimisantes = [
                identifiant
                for identifiant, distribution in latences.items()
                if distribution[0] == minimum
            ]
            if len(minimisantes) == 1:
                constat_latence = (
                    "La valeur minimale préenregistrée appartient à "
                    f"<code>{_echapper(minimisantes[0])}</code>, sur cet "
                    "axe seulement."
                )
            else:
                constat_latence = (
                    "Aucun minimum strict : les distributions "
                    "préenregistrées portent des valeurs égales ; aucune "
                    "configuration ne minimise cet axe."
                )
            contenu_latence = (
                "<p>Axe <code>latence-preenregistree</code> — latence "
                "préenregistrée, minimisée. Distributions complètes "
                f"préenregistrées : {latences_textes}. Chaque "
                "distribution porte une valeur unique : la comparaison "
                "ne calcule aucune statistique nouvelle. "
                f"{constat_latence}</p>"
            )
            attributs_latence = (
                f' data-axe-comparaison="{AXE_LATENCE}"'
                ' data-premisses="distributions complètes préenregistrées'
                ' de la table de métriques versionnée citée en source,'
                ' valeurs uniques comparées sans statistique nouvelle"'
            )
        else:
            contenu_latence = (
                "<p>Axe <code>latence-preenregistree</code> — latence "
                "préenregistrée, minimisée — <code>ABSTENTION</code> de "
                "cet axe : la règle <code>DISTRIBUTION_COMPLETE</code> ne "
                "préenregistre aucune statistique et au moins une "
                "distribution porte plusieurs valeurs. Distributions "
                f"complètes publiées : {latences_textes}."
                + _texte_abstention_axe(
                    "statistique de latence préenregistrée",
                    "adopter par décision propriétaire une statistique "
                    "préenregistrée de latence",
                )
                + "</p>"
            )
            attributs_latence = (
                f' data-axe-comparaison="{AXE_LATENCE}"'
                f' data-axe-abstention="{AXE_LATENCE}"'
                ' data-premisses="distributions complètes préenregistrées'
                ' de la table de métriques versionnée citée en source,'
                ' aucune statistique nouvelle calculée"'
            )
        articles.append(
            _article(
                "deduction",
                contenu_latence + src_table + src_rules,
                attributs_latence,
            )
        )

    return (
        '<section id="restitution-complete"'
        ' data-restitution-complete="section">'
        "<h2>Restitution complète V1 : abstention ou comparaison "
        "située</h2>"
        "<p>Section produite par <code>restituer</code> : chaque "
        "déclencheur d'abstention U-018 est évalué depuis les seules "
        "preuves versionnées, puis la branche est décidée par ces "
        "preuves — abstention nommant preuve absente et action humaine "
        "possible, ou comparaison strictement intra-panel abonnement sur "
        "trois axes figés. Aucun ordre unique toutes dimensions, aucun "
        "total inter-axes, aucune conclusion hors du profil abonnement. "
        "La lisibilité de cette section n'améliore aucune preuve.</p>"
        + "".join(articles)
        + "</section>"
    )


# ---------------------------------------------------------------------------
# Retours propriétaires V1-XS-14 (Issue #144) : explications de restitution.
# Chaque article répond à « qu'est-ce que cela veut dire, pourquoi, qu'est-ce
# qui bloque, que faut-il faire » depuis les seuls artefacts déjà chargés ;
# aucune preuve n'est modifiée et aucune valeur n'est inventée


def _charger_verrou_completion_restitution(
    racine: Path,
) -> tuple[str, dict, str] | None:
    """Verrou de complétion pour le rendu : (chemin relatif, données,
    SHA-256 du fichier), ou None lorsque l'artefact n'existe pas."""
    chemin = racine / CHEMIN_VERROU_COMPLETION
    if not os.path.lexists(chemin):
        return None
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurRestitution(
            f"verrou de complétion illisible : {erreur}"
        ) from erreur
    if (
        not isinstance(donnees, dict)
        or donnees.get("schema_version") != SCHEMA_VERROU_COMPLETION
    ):
        raise ErreurRestitution(
            "verrou de complétion de schéma inattendu : "
            f"{CHEMIN_VERROU_COMPLETION.as_posix()}"
        )
    return (
        CHEMIN_VERROU_COMPLETION.as_posix(),
        donnees,
        _sha256_fichier(chemin),
    )


def _configurations_completion(completion: dict) -> set[str]:
    return {
        entree["configuration_id"] for entree in completion["configurations"]
    }


def _completion_citee(
    completion: tuple[str, dict, str] | None,
    preflights: list[tuple[str, dict, str]],
    verrou_charge: tuple[str, dict, str] | None,
) -> bool:
    """Vrai si et seulement si un span citant le verrou de complétion est
    réellement rendu dans la page. Deux voies exactes : l'encadré des
    blocages, rendu dès que le verrou de campagne existe et qui cite
    toujours le verrou de complétion présent ; ou l'explication d'un
    préflight HOLD MISSING_OBSERVATION dont la configuration figure au
    verrou de complétion. Sans citation rendue, l'empreinte n'entre pas
    dans la provenance."""
    if completion is None:
        return False
    if verrou_charge is not None:
        return True
    identifiants = _configurations_completion(completion[1])
    return any(
        recu["verdict"] == "HOLD"
        and recu["cause"] == "MISSING_OBSERVATION"
        and recu["configuration_id"] in identifiants
        for _, recu, _ in preflights
    )


def _article_explication_preflight(
    relatif: str,
    sha_fichier: str,
    recu: dict,
    completion: tuple[str, dict, str] | None,
    empreintes: dict[str, str],
) -> str:
    """Explication d'un reçu de préflight : READY à identité servie
    INCONNU, ou HOLD MISSING_OBSERVATION. Vide pour tout autre reçu."""
    identifiant = recu["configuration_id"]
    span_preflight = _span_source(relatif, sha_fichier, SECTION_PREFLIGHT)
    span_rules = _span_source(
        "docs/RULES.md", empreintes["docs/RULES.md"], "U-018"
    )
    if (
        recu["verdict"] == "READY"
        and recu.get("identite_reellement_servie") == INCONNU
    ):
        contenu = (
            f"<p><strong>{_echapper(identifiant)}</strong> — que veut dire "
            "<code>identite_reellement_servie</code> <code>INCONNU</code> "
            "avec un verdict <code>READY</code> ? Le préflight est non "
            "génératif : ses sondes observent la route et le plan (client, "
            "authentification, catalogue, quota) sans envoyer une seule "
            "génération. Une route et un plan observables ne prouvent "
            "jamais quelle identité de modèle répondrait réellement à un "
            "appel.</p>"
            '<p class="blocage"><strong>Blocage exact : aucune observation '
            "générative attribuable ne prouve l'identité servie. Pour "
            "lever cette inconnue, il faudrait une autorité propriétaire "
            "d'acquisition explicite et bornée, puis une génération dont "
            "la trace attribuable prouve l'identité servie, ingérée comme "
            "preuve.</strong></p>" + span_preflight + span_rules
        )
        return _article(
            "fait",
            contenu,
            f' data-explication-preflight="{identifiant}"',
        )
    if (
        recu["verdict"] == "HOLD"
        and recu["cause"] == "MISSING_OBSERVATION"
    ):
        fragment_completion = ""
        span_completion = ""
        if completion is not None and identifiant in (
            _configurations_completion(completion[1])
        ):
            donnees_completion = completion[1]
            # Les significations viennent des champs aptitude_statique du
            # verrou lui-même, jamais de littéraux dupliqués dans le code
            aptitude = donnees_completion["aptitude_statique"]
            entree_completion = next(
                entree
                for entree in donnees_completion["configurations"]
                if entree["configuration_id"] == identifiant
            )
            jamais = " · ".join(
                f"<code>{_echapper(element)}</code>"
                for element in aptitude["ne_prouve_jamais"]
            )
            fragment_completion = (
                "<p>Le verrou de complétion versionné porte pour cette "
                "configuration le verdict <code>"
                f"{_echapper(entree_completion['verdict'])}</code> — "
                f"{_echapper(aptitude['signifie'])}. Cette aptitude "
                f"statique ne prouve jamais : {jamais} ; son autorité "
                "d'exécution reste <code>"
                f"{_echapper(donnees_completion['autorite_execution'])}"
                "</code> et ses créneaux exécutés <code>"
                f"{_echapper(donnees_completion['creneaux_executes'])}"
                "</code>.</p>"
            )
            span_completion = _span_source(
                completion[0], completion[2], SECTION_VERROU_COMPLETION
            )
        contenu = (
            f"<p><strong>{_echapper(identifiant)}</strong> — que veut dire "
            "<code>MISSING_OBSERVATION</code> ? La CLI n'est pas absente : "
            "le reçu ci-dessus prouve des observations locales (client, "
            "version, authentification ou catalogue selon les sondes). "
            "Mais une installation, une authentification locale ou une "
            "aide de syntaxe ne prouve aucun des faits distants exigés par "
            "<code>READY</code> : les clés fermées non observées, "
            "énumérées dans le champ fait du reçu ci-dessus, restent "
            "<code>INCONNU</code> sans commande générative, que le "
            "préflight s'interdit.</p>"
            + fragment_completion
            + '<p class="blocage"><strong>Blocage restant : les faits '
            "distants exigés par READY ne sont pas observés, et tout appel "
            "génératif qui les observerait exigerait une autorité "
            "propriétaire d'acquisition explicite et bornée.</strong></p>"
            + span_preflight
            + span_completion
            + span_rules
        )
        return _article(
            "fait",
            contenu,
            f' data-explication-preflight="{identifiant}"',
        )
    return ""


def _articles_autorite_completion(
    verrou_charge: tuple[str, dict, str],
    autorisation: tuple[str, dict, str],
    completion: tuple[str, dict, str] | None,
    recus_officiels: list[tuple[str, dict, str]],
) -> list[str]:
    """Articles de la section d'autorité : NOT_GRANTED historique
    distingué de D-V1-04, puis état des configurations sans autorité."""
    span_verrou = _span_source(
        verrou_charge[0], verrou_charge[2], SECTION_VERROU
    )
    span_autorisation = _span_source(
        autorisation[0], autorisation[2], SECTION_AUTORISATION_ACQUISITION
    )
    creneaux_autorises = " et ".join(
        f"<code>{_echapper(creneau['configuration_id'])}</code>"
        for creneau in autorisation[1]["portee"]["acquisitions"]
    )
    fragment_execution = (
        ", et des reçus immuables de ces exécutions sont restitués plus bas"
        if recus_officiels
        else ""
    )
    articles = [
        _article(
            "fait",
            "<p>Que veut dire <code>NOT_GRANTED</code> dans le verrou ? "
            "C'est l'état historique du verrou à sa matérialisation : un "
            "verrou ne s'auto-confère aucune autorité d'exécution. Ce "
            "jeton historique ne porte aucune interdiction actuelle sur "
            "les deux créneaux ensuite couverts par l'autorité séparée "
            f"D-V1-04 ({creneaux_autorises}), autorisés sans reprise ni "
            f"fallback{fragment_execution}.</p>"
            + span_verrou
            + span_autorisation,
            ' data-explication-autorite="not-granted-historique"',
        )
    ]
    if completion is not None:
        donnees_completion = completion[1]
        nombre_attente = len(donnees_completion["configurations"])
        span_completion = _span_source(
            completion[0], completion[2], SECTION_VERROU_COMPLETION
        )
        # Portée réellement dérivée : le recouvrement entre les créneaux
        # de D-V1-04 et les configurations du verrou de complétion est
        # calculé, jamais présumé ; aucune affirmation sur des artefacts
        # d'autorité non chargés ici
        identifiants_completion = _configurations_completion(
            donnees_completion
        )
        identifiants_autorises = {
            creneau["configuration_id"]
            for creneau in autorisation[1]["portee"]["acquisitions"]
        }
        recouvrement = sorted(
            identifiants_completion & identifiants_autorises
        )
        if recouvrement:
            phrase_portee = (
                " La portée de l'autorité D-V1-04 restituée ci-dessus "
                "nomme "
                + ", ".join(
                    f"<code>{_echapper(identifiant)}</code>"
                    for identifiant in recouvrement
                )
                + " parmi ces configurations."
            )
        else:
            phrase_portee = (
                " La portée de l'autorité D-V1-04 restituée ci-dessus — "
                "seule autorité d'acquisition chargée par cette section — "
                f"nomme exactement ses {len(identifiants_autorises)} "
                "créneaux : elle ne nomme aucune de ces configurations."
            )
        articles.append(
            _article(
                "fait",
                f"<p>Pour les {nombre_attente} configuration(s) du verrou "
                "de complétion : l'autorité d'exécution y reste <code>"
                f"{_echapper(donnees_completion['autorite_execution'])}"
                "</code> et zéro créneau exécuté (<code>creneaux_executes"
                f"</code> <code>"
                f"{_echapper(donnees_completion['creneaux_executes'])}"
                f"</code>).{phrase_portee}</p>"
                + span_completion
                + span_autorisation,
                ' data-explication-autorite="attente-completion"',
            )
        )
        if not recouvrement:
            articles.append(
                _article(
                    "deduction",
                    "<p>Déduction raisonnée : avant tout appel "
                    "fournisseur pour ces configurations en attente, une "
                    "nouvelle autorité propriétaire bornée — créneaux "
                    "nommés, plafond d'appels, sans reprise ni fallback, "
                    "sur le modèle de D-V1-04 — serait nécessaire. La "
                    "restitution ne crée aucune autorité.</p>"
                    + span_completion
                    + span_autorisation,
                    ' data-explication-autorite="autorite-necessaire"'
                    ' data-premisses="le verrou de complétion conserve'
                    " autorite_execution NOT_GRANTED et creneaux_executes"
                    " 0 ; la portée de D-V1-04 ne nomme aucune de ces"
                    " configurations ; toute acquisition exige une"
                    ' autorité propriétaire explicite et bornée"',
                )
            )
    return articles


def _explication_validation_applicable(registre: dict) -> bool:
    """Vrai si chaque échec du registre est exactement le motif expliqué :
    G-005 franchie, G-001 en cause, origine CANDIDATE_ERROR."""
    entrees_fail = [
        entree
        for entree in registre["entrees"]
        if entree["verdict"] is not None
        and entree["verdict"]["statut"] == "FAIL"
    ]
    if not entrees_fail:
        return False
    return all(
        entree["verdict"]["porte_en_cause"] == "G-001"
        and entree["verdict"]["origine"] == "CANDIDATE_ERROR"
        and dict(
            (nom, franchie) for nom, franchie in entree["verdict"]["portes"]
        ).get("G-005") is True
        for entree in entrees_fail
    )


def _charger_registre_verite_restitution(
    racine: Path, registre_validation: tuple[str, dict, str] | None
) -> str | None:
    """SHA-256 du registre de vérité, uniquement lorsque l'explication des
    échecs G-001 est applicable et que le fichier existe."""
    if registre_validation is None:
        return None
    if not _explication_validation_applicable(registre_validation[1]):
        return None
    chemin = racine / CHEMIN_REGISTRE_VERITE
    if not os.path.lexists(chemin):
        return None
    return _sha256_fichier(chemin)


def _article_explication_validation(
    relatif_registre: str,
    sha_registre: str,
    registre: dict,
    sha_verite: str,
) -> str:
    """Explication des échecs automatiques : portes franchies et porte en
    cause, sans rien déduire au-delà du registre et des reçus."""
    nombre_fail = registre["couverture"]["verdicts"]["FAIL"]
    contenu = (
        f"<p>Que veulent dire ces {nombre_fail} <code>FAIL</code> "
        "automatiques ? Chaque sortie candidate observée franchit d'abord "
        "la porte <code>G-005</code> — intégrité et provenance mécaniques "
        "du paquet : le dispositif de contrôle était sain — puis échoue à "
        "la porte <code>G-001</code> avec l'origine "
        "<code>CANDIDATE_ERROR</code> : l'échec est attribuable à la "
        "sortie candidate elle-même, jamais au harnais.</p>"
        "<p><code>G-001</code> contrôle l'enveloppe de la sortie : "
        "Markdown lisible, schéma des champs requis, valeurs des champs à "
        "vocabulaire fermé et sections requises présentes dans l'ordre. "
        "Le registre versionné et les reçus ne consignent rien de plus "
        "sur ces échecs ; aucune autre déduction n'en est tirée ici.</p>"
        + _span_source(
            relatif_registre, sha_registre, SECTION_REGISTRE_VALIDATION
        )
        + _span_source(
            CHEMIN_REGISTRE_VERITE, sha_verite, SECTION_REGISTRE_VERITE
        )
    )
    return _article(
        "fait", contenu, ' data-explication-validation="fail-g-001"'
    )


def _identite_complete(donnees: dict) -> bool:
    """Vrai si aucune valeur INCONNU ne subsiste dans l'identité déclarée
    d'une configuration : le critère « identités complètes » du parcours
    n'est jamais tenu pour acquis tant qu'un champ reste INCONNU."""

    def _contient_inconnu(valeur: object) -> bool:
        if isinstance(valeur, dict):
            return any(_contient_inconnu(v) for v in valeur.values())
        if isinstance(valeur, list):
            return any(_contient_inconnu(v) for v in valeur)
        return valeur == INCONNU

    return not _contient_inconnu(donnees)


def _articles_parcours(
    empreintes: dict[str, str],
    etat_relatif: str,
    configurations: list[tuple[str, dict]],
    qualification: tuple[str, dict, str] | None,
    verrou_charge: tuple[str, dict, str] | None,
    recus_officiels: list[tuple[str, dict, str]],
    registre_validation: tuple[str, dict, str] | None,
    artefacts_verdicts: dict | None,
    couverture_etat: dict | None,
) -> list[str]:
    """Les six capacités du parcours V1, chacune au statut dérivé des
    preuves versionnées présentes : realise, partiel, bloque, ou l'article
    planifié à venir historique lorsque aucune preuve n'existe."""
    span_verrou = (
        _span_source(verrou_charge[0], verrou_charge[2], SECTION_VERROU)
        if verrou_charge is not None
        else ""
    )
    articles: list[str] = []
    for rang, (nom, texte, chemin, section) in enumerate(
        ETAPES_FUTURES, start=1
    ):
        span_normatif = _span_source(chemin, empreintes[chemin], section)
        statut: str | None = None
        detail = ""
        spans_preuves = ""
        if nom == "panel-abonnement" and configurations:
            incompletes = [
                donnees["configuration_id"]
                for _, donnees in configurations
                if not _identite_complete(donnees)
            ]
            fragment_plans = ""
            if verrou_charge is not None:
                fragment_plans = (
                    f" et {len(verrou_charge[1]['panel'])} entrée(s) de "
                    "plan versionnée(s) sous l'autorité <code>"
                    + _echapper(
                        verrou_charge[1]["autorites"]["contrat_plans"]
                    )
                    + "</code>, chacune avec sa date de consultation et "
                    "sa classe MSW propre"
                )
            if incompletes:
                # Identités requises incomplètes : jamais RÉALISÉ tant
                # qu'un champ INCONNU subsiste dans une configuration
                statut = "partiel"
                detail = (
                    "matérialisé : le registre officiel versionné "
                    f"déclare {len(configurations)} configuration(s) "
                    "abonnement (produit, plan, quotas, resets, "
                    f"interface, harnais, intervention humaine)"
                    f"{fragment_plans}. Inconnu : les identités "
                    "requises restent incomplètes, "
                    f"{len(incompletes)} configuration(s) portent "
                    "encore des champs <code>INCONNU</code> hérités de "
                    "l'instantané déclaratif, jamais réécrits"
                )
            else:
                statut = "realise"
                detail = (
                    "le registre officiel versionné déclare "
                    f"{len(configurations)} configuration(s) abonnement "
                    "aux identités complètes, sans champ "
                    f"<code>INCONNU</code>{fragment_plans}"
                )
            spans_preuves = (
                "".join(
                    _span_source(
                        chemin_configuration,
                        empreintes[chemin_configuration],
                        SECTION_REGISTRE,
                    )
                    for chemin_configuration, _ in configurations
                )
                + span_verrou
            )
        elif (
            nom == "qualification-independante"
            and qualification is not None
            and qualification[1]["verdict"] == "PASS"
        ):
            statut = "realise"
            detail = (
                "le harnais V1 est qualifié par le rejeu des témoins "
                "approuvés du paquet (verdict <code>PASS</code>), "
                "indépendamment des profils API et auto-hébergé"
            )
            spans_preuves = _span_source(
                qualification[0], qualification[2], SECTION_QUALIFICATION
            )
        elif nom == "approbation-empreintes" and verrou_charge is not None:
            statut = "realise"
            detail = (
                "réalisée pour les objets effectivement verrouillés : "
                "panel, plans validés et engagements sont figés par "
                "empreintes sous les autorités citées par le verrou"
            )
            spans_preuves = span_verrou
        elif nom == "recus-immuables" and recus_officiels:
            # Dénominateur = les acquisitions elles-mêmes, jamais les
            # configurations du panel : le critère U-010 est « un reçu
            # immuable pour chaque acquisition »
            couvertes = sorted(
                {
                    enveloppe["payload"]["configuration"]["identifiant"]
                    for _, enveloppe, _ in recus_officiels
                }
            )
            total = len(configurations)
            nombre_acquisitions = len(recus_officiels)
            statut = "realise"
            liste_couvertes = ", ".join(
                f"<code>{_echapper(identifiant)}</code>"
                for identifiant in couvertes
            )
            detail = (
                "chaque acquisition officielle exécutée possède son reçu "
                "immuable, adressé par contenu et chaîné : "
                f"{nombre_acquisitions} acquisition(s) officielle(s), "
                f"{nombre_acquisitions} reçu(s). Cette couverture ne "
                f"concerne que {len(couvertes)} configuration(s) "
                f"({liste_couvertes}) sur {total} déclarées et ne "
                "complète pas le panel"
            )
            spans_preuves = "".join(
                _span_source(relatif, sha, SECTION_RECU_OFFICIEL)
                for relatif, _, sha in recus_officiels
            )
        elif (
            nom == "acceptabilite-officielle"
            and registre_validation is not None
        ):
            comptes = registre_validation[1]["couverture"]["verdicts"]
            span_registre = _span_source(
                registre_validation[0],
                registre_validation[2],
                SECTION_REGISTRE_VALIDATION,
            )
            span_gel = (
                _span_source(
                    artefacts_verdicts["gel"][0],
                    artefacts_verdicts["gel"][2],
                    SECTION_GEL_VERDICTS,
                )
                if artefacts_verdicts is not None
                else ""
            )
            if comptes["PASS"] == 0:
                statut = "bloque"
                detail = (
                    "bloquée sur le lot courant : zéro verdict automatique "
                    "<code>PASS</code>, donc aucun dossier de revue "
                    "humaine et aucune acceptabilité officielle possible "
                    "pour ce lot"
                )
            else:
                etats = (
                    artefacts_verdicts["revelation"][1]["etats_officiels"]
                    if artefacts_verdicts is not None
                    and artefacts_verdicts["revelation"] is not None
                    else []
                )
                if any(
                    entree["etat_officiel"] == "OFFICIALLY_ACCEPTABLE"
                    for entree in etats
                ):
                    statut = "realise"
                    detail = (
                        "au moins un état officiel "
                        "<code>OFFICIALLY_ACCEPTABLE</code> est établi par "
                        "la conjonction PASS automatique plus ACCEPTABLE "
                        "humain"
                    )
                else:
                    statut = "partiel"
                    detail = (
                        "des verdicts automatiques <code>PASS</code> "
                        "existent ; l'acceptabilité officielle exige "
                        "encore la revue humaine aveugle"
                    )
            spans_preuves = span_registre + span_gel
        elif (
            nom == "restitution-ou-abstention"
            and couverture_etat is not None
        ):
            statut = "realise"
            detail = (
                "réalisée pour l'état courant : les mesures versionnées "
                "sont restituées avec leurs dénominateurs et leurs "
                "manquants, et l'abstention correspondante est prononcée, "
                "<code>ABSTENTION</code> et limites préservées"
            )
            spans_preuves = _span_source(
                etat_relatif, empreintes[etat_relatif], SECTION_COUVERTURE_ETAT
            )
        if statut is None:
            articles.append(
                _article(
                    "planifie",
                    f"<p>Étape {rang} — {texte} <strong>à venir</strong></p>"
                    + span_normatif,
                    f' data-marqueur="a-venir" data-etape="{nom}"',
                )
            )
        else:
            articles.append(
                _article(
                    "fait",
                    f"<p>Étape {rang} — {texte} <strong>"
                    f"{LIBELLES_PARCOURS[statut]}</strong> — {detail}.</p>"
                    + span_normatif
                    + spans_preuves,
                    f' data-etape="{nom}"'
                    f' data-parcours-statut="{statut}"',
                )
            )
    return articles


def _section_blocages(
    empreintes: dict[str, str],
    verrou_charge: tuple[str, dict, str] | None,
    autorisation: tuple[str, dict, str] | None,
    completion: tuple[str, dict, str] | None,
    recus_officiels: list[tuple[str, dict, str]],
    registre_validation: tuple[str, dict, str] | None,
    artefacts_verdicts: dict | None,
) -> str:
    """Encadré prioritaire : faits historiques dépassés, inconnues encore
    réelles, autorité ou action exacte nécessaire. Rendu seulement quand
    le verrou de campagne existe ; chaque volet cite ses sources."""
    if verrou_charge is None:
        return ""
    verrou = verrou_charge[1]
    span_verrou = _span_source(
        verrou_charge[0], verrou_charge[2], SECTION_VERROU
    )
    relatif_sources_plans = verrou["sources_plans"]["chemin"]
    span_sources_plans = _span_source(
        relatif_sources_plans,
        verrou["sources_plans"]["sha256"],
        SECTION_SOURCES_PLANS,
    )
    dates_attestation = sorted(
        {entree["attestation"]["date"] for entree in verrou["panel"]}
    )
    date_attestation = ", ".join(
        f"<code>{_echapper(date)}</code>" for date in dates_attestation
    )
    fragment_autorisation = ""
    span_autorisation = ""
    if autorisation is not None:
        creneaux_autorises = " et ".join(
            f"<code>{_echapper(creneau['configuration_id'])}</code>"
            for creneau in autorisation[1]["portee"]["acquisitions"]
        )
        fragment_autorisation = (
            " ; l'autorité séparée D-V1-04 a ensuite autorisé exactement "
            f"deux créneaux ({creneaux_autorises}), sans reprise ni "
            "fallback"
            + (
                ", et leurs reçus immuables existent"
                if recus_officiels
                else ""
            )
        )
        span_autorisation = _span_source(
            autorisation[0],
            autorisation[2],
            SECTION_AUTORISATION_ACQUISITION,
        )
    article_historique = _article(
        "fait",
        "<p><strong>Faits historiques déjà résolus ou dépassés.</strong> "
        "Les nombreux <code>INCONNU</code> du panel officiel sont "
        "l'instantané déclaratif historique D-V1-01 du "
        f"{date_attestation}, conservé tel quel ; des sources de plans "
        "versionnées sous l'autorité <code>"
        + _echapper(verrou["autorites"]["contrat_plans"])
        + "</code> existent depuis, verrouillées avec leurs provenances : "
        "chaque entrée porte sa date de consultation et sa classe MSW "
        "propre, la date de publication pouvant rester "
        "<code>NON_DEFINI</code>. Le <code>NOT_GRANTED</code> du verrou "
        "est l'état historique du verrou, qui ne s'auto-confère aucune "
        "autorité"
        f"{fragment_autorisation}.</p>"
        + span_verrou
        + span_sources_plans
        + span_autorisation,
        ' data-blocage="historique"',
    )
    nombre_attente = len(
        [
            entree
            for entree in verrou["panel"]
            if entree["cause"] == "MISSING_OBSERVATION"
        ]
    )
    fragment_attente = ""
    if nombre_attente:
        fragment_attente = (
            f" {nombre_attente} configuration(s) restent en attente "
            "d'observation (<code>MISSING_OBSERVATION</code>) : leur "
            "disponibilité distante, leur quota et leur identité servie "
            "restent <code>INCONNU</code>."
        )
    fragment_pass = ""
    span_registre = ""
    if registre_validation is not None:
        comptes = registre_validation[1]["couverture"]["verdicts"]
        if comptes["PASS"] == 0:
            fragment_pass = (
                " Aucune sortie candidate <code>PASS</code> : "
                "l'acceptabilité officielle reste absente sur le lot "
                "courant."
            )
            span_registre = _span_source(
                registre_validation[0],
                registre_validation[2],
                SECTION_REGISTRE_VALIDATION,
            )
    span_completion = (
        _span_source(completion[0], completion[2], SECTION_VERROU_COMPLETION)
        if completion is not None
        else ""
    )
    article_inconnues = _article(
        "fait",
        "<p><strong>Inconnues encore réelles.</strong> L'identité "
        "réellement servie reste <code>INCONNU</code> pour chaque "
        "configuration du panel, y compris les routes <code>READY</code>"
        + (" et les acquisitions exécutées" if recus_officiels else "")
        + " : aucune observation générative attribuable ne l'a prouvée."
        + fragment_attente
        + fragment_pass
        + "</p>"
        + span_verrou
        + span_completion
        + span_registre,
        ' data-blocage="inconnues"',
    )
    article_actions = ""
    if (
        autorisation is not None
        and completion is not None
        and registre_validation is not None
        and registre_validation[1]["couverture"]["verdicts"]["PASS"] == 0
        and artefacts_verdicts is not None
    ):
        span_gel = _span_source(
            artefacts_verdicts["gel"][0],
            artefacts_verdicts["gel"][2],
            SECTION_GEL_VERDICTS,
        )
        article_actions = _article(
            "deduction",
            "<p><strong>Autorité ou action exacte nécessaire.</strong> "
            "1. Pour les configurations en attente : une nouvelle "
            "autorité propriétaire bornée — créneaux nommés, plafond "
            "d'appels, sans reprise ni fallback, sur le modèle de "
            "D-V1-04 — avant tout appel fournisseur. 2. Pour lever "
            "l'identité réellement servie : une observation générative "
            "autorisée et attribuable, ingérée comme preuve. 3. Pour "
            "l'acceptabilité officielle : une sortie automatique "
            "<code>PASS</code> dans un lot autorisé, puis la revue "
            "humaine aveugle. 4. Pour le relecteur humain, sur le lot "
            "courant : aucune action.</p>"
            + span_completion
            + span_registre
            + span_gel
            + span_autorisation,
            ' data-blocage="actions"'
            ' data-premisses="le verrou de complétion conserve'
            " autorite_execution NOT_GRANTED et creneaux_executes 0 ;"
            " le registre de validation ne contient aucun PASS ; le gel"
            " D-V1-06 constate un lot vide sans verdict requis ; la"
            ' portée de D-V1-04 nomme exactement deux créneaux"',
        )
    return (
        '<section id="blocages-reels" class="blocages">'
        "<h2>Blocages réels à lever</h2>"
        "<p>Lecture prioritaire : ce qui est déjà résolu ou dépassé, ce "
        "qui reste réellement inconnu, et l'autorité ou l'action exacte "
        "qui manque pour avancer. Chaque affirmation cite sa source ; "
        "rien ici n'améliore une preuve.</p>"
        + article_historique
        + article_inconnues
        + article_actions
        + "</section>"
    )


def _rendre_page(racine: Path) -> bytes:
    etat = _charger_etat(racine)
    repertoire = _repertoire_recus(racine, etat)
    _compter_recus(repertoire)
    # Tout fichier du répertoire doit être un reçu V1 valide et chaîné ; les
    # acquisitions officielles D-V1-04 sont restituées sans jamais changer la
    # conclusion ABSTENTION du panel, faute d'acceptabilité officielle.
    recus_locaux, recus_officiels = _partitionner_recus(racine, etat)
    configurations = _configurations_officielles(racine)
    _verifier_triplets_configuration(
        racine, recus_officiels, configurations
    )
    qualification = _charger_recu_qualification(racine)
    preflights = _charger_recus_preflight(racine)
    verrou_charge = _charger_verrou_restitution(racine)
    autorisation = _charger_autorisation_restitution(racine)
    registre_validation = _charger_registre_validation(racine)
    completion = _charger_verrou_completion_restitution(racine)
    sha_verite = _charger_registre_verite_restitution(
        racine, registre_validation
    )
    recuperation = _charger_verrou_recuperation(racine)
    autorisation_recuperation = _charger_autorisation_recuperation_restitution(
        racine
    )
    artefacts_dossiers = _charger_artefacts_dossiers(racine)
    if artefacts_dossiers is not None:
        _verifier_coherence_dossiers(
            racine, artefacts_dossiers, registre_validation, verrou_charge
        )
    artefacts_verdicts = _charger_artefacts_verdicts(racine)
    if artefacts_verdicts is not None:
        _verifier_coherence_verdicts(
            artefacts_verdicts,
            artefacts_dossiers,
            registre_validation,
            verrou_charge,
        )
    couverture_etat = etat.get("couverture")
    table_metriques = _charger_table_metriques(racine)
    cout_abonnement = _charger_cout_abonnement(racine)
    canon_panel = _canon_panel(couverture_etat)
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
    if _completion_citee(completion, preflights, verrou_charge):
        empreintes[completion[0]] = completion[2]
    else:
        completion = None
    if sha_verite is not None:
        empreintes[CHEMIN_REGISTRE_VERITE] = sha_verite
    if artefacts_dossiers is not None:
        for relatif, _, sha in artefacts_dossiers:
            empreintes[relatif] = sha
    if artefacts_verdicts is not None:
        for relatif, _, sha in _sources_verdicts(artefacts_verdicts):
            empreintes[relatif] = sha
    if recuperation is not None:
        empreintes[recuperation[0]] = recuperation[2]
    if autorisation_recuperation is not None:
        empreintes[autorisation_recuperation[0]] = autorisation_recuperation[2]
    if table_metriques is not None:
        empreintes[table_metriques[0]] = table_metriques[2]
        # Épingle figée du vocabulaire d'effort cité par la table : la
        # provenance est figée, sans lecture du fichier à l'exécution
        provenance_effort = table_metriques[1]["effort_humain"][
            "provenance_vocabulaire"
        ]
        empreintes[provenance_effort["chemin"]] = provenance_effort["sha256"]
    if cout_abonnement is not None:
        empreintes[cout_abonnement[0]] = cout_abonnement[2]
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

    # Retours propriétaires : encadré prioritaire des blocages réels,
    # rendu seulement quand le verrou de campagne existe
    encadre_blocages = _section_blocages(
        empreintes,
        verrou_charge,
        autorisation,
        completion,
        recus_officiels,
        registre_validation,
        artefacts_verdicts,
    )
    if encadre_blocages:
        sections.append(encadre_blocages)

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
        if canon_panel is not None:
            article_panel_courant = _article(
                "fait",
                f"<p><code id=\"jeton-panel\">{jeton_panel}</code> — le registre "
                "officiel versionné déclare ces configurations abonnement ; le "
                "registre de couverture publié porte "
                f"{couverture_etat['numerateur']} décision(s) disponible(s) "
                f"sur {couverture_etat['denominateur']} et aucune sortie "
                "officiellement acceptable.</p>"
                + spans_registre
                + src(etat_relatif, SECTION_COUVERTURE_ETAT),
            )
            article_conclusion = _article(
                "deduction",
                f"<p><code id=\"jeton-conclusion\">{jeton_conclusion}</code> — "
                "déduction raisonnée : "
                f"{jeton_panel} et {absence_acquisition} ; une absence de "
                "preuve n'est jamais transformée en résultat favorable, donc "
                "la seule conclusion dérivable est l'abstention. Aucune "
                "valeur de remplacement n'est créée.</p>"
                + src(rules, "U-018"),
                f' data-premisses="{jeton_panel} selon le registre de '
                f"couverture publié ; {premisse_recus} ; "
                'règle U-018 de docs/RULES.md"',
            )
        else:
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
        article_plans_valides = ""
        if verrou_charge is not None:
            # Comptages dérivés du verrou : classes MSW et dates de
            # publication NON_DEFINI ne sont jamais présumées uniformes
            panel_verrou = verrou_charge[1]["panel"]
            nombre_deductions = sum(
                1
                for entree in panel_verrou
                if entree["plan"]["classe_msw"] == CLASSE_PLAN_DEDUCTION
            )
            nombre_faits = sum(
                1
                for entree in panel_verrou
                if entree["plan"]["classe_msw"] == CLASSE_PLAN_FAIT
            )
            nombre_publications_non_definies = sum(
                1
                for entree in panel_verrou
                if entree["plan"]["date_publication"] == "NON_DEFINI"
            )
            contrat_plans = _echapper(
                verrou_charge[1]["autorites"]["contrat_plans"]
            )
            article_plans_valides = _article(
                "fait",
                "<p>Distinction des deux états : les <code>INCONNU</code> "
                "ci-dessus sont l'instantané historique D-V1-01 ; "
                "séparément, <code>sources-plans-v1.toml</code> porte "
                f"{len(panel_verrou)} entrée(s) de plan versionnée(s) "
                f"sous l'autorité <code>{contrat_plans}</code>, figées "
                "par le verrou de campagne et restituées entrée par "
                "entrée dans la section "
                '<a href="#verrou-campagne">Verrou de campagne '
                "abonnement</a>. Chaque entrée porte sa date de "
                "consultation et sa classe MSW propre : "
                f"{nombre_faits} <code>FAIT_ETABLI</code> et "
                f"{nombre_deductions} <code>DEDUCTION_RAISONNEE</code> ; "
                f"{nombre_publications_non_definies} entrée(s) portent "
                "une date de publication <code>NON_DEFINI</code>. Les "
                "valeurs historiques ne sont pas remplacées et rien du "
                "contenu déduit n'est promu en fait.</p>"
                + src(relatif_sources_plans, SECTION_SOURCES_PLANS)
                + src(verrou_charge[0], SECTION_VERROU),
                ' data-plans-valides="resume"',
            )
        sections.append(
            "<section id=\"panel-officiel\"><h2>Panel officiel déclaré</h2>"
            "<p>Chaque entrée reprend un fichier du registre officiel "
            "versionné : c'est l'instantané historique de l'attestation "
            f"D-V1-01 du {DATE_ATTESTATION_PANEL}, conservé tel quel. "
            "Chaque entrée est déclarée et non mesurée : tout champ non "
            "observé à cette date reste littéralement "
            "<code>INCONNU</code>, jamais réécrit, le modèle demandé est "
            "marqué REQUESTED, et aucune activité de compte, aucune "
            "authentification et aucune disponibilité n'en est déduite. "
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
            + article_plans_valides
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
                + _article_explication_preflight(
                    relatif, sha, recu, completion, empreintes
                )
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
            + (
                "".join(
                    _articles_autorite_completion(
                        verrou_charge,
                        autorisation,
                        completion,
                        recus_officiels,
                    )
                )
                if verrou_charge is not None
                else ""
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
            + (
                _article_explication_validation(
                    relatif_registre, sha_registre, registre, sha_verite
                )
                if sha_verite is not None
                else ""
            )
            + "</section>"
        )

    if artefacts_dossiers is not None:
        sections.append(
            _section_dossiers_revue(
                artefacts_dossiers[0],
                artefacts_dossiers[1],
                artefacts_dossiers[2],
                registre_validation,
            )
        )

    if artefacts_verdicts is not None:
        sections.append(
            _section_verdicts_humains(
                artefacts_verdicts, empreintes["docs/RULES.md"]
            )
        )

    if recuperation is not None:
        sections.append(
            "<section id=\"recuperation-harnais\"><h2>Récupération "
            "verrouillée des harnais</h2>"
            + "".join(
                _articles_recuperation(
                    recuperation[0],
                    recuperation[2],
                    recuperation[1],
                    autorisation_recuperation,
                )
            )
            + "</section>"
        )

    if couverture_etat is not None:
        # Le registre de couverture versionné est restitué tel quel,
        # jamais recalculé au rendu
        _valider_couverture_etat(couverture_etat)
        sections.append(
            _section_couverture_etat(
                etat_relatif, empreintes[etat_relatif], couverture_etat
            )
        )

    if table_metriques is not None:
        # La table de métriques versionnée est restituée telle quelle,
        # jamais recalculée au rendu
        sections.append(
            _section_table_metriques(
                table_metriques[0], table_metriques[2], table_metriques[1]
            )
        )

    if cout_abonnement is not None:
        # Le document de coût d'abonnement versionné est restitué tel
        # quel, jamais recalculé au rendu
        sections.append(
            _section_cout_abonnement(
                cout_abonnement[0], cout_abonnement[2], cout_abonnement[1]
            )
        )

    # Restitution complète V1-XS-14 : les déclencheurs d'abstention sont
    # évalués depuis les artefacts déjà chargés, jamais présumés ; la
    # comparaison située n'est rendue que si aucun déclencheur bloquant
    # n'est actif
    evaluation_complete = _evaluer_restitution_complete(
        racine,
        configurations,
        couverture_etat,
        table_metriques,
        cout_abonnement,
        verrou_charge,
    )
    sections.append(
        _section_restitution_complete(
            etat_relatif,
            empreintes,
            evaluation_complete,
            couverture_etat,
            table_metriques,
            cout_abonnement,
            verrou_charge,
        )
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
            "Les collectes restantes appartiennent aux étapes du parcours, "
            "décrites avec leurs sources et leur statut dans la section "
            '<a href="#etapes-futures">Parcours V1</a> de cette '
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
        _articles_parcours(
            empreintes,
            etat_relatif,
            configurations,
            qualification,
            verrou_charge,
            recus_officiels,
            registre_validation,
            artefacts_verdicts,
            couverture_etat,
        )
    )
    sections.append(
        "<section id=\"etapes-futures\"><h2>Parcours V1</h2>"
        "<p>Les six capacités du parcours V1, chacune avec son statut "
        "dérivé des preuves versionnées présentes : RÉALISÉ, PARTIEL, "
        "BLOQUÉ ou à venir. Aucun statut n'est déclaré sans source, et "
        "aucune capacité n'est annoncée non commencée quand des preuves "
        "existent.</p>" + lignes_etapes + "</section>"
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
                (
                    (artefacts_dossiers[0][0], SECTION_DOSSIERS_REVUE),
                    (artefacts_dossiers[1][0], SECTION_CONTROLE_FUITES),
                    (artefacts_dossiers[2][0], SECTION_ENGAGEMENT_ORDRE),
                )
                if artefacts_dossiers is not None
                else ()
            ),
            *(
                (
                    (artefacts_verdicts["gel"][0], SECTION_GEL_VERDICTS),
                    *(
                        (relatif, SECTION_RECU_VERDICT)
                        for relatif, _, _ in artefacts_verdicts["recus"]
                    ),
                    *(
                        (
                            (
                                artefacts_verdicts["revelation"][0],
                                SECTION_REVELATION,
                            ),
                        )
                        if artefacts_verdicts["revelation"] is not None
                        else ()
                    ),
                )
                if artefacts_verdicts is not None
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
            *(
                ((recuperation[0], SECTION_VERROU_RECUPERATION),)
                if recuperation is not None
                else ()
            ),
            *(
                ((cout_abonnement[0], SECTION_COUT_ABONNEMENT),)
                if cout_abonnement is not None
                else ()
            ),
            *(
                ((completion[0], SECTION_VERROU_COMPLETION),)
                if completion is not None
                else ()
            ),
            *(
                ((CHEMIN_REGISTRE_VERITE, SECTION_REGISTRE_VERITE),)
                if sha_verite is not None
                else ()
            ),
            (etat_relatif, "état V1 versionné"),
        )
    )
    if configurations:
        if canon_panel is not None:
            titre = (
                "Restitution humaine V1 — profil abonnement — "
                f"{canon_panel}"
            )
        else:
            titre = (
                "Restitution humaine V1 — profil abonnement — panel déclaré"
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
        "section.blocages{border:3px solid #8a1a1a;padding:0.4rem 1rem;"
        "background:#fbf3f3}\n"
        "section.blocages h2{font-size:1.35rem;border-bottom:none;"
        "color:#8a1a1a}\n"
        "p.blocage{font-size:1.1rem;font-weight:bold}\n"
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
    # Reçu de coût d'abonnement : dérivé strictement des sources
    # courantes ; un reçu existant est régénéré avant le rendu pour que
    # la page ne restitue jamais une citation de source périmée. Un
    # reçu absent n'est jamais créé ici : seule la sous-commande cout
    # le produit.
    chemin_cout = racine / CHEMIN_COUT_ABONNEMENT
    if os.path.lexists(chemin_cout) and stat.S_ISREG(
        os.lstat(chemin_cout).st_mode
    ):
        _ecrire_cout_abonnement(racine)
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
        octets_page = chemin_page.read_bytes()
        page = octets_page.decode("utf-8")
    except (OSError, UnicodeDecodeError) as erreur:
        print(f"ECHEC page illisible : {erreur}")
        return 1

    # Attendus recalculés depuis les entrées, indépendamment du rendu.
    etat = _charger_etat(racine)
    repertoire = _repertoire_recus(racine, etat)
    _compter_recus(repertoire)
    recus_locaux, recus_officiels = _partitionner_recus(racine, etat)
    configurations = _configurations_officielles(racine)
    _verifier_triplets_configuration(
        racine, recus_officiels, configurations
    )
    qualification = _charger_recu_qualification(racine)
    preflights = _charger_recus_preflight(racine)
    verrou_charge = _charger_verrou_restitution(racine)
    autorisation = _charger_autorisation_restitution(racine)
    registre_validation = _charger_registre_validation(racine)
    recuperation = _charger_verrou_recuperation(racine)
    autorisation_recuperation = _charger_autorisation_recuperation_restitution(
        racine
    )
    artefacts_dossiers = _charger_artefacts_dossiers(racine)
    if artefacts_dossiers is not None:
        _verifier_coherence_dossiers(
            racine, artefacts_dossiers, registre_validation, verrou_charge
        )
    artefacts_verdicts = _charger_artefacts_verdicts(racine)
    if artefacts_verdicts is not None:
        _verifier_coherence_verdicts(
            artefacts_verdicts,
            artefacts_dossiers,
            registre_validation,
            verrou_charge,
        )
    # Contrôle de fidélité uniquement : la couverture est redérivée depuis
    # le registre, les reçus et les verdicts, puis comparée à la source
    # publiée etat-v1.json, qui demeure l'unique source restituée
    couverture_rederivee = _calculer_couverture(
        configurations,
        recus_officiels,
        registre_validation,
        artefacts_verdicts,
        preflights,
    )
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
    completion = _charger_verrou_completion_restitution(racine)
    if _completion_citee(completion, preflights, verrou_charge):
        empreintes[completion[0]] = completion[2]
    else:
        completion = None
    sha_verite = _charger_registre_verite_restitution(
        racine, registre_validation
    )
    if sha_verite is not None:
        empreintes[CHEMIN_REGISTRE_VERITE] = sha_verite
    if artefacts_dossiers is not None:
        for relatif, _, sha in artefacts_dossiers:
            empreintes[relatif] = sha
    if artefacts_verdicts is not None:
        for relatif, _, sha in _sources_verdicts(artefacts_verdicts):
            empreintes[relatif] = sha
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
    if autorisation_recuperation is not None:
        empreintes[autorisation_recuperation[0]] = autorisation_recuperation[2]
    if recuperation is not None:
        empreintes[recuperation[0]] = recuperation[2]
        for attendu in _articles_recuperation(
            recuperation[0],
            recuperation[2],
            recuperation[1],
            autorisation_recuperation,
        ):
            if attendu not in page:
                echecs.append("entrée de récupération infidèle ou absente")
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
    nombre_recuperations = page.count(' data-recuperation-harnais="')
    attendu_recuperations = 0 if recuperation is None else len(
        _articles_recuperation(
            recuperation[0],
            recuperation[2],
            recuperation[1],
            autorisation_recuperation,
        )
    )
    if nombre_recuperations != attendu_recuperations:
        echecs.append(
            f"{attendu_recuperations} entrée(s) de récupération attendues "
            f"dans la page, {nombre_recuperations} trouvée(s)"
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

    if artefacts_dossiers is not None:
        attendu_section = _section_dossiers_revue(
            artefacts_dossiers[0],
            artefacts_dossiers[1],
            artefacts_dossiers[2],
            registre_validation,
        )
        if attendu_section not in page:
            echecs.append(
                "section de dossiers de revue aveugle infidèle ou absente"
            )
    nombre_sections_dossiers = page.count(' data-dossiers-revue="section"')
    attendu_sections_dossiers = 0 if artefacts_dossiers is None else 1
    if nombre_sections_dossiers != attendu_sections_dossiers:
        echecs.append(
            f"{attendu_sections_dossiers} section de dossiers de revue "
            f"attendue dans la page, {nombre_sections_dossiers} trouvée"
        )
    nombre_dossiers_revue = page.count(' data-dossier-revue="')
    attendu_dossiers_revue = (
        len(artefacts_dossiers[0][1]["dossiers"])
        if artefacts_dossiers is not None
        else 0
    )
    if nombre_dossiers_revue != attendu_dossiers_revue:
        echecs.append(
            f"{attendu_dossiers_revue} entrées de dossier de revue attendues "
            f"dans la page, {nombre_dossiers_revue} trouvées"
        )
    nombre_exclusions_revue = page.count(' data-exclusion-revue="')
    attendu_exclusions_revue = (
        len(_exclusions_revue(registre_validation[1]))
        if artefacts_dossiers is not None
        else 0
    )
    if nombre_exclusions_revue != attendu_exclusions_revue:
        echecs.append(
            f"{attendu_exclusions_revue} entrées d'exclusion de revue "
            f"attendues dans la page, {nombre_exclusions_revue} trouvées"
        )

    if artefacts_verdicts is not None:
        attendu_section_verdicts = _section_verdicts_humains(
            artefacts_verdicts, empreintes["docs/RULES.md"]
        )
        if attendu_section_verdicts not in page:
            echecs.append(
                "section des verdicts humains gelés infidèle ou absente"
            )
    nombre_sections_verdicts = page.count(' data-verdicts-humains="section"')
    attendu_sections_verdicts = 0 if artefacts_verdicts is None else 1
    if nombre_sections_verdicts != attendu_sections_verdicts:
        echecs.append(
            f"{attendu_sections_verdicts} section de verdicts humains "
            f"attendue dans la page, {nombre_sections_verdicts} trouvée"
        )
    nombre_verdicts_humains = page.count(' data-verdict-humain="')
    attendu_verdicts_humains = (
        len(artefacts_verdicts["recus"]) if artefacts_verdicts is not None else 0
    )
    if nombre_verdicts_humains != attendu_verdicts_humains:
        echecs.append(
            f"{attendu_verdicts_humains} entrées de verdict humain attendues "
            f"dans la page, {nombre_verdicts_humains} trouvées"
        )
    nombre_etats_officiels = page.count(' data-etat-officiel="')
    attendu_etats_officiels = (
        len(artefacts_verdicts["revelation"][1]["etats_officiels"])
        if artefacts_verdicts is not None
        and artefacts_verdicts["revelation"] is not None
        else 0
    )
    if nombre_etats_officiels != attendu_etats_officiels:
        echecs.append(
            f"{attendu_etats_officiels} entrées d'état officiel attendues "
            f"dans la page, {nombre_etats_officiels} trouvées"
        )
    nombre_revelations = page.count(' data-revelation="correspondance"')
    attendu_revelations = (
        1
        if artefacts_verdicts is not None
        and artefacts_verdicts["revelation"] is not None
        else 0
    )
    if nombre_revelations != attendu_revelations:
        echecs.append(
            f"{attendu_revelations} entrée de révélation attendue dans la "
            f"page, {nombre_revelations} trouvée"
        )

    couverture_etat = etat.get("couverture")
    if couverture_etat is not None:
        _valider_couverture_etat(couverture_etat)
        if couverture_etat != couverture_rederivee:
            echecs.append(
                "couverture stockée divergente de la redérivation "
                "indépendante : "
                f"{couverture_rederivee['fraction']} attendu, "
                f"{couverture_etat['fraction']} stocké dans "
                f"{CHEMIN_ETAT.as_posix()} — aucune réparation"
            )
        attendu_section_couverture = _section_couverture_etat(
            etat_relatif, empreintes[etat_relatif], couverture_etat
        )
        if attendu_section_couverture not in page:
            echecs.append("section de couverture V1 infidèle ou absente")
    nombre_sections_couverture = page.count(' data-couverture-v1="section"')
    attendu_sections_couverture = 0 if couverture_etat is None else 1
    if nombre_sections_couverture != attendu_sections_couverture:
        echecs.append(
            f"{attendu_sections_couverture} section de couverture V1 "
            f"attendue dans la page, {nombre_sections_couverture} trouvée"
        )
    nombre_creneaux_couverture = page.count(' data-couverture-creneau="')
    attendu_creneaux_couverture = (
        len(couverture_etat["creneaux"]) if couverture_etat is not None else 0
    )
    if nombre_creneaux_couverture != attendu_creneaux_couverture:
        echecs.append(
            f"{attendu_creneaux_couverture} créneaux de couverture attendus "
            f"dans la page, {nombre_creneaux_couverture} trouvés"
        )

    # Table de métriques V1-XS-12B : la table stockée est comparée à une
    # reconstruction indépendante depuis les sources (couverture reprise,
    # motifs de retrait, latence, effort), puis chaque fragment rendu est
    # contrôlé dans la page
    table_metriques = _charger_table_metriques(racine)
    attendu_lignes_metriques = 0
    if table_metriques is not None:
        relatif_table, table_stockee, sha_table = table_metriques
        empreintes[relatif_table] = sha_table
        # Épingle figée du vocabulaire d'effort cité par la table : la
        # provenance est figée, sans lecture du fichier à l'exécution
        provenance_effort = table_stockee["effort_humain"][
            "provenance_vocabulaire"
        ]
        empreintes[provenance_effort["chemin"]] = provenance_effort["sha256"]
        table_attendue = _construire_table_metriques(racine)
        attendu_lignes_metriques = len(table_attendue["configurations"])
        identifiants_stockes = [
            ligne["configuration_id"] for ligne in table_stockee["configurations"]
        ]
        identifiants_attendus = [
            ligne["configuration_id"] for ligne in table_attendue["configurations"]
        ]
        if identifiants_stockes != identifiants_attendus:
            echecs.append(
                "registre de configurations de la table de métriques "
                "infidèle : une configuration surnuméraire ou absente — "
                "aucune réparation"
            )
        if table_stockee["couverture_reprise"] != table_attendue[
            "couverture_reprise"
        ]:
            echecs.append(
                "couverture reprise divergente de la couverture source "
                f"{CHEMIN_ETAT.as_posix()} : "
                f"{table_attendue['couverture_reprise']['fraction']} "
                "attendu, "
                f"{table_stockee['couverture_reprise']['fraction']} "
                "stocké — aucune réparation"
            )
        lignes_stockees = {
            ligne["configuration_id"]: ligne
            for ligne in table_stockee["configurations"]
        }
        for ligne_attendue in table_attendue["configurations"]:
            identifiant = ligne_attendue["configuration_id"]
            ligne_stockee = lignes_stockees.get(identifiant)
            if (
                ligne_stockee is None
                or ligne_stockee["comparabilite"]
                != ligne_attendue["comparabilite"]
            ):
                echecs.append(
                    f"motif de retrait absent ou inexact : {identifiant}"
                )
            elif ligne_stockee != ligne_attendue:
                echecs.append(
                    f"ligne de métriques infidèle : {identifiant}"
                )
        if table_stockee["agregat"] != table_attendue["agregat"]:
            echecs.append("agrégat de la table de métriques infidèle")
        if table_stockee["effort_humain"] != table_attendue["effort_humain"]:
            echecs.append("effort humain de la table de métriques infidèle")
        attendu_section_metriques = _section_table_metriques(
            relatif_table, sha_table, table_stockee
        )
        if attendu_section_metriques not in page:
            echecs.append("section de la table de métriques infidèle ou absente")
    nombre_sections_metriques = page.count('<section id="metriques-v1">')
    attendu_sections_metriques = 0 if table_metriques is None else 1
    if nombre_sections_metriques != attendu_sections_metriques:
        echecs.append(
            f"{attendu_sections_metriques} section de table de métriques "
            f"attendue dans la page, {nombre_sections_metriques} trouvée"
        )
    nombre_lignes_metriques = page.count(' data-metriques-configuration="')
    if nombre_lignes_metriques != attendu_lignes_metriques:
        echecs.append(
            f"{attendu_lignes_metriques} lignes de métriques attendues "
            f"dans la page, {nombre_lignes_metriques} trouvées"
        )

    # Document de coût d'abonnement V1-XS-13 : le document stocké est
    # comparé à une reconstruction indépendante depuis les sources
    # (table de métriques, sources de plans, registre officiel), puis la
    # section rendue est contrôlée dans la page — toute substitution de
    # NON_DEFINI est déjà refusée au chargement, jamais réparée
    cout_abonnement = _charger_cout_abonnement(racine)
    attendu_tarifs_cout = 0
    attendu_quotas_cout = 0
    if cout_abonnement is not None:
        relatif_cout, document_stocke, sha_cout = cout_abonnement
        empreintes[relatif_cout] = sha_cout
        for source in document_stocke["sources"]:
            chemin_source = source["chemin"]
            if chemin_source not in empreintes:
                empreintes[chemin_source] = _sha256_fichier(
                    racine / chemin_source
                )
        document_attendu = _construire_cout_abonnement(racine)
        attendu_tarifs_cout = len(
            document_attendu["tarifs_catalogue"]["configurations"]
        )
        attendu_quotas_cout = len(
            document_attendu["quotas_declares"]["configurations"]
        )
        identifiants_stockes = [
            tarif["configuration_id"]
            for tarif in document_stocke["tarifs_catalogue"]["configurations"]
        ]
        identifiants_attendus = [
            tarif["configuration_id"]
            for tarif in document_attendu["tarifs_catalogue"]["configurations"]
        ]
        if identifiants_stockes != identifiants_attendus:
            echecs.append(
                "registre de configurations du document de coût "
                "d'abonnement infidèle : une configuration surnuméraire "
                "ou absente — aucune réparation"
            )
        if (
            document_stocke["sorties_officiellement_acceptables"]
            != document_attendu["sorties_officiellement_acceptables"]
        ):
            echecs.append(
                "nombre de sorties officiellement acceptables du document "
                "de coût d'abonnement divergent de la table de métriques "
                f"{CHEMIN_TABLE_METRIQUES.as_posix()} — aucune réparation"
            )
        if (
            document_stocke["tarifs_catalogue"]
            != document_attendu["tarifs_catalogue"]
        ):
            echecs.append(
                "tarifs catalogue du document de coût d'abonnement "
                "infidèles — aucune réparation"
            )
        if (
            document_stocke["quotas_declares"]
            != document_attendu["quotas_declares"]
        ):
            echecs.append(
                "quotas déclarés du document de coût d'abonnement "
                "infidèles — aucune réparation"
            )
        if (
            document_stocke["decision"] != document_attendu["decision"]
            or document_stocke["metrique"] != document_attendu["metrique"]
            or document_stocke["sources"] != document_attendu["sources"]
        ):
            echecs.append(
                "décision, métrique ou sources du document de coût "
                "d'abonnement infidèles — aucune réparation"
            )
        attendu_section_cout = _section_cout_abonnement(
            relatif_cout, sha_cout, document_stocke
        )
        if attendu_section_cout not in page:
            echecs.append(
                "section du coût d'abonnement infidèle ou absente"
            )
    nombre_sections_cout = page.count('<section id="cout-abonnement-v1">')
    attendu_sections_cout = 0 if cout_abonnement is None else 1
    if nombre_sections_cout != attendu_sections_cout:
        echecs.append(
            f"{attendu_sections_cout} section de coût d'abonnement "
            f"attendue dans la page, {nombre_sections_cout} trouvée"
        )
    nombre_metriques_cout = page.count(' data-cout-metrique="non-defini"')
    if nombre_metriques_cout != attendu_sections_cout:
        echecs.append(
            f"{attendu_sections_cout} métrique de coût d'abonnement "
            f"NON_DEFINI attendue dans la page, {nombre_metriques_cout} "
            "trouvée"
        )
    nombre_tarifs_cout = page.count(' data-cout-tarif="')
    if nombre_tarifs_cout != attendu_tarifs_cout:
        echecs.append(
            f"{attendu_tarifs_cout} tarifs catalogue attendus dans la "
            f"page, {nombre_tarifs_cout} trouvés"
        )
    nombre_quotas_cout = page.count(' data-cout-quota="')
    if nombre_quotas_cout != attendu_quotas_cout:
        echecs.append(
            f"{attendu_quotas_cout} lignes de quotas déclarés attendues "
            f"dans la page, {nombre_quotas_cout} trouvées"
        )

    # Restitution complète V1-XS-14 : les déclencheurs et la branche sont
    # réévalués indépendamment depuis les artefacts rechargés ci-dessus,
    # puis la section rendue, les axes, la date, la fenêtre, les absences
    # et l'abstention monétaire sont contrôlés dans la page — un axe omis,
    # une date ou des absences omises et toute conversion de jeton
    # normatif sont des refus, jamais des réparations
    evaluation_complete = _evaluer_restitution_complete(
        racine,
        configurations,
        couverture_etat,
        table_metriques,
        cout_abonnement,
        verrou_charge,
    )
    attendu_section_complete = _section_restitution_complete(
        etat_relatif,
        empreintes,
        evaluation_complete,
        couverture_etat,
        table_metriques,
        cout_abonnement,
        verrou_charge,
    )
    if attendu_section_complete not in page:
        echecs.append(
            "section de restitution complète infidèle ou absente"
        )
    nombre_sections_completes = page.count(
        ' data-restitution-complete="section"'
    )
    if nombre_sections_completes != 1:
        echecs.append(
            "1 section de restitution complète attendue dans la page, "
            f"{nombre_sections_completes} trouvée"
        )
    nombre_declencheurs = page.count(' data-declencheur-abstention="')
    if nombre_declencheurs != len(FAMILLES_DECLENCHEURS):
        echecs.append(
            f"{len(FAMILLES_DECLENCHEURS)} déclencheurs d'abstention "
            f"attendus dans la page, {nombre_declencheurs} trouvés"
        )
    for famille in FAMILLES_DECLENCHEURS:
        if page.count(f' data-declencheur-abstention="{famille}"') != 1:
            echecs.append(
                f"déclencheur d'abstention omis ou dupliqué : {famille}"
            )
    if evaluation_complete["branche"] == "comparaison":
        for axe in AXES_COMPARAISON:
            if page.count(f' data-axe-comparaison="{axe}"') != 1:
                echecs.append(f"axe de comparaison omis ou dupliqué : {axe}")
        if page.count(' data-axe-comparaison="') != len(AXES_COMPARAISON):
            echecs.append(
                f"{len(AXES_COMPARAISON)} axes de comparaison attendus "
                "dans la page"
            )
        if page.count(' data-comparaison-situee="cadre"') != 1:
            echecs.append("cadre de comparaison située omis ou dupliqué")
        dates_attendues = sorted(
            {
                entree["attestation"]["date"]
                for entree in verrou_charge[1]["panel"]
            }
        )
        for date in dates_attendues:
            if f' data-comparaison-date="{date}"' not in page:
                echecs.append(f"date de comparaison omise : {date}")
        if page.count(' data-comparaison-fenetre="') != 1:
            echecs.append("fenêtre de fraîcheur de comparaison omise")
        absences_attendues = [
            ligne["configuration_id"]
            for ligne in table_metriques[1]["configurations"]
            if ligne["comparabilite"]["statut"] != "COMPARABLE"
        ]
        if page.count(' data-comparaison-absence="') != len(
            absences_attendues
        ):
            echecs.append(
                f"{len(absences_attendues)} absences de comparaison "
                "attendues dans la page — absences omises ou altérées"
            )
        for identifiant in absences_attendues:
            if f' data-comparaison-absence="{identifiant}"' not in page:
                echecs.append(f"absence de comparaison omise : {identifiant}")
        if (
            cout_abonnement[1]["metrique"]["valeur"] == "NON_DEFINI"
            and page.count(f' data-axe-abstention="{AXE_COUT}"') != 1
        ):
            echecs.append(
                "abstention de l'axe monétaire absente ou convertie "
                "alors que la métrique versionnée reste NON_DEFINI"
            )
        if (
            any(
                ligne["denominateur_decidable"] == 0
                for ligne in evaluation_complete["comparables"]
            )
            and page.count(f' data-axe-abstention="{AXE_TAUX}"') != 1
        ):
            echecs.append(
                "abstention de l'axe taux absente ou convertie alors "
                "qu'un taux comparable reste NON_DEFINI"
            )
        if page.count(' data-comparaison-situee="abstention"') != 0:
            echecs.append(
                "abstention de comparaison présente alors que les preuves "
                "autorisent la comparaison située"
            )
    else:
        if page.count(' data-comparaison-situee="abstention"') != 1:
            echecs.append(
                "1 abstention de comparaison attendue dans la page"
            )
        if page.count(' data-axe-comparaison="') != 0:
            echecs.append(
                "axe de comparaison présent alors que les preuves "
                "imposent l'abstention"
            )
        if page.count(' data-comparaison-situee="cadre"') != 0:
            echecs.append(
                "cadre de comparaison présent alors que les preuves "
                "imposent l'abstention"
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

    # Refus V1-XS-14 : aucun motif de classement général, de vainqueur
    # universel ni de score agrégé n'est toléré nulle part dans la page
    for motif in MOTIFS_RESTITUTION_INTERDITS:
        if motif in page_basse:
            echecs.append(f"motif interdit présent : {motif!r}")
    for motif in MOTIFS_INTER_PROFILS_INTERDITS:
        if motif in page_basse:
            echecs.append(
                f"comparaison inter-profils interdite présente : {motif!r}"
            )

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

    # Parcours V1 : les six étapes et leurs statuts sont redérivés depuis
    # les artefacts rechargés, jamais lus dans la page ; un statut rendu
    # divergent, une étape omise ou un « à venir » alors que des preuves
    # existent sont des refus, jamais des réparations
    noms_attendus = [nom for nom, _, _, _ in ETAPES_FUTURES]
    articles_parcours_attendus = _articles_parcours(
        empreintes,
        etat_relatif,
        configurations,
        qualification,
        verrou_charge,
        recus_officiels,
        registre_validation,
        artefacts_verdicts,
        couverture_etat,
    )
    for rang, attendu in enumerate(articles_parcours_attendus):
        if attendu not in page:
            echecs.append(
                "étape de parcours infidèle ou absente : "
                f"{noms_attendus[rang]}"
            )
    noms_rendus = re.findall(r' data-etape="([^"]+)"', page)
    if noms_rendus != noms_attendus:
        echecs.append(
            f"six étapes de parcours attendues {noms_attendus}, "
            f"trouvées {noms_rendus}"
        )
    attendu_a_venir = sum(
        1
        for article in articles_parcours_attendus
        if ' data-marqueur="a-venir"' in article
    )
    nombre_a_venir = page.count(' data-marqueur="a-venir"')
    if nombre_a_venir != attendu_a_venir:
        echecs.append(
            f"{attendu_a_venir} étape(s) de parcours à venir attendues "
            f"dans la page, {nombre_a_venir} trouvées — un rendu tout à "
            "venir est interdit quand des preuves existent"
        )

    # Contrôle final V1-XS-14 : la page publiée doit rester byte-identique
    # au rendu déterministe des sources courantes — toute injection
    # additive, même bien formée, est refusée, jamais réparée
    if octets_page != _rendre_page(racine):
        echecs.append(
            "page divergente du rendu déterministe courant — aucune "
            "réparation"
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
    "| acquerir --recuperation --configuration <id> "
    "| acquerir --completion --configuration <id> "
    "| preflight --configuration <id> "
    "| qualifier | verrouiller | valider | dossiers | geler | etat "
    "| metriques | cout | restituer | verifier-restitution "
    "| preparer-recuperation | preparer-completion"
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
    if arguments == ["dossiers"]:
        # racine_privee n'existe que pour les tests Python : la CLI de
        # production conserve la racine privée obligatoire exacte
        return dossiers(racine, racine_privee)
    if arguments == ["geler"]:
        # racine_privee n'existe que pour les tests Python : la CLI de
        # production conserve la racine privée obligatoire exacte
        return geler(racine, racine_privee)
    if arguments == ["etat"]:
        try:
            return etat(racine)
        except ErreurRestitution as erreur:
            print(f"ECHEC {erreur}")
            return 1
    if arguments == ["metriques"]:
        try:
            return metriques(racine)
        except ErreurRestitution as erreur:
            print(f"ECHEC {erreur}")
            return 1
    if arguments == ["cout"]:
        try:
            return cout(racine)
        except (ErreurRestitution, ErreurSourcesPlans) as erreur:
            print(f"ECHEC {erreur}")
            return 1
    if arguments == ["restituer"]:
        try:
            return restituer(racine)
        except (ErreurRestitution, ErreurSourcesPlans) as erreur:
            print(f"ECHEC {erreur}")
            return 1
    if arguments == ["verifier-restitution"]:
        try:
            return verifier_restitution(racine)
        except (ErreurRestitution, ErreurSourcesPlans) as erreur:
            print(f"ECHEC {erreur}")
            return 1
    if arguments == ["preparer-recuperation"]:
        return preparer_recuperation(racine)
    if arguments == ["preparer-completion"]:
        return preparer_completion(racine)
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
        # Trois formes figées : locale de démonstration, officielle D-V1-04,
        # récupération V1-R2 sous l'autorité additive D-V1-05
        if len(arguments) != 4 or arguments[2] != "--configuration":
            print(_USAGE)
            return 2
        if arguments[1] == "--local":
            return acquerir_local(racine, arguments[3])
        if arguments[1] == "--officiel":
            # racine_privee n'existe que pour les tests Python : la CLI de
            # production conserve la racine privée obligatoire exacte
            return acquerir_officiel(racine, arguments[3], racine_privee)
        if arguments[1] == "--recuperation":
            # racine_privee n'existe que pour les tests Python : la CLI de
            # production conserve la racine privée obligatoire exacte
            return acquerir_recuperation(racine, arguments[3], racine_privee)
        if arguments[1] == "--completion":
            # Garde pure V1-R4 : AUTORITE_ABSENTE avant toute résolution
            return acquerir_completion(arguments[3])
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
