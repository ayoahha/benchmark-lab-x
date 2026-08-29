# /// script
# requires-python = ">=3.12"
# ///
"""Contrôles verticaux de la préparation de complétion V1-R4 (#139) au seam
public : CLI `preparer-completion` et garde CLI `acquerir --completion
--configuration <id>`.

Chaque test passe par `principal` avec une racine de dépôt temporaire copiée
du dépôt réel (doubles locaux). Aucun fournisseur, harnais ou exécutable
réel n'est résolu ni lancé : `subprocess.Popen` et `shutil.which` sont
doublés en échec explicite par défaut ; le seul test qui exerce l'adaptateur
avec un exécutable double local restaure ces frontières et lance un script
écrit par le test lui-même.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tools"))

import campagne_v1 as M  # noqa: E402

from tests._helpers_v1 import retirer_couverture_publiee  # noqa: E402

_CAMPAGNE = Path("tasks/dev/pre-cadrage-entretien-client/campagne-v1")
_PRE_CADRAGE = Path("tasks/dev/pre-cadrage-entretien-client")

# Les cinq configurations MISSING_OBSERVATION et leurs créneaux -001 figés
# par le contrat #139 (identifiants D-V1-01), dans l'ordre du verrou.
CRENEAUX_COMPLETION = (
    ("claude-code-fable-5", "ACQ-V1-CLAUDE-CODE-FABLE-5-001"),
    ("claude-code-opus-5", "ACQ-V1-CLAUDE-CODE-OPUS-5-001"),
    ("codex-gpt-5-6-sol", "ACQ-V1-CODEX-GPT-5-6-SOL-001"),
    ("cursor-kimi-k3", "ACQ-V1-CURSOR-KIMI-K3-001"),
    ("grok-build-grok-4-6", "ACQ-V1-GROK-BUILD-GROK-4-6-001"),
)

# Descripteurs standards D-V1-01 : exactement le harnais du registre
# officiel, sans wrapper fournisseur ni variante.
ARGV_STANDARDS = {
    "claude-code-fable-5": ["claude", "__PROMPT_FILE__"],
    "claude-code-opus-5": ["claude", "__PROMPT_FILE__"],
    "codex-gpt-5-6-sol": ["codex", "__PROMPT_FILE__"],
    "cursor-kimi-k3": ["agent", "__PROMPT_FILE__"],
    "grok-build-grok-4-6": ["grok", "__PROMPT_FILE__"],
}

_FICHIERS_ENTREE = tuple(chemin for chemin, _ in M.SOURCES_AUTORISEES) + (
    M.CHEMIN_CARTE,
    M.CHEMIN_STIMULUS,
    M.CHEMIN_ETAT.as_posix(),
    M.CHEMIN_SOURCES_PLANS.as_posix(),
    M.CHEMIN_VERROU.as_posix(),
    M.CHEMIN_AUTORISATION_ACQUISITION.as_posix(),
    M.CHEMIN_REGISTRE_VALIDATION.as_posix(),
    M.CHEMIN_RECU_QUALIFICATION.as_posix(),
)
_REPERTOIRES_ENTREE = (
    _CAMPAGNE / "registre-panel-v1",
    _CAMPAGNE / "preflights-v1",
)
# Reçus de référence copiés un à un : le répertoire vivant recus-v1 n'est
# jamais copié en bloc, un reçu -002 réel du dépôt ne doit pas entrer dans
# les bacs temporaires des tests
_RECUS_REFERENCE = (
    _CAMPAGNE
    / "recus-v1"
    / "80046afee6e56ab9dcbdbbda4d5a4190d0d77cad2449b900ae16861e14cad839.json",
    _CAMPAGNE
    / "recus-v1"
    / "0964422c4970ed527846e5dce3f7f9fcc9640897424044aad3f7cbc146695f40.json",
    _CAMPAGNE
    / "recus-v1"
    / "955c15c1d635386c7a25b9b0f3013e519883326236fcc2810cb05683d859a7f9.json",
)


def _refus_executable(*arguments: object, **cles: object) -> None:
    raise AssertionError("aucun exécutable ne doit être résolu ni lancé")


class _BaseCompletion(unittest.TestCase):
    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        for relatif in _FICHIERS_ENTREE:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        retirer_couverture_publiee(self.racine / M.CHEMIN_ETAT)
        for repertoire in _REPERTOIRES_ENTREE:
            shutil.copytree(RACINE / repertoire, self.racine / repertoire)
        repertoire_recus = self.racine / _CAMPAGNE / "recus-v1"
        repertoire_recus.mkdir(parents=True, exist_ok=True)
        for relatif in _RECUS_REFERENCE:
            shutil.copyfile(RACINE / relatif, self.racine / relatif)
        self._aligner_registre_validation_sur_le_bac()
        self.chemin_verrou_completion = (
            self.racine / M.CHEMIN_VERROU_COMPLETION
        )
        self._popen_d_origine = subprocess.Popen
        self._which_d_origine = shutil.which
        subprocess.Popen = _refus_executable
        shutil.which = _refus_executable
        self.addCleanup(setattr, subprocess, "Popen", self._popen_d_origine)
        self.addCleanup(setattr, shutil, "which", self._which_d_origine)

    def _aligner_registre_validation_sur_le_bac(self) -> None:
        """Restreint le registre de validation copié aux seuls reçus isolés
        du bac : les entrées couvrant des reçus officiels du dépôt réel
        (les -002 vivants) sont retirées et la couverture recomptée, sans
        jamais copier ces reçus dans le bac."""
        chemin_registre = self.racine / M.CHEMIN_REGISTRE_VALIDATION
        registre = json.loads(chemin_registre.read_text(encoding="utf-8"))
        registre["entrees"] = [
            entree
            for entree in registre["entrees"]
            if (self.racine / entree["recu"]).is_file()
        ]
        recompte = {verdict: 0 for verdict in M.VERDICTS_CANDIDATS}
        for entree in registre["entrees"]:
            if entree["verdict"] is not None:
                recompte[entree["verdict"]["statut"]] += 1
        registre["couverture"] = {
            "acquisitions_officielles": len(registre["entrees"]),
            "sorties_candidates": sum(recompte.values()),
            "verdicts": recompte,
        }
        chemin_registre.write_bytes(M.octets_canoniques(registre))

    def _appeler(self, arguments: list[str]) -> tuple[int, str]:
        tampon = io.StringIO()
        with redirect_stdout(tampon):
            code = M.principal(arguments, racine=self.racine)
        return code, tampon.getvalue()

    def _instantane(self) -> dict[str, str]:
        instantanes: dict[str, str] = {}
        for chemin in sorted(self.racine.rglob("*")):
            relatif = chemin.relative_to(self.racine).as_posix()
            if chemin.is_dir():
                instantanes[relatif] = "repertoire"
            else:
                instantanes[relatif] = hashlib.sha256(
                    chemin.read_bytes()
                ).hexdigest()
        return instantanes

    def _verrou_completion(self) -> dict:
        return json.loads(
            self.chemin_verrou_completion.read_text(encoding="utf-8")
        )


class GardeAcquisitionCompletionTests(_BaseCompletion):
    """La garde d'autorité absente s'arrête avant toute résolution
    d'exécutable, processus, espace de travail, journal ou reçu."""

    def test_acquerir_completion_rend_deux_autorite_absente_sans_effet(self):
        for identifiant, acquisition_id in CRENEAUX_COMPLETION:
            avant = self._instantane()
            code, sortie = self._appeler(
                ["acquerir", "--completion", "--configuration", identifiant]
            )
            self.assertEqual(code, 2, sortie)
            self.assertIn("AUTORITE_ABSENTE", sortie)
            self.assertIn(acquisition_id, sortie)
            self.assertIn("aucun exécutable résolu", sortie)
            self.assertIn("aucun processus fournisseur", sortie)
            self.assertIn("aucun espace de travail", sortie)
            self.assertIn("aucun journal", sortie)
            self.assertIn("aucun reçu", sortie)
            self.assertIn("aucun appel", sortie)
            self.assertEqual(self._instantane(), avant)

    def test_acquerir_completion_refuse_un_slug_invalide(self):
        avant = self._instantane()
        code, sortie = self._appeler(
            ["acquerir", "--completion", "--configuration", "Majus-cule"]
        )
        self.assertEqual(code, 2)
        self.assertIn("slug stable", sortie)
        self.assertEqual(self._instantane(), avant)

    def test_acquerir_completion_refuse_une_configuration_hors_portee(self):
        for identifiant in ("antigravity-gemini-3-7-flash", "zai-glm-5-3"):
            avant = self._instantane()
            code, sortie = self._appeler(
                ["acquerir", "--completion", "--configuration", identifiant]
            )
            self.assertEqual(code, 2, sortie)
            self.assertIn("hors de la portée", sortie)
            self.assertEqual(self._instantane(), avant)

    def test_garde_active_meme_apres_preparation(self):
        code, _ = self._appeler(["preparer-completion"])
        self.assertEqual(code, 0)
        avant = self._instantane()
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "claude-code-fable-5",
            ]
        )
        self.assertEqual(code, 2, sortie)
        self.assertIn("AUTORITE_ABSENTE", sortie)
        self.assertEqual(self._instantane(), avant)


class PreparationCompletionTests(_BaseCompletion):
    """`preparer-completion` matérialise ou vérifie le verrou additif."""

    def _sources_attendues(self) -> list[dict]:
        relatifs = [
            (_CAMPAGNE / "verrou-campagne-v1" / "verrou.json").as_posix(),
            (_PRE_CADRAGE / "stimulus.md").as_posix(),
        ]
        for configuration_id, _ in CRENEAUX_COMPLETION:
            relatifs.append(
                (
                    _CAMPAGNE
                    / "registre-panel-v1"
                    / f"{configuration_id}.toml"
                ).as_posix()
            )
            relatifs.append(
                (
                    _CAMPAGNE / "preflights-v1" / f"{configuration_id}.json"
                ).as_posix()
            )
        return [
            {
                "chemin": relatif,
                "sha256": hashlib.sha256(
                    (self.racine / relatif).read_bytes()
                ).hexdigest(),
            }
            for relatif in relatifs
        ]

    def test_preparer_completion_materialise_le_verrou_exact(self):
        code, sortie = self._appeler(["preparer-completion"])
        self.assertEqual(code, 0, sortie)
        verrou = self._verrou_completion()
        self.assertEqual(
            self.chemin_verrou_completion.read_bytes(),
            M.octets_canoniques(verrou),
        )
        self.assertEqual(
            verrou["schema_version"], "campagne-v1-verrou-completion/v1"
        )
        self.assertEqual(
            verrou["portee"],
            {
                "issue": "https://github.com/ayoahha/benchmark-lab-x/issues/139",
                "product_version": "V1",
                "tranche": "V1-R4",
            },
        )
        self.assertEqual(
            verrou["version_v1_r3"],
            {
                "issue": "https://github.com/ayoahha/benchmark-lab-x/issues/138",
                "commit": "ede86a2c9475c3186aa57b4a95b8754513e4f2ce",
            },
        )
        self.assertEqual(
            verrou["configurations"],
            [
                {
                    "configuration_id": configuration_id,
                    "acquisition_id": acquisition_id,
                    "descripteur": {
                        "argv": ARGV_STANDARDS[configuration_id],
                        "stimulus_utf8": "fichier-prompt",
                    },
                    "verdict": "APTITUDE_STATIQUE_PRETE",
                    "cause": "STATIQUE_COMPLETE",
                    "faits_a_l_appel": {
                        "identite_servie": "INCONNU",
                        "effort_effectif": "INCONNU",
                        "disponibilite_distante": "INCONNU",
                        "quota_restant": "INCONNU",
                    },
                }
                for configuration_id, acquisition_id in CRENEAUX_COMPLETION
            ],
        )
        self.assertEqual(verrou["autorite_execution"], "NOT_GRANTED")
        self.assertEqual(verrou["creneaux_executes"], 0)
        self.assertEqual(verrou["reprises_executees"], 0)
        self.assertEqual(verrou["fallback"], "NONE")
        self.assertEqual(
            verrou["variantes_interdites"],
            ["fallback", "retry", "fast", "priority", "max", "ultra"],
        )
        self.assertIn("READY de préflight", verrou["aptitude_statique"]["ne_prouve_jamais"])
        self.assertIn("identité servie", verrou["aptitude_statique"]["ne_prouve_jamais"])
        self.assertEqual(
            verrou["jamais_preuve"], ["argv demandé", "code de sortie 0"]
        )
        self.assertEqual(
            verrou["sources_historiques"], self._sources_attendues()
        )
        lignes_verdict = [
            ligne for ligne in sortie.splitlines() if " · verdict " in ligne
        ]
        self.assertEqual(len(lignes_verdict), 5)
        for (configuration_id, acquisition_id), ligne in zip(
            CRENEAUX_COMPLETION, lignes_verdict
        ):
            self.assertIn(acquisition_id, ligne)
            self.assertIn(configuration_id, ligne)
            self.assertIn("verdict APTITUDE_STATIQUE_PRETE", ligne)
            self.assertIn("cause STATIQUE_COMPLETE", ligne)
            self.assertIn("identite_servie=INCONNU", ligne)
            self.assertIn("effort_effectif=INCONNU", ligne)
            self.assertIn("disponibilite_distante=INCONNU", ligne)
            self.assertIn("quota_restant=INCONNU", ligne)
        self.assertIn("verrou de complétion vérifié", sortie)
        self.assertIn(
            "créneaux : 5 · autorite_execution : NOT_GRANTED", sortie
        )
        self.assertIn("APTITUDE_STATIQUE_PRETE reste distinct du READY", sortie)
        empreinte = hashlib.sha256(
            self.chemin_verrou_completion.read_bytes()
        ).hexdigest()
        self.assertIn(empreinte, sortie)

    def test_faits_dynamiques_inconnus_jamais_promus_ni_degradants(self):
        code, _ = self._appeler(["preparer-completion"])
        self.assertEqual(code, 0)
        for entree in self._verrou_completion()["configurations"]:
            # Les quatre faits dynamiques restent littéralement INCONNU et
            # ne dégradent pas l'aptitude statique complète
            self.assertEqual(
                sorted(entree["faits_a_l_appel"]),
                [
                    "disponibilite_distante",
                    "effort_effectif",
                    "identite_servie",
                    "quota_restant",
                ],
            )
            self.assertEqual(
                set(entree["faits_a_l_appel"].values()), {"INCONNU"}
            )
            self.assertEqual(entree["verdict"], "APTITUDE_STATIQUE_PRETE")


