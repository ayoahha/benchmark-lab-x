# /// script
# requires-python = ">=3.12"
# ///
"""Contrôles du verrou de campagne abonnement V1-XS-07 au seam public.

Chaque test passe par `principal` avec une racine de dépôt temporaire et une
racine privée temporaire. Aucun collaborateur interne n'est simulé, aucun
fournisseur n'est exécuté, et aucun contenu privé (sel, manifeste d'ordre)
n'est jamais affiché : seuls chemins, types, modes, tailles et empreintes
sont vérifiés.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import campagne_v1 as M  # noqa: E402

from tests._helpers_v1 import retirer_couverture_publiee  # noqa: E402

_CAMPAGNE = Path("tasks/dev/pre-cadrage-entretien-client/campagne-v1")
_REPERTOIRES_ENTREE = (
    _CAMPAGNE / "registre-panel-v1",
    _CAMPAGNE / "preflights-v1",
)
_FICHIERS_ENTREE = tuple(chemin for chemin, _ in M.SOURCES_AUTORISEES) + (
    M.CHEMIN_ETAT.as_posix(),
    (_CAMPAGNE / "sources-plans-v1.toml").as_posix(),
)

_CRENEAUX_ATTENDUS = (
    "ACQ-V1-ANTIGRAVITY-GEMINI-3-7-FLASH-001",
    "ACQ-V1-ZAI-GLM-5-3-001",
)
# Méthode d'engagement masqué figée par le contrat de récupération V1-XS-07
_DOMAINE_ENGAGEMENT = b"benchmark-lab-x/campagne-v1/manifeste-ordre/v1\x00"
_METHODE_ENGAGEMENT = "HMAC_SHA256_KEY_SALT_DOMAIN_SEPARATED_V1"
_ELIGIBLES_ATTENDUS = ("antigravity-gemini-3-7-flash", "zai-glm-5-3")
_EXCLUES_ATTENDUES = (
    "claude-code-fable-5",
    "claude-code-opus-5",
    "codex-gpt-5-6-sol",
    "cursor-kimi-k3",
    "grok-build-grok-4-6",
)


def _mode(chemin: Path) -> str:
    return f"{stat.S_IMODE(os.lstat(chemin).st_mode):04o}"


class VerrouCampagneTests(unittest.TestCase):
    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self._temporaire_prive = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire_prive.cleanup)
        self.racine = Path(self._temporaire.name)
        self.privee = Path(self._temporaire_prive.name)
        for relatif in _FICHIERS_ENTREE:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        retirer_couverture_publiee(self.racine / M.CHEMIN_ETAT)
        for repertoire in _REPERTOIRES_ENTREE:
            shutil.copytree(RACINE / repertoire, self.racine / repertoire)
        self.chemin_verrou = self.racine / M.CHEMIN_VERROU
        self.materiel = self.privee / "v1-execution" / "xs-07" / "material"
        self.chemin_sel = self.materiel / "sel.bin"
        self.chemin_manifeste = self.materiel / "manifeste-ordre.json"

    def _verrouiller(self) -> int:
        return M.principal(
            ["verrouiller"], racine=self.racine, racine_privee=self.privee
        )

    def _verrou(self) -> dict:
        return json.loads(self.chemin_verrou.read_text(encoding="utf-8"))

    def test_materialise_et_verifie_en_une_invocation(self):
        self.assertEqual(self._verrouiller(), 0)
        self.assertTrue(self.chemin_verrou.is_file())
        self.assertTrue(self.chemin_sel.is_file())
        self.assertTrue(self.chemin_manifeste.is_file())

    def test_cardinalites_dispositions_et_creneaux_exacts(self):
        self.assertEqual(self._verrouiller(), 0)
        verrou = self._verrou()
        self.assertEqual(verrou["schema_version"], "campagne-v1-verrou-abonnement/v1")
        self.assertEqual(verrou["cardinalite_declaree"], 7)
        self.assertEqual(verrou["cardinalite_eligible"], 2)
        self.assertEqual(len(verrou["panel"]), 7)
        dispositions = {
            entree["configuration_id"]: entree["disposition"]
            for entree in verrou["panel"]
        }
        for identifiant in _ELIGIBLES_ATTENDUS:
            self.assertEqual(dispositions[identifiant], "ELIGIBLE")
        for identifiant in _EXCLUES_ATTENDUES:
            self.assertEqual(dispositions[identifiant], "EXCLUDED_WAITING")
        self.assertEqual(
            tuple(creneau["acquisition_id"] for creneau in verrou["creneaux"]),
            _CRENEAUX_ATTENDUS,
        )
        self.assertEqual(verrou["creneaux_par_configuration_eligible"], 1)
        self.assertEqual(verrou["reprises"], {"automatiques": 0, "manuelles": 0})
        self.assertEqual(verrou["fallbacks"], "NONE")
        self.assertEqual(
            verrou["autorite_execution"]["autorite_acquisition_d_v1_04"],
            "NOT_GRANTED",
        )
        self.assertEqual(verrou["fraicheur"]["regle"], "EXACT_LOCK_EVENT_BASED_NO_TTL")
        self.assertEqual(
            verrou["fraicheur"]["evenements_materiels"],
            list(M.EVENEMENTS_FRAICHEUR_VERROU),
        )
        self.assertEqual(
            verrou["fraicheur"]["effet"], "HOLD_STOP_NO_CROSS_EVENT_COMPARISON"
        )

    def test_exclusions_hold_avec_cause_missing_observation(self):
        self.assertEqual(self._verrouiller(), 0)
        entrees = {
            entree["configuration_id"]: entree for entree in self._verrou()["panel"]
        }
        for identifiant in _EXCLUES_ATTENDUES:
            self.assertEqual(entrees[identifiant]["verdict"], "HOLD")
            self.assertEqual(entrees[identifiant]["cause"], "MISSING_OBSERVATION")
        for identifiant in _ELIGIBLES_ATTENDUS:
            self.assertEqual(entrees[identifiant]["verdict"], "READY")
            self.assertIsNone(entrees[identifiant]["cause"])

    def test_sel_32_octets_modes_et_engagements_publics_exacts(self):
        self.assertEqual(self._verrouiller(), 0)
        self.assertEqual(_mode(self.materiel), "0700")
        self.assertEqual(_mode(self.chemin_sel), "0600")
        self.assertEqual(_mode(self.chemin_manifeste), "0600")
        self.assertEqual(os.lstat(self.chemin_sel).st_size, 32)
        self.assertEqual(
            sorted(entree.name for entree in self.materiel.iterdir()),
            ["manifeste-ordre.json", "sel.bin"],
        )
        engagements = {
            engagement["kind"]: engagement
            for engagement in self._verrou()["engagements_prives"]
        }
        self.assertEqual(sorted(engagements), ["manifeste-ordre", "sel"])
        self.assertEqual(engagements["sel"]["mode"], "0600")
        self.assertEqual(engagements["sel"]["size"], 32)
        self.assertEqual(
            engagements["sel"]["sha256"], M._sha256_fichier(self.chemin_sel)
        )
        self.assertEqual(engagements["manifeste-ordre"]["mode"], "0600")
        self.assertEqual(
            engagements["manifeste-ordre"]["size"],
            os.lstat(self.chemin_manifeste).st_size,
        )

    def test_verrou_public_sans_contenu_ni_chemin_prives(self):
        self.assertEqual(self._verrouiller(), 0)
        texte = self.chemin_verrou.read_text(encoding="utf-8")
        self.assertNotIn(str(self.privee), texte)
        self.assertNotIn("sel.bin", texte)
        self.assertNotIn("manifeste-ordre.json", texte)
        self.assertNotIn("material", texte)
        verrou = json.loads(texte)
        # l'ordre reste aveugle : aucun objet public ne lie item et créneau
        engagement_ordre = verrou["engagement_ordre"]
        self.assertEqual(engagement_ordre["items"], ["ITEM-001", "ITEM-002"])
        self.assertEqual(engagement_ordre["positions"], [1, 2])
        self.assertNotIn("acquisition_id", engagement_ordre)
        for creneau in verrou["creneaux"]:
            self.assertEqual(
                sorted(creneau), ["acquisition_id", "configuration_id"]
            )
        for engagement in verrou["engagements_prives"]:
            if engagement["kind"] == "manifeste-ordre":
                self.assertEqual(
                    sorted(engagement),
                    ["commitment", "commitment_method", "kind", "mode", "size"],
                )
            else:
                self.assertEqual(
                    sorted(engagement), ["kind", "mode", "sha256", "size"]
                )

    def test_reexecution_idempotente_sans_changement_octets(self):
        self.assertEqual(self._verrouiller(), 0)
        octets_verrou = self.chemin_verrou.read_bytes()
        empreinte_sel = M._sha256_fichier(self.chemin_sel)
        empreinte_manifeste = M._sha256_fichier(self.chemin_manifeste)
        self.assertEqual(self._verrouiller(), 0)
        self.assertEqual(self.chemin_verrou.read_bytes(), octets_verrou)
        self.assertEqual(M._sha256_fichier(self.chemin_sel), empreinte_sel)
        self.assertEqual(
            M._sha256_fichier(self.chemin_manifeste), empreinte_manifeste
        )


    def test_engagement_manifeste_public_sans_sha256_direct(self):
        self.assertEqual(self._verrouiller(), 0)
        engagements = {
            engagement["kind"]: engagement
            for engagement in self._verrou()["engagements_prives"]
        }
        manifeste = engagements["manifeste-ordre"]
        self.assertEqual(
            sorted(manifeste),
            ["commitment", "commitment_method", "kind", "mode", "size"],
        )
        self.assertNotIn("sha256", manifeste)
        self.assertEqual(manifeste["commitment_method"], _METHODE_ENGAGEMENT)
        self.assertRegex(manifeste["commitment"], r"^[a-f0-9]{64}$")
        # le sel conserve son empreinte directe
        self.assertEqual(
            sorted(engagements["sel"]), ["kind", "mode", "sha256", "size"]
        )

    def test_commitment_non_reproductible_par_sha256_des_permutations(self):
        self.assertEqual(self._verrouiller(), 0)
        verrou = self._verrou()
        engagements = {
            engagement["kind"]: engagement
            for engagement in verrou["engagements_prives"]
        }
        commitment = engagements["manifeste-ordre"]["commitment"]
        identifiants = [
            creneau["acquisition_id"] for creneau in verrou["creneaux"]
        ]
        permutations = (identifiants, list(reversed(identifiants)))
        for ordre in permutations:
            candidat = M.octets_canoniques(
                [
                    {
                        "acquisition_id": acquisition_id,
                        "item": f"ITEM-{position:03d}",
                        "position": position,
                    }
                    for position, acquisition_id in enumerate(ordre, start=1)
                ]
            )
            self.assertNotEqual(
                hashlib.sha256(candidat).hexdigest(), commitment
            )
            self.assertNotEqual(
                hashlib.sha256(_DOMAINE_ENGAGEMENT + candidat).hexdigest(),
                commitment,
            )

    def test_commitment_egal_hmac_du_sel_et_du_manifeste_prives(self):
        self.assertEqual(self._verrouiller(), 0)
        engagements = {
            engagement["kind"]: engagement
            for engagement in self._verrou()["engagements_prives"]
        }
        attendu = hmac.new(
            self.chemin_sel.read_bytes(),
            _DOMAINE_ENGAGEMENT + self.chemin_manifeste.read_bytes(),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(engagements["manifeste-ordre"]["commitment"], attendu)

    def test_alteration_du_manifeste_prive_rend_deux_sans_reecriture(self):
        self.assertEqual(self._verrouiller(), 0)
        octets_verrou = self.chemin_verrou.read_bytes()
        altere = self.chemin_manifeste.read_bytes().replace(
            b"ITEM-001", b"ITEM-009"
        )
        self.chemin_manifeste.write_bytes(altere)
        self.assertEqual(self._verrouiller(), 2)
        self.assertEqual(self.chemin_verrou.read_bytes(), octets_verrou)
        self.assertEqual(self.chemin_manifeste.read_bytes(), altere)

    def test_refus_verrou_public_symbolique_par_cause_nommee(self):
        self.assertEqual(self._verrouiller(), 0)
        deplace = self.chemin_verrou.with_name("verrou-deplace.json")
        self.chemin_verrou.rename(deplace)
        self.chemin_verrou.symlink_to(deplace)
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            self.assertEqual(self._verrouiller(), 2)
        self.assertIn(
            "verrou public : fichier régulier non symbolique attendu",
            sortie.getvalue(),
        )

    def test_configuration_changee_apres_verrou_rend_deux_sans_reecriture(self):
        self.assertEqual(self._verrouiller(), 0)
        octets_verrou = self.chemin_verrou.read_bytes()
        chemin = (
            self.racine / _CAMPAGNE / "registre-panel-v1" / "zai-glm-5-3.toml"
        )
        contenu = chemin.read_text(encoding="utf-8")
        modifie = contenu.replace('type = "cli"', 'type = "ide"')
        self.assertNotEqual(modifie, contenu)
        chemin.write_text(modifie, encoding="utf-8")
        self.assertEqual(self._verrouiller(), 2)
        self.assertEqual(self.chemin_verrou.read_bytes(), octets_verrou)

    def test_preflight_change_apres_verrou_rend_deux_sans_reecriture(self):
        self.assertEqual(self._verrouiller(), 0)
        octets_verrou = self.chemin_verrou.read_bytes()
        chemin = (
            self.racine / _CAMPAGNE / "preflights-v1" / "zai-glm-5-3.json"
        )
        recu = json.loads(chemin.read_text(encoding="utf-8"))
        chemin.write_bytes(M.octets_canoniques(recu) + b"\n")
        self.assertEqual(self._verrouiller(), 2)
        self.assertEqual(self.chemin_verrou.read_bytes(), octets_verrou)

    def test_oserror_sur_artefact_du_verrou_devient_cause_nommee(self):
        self.assertEqual(self._verrouiller(), 0)
        self.addCleanup(os.chmod, self.chemin_verrou, 0o644)
        os.chmod(self.chemin_verrou, 0o000)
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            self.assertEqual(self._verrouiller(), 2)
        self.assertIn("ECHEC", sortie.getvalue())

    def test_refus_provenance_de_prix_absente_avant_toute_ecriture(self):
        chemin_sources = self.racine / _CAMPAGNE / "sources-plans-v1.toml"
        contenu = chemin_sources.read_text(encoding="utf-8")
        ampute = contenu.replace(
            'source_url = "https://docs.z.ai/devpack/transition"\n', ""
        )
        self.assertNotEqual(ampute, contenu)
        chemin_sources.write_text(ampute, encoding="utf-8")
        self.assertEqual(self._verrouiller(), 1)
        self.assertFalse(self.chemin_verrou.exists())
        self.assertFalse(self.materiel.exists())

    def test_source_de_plans_incomplete_rend_un(self):
        chemin_sources = self.racine / _CAMPAGNE / "sources-plans-v1.toml"
        contenu = chemin_sources.read_text(encoding="utf-8")
        tronque = contenu[: contenu.rindex("[[plan]]")]
        chemin_sources.write_text(tronque, encoding="utf-8")
        self.assertEqual(self._verrouiller(), 1)
        self.assertFalse(self.chemin_verrou.exists())
        self.assertFalse(self.materiel.exists())

    def test_changement_de_plan_apres_verrou_rend_deux_sans_ecrasement(self):
        self.assertEqual(self._verrouiller(), 0)
        octets_verrou = self.chemin_verrou.read_bytes()
        empreinte_sel = M._sha256_fichier(self.chemin_sel)
        empreinte_manifeste = M._sha256_fichier(self.chemin_manifeste)
        chemin_sources = self.racine / _CAMPAGNE / "sources-plans-v1.toml"
        contenu = chemin_sources.read_text(encoding="utf-8")
        chemin_sources.write_text(
            contenu.replace("prix_montant = 18", "prix_montant = 19"),
            encoding="utf-8",
        )
        self.assertEqual(self._verrouiller(), 2)
        self.assertEqual(self.chemin_verrou.read_bytes(), octets_verrou)
        self.assertEqual(M._sha256_fichier(self.chemin_sel), empreinte_sel)
        self.assertEqual(
            M._sha256_fichier(self.chemin_manifeste), empreinte_manifeste
        )

    def test_inclusion_forcee_non_ready_rend_deux_sans_reecriture(self):
        self.assertEqual(self._verrouiller(), 0)
        verrou = self._verrou()
        for entree in verrou["panel"]:
            if entree["configuration_id"] == "claude-code-fable-5":
                entree["disposition"] = "ELIGIBLE"
        octets_forces = M.octets_canoniques(verrou)
        self.chemin_verrou.write_bytes(octets_forces)
        self.assertEqual(self._verrouiller(), 2)
        self.assertEqual(self.chemin_verrou.read_bytes(), octets_forces)

    def test_refus_lien_symbolique_sur_objet_prive(self):
        self.assertEqual(self._verrouiller(), 0)
        deplace = self.materiel / "sel-deplace.bin"
        self.chemin_sel.rename(deplace)
        self.chemin_sel.symlink_to(deplace)
        self.assertEqual(self._verrouiller(), 2)

    def test_sortie_partielle_rend_deux_sans_reparation(self):
        self.assertEqual(self._verrouiller(), 0)
        octets_verrou = self.chemin_verrou.read_bytes()
        self.chemin_manifeste.unlink()
        self.assertEqual(self._verrouiller(), 2)
        self.assertFalse(self.chemin_manifeste.exists())
        self.assertEqual(self.chemin_verrou.read_bytes(), octets_verrou)

    def test_repertoire_prive_partiel_sans_verrou_rend_deux(self):
        self.materiel.mkdir(parents=True)
        self.assertEqual(self._verrouiller(), 2)
        self.assertFalse(self.chemin_verrou.exists())
        self.assertFalse(self.chemin_sel.exists())

    def test_racine_privee_de_production_figee_sans_option_cli(self):
        self.assertEqual(
            M.RACINE_PRIVEE_PRODUCTION,
            Path("/Users/ayo/Library/Application Support/Benchmark Lab-X/private"),
        )
        # toute option CLI est refusée avant la moindre écriture
        self.assertEqual(
            M.principal(
                ["verrouiller", "--racine-privee", str(self.privee)],
                racine=self.racine,
                racine_privee=self.privee,
            ),
            2,
        )
        self.assertFalse(self.chemin_verrou.exists())
        self.assertFalse(self.materiel.exists())


    def test_restitution_fidele_au_verrou_et_aux_sources_de_plans(self):
        self.assertEqual(self._verrouiller(), 0)
        self.assertEqual(M.principal(["restituer"], racine=self.racine), 0)
        self.assertEqual(
            M.principal(["verifier-restitution"], racine=self.racine), 0
        )
        page = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        verrou = self._verrou()
        for creneau in _CRENEAUX_ATTENDUS:
            self.assertIn(creneau, page)
        self.assertEqual(page.count(' data-verrou-panel="'), 7)
        self.assertIn("EXACT_LOCK_EVENT_BASED_NO_TTL", page)
        self.assertIn("EXCLUDED_WAITING", page)
        self.assertIn("MISSING_OBSERVATION", page)
        self.assertIn("NOT_GRANTED", page)
        self.assertIn("Codex Pro 20x", page)
        for engagement in verrou["engagements_prives"]:
            if engagement["kind"] == "manifeste-ordre":
                self.assertIn(engagement["commitment"], page)
            else:
                self.assertIn(engagement["sha256"], page)
        # aucune fuite privée : ni chemin de racine privée, ni nom d'objet privé
        self.assertNotIn(str(self.privee), page)
        self.assertNotIn("sel.bin", page)
        self.assertNotIn("manifeste-ordre.json", page)

    def test_restitution_infidele_au_verrou_refusee(self):
        self.assertEqual(self._verrouiller(), 0)
        self.assertEqual(M.principal(["restituer"], racine=self.racine), 0)
        chemin_page = self.racine / M.CHEMIN_PAGE
        page = chemin_page.read_text(encoding="utf-8")
        engagement = self._verrou()["engagements_prives"][0]["sha256"]
        chemin_page.write_text(
            page.replace(engagement, "0" * 64), encoding="utf-8"
        )
        self.assertNotEqual(
            M.principal(["verifier-restitution"], racine=self.racine), 0
        )

    def test_restitution_sans_verrou_reste_conforme(self):
        self.assertEqual(M.principal(["restituer"], racine=self.racine), 0)
        page = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        self.assertEqual(page.count(' data-verrou-panel="'), 0)
        self.assertEqual(
            M.principal(["verifier-restitution"], racine=self.racine), 0
        )


if __name__ == "__main__":
    unittest.main()
