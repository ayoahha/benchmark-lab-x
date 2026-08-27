# /// script
# requires-python = ">=3.12"
# ///
"""Contrôles XS-02 : contrat de configuration abonnement et registre de panel."""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import campagne_v1 as M  # noqa: E402

from tests._helpers_v1 import retirer_couverture_publiee  # noqa: E402

CONFIGURATIONS_OFFICIELLES = (
    RACINE / "tasks/dev/pre-cadrage-entretien-client/campagne-v1/configurations"
)
FIXTURES = RACINE / "tests/fixtures/campagne-v1"

IDS_OFFICIELS = (
    "antigravity-gemini-3-7-flash",
    "claude-code-fable-5",
    "claude-code-opus-5",
    "codex-gpt-5-6-sol",
    "cursor-kimi-k3",
    "grok-build-grok-4-6",
    "zai-glm-5-3",
)

INVALIDES_ET_CHAMPS = (
    ("invalide-modele-absent.toml", "modele"),
    ("invalide-interface-type.toml", "interface.type"),
    ("invalide-harnais-argv.toml", "harnais.argv"),
)


def _principal(arguments: list[str], racine: Path) -> tuple[int, str]:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = M.principal(arguments, racine=racine)
    return code, sortie.getvalue()


class BaseXS02(unittest.TestCase):
    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        self.officiel = self.racine / M.REGISTRE_OFFICIEL

    def _enregistrer_les_sept(self) -> None:
        for identifiant in IDS_OFFICIELS:
            chemin = CONFIGURATIONS_OFFICIELLES / f"{identifiant}.toml"
            code, sortie = _principal(
                ["enregistrer", "--fichier", str(chemin)], self.racine
            )
            self.assertEqual(code, 0, sortie)


class EnregistrerTests(BaseXS02):
    def test_enregistrer_officiel_rend_zero_et_ecrit_le_registre(self):
        source = CONFIGURATIONS_OFFICIELLES / "claude-code-fable-5.toml"
        code, sortie = _principal(
            ["enregistrer", "--fichier", str(source)], self.racine
        )
        self.assertEqual(code, 0, sortie)
        destination = self.officiel / "claude-code-fable-5.toml"
        self.assertEqual(destination.read_bytes(), source.read_bytes())

    def test_enregistrer_les_sept_configurations_officielles(self):
        self._enregistrer_les_sept()
        self.assertEqual(
            sorted(chemin.name for chemin in self.officiel.glob("*.toml")),
            [f"{identifiant}.toml" for identifiant in IDS_OFFICIELS],
        )

    def test_enregistrer_refuse_le_doublon_en_nommant_configuration_id(self):
        source = CONFIGURATIONS_OFFICIELLES / "claude-code-fable-5.toml"
        _principal(["enregistrer", "--fichier", str(source)], self.racine)
        code, sortie = _principal(
            ["enregistrer", "--fichier", str(source)], self.racine
        )
        self.assertEqual(code, 1)
        self.assertIn("configuration_id", sortie)
        self.assertIn("claude-code-fable-5", sortie)

    def test_enregistrer_registre_isole_ne_cree_ni_ne_lit_l_officiel(self):
        bac = self.racine / "bac-a-sable"
        bac.mkdir()
        demonstration = (
            FIXTURES / "demonstration/claude-code-demonstration-fable-5.toml"
        )
        code, sortie = _principal(
            ["enregistrer", "--registre", str(bac), "--fichier", str(demonstration)],
            self.racine,
        )
        self.assertEqual(code, 0, sortie)
        self.assertTrue(
            (bac / "claude-code-demonstration-fable-5.toml").is_file()
        )
        self.assertFalse(self.officiel.exists())

    def test_enregistrer_registre_isole_absent_refuse(self):
        demonstration = (
            FIXTURES / "demonstration/claude-code-demonstration-fable-5.toml"
        )
        code, sortie = _principal(
            [
                "enregistrer",
                "--registre",
                str(self.racine / "absent"),
                "--fichier",
                str(demonstration),
            ],
            self.racine,
        )
        self.assertEqual(code, 1)
        self.assertFalse(self.officiel.exists())

    def test_trois_invalides_rendent_un_nomment_le_champ_et_ne_touchent_rien(self):
        bac = self.racine / "bac-a-sable"
        bac.mkdir()
        for nom, champ in INVALIDES_ET_CHAMPS:
            with self.subTest(fichier=nom):
                code, sortie = _principal(
                    [
                        "enregistrer",
                        "--registre",
                        str(bac),
                        "--fichier",
                        str(FIXTURES / "invalides" / nom),
                    ],
                    self.racine,
                )
                self.assertEqual(code, 1)
                self.assertIn(champ, sortie)
        self.assertEqual(list(bac.iterdir()), [])
        self.assertFalse(self.officiel.exists())

    def test_enregistrer_sans_fichier_rend_deux(self):
        code, _ = _principal(["enregistrer"], self.racine)
        self.assertEqual(code, 2)


