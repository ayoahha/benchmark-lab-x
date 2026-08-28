# /// script
# requires-python = ">=3.12"
# ///
"""Restitution complète V1-XS-14 au seam public, sans appel distant.

Chaque test passe par `principal(["restituer"])` et
`principal(["verifier-restitution"])` avec une racine de dépôt
temporaire où les preuves versionnées réelles sont copiées. Les valeurs
attendues sont des littéraux indépendants issus de la lecture humaine
des preuves versionnées (etat-v1.json, metriques-v1.json,
cout-abonnement-v1.json, verrou.json), jamais un recalcul de
l'implémentation : couverture 2/7, deux configurations comparables aux
taux 0/1 et aux distributions de latence [22925] et [199430] ms, coût
d'abonnement littéralement NON_DEFINI, attestation du panel verrouillé
datée 2026-08-22, fenêtre de fraîcheur EXACT_LOCK_EVENT_BASED_NO_TTL.
La restitution complète évalue chaque déclencheur d'abstention U-018 et
ne rend une comparaison strictement intra-panel abonnement, sur trois
axes figés, que lorsque les preuves versionnées l'autorisent. Aucun
appel candidat, aucune acquisition, aucune mesure, aucun classement
général, aucun vainqueur, aucun score agrégé.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))
# La racine du dépôt rend le package tests importable quel que soit le
# lanceur (pytest direct ou python -m pytest)
sys.path.insert(0, str(RACINE))

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
_SOURCES_AUTORISEES = tuple(chemin for chemin, _ in M.SOURCES_AUTORISEES)

# Littéraux indépendants lus dans les preuves versionnées
_FAMILLES = (
    "identite",
    "provenance",
    "fraicheur",
    "comparabilite",
    "preference",
)
_AXES = (
    "taux-acceptable",
    "cout-par-sortie-acceptable",
    "latence-preenregistree",
)
_COMPARABLES = ("antigravity-gemini-3-7-flash", "zai-glm-5-3")
_ABSENTS = (
    "claude-code-fable-5",
    "claude-code-opus-5",
    "codex-gpt-5-6-sol",
    "cursor-kimi-k3",
    "grok-build-grok-4-6",
)
_DATE_ATTESTATION = "2026-08-22"
_FENETRE = "EXACT_LOCK_EVENT_BASED_NO_TTL"
_EFFET_FENETRE = "HOLD_STOP_NO_CROSS_EVENT_COMPARISON"
_LATENCE_ANTIGRAVITY_MS = "22925"
_LATENCE_ZAI_MS = "199430"

_MOTIF_ARTICLE_AXE = {
    axe: re.compile(
        '<article class="affirmation"[^>]*'
        f' data-axe-comparaison="{axe}"[^>]*>.*?</article>',
        re.DOTALL,
    )
    for axe in _AXES
}
_MOTIF_SPAN_SOURCE = re.compile(
    '<span class="source" data-chemin="[^"]+" data-sha256="[a-f0-9]{64}">'
    ".*?</span>"
)


class _ArbrePreuvesReelles(unittest.TestCase):
    """Copie de l'arbre de preuves versionnées réel : branche décidée par
    les preuves courantes."""

    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        shutil.copytree(RACINE / _CAMPAGNE, self.racine / _CAMPAGNE)
        for relatif in _SOURCES_AUTORISEES:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        for nom in _FICHIERS_PAQUET:
            destination = (
                self.racine / _SOURCES_PAQUET.relative_to(RACINE) / nom
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_SOURCES_PAQUET / nom, destination)
        self.page = self.racine / M.CHEMIN_PAGE

    def _commande(self, *arguments: str) -> tuple[int, str]:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = M.principal(list(arguments), racine=self.racine)
        return code, sortie.getvalue()

    def _restituer(self) -> str:
        code, sortie = self._commande("restituer")
        self.assertEqual(code, 0, sortie)
        return self.page.read_text(encoding="utf-8")

    def _verifier(self) -> tuple[int, str]:
        return self._commande("verifier-restitution")

    def _verifier_apres_injection(
        self, originale: str, modifiee: str
    ) -> str:
        """L'injection est refusée au seam public, puis la page restaurée
        redevient conforme. Rend la sortie du refus."""
        self.assertNotEqual(modifiee, originale)
        self.page.write_text(modifiee, encoding="utf-8")
        code, sortie = self._verifier()
        self.assertNotEqual(code, 0)
        self.page.write_text(originale, encoding="utf-8")
        code, _ = self._verifier()
        self.assertEqual(code, 0)
        return sortie

    def _injecter_article(self, page: str, texte: str) -> str:
        """Article de forme valide (classe MSW, source citée existante)
        ajouté en fin de page : seule la substance interdite le distingue."""
        span = _MOTIF_SPAN_SOURCE.search(page)
        assert span is not None
        return page.replace(
            "</body>",
            '<article class="affirmation" data-classe="fait">'
            f"<p>{texte}</p>{span.group(0)}</article></body>",
        )


class RestitutionCompleteComparaisonTests(_ArbrePreuvesReelles):
    """Preuves courantes : les déclencheurs bloquants sont éteints, la
    comparaison située intra-panel est rendue sur les trois axes."""

    def test_section_et_cinq_declencheurs_evalues(self):
        page = self._restituer()
        self.assertEqual(
            page.count(' data-restitution-complete="section"'), 1
        )
        self.assertEqual(
            page.count(' data-declencheur-abstention="'), len(_FAMILLES)
        )
        for famille in _FAMILLES:
            self.assertEqual(
                page.count(f' data-declencheur-abstention="{famille}"'),
                1,
                famille,
            )

    def test_cadre_situe_date_fenetre_profil_panel_absences(self):
        page = self._restituer()
        self.assertEqual(page.count(' data-comparaison-situee="cadre"'), 1)
        self.assertEqual(
            page.count(' data-comparaison-profil="abonnement"'), 1
        )
        self.assertIn(
            f' data-comparaison-date="{_DATE_ATTESTATION}"', page
        )
        self.assertIn(f' data-comparaison-fenetre="{_FENETRE}"', page)
        self.assertIn(_EFFET_FENETRE, page)
        self.assertEqual(
            page.count(' data-comparaison-absence="'), len(_ABSENTS)
        )
        for identifiant in _ABSENTS:
            self.assertIn(
                f' data-comparaison-absence="{identifiant}"', page
            )
        # Panel situé : le canon exact de couverture reste visible
        self.assertIn("2 décisions", page)
        self.assertEqual(
            page.count(' data-comparaison-situee="abstention"'), 0
        )

    def test_trois_axes_exacts_et_valeurs_litterales(self):
        page = self._restituer()
        self.assertEqual(page.count(' data-axe-comparaison="'), len(_AXES))
        for axe in _AXES:
            self.assertEqual(
                page.count(f' data-axe-comparaison="{axe}"'), 1, axe
            )
        axe_taux = _MOTIF_ARTICLE_AXE["taux-acceptable"].search(page)
        self.assertIsNotNone(axe_taux)
        for identifiant in _COMPARABLES:
            self.assertIn(identifiant, axe_taux.group(0))
        self.assertIn("0/1", axe_taux.group(0))
        # Taux égaux à zéro : aucun maximum strict, aucun candidat promu
        self.assertIn("aucun maximum strict", axe_taux.group(0).lower())
        axe_latence = _MOTIF_ARTICLE_AXE["latence-preenregistree"].search(
            page
        )
        self.assertIsNotNone(axe_latence)
        self.assertIn(_LATENCE_ANTIGRAVITY_MS, axe_latence.group(0))
        self.assertIn(_LATENCE_ZAI_MS, axe_latence.group(0))
        # 22925 < 199430 : la valeur minimale préenregistrée appartient à
        # antigravity-gemini-3-7-flash, sur cet axe seulement
        self.assertIn("valeur minimale", axe_latence.group(0))
        self.assertIn("antigravity-gemini-3-7-flash", axe_latence.group(0))

    def test_axe_monetaire_abstention_non_defini_litteral(self):
        page = self._restituer()
        self.assertEqual(
            page.count(
                ' data-axe-abstention="cout-par-sortie-acceptable"'
            ),
            1,
        )
        axe_cout = _MOTIF_ARTICLE_AXE["cout-par-sortie-acceptable"].search(
            page
        )
        self.assertIsNotNone(axe_cout)
        self.assertIn("NON_DEFINI", axe_cout.group(0))
        self.assertIn("ABSTENTION", axe_cout.group(0))
        self.assertIn("Preuve absente :", axe_cout.group(0))
        self.assertIn("Action humaine possible :", axe_cout.group(0))

    def test_verifier_conforme_et_regeneration_byte_identique(self):
        premiere = self._restituer()
        code, sortie = self._verifier()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self._restituer(), premiere)


class RefusInjectionsTests(_ArbrePreuvesReelles):
    """Chaque injection est refusée via l'interface publique
    verifier-restitution, page restaurée conforme ensuite."""

    def test_refuse_vainqueur_universel(self):
        page = self._restituer()
        sortie = self._verifier_apres_injection(
            page,
            self._injecter_article(
                page, "vainqueur universel : antigravity-gemini-3-7-flash"
            ),
        )
        self.assertIn("motif interdit", sortie)

    def test_refuse_classement_general(self):
        page = self._restituer()
        sortie = self._verifier_apres_injection(
            page,
            self._injecter_article(
                page, "classement général du panel abonnement"
            ),
        )
        self.assertIn("motif interdit", sortie)

    def test_refuse_score_agrege(self):
        page = self._restituer()
        sortie = self._verifier_apres_injection(
            page,
            self._injecter_article(
                page, "score agrégé des trois axes : 0.42"
            ),
        )
        self.assertIn("motif interdit", sortie)

    def test_refuse_comparaison_inter_profils(self):
        page = self._restituer()
        sortie = self._verifier_apres_injection(
            page,
            self._injecter_article(
                page,
                "le profil abonnement surpasse le profil API mesuré en V0",
            ),
        )
        self.assertIn("inter-profils", sortie)

    def test_refuse_axe_omis(self):
        page = self._restituer()
        article = _MOTIF_ARTICLE_AXE["latence-preenregistree"].search(page)
        self.assertIsNotNone(article)
        sortie = self._verifier_apres_injection(
            page, page.replace(article.group(0), "")
        )
        self.assertIn("latence-preenregistree", sortie)

    def test_refuse_date_omise(self):
        page = self._restituer()
        sortie = self._verifier_apres_injection(
            page,
            page.replace(
                f' data-comparaison-date="{_DATE_ATTESTATION}"', ""
            ),
        )
        self.assertIn("date de comparaison omise", sortie)

    def test_refuse_absences_omises(self):
        page = self._restituer()
        sortie = self._verifier_apres_injection(
            page,
            page.replace(
                ' data-comparaison-absence="', ' data-retire="'
            ),
        )
        self.assertIn("absences omises", sortie)

    def test_refuse_conversion_jeton_non_defini(self):
        page = self._restituer()
        sortie = self._verifier_apres_injection(
            page, page.replace("NON_DEFINI", "0 USD")
        )
        self.assertIn("jeton attendu absent", sortie)
        self.assertIn("NON_DEFINI", sortie)

    def test_refuse_conversion_jeton_abstention(self):
        page = self._restituer()
        sortie = self._verifier_apres_injection(
            page, page.replace("ABSTENTION", "COMPARAISON")
        )
        self.assertIn("jeton attendu absent", sortie)
        self.assertIn("ABSTENTION", sortie)

    def test_refuse_article_additif_meme_bien_forme(self):
        page = self._restituer()
        self._verifier_apres_injection(
            page,
            self._injecter_article(
                page, "note additionnelle sans substance interdite"
            ),
        )


class TauxNonDefiniComparableTests(_ArbrePreuvesReelles):
    """Ligne COMPARABLE à dénominateur décidable nul : décision normative
    non décidable, taux littéralement NON_DEFINI. L'axe taux s'abstient
    sans traceback ; aucune fraction n'est construite."""

    def test_axe_taux_abstention_sans_traceback(self):
        chemin_table = self.racine / M.CHEMIN_TABLE_METRIQUES
        table = json.loads(chemin_table.read_text(encoding="utf-8"))
        for ligne in table["configurations"]:
            if ligne["configuration_id"] == "zai-glm-5-3":
                ligne["numerateur"] = 0
                ligne["denominateur_decidable"] = 0
                ligne["taux"] = "NON_DEFINI"
        chemin_table.write_text(
            json.dumps(table, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        code, sortie = self._commande("restituer")
        self.assertEqual(code, 0, sortie)
        page = self.page.read_text(encoding="utf-8")
        self.assertEqual(
            page.count(' data-axe-abstention="taux-acceptable"'), 1
        )
        axe_taux = _MOTIF_ARTICLE_AXE["taux-acceptable"].search(page)
        self.assertIsNotNone(axe_taux)
        self.assertIn("NON_DEFINI", axe_taux.group(0))
        self.assertIn("ABSTENTION", axe_taux.group(0))
        self.assertIn("Preuve absente :", axe_taux.group(0))
        self.assertIn("Action humaine possible :", axe_taux.group(0))
        # La table mutée de la fixture reste détectée fail-closed par le
        # contrôle préexistant de fidélité aux sources, jamais réparée
        code, sortie = self._verifier()
        self.assertNotEqual(code, 0)
        self.assertIn("ligne de métriques infidèle", sortie)


class FraicheurDeclencheeTests(_ArbrePreuvesReelles):
    """Un artefact verrouillé modifié après le verrou est un événement
    matériel LOCKED_ARTIFACT_CHANGED : la comparaison s'abstient."""

    def test_artefact_verrouille_modifie_impose_abstention(self):
        # claude-code-fable-5.toml est verrouillé sans reçu officiel : un
        # commentaire ajouté change son empreinte sans changer ses données
        chemin = (
            self.racine
            / _CAMPAGNE
            / "registre-panel-v1"
            / "claude-code-fable-5.toml"
        )
        chemin.write_text(
            chemin.read_text(encoding="utf-8")
            + "# empreinte modifiée après verrou\n",
            encoding="utf-8",
        )
        code, sortie = self._commande("restituer")
        self.assertEqual(code, 0, sortie)
        page = self.page.read_text(encoding="utf-8")
        self.assertEqual(
            page.count(
                ' data-declencheur-abstention="fraicheur"'
                ' data-declenche="oui"'
            ),
            1,
        )
        self.assertIn("LOCKED_ARTIFACT_CHANGED", page)
        self.assertIn("claude-code-fable-5.toml", page)
        self.assertEqual(
            page.count(' data-comparaison-situee="abstention"'), 1
        )
        self.assertEqual(page.count(' data-axe-comparaison="'), 0)
        # Le vérificateur préexistant refuse ensuite fail-closed toute
        # empreinte citée divergente d'un artefact verrouillé modifié :
        # l'état muté reste invérifiable, jamais réparé
        code, sortie = self._verifier()
        self.assertNotEqual(code, 0)
        self.assertIn("empreinte citée divergente", sortie)


class RestitutionCompleteAbstentionTests(unittest.TestCase):
    """Arbre minimal XS-01 : preuves absentes, la branche est
    l'abstention, chaque déclencheur actif nomme preuve absente et
    action humaine."""

    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        entrees = _SOURCES_AUTORISEES + (M.CHEMIN_ETAT.as_posix(),)
        for relatif in entrees:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        retirer_couverture_publiee(self.racine / M.CHEMIN_ETAT)
        self.page = self.racine / M.CHEMIN_PAGE

    def _commande(self, *arguments: str) -> tuple[int, str]:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = M.principal(list(arguments), racine=self.racine)
        return code, sortie.getvalue()

    def test_abstention_nomme_preuves_absentes_et_actions(self):
        code, sortie = self._commande("restituer")
        self.assertEqual(code, 0, sortie)
        page = self.page.read_text(encoding="utf-8")
        self.assertEqual(
            page.count(' data-restitution-complete="section"'), 1
        )
        self.assertEqual(
            page.count(' data-comparaison-situee="abstention"'), 1
        )
        self.assertEqual(page.count(' data-axe-comparaison="'), 0)
        self.assertEqual(page.count(' data-comparaison-situee="cadre"'), 0)
        for famille in ("identite", "provenance", "comparabilite"):
            self.assertEqual(
                page.count(
                    f' data-declencheur-abstention="{famille}"'
                    ' data-declenche="oui"'
                ),
                1,
                famille,
            )
        self.assertIn("Preuve absente :", page)
        self.assertIn("Action humaine possible :", page)
        code, sortie = self._commande("verifier-restitution")
        self.assertEqual(code, 0, sortie)


if __name__ == "__main__":
    unittest.main()