class IdempotenceCompletionTests(_BaseCompletion):
    def test_seconde_execution_verifie_les_octets_sans_reecriture(self):
        premier, _ = self._appeler(["preparer-completion"])
        self.assertEqual(premier, 0)
        octets_premier = self.chemin_verrou_completion.read_bytes()
        infos_premier = os.lstat(self.chemin_verrou_completion)
        avant = self._instantane()
        second, sortie = self._appeler(["preparer-completion"])
        self.assertEqual(second, 0, sortie)
        lignes_verdict = [
            ligne for ligne in sortie.splitlines() if " · verdict " in ligne
        ]
        self.assertEqual(len(lignes_verdict), 5)
        self.assertEqual(
            self.chemin_verrou_completion.read_bytes(), octets_premier
        )
        infos_second = os.lstat(self.chemin_verrou_completion)
        self.assertEqual(infos_second.st_ino, infos_premier.st_ino)
        self.assertEqual(infos_second.st_mtime_ns, infos_premier.st_mtime_ns)
        self.assertEqual(self._instantane(), avant)

    def test_divergence_du_verrou_rend_deux_et_nomme_le_champ_fautif(self):
        code, _ = self._appeler(["preparer-completion"])
        self.assertEqual(code, 0)
        verrou = self._verrou_completion()
        verrou["autorite_execution"] = "GRANTED"
        self.chemin_verrou_completion.write_bytes(M.octets_canoniques(verrou))
        octets_divergents = self.chemin_verrou_completion.read_bytes()
        code, sortie = self._appeler(["preparer-completion"])
        self.assertEqual(code, 2)
        self.assertIn("autorite_execution", sortie)
        self.assertIn("aucune réécriture", sortie)
        self.assertEqual(
            self.chemin_verrou_completion.read_bytes(), octets_divergents
        )

    def test_divergence_d_une_ligne_nomme_le_champ_exact(self):
        code, _ = self._appeler(["preparer-completion"])
        self.assertEqual(code, 0)
        verrou = self._verrou_completion()
        verrou["configurations"][2]["descripteur"]["argv"][0] = "wrapper"
        self.chemin_verrou_completion.write_bytes(M.octets_canoniques(verrou))
        code, sortie = self._appeler(["preparer-completion"])
        self.assertEqual(code, 2)
        self.assertIn(
            "configurations[codex-gpt-5-6-sol].descripteur.argv", sortie
        )

    def test_verrou_completion_symbolique_rend_deux(self):
        cible = self.racine / M.CHEMIN_ETAT
        self.chemin_verrou_completion.parent.mkdir(
            parents=True, exist_ok=True
        )
        self.chemin_verrou_completion.symlink_to(cible)
        code, sortie = self._appeler(["preparer-completion"])
        self.assertEqual(code, 2)
        self.assertIn("fichier régulier non symbolique attendu", sortie)

    def test_course_de_creation_fileexistserror_rend_deux_distinct(self):
        open_origine = os.open

        def _os_open_gardien(chemin, *args, **cles):
            if Path(chemin).name == M.CHEMIN_VERROU_COMPLETION.name:
                raise FileExistsError(
                    17, "File exists (course simulée)", str(chemin)
                )
            return open_origine(chemin, *args, **cles)

        os.open = _os_open_gardien
        try:
            code, sortie = self._appeler(["preparer-completion"])
        finally:
            os.open = open_origine
        self.assertEqual(code, 2)
        self.assertIn("création concurrente détectée", sortie)
        self.assertFalse(self.chemin_verrou_completion.exists())


class BranchesVerdictCompletionTests(_BaseCompletion):
    """Chaque branche observable : APTITUDE_STATIQUE_PRETE=0 (couverte par
    la matérialisation), UNAVAILABLE=1 et HOLD=2."""

    def _ligne_de(self, sortie: str, configuration_id: str) -> str:
        for ligne in sortie.splitlines():
            if f" · {configuration_id} · " in ligne:
                return ligne
        raise AssertionError(f"ligne absente pour {configuration_id}")

    def test_preflight_absent_rend_unavailable_et_code_un(self):
        (
            self.racine / _CAMPAGNE / "preflights-v1" / "cursor-kimi-k3.json"
        ).unlink()
        code, sortie = self._appeler(["preparer-completion"])
        self.assertEqual(code, 1, sortie)
        ligne = self._ligne_de(sortie, "cursor-kimi-k3")
        self.assertIn("verdict UNAVAILABLE", ligne)
        self.assertIn("cause PREFLIGHT_ABSENT", ligne)
        self.assertIn("identite_servie=INCONNU", ligne)
        for autre in (
            "claude-code-fable-5",
            "claude-code-opus-5",
            "codex-gpt-5-6-sol",
            "grok-build-grok-4-6",
        ):
            self.assertIn(
                "verdict APTITUDE_STATIQUE_PRETE", self._ligne_de(sortie, autre)
            )
        self.assertIn("ECHEC UNAVAILABLE", sortie)
        self.assertIn("impossibilité locale explicite", sortie)
        self.assertIn("aucun verrou écrit", sortie)
        self.assertFalse(self.chemin_verrou_completion.exists())

    def test_configuration_absente_rend_unavailable_et_code_un(self):
        (
            self.racine
            / _CAMPAGNE
            / "registre-panel-v1"
            / "grok-build-grok-4-6.toml"
        ).unlink()
        code, sortie = self._appeler(["preparer-completion"])
        self.assertEqual(code, 1, sortie)
        ligne = self._ligne_de(sortie, "grok-build-grok-4-6")
        self.assertIn("verdict UNAVAILABLE", ligne)
        self.assertIn("cause CONFIGURATION_ABSENTE", ligne)
        self.assertFalse(self.chemin_verrou_completion.exists())

    def test_scelle_configuration_divergent_rend_hold_et_code_deux(self):
        configuration = (
            self.racine
            / _CAMPAGNE
            / "registre-panel-v1"
            / "grok-build-grok-4-6.toml"
        )
        configuration.write_bytes(configuration.read_bytes() + b"\n")
        code, sortie = self._appeler(["preparer-completion"])
        self.assertEqual(code, 2, sortie)
        ligne = self._ligne_de(sortie, "grok-build-grok-4-6")
        self.assertIn("verdict HOLD", ligne)
        self.assertIn("cause SCELLE_CONFIGURATION_DIVERGENT", ligne)
        self.assertIn("ECHEC HOLD", sortie)
        self.assertIn("scellé divergent", sortie)
        self.assertIn("grok-build-grok-4-6.toml", sortie)
        self.assertFalse(self.chemin_verrou_completion.exists())

    def test_scelle_preflight_divergent_rend_hold_et_code_deux(self):
        preflight = (
            self.racine
            / _CAMPAGNE
            / "preflights-v1"
            / "claude-code-fable-5.json"
        )
        preflight.write_bytes(preflight.read_bytes() + b"\n")
        code, sortie = self._appeler(["preparer-completion"])
        self.assertEqual(code, 2, sortie)
        ligne = self._ligne_de(sortie, "claude-code-fable-5")
        self.assertIn("verdict HOLD", ligne)
        self.assertIn("cause SCELLE_PREFLIGHT_DIVERGENT", ligne)
        self.assertFalse(self.chemin_verrou_completion.exists())

    def test_hold_prime_sur_unavailable(self):
        (
            self.racine / _CAMPAGNE / "preflights-v1" / "cursor-kimi-k3.json"
        ).unlink()
        configuration = (
            self.racine
            / _CAMPAGNE
            / "registre-panel-v1"
            / "grok-build-grok-4-6.toml"
        )
        configuration.write_bytes(configuration.read_bytes() + b"\n")
        code, sortie = self._appeler(["preparer-completion"])
        self.assertEqual(code, 2, sortie)
        self.assertIn("ECHEC HOLD", sortie)
        self.assertFalse(self.chemin_verrou_completion.exists())

    def test_source_partagee_divergente_rend_deux_sans_lignes(self):
        stimulus = self.racine / M.CHEMIN_STIMULUS
        stimulus.write_bytes(stimulus.read_bytes() + b"\nalteration")
        code, sortie = self._appeler(["preparer-completion"])
        self.assertEqual(code, 2, sortie)
        self.assertIn("constante figée divergente", sortie)
        self.assertIn("stimulus.md", sortie)
        self.assertFalse(self.chemin_verrou_completion.exists())

    def test_creneau_consomme_rend_hold_et_code_deux(self):
        repertoire = self.racine / _CAMPAGNE / "recus-v1"
        enveloppes = {}
        for chemin in repertoire.iterdir():
            enveloppes[chemin.stem] = json.loads(
                chemin.read_text(encoding="utf-8")
            )
        references = {
            enveloppe["payload"]["predecesseur_adresse_contenu"]
            for enveloppe in enveloppes.values()
        }
        queue = next(
            adresse for adresse in enveloppes if adresse not in references
        )
        modele = json.loads(
            json.dumps(
                enveloppes[
                    "0964422c4970ed527846e5dce3f7f9fcc9640897424044aad3f7cbc146695f40"
                ]
            )
        )
        charge = modele["payload"]
        relatif_configuration = (
            _CAMPAGNE / "registre-panel-v1" / "claude-code-fable-5.toml"
        ).as_posix()
        charge["configuration"] = {
            "identifiant": "claude-code-fable-5",
            "chemin": relatif_configuration,
            "sha256": hashlib.sha256(
                (self.racine / relatif_configuration).read_bytes()
            ).hexdigest(),
        }
        charge["creneau"] = (
            f"claude-code-fable-5:{charge['stimulus']['sha256']}"
        )
        charge["predecesseur_adresse_contenu"] = queue
        adresse = M.adresse_canonique(charge)
        enveloppe = {
            "schema_version": modele["schema_version"],
            "content_address": {"algorithm": "SHA256", "sha256": adresse},
            "payload": charge,
        }
        (repertoire / f"{adresse}.json").write_bytes(
            M.octets_canoniques(enveloppe)
        )
        code, sortie = self._appeler(["preparer-completion"])
        self.assertEqual(code, 2, sortie)
        ligne = self._ligne_de(sortie, "claude-code-fable-5")
        self.assertIn("verdict HOLD", ligne)
        self.assertIn("cause CRENEAU_CONSOMME", ligne)
        self.assertFalse(self.chemin_verrou_completion.exists())


