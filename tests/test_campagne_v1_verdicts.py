# /// script
# requires-python = ">=3.12"
# ///
"""Gel des verdicts humains aveugles V1-XS-11 au seam public, sans appel distant.

Chaque test passe par `principal(["geler"])` avec une racine de dépôt
temporaire et une racine privée temporaire : le verrou et son matériel privé
y sont matérialisés par `verrouiller`, les reçus d'acquisition sont des
enveloppes V1 valides construites par le test, le registre de verdicts est
produit par `valider` et les dossiers par `dossiers`. Les saisies de verdicts
sont des fixtures : aucun verdict humain réel n'est fabriqué. Aucun contenu
privé (sel, manifeste d'ordre) n'est jamais affiché ni publié avant un gel
complet valide.
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

from tests._helpers_v1 import retirer_couverture_publiee  # noqa: E402

_CAMPAGNE = Path("tasks/dev/pre-cadrage-entretien-client/campagne-v1")
_SOURCES_PAQUET = RACINE / "tasks/dev/pre-cadrage-entretien-client"
_FICHIERS_PAQUET = (
    "manifeste-paquet.json",
    "brief-proprietaire.md",
    "registre-verite.md",
    "stimulus.md",
    "temoins-qualification.md",
)
_FICHIERS_ENTREE = (
    M.CHEMIN_ETAT.as_posix(),
    M.CHEMIN_SOURCES_PLANS.as_posix(),
    "docs/PRD.md",
    "docs/ARD.md",
    "docs/RULES.md",
    "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
    "rapport-decision-m10-2-v1/rapport-interne.md",
)
_REPERTOIRES_ENTREE = (
    _CAMPAGNE / "registre-panel-v1",
    _CAMPAGNE / "preflights-v1",
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
) -> tuple[str, dict]:
    charge = {
        "carte": {"chemin": M.CHEMIN_CARTE, "sha256": "0" * 64},
        "configuration": {
            "identifiant": identifiant,
            "chemin": f"{M.REGISTRE_OFFICIEL.as_posix()}/{identifiant}.toml",
            "sha256": hashlib.sha256(
                (RACINE / M.REGISTRE_OFFICIEL / f"{identifiant}.toml")
                .read_bytes()
            ).hexdigest(),
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
        "latence_ms": 4273,
    }


class GelVerdictsHumainsTests(unittest.TestCase):
    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self._temporaire_prive = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire_prive.cleanup)
        self.racine = Path(self._temporaire.name)
        self.privee = Path(self._temporaire_prive.name)
        for nom in _FICHIERS_PAQUET:
            destination = self.racine / _SOURCES_PAQUET.relative_to(RACINE) / nom
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_SOURCES_PAQUET / nom, destination)
        validateur = self.racine / M.CHEMIN_VALIDATEUR
        validateur.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RACINE / M.CHEMIN_VALIDATEUR, validateur)
        for relatif in _FICHIERS_ENTREE:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        retirer_couverture_publiee(self.racine / M.CHEMIN_ETAT)
        for repertoire in _REPERTOIRES_ENTREE:
            shutil.copytree(RACINE / repertoire, self.racine / repertoire)
        self.recus = self.racine / _CAMPAGNE / "recus-v1"
        self.recus.mkdir(parents=True, exist_ok=True)
        self.stimulus_sha = hashlib.sha256(
            (self.racine / M.CHEMIN_STIMULUS).read_bytes()
        ).hexdigest()
        self.repertoire_verdicts = self.racine / _CAMPAGNE / "verdicts-humains-v1"
        self.repertoire_saisie = self.repertoire_verdicts / "saisie"
        self.repertoire_recus_verdicts = self.repertoire_verdicts / "recus"
        self.chemin_gel = self.repertoire_verdicts / "gel-verdicts.json"
        self.chemin_revelation = (
            self.repertoire_verdicts / "revelation-correspondance.json"
        )
        self.chemin_manifeste = (
            self.racine / _CAMPAGNE / "dossiers-revue-aveugle-v1"
            / "manifeste-dossiers.json"
        )
        # Verrou matérialisé dans le bac : matériel privé temporaire cohérent
        self.assertEqual(
            M.principal(
                ["verrouiller"], racine=self.racine, racine_privee=self.privee
            ),
            0,
        )

    def _deposer_recu(self, adresse: str, enveloppe: dict) -> Path:
        chemin = self.recus / f"{adresse}.json"
        chemin.write_text(
            json.dumps(enveloppe, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        return chemin

    def _valider(self) -> int:
        # Frontière système simulée à un CPython 3.12 concret, à l'identique
        # de la fixture de validation : le pin de production reste intact
        with (
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
            return M.principal(["valider"], racine=self.racine)

    def _deposer_et_valider(
        self, identifiant: str, stdout: str, predecesseur: str | None = None
    ) -> str:
        adresse, enveloppe = _enveloppe_recu(
            identifiant,
            _execution_observee(stdout),
            predecesseur,
            self.stimulus_sha,
        )
        self._deposer_recu(adresse, enveloppe)
        self.assertEqual(self._valider(), 0)
        return adresse

    def _dossiers(self) -> int:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = M.principal(
                ["dossiers"], racine=self.racine, racine_privee=self.privee
            )
        self.assertEqual(0, code, sortie.getvalue())
        return code

    def _geler(self) -> tuple[int, str]:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = M.principal(
                ["geler"], racine=self.racine, racine_privee=self.privee
            )
        return code, sortie.getvalue()

    def _preparer_lot_vide(self) -> None:
        # sortie non conforme → verdict automatique FAIL : lot éligible vide
        self._deposer_et_valider("zai-glm-5-3", "sortie non conforme\n")
        self._dossiers()

    def _preparer_lot_pass(self) -> list[dict]:
        # deux sorties PASS : les deux créneaux verrouillés deviennent
        # éligibles, le lot compte deux dossiers opaques
        adresse = self._deposer_et_valider("zai-glm-5-3", _sortie_acceptable())
        self._deposer_et_valider(
            "antigravity-gemini-3-7-flash",
            _sortie_acceptable(),
            predecesseur=adresse,
        )
        self._dossiers()
        manifeste = json.loads(self.chemin_manifeste.read_text(encoding="utf-8"))
        self.assertEqual(2, len(manifeste["dossiers"]))
        return manifeste["dossiers"]

    def _saisir(self, item: str, verdict: str, justification: str) -> Path:
        self.repertoire_saisie.mkdir(parents=True, exist_ok=True)
        chemin = self.repertoire_saisie / f"{item}.json"
        chemin.write_text(
            json.dumps(
                {
                    "schema_version": M.SCHEMA_SAISIE_VERDICT_HUMAIN,
                    "item": item,
                    "verdict": verdict,
                    "justification": justification,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return chemin

    def test_saisie_manquante_refusee_sans_gel_partiel_ni_revelation(self):
        dossiers = self._preparer_lot_pass()
        # une seule saisie sur deux verdicts requis
        self._saisir(
            dossiers[0]["item"], "ACCEPTABLE", "Utilisable tel quel."
        )

        code, sortie = self._geler()
        self.assertEqual(1, code)
        self.assertIn("verdict humain manquant", sortie)
        self.assertIn(dossiers[1]["item"], sortie)
        # aucun gel partiel : ni reçu, ni gel, ni révélation
        self.assertFalse(self.chemin_gel.exists())
        self.assertFalse(self.chemin_revelation.exists())
        self.assertFalse(self.repertoire_recus_verdicts.exists())

    def test_justification_vide_refusee_au_seam_public(self):
        dossiers = self._preparer_lot_pass()
        self._saisir(dossiers[0]["item"], "ACCEPTABLE", "   ")
        self._saisir(
            dossiers[1]["item"], "NOT_ACCEPTABLE", "Reconstruction requise."
        )

        code, sortie = self._geler()
        self.assertEqual(1, code)
        self.assertIn("justification manquante", sortie)
        self.assertIn(dossiers[0]["item"], sortie)
        self.assertFalse(self.chemin_gel.exists())
        self.assertFalse(self.repertoire_recus_verdicts.exists())
        self.assertFalse(self.chemin_revelation.exists())

    def test_verdict_hors_vocabulaire_refuse(self):
        dossiers = self._preparer_lot_pass()
        self._saisir(dossiers[0]["item"], "GOOD", "Utilisable tel quel.")
        self._saisir(
            dossiers[1]["item"], "ACCEPTABLE", "Utilisable tel quel."
        )

        code, sortie = self._geler()
        self.assertEqual(1, code)
        self.assertIn("verdict hors vocabulaire", sortie)
        self.assertIn(dossiers[0]["item"], sortie)
        self.assertIn("ACCEPTABLE", sortie)
        self.assertIn("NOT_ACCEPTABLE", sortie)
        self.assertIn("UNABLE_TO_JUDGE", sortie)
        self.assertFalse(self.chemin_gel.exists())
        self.assertFalse(self.repertoire_recus_verdicts.exists())

    def _geler_lot_complet(self) -> tuple[list[dict], dict, dict, dict]:
        """Gel complet de deux verdicts : ACCEPTABLE puis NOT_ACCEPTABLE."""
        dossiers = self._preparer_lot_pass()
        self._saisir(
            dossiers[0]["item"],
            "ACCEPTABLE",
            "Le pré-cadrage est utilisable tel quel pour cet item.",
        )
        self._saisir(
            dossiers[1]["item"],
            "NOT_ACCEPTABLE",
            "Une reconstruction matérielle est nécessaire pour cet item.",
        )
        code, sortie = self._geler()
        self.assertEqual(0, code, sortie)
        gel = json.loads(self.chemin_gel.read_text(encoding="utf-8"))
        revelation = json.loads(
            self.chemin_revelation.read_text(encoding="utf-8")
        )
        recus = {
            entree["item"]: json.loads(
                (self.racine / entree["chemin"]).read_text(encoding="utf-8")
            )
            for entree in gel["recus"]
        }
        return dossiers, gel, revelation, recus

    def test_gel_complet_ecrit_un_recu_immuable_aveugle_par_verdict(self):
        dossiers, gel, _, recus = self._geler_lot_complet()

        self.assertEqual(2, gel["verdicts_requis"])
        self.assertEqual(2, len(gel["recus"]))
        self.assertEqual("EFFECTUEE", gel["intervention_relecteur"])
        self.assertEqual(
            "AFTER_ALL_HUMAN_VERDICTS_FROZEN", gel["revelation"]
        )
        self.assertEqual("DISABLED", gel["juge_fantome"])
        verdicts_attendus = {
            dossiers[0]["item"]: "ACCEPTABLE",
            dossiers[1]["item"]: "NOT_ACCEPTABLE",
        }
        for entree_gel, entree_manifeste in zip(gel["recus"], dossiers):
            item = entree_manifeste["item"]
            self.assertEqual(item, entree_gel["item"])
            # l'empreinte du gel colle au reçu réellement écrit
            octets = (self.racine / entree_gel["chemin"]).read_bytes()
            self.assertEqual(
                hashlib.sha256(octets).hexdigest(), entree_gel["sha256"]
            )
            recu = recus[item]
            self.assertEqual(
                M.SCHEMA_RECU_VERDICT_HUMAIN, recu["schema_version"]
            )
            self.assertEqual(verdicts_attendus[item], recu["verdict"])
            self.assertTrue(recu["justification"].strip())
            # la justification est liée à la sortie : item opaque et
            # empreinte exacte du dossier revu
            self.assertEqual(item, recu["item"])
            self.assertEqual(
                entree_manifeste["sha256"], recu["dossier"]["sha256"]
            )
            self.assertEqual(
                entree_manifeste["fichier"], recu["dossier"]["fichier"]
            )
            self.assertEqual("ayoahha", recu["relecteur"])
            self.assertEqual("D-V1-06", recu["decision"]["id"])
            # reçu aveugle : aucune identité de configuration ni
            # d'acquisition avant révélation
            self.assertNotIn("zai-glm-5-3", octets.decode("utf-8"))
            self.assertNotIn("antigravity", octets.decode("utf-8"))
            self.assertNotIn("ACQ-V1", octets.decode("utf-8"))

    def test_revelation_strictement_posterieure_au_gel(self):
        _, gel, revelation, recus = self._geler_lot_complet()

        horodatages_recus = [recu["horodatage_utc"] for recu in recus.values()]
        # chronologie relative prouvée : chaque reçu précède ou égale le gel,
        # la révélation est strictement postérieure au gel
        for horodatage in horodatages_recus:
            self.assertLessEqual(horodatage, gel["horodatage_gel_utc"])
        self.assertGreater(
            revelation["horodatage_revelation_utc"],
            gel["horodatage_gel_utc"],
        )
        # la révélation se chaîne au gel réellement écrit, par empreinte
        self.assertEqual(
            hashlib.sha256(self.chemin_gel.read_bytes()).hexdigest(),
            revelation["gel"]["sha256"],
        )

    def test_revelation_correspondance_conforme_au_manifeste_prive(self):
        dossiers, _, revelation, _ = self._geler_lot_complet()

        self.assertEqual(
            M.SCHEMA_REVELATION_CORRESPONDANCE, revelation["schema_version"]
        )
        # l'engagement masqué du verrou est vérifié au moment de révéler
        self.assertEqual(
            "CONFORME", revelation["engagement_verifie"]["resultat"]
        )
        # la correspondance révélée est exactement le manifeste d'ordre
        # privé scellé au verrou (comparaison légitime : bac à sable de test)
        manifeste_prive = json.loads(
            (
                self.privee / M.RELATIF_MATERIEL_VERROU / M.NOM_MANIFESTE_ORDRE
            ).read_bytes()
        )
        attendu = sorted(
            (
                {
                    "item": entree["item"],
                    "position": entree["position"],
                    "acquisition_id": entree["acquisition_id"],
                }
                for entree in manifeste_prive
            ),
            key=lambda entree: entree["position"],
        )
        observe = [
            {
                "item": entree["item"],
                "position": entree["position"],
                "acquisition_id": entree["acquisition_id"],
            }
            for entree in revelation["correspondance"]
        ]
        self.assertEqual(attendu, observe)
        # chaque entrée révélée porte la configuration du créneau verrouillé
        verrou = json.loads(
            (self.racine / M.CHEMIN_VERROU).read_text(encoding="utf-8")
        )
        configurations = {
            creneau["acquisition_id"]: creneau["configuration_id"]
            for creneau in verrou["creneaux"]
        }
        for entree in revelation["correspondance"]:
            self.assertEqual(
                configurations[entree["acquisition_id"]],
                entree["configuration_id"],
            )

    def test_etats_officiels_par_conjonction_stricte(self):
        dossiers, _, revelation, recus = self._geler_lot_complet()

        correspondance = {
            entree["configuration_id"]: entree["item"]
            for entree in revelation["correspondance"]
        }
        etats = {
            entree["configuration_id"]: entree
            for entree in revelation["etats_officiels"]
        }
        self.assertEqual(2, len(revelation["etats_officiels"]))
        for configuration_id, entree in etats.items():
            item = correspondance[configuration_id]
            verdict_humain = recus[item]["verdict"]
            self.assertEqual("PASS", entree["verdict_automatique"])
            self.assertEqual(verdict_humain, entree["verdict_humain"])
            self.assertEqual(item, entree["item"])
            attendu = (
                "OFFICIALLY_ACCEPTABLE"
                if verdict_humain == "ACCEPTABLE"
                else "CANDIDATE_NOT_ACCEPTABLE"
            )
            self.assertEqual(attendu, entree["etat_officiel"])
        # les deux verdicts saisis couvrent les deux issues de conjonction
        self.assertEqual(
            {"OFFICIALLY_ACCEPTABLE", "CANDIDATE_NOT_ACCEPTABLE"},
            {e["etat_officiel"] for e in etats.values()},
        )

    def test_quatre_combinaisons_automatique_humain_couvertes(self):
        # PASS+UNABLE_TO_JUDGE et FAIL sans verdict humain ; avec
        # PASS+ACCEPTABLE et PASS+NOT_ACCEPTABLE du gel complet, les quatre
        # combinaisons passent par le seam public
        adresse = self._deposer_et_valider("zai-glm-5-3", _sortie_acceptable())
        adresse = self._deposer_et_valider(
            "antigravity-gemini-3-7-flash",
            _sortie_acceptable(),
            predecesseur=adresse,
        )
        self._deposer_et_valider(
            "claude-code-opus-5", "sortie non conforme\n", predecesseur=adresse
        )
        self._dossiers()
        dossiers = json.loads(
            self.chemin_manifeste.read_text(encoding="utf-8")
        )["dossiers"]
        self.assertEqual(2, len(dossiers))
        self._saisir(
            dossiers[0]["item"],
            "UNABLE_TO_JUDGE",
            "Le dossier ne permet pas de répondre pour cet item.",
        )
        self._saisir(
            dossiers[1]["item"],
            "ACCEPTABLE",
            "Le pré-cadrage est utilisable tel quel pour cet item.",
        )

        code, sortie = self._geler()
        self.assertEqual(0, code, sortie)
        revelation = json.loads(
            self.chemin_revelation.read_text(encoding="utf-8")
        )
        etats = {
            (e["verdict_automatique"], e["verdict_humain"]): e["etat_officiel"]
            for e in revelation["etats_officiels"]
        }
        # PASS+UNABLE_TO_JUDGE : preuve humaine indisponible, candidat non
        # dégradé ; FAIL sans verdict humain : candidate non acceptable
        self.assertEqual("UNABLE_TO_JUDGE", etats[("PASS", "UNABLE_TO_JUDGE")])
        self.assertEqual(
            "OFFICIALLY_ACCEPTABLE", etats[("PASS", "ACCEPTABLE")]
        )
        self.assertEqual("CANDIDATE_NOT_ACCEPTABLE", etats[("FAIL", None)])
        entree_fail = next(
            e
            for e in revelation["etats_officiels"]
            if e["verdict_automatique"] == "FAIL"
        )
        # une sortie FAIL n'entre jamais en revue : aucun item, aucun
        # verdict humain fantôme
        self.assertIsNone(entree_fail["item"])
        self.assertIsNone(entree_fail["verdict_humain"])
        self.assertEqual("claude-code-opus-5", entree_fail["configuration_id"])

    def test_harness_error_automatique_reste_harness_error_officiel(self):
        # un HARNESS_ERROR automatique est un défaut du dispositif : l'état
        # officiel reste HARNESS_ERROR, sans verdict humain et sans
        # pénalité de configuration
        adresse = self._deposer_et_valider("zai-glm-5-3", _sortie_acceptable())
        adresse = self._deposer_et_valider(
            "antigravity-gemini-3-7-flash",
            _sortie_acceptable(),
            predecesseur=adresse,
        )
        stdout_harnais = "sortie témoin d'erreur de harnais\n"
        adresse, enveloppe = _enveloppe_recu(
            "claude-code-opus-5",
            _execution_observee(stdout_harnais),
            adresse,
            self.stimulus_sha,
        )
        self._deposer_recu(adresse, enveloppe)
        # frontière système simulée à l'identique de la suite de
        # validation : la sortie candidate de ce seul reçu devient illisible
        # dans l'espace du validateur, verdict automatique HARNESS_ERROR
        lecture_originale = Path.read_bytes

        def lire(chemin: Path) -> bytes:
            octets = lecture_originale(chemin)
            if (
                chemin.name == "sortie-candidate.md"
                and octets == stdout_harnais.encode("utf-8")
            ):
                raise OSError("lecture de la sortie candidate impossible")
            return octets

        with mock.patch.object(
            Path, "read_bytes", autospec=True, side_effect=lire
        ):
            self.assertEqual(0, self._valider())
        registre = json.loads(
            (self.racine / M.CHEMIN_REGISTRE_VALIDATION).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            "HARNESS_ERROR", registre["entrees"][2]["verdict"]["statut"]
        )
        self._dossiers()
        dossiers = json.loads(
            self.chemin_manifeste.read_text(encoding="utf-8")
        )["dossiers"]
        self.assertEqual(2, len(dossiers))
        self._saisir(
            dossiers[0]["item"],
            "ACCEPTABLE",
            "Le pré-cadrage est utilisable tel quel pour cet item.",
        )
        self._saisir(
            dossiers[1]["item"],
            "ACCEPTABLE",
            "Le pré-cadrage est utilisable tel quel pour cet item.",
        )

        code, sortie = self._geler()
        self.assertEqual(0, code, sortie)
        revelation = json.loads(
            self.chemin_revelation.read_text(encoding="utf-8")
        )
        entree = next(
            e
            for e in revelation["etats_officiels"]
            if e["configuration_id"] == "claude-code-opus-5"
        )
        self.assertEqual("HARNESS_ERROR", entree["verdict_automatique"])
        self.assertEqual("HARNESS_ERROR", entree["etat_officiel"])
        # aucun verdict humain fantôme, aucun item de revue
        self.assertIsNone(entree["verdict_humain"])
        self.assertIsNone(entree["item"])
        # aucune pénalité de configuration
        self.assertNotEqual("CANDIDATE_NOT_ACCEPTABLE", entree["etat_officiel"])

    def test_verdict_gele_immuable_apres_revelation(self):
        dossiers, gel, _, _ = self._geler_lot_complet()
        item = dossiers[0]["item"]
        # la saisie change après gel et révélation : refus, reçu intact
        self._saisir(
            item, "NOT_ACCEPTABLE", "Changement d'avis après révélation."
        )
        chemin_recu = self.racine / gel["recus"][0]["chemin"]
        octets_avant = chemin_recu.read_bytes()

        code, sortie = self._geler()
        self.assertEqual(1, code)
        self.assertIn("immuable", sortie)
        self.assertEqual(octets_avant, chemin_recu.read_bytes())

    def test_recu_altere_apres_revelation_refuse(self):
        dossiers, gel, _, _ = self._geler_lot_complet()
        chemin_recu = self.racine / gel["recus"][0]["chemin"]
        recu = json.loads(chemin_recu.read_text(encoding="utf-8"))
        recu["verdict"] = "NOT_ACCEPTABLE"
        chemin_recu.write_text(
            json.dumps(recu, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        # la saisie d'origine reste en place : seule l'altération du reçu
        # gelé explique la divergence
        code, sortie = self._geler()
        self.assertEqual(1, code)
        self.assertIn("immuable", sortie)

    def test_geler_idempotent_sans_reecriture(self):
        self._geler_lot_complet()
        octets_gel = self.chemin_gel.read_bytes()
        octets_revelation = self.chemin_revelation.read_bytes()

        code, sortie = self._geler()
        self.assertEqual(0, code, sortie)
        # aucun artefact gelé n'est réécrit : octets identiques
        self.assertEqual(octets_gel, self.chemin_gel.read_bytes())
        self.assertEqual(
            octets_revelation, self.chemin_revelation.read_bytes()
        )

    def test_gel_lot_vide_idempotent_sans_reecriture(self):
        self._preparer_lot_vide()
        code, _ = self._geler()
        self.assertEqual(0, code)
        octets = self.chemin_gel.read_bytes()

        code, sortie = self._geler()
        self.assertEqual(0, code, sortie)
        # le gel du lot vide n'est jamais réécrit : octets identiques
        self.assertEqual(octets, self.chemin_gel.read_bytes())

    def test_gel_lot_vide_altere_refuse_sans_reecriture(self):
        self._preparer_lot_vide()
        code, _ = self._geler()
        self.assertEqual(0, code)
        gel = json.loads(self.chemin_gel.read_text(encoding="utf-8"))
        gel["intervention_relecteur"] = "EFFECTUEE"
        self.chemin_gel.write_text(
            json.dumps(gel, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        octets_alteres = self.chemin_gel.read_bytes()

        code, sortie = self._geler()
        self.assertEqual(1, code)
        self.assertIn("immuable", sortie)
        # aucune réparation ni réécriture silencieuse
        self.assertEqual(octets_alteres, self.chemin_gel.read_bytes())

    def test_restitution_lot_vide_aucune_intervention_relecteur(self):
        self._preparer_lot_vide()
        code, _ = self._geler()
        self.assertEqual(0, code)

        self.assertEqual(0, M.principal(["restituer"], racine=self.racine))
        page = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        self.assertIn('id="verdicts-humains"', page)
        # le lot vide déclare l'absence d'intervention, sans état officiel
        self.assertIn("aucune intervention du relecteur humain", page)
        self.assertNotIn("OFFICIALLY_ACCEPTABLE", page)
        # provenance D-V1-06 conservée avec l'URL du commentaire, affichée
        # sous la forme neutralisée de la page autonome (schéma sans '://')
        self.assertIn("D-V1-06", page)
        self.assertIn(
            "https&#58;//github.com/ayoahha/benchmark-lab-x/issues/111"
            "#issuecomment-5441950621",
            page,
        )
        self.assertEqual(
            0, M.principal(["verifier-restitution"], racine=self.racine)
        )

    def test_restitution_lot_gele_etats_officiels_et_identite(self):
        dossiers, _, revelation, recus = self._geler_lot_complet()

        self.assertEqual(0, M.principal(["restituer"], racine=self.racine))
        page = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        self.assertIn('id="verdicts-humains"', page)
        # identité du relecteur affichée après révélation réelle
        self.assertIn("ayoahha", page)
        # chaque verdict gelé et sa justification apparaissent
        for item, recu in recus.items():
            self.assertIn(item, page)
            self.assertIn(recu["justification"], page)
        # les états officiels révélés apparaissent, conjonction stricte
        self.assertIn("OFFICIALLY_ACCEPTABLE", page)
        self.assertIn("CANDIDATE_NOT_ACCEPTABLE", page)
        # la correspondance révélée relie items et configurations
        for entree in revelation["correspondance"]:
            self.assertIn(entree["configuration_id"], page)
        self.assertEqual(
            0, M.principal(["verifier-restitution"], racine=self.racine)
        )

    def test_restitution_refuse_revelation_orpheline(self):
        # une révélation présente sans gel complet est une divulgation
        # prématurée : la restitution la refuse, jamais ne la répare
        self._preparer_lot_pass()
        self.repertoire_verdicts.mkdir(parents=True, exist_ok=True)
        self.chemin_revelation.write_text("{}\n", encoding="utf-8")

        self.assertEqual(1, M.principal(["restituer"], racine=self.racine))
        self.assertEqual(
            1, M.principal(["verifier-restitution"], racine=self.racine)
        )

    def test_verifier_restitution_refuse_recu_altere_apres_gel(self):
        _, gel, _, _ = self._geler_lot_complet()
        self.assertEqual(0, M.principal(["restituer"], racine=self.racine))
        self.assertEqual(
            0, M.principal(["verifier-restitution"], racine=self.racine)
        )
        chemin_recu = self.racine / gel["recus"][0]["chemin"]
        recu = json.loads(chemin_recu.read_text(encoding="utf-8"))
        recu["verdict"] = "NOT_ACCEPTABLE"
        chemin_recu.write_text(
            json.dumps(recu, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        self.assertEqual(
            1, M.principal(["verifier-restitution"], racine=self.racine)
        )

    def test_lot_vide_rend_zero_et_declare_le_fait_sans_faux_verdict(self):
        self._preparer_lot_vide()

        code, sortie = self._geler()
        self.assertEqual(0, code, sortie)

        gel = json.loads(self.chemin_gel.read_text(encoding="utf-8"))
        self.assertEqual(M.SCHEMA_GEL_VERDICTS, gel["schema_version"])
        # zéro verdict requis, zéro reçu écrit, fait de lot vide exact
        self.assertEqual(0, gel["verdicts_requis"])
        self.assertEqual([], gel["recus"])
        self.assertEqual("aucune_sortie_pass", gel["lot_vide"]["cause"])
        self.assertEqual({"FAIL": 1}, gel["lot_vide"]["comptage_statuts"])
        # aucune fausse intervention humaine, aucune révélation d'identité
        self.assertEqual("AUCUNE", gel["intervention_relecteur"])
        self.assertEqual("NON_APPLICABLE_LOT_VIDE", gel["revelation"])
        self.assertFalse(self.chemin_revelation.exists())
        self.assertFalse(self.repertoire_recus_verdicts.exists())
        # provenance D-V1-06 conservée avec l'URL du commentaire propriétaire
        self.assertEqual("D-V1-06", gel["decision"]["id"])
        self.assertEqual("ayoahha", gel["decision"]["relecteur"])
        self.assertEqual(
            "https://github.com/ayoahha/benchmark-lab-x/issues/111"
            "#issuecomment-5441950621",
            gel["decision"]["url"],
        )
        # juge fantôme hérité DISABLED : aucun juge LLM n'intervient
        self.assertEqual("DISABLED", gel["juge_fantome"])
        # RG-07 : la sortie de la commande déclare l'état exact
        self.assertIn("lot éligible vide", sortie)
        self.assertIn("0 verdict", sortie)
        self.assertIn("aucune intervention", sortie)


if __name__ == "__main__":
    unittest.main()
