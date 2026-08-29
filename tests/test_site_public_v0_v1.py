# /// script
# requires-python = ">=3.12"
# ///
"""Site public V0+V1 : faits recalculés depuis les sources canoniques.

Chaque valeur attendue est relue dans les artefacts versionnés, jamais
dans le HTML. Le site ne doit porter ni vocabulaire de classement ni
requête réseau.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE))

import campagne_v1 as M  # noqa: E402
from validateur_pre_cadrage_v0 import (  # noqa: E402
    PaquetApprouveV0,
    valider_pre_cadrage_v0,
)

_PAGES = RACINE / "pages"
_CAMPAGNE_V0 = RACINE / "tasks/dev/pre-cadrage-entretien-client/campagne-v0"
_CAMPAGNE_V1 = RACINE / "tasks/dev/pre-cadrage-entretien-client/campagne-v1"
_PAQUET = RACINE / "tasks/dev/pre-cadrage-entretien-client"
_TABLE_V0 = (
    _CAMPAGNE_V0 / "metriques-decision-m10-1-v1" / "table-metriques.json"
)
_RAPPORT_V0 = (
    _CAMPAGNE_V0 / "rapport-decision-m10-2-v1" / "rapport-interne.md"
)
_PANEL_V0 = _CAMPAGNE_V0 / "panel-identites-v1" / "panel-identites.json"
_REGISTRE_V0 = (
    _CAMPAGNE_V0
    / "validation-automatique-m8-2-v1"
    / "registre-couverture-verdicts.json"
)
_STIMULUS = _PAQUET / "stimulus.md"
_TEMOINS = _PAQUET / "temoins-qualification.md"
_VALIDATEUR = RACINE / "tools" / "validateur_pre_cadrage_v0.py"

_VOCABULAIRE_CLASSEMENT = (
    "classement",
    "podium",
    "médaille",
    "medaille",
    "gagnant",
    "vainqueur",
    "score agrégé",
    "score global",
    "meilleur modèle",
    "meilleure configuration",
    "recommandation",
)

_SECTIONS_G001 = (
    "Périmètre",
    "Faits établis",
    "Contraintes critiques",
    "Inconnues",
    "Hypothèses conditionnelles",
    "Contradictions à arbitrer",
    "Risques prioritaires",
    "Questions prioritaires pour l'entretien",
    "Prochaine action",
    "Exclusions",
)


def _lire_pages() -> dict[str, str]:
    return {
        nom: (_PAGES / nom).read_text(encoding="utf-8")
        for nom in ("index.html", "v0.html", "v1.html", "methode.html")
    }


def _landmark_principal(html: str) -> str:
    match = re.search(r"<main\b[^>]*>(.*)</main>", html, re.DOTALL)
    if match is None:
        raise AssertionError("landmark principal <main> absent")
    return match.group(1)


def _attribut(balise: str, nom: str) -> str | None:
    match = re.search(
        rf"""\b{re.escape(nom)}=(['"])(.*?)\1""",
        balise,
    )
    if match is None:
        return None
    return match.group(2)


def _concatener(pages: dict[str, str]) -> str:
    return "\n".join(pages.values())


def _luminance(hex_color: str) -> float:
    brut = hex_color.lstrip("#")
    canaux = [
        int(brut[i : i + 2], 16) / 255
        for i in range(0, 6, 2)
    ]
    lineaires = [
        canal / 12.92 if canal <= 0.04045 else ((canal + 0.055) / 1.055) ** 2.4
        for canal in canaux
    ]
    return 0.2126 * lineaires[0] + 0.7152 * lineaires[1] + 0.0722 * lineaires[2]


def _contraste(fond: str, encre: str) -> float:
    clair, sombre = sorted((_luminance(fond), _luminance(encre)), reverse=True)
    return (clair + 0.05) / (sombre + 0.05)


class SitePublicV0V1Tests(unittest.TestCase):
    def test_valeurs_v0_recalculees_depuis_sources(self) -> None:
        table = json.loads(_TABLE_V0.read_text(encoding="utf-8"))
        panel = json.loads(_PANEL_V0.read_text(encoding="utf-8"))
        rapport = _RAPPORT_V0.read_text(encoding="utf-8")
        registre = json.loads(_REGISTRE_V0.read_text(encoding="utf-8"))
        self.assertEqual(table["aggregate"]["coverage"]["exact_fraction"], "1/2")
        self.assertEqual(
            table["aggregate"]["official_acceptance_rate"]["exact_fraction"],
            "0/1",
        )
        self.assertEqual(panel["panel"]["cardinality"], 2)
        identifiants = [
            entree["configuration_id"]
            for entree in panel["panel"]["configurations"]
        ]
        self.assertEqual(
            identifiants,
            ["grok46_xai_build_oauth", "kimi_k3_cursor_cli"],
        )
        par_id = {
            ligne["configuration_id"]: ligne for ligne in table["configurations"]
        }
        self.assertEqual(
            par_id["grok46_xai_build_oauth"]["official_outcome"],
            "CANDIDATE_NOT_ACCEPTABLE",
        )
        self.assertEqual(
            par_id["kimi_k3_cursor_cli"]["official_outcome"],
            "HARNESS_ERROR",
        )
        grok_auto = registre["acquisitions"][0]["automatic_verdict"]
        self.assertEqual(grok_auto["status"], "FAIL")
        self.assertEqual(grok_auto["gates"], [["G-005", True], ["G-001", False]])
        self.assertIn("status: ABSTENTION", rapport)
        pages = _concatener(_lire_pages())
        self.assertIn("1/2", pages)
        self.assertIn("0/1", pages)
        self.assertIn("CANDIDATE_NOT_ACCEPTABLE", pages)
        self.assertIn("HARNESS_ERROR", pages)
        self.assertIn("ABSTENTION", pages)
        self.assertIn("G-001", pages)
        self.assertIn("Grok 4.6", pages)
        self.assertIn("Kimi K3", pages)

    def test_valeurs_v1_recalculees_depuis_sources(self) -> None:
        etat = json.loads((_CAMPAGNE_V1 / "etat-v1.json").read_text(encoding="utf-8"))
        metriques = json.loads(
            (_CAMPAGNE_V1 / "metriques-v1.json").read_text(encoding="utf-8")
        )
        registre = json.loads(
            (
                _CAMPAGNE_V1
                / "validation-automatique-v1"
                / "registre-couverture-verdicts.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(etat["couverture"]["fraction"], "6/7")
        self.assertEqual(metriques["agregat"]["taux"], "0/6")
        self.assertEqual(len(etat["couverture"]["creneaux"]), 7)
        non_couverts = [
            creneau
            for creneau in etat["couverture"]["creneaux"]
            if not creneau["couvert"]
        ]
        self.assertEqual(
            [creneau["configuration_id"] for creneau in non_couverts],
            ["cursor-kimi-k3"],
        )
        self.assertEqual(non_couverts[0]["cause"], "HARNESS_ERROR")
        fails = [
            entree
            for entree in registre["entrees"]
            if entree["verdict"] is not None
        ]
        self.assertEqual(len(fails), 6)
        self.assertTrue(
            all(
                entree["verdict"]["statut"] == "FAIL"
                and entree["verdict"]["porte_en_cause"] == "G-001"
                for entree in fails
            )
        )
        pages = _concatener(_lire_pages())
        self.assertIn("6/7", pages)
        self.assertIn("0/6", pages)
        self.assertIn("FAIL", pages)
        self.assertIn("G-001", pages)
        self.assertIn("cursor-kimi-k3", pages)
        self.assertIn("HARNESS_ERROR", pages)
        self.assertIn("ABSTENTION", pages)
        self.assertIn("CANDIDATE_NOT_ACCEPTABLE", pages)
        self.assertIn("INCONNU", pages)
        self.assertIn("NON_DEFINI", pages)
        for identifiant in (
            "antigravity-gemini-3-7-flash",
            "claude-code-fable-5",
            "claude-code-opus-5",
            "codex-gpt-5-6-sol",
            "cursor-kimi-k3",
            "grok-build-grok-4-6",
            "zai-glm-5-3",
        ):
            self.assertIn(identifiant, pages)

    def test_protocol_stimulus_yaml_contre_frontmatter(self) -> None:
        stimulus = _STIMULUS.read_text(encoding="utf-8")
        validateur = _VALIDATEUR.read_text(encoding="utf-8")
        self.assertIn("```yaml", stimulus)
        self.assertIn("artifact_type: pre_cadrage_entretien_client", stimulus)
        self.assertIn('if not lignes or lignes[0] != "---":', validateur)
        pages = _concatener(_lire_pages())
        self.assertIn("```yaml", pages)
        self.assertIn("---", pages)
        self.assertIn("stimulus.md", pages)
        self.assertIn("validateur_pre_cadrage_v0.py", pages)
        self.assertIn("verdict mécanique", pages.lower())
        self.assertIn("interprétation permise", pages.lower())

    def test_rejeu_g001_forme_stimulus_contre_frontmatter(self) -> None:
        champs = (
            "artifact_type: pre_cadrage_entretien_client\n"
            "version: V0\n"
            "scenario: synthetique\n"
            "client_ready: false\n"
            "qualification: QUALIFIABLE\n"
            "conformite: NON_EVALUEE\n"
        )
        corps = "\n".join(
            f"# {titre}\n\nTexte minimal sans ancre.\n" for titre in _SECTIONS_G001
        )
        forme_stimulus = f"```yaml\n{champs}```\n\n{corps}"
        forme_exigee = f"---\n{champs}---\n\n{corps}"
        paquet = PaquetApprouveV0(
            manifeste=_PAQUET / "manifeste-paquet.json",
            empreinte_manifeste_approuvee=(
                "8030128d159e4203483b19f0e37692a53f01baecc38fbccaa321541c23e71a10"
            ),
            approbateur="Ayo",
            verdict_approbation="APPROUVE",
        )
        with tempfile.TemporaryDirectory() as dossier:
            chemin_stimulus = Path(dossier) / "stimulus.md"
            chemin_exige = Path(dossier) / "exige.md"
            chemin_stimulus.write_text(forme_stimulus, encoding="utf-8")
            chemin_exige.write_text(forme_exigee, encoding="utf-8")
            resultat_stimulus = valider_pre_cadrage_v0(paquet, chemin_stimulus)
            resultat_exige = valider_pre_cadrage_v0(paquet, chemin_exige)
        self.assertEqual(resultat_stimulus.statut, "FAIL")
        self.assertEqual(
            resultat_stimulus.gates,
            [("G-005", True), ("G-001", False)],
        )
        self.assertEqual(resultat_exige.statut, "FAIL")
        self.assertEqual(
            resultat_exige.gates,
            [
                ("G-005", True),
                ("G-001", True),
                ("G-002", True),
                ("G-003", False),
            ],
        )
        pages = _concatener(_lire_pages())
        self.assertIn("G-003", pages)

    def test_six_candidats_sans_frontmatter(self) -> None:
        registre = json.loads(
            (
                _CAMPAGNE_V1
                / "validation-automatique-v1"
                / "registre-couverture-verdicts.json"
            ).read_text(encoding="utf-8")
        )
        yaml_fence = 0
        preambule = 0
        frontmatter = 0
        for entree in registre["entrees"]:
            if entree["verdict"] is None:
                continue
            recu = json.loads(Path(entree["recu"]).read_text(encoding="utf-8"))
            stdout = recu["payload"]["execution"]["sortie"]["stdout"]
            candidat = M._extraire_sortie_candidate(stdout).lstrip()
            self.assertIn("artifact_type", candidat)
            if candidat.startswith("---"):
                frontmatter += 1
            elif candidat.startswith("```yaml"):
                yaml_fence += 1
            else:
                preambule += 1
        self.assertEqual(yaml_fence, 3)
        self.assertEqual(preambule, 3)
        self.assertEqual(frontmatter, 0)
        pages = _concatener(_lire_pages())
        self.assertIn("trois", pages.lower())
        self.assertIn("préambule", pages.lower())

    def test_absence_vocabulaire_classement(self) -> None:
        pages = _concatener(_lire_pages()).lower()
        for motif in _VOCABULAIRE_CLASSEMENT:
            self.assertNotIn(motif, pages, motif)

    def test_hors_ligne_liens_relatifs_et_clavier(self) -> None:
        pages = _lire_pages()
        css = (_PAGES / "styles.css").read_text(encoding="utf-8")
        corpus = _concatener(pages) + css
        self.assertNotIn("http://", corpus)
        self.assertNotIn("https://", corpus)
        self.assertNotIn("<script", corpus.lower())
        self.assertNotIn("@import", css)
        self.assertNotIn("url(http", css)
        for nom, html in pages.items():
            self.assertIn('href="./styles.css"', html, nom)
            self.assertIn('rel="stylesheet"', html, nom)
            self.assertIn("<nav", html, nom)
            self.assertIn('lang="fr"', html, nom)
            self.assertIn('name="viewport"', html, nom)
            self.assertIn("<main", html, nom)
            self.assertIn(":focus-visible", css)
            self.assertNotIn("style_gate", html, nom)
        accueil = pages["index.html"]
        for cible in ("./v0.html", "./v1.html", "./methode.html"):
            self.assertIn(f'href="{cible}"', accueil)
        for nom in ("v0.html", "v1.html", "methode.html"):
            self.assertIn('href="./index.html"', pages[nom], nom)

    def test_lien_evitement_cible_focusable(self) -> None:
        """Le lien d'évitement mène à une cible présente et focusable.

        L'ordre des attributs HTML n'est pas une preuve : on relit href
        et id, puis on exige tabindex="-1" sur la cible.
        """
        for nom, html in _lire_pages().items():
            with self.subTest(page=nom):
                saut = re.search(
                    r"<a\b([^>]*)>Aller au contenu</a>",
                    html,
                )
                self.assertIsNotNone(saut, nom)
                href = _attribut(saut.group(1), "href")
                self.assertIsNotNone(href, nom)
                self.assertTrue(href.startswith("#"), nom)
                cible = href[1:]
                self.assertTrue(cible, nom)
                cible_match = re.search(
                    rf"<([a-z]+)(\b[^>]*\bid=(['\"]){re.escape(cible)}\3[^>]*)>",
                    html,
                )
                self.assertIsNotNone(cible_match, nom)
                attributs = cible_match.group(2)
                self.assertEqual(_attribut(attributs, "tabindex"), "-1", nom)
                self.assertEqual(cible_match.group(1), "main", nom)

    def test_latences_relues_depuis_sources_sans_classement(self) -> None:
        """Chaque latence publiée est relue dans V0/V1, dans l'ordre source."""
        table_v0 = json.loads(_TABLE_V0.read_text(encoding="utf-8"))
        metriques_v1 = json.loads(
            (_CAMPAGNE_V1 / "metriques-v1.json").read_text(encoding="utf-8")
        )
        pages = _lire_pages()
        v0 = pages["v0.html"]
        v1 = pages["v1.html"]
        ids_v0_source = [
            ligne["configuration_id"] for ligne in table_v0["configurations"]
        ]
        ids_v0_page = re.findall(r"<code>(grok46_xai_build_oauth|kimi_k3_cursor_cli)</code>", v0)
        self.assertEqual(ids_v0_page[:2], ids_v0_source)
        for ligne in table_v0["configurations"]:
            axe = ligne["latency"]["pareto_axis"]
            identifiant = ligne["configuration_id"]
            self.assertIn(identifiant, v0)
            if axe.get("state") == "OBSERVED":
                for valeur in axe["raw_singleton_ms"]:
                    self.assertIn(str(valeur), v0, identifiant)
            else:
                self.assertEqual(axe.get("value"), "INCONNU")
                self.assertIn("INCONNU", v0)
        ids_v1_source = [
            ligne["configuration_id"] for ligne in metriques_v1["configurations"]
        ]
        ids_v1_page = re.findall(
            r"<th scope=\"row\"><code>([^<]+)</code></th>",
            v1,
        )
        self.assertEqual(ids_v1_page, ids_v1_source)
        for ligne in metriques_v1["configurations"]:
            identifiant = ligne["configuration_id"]
            distribution = ligne["latence_configuration"]["distribution_ms"]
            self.assertIn(identifiant, v1)
            if distribution:
                for valeur in distribution:
                    self.assertIn(str(valeur), v1, identifiant)
            else:
                self.assertEqual(distribution, [])
                self.assertIn("distribution vide", v1)
        corpus = _concatener(pages).lower()
        for interdit in ("plus rapide", "moins lent", "ordre de classement"):
            self.assertNotIn(interdit, corpus, interdit)

    def test_accueil_cadre_deux_profils_non_comparables(self) -> None:
        accueil = _lire_pages()["index.html"]
        self.assertIn("1/2", accueil)
        self.assertIn("6/7", accueil)
        self.assertIn("deux profils", accueil)
        self.assertIn("deux panels", accueil)
        self.assertIn("ne sont pas comparables", accueil)

    def test_provenance_visible_dans_le_landmark_principal(self) -> None:
        pages = _lire_pages()
        accueil = _landmark_principal(pages["index.html"])
        methode = _landmark_principal(pages["methode.html"])
        v0 = _landmark_principal(pages["v0.html"])
        v1 = _landmark_principal(pages["v1.html"])
        for fragment in (accueil, methode, v0):
            self.assertIn(
                "campagne-v0/metriques-decision-m10-1-v1/table-metriques.json",
                fragment,
            )
        for fragment in (accueil, methode, v1):
            self.assertIn("campagne-v1/etat-v1.json", fragment)
            self.assertIn("campagne-v1/metriques-v1.json", fragment)
        self.assertIn("stimulus.md", accueil)
        self.assertIn("validateur_pre_cadrage_v0.py", accueil)
        self.assertIn("stimulus.md", methode)
        self.assertIn("validateur_pre_cadrage_v0.py", methode)

    def test_contraste_et_responsive(self) -> None:
        css = (_PAGES / "styles.css").read_text(encoding="utf-8")
        variables = dict(
            re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", css)
        )
        self.assertIn("papier", variables)
        self.assertIn("encre", variables)
        rapport = _contraste(variables["papier"], variables["encre"])
        self.assertGreaterEqual(rapport, 7.0)
        if "rouille" in variables:
            self.assertGreaterEqual(
                _contraste(variables["papier"], variables["rouille"]), 4.5
            )
        self.assertIn("@media", css)
        self.assertIn("max-width", css)
        for html in _lire_pages().values():
            self.assertIn("width=device-width", html)


if __name__ == "__main__":
    unittest.main()