class AdaptateurCompletionTests(_BaseCompletion):
    """L'adaptateur pur des tentatives futures, exercé uniquement avec des
    doubles locaux : argv fermé, stimulus par fichier de prompt, espace de
    travail isolé, aucun descendant d'agent."""

    def test_tentative_substitue_le_fichier_prompt_sans_stdin(self):
        binaires = {
            "claude-code-fable-5": "claude",
            "claude-code-opus-5": "claude",
            "codex-gpt-5-6-sol": "codex",
            "cursor-kimi-k3": "agent",
            "grok-build-grok-4-6": "grok",
        }
        for configuration_id, binaire in binaires.items():
            tentative = M.construire_tentative_completion(
                configuration_id, b"octets du stimulus", "/espace/isole"
            )
            self.assertEqual(
                tentative["argv"], [binaire, "/espace/isole/stimulus.md"]
            )
            self.assertIsNone(tentative["stdin"])
            self.assertEqual(tentative["cwd"], "/espace/isole")
            self.assertEqual(
                tentative["fichier_prompt"],
                {
                    "chemin": "/espace/isole/stimulus.md",
                    "stimulus_utf8": b"octets du stimulus",
                },
            )

    def test_tentative_refuse_tout_identifiant_hors_creneaux(self):
        for identifiant in (
            "antigravity-gemini-3-7-flash",
            "zai-glm-5-3",
            "claude-code-fable-5-001",
        ):
            with self.assertRaises(M.ErreurCompletion):
                M.construire_tentative_completion(
                    identifiant, b"x", "/espace/isole"
                )

    def test_double_local_observe_espace_isole_et_zero_descendant(self):
        # Seul test qui lance un processus : un double local écrit par le
        # test lui-même, jamais une CLI fournisseur réelle.
        subprocess.Popen = self._popen_d_origine
        shutil.which = self._which_d_origine
        bac = Path(self._temporaire.name)
        repertoire_doubles = bac / "doubles"
        repertoire_doubles.mkdir()
        double = repertoire_doubles / "claude"
        double.write_text('#!/bin/sh\npwd\ncat "$1"\n', encoding="utf-8")
        double.chmod(0o755)
        espace = bac / "espace-tentative"
        espace.mkdir()
        stimulus = "stimulus de complétion : éventail UTF-8".encode("utf-8")
        tentative = M.construire_tentative_completion(
            "claude-code-fable-5", stimulus, str(espace)
        )
        Path(tentative["fichier_prompt"]["chemin"]).write_bytes(
            tentative["fichier_prompt"]["stimulus_utf8"]
        )
        chemin_path_origine = os.environ["PATH"]
        os.environ["PATH"] = f"{repertoire_doubles}:{chemin_path_origine}"
        self.addCleanup(
            os.environ.__setitem__, "PATH", chemin_path_origine
        )
        execution, descendants = M._executer_acquisition(
            tentative["argv"], b"", Path(tentative["cwd"]), 30
        )
        self.assertEqual(execution["etat"], "OBSERVED")
        self.assertEqual(execution["code_sortie"], 0)
        sortie = execution["sortie"]["stdout"]
        self.assertIn(espace.name, sortie)
        self.assertIn("stimulus de complétion : éventail UTF-8", sortie)
        self.assertEqual(descendants, 0)


class IntegrationCompletionTests(_BaseCompletion):
    """L'état et la restitution restent verts et inchangés en présence du
    verrou de complétion : la préparation est purement additive."""

    def test_etat_et_restitution_restent_verts_avec_le_verrou(self):
        code, _ = self._appeler(["preparer-completion"])
        self.assertEqual(code, 0)
        octets_verrou = self.chemin_verrou_completion.read_bytes()
        code, sortie_etat = self._appeler(["etat"])
        self.assertEqual(code, 0, sortie_etat)
        code, sortie = self._appeler(["restituer"])
        self.assertEqual(code, 0, sortie)
        code, sortie = self._appeler(["verifier-restitution"])
        self.assertEqual(code, 0, sortie)
        self.assertEqual(
            self.chemin_verrou_completion.read_bytes(), octets_verrou
        )
        code, sortie = self._appeler(["preparer-completion"])
        self.assertEqual(code, 0, sortie)

    def test_restitution_cite_le_verrou_de_completion_sans_le_promouvoir(self):
        # Contrat de rendu V1-XS-14 (retours propriétaires) : le verrou de
        # complétion est cité par la page comme source d'explication —
        # APTITUDE_STATIQUE_PRETE ne prouve jamais READY ni un résultat —
        # sans changer aucun verdict, aucune preuve ni la conclusion
        code, _ = self._appeler(["restituer"])
        self.assertEqual(code, 0)
        page_sans = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        self.assertNotIn("verrou-completion.json", page_sans)
        code, sortie = self._appeler(["verifier-restitution"])
        self.assertEqual(code, 0, sortie)
        code, _ = self._appeler(["preparer-completion"])
        self.assertEqual(code, 0)
        code, _ = self._appeler(["restituer"])
        self.assertEqual(code, 0)
        page_avec = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        self.assertNotEqual(page_avec, page_sans)
        empreinte = hashlib.sha256(
            self.chemin_verrou_completion.read_bytes()
        ).hexdigest()
        relatif = M.CHEMIN_VERROU_COMPLETION.as_posix()
        self.assertIn(
            f'data-chemin="{relatif}" data-sha256="{empreinte}"', page_avec
        )
        self.assertIn("APTITUDE_STATIQUE_PRETE", page_avec)
        self.assertIn("ne prouve jamais", page_avec)
        # La conclusion et les jetons factuels restent inchangés
        self.assertIn("conclusion: ABSTENTION", page_avec)
        # Les verdicts, comptages et sections de preuve restent
        # byte-identiques : la citation du verrou n'altère ni l'état, ni
        # la validation, ni la couverture, ni le parcours
        # La couverture publiée est retirée par le bac (_helpers_v1) :
        # la section couverture-v1 n'existe pas ici, dans aucun des deux
        # états ; les sections présentes doivent rester byte-identiques
        self.assertNotIn('<section id="couverture-v1"', page_sans)
        self.assertNotIn('<section id="couverture-v1"', page_avec)
        for identifiant_section in (
            '<section id="etat-v1">',
            '<section id="validation-automatique">',
            '<section id="etapes-futures">',
        ):
            avec = page_avec.split(identifiant_section, 1)[1].split(
                "</section>", 1
            )[0]
            sans = page_sans.split(identifiant_section, 1)[1].split(
                "</section>", 1
            )[0]
            self.assertEqual(avec, sans, identifiant_section)
        for invariant in (
            ' data-validation="',
            ' data-preflight="',
            ' data-acquisition-officielle="',
            "FAIL",
            "HARNESS_ERROR",
        ):
            self.assertEqual(
                page_avec.count(invariant),
                page_sans.count(invariant),
                invariant,
            )
        code, sortie = self._appeler(["verifier-restitution"])
        self.assertEqual(code, 0, sortie)


