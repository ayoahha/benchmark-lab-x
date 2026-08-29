# /// script
# requires-python = ">=3.12"
# ///
"""Commande cout V1-XS-13 au seam public, sans appel distant.

Chaque test passe par `principal(["cout"])` avec une racine de dépôt
temporaire : les preuves versionnées réelles y sont copiées, ou la table
de métriques copiée est ajustée en double local pour la branche absente
du lot réel (nombre positif de sorties officiellement acceptables).
D_V1_02 = NON_DEFINI_V1 : la métrique « coût d'abonnement par sortie
officiellement acceptable » reste littéralement NON_DEFINI, que le
nombre de sorties officiellement acceptables soit nul ou positif ;
aucune division, allocation, valeur nulle ni valeur de remplacement
n'est calculée. Les tarifs catalogue mensuels des sources de plans
validées sont publiés comme tels, sans total ; les quotas déclarés du
registre officiel forment un objet distinct, jamais converti en monnaie.
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
# Tarifs catalogue mensuels attendus, littéraux indépendants issus de la
# lecture humaine de sources-plans-v1.toml : (nom, montant, classe MSW)
_TARIFS_ATTENDUS = {
    "antigravity-gemini-3-7-flash": ("Google AI Pro", 20, "FAIT_ETABLI"),
    "claude-code-fable-5": ("Claude Max 5x", 100, "FAIT_ETABLI"),
    "claude-code-opus-5": ("Claude Max 5x, même compte", 100, "FAIT_ETABLI"),
    "codex-gpt-5-6-sol": ("Codex Pro 20x", 200, "DEDUCTION_RAISONNEE"),
    "cursor-kimi-k3": ("Cursor Ultra", 200, "FAIT_ETABLI"),
    "grok-build-grok-4-6": ("SuperGrok Heavy", 300, "FAIT_ETABLI"),
    "zai-glm-5-3": ("Z.AI Coding Plan Lite", 18, "FAIT_ETABLI"),
}
_CHAMPS_QUOTA_ORDRE = (
    "unite",
    "valeur",
    "portee",
    "reset_fenetre",
    "reset_ancrage",
    "reset_au_depassement",
)


def _cles_profondes(valeur: object) -> list[str]:
    """Toutes les clés du document, à tous les niveaux, en minuscules."""
    if isinstance(valeur, dict):
        cles = [str(cle).lower() for cle in valeur]
        for sous_valeur in valeur.values():
            cles.extend(_cles_profondes(sous_valeur))
        return cles
    if isinstance(valeur, list):
        cles: list[str] = []
        for element in valeur:
            cles.extend(_cles_profondes(element))
        return cles
    return []


class _ArbrePreuvesReelles:
    racine: Path
    chemin_cout: Path

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
        self.chemin_cout = self.racine / M.CHEMIN_COUT_ABONNEMENT
        # Le reçu dérivé copié avec l'arbre réel est retiré : chaque test
        # part sans reçu, seule la commande cout le produit
        self.chemin_cout.unlink(missing_ok=True)
        self.page = self.racine / M.CHEMIN_PAGE

    def _commande(self, *arguments: str) -> tuple[int, str]:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = M.principal(list(arguments), racine=self.racine)
        return code, sortie.getvalue()

    def _cout(self) -> tuple[int, str]:
        return self._commande("cout")

    def _document(self) -> dict:
        return json.loads(self.chemin_cout.read_text(encoding="utf-8"))

    def _section_cout(self) -> str:
        page = self.page.read_text(encoding="utf-8")
        return page.split('<section id="cout-abonnement-v1">', 1)[1].split(
            "</section>", 1
        )[0]


class CoutPreuveCouranteTests(_ArbrePreuvesReelles, unittest.TestCase):
    """Preuve courante : zéro sortie officiellement acceptable."""

    def test_cout_non_defini_tarifs_visibles_quota_distinct(self):
        code, sortie = self._cout()
        self.assertEqual(0, code, sortie)
        self.assertTrue(self.chemin_cout.is_file())
        document = self._document()
        # Décision propriétaire figée, valeur exacte
        self.assertEqual("D_V1_02", document["decision"]["reference"])
        self.assertEqual("NON_DEFINI_V1", document["decision"]["valeur"])
        # Métrique littéralement NON_DEFINI avec zéro sortie acceptable
        self.assertEqual("NON_DEFINI", document["metrique"]["valeur"])
        sorties = document["sorties_officiellement_acceptables"]
        self.assertEqual(0, sorties["nombre"])
        self.assertEqual(
            M.CHEMIN_TABLE_METRIQUES.as_posix(), sorties["source"]["chemin"]
        )
        sha_table = hashlib.sha256(
            (self.racine / M.CHEMIN_TABLE_METRIQUES).read_bytes()
        ).hexdigest()
        self.assertEqual(sha_table, sorties["source"]["sha256"])
        # Tarifs catalogue mensuels par configuration, sans total
        tarifs = document["tarifs_catalogue"]["configurations"]
        self.assertEqual(list(_PANEL), [t["configuration_id"] for t in tarifs])
        for tarif in tarifs:
            nom, montant, classe = _TARIFS_ATTENDUS[tarif["configuration_id"]]
            self.assertEqual(nom, tarif["nom"], tarif["configuration_id"])
            self.assertEqual(montant, tarif["prix_montant"], tarif["configuration_id"])
            self.assertEqual("USD", tarif["prix_devise"], tarif["configuration_id"])
            self.assertEqual("MONTH", tarif["periode"], tarif["configuration_id"])
            self.assertEqual(classe, tarif["classe_msw"], tarif["configuration_id"])
            self.assertEqual(
                "D-V1-01",
                tarif["attestation_reference"],
                tarif["configuration_id"],
            )
        self.assertEqual(
            "CATALOGUE_STANDARD_MENSUEL_USD_HORS_TAXE_REMISE_ET_FACTURATION_LOCALE",
            document["tarifs_catalogue"]["semantique_prix"],
        )
        # La déduction raisonnée Codex conserve ses prémisses explicites
        codex = next(
            t for t in tarifs if t["configuration_id"] == "codex-gpt-5-6-sol"
        )
        self.assertIn("premisses", codex)
        self.assertEqual(3, len(codex["premisses"]))
        # Quotas déclarés : objet distinct, champs du registre tels quels
        quotas = document["quotas_declares"]["configurations"]
        self.assertEqual(list(_PANEL), [q["configuration_id"] for q in quotas])
        for entree in quotas:
            self.assertEqual(1, len(entree["quotas"]), entree["configuration_id"])
            quota = entree["quotas"][0]
            self.assertEqual(
                list(_CHAMPS_QUOTA_ORDRE), list(quota), entree["configuration_id"]
            )
            for cle in _CHAMPS_QUOTA_ORDRE:
                self.assertEqual(
                    "INCONNU", quota[cle], f"{entree['configuration_id']}.{cle}"
                )
        # Chemins et SHA-256 des sources utilisées
        chemins_sources = [s["chemin"] for s in document["sources"]]
        self.assertIn(M.CHEMIN_TABLE_METRIQUES.as_posix(), chemins_sources)
        self.assertIn(M.CHEMIN_SOURCES_PLANS.as_posix(), chemins_sources)
        for ident in _PANEL:
            self.assertIn(
                (M.REGISTRE_OFFICIEL / f"{ident}.toml").as_posix(),
                chemins_sources,
            )
        for source in document["sources"]:
            sha_reel = hashlib.sha256(
                (self.racine / source["chemin"]).read_bytes()
            ).hexdigest()
            self.assertEqual(sha_reel, source["sha256"], source["chemin"])

    def test_cout_refuse_sans_table_metriques(self):
        # Sans table publiée par metriques, cout ne recalcule rien :
        # refus fail-closed nommé, aucun document écrit
        (self.racine / M.CHEMIN_TABLE_METRIQUES).unlink()
        code, sortie = self._cout()
        self.assertEqual(1, code)
        self.assertIn("table de métriques absente", sortie)
        self.assertFalse(self.chemin_cout.exists())


class CoutNombrePositifTests(_ArbrePreuvesReelles, unittest.TestCase):
    """Fixture publique : nombre positif de sorties acceptables sous
    NON_DEFINI_V1 — la métrique reste NON_DEFINI, sans division."""

    def setUp(self):
        super().setUp()
        # Double local : la table copiée porte trois sorties
        # officiellement acceptables, branche absente du lot réel
        chemin_table = self.racine / M.CHEMIN_TABLE_METRIQUES
        table = json.loads(chemin_table.read_text(encoding="utf-8"))
        table["agregat"]["numerateur"] = 3
        chemin_table.write_text(
            json.dumps(table, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_nombre_positif_reste_non_defini_sans_division(self):
        code, sortie = self._cout()
        self.assertEqual(0, code, sortie)
        document = self._document()
        self.assertEqual("NON_DEFINI_V1", document["decision"]["valeur"])
        # Toujours NON_DEFINI, jamais une division ni une allocation
        self.assertEqual("NON_DEFINI", document["metrique"]["valeur"])
        self.assertEqual(
            3, document["sorties_officiellement_acceptables"]["nombre"]
        )
        # Aucune clé d'allocation ou de coût calculé n'apparaît
        for cle in _cles_profondes(document):
            self.assertNotIn("allocation", cle)
            self.assertNotIn("par_sortie", cle)
            self.assertNotIn("total", cle)
        # Les tarifs catalogue restent des tarifs, jamais des parts
        for tarif in document["tarifs_catalogue"]["configurations"]:
            _, montant, _ = _TARIFS_ATTENDUS[tarif["configuration_id"]]
            self.assertEqual(montant, tarif["prix_montant"])


class CoutSeparationObjetsTests(_ArbrePreuvesReelles, unittest.TestCase):
    """Refus de toute conversion quota-monnaie ; absence de total et de
    double comptage du plan Claude partagé."""

    def test_aucune_conversion_aucun_total_aucun_double_comptage(self):
        code, sortie = self._cout()
        self.assertEqual(0, code, sortie)
        document = self._document()
        # Aucun total à aucun niveau du document
        for cle in _cles_profondes(document):
            self.assertNotIn("total", cle)
        # L'objet quotas est distinct et ne porte aucune monnaie
        for entree in document["quotas_declares"]["configurations"]:
            self.assertNotIn("prix_montant", entree)
            self.assertNotIn("prix_devise", entree)
            for quota in entree["quotas"]:
                self.assertEqual(list(_CHAMPS_QUOTA_ORDRE), list(quota))
        # L'objet tarifs ne porte aucun quota
        for tarif in document["tarifs_catalogue"]["configurations"]:
            self.assertNotIn("quotas", tarif)
            self.assertNotIn("quota", tarif)
        # Les deux configurations Claude partagent un même plan déclaré :
        # elles restent deux lignes de tarif catalogue, sans aucun total
        # qui les compterait deux fois comme dépense
        tarifs = document["tarifs_catalogue"]["configurations"]
        claude = [
            t["prix_montant"]
            for t in tarifs
            if t["configuration_id"]
            in ("claude-code-fable-5", "claude-code-opus-5")
        ]
        self.assertEqual([100, 100], claude)
        texte = json.dumps(document)
        # 200 n'apparaît que comme tarifs catalogue Codex et Cursor,
        # jamais comme somme du plan Claude partagé
        self.assertNotIn('"total"', texte)


class CoutDeterminismeTests(_ArbrePreuvesReelles, unittest.TestCase):
    """Déterminisme byte-identique sur deux générations."""

    def test_cout_byte_identique(self):
        code, sortie = self._cout()
        self.assertEqual(0, code, sortie)
        premiere = self.chemin_cout.read_bytes()
        code, sortie = self._cout()
        self.assertEqual(0, code, sortie)
        self.assertEqual(premiere, self.chemin_cout.read_bytes())

    def test_cout_puis_restituer_byte_identique(self):
        code, sortie = self._cout()
        self.assertEqual(0, code, sortie)
        code, sortie = self._commande("restituer")
        self.assertEqual(0, code, sortie)
        premiere_cout = self.chemin_cout.read_bytes()
        premiere_page = self.page.read_bytes()
        code, sortie = self._cout()
        self.assertEqual(0, code, sortie)
        code, sortie = self._commande("restituer")
        self.assertEqual(0, code, sortie)
        self.assertEqual(premiere_cout, self.chemin_cout.read_bytes())
        self.assertEqual(premiere_page, self.page.read_bytes())


class CoutRafraichissementTests(_ArbrePreuvesReelles, unittest.TestCase):
    """Un reçu de coût existant est régénéré par restituer depuis les
    sources courantes : après régénération de la table de métriques, la
    page ne restitue jamais une citation de source périmée et le
    vérificateur strict valide."""

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

    def test_restituer_rafraichit_le_recu_apres_regeneration_metriques(self):
        code, sortie = self._cout()
        self.assertEqual(0, code, sortie)
        premiere = self.chemin_cout.read_bytes()
        # Double cohérent : la requête du reçu zai -002 diverge du
        # descripteur verrouillé — la table régénérée change d'empreinte
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
        code, sortie = self._commande("metriques")
        self.assertEqual(0, code, sortie)
        code, sortie = self._commande("restituer")
        self.assertEqual(0, code, sortie)
        # Le reçu existant a été régénéré depuis les sources courantes :
        # il cite l'empreinte courante de la table, et la métrique reste
        # littéralement NON_DEFINI
        self.assertNotEqual(premiere, self.chemin_cout.read_bytes())
        document = self._document()
        sha_table = hashlib.sha256(
            (self.racine / M.CHEMIN_TABLE_METRIQUES).read_bytes()
        ).hexdigest()
        sorties = document["sorties_officiellement_acceptables"]
        self.assertEqual(sha_table, sorties["source"]["sha256"])
        self.assertEqual(0, sorties["nombre"])
        self.assertEqual("NON_DEFINI", document["metrique"]["valeur"])
        self.assertEqual("NON_DEFINI_V1", document["decision"]["valeur"])
        code, sortie = self._commande("verifier-restitution")
        self.assertEqual(0, code, sortie)

    def test_restituer_ne_cree_jamais_le_recu_absent(self):
        # Sans reçu produit par cout, restituer n'en crée aucun
        self.assertFalse(self.chemin_cout.exists())
        code, sortie = self._commande("restituer")
        self.assertEqual(0, code, sortie)
        self.assertFalse(self.chemin_cout.exists())
        code, sortie = self._commande("verifier-restitution")
        self.assertEqual(0, code, sortie)


class CoutRestitutionTests(_ArbrePreuvesReelles, unittest.TestCase):
    """Restitution et vérificateur : section distincte, fidélité
    contrôlée, refus ciblé après altération."""

    def _generer(self) -> None:
        code, sortie = self._cout()
        self.assertEqual(0, code, sortie)
        code, sortie = self._commande("restituer")
        self.assertEqual(0, code, sortie)

    def test_restitution_section_cout_et_verificateur_valide(self):
        self._generer()
        page = self.page.read_text(encoding="utf-8")
        self.assertIn('<section id="cout-abonnement-v1">', page)
        section = self._section_cout()
        # La métrique exacte NON_DEFINI sous la décision figée
        self.assertIn("D_V1_02", section)
        self.assertIn("NON_DEFINI_V1", section)
        self.assertIn("<code>NON_DEFINI</code>", section)
        self.assertIn(
            "cout_abonnement_par_sortie_officiellement_acceptable", section
        )
        # Nombre courant de sorties officiellement acceptables
        self.assertIn("<code>0</code>", section)
        # Tarifs catalogue comme tels, avec période, devise et classe MSW
        for ident, (nom, montant, classe) in _TARIFS_ATTENDUS.items():
            self.assertIn(ident, section)
            self.assertIn(nom, section)
            self.assertIn(f"<code>{montant}</code>", section)
            self.assertIn(classe, section)
        self.assertIn("<code>USD</code>", section)
        self.assertIn("<code>MONTH</code>", section)
        self.assertIn("2026-08-26", section)
        self.assertIn("2026-05-19", section)
        # Quotas séparément, sur leurs propres lignes
        self.assertEqual(7, section.count(' data-cout-tarif="'))
        self.assertEqual(7, section.count(' data-cout-quota="'))
        self.assertEqual(1, section.count(' data-cout-metrique="non-defini"'))
        # Sources citées avec leurs empreintes
        self.assertIn(M.CHEMIN_SOURCES_PLANS.as_posix(), section)
        self.assertIn(M.CHEMIN_TABLE_METRIQUES.as_posix(), section)
        code, sortie = self._commande("verifier-restitution")
        self.assertEqual(0, code, sortie)

    def test_verificateur_refuse_metrique_substituee(self):
        # Altération : une valeur de remplacement chasse NON_DEFINI du
        # document stocké — refus fail-closed nommé (RG-09)
        self._generer()
        document = self._document()
        document["metrique"]["valeur"] = "0"
        self.chemin_cout.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        code, sortie = self._commande("verifier-restitution")
        self.assertEqual(1, code)
        self.assertIn("NON_DEFINI", sortie)

    def test_verificateur_refuse_tarif_altere(self):
        # Altération : un tarif catalogue stocké est falsifié — le
        # document est comparé à la reconstruction indépendante
        self._generer()
        document = self._document()
        for tarif in document["tarifs_catalogue"]["configurations"]:
            if tarif["configuration_id"] == "antigravity-gemini-3-7-flash":
                tarif["prix_montant"] = 21
        self.chemin_cout.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        code, sortie = self._commande("verifier-restitution")
        self.assertEqual(1, code)
        self.assertIn("tarifs catalogue", sortie)

    def test_verificateur_refuse_section_alteree(self):
        # Altération : la section rendue est retouchée après génération —
        # la fidélité de la section est contrôlée fragment par fragment
        self._generer()
        page = self.page.read_text(encoding="utf-8")
        section = self._section_cout()
        alteree = section.replace(
            "<code>NON_DEFINI</code>", "<code>12.5 USD</code>", 1
        )
        self.assertNotEqual(section, alteree)
        self.page.write_text(
            page.replace(section, alteree, 1), encoding="utf-8"
        )
        code, sortie = self._commande("verifier-restitution")
        self.assertEqual(1, code)
        self.assertIn("coût d'abonnement", sortie)


if __name__ == "__main__":
    unittest.main()
