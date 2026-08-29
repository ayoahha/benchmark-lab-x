# /// script
# requires-python = ">=3.12"
# ///
"""Documentation du parcours V1-XS-15, vérifiée par exécution.

Les tests passent par la couture publique `principal(..., racine=<temp>)`
sur des racines temporaires jetables. Le registre officiel du dépôt n'est
jamais modifié. Aucune commande d'acquisition, de préflight ou distante
n'est exécutée : `acquerir` sous toute forme, `preflight`, `qualifier`,
`verrouiller`, `valider`, `dossiers`, `geler` et les commandes
`preparer-*` sont hors de ce module.

Les valeurs attendues sont des littéraux indépendants : les codes de
sortie viennent du contrat de la surface figée 5.4 (`0` succès, `1` refus
fail-closed nommé, `2` HOLD), les empreintes de répertoire viennent du
commentaire de scellement de l'Issue #116, et le journal versionné sert
d'attendu figé que le rejeu doit reproduire.
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
sys.path.insert(0, str(RACINE))

import campagne_v1 as M  # noqa: E402

_CAMPAGNE = Path("tasks/dev/pre-cadrage-entretien-client/campagne-v1")
_PAQUET = Path("tasks/dev/pre-cadrage-entretien-client")
_FICHIERS_PAQUET = (
    "manifeste-paquet.json",
    "brief-proprietaire.md",
    "registre-verite.md",
    "stimulus.md",
    "temoins-qualification.md",
)
_GUIDE = RACINE / M.CHEMIN_GUIDE_UTILISATION
_JOURNAL = _GUIDE.parent / "journal-rejeu-local.json"

# Empreintes figées par le commentaire de scellement de l'Issue #116
_RECUS_SCELLES = (
    "397b868cafe2a56facc95ac8df8b772cc802fc1b89b9d94b3b2d8910da1f90ac"
)
_PREFLIGHTS_SCELLES = (
    "1aeaf3102effb3bec57de722868f4067353e680db96c78687e8c4a2c0b4a6e8b"
)
_RECUS = f"{_CAMPAGNE.as_posix()}/recus-v1"
_PREFLIGHTS = f"{_CAMPAGNE.as_posix()}/preflights-v1"

# Les six étapes figées par les décisions de l'Issue #116, dans l'ordre
_ETAPES = (
    "## Étape 1. Enregistrer une configuration",
    "## Étape 2. Comprendre les autorisations",
    "## Étape 3. Lancer le benchmark",
    "## Étape 4. Voir les incidents et les données manquantes",
    "## Étape 5. Régénérer la restitution",
    "## Étape 6. Mettre à jour une comparaison située",
)

# Invocations exactes de la surface de commande figée 5.4
_INVOCATIONS = (
    "uv run tools/campagne_v1.py restituer",
    "uv run tools/campagne_v1.py verifier-restitution",
    "uv run tools/campagne_v1.py enregistrer --fichier "
    "<chemin-de-la-configuration>",
    "uv run tools/campagne_v1.py panel",
    "uv run tools/campagne_v1.py autorisations",
    "uv run tools/campagne_v1.py autorisations --configuration <id>",
    "uv run tools/campagne_v1.py acquerir --local --configuration <id>",
    "uv run tools/campagne_v1.py qualifier",
    "uv run tools/campagne_v1.py preflight --configuration <id>",
    "uv run tools/campagne_v1.py verrouiller",
    "uv run tools/campagne_v1.py acquerir --configuration <id>",
    "uv run tools/campagne_v1.py valider",
    "uv run tools/campagne_v1.py dossiers",
    "uv run tools/campagne_v1.py geler",
    "uv run tools/campagne_v1.py etat",
    "uv run tools/campagne_v1.py metriques",
    "uv run tools/campagne_v1.py cout",
)

# Formes de surface figées en 5.4, crochets compris : le guide les cite
# littéralement, y compris quand la ligne d'usage implémentée en diverge
_SURFACES_FIGEES = (
    "enregistrer [--registre <chemin>] --fichier <chemin>",
    "panel [--registre <chemin>]",
    "autorisations [--configuration <id>]",
    "preflight [--configuration <id>]",
)

# Contrat de codes de la surface figée 5.4 : la même triade pour toutes les
# sous-commandes, sans code d'usage. `preflight` la décline verdict par verdict
_CONTRAT_GENERIQUE = "`0` succès, `1` refus fail-closed nommé, `2` `HOLD`"
_CONTRAT_PREFLIGHT = "`0` `READY`, `1` `UNAVAILABLE`, `2` `HOLD`"

# Préfixe de ligne de tableau -> cellule de contrat contractuel exigée
_CONTRAT_PAR_SOUS_COMMANDE = (
    ("enregistrer", _CONTRAT_GENERIQUE),
    ("panel", _CONTRAT_GENERIQUE),
    ("autorisations", _CONTRAT_GENERIQUE),
    ("qualifier", _CONTRAT_GENERIQUE),
    ("verrouiller", _CONTRAT_GENERIQUE),
    ("acquerir --local", _CONTRAT_GENERIQUE),
    ("acquerir --configuration", _CONTRAT_GENERIQUE),
    ("valider", _CONTRAT_GENERIQUE),
    ("dossiers", _CONTRAT_GENERIQUE),
    ("geler", _CONTRAT_GENERIQUE),
    ("etat", _CONTRAT_GENERIQUE),
    ("metriques", _CONTRAT_GENERIQUE),
    ("cout", _CONTRAT_GENERIQUE),
    ("restituer", _CONTRAT_GENERIQUE),
    ("verifier-restitution", _CONTRAT_GENERIQUE),
    ("preflight", _CONTRAT_PREFLIGHT),
)

# Sous-commandes rejouées par ce ticket : locales, sans dépense, sans
# consommation de quota et sans écriture de reçu
_REJOUABLES = (
    "restituer",
    "verifier-restitution",
    "enregistrer",
    "panel",
    "autorisations",
    "etat",
    "metriques",
    "cout",
)

# Commandes vérifiées sur pièces, jamais relancées par ce ticket
_SUR_PIECES = (
    ("qualifier", "issues/100#issuecomment-"),
    ("preflight", "issues/101#issuecomment-"),
    ("verrouiller", "issues/107#issuecomment-"),
    ("acquerir --local --configuration", "issues/99#issuecomment-"),
    ("acquerir --configuration <id>", "issues/108#issuecomment-"),
    ("valider", "issues/109#issuecomment-"),
    ("dossiers", "issues/110#issuecomment-"),
    ("geler", "issues/111#issuecomment-"),
)

_IDENTIFIANT_C = "demonstration-v1-xs-15"
# Une occurrence par entrée de panel rendue : sert de compteur de cardinalité
_CARDINALITE_PANEL = "entrée déclarée et non mesurée"
_RELATIF_C = (
    _CAMPAGNE / "configurations" / f"{_IDENTIFIANT_C}.toml"
).as_posix()

_PLAN_RENSEIGNE = (
    '[plan]\nnom = "Claude Max 5x"\nprix_montant = 100\n'
    'prix_devise = "USD"\nperiode = "MONTH"\n'
    'source_url = "https://support.claude.com/en/articles/'
    '11049762-choose-a-claude-plan"\n'
    'date_publication = "2026-05-19"\n'
    'date_consultation = "2026-08-26"\n'
)
_PLAN_INCONNU = (
    '[plan]\nnom = "INCONNU"\nprix_montant = "INCONNU"\n'
    'prix_devise = "INCONNU"\nperiode = "INCONNU"\n'
    'source_url = "INCONNU"\ndate_publication = "INCONNU"\n'
    'date_consultation = "INCONNU"\n'
)


def _configuration_c(plan_renseigne: bool) -> str:
    plan = _PLAN_RENSEIGNE if plan_renseigne else _PLAN_INCONNU
    return f"""\
