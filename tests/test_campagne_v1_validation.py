# /// script
# requires-python = ">=3.12"
# ///
"""Validation automatique V1-XS-09 au seam public, sans appel distant.

Chaque test passe par `principal(["valider"])` avec une racine de dépôt
temporaire : le paquet approuvé et le validateur qualifié y sont copiés
byte-identiques, et les reçus d'acquisition sont des enveloppes V1 valides
construites par le test. Les trois états PASS, FAIL et HARNESS_ERROR sont
couverts avec leurs jetons exacts, la porte en cause et l'origine ; un
quatrième test couvre l'acquisition sans sortie candidate, l'absence de
verdict candidat, la conservation de cause et l'exclusion du reçu local ;
un cinquième impose l'empreinte du paquet approuvé identique avant et après.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import campagne_v1 as M  # noqa: E402

_CAMPAGNE = Path("tasks/dev/pre-cadrage-entretien-client/campagne-v1")
_SOURCES_PAQUET = RACINE / "tasks/dev/pre-cadrage-entretien-client"
_FICHIERS_PAQUET = (
    "manifeste-paquet.json",
    "brief-proprietaire.md",
    "registre-verite.md",
    "stimulus.md",
    "temoins-qualification.md",
)


def _sortie_acceptable() -> str:
    temoins = (_SOURCES_PAQUET / "temoins-qualification.md").read_text(
        encoding="utf-8"
    )
    return temoins.split("```markdown\n", 1)[1].split("\n```", 1)[0] + "\n"


def _enveloppe_recu(
    identifiant: str,
    execution: dict,
    predecesseur: str | None,
    stimulus_sha: str,
    officiel: bool = True,
) -> tuple[str, dict]:
    registre = M.REGISTRE_OFFICIEL if officiel else M.CONFIGURATIONS_LOCALES
    charge = {
        "carte": {"chemin": M.CHEMIN_CARTE, "sha256": "0" * 64},
        "configuration": {
            "identifiant": identifiant,
            "chemin": f"{registre.as_posix()}/{identifiant}.toml",
            "sha256": "1" * 64,
        },
        "creneau": f"{identifiant}:{stimulus_sha}",
        "execution": execution,
        "interface_declaree": {
            "etat": "DECLARE",
            "champs": {"type": "cli", "version": "INCONNU"},
        },
        "measurement_profile": "subscription",
        "paquet": {
            "chemin": M.CHEMIN_PAQUET,
            "sha256": M.EMPREINTE_MANIFESTE_APPROUVEE,
        },
        "plan_declare": {"etat": "DECLARE", "champs": {"nom": "INCONNU"}},
        "predecesseur_adresse_contenu": predecesseur,
        "provenance_servie": "INCONNU",
        "quota_observe": "INCONNU",
        "requete": {
            "etat": "REQUESTED",
            "argv_resolu": ["double-harnais", "__PROMPT_FILE__"],
            "mode_stdin": "__PROMPT_FILE__",
            "espace_de_travail": "__ISOLATED_WORKSPACE__",
        },
        "stimulus": {"chemin": M.CHEMIN_STIMULUS, "sha256": stimulus_sha},
    }
    adresse = M.adresse_canonique(charge)
    return adresse, {
        "schema_version": M.SCHEMA_RECU,
        "content_address": {"algorithm": "SHA256", "sha256": adresse},
        "payload": charge,
    }


def _execution_observee(stdout: str) -> dict:
    return {
        "etat": "OBSERVED",
        "sortie": {"stdout": stdout, "stderr": ""},
        "code_sortie": 0,
        "latence_ms": 1,
    }


class ValidationAutomatiqueTests(unittest.TestCase):
    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        for nom in _FICHIERS_PAQUET:
            destination = self.racine / _SOURCES_PAQUET.relative_to(RACINE) / nom
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_SOURCES_PAQUET / nom, destination)
        validateur = self.racine / M.CHEMIN_VALIDATEUR
        validateur.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RACINE / M.CHEMIN_VALIDATEUR, validateur)
        etat = self.racine / M.CHEMIN_ETAT
        etat.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RACINE / M.CHEMIN_ETAT, etat)
        self.recus = self.racine / _CAMPAGNE / "recus-v1"
        self.recus.mkdir(parents=True, exist_ok=True)
        self.stimulus_sha = hashlib.sha256(
            (self.racine / M.CHEMIN_STIMULUS).read_bytes()
        ).hexdigest()
        self.registre = self.racine / M.CHEMIN_REGISTRE_VALIDATION

    def _deposer_recu(self, adresse: str, enveloppe: dict) -> Path:
        chemin = self.recus / f"{adresse}.json"
        chemin.write_text(
            json.dumps(enveloppe, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        return chemin

    def _valider(self) -> tuple[int, str]:
        # Frontière système simulée à un CPython 3.12 concret, à l'identique
        # de la fixture de qualification : le pin de production reste intact
        sortie = io.StringIO()
        with (
            contextlib.redirect_stdout(sortie),
            mock.patch.object(
                M.platform, "python_implementation", return_value="CPython"
            ),
            mock.patch.object(
                M.platform, "python_version", return_value="3.12.13"
            ),
            mock.patch.object(
                M.platform,
                "python_version_tuple",
                return_value=("3", "12", "13"),
            ),
        ):
            code = M.principal(["valider"], racine=self.racine)
        return code, sortie.getvalue()

    def _registre_charge(self) -> dict:
        registre = json.loads(self.registre.read_text(encoding="utf-8"))
        self.assertEqual(M.SCHEMA_REGISTRE_VALIDATION, registre["schema_version"])
        self.assertEqual(
            M.EMPREINTE_MANIFESTE_APPROUVEE, registre["paquet"]["sha256"]
        )
        self.assertEqual(
            M.EMPREINTE_VALIDATEUR_APPROUVEE, registre["validateur"]["sha256"]
        )
        self.assertEqual(list(M.PORTES_PAQUET), registre["portes"])
        return registre

    def test_sortie_candidate_pass(self):
        stdout = _sortie_acceptable()
        adresse, enveloppe = _enveloppe_recu(
            "candidate-pass",
            _execution_observee(stdout),
            None,
            self.stimulus_sha,
        )
        self._deposer_recu(adresse, enveloppe)

        code, sortie = self._valider()
        self.assertEqual(0, code, sortie)

        self.assertEqual(0, code)
        registre = self._registre_charge()
        self.assertEqual(1, len(registre["entrees"]))
        entree = registre["entrees"][0]
        self.assertEqual("PRESENTE", entree["sortie_candidate"])
        self.assertIsNone(entree["cause_recue"])
        verdict = entree["verdict"]
        self.assertEqual("PASS", verdict["statut"])
        self.assertIsNone(verdict["origine"])
        self.assertIsNone(verdict["porte_en_cause"])
        self.assertEqual(
            [
                ["G-005", True],
                ["G-001", True],
                ["G-002", True],
                ["G-003", True],
                ["G-004", True],
            ],
            verdict["portes"],
        )
        self.assertEqual(
            hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
            verdict["empreinte_candidate"],
        )
        self.assertEqual(
            {"PASS": 1, "FAIL": 0, "HARNESS_ERROR": 0},
            registre["couverture"]["verdicts"],
        )
        self.assertEqual(1, registre["couverture"]["sorties_candidates"])

    def test_sortie_candidate_fail_porte_et_origine(self):
        stdout = _sortie_acceptable().replace(
            "client_ready: false", "client_ready: true", 1
        )
        adresse, enveloppe = _enveloppe_recu(
            "candidate-fail",
            _execution_observee(stdout),
            None,
            self.stimulus_sha,
        )
        self._deposer_recu(adresse, enveloppe)

        code, sortie = self._valider()
        self.assertEqual(0, code, sortie)

        self.assertEqual(0, code)
        registre = self._registre_charge()
        verdict = registre["entrees"][0]["verdict"]
        self.assertEqual("FAIL", verdict["statut"])
        self.assertEqual("CANDIDATE_ERROR", verdict["origine"])
        self.assertEqual("G-002", verdict["porte_en_cause"])
        self.assertEqual(
            {"PASS": 0, "FAIL": 1, "HARNESS_ERROR": 0},
            registre["couverture"]["verdicts"],
        )

    def test_sortie_candidate_harness_error_designe_le_harnais(self):
        stdout = _sortie_acceptable()
        adresse, enveloppe = _enveloppe_recu(
            "candidate-harness",
            _execution_observee(stdout),
            None,
            self.stimulus_sha,
        )
        self._deposer_recu(adresse, enveloppe)
        lecture_originale = Path.read_bytes

        def lire(chemin: Path) -> bytes:
            if chemin.name == "sortie-candidate.md":
                raise OSError("lecture de la sortie candidate impossible")
            return lecture_originale(chemin)

        with mock.patch.object(Path, "read_bytes", autospec=True, side_effect=lire):
            code, sortie = self._valider()
        self.assertEqual(0, code, sortie)

        registre = self._registre_charge()
        verdict = registre["entrees"][0]["verdict"]
        self.assertEqual("HARNESS_ERROR", verdict["statut"])
        self.assertEqual("HARNESS_ERROR", verdict["origine"])
        self.assertEqual("G-005", verdict["porte_en_cause"])
        # L'empreinte candidate exacte est conservée malgré l'erreur de
        # lecture simulée : elle provient des octets UTF-8 exacts du reçu
        self.assertEqual(
            hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
            verdict["empreinte_candidate"],
        )
        self.assertEqual(
            {"PASS": 0, "FAIL": 0, "HARNESS_ERROR": 1},
            registre["couverture"]["verdicts"],
        )
        # Le registre écrit reste lisible par la restitution
        relatif, relu, sha = M._charger_registre_validation(self.racine)
        self.assertEqual(M.CHEMIN_REGISTRE_VALIDATION.as_posix(), relatif)
        self.assertEqual(registre, relu)
        self.assertEqual(
            hashlib.sha256(self.registre.read_bytes()).hexdigest(), sha
        )

    def test_acquisition_sans_sortie_candidate_sans_verdict(self):
        adresse_locale, enveloppe_locale = _enveloppe_recu(
            "local-system-wc",
            _execution_observee("    4273\n"),
            None,
            self.stimulus_sha,
            officiel=False,
        )
        adresse_harness, enveloppe_harness = _enveloppe_recu(
            "officiel-harness",
            {
                "etat": "INCIDENT",
                "incident": "HARNESS_ERROR",
                "fait": "code client 1 sans sortie candidate : erreur du "
                "harnais local, créneau consommé sans retry",
            },
            adresse_locale,
            self.stimulus_sha,
        )
        adresse_provider, enveloppe_provider = _enveloppe_recu(
            "officiel-provider",
            {
                "etat": "INCIDENT",
                "incident": "PROVIDER_FAILURE",
                "fait": "refus explicite du fournisseur, créneau consommé "
                "sans retry",
                "preuve_attribuable": "stderr du client : refus explicite "
                "du fournisseur",
            },
            adresse_harness,
            self.stimulus_sha,
        )
        chemins = [
            self._deposer_recu(adresse_locale, enveloppe_locale),
            self._deposer_recu(adresse_harness, enveloppe_harness),
            self._deposer_recu(adresse_provider, enveloppe_provider),
        ]
        empreintes_avant = {
            chemin.name: hashlib.sha256(chemin.read_bytes()).hexdigest()
            for chemin in chemins
        }

        code, sortie = self._valider()
        self.assertEqual(0, code, sortie)

        self.assertEqual(0, code)
        registre = self._registre_charge()
        # Le reçu local reste hors panel officiel et hors validation officielle
        self.assertEqual(2, len(registre["entrees"]))
        self.assertEqual(
            ["officiel-harness", "officiel-provider"],
            [entree["configuration_id"] for entree in registre["entrees"]],
        )
        causes = {}
        for entree in registre["entrees"]:
            self.assertEqual("ABSENTE", entree["sortie_candidate"])
            self.assertIsNone(entree["verdict"])
            causes[entree["configuration_id"]] = entree["cause_recue"]
        self.assertEqual(
            {"officiel-harness": "HARNESS_ERROR", "officiel-provider": "PROVIDER_FAILURE"},
            causes,
        )
        self.assertEqual(
            {"PASS": 0, "FAIL": 0, "HARNESS_ERROR": 0},
            registre["couverture"]["verdicts"],
        )
        self.assertEqual(0, registre["couverture"]["sorties_candidates"])
        self.assertEqual(2, registre["couverture"]["acquisitions_officielles"])
        # Les reçus restent byte-identiques : aucune cause n'est convertie
        for chemin in chemins:
            self.assertEqual(
                empreintes_avant[chemin.name],
                hashlib.sha256(chemin.read_bytes()).hexdigest(),
            )

    def test_empreintes_paquet_et_validateur_identiques_avant_apres(self):
        adresse, enveloppe = _enveloppe_recu(
            "candidate-pass",
            _execution_observee(_sortie_acceptable()),
            None,
            self.stimulus_sha,
        )
        self._deposer_recu(adresse, enveloppe)
        scelles = (M.CHEMIN_PAQUET, M.CHEMIN_VALIDATEUR)
        avant = {
            relatif: hashlib.sha256((self.racine / relatif).read_bytes()).hexdigest()
            for relatif in scelles
        }
        self.assertEqual(
            M.EMPREINTE_MANIFESTE_APPROUVEE, avant[M.CHEMIN_PAQUET]
        )
        self.assertEqual(
            M.EMPREINTE_VALIDATEUR_APPROUVEE, avant[M.CHEMIN_VALIDATEUR]
        )

        code, sortie = self._valider()
        self.assertEqual(0, code, sortie)

        self.assertEqual(0, code)
        for relatif in scelles:
            self.assertEqual(
                avant[relatif],
                hashlib.sha256((self.racine / relatif).read_bytes()).hexdigest(),
            )
        # Génération JSON canonique simple du registre
        texte = self.registre.read_text(encoding="utf-8")
        self.assertEqual(
            json.dumps(json.loads(texte), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            texte,
        )


if __name__ == "__main__":
    unittest.main()