class PanelTests(BaseXS02):
    def test_panel_officiel_vide_rend_zero_et_cardinalite_zero(self):
        code, sortie = _principal(["panel"], self.racine)
        self.assertEqual(code, 0, sortie)
        self.assertIn("panel : vide (0 configuration déclarée)", sortie)

    def test_panel_officiel_affiche_les_sept_identites_completes(self):
        self._enregistrer_les_sept()
        code, sortie = _principal(["panel"], self.racine)
        self.assertEqual(code, 0, sortie)
        self.assertIn("panel : 7 configurations déclarées, non mesurées", sortie)
        for identifiant in IDS_OFFICIELS:
            self.assertIn(identifiant, sortie)
        self.assertEqual(sortie.count("[DECLAREE, NON MESUREE]"), 7)
        self.assertEqual(sortie.count("modèle demandé [REQUESTED]"), 7)
        self.assertIn("claude-fable-5", sortie)
        self.assertIn("Z.AI Coding Plan", sortie)
        # Identité complète : les champs non observés restent littéralement INCONNU.
        for fragment in (
            "prix : INCONNU INCONNU",
            "période : INCONNU",
            "interface : cli",
            "version : INCONNU",
            "reset_fenetre=INCONNU",
            "intervention humaine : INCONNU",
        ):
            self.assertIn(fragment, sortie)

    def test_panel_isole_passe_de_sept_a_huit_sans_toucher_l_officiel(self):
        self._enregistrer_les_sept()
        bac = self.racine / "bac-a-sable"
        shutil.copytree(self.officiel, bac)
        demonstration = (
            FIXTURES / "demonstration/claude-code-demonstration-fable-5.toml"
        )
        code, sortie = _principal(["panel", "--registre", str(bac)], self.racine)
        self.assertEqual(code, 0, sortie)
        self.assertIn("panel : 7 configurations déclarées, non mesurées", sortie)
        code, _ = _principal(
            ["enregistrer", "--registre", str(bac), "--fichier", str(demonstration)],
            self.racine,
        )
        self.assertEqual(code, 0)
        code, sortie = _principal(["panel", "--registre", str(bac)], self.racine)
        self.assertEqual(code, 0, sortie)
        self.assertIn("panel : 8 configurations déclarées, non mesurées", sortie)
        self.assertIn("claude-code-demonstration-fable-5", sortie)
        code, sortie = _principal(["panel"], self.racine)
        self.assertEqual(code, 0, sortie)
        self.assertIn("panel : 7 configurations déclarées, non mesurées", sortie)
        self.assertNotIn("claude-code-demonstration-fable-5", sortie)

    def test_panel_registre_isole_absent_refuse(self):
        code, _ = _principal(
            ["panel", "--registre", str(self.racine / "absent")], self.racine
        )
        self.assertEqual(code, 1)

    def test_panel_refuse_une_entree_corrompue_en_nommant_le_champ(self):
        bac = self.racine / "bac-a-sable"
        bac.mkdir()
        shutil.copyfile(
            FIXTURES / "invalides/invalide-interface-type.toml",
            bac / "invalide-interface-type.toml",
        )
        code, sortie = _principal(["panel", "--registre", str(bac)], self.racine)
        self.assertEqual(code, 1)
        self.assertIn("interface.type", sortie)

    def test_panel_option_inconnue_rend_deux(self):
        code, _ = _principal(["panel", "--autre", "x"], self.racine)
        self.assertEqual(code, 2)