# Configuration de démonstration V1-XS-15, écrite dans une racine temporaire
# jetable. Elle n'entre jamais dans le registre officiel du dépôt.
schema_version = "campagne-v1-configuration-abonnement/v1"
configuration_id = "{_IDENTIFIANT_C}"

[produit]
nom = "Claude Code"
editeur = "INCONNU"

{plan}
[[quota]]
unite = "INCONNU"
valeur = "INCONNU"
portee = "INCONNU"
reset_fenetre = "INCONNU"
reset_ancrage = "INCONNU"
reset_au_depassement = "INCONNU"

[interface]
type = "cli"
version = "INCONNU"

[modele]
demande = "INCONNU"

[harnais]
argv = ["INCONNU", "__PROMPT_FILE__"]
espace_de_travail = "__ISOLATED_WORKSPACE__"
delai_secondes = 0

[intervention_humaine]
etapes = ["INCONNU"]
"""


_ENTREE_PLAN = f"""
[[plan]]
configuration_id = "{_IDENTIFIANT_C}"
nom = "Claude Max 5x"
prix_montant = 100
prix_devise = "USD"
periode = "MONTH"
source_url = "https://support.claude.com/en/articles/11049762-choose-a-claude-plan"
date_publication = "2026-05-19"
date_consultation = "2026-08-26"
classe_msw = "{M.CLASSE_PLAN_FAIT}"
attestation_reference = "{M.ATTESTATION_PANEL}"
"""


class _RacineJetable(unittest.TestCase):
    """Racine temporaire jetable par test : le worktree n'est jamais écrit."""

    def _preparer(self) -> Path:
        temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(temporaire.cleanup)
        racine = Path(temporaire.name)
        shutil.copytree(RACINE / _CAMPAGNE, racine / _CAMPAGNE)
        for relatif, _ in M.SOURCES_AUTORISEES:
            (racine / relatif).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, racine / relatif)
        for nom in _FICHIERS_PAQUET:
            (racine / _PAQUET / nom).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / _PAQUET / nom, racine / _PAQUET / nom)
        return racine

    def _executer(self, racine: Path, *arguments: str) -> dict:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = M.principal(list(arguments), racine=racine)
        rendu = [
            f"<racine-temporaire>/{_RELATIF_C}" if str(racine) in a else a
            for a in arguments
        ]
        lignes = sortie.getvalue().splitlines()
        return {
            "invocation": "uv run tools/campagne_v1.py " + " ".join(rendu),
            "code_sortie": code,
            "premiere_ligne_stdout": lignes[0] if lignes else "",
        }

    def _manifeste(self, racine: Path, relatif: str) -> str:
        lignes = [
            f"{hashlib.sha256(c.read_bytes()).hexdigest()}  {relatif}/{c.name}\n"
            for c in sorted((racine / relatif).iterdir(), key=lambda c: c.name)
        ]
        return hashlib.sha256("".join(lignes).encode("utf-8")).hexdigest()

    def _empreinte_page(self, racine: Path) -> str:
        return hashlib.sha256((racine / M.CHEMIN_PAGE).read_bytes()).hexdigest()

    def _journal(self) -> dict:
        return json.loads(_JOURNAL.read_text(encoding="utf-8"))

    def _contexte(self, nom: str) -> dict:
        for contexte in self._journal()["contextes"]:
            if contexte["contexte"] == nom:
                return contexte
        self.fail(f"contexte absent du journal : {nom}")


