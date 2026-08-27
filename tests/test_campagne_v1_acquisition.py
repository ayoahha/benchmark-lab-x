# /// script
# requires-python = ">=3.12"
# ///
"""Acquisition officielle V1-XS-08 au seam public, sans fournisseur réel.

Chaque test passe par `principal` avec une racine de dépôt temporaire, une
racine privée temporaire et un PATH réduit à des doubles locaux : aucun
client réel (`agy`, `codex`, OpenCodex) n'est jamais lancé et aucun modèle
n'est appelé. Les doubles tracent leurs arguments et leur stdin dans des
fichiers du test ; le contenu privé (manifeste d'ordre, sel) n'est jamais lu
ni affiché.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import stat
import shutil
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
    (_CAMPAGNE / "verrou-campagne-v1" / "verrou.json").as_posix(),
    M.CHEMIN_CARTE,
    M.CHEMIN_STIMULUS,
    M.CHEMIN_AUTORISATION_ACQUISITION.as_posix(),
)

_ID_ANTIGRAVITY = "antigravity-gemini-3-7-flash"
_ID_ZAI = "zai-glm-5-3"
_ACQ_ANTIGRAVITY = "ACQ-V1-ANTIGRAVITY-GEMINI-3-7-FLASH-001"
_ACQ_ZAI = "ACQ-V1-ZAI-GLM-5-3-001"
_ADRESSE_RECU_LOCAL = (
    "955c15c1d635386c7a25b9b0f3013e519883326236fcc2810cb05683d859a7f9"
)

_ARGV_RESOLU_ANTIGRAVITY_ATTENDU = [
    "agy",
    "--print",
    "--model",
    "gemini-3.7-flash-high",
    "--effort",
    "high",
    "--sandbox",
    "--mode",
    "plan",
    "--disable-slash-commands",
    "__STIMULUS_UTF8__",
]
_ARGV_RESOLU_ZAI_ATTENDU = [
    "codex",
    "exec",
    "--model",
    "zai/glm-5.3",
    "--cd",
    "__ISOLATED_WORKSPACE__",
    "--config",
    'model_reasoning_effort="high"',
    "-",
]

_FAUX_AGY_OK = """#!/bin/sh
printf '%s\\0' "$@" > "$XS08_TRACE_AGY"
printf 'invocation\\n' >> "$XS08_COMPTEUR_AGY"
printf 'sortie candidate antigravity\\n'
exit 0
"""
_FAUX_AGY_ECHEC = """#!/bin/sh
printf '%s\\0' "$@" > "$XS08_TRACE_AGY"
printf 'invocation\\n' >> "$XS08_COMPTEUR_AGY"
printf 'refus explicite du fournisseur\\n' >&2
exit 3
"""
_FAUX_AGY_IDENTITE = """#!/bin/sh
printf '%s\\0' "$@" > "$XS08_TRACE_AGY"
printf 'invocation\\n' >> "$XS08_COMPTEUR_AGY"
printf 'model: gemini-9-ultra\\n'
printf 'sortie candidate\\n'
exit 0
"""
_FAUX_AGY_ORPHELIN = """#!/bin/sh
printf '%s\\0' "$@" > "$XS08_TRACE_AGY"
printf 'invocation\\n' >> "$XS08_COMPTEUR_AGY"
/bin/sleep 300 > /dev/null 2>&1 < /dev/null &
printf 'sortie candidate\\n'
exit 0
"""
_FAUX_CODEX_OK = """#!/bin/sh
/bin/cat > "$XS08_STDIN_CODEX"
printf '%s\\0' "$@" > "$XS08_TRACE_CODEX"
printf 'invocation\\n' >> "$XS08_COMPTEUR_CODEX"
printf 'sortie candidate zai\\n'
exit 0
"""


class AcquisitionOfficielleTests(unittest.TestCase):
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
        # Seule la tête de chaîne locale entre dans la racine de test : les
        # créneaux officiels y restent libres quel que soit l'état du dépôt
        recu_local = _CAMPAGNE / "recus-v1" / f"{_ADRESSE_RECU_LOCAL}.json"
        (self.racine / recu_local).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RACINE / recu_local, self.racine / recu_local)
        # PATH réduit aux seuls doubles : aucun client réel n'est joignable
        self.bin = self.racine / "doubles-bin"
        self.bin.mkdir()
        self._path_initial = os.environ.get("PATH")
        os.environ["PATH"] = str(self.bin)
        self.addCleanup(self._restaurer_path)
        self.trace_agy = self.racine / "trace-agy.txt"
        self.compteur_agy = self.racine / "compteur-agy.txt"
        self.stdin_codex = self.racine / "stdin-codex.bin"
        self.trace_codex = self.racine / "trace-codex.txt"
        self.compteur_codex = self.racine / "compteur-codex.txt"
        os.environ["XS08_TRACE_AGY"] = str(self.trace_agy)
        os.environ["XS08_COMPTEUR_AGY"] = str(self.compteur_agy)
        os.environ["XS08_STDIN_CODEX"] = str(self.stdin_codex)
        os.environ["XS08_TRACE_CODEX"] = str(self.trace_codex)
        os.environ["XS08_COMPTEUR_CODEX"] = str(self.compteur_codex)
        self.journal = (
            self.privee / "v1-execution" / "xs-08" / "execution-journal.json"
        )
        self.runtime = self.privee / "v1-execution" / "xs-08" / "runtime"
        self.recus = self.racine / _CAMPAGNE / "recus-v1"
        self.stimulus_octets = (self.racine / M.CHEMIN_STIMULUS).read_bytes()

    def _restaurer_path(self):
        if self._path_initial is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = self._path_initial

    def _installer(self, nom: str, script: str) -> None:
        cible = self.bin / nom
        cible.write_text(script, encoding="utf-8")
        cible.chmod(0o755)

    def _acquerir(self, identifiant: str) -> tuple[int, str]:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = M.principal(
                ["acquerir", "--officiel", "--configuration", identifiant],
                racine=self.racine,
                racine_privee=self.privee,
            )
        return code, sortie.getvalue()

    def _recu_officiel(self, identifiant: str) -> dict:
        for chemin in sorted(self.recus.iterdir()):
            enveloppe = json.loads(chemin.read_text(encoding="utf-8"))
            charge = enveloppe["payload"]
            if (
                charge["configuration"]["identifiant"] == identifiant
                and charge["configuration"]["chemin"].startswith(
                    M.REGISTRE_OFFICIEL.as_posix() + "/"
                )
            ):
                return enveloppe
        raise AssertionError(f"reçu officiel absent : {identifiant}")

    def _entrees_journal(self) -> list[dict]:
        journal = json.loads(self.journal.read_text(encoding="utf-8"))
        self.assertEqual(
            journal["schema_version"], "campagne-v1-execution-journal/v1"
        )
        return journal["entrees"]

    # --- refus avant tout processus fournisseur ---

    def test_autorisation_absente_rend_deux_sans_processus_ni_recu(self):
        self._installer("agy", _FAUX_AGY_OK)
        (self.racine / M.CHEMIN_AUTORISATION_ACQUISITION).unlink()
        code, sortie = self._acquerir(_ID_ANTIGRAVITY)
        self.assertEqual(code, 2, sortie)
        self.assertFalse(self.trace_agy.exists())
        self.assertFalse(self.journal.exists())
        self.assertEqual(sum(1 for _ in self.recus.iterdir()), 1)

    def test_autorisation_divergente_rend_deux_sans_processus_ni_recu(self):
        self._installer("agy", _FAUX_AGY_OK)
        chemin = self.racine / M.CHEMIN_AUTORISATION_ACQUISITION
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
        donnees["verrou"]["sha256"] = "0" * 64
        chemin.write_bytes(M.octets_canoniques(donnees))
        code, sortie = self._acquerir(_ID_ANTIGRAVITY)
        self.assertEqual(code, 2, sortie)
        self.assertFalse(self.trace_agy.exists())
        self.assertFalse(self.journal.exists())
        self.assertEqual(sum(1 for _ in self.recus.iterdir()), 1)

    def test_configuration_hors_portee_rend_deux_sans_processus(self):
        self._installer("agy", _FAUX_AGY_OK)
        code, sortie = self._acquerir("claude-code-fable-5")
        self.assertEqual(code, 2, sortie)
        self.assertFalse(self.trace_agy.exists())
        self.assertFalse(self.journal.exists())

    def test_delai_configure_non_nul_rend_deux_sans_processus(self):
        self._installer("agy", _FAUX_AGY_OK)
        chemin = (
            self.racine / M.REGISTRE_OFFICIEL / f"{_ID_ANTIGRAVITY}.toml"
        )
        contenu = chemin.read_text(encoding="utf-8")
        chemin.write_text(
            contenu.replace("delai_secondes = 0", "delai_secondes = 5"),
            encoding="utf-8",
        )
        code, sortie = self._acquerir(_ID_ANTIGRAVITY)
        self.assertEqual(code, 2, sortie)
        self.assertFalse(self.trace_agy.exists())

    def test_cli_hors_forme_rend_deux(self):
        for arguments in (
            ["acquerir", "--officiel"],
            ["acquerir", "--officiel", "--local", "--configuration", _ID_ZAI],
            ["acquerir", "--configuration", _ID_ZAI],
        ):
            with self.subTest(arguments=arguments):
                sortie = io.StringIO()
                with contextlib.redirect_stdout(sortie):
                    code = M.principal(
                        arguments, racine=self.racine, racine_privee=self.privee
                    )
                self.assertEqual(code, 2, sortie.getvalue())

    # --- décisions techniques fermées ---

    def test_plafond_officiel_600_secondes(self):
        self.assertEqual(M.DELAI_ACQUISITION_OFFICIELLE, 600)

    def test_flags_interdits_absents_des_descripteurs(self):
        interdits = set(M.FLAGS_INTERDITS_ACQUISITION)
        for element in (
            "--continue",
            "-c",
            "--conversation",
            "--agent",
            "--project",
            "--new-project",
            "--prompt-interactive",
            "-i",
        ):
            self.assertIn(element, interdits)
        for argv in (
            _ARGV_RESOLU_ANTIGRAVITY_ATTENDU,
            _ARGV_RESOLU_ZAI_ATTENDU,
        ):
            self.assertFalse(interdits.intersection(argv))

    # --- acquisition Antigravity ---

    def test_antigravity_selection_explicite_et_recu_chaine(self):
        self._installer("agy", _FAUX_AGY_OK)
        code, sortie = self._acquerir(_ID_ANTIGRAVITY)
        self.assertEqual(code, 0, sortie)
        arguments = self.trace_agy.read_text(encoding="utf-8").split("\0")[:-1]
        self.assertEqual(
            arguments[:-1], _ARGV_RESOLU_ANTIGRAVITY_ATTENDU[1:-1]
        )
        # le stimulus UTF-8 exact est l'unique prompt, jamais son chemin
        self.assertEqual(
            arguments[-1], self.stimulus_octets.decode("utf-8")
        )
        enveloppe = self._recu_officiel(_ID_ANTIGRAVITY)
        charge = enveloppe["payload"]
        self.assertEqual(
            charge["predecesseur_adresse_contenu"], _ADRESSE_RECU_LOCAL
        )
        self.assertEqual(
            charge["requete"]["argv_resolu"], _ARGV_RESOLU_ANTIGRAVITY_ATTENDU
        )
        self.assertEqual(charge["requete"]["mode_stdin"], "aucun")
        self.assertEqual(charge["quota_observe"], "INCONNU")
        self.assertEqual(charge["provenance_servie"], "INCONNU")
        self.assertEqual(charge["execution"]["etat"], "OBSERVED")
        self.assertEqual(charge["execution"]["code_sortie"], 0)
        self.assertEqual(
            charge["configuration"]["chemin"],
            (M.REGISTRE_OFFICIEL / f"{_ID_ANTIGRAVITY}.toml").as_posix(),
        )
        # requête expurgée : le texte du stimulus n'entre pas dans le reçu
        adresse = enveloppe["content_address"]["sha256"]
        octets_recu = (self.recus / f"{adresse}.json").read_bytes()
        self.assertNotIn(
            self.stimulus_octets.decode("utf-8").splitlines()[0],
            octets_recu.decode("utf-8"),
        )

    def test_antigravity_espace_reel_conserve_et_sortie_capturee(self):
        self._installer("agy", _FAUX_AGY_OK)
        code, sortie = self._acquerir(_ID_ANTIGRAVITY)
        self.assertEqual(code, 0, sortie)
        espace = self.runtime / _ACQ_ANTIGRAVITY
        self.assertTrue(espace.is_dir())
        self.assertEqual(
            (espace / "sortie-stdout.txt").read_text(encoding="utf-8"),
            "sortie candidate antigravity\n",
        )

    # --- acquisition Z.AI ---

    def test_zai_descripteur_exact_et_stimulus_sur_stdin(self):
        self._installer("codex", _FAUX_CODEX_OK)
        code, sortie = self._acquerir(_ID_ZAI)
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.stdin_codex.read_bytes(), self.stimulus_octets)
        arguments = self.trace_codex.read_text(encoding="utf-8").split("\0")[:-1]
        self.assertEqual(arguments[0], "exec")
        self.assertIn("zai/glm-5.3", arguments)
        self.assertIn('model_reasoning_effort="high"', arguments)
        enveloppe = self._recu_officiel(_ID_ZAI)
        charge = enveloppe["payload"]
        self.assertEqual(
            charge["requete"]["argv_resolu"], _ARGV_RESOLU_ZAI_ATTENDU
        )
        self.assertEqual(charge["requete"]["mode_stdin"], "__PROMPT_FILE__")
        self.assertEqual(
            charge["requete"]["espace_de_travail"], "__ISOLATED_WORKSPACE__"
        )
        # l'espace résolu réel ne fuit pas dans le reçu
        self.assertNotIn(
            str(self.privee),
            (self.recus / f"{enveloppe['content_address']['sha256']}.json")
            .read_text(encoding="utf-8"),
        )

    # --- journal privé ---

    def test_journal_exact_apres_acquisition(self):
        self._installer("agy", _FAUX_AGY_OK)
        code, _ = self._acquerir(_ID_ANTIGRAVITY)
        self.assertEqual(code, 0)
        self.assertEqual(
            stat.S_IMODE(os.lstat(self.journal).st_mode), 0o600
        )
        entrees = self._entrees_journal()
        self.assertEqual(len(entrees), 1)
        entree = entrees[0]
        self.assertEqual(entree["acquisition_id"], _ACQ_ANTIGRAVITY)
        self.assertEqual(entree["configuration_id"], _ID_ANTIGRAVITY)
        self.assertEqual(
            entree["invocation_publique"],
            "uv run tools/campagne_v1.py acquerir --officiel "
            f"--configuration {_ID_ANTIGRAVITY}",
        )
        self.assertEqual(entree["code"], 0)
        self.assertEqual(entree["etat_terminal"], "OBSERVED")
        self.assertEqual(entree["retry"], 0)
        self.assertEqual(entree["descendants"], 0)
        enveloppe = self._recu_officiel(_ID_ANTIGRAVITY)
        self.assertEqual(entree["recu"], enveloppe["content_address"]["sha256"])
        self.assertIsInstance(entree["latence_ms"], int)
        # aucune sortie candidate ni texte de stimulus dans le journal
        texte_journal = self.journal.read_text(encoding="utf-8")
        self.assertNotIn("sortie candidate", texte_journal)
        self.assertNotIn(
            self.stimulus_octets.decode("utf-8").splitlines()[0], texte_journal
        )

    def test_second_enregistrement_du_meme_creneau_refuse(self):
        self._installer("agy", _FAUX_AGY_OK)
        self.assertEqual(self._acquerir(_ID_ANTIGRAVITY)[0], 0)
        nombre_recus = sum(1 for _ in self.recus.iterdir())
        code, sortie = self._acquerir(_ID_ANTIGRAVITY)
        self.assertEqual(code, 2, sortie)
        self.assertEqual(
            self.compteur_agy.read_text(encoding="utf-8").count("invocation"), 1
        )
        self.assertEqual(len(self._entrees_journal()), 1)
        self.assertEqual(sum(1 for _ in self.recus.iterdir()), nombre_recus)

    # --- incidents terminaux ---

    def test_code_client_non_nul_sans_sortie_devient_harness_error(self):
        self._installer("agy", _FAUX_AGY_ECHEC)
        self._installer("codex", _FAUX_CODEX_OK)
        code, sortie = self._acquerir(_ID_ANTIGRAVITY)
        # la commande locale de capture termine : reçu terminal, zéro descendant
        self.assertEqual(code, 0, sortie)
        enveloppe = self._recu_officiel(_ID_ANTIGRAVITY)
        execution = enveloppe["payload"]["execution"]
        self.assertEqual(execution["etat"], "INCIDENT")
        self.assertEqual(execution["incident"], "HARNESS_ERROR")
        self.assertIn("code client 3", execution["fait"])
        # aucune sortie candidate ni stderr brute n'entre dans le reçu public
        self.assertNotIn("sortie", execution)
        self.assertNotIn("refus explicite", json.dumps(enveloppe))
        # la stderr reste capturée dans l'espace réel privé
        self.assertIn(
            "refus explicite",
            (
                self.runtime
                / _ACQ_ANTIGRAVITY
                / "sortie-stderr.txt"
            ).read_text(encoding="utf-8"),
        )
        entrees = self._entrees_journal()
        self.assertEqual(entrees[0]["etat_terminal"], "HARNESS_ERROR")
        self.assertEqual(entrees[0]["descendants"], 0)
        self.assertEqual(
            entrees[0]["recu"], enveloppe["content_address"]["sha256"]
        )
        # incident terminal correctement reçu : l'autre créneau reste ouvert
        self.assertEqual(self._acquerir(_ID_ZAI)[0], 0)
        self.assertEqual(len(self._entrees_journal()), 2)

    def test_client_introuvable_devient_harness_error_recu(self):
        # aucun double 'agy' : le lancement échoue localement, sans réseau
        code, sortie = self._acquerir(_ID_ANTIGRAVITY)
        self.assertEqual(code, 0, sortie)
        charge = self._recu_officiel(_ID_ANTIGRAVITY)["payload"]
        self.assertEqual(charge["execution"]["etat"], "INCIDENT")
        self.assertEqual(charge["execution"]["incident"], "HARNESS_ERROR")
        entrees = self._entrees_journal()
        self.assertEqual(entrees[0]["etat_terminal"], "HARNESS_ERROR")

    def test_identite_divergente_explicite_impose_hold(self):
        self._installer("agy", _FAUX_AGY_IDENTITE)
        self._installer("codex", _FAUX_CODEX_OK)
        code, sortie = self._acquerir(_ID_ANTIGRAVITY)
        self.assertEqual(code, 0, sortie)
        charge = self._recu_officiel(_ID_ANTIGRAVITY)["payload"]
        self.assertEqual(charge["execution"]["etat"], "INCIDENT")
        self.assertEqual(charge["execution"]["incident"], "IDENTITY_MISMATCH")
        self.assertIn(
            "gemini-9-ultra", charge["execution"]["preuve_attribuable"]
        )
        # HOLD : aucun autre appel tant que la divergence n'est pas arbitrée
        code, sortie = self._acquerir(_ID_ZAI)
        self.assertEqual(code, 2, sortie)
        self.assertFalse(self.trace_codex.exists())

    def test_descendant_survivant_detecte_tue_et_code_un(self):
        self._installer("agy", _FAUX_AGY_ORPHELIN)
        self._installer("codex", _FAUX_CODEX_OK)
        code, sortie = self._acquerir(_ID_ANTIGRAVITY)
        self.assertEqual(code, 1, sortie)
        self.assertIn("descendant", sortie)
        entrees = self._entrees_journal()
        self.assertGreaterEqual(entrees[0]["descendants"], 1)
        # HOLD : le créneau suivant est refusé avant tout processus
        code, sortie = self._acquerir(_ID_ZAI)
        self.assertEqual(code, 2, sortie)
        self.assertFalse(self.trace_codex.exists())

    # --- artefact d'autorisation du dépôt ---

    def test_artefact_autorisation_du_depot_conforme(self):
        donnees = json.loads(
            (RACINE / M.CHEMIN_AUTORISATION_ACQUISITION).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            donnees["schema_version"], "campagne-v1-autorisation-acquisition/v1"
        )
        self.assertEqual(donnees["autorite"], "D-V1-04")
        self.assertEqual(donnees["jeton"], "Donc Go D-V1-04, V1-XS-08")
        commentaire = donnees["commentaire"]
        self.assertEqual(commentaire["auteur"], "ayoahha")
        self.assertEqual(commentaire["association"], "OWNER")
        self.assertEqual(commentaire["date"], "2026-08-27")
        self.assertEqual(
            commentaire["url"],
            "https://github.com/ayoahha/benchmark-lab-x/issues/108"
            "#issuecomment-5434400855",
        )
        self.assertEqual(
            commentaire["sha256_corps"],
            "5a405a72b31a80b32d89e4db59e0d39f7d3f140b79c5ae3e595af9e05cd06c4f",
        )
        self.assertEqual(
            donnees["verrou"]["sha256"],
            M._sha256_fichier(RACINE / M.CHEMIN_VERROU),
        )
        self.assertEqual(
            donnees["stimulus"]["sha256"],
            M._sha256_fichier(RACINE / M.CHEMIN_STIMULUS),
        )
        portee = donnees["portee"]
        self.assertEqual(
            portee["acquisitions"],
            [
                {
                    "acquisition_id": _ACQ_ANTIGRAVITY,
                    "configuration_id": _ID_ANTIGRAVITY,
                },
                {"acquisition_id": _ACQ_ZAI, "configuration_id": _ID_ZAI},
            ],
        )
        self.assertEqual(portee["appels_fournisseur_max"], 2)
        self.assertEqual(portee["appels_par_creneau"], 1)
        self.assertEqual(portee["depense_incrementale"], 0)
        self.assertEqual(portee["reprises_automatiques"], 0)
        self.assertEqual(portee["reprises_manuelles"], 0)
        self.assertEqual(portee["fallback"], "NONE")
        self.assertEqual(portee["consommation_quota"], "ABONNEMENTS_EXISTANTS")
        self.assertNotIn("self_hash", donnees)

    # --- restitution ---

    def test_restitution_apres_deux_acquisitions(self):
        self._installer("agy", _FAUX_AGY_OK)
        self._installer("codex", _FAUX_CODEX_OK)
        self.assertEqual(self._acquerir(_ID_ANTIGRAVITY)[0], 0)
        self.assertEqual(self._acquerir(_ID_ZAI)[0], 0)
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            self.assertEqual(
                M.principal(["restituer"], racine=self.racine), 0
            )
            self.assertEqual(
                M.principal(["verifier-restitution"], racine=self.racine),
                0,
                sortie.getvalue(),
            )
        page = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        self.assertIn("acquisitions: 2", page)
        self.assertIn("conclusion: ABSTENTION", page)
        self.assertIn("NOT_GRANTED", page)
        self.assertIn("D-V1-04", page)
        self.assertEqual(page.count(' data-autorisation-acquisition="'), 1)
        self.assertEqual(page.count(' data-acquisition-officielle="'), 2)
        self.assertIn("EXCLUDED_WAITING", page)
        self.assertIn("INCONNU", page)
        section = page.split('<section id="acquisitions-officielles">')[1].split(
            "</section>"
        )[0]
        for interdit in ("classement", "gagnant", "recommand", "score"):
            self.assertNotIn(interdit, section.lower())
        # l'ordre privé n'est jamais publié : aucune liaison item-créneau
        self.assertNotIn("ITEM-001 :", page)
        self.assertNotIn(str(self.privee), page)

    def test_restitution_sans_acquisition_reste_conforme(self):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            self.assertEqual(
                M.principal(["restituer"], racine=self.racine), 0
            )
            self.assertEqual(
                M.principal(["verifier-restitution"], racine=self.racine),
                0,
                sortie.getvalue(),
            )
        page = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        self.assertIn("acquisitions: 0", page)
        self.assertIn("conclusion: ABSTENTION", page)
        self.assertEqual(page.count(' data-autorisation-acquisition="'), 1)
        self.assertEqual(page.count(' data-acquisition-officielle="'), 0)

    def test_restitution_refuse_article_officiel_altere(self):
        self._installer("agy", _FAUX_AGY_OK)
        self.assertEqual(self._acquerir(_ID_ANTIGRAVITY)[0], 0)
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            self.assertEqual(
                M.principal(["restituer"], racine=self.racine), 0
            )
        chemin_page = self.racine / M.CHEMIN_PAGE
        page = chemin_page.read_text(encoding="utf-8")
        enveloppe = self._recu_officiel(_ID_ANTIGRAVITY)
        alteree = page.replace(
            enveloppe["content_address"]["sha256"], "1" * 64
        )
        self.assertNotEqual(alteree, page)
        chemin_page.write_text(alteree, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertNotEqual(
                M.principal(["verifier-restitution"], racine=self.racine), 0
            )


if __name__ == "__main__":
    unittest.main()