class ContratDelaiTests(BaseXS02):
    """Contrat figé harnais.delai_secondes : entier >= 0, aucune branche INCONNU."""

    def test_delai_secondes_zero_accepte(self):
        source = CONFIGURATIONS_OFFICIELLES / "claude-code-fable-5.toml"
        self.assertIn('delai_secondes = 0', source.read_text(encoding="utf-8"))
        code, sortie = _principal(
            ["enregistrer", "--fichier", str(source)], self.racine
        )
        self.assertEqual(code, 0, sortie)

    def test_delai_secondes_inconnu_refuse_en_nommant_le_champ(self):
        bac = self.racine / "bac-a-sable"
        bac.mkdir()
        demonstration = (
            FIXTURES / "demonstration/claude-code-demonstration-fable-5.toml"
        )
        invalide = self.racine / "delai-inconnu.toml"
        invalide.write_text(
            demonstration.read_text(encoding="utf-8").replace(
                "delai_secondes = 0", 'delai_secondes = "INCONNU"'
            ),
            encoding="utf-8",
        )
        code, sortie = _principal(
            ["enregistrer", "--registre", str(bac), "--fichier", str(invalide)],
            self.racine,
        )
        self.assertEqual(code, 1)
        self.assertIn("harnais.delai_secondes", sortie)
        self.assertEqual(list(bac.iterdir()), [])


_ARGV_CODEX_ZAI = (
    'argv = ["codex", "exec", "--model", "zai/glm-5.3", "--cd", '
    '"__ISOLATED_WORKSPACE__", "--config", "model_reasoning_effort=\\"high\\"", "-"]'
)


class ContratStdinFichierTests(BaseXS02):
    """Contrat XS-02 : __PROMPT_FILE__ exactement une fois dans argv ∪ stdin_fichier."""

    def setUp(self):
        super().setUp()
        self.bac = self.racine / "bac-a-sable"
        self.bac.mkdir()

    def _candidate(self, ligne_argv: str, ligne_stdin: str | None = None) -> Path:
        demonstration = (
            FIXTURES / "demonstration/claude-code-demonstration-fable-5.toml"
        )
        remplacement = ligne_argv
        if ligne_stdin is not None:
            remplacement += "\n" + ligne_stdin
        texte = demonstration.read_text(encoding="utf-8").replace(
            'argv = ["claude", "__PROMPT_FILE__"]', remplacement
        )
        chemin = self.racine / "candidate.toml"
        chemin.write_text(texte, encoding="utf-8")
        return chemin

    def _enregistrer_candidate(self, chemin: Path) -> tuple[int, str]:
        return _principal(
            ["enregistrer", "--registre", str(self.bac), "--fichier", str(chemin)],
            self.racine,
        )

    def test_stdin_fichier_avec_argv_sans_jeton_accepte(self):
        chemin = self._candidate(_ARGV_CODEX_ZAI, 'stdin_fichier = "__PROMPT_FILE__"')
        code, sortie = self._enregistrer_candidate(chemin)
        self.assertEqual(code, 0, sortie)
        self.assertTrue(
            (self.bac / "claude-code-demonstration-fable-5.toml").is_file()
        )

    def test_jeton_absent_d_argv_et_de_stdin_fichier_refuse(self):
        chemin = self._candidate(_ARGV_CODEX_ZAI)
        code, sortie = self._enregistrer_candidate(chemin)
        self.assertEqual(code, 1)
        self.assertIn("harnais.argv", sortie)
        self.assertIn("harnais.stdin_fichier", sortie)
        self.assertIn("exactement une fois", sortie)
        self.assertEqual(list(self.bac.iterdir()), [])

    def test_jeton_present_dans_argv_et_stdin_fichier_refuse(self):
        chemin = self._candidate(
            'argv = ["claude", "__PROMPT_FILE__"]',
            'stdin_fichier = "__PROMPT_FILE__"',
        )
        code, sortie = self._enregistrer_candidate(chemin)
        self.assertEqual(code, 1)
        self.assertIn("harnais.argv", sortie)
        self.assertIn("harnais.stdin_fichier", sortie)
        self.assertIn("exactement une fois", sortie)
        self.assertEqual(list(self.bac.iterdir()), [])

    def test_jeton_double_dans_argv_seul_refuse(self):
        chemin = self._candidate(
            'argv = ["claude", "__PROMPT_FILE__", "__PROMPT_FILE__"]'
        )
        code, sortie = self._enregistrer_candidate(chemin)
        self.assertEqual(code, 1)
        self.assertIn("exactement une fois", sortie)
        self.assertEqual(list(self.bac.iterdir()), [])

    def test_stdin_fichier_non_conforme_refuse_en_nommant_le_champ(self):
        chemin = self._candidate(_ARGV_CODEX_ZAI, 'stdin_fichier = "prompt.txt"')
        code, sortie = self._enregistrer_candidate(chemin)
        self.assertEqual(code, 1)
        self.assertIn("harnais.stdin_fichier", sortie)
        self.assertIn("__PROMPT_FILE__", sortie)
        self.assertEqual(list(self.bac.iterdir()), [])