class RejeuLectureSeuleTests(_RacineJetable):
    """Les huit sous-commandes rejouables tournent sans écrire de reçu."""

    def test_sept_commandes_de_lecture_rendent_le_code_du_journal(self):
        racine = self._preparer()
        attendu = self._contexte("lecture-seule")
        obtenu = [
            self._executer(racine, "panel"),
            self._executer(racine, "autorisations"),
            self._executer(racine, "etat"),
            self._executer(racine, "metriques"),
            self._executer(racine, "cout"),
            self._executer(racine, "restituer"),
            self._executer(racine, "verifier-restitution"),
        ]
        self.assertEqual(obtenu, attendu["commandes"])

    def test_empreinte_html_du_journal_reproduite(self):
        racine = self._preparer()
        self._executer(racine, "restituer")
        self.assertEqual(
            self._empreinte_page(racine),
            self._contexte("lecture-seule")["empreinte_html"],
        )

    def test_repertoire_des_recus_intact_et_scelle(self):
        racine = self._preparer()
        avant = self._manifeste(racine, _RECUS)
        for commande in ("panel", "etat", "metriques", "cout", "restituer"):
            self._executer(racine, commande)
        apres = self._manifeste(racine, _RECUS)
        self.assertEqual(avant, _RECUS_SCELLES)
        self.assertEqual(apres, _RECUS_SCELLES)

    def test_repertoire_des_preflights_intact_et_scelle(self):
        racine = self._preparer()
        avant = self._manifeste(racine, _PREFLIGHTS)
        self._executer(racine, "restituer")
        self.assertEqual(avant, _PREFLIGHTS_SCELLES)
        self.assertEqual(self._manifeste(racine, _PREFLIGHTS), _PREFLIGHTS_SCELLES)


