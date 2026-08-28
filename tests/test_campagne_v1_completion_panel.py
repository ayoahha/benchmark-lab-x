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
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

RACINE = Path(__file__).parent.parent
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


if __name__ == "__main__":
    unittest.main()