class GardeRegistreOfficielTests(BaseXS02):
    """Isolation absolue : '--registre' ne vise jamais le registre officiel."""

    def test_enregistrer_registre_officiel_refuse_sans_huitieme_fichier(self):
        self._enregistrer_les_sept()
        demonstration = (
            FIXTURES / "demonstration/claude-code-demonstration-fable-5.toml"
        )
        code, sortie = _principal(
            [
                "enregistrer",
                "--registre",
                str(self.officiel),
                "--fichier",
                str(demonstration),
            ],
            self.racine,
        )
        self.assertEqual(code, 1)
        self.assertIn("--registre", sortie)
        self.assertIn(M.REGISTRE_OFFICIEL.as_posix(), sortie)
        self.assertEqual(len(list(self.officiel.glob("*.toml"))), 7)

    def test_panel_registre_officiel_refuse(self):
        self._enregistrer_les_sept()
        code, sortie = _principal(
            ["panel", "--registre", str(self.officiel)], self.racine
        )
        self.assertEqual(code, 1)
        self.assertIn("--registre", sortie)
        self.assertIn(M.REGISTRE_OFFICIEL.as_posix(), sortie)

    def test_panel_officiel_sans_registre_reste_exactement_a_sept(self):
        self._enregistrer_les_sept()
        demonstration = (
            FIXTURES / "demonstration/claude-code-demonstration-fable-5.toml"
        )
        code, _ = _principal(
            [
                "enregistrer",
                "--registre",
                str(self.officiel),
                "--fichier",
                str(demonstration),
            ],
            self.racine,
        )
        self.assertEqual(code, 1)
        code, sortie = _principal(["panel"], self.racine)
        self.assertEqual(code, 0, sortie)
        self.assertIn("panel : 7 configurations déclarées, non mesurées", sortie)
        self.assertNotIn("claude-code-demonstration-fable-5", sortie)


_HARNAIS_ZAI_ATTENDU = (
    "[harnais]\n"
    'argv = ["codex", "exec", "--model", "zai/glm-5.3", "--cd", '
    '"__ISOLATED_WORKSPACE__", "--config", "model_reasoning_effort=\\"high\\"", '
    '"-"]\n'
    'stdin_fichier = "__PROMPT_FILE__"\n'
    'espace_de_travail = "__ISOLATED_WORKSPACE__"\n'
    'delai_secondes = 0\n'
)

_ARGV_SANS_STDIN_ATTENDUS = {
    "antigravity-gemini-3-7-flash": 'argv = ["agy", "__PROMPT_FILE__"]',
    "claude-code-fable-5": 'argv = ["claude", "__PROMPT_FILE__"]',
    "claude-code-opus-5": 'argv = ["claude", "__PROMPT_FILE__"]',
    "codex-gpt-5-6-sol": 'argv = ["codex", "__PROMPT_FILE__"]',
    "cursor-kimi-k3": 'argv = ["agent", "__PROMPT_FILE__"]',
    "grok-build-grok-4-6": 'argv = ["grok", "__PROMPT_FILE__"]',
}


class ContratZaiOfficielTests(BaseXS02):
    """Route agente Z.AI corrigée : Codex CLI agent, prompt sur stdin."""

    def test_source_zai_porte_le_contrat_harnais_codex_stdin(self):
        source = CONFIGURATIONS_OFFICIELLES / "zai-glm-5-3.toml"
        self.assertIn(_HARNAIS_ZAI_ATTENDU, source.read_text(encoding="utf-8"))
        code, sortie = _principal(
            ["enregistrer", "--fichier", str(source)], self.racine
        )
        self.assertEqual(code, 0, sortie)

    def test_source_zai_et_registre_officiel_identiques(self):
        source = CONFIGURATIONS_OFFICIELLES / "zai-glm-5-3.toml"
        registre = RACINE / M.REGISTRE_OFFICIEL / "zai-glm-5-3.toml"
        self.assertEqual(source.read_bytes(), registre.read_bytes())

    def test_six_autres_configurations_inchangees_sans_stdin_fichier(self):
        for identifiant, ligne_argv in _ARGV_SANS_STDIN_ATTENDUS.items():
            for repertoire in (CONFIGURATIONS_OFFICIELLES, RACINE / M.REGISTRE_OFFICIEL):
                with self.subTest(configuration=identifiant, repertoire=str(repertoire)):
                    texte = (repertoire / f"{identifiant}.toml").read_text(
                        encoding="utf-8"
                    )
                    self.assertIn(ligne_argv, texte)
                    self.assertNotIn("stdin_fichier", texte)

    def test_panel_affiche_argv_codex_et_source_stdin_pour_zai(self):
        self._enregistrer_les_sept()
        code, sortie = _principal(["panel"], self.racine)
        self.assertEqual(code, 0, sortie)
        self.assertIn(
            "argv=['codex', 'exec', '--model', 'zai/glm-5.3', '--cd', "
            "'__ISOLATED_WORKSPACE__', '--config', "
            "'model_reasoning_effort=\"high\"', '-']",
            sortie,
        )
        self.assertIn("stdin=__PROMPT_FILE__", sortie)
        # Une seule configuration porte la source stdin, les six autres aucune
        self.assertEqual(sortie.count("stdin="), 1)


