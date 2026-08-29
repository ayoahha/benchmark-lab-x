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
l'implémentation : couverture 6/7, sept configurations comparables, six
taux 0/1, un taux NON_DEFINI et six distributions de latence observées, coût
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
import hashlib
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

from tests._helpers_v1 import (  # noqa: E402
    realigner_chaine_recus,
    retirer_couverture_publiee,
)

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
_COMPARABLES = (
    "antigravity-gemini-3-7-flash",
    "claude-code-fable-5",
    "claude-code-opus-5",
    "codex-gpt-5-6-sol",
    "cursor-kimi-k3",
    "grok-build-grok-4-6",
    "zai-glm-5-3",
)
_ABSENTS = ()
_PREFLIGHTS_READY = (
    "antigravity-gemini-3-7-flash",
    "zai-glm-5-3",
)
_PREFLIGHTS_COMPLETION = (
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
_AUTRES_LATENCES_MS = ("37605", "126870", "78017", "179590")

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
        self.assertIn("6 décisions", page)
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
        # Le taux NON_DEFINI de Cursor impose l'abstention de cet axe
        self.assertIn("NON_DEFINI", axe_taux.group(0))
        self.assertIn("ABSTENTION", axe_taux.group(0))
        axe_latence = _MOTIF_ARTICLE_AXE["latence-preenregistree"].search(
            page
        )
        self.assertIsNotNone(axe_latence)
        self.assertIn(_LATENCE_ANTIGRAVITY_MS, axe_latence.group(0))
        self.assertIn(_LATENCE_ZAI_MS, axe_latence.group(0))
        for latence in _AUTRES_LATENCES_MS:
            self.assertIn(latence, axe_latence.group(0))
        # DISTRIBUTION_COMPLETE ne préenregistre aucune statistique : cet
        # axe s'abstient sans calculer de minimum à partir des distributions
        self.assertIn("ABSTENTION", axe_latence.group(0))
        self.assertIn("statistique", axe_latence.group(0))
        self.assertIn(
            "au moins une distribution n'a pas exactement une valeur",
            axe_latence.group(0),
        )
        self.assertIn(
            "cursor-kimi-k3</code> <code>[]</code> ms",
            axe_latence.group(0),
        )
        self.assertNotIn(
            "porte plusieurs valeurs", axe_latence.group(0)
        )
        self.assertNotIn("valeur minimale", axe_latence.group(0))

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
        # Scénario isolé : toutes les preuves Fable courantes et leurs
        # projections dérivées sont retirées ensemble avant restitution
        realigner_chaine_recus(
            M,
            self.racine,
            _CAMPAGNE,
            M.CHEMIN_REGISTRE_VALIDATION,
            M.CHEMIN_ETAT,
            configurations_retirees={"claude-code-fable-5"},
        )
        chemin_manifeste = self.racine / M.CHEMIN_MANIFESTE_DOSSIERS
        manifeste = json.loads(chemin_manifeste.read_text(encoding="utf-8"))
        manifeste["lot_vide"]["comptage_statuts"] = {
            "ABSENTE": 3,
            "FAIL": 5,
        }
        chemin_manifeste.write_bytes(M.octets_canoniques(manifeste))
        chemin_etat = self.racine / M.CHEMIN_ETAT
        etat = json.loads(chemin_etat.read_text(encoding="utf-8"))
        etat.pop("couverture", None)
        etat.pop("execution_completion", None)
        chemin_etat.write_bytes(M.octets_canoniques(etat))
        code, sortie = self._commande("etat")
        self.assertEqual(code, 0, sortie)
        code, sortie = self._commande("metriques")
        self.assertEqual(code, 0, sortie)
        page = self._restituer()
        self.assertIn(
            ' data-comparaison-absence="claude-code-fable-5"', page
        )
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
        # La configuration Fable verrouillée change d'empreinte ; les reçus
        # de la fixture sont réalignés sur ce fichier courant, de sorte que
        # seule la fenêtre du verrou historique reste divergente
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
        sha_configuration = hashlib.sha256(chemin.read_bytes()).hexdigest()
        repertoire = self.racine / _CAMPAGNE / "recus-v1"
        mutations = {}
        for recu in repertoire.iterdir():
            enveloppe = json.loads(recu.read_text(encoding="utf-8"))
            if (
                enveloppe["payload"]["configuration"]["identifiant"]
                == "claude-code-fable-5"
            ):
                mutations[recu.name] = lambda charge: charge[
                    "configuration"
                ].update(sha256=sha_configuration)
        realigner_chaine_recus(
            M,
            self.racine,
            _CAMPAGNE,
            M.CHEMIN_REGISTRE_VALIDATION,
            M.CHEMIN_ETAT,
            mutations=mutations,
        )
        code, sortie = self._commande("metriques")
        self.assertEqual(code, 0, sortie)
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

    def test_completion_present_sans_verrou_jamais_cite_ni_promu(self):
        # Arbre partiel : verrou de complétion présent sans verrou de
        # campagne ni préflight — aucun span ne le cite, donc son
        # empreinte n'entre pas dans la provenance ; restituer et
        # verifier-restitution restent cohérents
        destination = self.racine / M.CHEMIN_VERROU_COMPLETION
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RACINE / M.CHEMIN_VERROU_COMPLETION, destination)
        code, sortie = self._commande("restituer")
        self.assertEqual(code, 0, sortie)
        page = self.page.read_text(encoding="utf-8")
        self.assertNotIn("verrou-completion.json", page)
        self.assertNotIn("APTITUDE_STATIQUE_PRETE", page)
        code, sortie = self._commande("verifier-restitution")
        self.assertEqual(code, 0, sortie)