class RefusProvenanceDePrixTests(_RacineJetable):
    """Enregistrer une configuration sans provenance de prix rend `0`, puis
    bloque la régénération par un refus fail-closed nommé."""

    def test_codes_du_journal_reproduits(self):
        racine = self._preparer()
        fichier = racine / _RELATIF_C
        fichier.write_text(_configuration_c(False), encoding="utf-8")
        obtenu = [
            self._executer(racine, "enregistrer", "--fichier", str(fichier)),
            self._executer(racine, "restituer"),
        ]
        self.assertEqual(
            obtenu, self._contexte("refus-provenance-de-prix")["commandes"]
        )

    def test_refus_nomme_le_champ_fautif_et_la_configuration(self):
        racine = self._preparer()
        fichier = racine / _RELATIF_C
        fichier.write_text(_configuration_c(False), encoding="utf-8")
        self._executer(racine, "enregistrer", "--fichier", str(fichier))
        refus = self._executer(racine, "restituer")
        self.assertEqual(refus["code_sortie"], 1)
        self.assertIn("plan", refus["premiere_ligne_stdout"])
        self.assertIn(_IDENTIFIANT_C, refus["premiere_ligne_stdout"])

    def test_aucun_recu_ecrit_par_le_refus(self):
        racine = self._preparer()
        fichier = racine / _RELATIF_C
        fichier.write_text(_configuration_c(False), encoding="utf-8")
        self._executer(racine, "enregistrer", "--fichier", str(fichier))
        self._executer(racine, "restituer")
        self.assertEqual(self._manifeste(racine, _RECUS), _RECUS_SCELLES)