_ENTREES_RESTITUTION = tuple(chemin for chemin, _ in M.SOURCES_AUTORISEES) + (
    M.CHEMIN_ETAT.as_posix(),
)


class RestitutionPanelTests(BaseXS02):
    """Restitution régénérée sur un registre officiel à sept entrées."""

    def setUp(self):
        super().setUp()
        for relatif in _ENTREES_RESTITUTION:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        retirer_couverture_publiee(self.racine / M.CHEMIN_ETAT)
        self._enregistrer_les_sept()
        self.page = self.racine / M.CHEMIN_PAGE

    def _restituer(self) -> str:
        code, sortie = _principal(["restituer"], self.racine)
        self.assertEqual(code, 0, sortie)
        return self.page.read_text(encoding="utf-8")

    def test_page_affiche_les_sept_entrees_declarees_non_mesurees(self):
        page = self._restituer()
        self.assertIn("panel: 7 configurations déclarées, non mesurées", page)
        self.assertIn("conclusion: ABSTENTION", page)
        self.assertEqual(page.count('data-statut="declaree-non-mesuree"'), 7)
        for identifiant in IDS_OFFICIELS:
            self.assertIn(f'data-configuration="{identifiant}"', page)
        self.assertEqual(page.count("<code>REQUESTED</code>"), 7)
        self.assertNotIn("panel: vide", page)

    def test_page_affiche_argv_codex_et_source_stdin_pour_zai(self):
        page = self._restituer()
        for fragment in (
            "<code>codex</code>",
            "<code>exec</code>",
            "<code>zai/glm-5.3</code>",
            "<code>model_reasoning_effort=&quot;high&quot;</code>",
            "<code>-</code>",
            "stdin <code>__PROMPT_FILE__</code>",
        ):
            self.assertIn(fragment, page)
        # Une seule entrée de panel porte la source stdin
        self.assertEqual(page.count("stdin <code>"), 1)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_restitutions_successives_byte_identiques_avec_panel(self):
        premiere = self._restituer()
        self.assertEqual(premiere, self._restituer())

    def test_verifier_rend_zero_sur_page_regeneree(self):
        self._restituer()
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_verifier_refuse_une_entree_panel_alteree(self):
        page = self._restituer()
        self.page.write_text(
            page.replace("claude-fable-5", "claude-fable-6"), encoding="utf-8"
        )
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)

    def test_verifier_refuse_un_registre_modifie_apres_restitution(self):
        self._restituer()
        entree = self.officiel / "claude-code-fable-5.toml"
        entree.write_bytes(entree.read_bytes() + b"\n")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)

    def test_verifier_refuse_une_huitieme_entree_injectee_dans_la_page(self):
        page = self._restituer()
        self.page.write_text(
            page.replace(
                "</body>",
                '<article class="affirmation" data-classe="fait" '
                'data-configuration="huitieme" data-statut="declaree-non-mesuree">'
                "<p>entrée injectée</p></article></body>",
            ),
            encoding="utf-8",
        )
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)

    def test_etat_panel_non_vide_reste_refuse(self):
        etat = self.racine / M.CHEMIN_ETAT
        etat.write_text(
            etat.read_text(encoding="utf-8").replace('"panel": []', '"panel": ["x"]'),
            encoding="utf-8",
        )
        code, sortie = _principal(["restituer"], self.racine)
        self.assertEqual(code, 1, sortie)


if __name__ == "__main__":
    unittest.main()