class RetoursProprietairesTests(_ArbrePreuvesReelles):
    """Les douze retours propriétaires de la revue humaine : instantanés
    historiques datés, blockers explicites, autorités distinguées et
    parcours V1 au statut dérivé des preuves. Aucune preuve n'est
    modifiée ; seule la lisibilité change."""

    def test_encadre_blocages_reels_en_tete(self):
        page = self._restituer()
        self.assertEqual(page.count('<section id="blocages-reels"'), 1)
        # L'encadré précède l'état courant : il est lu en premier
        self.assertLess(
            page.index('<section id="blocages-reels"'),
            page.index('<section id="etat-v1">'),
        )
        self.assertIn("Blocages réels à lever", page)
        encadre = page.split('<section id="blocages-reels"', 1)[1].split(
            "</section>", 1
        )[0]
        for bloc in ("historique", "inconnues", "actions"):
            self.assertEqual(
                encadre.count(f' data-blocage="{bloc}"'), 1, bloc
            )
        self.assertIn("NOT_GRANTED", encadre)
        self.assertIn("D-V1-04", encadre)
        self.assertIn("identité réellement servie", encadre)
        self.assertIn("D-V1-01", encadre)

    def test_panel_inconnu_etiquete_instantane_historique(self):
        page = self._restituer()
        section = page.split('<section id="panel-officiel">', 1)[1].split(
            "</section>", 1
        )[0]
        self.assertIn("instantané historique", section)
        self.assertIn("D-V1-01", section)
        self.assertIn("2026-08-22", section)
        # L'état validé et daté est montré séparément, sans réécrire
        # les INCONNU historiques
        self.assertEqual(section.count(' data-plans-valides="resume"'), 1)
        self.assertIn("sources-plans-v1.toml", section)
        self.assertIn('href="#verrou-campagne"', section)
        self.assertIn("INCONNU", section)

    def test_explication_ready_identite_servie_inconnue(self):
        page = self._restituer()
        for identifiant in _PREFLIGHTS_READY:
            motif = re.compile(
                '<article class="affirmation"[^>]*'
                f' data-explication-preflight="{identifiant}"[^>]*>'
                ".*?</article>",
                re.DOTALL,
            )
            article = motif.search(page)
            self.assertIsNotNone(article, identifiant)
            texte = article.group(0)
            self.assertIn("générative", texte)
            self.assertIn("identite_reellement_servie", texte)
            self.assertIn("INCONNU", texte)
            self.assertIn("Blocage exact", texte)
            self.assertIn("observation générative", texte)
            self.assertIn("autorité propriétaire", texte)
            self.assertIn('class="blocage"', texte)

    def test_explication_missing_observation_cinq_configurations(self):
        page = self._restituer()
        for identifiant in _PREFLIGHTS_COMPLETION:
            motif = re.compile(
                '<article class="affirmation"[^>]*'
                f' data-explication-preflight="{identifiant}"[^>]*>'
                ".*?</article>",
                re.DOTALL,
            )
            article = motif.search(page)
            self.assertIsNotNone(article, identifiant)
            texte = article.group(0)
            # La CLI n'est jamais dite absente : le reçu prouve des
            # observations locales
            self.assertIn("n'est pas absente", texte)
            self.assertIn("ne prouve aucun des faits distants", texte)
            self.assertIn("READY", texte)
            self.assertIn("APTITUDE_STATIQUE_PRETE", texte)
            self.assertIn("ne prouve jamais", texte)
            self.assertIn("Blocage restant", texte)
            self.assertIn('class="blocage"', texte)
            self.assertIn("verrou-completion.json", texte)

    def test_autorites_not_granted_historique_et_cinq_restants(self):
        page = self._restituer()
        section = page.split(
            '<section id="autorite-acquisition">', 1
        )[1].split("</section>", 1)[0]
        # NOT_GRANTED historique jamais formulé comme interdiction
        # actuelle sur les deux créneaux exécutés sous D-V1-04
        self.assertIn("état historique", section)
        self.assertIn("aucune interdiction actuelle", section)
        self.assertIn("verrou-completion.json", section)
        self.assertIn("zéro créneau exécuté", section)
        self.assertIn("nouvelle autorité propriétaire bornée", section)
        # Portée réellement dérivée : D-V1-04 ne nomme aucune des
        # configurations en attente ; aucune négative universelle sur
        # des artefacts non chargés
        self.assertIn("ne nomme aucune de ces configurations", section)
        self.assertNotIn("Aucun artefact d'autorité versionné", page)

    def test_explication_fail_g001(self):
        page = self._restituer()
        section = page.split(
            '<section id="validation-automatique">', 1
        )[1].split("</section>", 1)[0]
        self.assertEqual(
            section.count(' data-explication-validation="fail-g-001"'), 1
        )
        self.assertIn("G-005", section)
        self.assertIn("G-001", section)
        self.assertIn("CANDIDATE_ERROR", section)
        self.assertIn("enveloppe", section)
        self.assertIn("vocabulaire fermé", section)
        self.assertIn("dans l'ordre", section)
        self.assertIn("registre-verite.md", section)

    def test_juge_fantome_et_relecteur_non_sollicite(self):
        page = self._restituer()
        section = page.split('<section id="verdicts-humains"', 1)[1].split(
            "</section>", 1
        )[0]
        self.assertIn("DISABLED", section)
        self.assertIn("juge synthétique", section)
        self.assertIn("pas un blocage", section)
        self.assertIn("D-V1-06", section)
        self.assertIn("zéro dossier", section)
        self.assertIn("aucune", section)
        self.assertIn("PASS", section)
        self.assertIn("ne peut pas la fabriquer", section)
        # DISABLED est un fait ; le rationnel du juge fantôme est une
        # déduction raisonnée, prémisses visibles, U-015 citée
        article = re.search(
            '<article class="affirmation"[^>]*'
            ' data-explication-verdicts="juge-fantome"[^>]*>.*?</article>',
            section,
            re.DOTALL,
        )
        self.assertIsNotNone(article)
        self.assertIn('data-classe="deduction"', article.group(0))
        self.assertIn("data-premisses=", article.group(0))
        self.assertIn("U-015", article.group(0))

    def test_plans_sans_universelle_validee_datee(self):
        page = self._restituer()
        # L'universelle « validés et datés » ne correspond pas aux
        # sources : quatre dates de publication restent NON_DEFINI et
        # l'entrée Codex reste une déduction raisonnée
        self.assertNotIn("validés et datés", page)
        article = re.search(
            '<article class="affirmation"[^>]*'
            ' data-plans-valides="resume"[^>]*>.*?</article>',
            page,
            re.DOTALL,
        )
        self.assertIsNotNone(article)
        texte = article.group(0)
        self.assertIn("date de consultation", texte)
        self.assertIn("FAIT_ETABLI", texte)
        self.assertIn("DEDUCTION_RAISONNEE", texte)
        self.assertIn("NON_DEFINI", texte)
        self.assertIn("4 entrée(s)", texte)
        self.assertIn("V1_XS_07_PLAN_CONTRACT", texte)

    def test_identites_incompletes_jamais_realisees(self):
        # Dérivation unitaire : la configuration réelle porte des champs
        # INCONNU, l'identité n'est pas complète ; une copie sans INCONNU
        # devient complète
        chemin = (
            self.racine
            / _CAMPAGNE
            / "registre-panel-v1"
            / "claude-code-fable-5.toml"
        )
        import tomllib

        donnees = tomllib.loads(chemin.read_text(encoding="utf-8"))
        self.assertFalse(M._identite_complete(donnees))

        def _remplacer(valeur):
            if isinstance(valeur, dict):
                return {cle: _remplacer(val) for cle, val in valeur.items()}
            if isinstance(valeur, list):
                return [_remplacer(val) for val in valeur]
            return "x" if valeur == "INCONNU" else valeur

        self.assertTrue(M._identite_complete(_remplacer(donnees)))
        # Sur la page : l'étape panel reste PARTIEL, jamais RÉALISÉ,
        # tant que les identités requises restent incomplètes
        page = self._restituer()
        article = re.search(
            '<article class="affirmation"[^>]*'
            ' data-etape="panel-abonnement"[^>]*>.*?</article>',
            page,
            re.DOTALL,
        )
        self.assertIsNotNone(article)
        self.assertIn(
            'data-parcours-statut="partiel"', article.group(0)
        )
        self.assertIn("INCONNU", article.group(0))
        self.assertIn("matérialisé", article.group(0))

    def test_verrou_completion_altere_refuse_avant_rendu(self):
        # L'autorisation additive R5 épingle le verrou : une divergence de
        # la source est refusée avant tout rendu, jamais réparée
        chemin = self.racine / M.CHEMIN_VERROU_COMPLETION
        verrou = json.loads(chemin.read_text(encoding="utf-8"))
        verrou["aptitude_statique"]["signifie"] = "SENS_DIVERGENT_TEST"
        verrou["aptitude_statique"]["ne_prouve_jamais"] = [
            "PREUVE_DIVERGENTE_TEST"
        ]
        chemin.write_text(
            json.dumps(verrou, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        code, sortie = self._commande("restituer")
        self.assertEqual(code, 1)
        self.assertIn("LOCKED_ARTIFACT_CHANGED", sortie)

    def test_parcours_v1_statuts_derives_des_preuves(self):
        page = self._restituer()
        self.assertEqual(page.count(' data-parcours-statut="realise"'), 4)
        self.assertEqual(page.count(' data-parcours-statut="partiel"'), 1)
        self.assertEqual(page.count(' data-parcours-statut="bloque"'), 1)
        # Aucune étape « à venir » quand des preuves existent
        self.assertEqual(page.count('data-marqueur="a-venir"'), 0)
        noms = re.findall(r' data-etape="([^"]+)"', page)
        self.assertEqual(noms, [nom for nom, _, _, _ in M.ETAPES_FUTURES])
        self.assertIn("RÉALISÉ", page)
        self.assertIn("PARTIEL", page)
        self.assertIn("BLOQUÉ", page)
        section = page.split('<section id="etapes-futures">', 1)[1].split(
            "</section>", 1
        )[0]
        # Panel : PARTIEL, identités requises incomplètes (INCONNU)
        self.assertIn(
            ' data-etape="panel-abonnement" data-parcours-statut="partiel"',
            section,
        )
        # Reçus immuables : RÉALISÉ sur son propre critère « chaque
        # acquisition », dénominateur = acquisitions, pas configurations
        article_recus = re.search(
            '<article class="affirmation"[^>]*'
            ' data-etape="recus-immuables"[^>]*>.*?</article>',
            section,
            re.DOTALL,
        )
        self.assertIsNotNone(article_recus)
        self.assertIn(
            'data-parcours-statut="realise"', article_recus.group(0)
        )
        self.assertIn("9 acquisition(s)", article_recus.group(0))
        self.assertIn("9 reçu(s)", article_recus.group(0))
        self.assertIn("7 configuration(s)", article_recus.group(0))
        self.assertIn("ne complète pas le panel", article_recus.group(0))
        # Acceptabilité : bloquée par zéro PASS sur le lot courant
        self.assertIn("zéro verdict automatique", section)

    def test_refuse_statut_parcours_altere(self):
        page = self._restituer()
        sortie = self._verifier_apres_injection(
            page,
            page.replace(
                ' data-parcours-statut="bloque"',
                ' data-parcours-statut="realise"',
            ),
        )
        self.assertIn("parcours", sortie)

    def test_verifier_conforme_et_regeneration_byte_identique(self):
        premiere = self._restituer()
        code, sortie = self._verifier()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self._restituer(), premiere)


class RenvoiGuideUtilisationTests(_ArbrePreuvesReelles):
    """V1-XS-15 : la restitution renvoie vers le guide d'utilisation, par un
    lien relatif utilisable hors ligne depuis la page ouverte localement."""

    # Littéral indépendant : chemin relatif de index.html vers le guide
    _LIEN = "../guide-utilisation-v1/README.md"

    def test_page_porte_le_lien_relatif_vers_le_guide(self):
        page = self._restituer()
        self.assertEqual(page.count(f'href="{self._LIEN}"'), 1)

    def test_lien_designe_un_fichier_present_dans_le_depot(self):
        cible = (RACINE / M.CHEMIN_PAGE).parent / self._LIEN
        self.assertTrue(cible.resolve().is_file(), cible)

    def test_lien_ne_sort_pas_du_depot_et_reste_hors_ligne(self):
        page = self._restituer()
        depart = page.index(f'href="{self._LIEN}"')
        contexte = page[depart - 200 : depart + 200]
        self.assertNotIn("http://", contexte)
        self.assertNotIn("https://", contexte)

    def test_lien_survit_a_la_regeneration_et_a_la_verification(self):
        premiere = self._restituer()
        code, sortie = self._verifier()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self._restituer(), premiere)
        self.assertIn(f'href="{self._LIEN}"', premiere)


if __name__ == "__main__":
    unittest.main()