class AjoutPuisRegenerationTests(_RacineJetable):
    """Enregistrement puis régénération : la restitution change, le
    répertoire des reçus non."""

    def _preparer_ajout(self) -> tuple[Path, str]:
        racine = self._preparer()
        self._executer(racine, "restituer")
        avant = self._empreinte_page(racine)
        fichier = racine / _RELATIF_C
        fichier.write_text(_configuration_c(True), encoding="utf-8")
        sources = racine / _CAMPAGNE / "sources-plans-v1.toml"
        sources.write_text(
            sources.read_text(encoding="utf-8") + _ENTREE_PLAN,
            encoding="utf-8",
        )
        return racine, avant

    def test_codes_du_journal_reproduits(self):
        racine, _ = self._preparer_ajout()
        fichier = racine / _RELATIF_C
        obtenu = [
            self._executer(racine, "enregistrer", "--fichier", str(fichier)),
            self._executer(racine, "restituer"),
            self._executer(racine, "verifier-restitution"),
            self._executer(racine, "panel"),
            self._executer(
                racine, "autorisations", "--configuration", _IDENTIFIANT_C
            ),
        ]
        self.assertEqual(
            obtenu, self._contexte("ajout-puis-regeneration")["commandes"]
        )

    def test_empreintes_html_avant_et_apres_different(self):
        racine, avant = self._preparer_ajout()
        fichier = racine / _RELATIF_C
        self._executer(racine, "enregistrer", "--fichier", str(fichier))
        self._executer(racine, "restituer")
        apres = self._empreinte_page(racine)
        self.assertNotEqual(avant, apres)
        contexte = self._contexte("ajout-puis-regeneration")
        self.assertEqual(avant, contexte["empreinte_html_avant"])
        self.assertEqual(apres, contexte["empreinte_html_apres"])

    def test_effet_semantique_operateur_visible_dans_la_page(self):
        """Le tracer bullet prouve un effet lisible par l'opérateur, pas
        seulement un SHA-256 différent."""
        racine, _ = self._preparer_ajout()
        page_avant = (racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        self._executer(
            racine, "enregistrer", "--fichier", str(racine / _RELATIF_C)
        )
        self._executer(racine, "restituer")
        page_apres = (racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        preuve = self._contexte("ajout-puis-regeneration")[
            "preuve_semantique_html"
        ]
        marqueur = preuve["marqueur_operateur"]
        self.assertEqual(
            page_avant.count(marqueur), preuve["occurrences_marqueur_avant"]
        )
        self.assertEqual(
            page_apres.count(marqueur), preuve["occurrences_marqueur_apres"]
        )
        self.assertIn(_IDENTIFIANT_C, page_apres)
        self.assertNotIn(_IDENTIFIANT_C, page_avant)
        self.assertEqual(
            page_avant.count(_CARDINALITE_PANEL),
            preuve["cardinalite_entrees_panel_avant"],
        )
        self.assertEqual(
            page_apres.count(_CARDINALITE_PANEL),
            preuve["cardinalite_entrees_panel_apres"],
        )

    def test_verification_refuse_la_couverture_divergente(self):
        """`verifier-restitution` rend `1` ici : c'est le refus fail-closed
        attendu de cette branche, jamais un succès."""
        racine, _ = self._preparer_ajout()
        self._executer(
            racine, "enregistrer", "--fichier", str(racine / _RELATIF_C)
        )
        self.assertEqual(self._executer(racine, "restituer")["code_sortie"], 0)
        refus = self._executer(racine, "verifier-restitution")
        self.assertEqual(refus["code_sortie"], 1)
        self.assertIn("6/8 attendu", refus["premiere_ligne_stdout"])
        self.assertIn("6/7 stocké", refus["premiere_ligne_stdout"])
        self.assertIn("aucune réparation", refus["premiere_ligne_stdout"])

    def test_manifestes_de_recus_identiques_avant_et_apres(self):
        racine, _ = self._preparer_ajout()
        fichier = racine / _RELATIF_C
        avant = self._manifeste(racine, _RECUS)
        self._executer(racine, "enregistrer", "--fichier", str(fichier))
        self._executer(racine, "restituer")
        self._executer(racine, "verifier-restitution")
        self.assertEqual(avant, _RECUS_SCELLES)
        self.assertEqual(self._manifeste(racine, _RECUS), _RECUS_SCELLES)
        self.assertEqual(self._manifeste(racine, _PREFLIGHTS), _PREFLIGHTS_SCELLES)

    def test_registre_officiel_du_worktree_inchange(self):
        avant = sorted(
            (chemin.name, hashlib.sha256(chemin.read_bytes()).hexdigest())
            for chemin in (RACINE / M.REGISTRE_OFFICIEL).iterdir()
        )
        racine, _ = self._preparer_ajout()
        self._executer(
            racine, "enregistrer", "--fichier", str(racine / _RELATIF_C)
        )
        apres = sorted(
            (chemin.name, hashlib.sha256(chemin.read_bytes()).hexdigest())
            for chemin in (RACINE / M.REGISTRE_OFFICIEL).iterdir()
        )
        self.assertEqual(avant, apres)
        self.assertNotIn(f"{_IDENTIFIANT_C}.toml", [nom for nom, _ in apres])


class JournalRejeuLocalTests(unittest.TestCase):
    """Le journal versionné est lisible, déterministe et fermé aux
    acquisitions."""

    def setUp(self):
        self.journal = json.loads(_JOURNAL.read_text(encoding="utf-8"))
        self.brut = _JOURNAL.read_text(encoding="utf-8")

    def test_journal_deterministe_trie_et_termine_par_un_saut_de_ligne(self):
        rendu = (
            json.dumps(
                self.journal, ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n"
        )
        self.assertEqual(self.brut, rendu)

    def test_identite_de_tranche_conforme_au_scellement(self):
        self.assertEqual(self.journal["ticket"], "V1-XS-15")
        self.assertEqual(
            self.journal["base_git"],
            "368455ea08abb861709baf16ead0f438ec1acb29",
        )
        self.assertEqual(
            self.journal["contrat_sha256"],
            "16ff9fba1ca16b87850405aad97311f5b746dfd2ab9cc8fd51216ef1960694e4",
        )

    def test_couture_publique_et_isolement_declares(self):
        self.assertIn("principal(", self.journal["couture_publique"])
        self.assertIn("racine=", self.journal["couture_publique"])
        self.assertIn("temporaire", self.journal["isolement"])
        self.assertIn("registre officiel", self.journal["isolement"])

    def test_trois_contextes_isoles_nommes(self):
        noms = [contexte["contexte"] for contexte in self.journal["contextes"]]
        self.assertEqual(
            noms,
            [
                "lecture-seule",
                "refus-provenance-de-prix",
                "ajout-puis-regeneration",
            ],
        )

    def test_chaque_contexte_porte_ses_manifestes_avant_et_apres(self):
        for contexte in self.journal["contextes"]:
            with self.subTest(contexte=contexte["contexte"]):
                self.assertEqual(
                    contexte["manifeste_recus_avant"], _RECUS_SCELLES
                )
                self.assertEqual(
                    contexte["manifeste_recus_apres"], _RECUS_SCELLES
                )
                self.assertEqual(
                    contexte["manifeste_preflights_avant"],
                    _PREFLIGHTS_SCELLES,
                )
                self.assertEqual(
                    contexte["manifeste_preflights_apres"],
                    _PREFLIGHTS_SCELLES,
                )

    def test_empreintes_html_avant_et_apres_de_l_ajout_different(self):
        ajout = next(
            c
            for c in self.journal["contextes"]
            if c["contexte"] == "ajout-puis-regeneration"
        )
        self.assertNotEqual(
            ajout["empreinte_html_avant"], ajout["empreinte_html_apres"]
        )
        for cle in ("empreinte_html_avant", "empreinte_html_apres"):
            self.assertRegex(ajout[cle], r"^[0-9a-f]{64}$")

    def test_preuve_semantique_consignee_pour_le_tracer_bullet(self):
        ajout = next(
            c
            for c in self.journal["contextes"]
            if c["contexte"] == "ajout-puis-regeneration"
        )
        preuve = ajout["preuve_semantique_html"]
        self.assertIn(_IDENTIFIANT_C, preuve["marqueur_operateur"])
        self.assertEqual(preuve["occurrences_marqueur_avant"], 0)
        self.assertEqual(preuve["occurrences_marqueur_apres"], 1)
        self.assertEqual(preuve["cardinalite_entrees_panel_avant"], 7)
        self.assertEqual(preuve["cardinalite_entrees_panel_apres"], 8)
        self.assertIn(_CARDINALITE_PANEL, preuve["selecteur_cardinalite"])

    def test_refus_de_verification_consigne_comme_refus(self):
        ajout = next(
            c
            for c in self.journal["contextes"]
            if c["contexte"] == "ajout-puis-regeneration"
        )
        verification = next(
            commande
            for commande in ajout["commandes"]
            if commande["invocation"].endswith("verifier-restitution")
        )
        self.assertEqual(verification["code_sortie"], 1)
        self.assertIn("6/8 attendu", verification["premiere_ligne_stdout"])
        lecture = ajout["preuve_semantique_html"][
            "lecture_du_refus_verifier_restitution"
        ]
        self.assertIn("6/8 attendu", lecture)
        self.assertIn("6/7 stocké", lecture)
        self.assertIn("fail-closed", lecture)
        self.assertIn("Ce n'est pas un succès.", lecture)

    def test_codes_de_sortie_dans_le_vocabulaire_de_la_surface_figee(self):
        for contexte in self.journal["contextes"]:
            for commande in contexte["commandes"]:
                with self.subTest(invocation=commande["invocation"]):
                    self.assertIn(commande["code_sortie"], (0, 1, 2))

    def test_acquisition_absente_du_journal_de_rejeu_local(self):
        for contexte in self.journal["contextes"]:
            for commande in contexte["commandes"]:
                self.assertNotIn("acquerir", commande["invocation"])
        for interdite in (
            "acquerir",
            "preflight",
            "qualifier",
            "verrouiller",
            "valider",
            "dossiers",
            "geler",
            "preparer-",
        ):
            with self.subTest(commande=interdite):
                self.assertNotIn(
                    f"campagne_v1.py {interdite}",
                    json.dumps(self.journal["contextes"], ensure_ascii=False),
                )

    def test_partition_rejouable_et_sur_pieces_couvre_la_surface(self):
        self.assertEqual(
            sorted(self.journal["sous_commandes_rejouables"]),
            sorted(_REJOUABLES),
        )
        jamais = self.journal["sous_commandes_jamais_rejouees"]
        self.assertIn("acquerir --local --configuration", jamais)
        self.assertIn("acquerir --configuration", jamais)
        self.assertEqual(
            set(self.journal["sous_commandes_rejouables"]) & set(jamais), set()
        )

    def test_aucun_chemin_absolu_de_racine_temporaire_publie(self):
        self.assertNotIn("/var/folders/", self.brut)
        self.assertNotIn("/tmp/", self.brut)
        self.assertIn("<racine-temporaire>", self.brut)


class GuideUtilisationTests(unittest.TestCase):
    """Le guide couvre les six étapes, la surface figée et ses renvois."""

    def setUp(self):
        self.texte = _GUIDE.read_text(encoding="utf-8")

    def test_frontmatter_porte_le_verdict_du_style_gate(self):
        self.assertTrue(self.texte.startswith("---\n"))
        entete = self.texte.split("---\n", 2)[1]
        self.assertIn("style_gate: pass", entete)

    def test_six_etapes_presentes_dans_l_ordre(self):
        positions = []
        for titre in _ETAPES:
            with self.subTest(etape=titre):
                self.assertIn(titre, self.texte)
            positions.append(self.texte.index(titre))
        self.assertEqual(positions, sorted(positions))

    def test_chaque_etape_nomme_autorisation_depense_et_quota(self):
        bornes = [self.texte.index(titre) for titre in _ETAPES] + [
            len(self.texte)
        ]
        for rang, titre in enumerate(_ETAPES):
            section = self.texte[bornes[rang] : bornes[rang + 1]]
            with self.subTest(etape=titre):
                self.assertIn("Autorisation :", section)
                self.assertIn("Dépense :", section)
                self.assertIn("Quota :", section)

    def test_chaque_sous_commande_citee_avec_son_invocation_exacte(self):
        for invocation in _INVOCATIONS:
            with self.subTest(invocation=invocation):
                self.assertIn(invocation, self.texte)

    def _lignes_de_table(self, sous_commande: str) -> list[str]:
        return [
            ligne
            for ligne in self.texte.splitlines()
            if ligne.startswith(f"| `{sous_commande}")
        ]

    def test_chaque_sous_commande_porte_la_ligne_contractuelle_exacte(self):
        """La cellule de contrat est exigée mot pour mot, pas seulement `0`."""
        for sous_commande, contrat in _CONTRAT_PAR_SOUS_COMMANDE:
            with self.subTest(sous_commande=sous_commande):
                lignes = self._lignes_de_table(sous_commande)
                self.assertTrue(lignes, sous_commande)
                for ligne in lignes:
                    self.assertIn(f"| {contrat} |", ligne)

    def test_aucun_contrat_de_code_d_usage_publie(self):
        """`2 usage` n'appartient pas au contrat 5.4 : il ne doit apparaître
        dans aucune cellule contractuelle du guide."""
        for interdit in ("`2` usage", "2 usage", "code d'usage :"):
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, self.texte)
        for ligne in self._lignes_de_table(""):
            with self.subTest(ligne=ligne[:60]):
                contrat = ligne.split("|")[2].strip()
                self.assertIn(
                    contrat, (_CONTRAT_GENERIQUE, _CONTRAT_PREFLIGHT), ligne
                )

    def test_contrat_generique_declare_identique_pour_toutes(self):
        for sous_commande in ("enregistrer", "panel", "autorisations"):
            with self.subTest(sous_commande=sous_commande):
                self.assertIn(f"`{sous_commande}`", self.texte)
        self.assertIn("Ce contrat ne connaît pas de code d'usage.", self.texte)

    def test_formes_de_surface_figees_citees_litteralement(self):
        for surface in _SURFACES_FIGEES:
            with self.subTest(surface=surface):
                self.assertIn(surface, self.texte)

    def test_commandes_rejouees_renvoient_au_journal_de_rejeu_local(self):
        self.assertIn("journal-rejeu-local.json", self.texte)
        for sous_commande in _REJOUABLES:
            with self.subTest(sous_commande=sous_commande):
                lignes = [
                    ligne
                    for ligne in self.texte.splitlines()
                    if ligne.startswith(f"| `{sous_commande}")
                ]
                self.assertTrue(lignes, sous_commande)
                self.assertTrue(
                    any("rejeu local V1-XS-15" in ligne for ligne in lignes),
                    sous_commande,
                )

    def test_commandes_sur_pieces_renvoient_a_leur_journal_proprietaire(self):
        for sous_commande, renvoi in _SUR_PIECES:
            with self.subTest(sous_commande=sous_commande):
                lignes = [
                    ligne
                    for ligne in self.texte.splitlines()
                    if ligne.startswith(f"| `{sous_commande}")
                ]
                self.assertTrue(lignes, sous_commande)
                self.assertTrue(
                    any(renvoi in ligne for ligne in lignes), sous_commande
                )

    def test_acquisition_locale_citee_comme_acquisition_non_rejouee(self):
        self.assertIn(
            "d351492a49c0ce64cfb1f0d74a3719914e4e64453d4f2d75a86a13d515ff694e",
            self.texte,
        )
        self.assertIn("local-system-wc", self.texte)
        self.assertIn("issues/99#issuecomment-", self.texte)
        self.assertIn("jamais rejouée", self.texte)

    def test_inconnues_des_journaux_conservees_litteralement(self):
        self.assertIn("non consigné", self.texte)
        self.assertIn("INCONNU", self.texte)

    def test_acquisition_officielle_conserve_l_ecart_de_forme_cli(self):
        self.assertIn("--officiel", self.texte)
        self.assertIn("HARNESS_ERROR", self.texte)

    def test_empreintes_scellees_citees(self):
        self.assertIn(_RECUS_SCELLES, self.texte)
        self.assertIn(_PREFLIGHTS_SCELLES, self.texte)

    def test_effet_semantique_et_refus_expliques_dans_le_guide(self):
        self.assertIn(
            "<strong>demonstration-v1-xs-15</strong> — entrée déclarée et non "
            "mesurée.",
            self.texte,
        )
        self.assertIn("de sept à huit", self.texte)
        self.assertIn("6/8 attendu, 6/7 stocké", self.texte)
        self.assertIn("il se lit comme un refus, pas comme un succès", self.texte)

    def test_aucune_conclusion_de_classement(self):
        for interdit in ("gagnant", "classement général", "score global"):
            with self.subTest(interdit=interdit):
                self.assertNotIn(f"{interdit} est", self.texte)
        self.assertIn("aucun classement", self.texte)


class LienDepuisLeReadmeRacineTests(unittest.TestCase):
    """Le README racine porte le lien minimal vers le guide, et rien de plus."""

    def setUp(self):
        self.texte = (RACINE / "README.md").read_text(encoding="utf-8")

    def test_lien_relatif_unique_vers_le_guide(self):
        cible = M.CHEMIN_GUIDE_UTILISATION.as_posix()
        self.assertEqual(self.texte.count(f"]({cible})"), 1)

    def test_lien_designe_un_fichier_present(self):
        self.assertTrue(_GUIDE.is_file())

    def test_ajout_limite_a_une_seule_ligne(self):
        lignes = [
            ligne
            for ligne in self.texte.splitlines()
            if M.CHEMIN_GUIDE_UTILISATION.as_posix() in ligne
        ]
        self.assertEqual(len(lignes), 1)
        # Item de liste ordinaire portant un lien et un seul
        self.assertRegex(lignes[0], r"^(?:- |\d+\. )")
        self.assertEqual(len(re.findall(r"\]\([^)]+\)", lignes[0])), 1)


if __name__ == "__main__":
    unittest.main()