class ExecutionCompletionR5Tests(_BaseCompletion):
    """V1-R5 (#145) : cinq descripteurs candidats exacts du contrat et
    autorisation additive distinguant route_execution, telemetrie_abonnement
    et resultat_mesure. Aucun exécutable réel n'est résolu ni lancé."""

    def setUp(self):
        super().setUp()
        self._temporaire_prive = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire_prive.cleanup)
        self.privee = Path(self._temporaire_prive.name)

    def _appeler(self, arguments: list[str]) -> tuple[int, str]:
        tampon = io.StringIO()
        with redirect_stdout(tampon):
            code = M.principal(
                arguments, racine=self.racine, racine_privee=self.privee
            )
        return code, tampon.getvalue()

    JETON_R5 = (
        "AUTHORIZE_SEMANTIC_FIX_AND_FIVE_SINGLE_SHOT_COMPLETION_ACQUISITIONS"
    )
    ISSUE_R5 = "https://github.com/ayoahha/benchmark-lab-x/issues/145"
    SHA_VERROU_R4 = (
        "26b994f8fd63c44c225e9d4b08aeb70e6faa4c98f7bf72b3fd7c133bc3a49539"
    )
    # Descripteurs fermés du contrat #145, recopiés littéralement : modèle
    # et effort observables dans chaque argv, aucun wrapper fournisseur.
    ARGV_R5 = {
        "claude-code-fable-5": [
            "claude", "--model", "claude-fable-5", "--effort", "high",
            "--print", "--input-format", "text", "--output-format", "json",
            "--permission-mode", "plan", "--disable-slash-commands",
            "--strict-mcp-config", "--no-session-persistence", "--no-chrome",
        ],
        "claude-code-opus-5": [
            "claude", "--model", "claude-opus-5", "--effort", "high",
            "--print", "--input-format", "text", "--output-format", "json",
            "--permission-mode", "plan", "--disable-slash-commands",
            "--strict-mcp-config", "--no-session-persistence", "--no-chrome",
        ],
        "codex-gpt-5-6-sol": [
            "codex", "exec", "--ephemeral", "--sandbox", "read-only",
            "--model", "gpt-5.6-sol", "--cd", "__ISOLATED_WORKSPACE__",
            "--config", 'model_reasoning_effort="high"', "-",
        ],
        "cursor-kimi-k3": [
            "agent", "--print", "--output-format", "json", "--mode", "ask",
            "--sandbox", "enabled", "--workspace", "__ISOLATED_WORKSPACE__",
            "--model", "kimi-k3-high", "__STIMULUS_UTF8__",
        ],
        "grok-build-grok-4-6": [
            "grok", "--model", "grok-4.6", "--reasoning-effort", "high",
            "--permission-mode", "plan", "--no-subagents",
            "--disable-web-search", "--cwd", "__ISOLATED_WORKSPACE__",
            "--prompt-file", "__PROMPT_FILE__", "--verbatim",
            "--output-format", "json",
        ],
    }
    TRANSPORTS_R5 = {
        "claude-code-fable-5": "stdin",
        "claude-code-opus-5": "stdin",
        "codex-gpt-5-6-sol": "stdin",
        "cursor-kimi-k3": "argument",
        "grok-build-grok-4-6": "fichier-prompt",
    }

    def test_cinq_descripteurs_r5_exacts_avec_transports_du_contrat(self):
        stimulus = "stimulus de complétion : éventail UTF-8 — ✓".encode(
            "utf-8"
        )
        espace = "/espace/isole"
        self.assertEqual(
            {
                identifiant: list(argv)
                for identifiant, argv in M.DESCRIPTEURS_COMPLETION_R5.items()
            },
            self.ARGV_R5,
        )
        for identifiant, acquisition_id in CRENEAUX_COMPLETION:
            tentative = M.construire_tentative_completion_r5(
                identifiant, stimulus, espace
            )
            attendu = [
                element.replace("__ISOLATED_WORKSPACE__", espace)
                for element in self.ARGV_R5[identifiant]
            ]
            transport = self.TRANSPORTS_R5[identifiant]
            if transport == "stdin":
                # Claude et Codex : stimulus intégral sur FD0 puis EOF,
                # aucun fichier de prompt, aucun argument stimulus
                self.assertEqual(tentative["argv"], attendu, identifiant)
                self.assertEqual(tentative["stdin"], stimulus, identifiant)
                self.assertIsNone(tentative["fichier_prompt"], identifiant)
            elif transport == "argument":
                # Cursor : les octets UTF-8 dans un unique argv, sans shell
                attendu = [
                    stimulus.decode("utf-8")
                    if element == "__STIMULUS_UTF8__"
                    else element
                    for element in attendu
                ]
                self.assertEqual(tentative["argv"], attendu, identifiant)
                self.assertEqual(
                    tentative["argv"].count(stimulus.decode("utf-8")), 1
                )
                self.assertIsNone(tentative["stdin"], identifiant)
                self.assertIsNone(tentative["fichier_prompt"], identifiant)
            else:
                # Grok : --prompt-file --verbatim vers le fichier privé isolé
                chemin_prompt = f"{espace}/stimulus.md"
                attendu = [
                    chemin_prompt if element == "__PROMPT_FILE__" else element
                    for element in attendu
                ]
                self.assertEqual(tentative["argv"], attendu, identifiant)
                self.assertIsNone(tentative["stdin"], identifiant)
                self.assertEqual(
                    tentative["fichier_prompt"],
                    {"chemin": chemin_prompt, "stimulus_utf8": stimulus},
                    identifiant,
                )
            self.assertEqual(tentative["cwd"], espace, identifiant)
            # Modèle et effort demandés : présents dans l'argv fermé
            self.assertIn("--model", tentative["argv"], identifiant)
            self.assertTrue(
                "high" in " ".join(tentative["argv"]), identifiant
            )

    def test_autorisation_additive_et_modele_de_domaine_r5(self):
        code, _ = self._appeler(["preparer-completion"])
        self.assertEqual(code, 0)
        code, sortie = self._appeler(["preparer-execution-completion"])
        self.assertEqual(code, 0, sortie)
        chemin = (
            self.racine
            / _CAMPAGNE
            / "completion-panel-v1"
            / "autorisation-completion-v1.json"
        )
        autorisation = json.loads(chemin.read_text(encoding="utf-8"))
        self.assertEqual(
            chemin.read_bytes(), M.octets_canoniques(autorisation)
        )
        self.assertEqual(autorisation["jeton"], self.JETON_R5)
        self.assertEqual(autorisation["portee"]["issue"], self.ISSUE_R5)
        self.assertEqual(autorisation["portee"]["tranche"], "V1-R5")
        self.assertEqual(
            autorisation["verrou_completion"],
            {
                "chemin": (
                    _CAMPAGNE
                    / "completion-panel-v1"
                    / "verrou-completion.json"
                ).as_posix(),
                "sha256": self.SHA_VERROU_R4,
            },
        )
        self.assertEqual(
            autorisation["stimulus"]["sha256"],
            hashlib.sha256(
                (self.racine / M.CHEMIN_STIMULUS).read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(
            autorisation["portee"]["acquisitions"],
            [
                {
                    "acquisition_id": acquisition_id,
                    "configuration_id": configuration_id,
                }
                for configuration_id, acquisition_id in CRENEAUX_COMPLETION
            ],
        )
        self.assertEqual(autorisation["portee"]["appels_fournisseur_max"], 5)
        self.assertEqual(autorisation["portee"]["appels_par_creneau"], 1)
        self.assertEqual(autorisation["portee"]["effort_candidat"], "high")
        self.assertEqual(autorisation["portee"]["reprises_automatiques"], 0)
        self.assertEqual(autorisation["portee"]["reprises_manuelles"], 0)
        self.assertEqual(autorisation["portee"]["fallback"], "NONE")
        self.assertEqual(autorisation["portee"]["depense_incrementale"], 0)
        self.assertEqual(
            autorisation["descripteurs"],
            {
                identifiant: {
                    "argv": self.ARGV_R5[identifiant],
                    "stimulus_utf8": self.TRANSPORTS_R5[identifiant],
                }
                for identifiant, _ in CRENEAUX_COMPLETION
            },
        )
        # Modèle de domaine : la route exécutable est distinguée de la
        # télémétrie de compte et du résultat de mesure ; un quota non
        # collecté ne dégrade jamais une route autrement prête
        lignes = [
            ligne for ligne in sortie.splitlines() if "route_execution" in ligne
        ]
        self.assertEqual(len(lignes), 5, sortie)
        for (configuration_id, acquisition_id), ligne in zip(
            CRENEAUX_COMPLETION, lignes
        ):
            self.assertIn(acquisition_id, ligne)
            self.assertIn(
                "route_execution PRETE_POUR_TENTATIVE_AUTORISEE", ligne
            )
            self.assertIn(
                "telemetrie_abonnement OBSERVABLE_COMPTE_NON_COLLECTE",
                ligne,
            )
            self.assertIn("resultat_mesure ABSENT", ligne)
        # Idempotence : seconde invocation, octets vérifiés sans réécriture
        octets = chemin.read_bytes()
        avant = self._instantane()
        code, _ = self._appeler(["preparer-execution-completion"])
        self.assertEqual(code, 0)
        self.assertEqual(chemin.read_bytes(), octets)
        self.assertEqual(self._instantane(), avant)

    def _preparer_autorisation_r5(self) -> Path:
        code, _ = self._appeler(["preparer-completion"])
        self.assertEqual(code, 0)
        code, _ = self._appeler(["preparer-execution-completion"])
        self.assertEqual(code, 0)
        return self.racine / M.CHEMIN_AUTORISATION_COMPLETION

    def test_etat_publie_le_modele_de_domaine_sous_autorisation_valide(self):
        chemin_autorisation = self._preparer_autorisation_r5()
        code, sortie = self._appeler(["etat"])
        self.assertEqual(code, 0, sortie)
        self.assertIn("modèle de domaine V1-R5 écrit dans l'état", sortie)
        chemin_etat = self.racine / M.CHEMIN_ETAT
        etat = json.loads(chemin_etat.read_text(encoding="utf-8"))
        section = etat["execution_completion"]
        # Provenance exacte de l'autorisation additive
        self.assertEqual(
            section["autorisation"],
            {
                "chemin": M.CHEMIN_AUTORISATION_COMPLETION.as_posix(),
                "sha256": hashlib.sha256(
                    chemin_autorisation.read_bytes()
                ).hexdigest(),
            },
        )
        # Statuts et références de preuve seulement, dérivés des preuves
        self.assertEqual(
            section["creneaux"],
            [
                {
                    "configuration_id": configuration_id,
                    "acquisition_id": acquisition_id,
                    "route_execution": "PRETE_POUR_TENTATIVE_AUTORISEE",
                    "cause_route": None,
                    "telemetrie_abonnement": (
                        "OBSERVABLE_COMPTE_NON_COLLECTE"
                    ),
                    "resultat_mesure": "ABSENT",
                }
                for configuration_id, acquisition_id in CRENEAUX_COMPLETION
            ],
        )
        # Déterminisme : une seconde invocation produit des octets
        # byte-identiques
        octets_premier = chemin_etat.read_bytes()
        code, _ = self._appeler(["etat"])
        self.assertEqual(code, 0)
        self.assertEqual(chemin_etat.read_bytes(), octets_premier)

    def test_restitution_rend_la_section_r5_et_sa_provenance(self):
        chemin_autorisation = self._preparer_autorisation_r5()
        code, _ = self._appeler(["etat"])
        self.assertEqual(code, 0)
        code, sortie = self._appeler(["restituer"])
        self.assertEqual(code, 0, sortie)
        page = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        self.assertEqual(
            page.count(' data-execution-completion="section"'), 1
        )
        self.assertEqual(
            page.count(' data-execution-completion-creneau="'), 5
        )
        for _, acquisition_id in CRENEAUX_COMPLETION:
            self.assertIn(
                f' data-execution-completion-creneau="{acquisition_id}"',
                page,
            )
        self.assertIn("route_execution", page)
        self.assertIn("PRETE_POUR_TENTATIVE_AUTORISEE", page)
        self.assertIn("OBSERVABLE_COMPTE_NON_COLLECTE", page)
        # Provenance exacte de l'autorisation additive citée dans la page
        empreinte = hashlib.sha256(
            chemin_autorisation.read_bytes()
        ).hexdigest()
        relatif = M.CHEMIN_AUTORISATION_COMPLETION.as_posix()
        self.assertIn(
            f'data-chemin="{relatif}" data-sha256="{empreinte}"', page
        )
        self.assertIn(self.JETON_R5, page)
        # Déterminisme du rendu et vérification ciblée
        code, _ = self._appeler(["restituer"])
        self.assertEqual(code, 0)
        self.assertEqual(
            (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8"), page
        )
        code, sortie = self._appeler(["verifier-restitution"])
        self.assertEqual(code, 0, sortie)

    def test_vues_historiques_preservees_sans_autorisation_additive(self):
        # Sans autorisation additive : aucune section publiée, l'état et la
        # page historiques restent vérifiables
        code, _ = self._appeler(["etat"])
        self.assertEqual(code, 0)
        etat = json.loads(
            (self.racine / M.CHEMIN_ETAT).read_text(encoding="utf-8")
        )
        self.assertNotIn("execution_completion", etat)
        code, _ = self._appeler(["restituer"])
        self.assertEqual(code, 0)
        page = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        self.assertNotIn("data-execution-completion", page)
        self.assertNotIn("autorisation-completion-v1.json", page)
        code, sortie = self._appeler(["verifier-restitution"])
        self.assertEqual(code, 0, sortie)

    def test_le_formulaire_prive_ne_fuit_jamais_dans_les_vues(self):
        self._preparer_autorisation_r5()
        formulaire = (
            self.privee
            / "campagne-v1"
            / "v1-r5"
            / "observations-abonnements.toml"
        )
        formulaire.parent.mkdir(parents=True, exist_ok=True)
        valeurs_privees = {
            "plan": "PLAN-PRIVE-NE-DOIT-JAMAIS-FUIR",
            "quota_5h_restant": "QUOTA-5H-PRIVE-88",
            "quota_hebdomadaire_restant": "QUOTA-HEBDO-PRIVE-77",
            "reset_5h": "RESET-5H-PRIVE",
            "reset_hebdomadaire": "RESET-HEBDO-PRIVE",
            "depassement_payant": "DEPASSEMENT-PRIVE",
        }
        formulaire.write_text(
            "[[observation]]\n"
            'produit = "ANTHROPIC"\n'
            'observe_le = "2026-08-28"\n'
            'surface = "CLAUDE_SETTINGS_USAGE"\n'
            + "".join(
                f'{cle} = "{valeur}"\n'
                for cle, valeur in valeurs_privees.items()
            ),
            encoding="utf-8",
        )
        code, _ = self._appeler(["etat"])
        self.assertEqual(code, 0)
        octets_etat = (self.racine / M.CHEMIN_ETAT).read_text(
            encoding="utf-8"
        )
        section = json.loads(octets_etat)["execution_completion"]
        telemetries = {
            creneau["configuration_id"]: creneau["telemetrie_abonnement"]
            for creneau in section["creneaux"]
        }
        # Seul le statut est publié : OBSERVED pour le produit renseigné
        self.assertEqual(telemetries["claude-code-fable-5"], "OBSERVED")
        self.assertEqual(telemetries["claude-code-opus-5"], "OBSERVED")
        self.assertEqual(
            telemetries["codex-gpt-5-6-sol"],
            "OBSERVABLE_COMPTE_NON_COLLECTE",
        )
        code, _ = self._appeler(["restituer"])
        self.assertEqual(code, 0)
        page = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        for valeur in (*valeurs_privees.values(), "2026-08-28"):
            self.assertNotIn(valeur, octets_etat)
            self.assertNotIn(valeur, page)
        code, sortie = self._appeler(["verifier-restitution"])
        self.assertEqual(code, 0, sortie)

    def test_verification_refuse_une_section_infidele(self):
        self._preparer_autorisation_r5()
        code, _ = self._appeler(["etat"])
        self.assertEqual(code, 0)
        chemin_etat = self.racine / M.CHEMIN_ETAT
        etat = json.loads(chemin_etat.read_text(encoding="utf-8"))
        # Altération du statut publié : la page rendue reste fidèle à la
        # section altérée, seule la redérivation indépendante la refuse
        etat["execution_completion"]["creneaux"][0][
            "telemetrie_abonnement"
        ] = "OBSERVED"
        chemin_etat.write_text(
            json.dumps(etat, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        code, _ = self._appeler(["restituer"])
        self.assertEqual(code, 0)
        code, sortie = self._appeler(["verifier-restitution"])
        self.assertEqual(code, 1, sortie)
        self.assertIn("redérivation indépendante", sortie)


_FICHIERS_PAQUET = (
    "manifeste-paquet.json",
    "brief-proprietaire.md",
    "registre-verite.md",
    "stimulus.md",
    "temoins-qualification.md",
)
_SOURCES_PAQUET = RACINE / "tasks/dev/pre-cadrage-entretien-client"


def _sortie_acceptable() -> str:
    temoins = (_SOURCES_PAQUET / "temoins-qualification.md").read_text(
        encoding="utf-8"
    )
    return temoins.split("```markdown\n", 1)[1].split("\n```", 1)[0] + "\n"


class _BaseExecutionR5(unittest.TestCase):
    """Bac d'exécution V1-R5 : verrou de campagne et matériel privé
    matérialisés par `verrouiller` dans une racine privée temporaire, verrou
    R4 copié byte-identique du dépôt, autorisation additive matérialisée par
    `preparer-execution-completion`. Aucun fournisseur réel n'est lancé :
    les seuls exécutables sont des doubles écrits par les tests."""

    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self._temporaire_prive = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire_prive.cleanup)
        self.racine = Path(self._temporaire.name)
        self.privee = Path(self._temporaire_prive.name)
        for nom in _FICHIERS_PAQUET:
            destination = (
                self.racine / _SOURCES_PAQUET.relative_to(RACINE) / nom
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_SOURCES_PAQUET / nom, destination)
        fichiers = (
            M.CHEMIN_VALIDATEUR,
            M.CHEMIN_ETAT.as_posix(),
            M.CHEMIN_SOURCES_PLANS.as_posix(),
            M.CHEMIN_AUTORISATION_ACQUISITION.as_posix(),
            M.CHEMIN_RECU_QUALIFICATION.as_posix(),
            "docs/PRD.md",
            "docs/ARD.md",
            "docs/RULES.md",
            "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
            "rapport-decision-m10-2-v1/rapport-interne.md",
        )
        for relatif in fichiers:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        retirer_couverture_publiee(self.racine / M.CHEMIN_ETAT)
        for repertoire in _REPERTOIRES_ENTREE:
            shutil.copytree(RACINE / repertoire, self.racine / repertoire)
        (self.racine / _CAMPAGNE / "recus-v1").mkdir(
            parents=True, exist_ok=True
        )
        self.assertEqual(self._appeler(["verrouiller"])[0], 0)
        # Cohérence de bac : l'autorisation D-V1-04 copiée référence le
        # verrou du dépôt ; le bac vient d'en matérialiser un neuf (sel
        # privé aléatoire), son empreinte est réalignée sans toucher au
        # dépôt réel
        chemin_autorisation = (
            self.racine / M.CHEMIN_AUTORISATION_ACQUISITION
        )
        autorisation = json.loads(
            chemin_autorisation.read_text(encoding="utf-8")
        )
        autorisation["verrou"]["sha256"] = hashlib.sha256(
            (self.racine / M.CHEMIN_VERROU).read_bytes()
        ).hexdigest()
        chemin_autorisation.write_bytes(M.octets_canoniques(autorisation))
        # Verrou R4 immuable : copié byte-identique du dépôt (empreinte
        # 26b994 figée par le contrat #145)
        destination = self.racine / M.CHEMIN_VERROU_COMPLETION
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RACINE / M.CHEMIN_VERROU_COMPLETION, destination)
        self.assertEqual(
            self._appeler(["preparer-execution-completion"])[0], 0
        )
        self.stimulus_octets = (
            self.racine / M.CHEMIN_STIMULUS
        ).read_bytes()
        self.stimulus_sha = hashlib.sha256(self.stimulus_octets).hexdigest()
        self.repertoire_doubles = self.racine / "doubles"
        self.repertoire_doubles.mkdir()
        self.chemin_sortie_acceptable = self.racine / "sortie-acceptable.md"
        self.chemin_sortie_acceptable.write_text(
            _sortie_acceptable(), encoding="utf-8"
        )
        chemin_path = os.environ["PATH"]
        os.environ["PATH"] = f"{self.repertoire_doubles}:{chemin_path}"
        self.addCleanup(os.environ.__setitem__, "PATH", chemin_path)

    def _appeler(self, arguments: list[str]) -> tuple[int, str]:
        tampon = io.StringIO()
        with redirect_stdout(tampon):
            code = M.principal(
                arguments, racine=self.racine, racine_privee=self.privee
            )
        return code, tampon.getvalue()

    def _double(self, nom: str, script: str) -> None:
        chemin = self.repertoire_doubles / nom
        chemin.write_text(script, encoding="utf-8")
        chemin.chmod(0o755)

    def _doubles_pass(self) -> None:
        script = (
            "#!/bin/sh\n"
            # Capture NUL-séparée : un argument UTF-8 multiligne reste un
            # seul enregistrement, la preuve de transport se compare en
            # octets exacts
            'printf \'%s\\0\' "$@" > ./capture-argv.txt\n'
            "cat > ./capture-stdin.txt\n"
            f'cat "{self.chemin_sortie_acceptable}"\n'
        )
        for nom in ("claude", "codex", "agent", "grok"):
            self._double(nom, script)

    def _valider(self) -> int:
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

    def _espace_tentative(self, acquisition_id: str) -> Path:
        return (
            self.privee
            / "v1-execution"
            / "r5"
            / "runtime"
            / acquisition_id
        )

    def _sans_processus(self):
        """Toute création de processus ou résolution d'exécutable échoue."""
        popen, which = subprocess.Popen, shutil.which
        subprocess.Popen = _refus_executable
        shutil.which = _refus_executable
        self.addCleanup(setattr, subprocess, "Popen", popen)
        self.addCleanup(setattr, shutil, "which", which)


class ExecutionAcquisitionR5Tests(_BaseExecutionR5):
    def _acquerir_grok_avec_usage(self, model_usage: dict | None) -> dict:
        enveloppe = {
            "text": _sortie_acceptable(),
            "stopReason": "end_turn",
            "sessionId": "session-locale-grok",
            "requestId": "requete-locale-grok",
        }
        if model_usage is not None:
            enveloppe["modelUsage"] = model_usage
        chemin_enveloppe = self.racine / "sortie-grok-usage.json"
        chemin_enveloppe.write_text(
            json.dumps(enveloppe, ensure_ascii=False), encoding="utf-8"
        )
        self._double(
            "grok",
            "#!/bin/sh\n"
            f'cat "{chemin_enveloppe}"\n',
        )
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "grok-build-grok-4-6",
            ]
        )
        self.assertEqual(code, 0, sortie)
        adresse = next(
            ligne.split(" : ", 1)[1]
            for ligne in sortie.splitlines()
            if ligne.startswith("adresse de contenu : ")
        )
        return json.loads(
            (
                self.racine / _CAMPAGNE / "recus-v1" / f"{adresse}.json"
            ).read_text(encoding="utf-8")
        )

    def _verifier_terminal_codex_fatal(self, terminal: dict) -> None:
        resultat = _sortie_acceptable()
        enveloppe = "\n".join(
            (
                json.dumps({"type": "thread.started", "thread_id": "t-fatal"}),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "item-avant-erreur",
                            "type": "agent_message",
                            "text": resultat,
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(terminal, ensure_ascii=False),
            )
        )
        chemin_enveloppe = self.racine / "erreur-codex.jsonl"
        chemin_enveloppe.write_text(enveloppe, encoding="utf-8")
        self._double(
            "codex",
            "#!/bin/sh\n"
            "cat > /dev/null\n"
            f'cat "{chemin_enveloppe}"\n'
            "exit 1\n",
        )
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "codex-gpt-5-6-sol",
            ]
        )
        self.assertEqual(code, 0, sortie)
        self.assertIn("état terminal : HARNESS_ERROR", sortie)
        adresse = next(
            ligne.split(" : ", 1)[1]
            for ligne in sortie.splitlines()
            if ligne.startswith("adresse de contenu : ")
        )
        recu = json.loads(
            (
                self.racine / _CAMPAGNE / "recus-v1" / f"{adresse}.json"
            ).read_text(encoding="utf-8")
        )
        execution = recu["payload"]["execution"]
        self.assertEqual(execution["incident"], "HARNESS_ERROR")
        self.assertIn("échec Codex terminal", execution["fait"])
        brut_prive = (
            self._espace_tentative("ACQ-V1-CODEX-GPT-5-6-SOL-001")
            / "sortie-stdout.txt"
        ).read_text(encoding="utf-8")
        self.assertEqual(brut_prive, enveloppe)
        self.assertEqual(self._valider(), 0)
        registre = json.loads(
            (self.racine / M.CHEMIN_REGISTRE_VALIDATION).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registre["entrees"][0]["sortie_candidate"], "ABSENTE")
        self.assertIsNone(registre["entrees"][0]["verdict"])
        code, sortie = self._appeler(["dossiers"])
        self.assertEqual(code, 0, sortie)
        manifeste = json.loads(
            (self.racine / M.CHEMIN_MANIFESTE_DOSSIERS).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifeste["dossiers"], [])

    def test_projection_identite_markdown_concordante_divergente_et_absente(self):
        brut = "# Résultat\n\nmodel: claude-fable-5\n"
        projection = M._projeter_sortie_harnais(
            brut, "", ("claude-fable-5",)
        )
        self.assertEqual(
            projection["identite_servie"]["statut"], "OBSERVED"
        )
        self.assertEqual(projection["modele"], "claude-fable-5")
        self.assertEqual(projection["sortie_candidate"], brut)

        projection = M._projeter_sortie_harnais(
            "model: claude-opus-5\n", "", ("claude-fable-5",)
        )
        self.assertEqual(
            projection["identite_servie"]["incident"],
            "IDENTITY_MISMATCH",
        )
        self.assertEqual(projection["modele"], "claude-opus-5")

        projection = M._projeter_sortie_harnais(
            "# Résultat sans métadonnée\n", "", ("claude-fable-5",)
        )
        self.assertEqual(
            projection["identite_servie"]["statut"], "INCONNU"
        )
        self.assertIsNone(projection["identite_servie"]["incident"])

    def test_projection_tableau_json_claude_first_party_et_resultat_terminal(self):
        resultat = "# Livrable\n\nmodel: contenu-candidat-ignore\n"
        enveloppe = json.dumps(
            [
                {
                    "type": "system",
                    "subtype": "init",
                    "model": "claude-fable-5",
                },
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "text",
                                "text": '{"model":"contenu-ignore"}',
                            }
                        ]
                    },
                },
                {
                    "type": "result",
                    "subtype": "success",
                    "result": resultat,
                    "modelUsage": {
                        "claude-fable-5": {
                            "canonicalModel": "claude-fable-5",
                            "provider": "firstParty",
                        }
                    },
                },
            ],
            ensure_ascii=False,
        )
        projection = M._projeter_sortie_harnais(
            enveloppe, "", ("claude-fable-5",)
        )
        self.assertEqual(
            projection["identite_servie"]["statut"], "OBSERVED"
        )
        self.assertEqual(projection["sortie_candidate"], resultat)
        self.assertEqual(
            {preuve["source"] for preuve in projection["provenances"]},
            {
                "system/init.model",
                "result.modelUsage.claude-fable-5.canonicalModel",
            },
        )
        self.assertNotIn("contenu-ignore", projection["preuve"])
        self.assertNotIn("contenu-candidat-ignore", projection["preuve"])

    def test_projection_jsonl_cursor_et_conflit_interne(self):
        resultat = "# Résultat Cursor\n"
        jsonl = "\n".join(
            (
                json.dumps(
                    {
                        "type": "system",
                        "subtype": "init",
                        "model": "kimi-k3-high",
                    }
                ),
                json.dumps({"type": "result", "result": resultat}),
            )
        )
        projection = M._projeter_sortie_harnais(
            jsonl, "", ("kimi-k3-high",)
        )
        self.assertEqual(
            projection["identite_servie"]["statut"], "OBSERVED"
        )
        self.assertEqual(projection["sortie_candidate"], resultat)

        conflit = json.dumps(
            [
                {
                    "type": "system",
                    "subtype": "init",
                    "model": "claude-fable-5",
                },
                {
                    "type": "result",
                    "result": resultat,
                    "modelUsage": {
                        "autre": {
                            "canonicalModel": "claude-opus-5",
                            "provider": "firstParty",
                        }
                    },
                },
            ]
        )
        projection = M._projeter_sortie_harnais(
            conflit, "", ("claude-fable-5",)
        )
        self.assertEqual(
            projection["identite_servie"]["incident"],
            "IDENTITY_MISMATCH",
        )
        self.assertIn("conflit interne", projection["identite_servie"]["cause"])

    def test_json_candidat_ordinaire_et_metadata_non_first_party_sont_ignores(self):
        candidat = '{"model":"modele-dans-le-contenu","reponse":"ok"}\n'
        projection = M._projeter_sortie_harnais(
            candidat, "", ("modele-dans-le-contenu",)
        )
        self.assertEqual(
            projection["identite_servie"]["statut"], "INCONNU"
        )
        self.assertEqual(projection["sortie_candidate"], candidat)

        enveloppe = json.dumps(
            {
                "type": "result",
                "result": "résultat",
                "modelUsage": {
                    "modele": {
                        "canonicalModel": "modele-tiers",
                        "provider": "thirdParty",
                    }
                },
            }
        )
        projection = M._projeter_sortie_harnais(
            enveloppe, "", ("modele-tiers",)
        )
        self.assertEqual(
            projection["identite_servie"]["statut"], "INCONNU"
        )
        self.assertEqual(projection["sortie_candidate"], "résultat")

    def test_valider_et_dossiers_partagent_le_resultat_terminal_structure(self):
        resultat = _sortie_acceptable()
        enveloppe = json.dumps(
            [
                {
                    "type": "system",
                    "subtype": "init",
                    "model": "claude-fable-5",
                },
                {
                    "type": "result",
                    "subtype": "success",
                    "result": resultat,
                    "modelUsage": {
                        "claude-fable-5": {
                            "canonicalModel": "claude-fable-5",
                            "provider": "firstParty",
                        }
                    },
                },
            ],
            ensure_ascii=False,
        )
        chemin_enveloppe = self.racine / "sortie-claude.json"
        chemin_enveloppe.write_text(enveloppe, encoding="utf-8")
        self._double(
            "claude",
            "#!/bin/sh\n"
            "cat > /dev/null\n"
            f'cat "{chemin_enveloppe}"\n',
        )
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "claude-code-fable-5",
            ]
        )
        self.assertEqual(code, 0, sortie)
        adresse = next(
            ligne.split(" : ", 1)[1]
            for ligne in sortie.splitlines()
            if ligne.startswith("adresse de contenu : ")
        )
        chemin_recu = self.racine / _CAMPAGNE / "recus-v1" / f"{adresse}.json"
        recu = json.loads(chemin_recu.read_text(encoding="utf-8"))
        self.assertEqual(
            recu["payload"]["completion"]["identite_servie"]["statut"],
            "OBSERVED",
        )
        self.assertEqual(
            recu["payload"]["provenance_servie"]["valeur"],
            {"modele": "claude-fable-5"},
        )
        self.assertEqual(
            recu["payload"]["execution"]["sortie"]["stdout"], enveloppe
        )

        self.assertEqual(self._valider(), 0)
        registre = json.loads(
            (self.racine / M.CHEMIN_REGISTRE_VALIDATION).read_text(
                encoding="utf-8"
            )
        )
        verdict = registre["entrees"][0]["verdict"]
        self.assertEqual(verdict["statut"], "PASS")
        self.assertEqual(
            verdict["empreinte_candidate"],
            hashlib.sha256(resultat.encode("utf-8")).hexdigest(),
        )
        code, sortie = self._appeler(["dossiers"])
        self.assertEqual(code, 0, sortie)
        manifeste = json.loads(
            (self.racine / M.CHEMIN_MANIFESTE_DOSSIERS).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(manifeste["dossiers"]), 1)
        dossier = (self.racine / manifeste["dossiers"][0]["fichier"]).read_text(
            encoding="utf-8"
        )
        self.assertIn(resultat, dossier)
        self.assertNotIn("system/init.model", dossier)

    def test_grok_json_traverse_acquisition_validation_et_dossier(self):
        resultat = _sortie_acceptable()
        enveloppe = json.dumps(
            {
                "text": resultat,
                "stopReason": "end_turn",
                "sessionId": "session-locale-grok",
                "requestId": "requete-locale-grok",
                "modelUsage": {
                    "grok-4.6-build": {
                        "modelCalls": 1,
                        "inputTokens": 10,
                        "outputTokens": 20,
                    }
                },
            },
            ensure_ascii=False,
        )
        chemin_enveloppe = self.racine / "sortie-grok.json"
        chemin_enveloppe.write_text(enveloppe, encoding="utf-8")
        self._double(
            "grok",
            "#!/bin/sh\n"
            f'cat "{chemin_enveloppe}"\n',
        )
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "grok-build-grok-4-6",
            ]
        )
        self.assertEqual(code, 0, sortie)
        adresse = next(
            ligne.split(" : ", 1)[1]
            for ligne in sortie.splitlines()
            if ligne.startswith("adresse de contenu : ")
        )
        recu = json.loads(
            (
                self.racine / _CAMPAGNE / "recus-v1" / f"{adresse}.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            recu["payload"]["execution"]["sortie"]["stdout"], enveloppe
        )
        self.assertEqual(
            recu["payload"]["completion"]["identite_servie"]["statut"],
            "OBSERVED",
        )
        self.assertEqual(
            recu["payload"]["provenance_servie"]["valeur"],
            {"modele": "grok-4.6-build"},
        )
        self.assertEqual(self._valider(), 0)
        registre = json.loads(
            (self.racine / M.CHEMIN_REGISTRE_VALIDATION).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registre["entrees"][0]["verdict"]["statut"], "PASS")
        code, sortie = self._appeler(["dossiers"])
        self.assertEqual(code, 0, sortie)
        manifeste = json.loads(
            (self.racine / M.CHEMIN_MANIFESTE_DOSSIERS).read_text(
                encoding="utf-8"
            )
        )
        dossier = (self.racine / manifeste["dossiers"][0]["fichier"]).read_text(
            encoding="utf-8"
        )
        self.assertIn(resultat, dossier)
        self.assertNotIn('"modelUsage"', dossier)

    def test_grok_json_error_devient_harness_error_sans_candidat(self):
        enveloppe = json.dumps(
            {"type": "error", "message": "échec local Grok attribuable"},
            ensure_ascii=False,
        )
        chemin_enveloppe = self.racine / "erreur-grok.json"
        chemin_enveloppe.write_text(enveloppe, encoding="utf-8")
        self._double(
            "grok",
            "#!/bin/sh\n"
            f'cat "{chemin_enveloppe}"\n',
        )
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "grok-build-grok-4-6",
            ]
        )
        self.assertEqual(code, 0, sortie)
        self.assertIn("état terminal : HARNESS_ERROR", sortie)
        adresse = next(
            ligne.split(" : ", 1)[1]
            for ligne in sortie.splitlines()
            if ligne.startswith("adresse de contenu : ")
        )
        recu = json.loads(
            (
                self.racine / _CAMPAGNE / "recus-v1" / f"{adresse}.json"
            ).read_text(encoding="utf-8")
        )
        execution = recu["payload"]["execution"]
        self.assertEqual(execution["incident"], "HARNESS_ERROR")
        self.assertIn("échec local Grok attribuable", execution["fait"])
        brut_prive = (
            self._espace_tentative("ACQ-V1-GROK-BUILD-GROK-4-6-001")
            / "sortie-stdout.txt"
        ).read_text(encoding="utf-8")
        self.assertEqual(brut_prive, enveloppe)
        self.assertEqual(self._valider(), 0)
        registre = json.loads(
            (self.racine / M.CHEMIN_REGISTRE_VALIDATION).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registre["entrees"][0]["sortie_candidate"], "ABSENTE")
        self.assertIsNone(registre["entrees"][0]["verdict"])
        code, sortie = self._appeler(["dossiers"])
        self.assertEqual(code, 0, sortie)
        manifeste = json.loads(
            (self.racine / M.CHEMIN_MANIFESTE_DOSSIERS).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifeste["dossiers"], [])

    def test_grok_sans_model_usage_conserve_identite_inconnue(self):
        recu = self._acquerir_grok_avec_usage(None)
        self.assertEqual(
            recu["payload"]["completion"]["identite_servie"]["statut"],
            "INCONNU",
        )

    def test_grok_model_usage_vide_conserve_identite_inconnue(self):
        recu = self._acquerir_grok_avec_usage({})
        self.assertEqual(
            recu["payload"]["completion"]["identite_servie"]["statut"],
            "INCONNU",
        )

    def test_grok_model_usage_multiple_conserve_identite_inconnue(self):
        recu = self._acquerir_grok_avec_usage(
            {
                "grok-4.6-build": {"modelCalls": 1},
                "grok-4.6": {"modelCalls": 1},
            }
        )
        self.assertEqual(
            recu["payload"]["completion"]["identite_servie"]["statut"],
            "INCONNU",
        )

    def test_grok_sans_appel_modele_positif_conserve_identite_inconnue(self):
        recu = self._acquerir_grok_avec_usage(
            {"grok-4.6-build": {"modelCalls": 0}}
        )
        self.assertEqual(
            recu["payload"]["completion"]["identite_servie"]["statut"],
            "INCONNU",
        )

    def test_codex_jsonl_traverse_acquisition_validation_et_dossier(self):
        resultat = _sortie_acceptable()
        enveloppe = "\n".join(
            (
                json.dumps({"type": "thread.started", "thread_id": "t-1"}),
                json.dumps({"type": "turn.started"}),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "item-erreur-non-terminale",
                            "type": "error",
                            "message": "erreur d'item non fatale",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "item-1",
                            "type": "agent_message",
                            "text": "brouillon non terminal",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "item-2",
                            "type": "agent_message",
                            "text": resultat,
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {"input_tokens": 10, "output_tokens": 20},
                        "modelUsage": {
                            "gpt-5.6-sol": {"modelCalls": 1}
                        },
                    }
                ),
            )
        )
        chemin_enveloppe = self.racine / "sortie-codex.jsonl"
        chemin_enveloppe.write_text(enveloppe, encoding="utf-8")
        self._double(
            "codex",
            "#!/bin/sh\n"
            "cat > /dev/null\n"
            f'cat "{chemin_enveloppe}"\n',
        )
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "codex-gpt-5-6-sol",
            ]
        )
        self.assertEqual(code, 0, sortie)
        adresse = next(
            ligne.split(" : ", 1)[1]
            for ligne in sortie.splitlines()
            if ligne.startswith("adresse de contenu : ")
        )
        recu = json.loads(
            (
                self.racine / _CAMPAGNE / "recus-v1" / f"{adresse}.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            recu["payload"]["execution"]["sortie"]["stdout"], enveloppe
        )
        self.assertEqual(
            recu["payload"]["completion"]["identite_servie"]["statut"],
            "INCONNU",
        )
        self.assertEqual(recu["payload"]["provenance_servie"], "INCONNU")
        self.assertEqual(self._valider(), 0)
        registre = json.loads(
            (self.racine / M.CHEMIN_REGISTRE_VALIDATION).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registre["entrees"][0]["verdict"]["statut"], "PASS")
        code, sortie = self._appeler(["dossiers"])
        self.assertEqual(code, 0, sortie)
        manifeste = json.loads(
            (self.racine / M.CHEMIN_MANIFESTE_DOSSIERS).read_text(
                encoding="utf-8"
            )
        )
        dossier = (self.racine / manifeste["dossiers"][0]["fichier"]).read_text(
            encoding="utf-8"
        )
        self.assertIn(resultat, dossier)
        self.assertNotIn("thread.started", dossier)
        self.assertNotIn("brouillon non terminal", dossier)

    def test_codex_top_level_error_est_fatal_apres_un_message_agent(self):
        self._verifier_terminal_codex_fatal(
            {"type": "error", "message": "échec Codex terminal"}
        )

    def test_codex_turn_failed_est_fatal_apres_un_message_agent(self):
        self._verifier_terminal_codex_fatal(
            {
                "type": "turn.failed",
                "error": {"message": "échec Codex terminal"},
            }
        )

    def test_cinq_acquisitions_pass_traversent_toute_la_chaine(self):
        self._doubles_pass()
        adresses: dict[str, str] = {}
        for identifiant, acquisition_id in CRENEAUX_COMPLETION:
            code, sortie = self._appeler(
                ["acquerir", "--completion", "--configuration", identifiant]
            )
            self.assertEqual(code, 0, sortie)
            self.assertIn(
                "route_execution PRETE_POUR_TENTATIVE_AUTORISEE", sortie
            )
            self.assertIn("état terminal : OBSERVED", sortie)
            self.assertIn("descendants survivants : 0", sortie)
            adresse = next(
                ligne.split(" : ", 1)[1]
                for ligne in sortie.splitlines()
                if ligne.startswith("adresse de contenu : ")
            )
            adresses[identifiant] = adresse
            enveloppe = json.loads(
                (
                    self.racine / _CAMPAGNE / "recus-v1" / f"{adresse}.json"
                ).read_text(encoding="utf-8")
            )
            charge = enveloppe["payload"]
            self.assertEqual(
                charge["creneau"],
                f"{identifiant}:{self.stimulus_sha}:{acquisition_id}",
            )
            self.assertEqual(
                charge["completion"]["acquisition_id"], acquisition_id
            )
            self.assertEqual(charge["completion"]["tranche"], "V1-R5")
            self.assertEqual(
                charge["requete"]["argv_resolu"],
                list(M.DESCRIPTEURS_COMPLETION_R5[identifiant]),
            )
            self.assertEqual(
                charge["requete"]["mode_stdin"],
                M.TRANSPORTS_COMPLETION_R5[identifiant],
            )
            # Transport réellement observé par le double local
            espace = self._espace_tentative(acquisition_id) / "espace"
            # Enregistrements NUL-séparés : le dernier séparateur produit
            # une queue vide, retirée sans toucher aux arguments réels
            argv_capture = (
                (espace / "capture-argv.txt").read_bytes().split(b"\0")[:-1]
            )
            stdin_capture = (espace / "capture-stdin.txt").read_bytes()
            transport = M.TRANSPORTS_COMPLETION_R5[identifiant]
            if transport == "stdin":
                self.assertEqual(stdin_capture, self.stimulus_octets)
                self.assertNotIn(self.stimulus_octets, argv_capture)
            elif transport == "argument":
                self.assertEqual(stdin_capture, b"")
                self.assertEqual(argv_capture[-1], self.stimulus_octets)
            else:
                self.assertEqual(stdin_capture, b"")
                self.assertEqual(
                    (espace / "stimulus.md").read_bytes(),
                    self.stimulus_octets,
                )
                self.assertIn(b"--prompt-file", argv_capture)
            self.assertIn(b"--model", argv_capture)
        self.assertEqual(self._valider(), 0)
        registre = json.loads(
            (self.racine / M.CHEMIN_REGISTRE_VALIDATION).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(registre["couverture"]["verdicts"]["PASS"], 5)
        code, sortie = self._appeler(["etat"])
        self.assertEqual(code, 0, sortie)
        code, sortie = self._appeler(["dossiers"])
        self.assertEqual(code, 0, sortie)
        manifeste = json.loads(
            (
                self.racine
                / _CAMPAGNE
                / "dossiers-revue-aveugle-v1"
                / "manifeste-dossiers.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(len(manifeste["dossiers"]), 5)
        engagement = json.loads(
            (
                self.racine
                / _CAMPAGNE
                / "dossiers-revue-aveugle-v1"
                / "engagement-ordre.json"
            ).read_text(encoding="utf-8")
        )
        # L'ordre engagé couvre le lot verrouillé complet : deux créneaux
        # historiques et cinq créneaux de complétion, items opaques du même
        # domaine ITEM-NNN, correspondance scellée jamais publiée
        self.assertEqual(engagement["cardinalite_revue"], 7)
        items = [entree["item"] for entree in engagement["ordre_revue"]]
        self.assertEqual(len(set(items)), 7)
        for item in items:
            self.assertRegex(item, r"^ITEM-\d{3}$")
        jetons_interdits = [b"ACQ-V1-", b"claude", b"codex", b"kimi", b"grok"]
        for entree in manifeste["dossiers"]:
            contenu = (self.racine / entree["fichier"]).read_bytes()
            self.assertIn(self.stimulus_octets, contenu)
            for identifiant, _ in CRENEAUX_COMPLETION:
                self.assertNotIn(identifiant.encode("utf-8"), contenu)
            for jeton in jetons_interdits:
                self.assertNotIn(jeton, contenu)
        code, sortie = self._appeler(["metriques"])
        self.assertEqual(code, 0, sortie)
        code, sortie = self._appeler(["restituer"])
        self.assertEqual(code, 0, sortie)
        code, sortie = self._appeler(["verifier-restitution"])
        self.assertEqual(code, 0, sortie)
        # Seconde invocation du même créneau : refusée avant tout processus
        self._sans_processus()
        avant = {
            chemin.name
            for chemin in (self.racine / _CAMPAGNE / "recus-v1").iterdir()
        }
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "claude-code-fable-5",
            ]
        )
        self.assertEqual(code, 2, sortie)
        self.assertIn("aucun retry", sortie)
        self.assertEqual(
            {
                chemin.name
                for chemin in (
                    self.racine / _CAMPAGNE / "recus-v1"
                ).iterdir()
            },
            avant,
        )

    def test_autorite_alteree_et_verrou_divergent_rendent_deux_sans_processus(
        self,
    ):
        self._sans_processus()
        chemin_autorisation = (
            self.racine / M.CHEMIN_AUTORISATION_COMPLETION
        )
        autorisation = json.loads(
            chemin_autorisation.read_text(encoding="utf-8")
        )
        autorisation["portee"]["appels_fournisseur_max"] = 6
        chemin_autorisation.write_bytes(M.octets_canoniques(autorisation))
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "claude-code-fable-5",
            ]
        )
        self.assertEqual(code, 2, sortie)
        self.assertIn("portee.appels_fournisseur_max", sortie)
        self.assertIn("aucun processus fournisseur", sortie)
        chemin_autorisation.write_bytes(
            M.octets_canoniques(M._structure_autorisation_completion())
        )
        chemin_verrou = self.racine / M.CHEMIN_VERROU_COMPLETION
        chemin_verrou.write_bytes(chemin_verrou.read_bytes() + b"\n")
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "claude-code-fable-5",
            ]
        )
        self.assertEqual(code, 2, sortie)
        self.assertIn("verrou R4", sortie)
        self.assertIn("LOCKED_ARTIFACT_CHANGED", sortie)

    def test_quota_inconnu_ne_bloque_pas_et_forme_invalide_fail_closed(self):
        formulaire = (
            self.privee
            / "campagne-v1"
            / "v1-r5"
            / "observations-abonnements.toml"
        )
        formulaire.parent.mkdir(parents=True, exist_ok=True)
        formulaire.write_text(
            "[[observation]]\n"
            'produit = "ANTHROPIC"\n'
            'observe_le = "INCONNU"\n'
            'surface = "CLAUDE_SETTINGS_USAGE"\n'
            'plan = "INCONNU"\n'
            'quota_5h_restant = "INCONNU"\n'
            'quota_hebdomadaire_restant = "INCONNU"\n'
            'reset_5h = "INCONNU"\n'
            'reset_hebdomadaire = "INCONNU"\n'
            'depassement_payant = "INCONNU"\n',
            encoding="utf-8",
        )
        self._doubles_pass()
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "claude-code-fable-5",
            ]
        )
        self.assertEqual(code, 0, sortie)
        self.assertIn(
            "route_execution PRETE_POUR_TENTATIVE_AUTORISEE", sortie
        )
        self.assertIn("telemetrie_abonnement", sortie)
        self.assertIn("OBSERVED", sortie)
        # Forme invalide : clé inconnue, refus fail-closed avant processus
        self._sans_processus()
        formulaire.write_text(
            "[[observation]]\n"
            'produit = "OPENAI"\n'
            'cle_inconnue = "x"\n',
            encoding="utf-8",
        )
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "codex-gpt-5-6-sol",
            ]
        )
        self.assertEqual(code, 2, sortie)
        self.assertIn("clés exactes", sortie)

    def test_quota_exhausted_exige_une_erreur_structuree_attribuable(self):
        # Erreur structurée explicite : incident QUOTA_EXHAUSTED attribuable
        self._double(
            "claude",
            "#!/bin/sh\n"
            "cat > /dev/null\n"
            'printf \'%s\\n\' \'{"error":{"code":"quota_exhausted",'
            '"message":"exhausted"}}\' >&2\n'
            "exit 1\n",
        )
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "claude-code-fable-5",
            ]
        )
        self.assertEqual(code, 0, sortie)
        self.assertIn("état terminal : QUOTA_EXHAUSTED", sortie)
        adresse = next(
            ligne.split(" : ", 1)[1]
            for ligne in sortie.splitlines()
            if ligne.startswith("adresse de contenu : ")
        )
        enveloppe = json.loads(
            (
                self.racine / _CAMPAGNE / "recus-v1" / f"{adresse}.json"
            ).read_text(encoding="utf-8")
        )
        execution = enveloppe["payload"]["execution"]
        self.assertEqual(execution["incident"], "QUOTA_EXHAUSTED")
        self.assertIn("quota_exhausted", execution["preuve_attribuable"])
        # Échec sans erreur structurée : jamais QUOTA_EXHAUSTED, incident
        # HARNESS_ERROR du dispositif local
        self._double(
            "codex",
            "#!/bin/sh\n"
            "cat > /dev/null\n"
            "printf 'quota probablement fini\\n' >&2\n"
            "exit 1\n",
        )
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "codex-gpt-5-6-sol",
            ]
        )
        self.assertEqual(code, 0, sortie)
        self.assertIn("état terminal : HARNESS_ERROR", sortie)
        self.assertNotIn("QUOTA_EXHAUSTED", sortie)

    def test_verdict_non_pass_ne_produit_aucun_dossier(self):
        self._double(
            "grok",
            "#!/bin/sh\n"
            "cat > /dev/null\n"
            "printf 'sortie candidate hors contrat\\n'\n",
        )
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "grok-build-grok-4-6",
            ]
        )
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self._valider(), 0)
        code, sortie = self._appeler(["dossiers"])
        self.assertEqual(code, 0, sortie)
        manifeste = json.loads(
            (
                self.racine
                / _CAMPAGNE
                / "dossiers-revue-aveugle-v1"
                / "manifeste-dossiers.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(manifeste["dossiers"], [])
        self.assertEqual(
            manifeste["lot_vide"]["cause"], "aucune_sortie_pass"
        )

    def test_objets_prives_r5_en_0600_et_repertoires_en_0700(self):
        # umask permissif : les modes doivent être forcés par le code, pas
        # hérités du processus de test
        umask_origine = os.umask(0)
        self.addCleanup(os.umask, umask_origine)
        self._doubles_pass()
        code, sortie = self._appeler(
            [
                "acquerir",
                "--completion",
                "--configuration",
                "grok-build-grok-4-6",
            ]
        )
        self.assertEqual(code, 0, sortie)

        def mode(chemin: Path) -> int:
            return stat.S_IMODE(os.lstat(chemin).st_mode)

        racine_r5 = self.privee / "v1-execution" / "r5"
        espace_tentative = self._espace_tentative(
            "ACQ-V1-GROK-BUILD-GROK-4-6-001"
        )
        espace = espace_tentative / "espace"
        for repertoire in (
            racine_r5,
            racine_r5 / "runtime",
            espace_tentative,
            espace,
        ):
            self.assertEqual(mode(repertoire), 0o700, repertoire)
        for fichier in (
            espace_tentative / "sortie-stdout.txt",
            espace_tentative / "sortie-stderr.txt",
            espace / "stimulus.md",
            racine_r5 / "execution-journal.json",
        ):
            self.assertEqual(mode(fichier), 0o600, fichier)


class HeadlessRecoveryR5Tests(_BaseExecutionR5):
    """Amendement append-only H3 : quatre créneaux -002 isolés."""

    CRENEAUX = (
        ("claude-code-fable-5", "ACQ-V1-CLAUDE-CODE-FABLE-5-002"),
        ("codex-gpt-5-6-sol", "ACQ-V1-CODEX-GPT-5-6-SOL-002"),
        ("cursor-kimi-k3", "ACQ-V1-CURSOR-KIMI-K3-002"),
        ("grok-build-grok-4-6", "ACQ-V1-GROK-BUILD-GROK-4-6-002"),
    )

    def _preparer(self) -> Path:
        code, sortie = self._appeler(["preparer-recuperation-headless"])
        self.assertEqual(code, 0, sortie)
        return self.racine / M.CHEMIN_AUTORISATION_RECUPERATION_HEADLESS

    def _acquerir(self, configuration_id: str) -> tuple[int, str]:
        return self._appeler([
            "acquerir", "--recuperation-headless", "--configuration",
            configuration_id,
        ])

    def test_preparer_materialise_quatre_descripteurs_corriges_canoniques(self):
        chemin = self._preparer()
        autorisation = json.loads(chemin.read_text(encoding="utf-8"))
        self.assertEqual(chemin.read_bytes(), M.octets_canoniques(autorisation))
        self.assertEqual(autorisation["jeton"], M.JETON_RECUPERATION_HEADLESS)
        self.assertEqual(
            [(e["configuration_id"], e["acquisition_id"])
             for e in autorisation["portee"]["acquisitions"]],
            list(self.CRENEAUX),
        )
        self.assertEqual(autorisation["portee"]["appels_fournisseur_max"], 4)
        self.assertEqual(autorisation["portee"]["reprises"], 0)
        self.assertEqual(autorisation["portee"]["fallback"], "NONE")
        self.assertEqual(autorisation["portee"]["overage"], "INTERDIT")
        descripteurs = autorisation["descripteurs"]
        self.assertIn("--restricted", descripteurs["claude-code-fable-5"]["argv"])
        self.assertIn("dontAsk", descripteurs["claude-code-fable-5"]["argv"])
        self.assertEqual(descripteurs["cursor-kimi-k3"]["stimulus_utf8"], "stdin")
        self.assertNotIn(M.JETON_STIMULUS_UTF8, descripteurs["cursor-kimi-k3"]["argv"])
        self.assertEqual(
            descripteurs["codex-gpt-5-6-sol"]["argv"][:4],
            ["codex", "--strict-config", "--ask-for-approval", "never"],
        )
        self.assertIn("--skip-git-repo-check", descripteurs["codex-gpt-5-6-sol"]["argv"])
        self.assertIn("--no-auto-update", descripteurs["grok-build-grok-4-6"]["argv"])
        self.assertIn("dontAsk", descripteurs["grok-build-grok-4-6"]["argv"])
        for configuration_id, _ in self.CRENEAUX:
            tentative = M.construire_tentative_completion_r5(
                configuration_id,
                self.stimulus_octets,
                "/bac/headless",
                M.DESCRIPTEURS_RECUPERATION_HEADLESS,
                M.TRANSPORTS_RECUPERATION_HEADLESS,
            )
            if configuration_id == "grok-build-grok-4-6":
                self.assertIsNone(tentative["stdin"])
                self.assertEqual(
                    tentative["fichier_prompt"]["stimulus_utf8"],
                    self.stimulus_octets,
                )
            else:
                self.assertEqual(tentative["stdin"], self.stimulus_octets)
                self.assertIsNone(tentative["fichier_prompt"])

    def test_recuperation_ecrit_journal_separe_et_selectionne_002_par_id(self):
        self._doubles_pass()
        code, sortie = self._appeler([
            "acquerir", "--completion", "--configuration", "claude-code-fable-5",
        ])
        self.assertEqual(code, 0, sortie)
        ancien = next(
            enveloppe for _, enveloppe in M._charger_recus(
                self.racine / _CAMPAGNE / "recus-v1"
            ) if enveloppe["payload"].get("completion")
        )
        ancien_sha = ancien["content_address"]["sha256"]
        self._preparer()
        code, sortie = self._acquerir("claude-code-fable-5")
        self.assertEqual(code, 0, sortie)
        self.assertIn("ACQ-V1-CLAUDE-CODE-FABLE-5-002", sortie)
        historique = self.privee / "v1-execution" / "r5" / "execution-journal.json"
        recuperation = self.privee / "v1-execution" / "r5-headless-recovery" / "execution-journal.json"
        self.assertEqual(json.loads(historique.read_text())["entrees"][0]["acquisition_id"], "ACQ-V1-CLAUDE-CODE-FABLE-5-001")
        self.assertEqual(json.loads(recuperation.read_text())["entrees"][0]["acquisition_id"], "ACQ-V1-CLAUDE-CODE-FABLE-5-002")
        tous = M._charger_recus(self.racine / _CAMPAGNE / "recus-v1")
        self.assertIn(ancien_sha, [r["content_address"]["sha256"] for _, r in tous])
        _, courants = M._partitionner_recus(self.racine, M._charger_etat(self.racine))
        fable = [r for _, r, _ in courants if r["payload"]["configuration"]["identifiant"] == "claude-code-fable-5"]
        self.assertEqual(len(fable), 1)
        self.assertEqual(fable[0]["payload"]["recuperation_headless"]["acquisition_id"], "ACQ-V1-CLAUDE-CODE-FABLE-5-002")

    def test_quota_kimi_structure_terminal_n_empeche_pas_grok(self):
        self._preparer()
        self._double(
            "agent",
            "#!/bin/sh\ncat > /dev/null\nprintf '%s\\n' '{\"error\":{\"code\":\"quota_exhausted\",\"message\":\"epuise\"}}' >&2\nexit 1\n",
        )
        code, sortie = self._acquerir("cursor-kimi-k3")
        self.assertEqual(code, 0, sortie)
        self.assertIn("état terminal : QUOTA_EXHAUSTED", sortie)
        self._doubles_pass()
        code, sortie = self._acquerir("grok-build-grok-4-6")
        self.assertEqual(code, 0, sortie)
        self.assertIn("ACQ-V1-GROK-BUILD-GROK-4-6-002", sortie)

    def test_kimi_texte_libre_de_quota_reste_harness_error(self):
        self._preparer()
        self._double(
            "agent",
            "#!/bin/sh\ncat > /dev/null\nprintf 'quota probablement fini\\n' >&2\nexit 1\n",
        )
        code, sortie = self._acquerir("cursor-kimi-k3")
        self.assertEqual(code, 0, sortie)
        self.assertIn("état terminal : HARNESS_ERROR", sortie)
        self.assertNotIn("état terminal : QUOTA_EXHAUSTED", sortie)

    def test_opus_reste_hors_ligne_sur_001_et_hors_des_creneaux(self):
        self._doubles_pass()
        code, sortie = self._appeler([
            "acquerir", "--completion", "--configuration", "claude-code-opus-5",
        ])
        self.assertEqual(code, 0, sortie)
        self._preparer()
        avant = len(M._charger_recus(self.racine / _CAMPAGNE / "recus-v1"))
        code, sortie = self._acquerir("claude-code-opus-5")
        self.assertEqual(code, 2, sortie)
        self.assertIn("hors de la portée", sortie)
        self.assertEqual(len(M._charger_recus(self.racine / _CAMPAGNE / "recus-v1")), avant)

    def test_gel_vide_historique_reste_immuable_apres_lot_courant_vide(self):
        self.assertEqual(self._valider(), 0)
        self.assertEqual(self._appeler(["dossiers"])[0], 0)
        code, sortie = self._appeler(["geler"])
        self.assertEqual(code, 0, sortie)
        chemin_gel = self.racine / M.CHEMIN_GEL_VERDICTS
        octets_gel = chemin_gel.read_bytes()
        gel_historique = json.loads(octets_gel)
        comptage_historique = gel_historique["lot_vide"]["comptage_statuts"]

        self._preparer()
        script_non_eligible = (
            "#!/bin/sh\ncat > /dev/null\nprintf 'sortie hors contrat\\n'\n"
        )
        for executable in ("claude", "codex", "agent", "grok"):
            self._double(executable, script_non_eligible)
        for configuration_id, _ in self.CRENEAUX:
            code, sortie = self._acquerir(configuration_id)
            self.assertEqual(code, 0, sortie)
        self.assertEqual(self._valider(), 0)
        self.assertEqual(self._appeler(["dossiers"])[0], 0)
        manifeste = json.loads(
            (self.racine / M.CHEMIN_MANIFESTE_DOSSIERS).read_text()
        )
        self.assertEqual(manifeste["dossiers"], [])
        comptage_courant = manifeste["lot_vide"]["comptage_statuts"]
        self.assertNotEqual(comptage_courant, comptage_historique)

        for commande in (["etat"], ["metriques"], ["restituer"], ["verifier-restitution"]):
            code, sortie = self._appeler(commande)
            self.assertEqual(code, 0, f"{commande}: {sortie}")
        self.assertEqual(chemin_gel.read_bytes(), octets_gel)
        page = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        self.assertIn(
            json.dumps(comptage_courant, sort_keys=True).replace('"', "&quot;"),
            page,
        )
        self.assertNotIn(
            json.dumps(comptage_historique, sort_keys=True).replace('"', "&quot;"),
            page,
        )

    def test_gel_vide_historique_refuse_un_lot_courant_non_vide(self):
        self.assertEqual(self._valider(), 0)
        self.assertEqual(self._appeler(["dossiers"])[0], 0)
        self.assertEqual(self._appeler(["geler"])[0], 0)
        self._preparer()
        self._doubles_pass()
        self.assertEqual(self._acquerir("claude-code-fable-5")[0], 0)
        self.assertEqual(self._valider(), 0)
        self.assertEqual(self._appeler(["dossiers"])[0], 0)
        manifeste = json.loads(
            (self.racine / M.CHEMIN_MANIFESTE_DOSSIERS).read_text()
        )
        self.assertEqual(len(manifeste["dossiers"]), 1)
        code, sortie = self._appeler(["etat"])
        self.assertEqual(code, 1, sortie)
        self.assertIn("non chaîné", sortie)

    def test_gel_vide_refuse_verdict_recu_ou_revelation(self):
        self.assertEqual(self._valider(), 0)
        self.assertEqual(self._appeler(["dossiers"])[0], 0)
        self.assertEqual(self._appeler(["geler"])[0], 0)
        chemin_gel = self.racine / M.CHEMIN_GEL_VERDICTS
        octets = chemin_gel.read_bytes()

        gel = json.loads(octets)
        gel["verdicts_requis"] = 1
        chemin_gel.write_bytes(M.octets_canoniques(gel))
        code, sortie = self._appeler(["etat"])
        self.assertEqual(code, 1, sortie)
        self.assertIn("gel de lot vide incohérent", sortie)

        chemin_gel.write_bytes(octets)
        gel = json.loads(octets)
        gel["recus"] = [{"item": "ITEM-001", "chemin": "x", "sha256": "0" * 64}]
        chemin_gel.write_bytes(M.octets_canoniques(gel))
        code, sortie = self._appeler(["etat"])
        self.assertEqual(code, 1, sortie)
        self.assertIn("gel de lot vide incohérent", sortie)

        chemin_gel.write_bytes(octets)
        chemin_revelation = self.racine / M.CHEMIN_REVELATION_CORRESPONDANCE
        chemin_revelation.parent.mkdir(parents=True, exist_ok=True)
        chemin_revelation.write_text("{}", encoding="utf-8")
        code, sortie = self._appeler(["etat"])
        self.assertEqual(code, 1, sortie)
        self.assertIn("lot vide gelé avec révélation", sortie)


if __name__ == "__main__":
    unittest.main()
