# /// script
# requires-python = ">=3.12"
# ///
"""Commande metriques V1-XS-12B au seam public, sans appel distant.

Chaque test passe par `principal(["metriques"])` avec une racine de dépôt
temporaire : les preuves versionnées réelles y sont copiées, ou des doubles
locaux valides y sont construits pour les branches absentes du lot réel
(divergence de comparabilité). La couverture publiée par V1-XS-12A est
reprise à l'identique, jamais recalculée : 6/7, six décisions
CANDIDATE_NOT_ACCEPTABLE, un incident HARNESS_ERROR non couvert, aucune
sortie OFFICIALLY_ACCEPTABLE. Les sept configurations portant une preuve
d'acquisition sont comptées comparables. La
politique de latence est éprouvée en chemin pur injecté : la branche
reconnaît uniquement LATENCY_MEDIAN_SUCCESS_E2E et valide le contrat
exact de la source locale versionnée ; le verrou courant ne porte aucun
champ de statistique et la campagne publie la distribution complète.
Aucun appel candidat, aucune acquisition et aucune dépense n'ont lieu.
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

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import campagne_v1 as M  # noqa: E402

from tests._helpers_v1 import realigner_chaine_recus  # noqa: E402

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
# Panel déclaré du registre officiel versionné, dans l'ordre des fichiers
_PANEL = (
    "antigravity-gemini-3-7-flash",
    "claude-code-fable-5",
    "claude-code-opus-5",
    "codex-gpt-5-6-sol",
    "cursor-kimi-k3",
    "grok-build-grok-4-6",
    "zai-glm-5-3",
)
_DECIDABLES = tuple(ident for ident in _PANEL if ident != "cursor-kimi-k3")
_NON_DECIDABLES = ("cursor-kimi-k3",)
_LATENCES_ATTENDUES = {
    "antigravity-gemini-3-7-flash": [22925],
    "claude-code-fable-5": [37605],
    "claude-code-opus-5": [126870],
    "codex-gpt-5-6-sol": [78017],
    "cursor-kimi-k3": [],
    "grok-build-grok-4-6": [179590],
    "zai-glm-5-3": [199430],
}
# Sept composantes d'effort humain du contrat U-025, sans conversion
_COMPOSANTES_EFFORT = (
    "configuration",
    "integration",
    "execution",
    "human_review",
    "verification",
    "maintenance",
    "report_production",
)


class _ArbrePreuvesReelles:
    racine: Path
    chemin_table: Path

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
        self.chemin_table = self.racine / M.CHEMIN_TABLE_METRIQUES
        self.page = self.racine / M.CHEMIN_PAGE

    def _metriques(self) -> tuple[int, str]:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = M.principal(["metriques"], racine=self.racine)
        return code, sortie.getvalue()

    def _commande(self, *arguments: str) -> tuple[int, str]:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = M.principal(list(arguments), racine=self.racine)
        return code, sortie.getvalue()

    def _section_metriques(self) -> str:
        page = self.page.read_text(encoding="utf-8")
        return page.split('<section id="metriques-v1">', 1)[1].split(
            "</section>", 1
        )[0]

    def _muter_recu_zai_002(self, mutation) -> None:
        """Mute la charge du reçu zai -002 (pointe de chaîne), réadresse le
        reçu et réaligne le registre de validation et les épingles de
        preuves du registre de couverture sur la nouvelle empreinte : le
        double simule une acquisition divergente produite de bout en bout,
        sans toucher aux autres preuves."""
        ancien_nom = (
            "dff58875d0412f275dfc1d781617214e2557ae1eeaf9177885f50b05a8591c2f"
            ".json"
        )
        realigner_chaine_recus(
            M,
            self.racine,
            _CAMPAGNE,
            M.CHEMIN_REGISTRE_VALIDATION,
            M.CHEMIN_ETAT,
            mutations={ancien_nom: mutation},
        )

    def _table(self) -> dict:
        return json.loads(self.chemin_table.read_text(encoding="utf-8"))

    def _lignes(self) -> dict[str, dict]:
        return {
            ligne["configuration_id"]: ligne
            for ligne in self._table()["configurations"]
        }


class LatencePolitiquePureTests(unittest.TestCase):
    """Politique de latence en chemin pur injecté : la branche reconnaît
    uniquement LATENCY_MEDIAN_SUCCESS_E2E et valide les sémantiques
    exactes de la source locale versionnée, sans prétendre que le verrou
    courant accepte un champ de statistique."""

    def _contrat_source(self) -> dict:
        return json.loads(
            (RACINE / M.CHEMIN_CONTRAT_LATENCE).read_text(encoding="utf-8")
        )["latency"]

    def test_distribution_complete_sans_statistique(self):
        bloc = M._latence_configuration([22925], None)
        self.assertEqual("DISTRIBUTION_COMPLETE", bloc["regle"])
        self.assertEqual([22925], bloc["distribution_ms"])
        self.assertNotIn("valeur_ms", bloc)

    def test_politique_exacte_succes_multiples_et_echec_exclu(self):
        # Contrat exact lu de la source versionnée ; plusieurs succès et
        # au moins un échec
        bloc = M._latence_configuration(
            [100, 22925, 199430],
            "LATENCY_MEDIAN_SUCCESS_E2E",
            echecs_ms=[5400],
            contrat=self._contrat_source(),
        )
        self.assertEqual("LATENCY_MEDIAN_SUCCESS_E2E", bloc["regle"])
        # Médiane calculée uniquement sur les durées E2E réussies
        self.assertEqual(22925, bloc["valeur_ms"])
        # La distribution des succès reste visible
        self.assertEqual([100, 22925, 199430], bloc["distribution_ms"])
        # L'échec est rapporté séparément et exclu de la médiane
        self.assertEqual([5400], bloc["echecs_ms"])

    def test_politique_exacte_sans_succes_indefinie(self):
        bloc = M._latence_configuration(
            [],
            "LATENCY_MEDIAN_SUCCESS_E2E",
            echecs_ms=[5400, 7200],
            contrat=self._contrat_source(),
        )
        # Sans succès, la valeur est exactement INDEFINIE
        self.assertEqual("INDEFINIE", bloc["valeur_ms"])
        self.assertEqual([], bloc["distribution_ms"])
        # Les échecs restent visibles, rapportés séparément
        self.assertEqual([5400, 7200], bloc["echecs_ms"])

    def test_politique_inconnue_refusee_de_facon_nommee(self):
        with self.assertRaises(M.ErreurRestitution) as contexte:
            M._latence_configuration(
                [100],
                "LATENCY_MEAN_SUCCESS_E2E",
                echecs_ms=[],
                contrat=self._contrat_source(),
            )
        self.assertIn(
            "politique de latence inconnue", str(contexte.exception)
        )

    def test_contrat_divergent_refuse_de_facon_nommee(self):
        contrat = self._contrat_source()
        contrat["no_success"] = "NON_DEFINI"
        with self.assertRaises(M.ErreurRestitution) as contexte:
            M._latence_configuration(
                [100],
                "LATENCY_MEDIAN_SUCCESS_E2E",
                echecs_ms=[],
                contrat=contrat,
            )
        self.assertIn(
            "contrat de latence divergent", str(contexte.exception)
        )

    def test_contrat_latence_epingle_a_la_source_versionnee(self):
        # Garde de dérive : le contrat exact et son épingle figée restent
        # ceux de la source locale versionnée courante
        octets = (RACINE / M.CHEMIN_CONTRAT_LATENCE).read_bytes()
        self.assertEqual(
            M.EMPREINTE_CONTRAT_LATENCE,
            hashlib.sha256(octets).hexdigest(),
        )
        self.assertEqual(
            M.CONTRAT_LATENCE_EXACT, json.loads(octets)["latency"]
        )

    def test_mediane_exacte_pair_impair(self):
        self.assertEqual(150, M._mediane_ms([100, 200]))
        self.assertEqual(2.5, M._mediane_ms([2, 3]))
        self.assertEqual(22925, M._mediane_ms([22925]))

    def test_aucune_occurrence_du_symbole_invente(self):
        symbole = "MED" "IANE"
        for relatif in (
            "tools/campagne_v1.py",
            "tests/test_campagne_v1_metriques.py",
        ):
            self.assertNotIn(
                symbole,
                (RACINE / relatif).read_text(encoding="utf-8"),
                relatif,
            )


class MetriquesPreuvesReellesTests(_ArbrePreuvesReelles, unittest.TestCase):
    """Arbre de preuves réel copié : le lot versionné tel quel."""

    def test_metriques_ecrit_la_table_avec_numerateurs_et_denominateurs(self):
        code, sortie = self._metriques()
        self.assertEqual(0, code, sortie)
        self.assertTrue(self.chemin_table.is_file())
        table = self._table()
        lignes = self._lignes()
        self.assertEqual(
            list(_PANEL), [l["configuration_id"] for l in table["configurations"]]
        )
        # Lot réel : six décisions CANDIDATE_NOT_ACCEPTABLE décidables,
        # un créneau non décidable, aucune sortie
        # officiellement acceptable
        for ident in _DECIDABLES:
            self.assertEqual(0, lignes[ident]["numerateur"], ident)
            self.assertEqual(1, lignes[ident]["denominateur_decidable"], ident)
            self.assertEqual("0/1", lignes[ident]["taux"], ident)
        for ident in _NON_DECIDABLES:
            self.assertEqual(0, lignes[ident]["numerateur"], ident)
            self.assertEqual(0, lignes[ident]["denominateur_decidable"], ident)
            self.assertEqual("NON_DEFINI", lignes[ident]["taux"], ident)
        agregat = table["agregat"]
        self.assertEqual(0, agregat["numerateur"])
        self.assertEqual(6, agregat["denominateur_decidable"])
        self.assertEqual("0/6", agregat["taux"])
        # La couverture publiée par V1-XS-12A est reprise à l'identique
        reprise = table["couverture_reprise"]
        self.assertEqual("6/7", reprise["fraction"])
        self.assertEqual(6, reprise["numerateur"])
        self.assertEqual(7, reprise["denominateur"])
        self.assertEqual(M.CHEMIN_ETAT.as_posix(), reprise["source"]["chemin"])

    def test_effort_humain_sept_composantes_separees_inconnues(self):
        code, sortie = self._metriques()
        self.assertEqual(0, code, sortie)
        effort = self._table()["effort_humain"]
        # Sept composantes du contrat U-025, séparées, sans conversion
        # monétaire ; aucune preuve d'effort n'existe dans le lot réel
        self.assertEqual(
            list(_COMPOSANTES_EFFORT),
            [c["composante"] for c in effort["composantes"]],
        )
        for composante in effort["composantes"]:
            self.assertEqual("INCONNU", composante["valeur"])
        # Provenance locale explicite du vocabulaire figé choisi
        provenance = effort["provenance_vocabulaire"]
        self.assertEqual(
            M.CHEMIN_VOCABULAIRE_EFFORT.as_posix(), provenance["chemin"]
        )
        sha_attendu = hashlib.sha256(
            (RACINE / M.CHEMIN_VOCABULAIRE_EFFORT).read_bytes()
        ).hexdigest()
        self.assertEqual(sha_attendu, provenance["sha256"])

    def test_latence_configuration_et_delai_decision_distingues(self):
        # Le verrou courant ne préenregistre aucune statistique de latence :
        # la distribution complète des latences de configuration observées
        # est publiée, et le délai complet avant décision officielle reste
        # INCONNU faute de preuve des temps de validation et de verdict
        code, sortie = self._metriques()
        self.assertEqual(0, code, sortie)
        lignes = self._lignes()
        # Latences lues littéralement des reçus officiels du lot réel
        for ident, distribution in _LATENCES_ATTENDUES.items():
            latence = lignes[ident]["latence_configuration"]
            self.assertEqual("DISTRIBUTION_COMPLETE", latence["regle"], ident)
            self.assertEqual(distribution, latence["distribution_ms"], ident)
        # PRD 8.4 : le délai complet avant décision officielle est distinct
        # de la latence de configuration et n'est pas établi par les
        # preuves courantes
        for ident in _PANEL:
            self.assertEqual(
                "INCONNU",
                lignes[ident]["delai_avant_decision_officielle"],
                ident,
            )

    def test_verrou_avec_champ_latence_refuse_hors_schema(self):
        # Le schéma fermé campagne-v1-verrou-abonnement/v1 n'admet aucun
        # champ de statistique de latence : un tel double est refusé
        chemin_verrou = self.racine / M.CHEMIN_VERROU
        verrou = json.loads(chemin_verrou.read_text(encoding="utf-8"))
        verrou["latence"] = {"statistique": "median"}
        chemin_verrou.write_text(
            json.dumps(verrou, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        code, sortie = self._metriques()
        self.assertEqual(1, code)
        self.assertIn("clés hors schéma fermé", sortie)

    def test_comparabilite_seules_configurations_avec_preuve_comparables(self):
        code, sortie = self._metriques()
        self.assertEqual(0, code, sortie)
        table = self._table()
        lignes = self._lignes()
        # Les sept configurations portant une preuve d'acquisition sont
        # comptées comparables, y compris l'incident non décidable Cursor
        for ident in _PANEL:
            self.assertEqual(
                "COMPARABLE", lignes[ident]["comparabilite"]["statut"], ident
            )
        agregat = table["agregat"]
        self.assertEqual(7, agregat["configurations_comparables"])
        self.assertEqual(0, agregat["configurations_retirees"])
        self.assertEqual(0, agregat["configurations_sans_observation"])

    def test_verifier_restitution_refuse_configuration_surnumeraire(self):
        # Double : la table stockée porte une huitième configuration
        # fictive, absente de la table attendue dérivée des preuves —
        # refus fail-closed nommé, et le comptage attendu des lignes
        # provient de la table attendue, jamais de la table stockée
        code, sortie = self._metriques()
        self.assertEqual(0, code, sortie)
        code, sortie = self._commande("restituer")
        self.assertEqual(0, code, sortie)
        table = self._table()
        table["configurations"].append(
            {
                "configuration_id": "configuration-fictive",
                "decision": None,
                "numerateur": 0,
                "denominateur_decidable": 0,
                "taux": "NON_DEFINI",
                "latence_configuration": {
                    "regle": "DISTRIBUTION_COMPLETE",
                    "distribution_ms": [],
                },
                "delai_avant_decision_officielle": "INCONNU",
                "comparabilite": {
                    "statut": "SANS_OBSERVATION",
                    "cause": "MISSING_OBSERVATION",
                },
            }
        )
        self.chemin_table.write_text(
            json.dumps(table, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        # La page est re-rendue depuis la table falsifiée : huit lignes
        # affichées, sept attendues d'après la table dérivée des preuves
        code, sortie = self._commande("restituer")
        self.assertEqual(0, code, sortie)
        code, sortie = self._commande("verifier-restitution")
        self.assertEqual(1, code)
        self.assertIn("registre de configurations", sortie)
        self.assertIn("7 lignes de métriques attendues", sortie)

    def _muter_cause_creneau(self, identifiant: str, cause: str) -> None:
        """Double : le créneau non couvert d'une configuration sans reçu
        porte une cause réelle divergente de MISSING_OBSERVATION."""
        realigner_chaine_recus(
            M,
            self.racine,
            _CAMPAGNE,
            M.CHEMIN_REGISTRE_VALIDATION,
            M.CHEMIN_ETAT,
            configurations_retirees={identifiant},
        )
        chemin_etat = self.racine / M.CHEMIN_ETAT
        etat = json.loads(chemin_etat.read_text(encoding="utf-8"))
        for creneau in etat["couverture"]["creneaux"]:
            if creneau["configuration_id"] == identifiant:
                creneau["couvert"] = False
                creneau["decision"] = None
                creneau["cause"] = cause
        etat["couverture"]["numerateur"] = 5
        etat["couverture"]["fraction"] = "5/7"
        etat.pop("execution_completion", None)
        chemin_etat.write_text(
            json.dumps(etat, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

    def test_comparabilite_sans_recu_identity_mismatch(self):
        # Double : créneau non couvert à la cause IDENTITY_MISMATCH, sans
        # aucun reçu d'acquisition — la configuration reste visible avec
        # sa cause réelle, hors du front de comparaison
        self._muter_cause_creneau("claude-code-fable-5", "IDENTITY_MISMATCH")
        code, sortie = self._metriques()
        self.assertEqual(0, code, sortie)
        comparabilite = self._lignes()["claude-code-fable-5"]["comparabilite"]
        self.assertEqual("SANS_OBSERVATION", comparabilite["statut"])
        self.assertEqual("IDENTITY_MISMATCH", comparabilite["cause"])
        agregat = self._table()["agregat"]
        self.assertEqual(6, agregat["configurations_comparables"])
        self.assertEqual(1, agregat["configurations_sans_observation"])

    def test_comparabilite_sans_recu_preuve_manquante(self):
        # Double : créneau non couvert à la cause PREUVE_MANQUANTE, sans
        # aucun reçu d'acquisition — la configuration reste visible avec
        # sa cause réelle, hors du front de comparaison
        self._muter_cause_creneau("codex-gpt-5-6-sol", "PREUVE_MANQUANTE")
        code, sortie = self._metriques()
        self.assertEqual(0, code, sortie)
        comparabilite = self._lignes()["codex-gpt-5-6-sol"]["comparabilite"]
        self.assertEqual("SANS_OBSERVATION", comparabilite["statut"])
        self.assertEqual("PREUVE_MANQUANTE", comparabilite["cause"])
        agregat = self._table()["agregat"]
        self.assertEqual(6, agregat["configurations_comparables"])
        self.assertEqual(1, agregat["configurations_sans_observation"])

    def test_divergence_fraicheur_retire_la_configuration_sans_la_masquer(self):
        # Double : le reçu de préflight de zai-glm-5-3 diffère de
        # l'empreinte verrouillée — événement matériel LOCKED_ARTIFACT_CHANGED
        chemin = (
            self.racine / _CAMPAGNE / "preflights-v1" / "zai-glm-5-3.json"
        )
        recu = json.loads(chemin.read_text(encoding="utf-8"))
        recu["fait"] = recu["fait"] + " (double de test)"
        chemin.write_text(
            json.dumps(recu, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        code, sortie = self._metriques()
        self.assertEqual(0, code, sortie)
        table = self._table()
        lignes = self._lignes()
        # La configuration retirée reste visible, avec son motif exact
        zai = lignes["zai-glm-5-3"]
        self.assertEqual("RETIREE", zai["comparabilite"]["statut"])
        self.assertIn("fraîcheur", zai["comparabilite"]["motif"])
        self.assertIn("LOCKED_ARTIFACT_CHANGED", zai["comparabilite"]["motif"])
        self.assertEqual(0, zai["numerateur"])
        self.assertEqual(1, zai["denominateur_decidable"])
        # Les six autres configurations prouvées restent comparables
        self.assertEqual(
            "COMPARABLE",
            lignes["antigravity-gemini-3-7-flash"]["comparabilite"]["statut"],
        )
        for ident in _PANEL:
            if ident == "zai-glm-5-3":
                continue
            self.assertEqual(
                "COMPARABLE",
                lignes[ident]["comparabilite"]["statut"],
                ident,
            )
        # L'agrégat ne compte que les configurations comparables
        agregat = table["agregat"]
        self.assertEqual(6, agregat["configurations_comparables"])
        self.assertEqual(1, agregat["configurations_retirees"])
        self.assertEqual(0, agregat["configurations_sans_observation"])
        self.assertEqual(0, agregat["numerateur"])
        self.assertEqual(5, agregat["denominateur_decidable"])
        self.assertEqual("0/5", agregat["taux"])

    def test_divergence_carte_retiree_la_configuration(self):
        # Double : le reçu zai -002 (pointe de chaîne) porte une empreinte
        # de carte divergente de la carte versionnée courante
        self._muter_recu_zai_002(
            lambda charge: charge["carte"].update(sha256="0" * 64)
        )
        code, sortie = self._metriques()
        self.assertEqual(0, code, sortie)
        lignes = self._lignes()
        zai = lignes["zai-glm-5-3"]
        self.assertEqual("RETIREE", zai["comparabilite"]["statut"])
        self.assertIn("carte", zai["comparabilite"]["motif"])
        agregat = self._table()["agregat"]
        self.assertEqual(6, agregat["configurations_comparables"])
        self.assertEqual(1, agregat["configurations_retirees"])
        self.assertEqual(0, agregat["configurations_sans_observation"])
        self.assertEqual("0/5", agregat["taux"])

    def test_metriques_idempotente_et_deterministe(self):
        code, sortie = self._metriques()
        self.assertEqual(0, code, sortie)
        premiere = self.chemin_table.read_bytes()
        code, sortie = self._metriques()
        self.assertEqual(0, code, sortie)
        self.assertEqual(premiere, self.chemin_table.read_bytes())

    def test_metriques_refuse_sans_verrou(self):
        # Sans verrou, la fenêtre de fraîcheur déclarée au verrou n'est pas
        # lisible : refus fail-closed nommé, aucune table écrite
        self.chemin_table.unlink(missing_ok=True)
        shutil.rmtree(self.racine / M.CHEMIN_VERROU.parent)
        code, sortie = self._metriques()
        self.assertEqual(1, code)
        self.assertIn("verrou de campagne absent", sortie)
        self.assertFalse(self.chemin_table.exists())

    def test_metriques_refuse_sans_registre_de_couverture(self):
        # Sans registre publié par etat, metriques ne recalcule rien :
        # refus fail-closed nommé, aucune table écrite
        self.chemin_table.unlink(missing_ok=True)
        chemin_etat = self.racine / M.CHEMIN_ETAT
        etat = json.loads(chemin_etat.read_text(encoding="utf-8"))
        del etat["couverture"]
        chemin_etat.write_text(
            json.dumps(etat, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        code, sortie = self._metriques()
        self.assertEqual(1, code)
        self.assertIn("registre de couverture absent", sortie)
        self.assertFalse(self.chemin_table.exists())

    def test_provenance_vocabulaire_effort_epinglee_a_la_source(self):
        # Garde de dérive : l'épingle figée du vocabulaire d'effort reste
        # celle de la source locale versionnée courante
        sha_source = hashlib.sha256(
            (RACINE / M.CHEMIN_VOCABULAIRE_EFFORT).read_bytes()
        ).hexdigest()
        self.assertEqual(sha_source, M.EMPREINTE_VOCABULAIRE_EFFORT)

    def test_restitution_affiche_la_table_et_le_verificateur_valide(self):
        code, sortie = self._metriques()
        self.assertEqual(0, code, sortie)
        code, sortie = self._commande("restituer")
        self.assertEqual(0, code, sortie)
        page = self.page.read_text(encoding="utf-8")
        self.assertIn('<section id="metriques-v1">', page)
        section = self._section_metriques()
        # Numérateur, dénominateur et taux par configuration et agrégat
        self.assertIn("0/6", section)
        self.assertIn("0/1", section)
        self.assertIn("NON_DEFINI", section)
        # Couverture reprise à l'identique, avec sa source et son empreinte
        self.assertIn("6/7", section)
        self.assertIn(M.CHEMIN_ETAT.as_posix(), section)
        sha_etat = hashlib.sha256(
            (self.racine / M.CHEMIN_ETAT).read_bytes()
        ).hexdigest()
        self.assertIn(sha_etat, section)
        # Une ligne par configuration, statut de comparabilité visible :
        # sept comparables, aucune configuration sans observation
        self.assertEqual(7, section.count(' data-metriques-configuration="'))
        self.assertEqual(7, section.count("<code>COMPARABLE</code>"))
        self.assertEqual(0, section.count("<code>SANS_OBSERVATION</code>"))
        self.assertEqual(0, section.count("<code>MISSING_OBSERVATION</code>"))
        # Sept composantes d'effort humain, séparées, sans conversion, avec
        # la provenance locale du vocabulaire figé
        for composante in _COMPOSANTES_EFFORT:
            self.assertIn(composante, section)
        self.assertIn(M.CHEMIN_VOCABULAIRE_EFFORT.as_posix(), section)
        # Latence de configuration distinguée du délai complet avant
        # décision officielle, ce dernier INCONNU faute de preuve
        self.assertIn("latence de la configuration", section)
        self.assertIn("DISTRIBUTION_COMPLETE", section)
        self.assertIn("22925", section)
        self.assertIn("199430", section)
        self.assertIn("Délai complet avant décision officielle", section)
        self.assertIn("INCONNU", section)
        # Fenêtre de fraîcheur déclarée au verrou, reprise
        self.assertIn("EXACT_LOCK_EVENT_BASED_NO_TTL", section)
        code, sortie = self._commande("verifier-restitution")
        self.assertEqual(0, code, sortie)

    def test_verifier_restitution_echoue_sur_couverture_reprise_divergente(self):
        code, sortie = self._metriques()
        self.assertEqual(0, code, sortie)
        code, sortie = self._commande("restituer")
        self.assertEqual(0, code, sortie)
        # Double : la table stockée déclare une couverture reprise
        # divergente de la source etat-v1.json
        table = self._table()
        table["couverture_reprise"]["fraction"] = "3/7"
        table["couverture_reprise"]["numerateur"] = 3
        self.chemin_table.write_text(
            json.dumps(table, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        code, sortie = self._commande("verifier-restitution")
        self.assertEqual(1, code)
        self.assertIn("couverture reprise divergente", sortie)

    def test_verifier_restitution_echoue_sur_motif_retrait_inexact(self):
        # Double : la requête du reçu zai -002 diverge du descripteur
        # verrouillé de l'acquisition — divergence de harnais
        self._muter_recu_zai_002(
            lambda charge: charge["requete"].update(
                argv_resolu=[
                    "uv",
                    "run",
                    "tools/harness_autre.py",
                    "--api",
                    "zai",
                    "--prompt-file",
                    "__PROMPT_FILE__",
                ]
            )
        )
        code, sortie = self._metriques()
        self.assertEqual(0, code, sortie)
        zai = self._lignes()["zai-glm-5-3"]
        self.assertEqual("RETIREE", zai["comparabilite"]["statut"])
        self.assertIn("harnais", zai["comparabilite"]["motif"])
        code, sortie = self._commande("restituer")
        self.assertEqual(0, code, sortie)
        code, sortie = self._commande("verifier-restitution")
        self.assertEqual(0, code, sortie)
        # Le motif exact est affiché dans la restitution, la configuration
        # retirée reste visible
        section = self._section_metriques()
        self.assertIn("RETIREE", section)
        self.assertIn("harnais", section)
        self.assertIn("zai-glm-5-3", section)
        # Double : le motif de retrait stocké est falsifié
        table = self._table()
        for ligne in table["configurations"]:
            if ligne["configuration_id"] == "zai-glm-5-3":
                ligne["comparabilite"]["motif"] = "motif falsifié"
        self.chemin_table.write_text(
            json.dumps(table, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        code, sortie = self._commande("verifier-restitution")
        self.assertEqual(1, code)
        self.assertIn("motif de retrait absent ou inexact", sortie)


if __name__ == "__main__":
    unittest.main()
