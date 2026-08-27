# /// script
# requires-python = ">=3.12"
# ///
"""Dossiers de revue aveugle V1-XS-10 au seam public, sans appel distant.

Chaque test passe par `principal(["dossiers"])` avec une racine de dépôt
temporaire et une racine privée temporaire : le verrou et son matériel privé
y sont matérialisés par `verrouiller`, les reçus d'acquisition sont des
enveloppes V1 valides construites par le test, et le registre de verdicts est
produit par `valider`. Aucun contenu privé (sel, manifeste d'ordre) n'est
jamais affiché ni publié.
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
from unittest import mock

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import campagne_v1 as M  # noqa: E402

_CAMPAGNE = Path("tasks/dev/pre-cadrage-entretien-client/campagne-v1")
_SOURCES_PAQUET = RACINE / "tasks/dev/pre-cadrage-entretien-client"
_FICHIERS_PAQUET = (
    "manifeste-paquet.json",
    "brief-proprietaire.md",
    "registre-verite.md",
    "stimulus.md",
    "temoins-qualification.md",
)
_FICHIERS_ENTREE = (
    M.CHEMIN_ETAT.as_posix(),
    M.CHEMIN_SOURCES_PLANS.as_posix(),
    "docs/PRD.md",
    "docs/ARD.md",
    "docs/RULES.md",
    "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
    "rapport-decision-m10-2-v1/rapport-interne.md",
)
_REPERTOIRES_ENTREE = (
    _CAMPAGNE / "registre-panel-v1",
    _CAMPAGNE / "preflights-v1",
)


def _sortie_acceptable() -> str:
    temoins = (_SOURCES_PAQUET / "temoins-qualification.md").read_text(
        encoding="utf-8"
    )
    return temoins.split("```markdown\n", 1)[1].split("\n```", 1)[0] + "\n"


def _enveloppe_recu(
    identifiant: str,
    execution: dict,
    predecesseur: str | None,
    stimulus_sha: str,
) -> tuple[str, dict]:
    charge = {
        "carte": {"chemin": M.CHEMIN_CARTE, "sha256": "0" * 64},
        "configuration": {
            "identifiant": identifiant,
            "chemin": f"{M.REGISTRE_OFFICIEL.as_posix()}/{identifiant}.toml",
            "sha256": "1" * 64,
        },
        "creneau": f"{identifiant}:{stimulus_sha}",
        "execution": execution,
        "interface_declaree": {
            "etat": "DECLARE",
            "champs": {"type": "cli", "version": "INCONNU"},
        },
        "measurement_profile": "subscription",
        "paquet": {
            "chemin": M.CHEMIN_PAQUET,
            "sha256": M.EMPREINTE_MANIFESTE_APPROUVEE,
        },
        "plan_declare": {"etat": "DECLARE", "champs": {"nom": "INCONNU"}},
        "predecesseur_adresse_contenu": predecesseur,
        "provenance_servie": "INCONNU",
        "quota_observe": "INCONNU",
        "requete": {
            "etat": "REQUESTED",
            "argv_resolu": ["double-harnais", "__PROMPT_FILE__"],
            "mode_stdin": "__PROMPT_FILE__",
            "espace_de_travail": "__ISOLATED_WORKSPACE__",
        },
        "stimulus": {"chemin": M.CHEMIN_STIMULUS, "sha256": stimulus_sha},
    }
    adresse = M.adresse_canonique(charge)
    return adresse, {
        "schema_version": M.SCHEMA_RECU,
        "content_address": {"algorithm": "SHA256", "sha256": adresse},
        "payload": charge,
    }


def _execution_observee(stdout: str) -> dict:
    return {
        "etat": "OBSERVED",
        "sortie": {"stdout": stdout, "stderr": ""},
        "code_sortie": 0,
        "latence_ms": 4273,
    }


class DossiersRevueAveugleTests(unittest.TestCase):
    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self._temporaire_prive = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire_prive.cleanup)
        self.racine = Path(self._temporaire.name)
        self.privee = Path(self._temporaire_prive.name)
        for nom in _FICHIERS_PAQUET:
            destination = self.racine / _SOURCES_PAQUET.relative_to(RACINE) / nom
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_SOURCES_PAQUET / nom, destination)
        validateur = self.racine / M.CHEMIN_VALIDATEUR
        validateur.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RACINE / M.CHEMIN_VALIDATEUR, validateur)
        for relatif in _FICHIERS_ENTREE:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        for repertoire in _REPERTOIRES_ENTREE:
            shutil.copytree(RACINE / repertoire, self.racine / repertoire)
        self.recus = self.racine / _CAMPAGNE / "recus-v1"
        self.recus.mkdir(parents=True, exist_ok=True)
        self.stimulus_sha = hashlib.sha256(
            (self.racine / M.CHEMIN_STIMULUS).read_bytes()
        ).hexdigest()
        self.repertoire_dossiers = self.racine / _CAMPAGNE / "dossiers-revue-aveugle-v1"
        self.chemin_manifeste = self.repertoire_dossiers / "manifeste-dossiers.json"
        self.chemin_engagement = self.repertoire_dossiers / "engagement-ordre.json"
        self.chemin_controle = self.repertoire_dossiers / "controle-fuites.json"
        # Verrou matérialisé dans le bac : matériel privé temporaire cohérent
        self.assertEqual(
            M.principal(
                ["verrouiller"], racine=self.racine, racine_privee=self.privee
            ),
            0,
        )

    def _deposer_recu(self, adresse: str, enveloppe: dict) -> Path:
        chemin = self.recus / f"{adresse}.json"
        chemin.write_text(
            json.dumps(enveloppe, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        return chemin

    def _valider(self) -> int:
        # Frontière système simulée à un CPython 3.12 concret, à l'identique
        # de la fixture de validation : le pin de production reste intact
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

    def _dossiers(self) -> tuple[int, str]:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = M.principal(
                ["dossiers"], racine=self.racine, racine_privee=self.privee
            )
        return code, sortie.getvalue()

    def _deposer_et_valider(
        self, identifiant: str, stdout: str, predecesseur: str | None = None
    ) -> str:
        adresse, enveloppe = _enveloppe_recu(
            identifiant,
            _execution_observee(stdout),
            predecesseur,
            self.stimulus_sha,
        )
        self._deposer_recu(adresse, enveloppe)
        self.assertEqual(self._valider(), 0)
        return adresse

    def test_lot_avec_pass_rend_zero_et_ecrit_le_manifeste(self):
        self._deposer_et_valider("zai-glm-5-3", _sortie_acceptable())

        code, sortie = self._dossiers()
        self.assertEqual(0, code, sortie)

        manifeste = json.loads(self.chemin_manifeste.read_text(encoding="utf-8"))
        self.assertEqual(1, len(manifeste["dossiers"]))

    def test_dossier_opaque_contenus_byte_identiques_sans_identifiant(self):
        stdout = _sortie_acceptable()
        self._deposer_et_valider("zai-glm-5-3", stdout)

        code, sortie = self._dossiers()
        self.assertEqual(0, code, sortie)

        manifeste = json.loads(self.chemin_manifeste.read_text(encoding="utf-8"))
        entree = manifeste["dossiers"][0]
        self.assertRegex(entree["item"], r"^ITEM-\d{3}$")
        contenu = (self.racine / entree["fichier"]).read_bytes()
        # stimulus et sortie candidate embarqués byte-identiques
        self.assertIn((self.racine / M.CHEMIN_STIMULUS).read_bytes(), contenu)
        self.assertIn(stdout.encode("utf-8"), contenu)
        # rubrique HR-001 byte-identique au bloc littéral du registre de vérité
        rubrique = (
            "- ID: HR-001\n"
            "  - Condition d'entrée : résultat automatique global `PASS` et "
            "dossier contenant le stimulus ainsi que la sortie candidate, "
            "sans identité de candidat ni IDs internes du corrigé\n"
            "  - Question absolue : « Ce pré-cadrage peut-il être utilisé tel "
            "quel par le consultant pour préparer l'entretien, sans "
            "reconstruction matérielle ? »\n"
            "  - `ACCEPTABLE` : oui ; les corrections éventuelles portent "
            "seulement sur la forme\n"
            "  - `NOT_ACCEPTABLE` : non ; une reconstruction matérielle est "
            "nécessaire\n"
            "  - `UNABLE_TO_JUDGE` : le dossier ne permet pas de répondre ; "
            "la preuve humaine est indisponible et le candidat n'est pas "
            "dégradé\n"
        ).encode("utf-8")
        registre_verite = (
            self.racine
            / "tasks/dev/pre-cadrage-entretien-client/registre-verite.md"
        ).read_bytes()
        self.assertIn(rubrique, registre_verite)
        self.assertIn(rubrique, contenu)
        # aucune identité : ni configuration, ni acquisition, ni modèle
        self.assertNotIn(b"zai-glm-5-3", contenu)
        self.assertNotIn(b"ACQ-V1-ZAI-GLM-5-3-001", contenu)
        self.assertNotIn("glm-5.3".encode("utf-8"), contenu)
        # le manifeste publie l'empreinte du fichier dossier écrit
        self.assertEqual(
            hashlib.sha256(contenu).hexdigest(), entree["sha256"]
        )

    def test_rubrique_byte_identique_verifiee_par_empreinte(self):
        self._deposer_et_valider("zai-glm-5-3", _sortie_acceptable())

        code, sortie = self._dossiers()
        self.assertEqual(0, code, sortie)

        manifeste = json.loads(self.chemin_manifeste.read_text(encoding="utf-8"))
        rubrique = manifeste["rubrique"]
        self.assertEqual("HR-001", rubrique["id"])
        # Empreinte attendue calculée depuis un littéral indépendant de
        # l'implémentation : le bloc exact du registre de vérité
        rubrique_litterale = (
            "- ID: HR-001\n"
            "  - Condition d'entrée : résultat automatique global `PASS` et "
            "dossier contenant le stimulus ainsi que la sortie candidate, "
            "sans identité de candidat ni IDs internes du corrigé\n"
            "  - Question absolue : « Ce pré-cadrage peut-il être utilisé tel "
            "quel par le consultant pour préparer l'entretien, sans "
            "reconstruction matérielle ? »\n"
            "  - `ACCEPTABLE` : oui ; les corrections éventuelles portent "
            "seulement sur la forme\n"
            "  - `NOT_ACCEPTABLE` : non ; une reconstruction matérielle est "
            "nécessaire\n"
            "  - `UNABLE_TO_JUDGE` : le dossier ne permet pas de répondre ; "
            "la preuve humaine est indisponible et le candidat n'est pas "
            "dégradé\n"
        ).encode("utf-8")
        self.assertEqual(
            hashlib.sha256(rubrique_litterale).hexdigest(), rubrique["sha256"]
        )
        # la source citée est le registre de vérité du paquet approuvé
        chemin_registre = (
            "tasks/dev/pre-cadrage-entretien-client/registre-verite.md"
        )
        self.assertEqual(chemin_registre, rubrique["source"]["chemin"])
        empreinte_fichier = hashlib.sha256(
            (self.racine / chemin_registre).read_bytes()
        ).hexdigest()
        self.assertEqual(empreinte_fichier, rubrique["source"]["sha256"])
        paquet = json.loads(
            (self.racine / M.CHEMIN_PAQUET).read_text(encoding="utf-8")
        )
        entree_paquet = next(
            f for f in paquet["fichiers"] if f["chemin"] == "registre-verite.md"
        )
        self.assertEqual(entree_paquet["sha256"], rubrique["source"]["sha256"])

    def test_engagement_ordre_ecrit_avant_dossiers_sans_correspondance(self):
        self._deposer_et_valider("zai-glm-5-3", _sortie_acceptable())
        ecritures: list[str] = []
        originale = Path.write_bytes

        def espion(chemin: Path, donnees: bytes) -> object:
            ecritures.append(str(chemin))
            return originale(chemin, donnees)

        with mock.patch.object(
            Path, "write_bytes", autospec=True, side_effect=espion
        ):
            code, sortie = self._dossiers()
        self.assertEqual(0, code, sortie)

        # l'engagement d'ordre est écrit avant tout fichier de dossier
        cibles = [
            chemin
            for chemin in ecritures
            if "dossiers-revue-aveugle-v1" in chemin
        ]
        self.assertTrue(cibles)
        premier_dossier = next(
            rang for rang, chemin in enumerate(cibles) if "/dossiers/" in chemin
        )
        self.assertTrue(
            any(
                chemin.endswith("engagement-ordre.json")
                for chemin in cibles[:premier_dossier]
            ),
            cibles,
        )
        # la correspondance n'est pas publiée : ni identifiant de
        # configuration, ni identifiant d'acquisition dans l'engagement
        texte_engagement = self.chemin_engagement.read_text(encoding="utf-8")
        self.assertNotIn("zai-glm-5-3", texte_engagement)
        self.assertNotIn("ACQ-V1", texte_engagement)
        engagement = json.loads(texte_engagement)
        self.assertEqual("SEALED", engagement["correspondance"])
        self.assertEqual(
            "AFTER_ALL_HUMAN_VERDICTS_FROZEN", engagement["revelation"]
        )
        # l'ordre de revue porte les seuls identifiants opaques et couvre le
        # lot verrouillé complet, indépendamment des verdicts ; les dossiers
        # produits forment une sous-séquence ordonnée de l'engagement
        manifeste = json.loads(self.chemin_manifeste.read_text(encoding="utf-8"))
        items_engagement = [
            (d["item"], d["position"]) for d in engagement["ordre_revue"]
        ]
        self.assertEqual(2, engagement["cardinalite_revue"])
        self.assertEqual(2, len(items_engagement))
        self.assertEqual(
            sorted(items_engagement, key=lambda entree: entree[1]),
            items_engagement,
        )
        positions = {d["item"]: d["position"] for d in engagement["ordre_revue"]}
        items_manifeste = [d["item"] for d in manifeste["dossiers"]]
        self.assertEqual(
            sorted(items_manifeste, key=lambda item: positions[item]),
            items_manifeste,
        )
        # l'engagement se chaîne au verrou par le commitment masqué, sans
        # jamais publier le contenu du manifeste privé
        verrou = json.loads(
            (self.racine / M.CHEMIN_VERROU).read_text(encoding="utf-8")
        )
        engagement_verrou = next(
            e
            for e in verrou["engagements_prives"]
            if e["kind"] == "manifeste-ordre"
        )
        self.assertEqual(
            engagement_verrou["commitment"],
            engagement["engagement_manifeste_verrou"]["commitment"],
        )
        self.assertEqual(
            engagement_verrou["commitment_method"],
            engagement["engagement_manifeste_verrou"]["commitment_method"],
        )

    def test_fuite_injectee_rend_non_nul_et_aucun_dossier_ecrit(self):
        # Fuite injectée dans un bloc ancré : le verdict automatique reste
        # PASS, seul le contrôle d'absence de fuite peut refuser le dossier
        stdout = _sortie_acceptable().replace(
            "- Aucun secret, identifiant ou jeton d'accès. [sources: N-G]",
            "- Aucun secret, identifiant ou jeton d'accès zai-glm-5-3. "
            "[sources: N-G]",
            1,
        )
        self._deposer_et_valider("zai-glm-5-3", stdout)

        code, sortie = self._dossiers()
        self.assertNotEqual(0, code)
        self.assertIn("fuite", sortie.lower())
        # fail-closed : aucun dossier, aucun manifeste
        self.assertFalse(self.chemin_manifeste.exists())
        self.assertFalse(
            (self.repertoire_dossiers / "dossiers").exists()
        )

    def test_controle_fuites_artefact_complet_et_reverifiable(self):
        self._deposer_et_valider("zai-glm-5-3", _sortie_acceptable())
        code, _ = self._dossiers()
        self.assertEqual(0, code)

        chemin_controle = self.repertoire_dossiers / "controle-fuites.json"
        self.assertTrue(chemin_controle.exists())
        controle = json.loads(chemin_controle.read_text(encoding="utf-8"))
        self.assertEqual(
            M.SCHEMA_CONTROLE_FUITES, controle["schema"]
        )
        self.assertEqual(
            "CONFORME_SUR_CATEGORIES_COUVERTES", controle["resultat"]
        )
        categories = controle["categories"]
        self.assertEqual(sorted(M.CATEGORIES_FUITES), sorted(categories))
        # materiel_prive n'est jamais sérialisé en valeurs : preuve non
        # réversible, la re-vérification exige la racine privée
        self.assertEqual(
            {
                "statut": "COUVERTE",
                "jetons_recherches": 2,
                "reverification": "RACINE_PRIVEE_REQUISE",
            },
            categories["materiel_prive"],
        )
        # chaque catégorie couverte et publiable porte ses jetons exacts,
        # dédupliqués
        self.assertIn(
            "zai-glm-5-3", categories["configuration_id"]["jetons"]
        )
        for entree in categories.values():
            for jeton in entree.get("jetons", []):
                self.assertEqual(
                    sorted(set(entree["jetons"])), entree["jetons"]
                )
        # re-vérification indépendante : aucun jeton couvert dans le dossier
        manifeste = json.loads(self.chemin_manifeste.read_text(encoding="utf-8"))
        self.assertEqual(1, len(manifeste["dossiers"]))
        entree = manifeste["dossiers"][0]
        dossier = (self.racine / entree["fichier"]).read_bytes()
        for entree_categorie in categories.values():
            for jeton in entree_categorie.get("jetons", []):
                self.assertNotIn(jeton.encode("utf-8"), dossier)
        # chaque dossier × catégorie : False si couverte, null sinon —
        # une absence de preuve n'est jamais une conclusion favorable
        self.assertEqual(1, len(controle["dossiers"]))
        self.assertEqual(entree["item"], controle["dossiers"][0]["item"])
        attendu_inclus = {
            nom: (False if ent["statut"] == "COUVERTE" else None)
            for nom, ent in categories.items()
        }
        self.assertEqual(
            attendu_inclus, controle["dossiers"][0]["jeton_inclus"]
        )

    def test_couverture_categories_explicite_et_honnete(self):
        self._deposer_et_valider("zai-glm-5-3", _sortie_acceptable())
        code, _ = self._dossiers()
        self.assertEqual(0, code)

        controle = json.loads(self.chemin_controle.read_text(encoding="utf-8"))
        categories = controle["categories"]
        # chaque catégorie porte un état explicite et un nombre de jetons
        self.assertEqual(sorted(M.CATEGORIES_FUITES), sorted(categories))
        for entree in categories.values():
            self.assertIn(entree["statut"], ("COUVERTE", "NON_COUVERTE"))
            self.assertIsInstance(entree["jetons_recherches"], int)
        # interface et quota : valeurs INCONNU dans le panel déclaré →
        # absence de preuve déclarée, jamais annoncées conformes
        for nom in ("interface", "quota"):
            self.assertEqual("NON_COUVERTE", categories[nom]["statut"])
            self.assertEqual(0, categories[nom]["jetons_recherches"])
            self.assertNotIn("jetons", categories[nom])
        self.assertEqual(
            "COUVERTE", categories["configuration_id"]["statut"]
        )
        self.assertGreater(
            categories["configuration_id"]["jetons_recherches"], 0
        )
        # le résultat global ne masque pas la couverture partielle
        self.assertEqual(
            "CONFORME_SUR_CATEGORIES_COUVERTES", controle["resultat"]
        )
        # la page ne cite que les catégories couvertes dans la phrase
        # d'absence de fuite et déclare les non couvertes comme absence
        # de preuve
        self.assertEqual(0, M.principal(["restituer"], racine=self.racine))
        page = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        self.assertIn("CONFORME_SUR_CATEGORIES_COUVERTES", page)
        segment = page.split("aucun jeton interdit", 1)[1].split(
            "n'apparaît", 1
        )[0]
        self.assertNotIn("interface", segment)
        self.assertNotIn("quota", segment)
        self.assertIn("interface", page)
        self.assertIn("quota", page)
        self.assertEqual(
            0, M.principal(["verifier-restitution"], racine=self.racine)
        )

    def test_sel_prive_absent_de_tout_artefact_public(self):
        self._deposer_et_valider("zai-glm-5-3", _sortie_acceptable())
        # stdout et stderr capturés ensemble : aucune valeur privée nulle part
        sortie = io.StringIO()
        with (
            contextlib.redirect_stdout(sortie),
            contextlib.redirect_stderr(sortie),
        ):
            code = M.principal(
                ["dossiers"], racine=self.racine, racine_privee=self.privee
            )
        self.assertEqual(0, code)
        self.assertEqual(0, M.principal(["restituer"], racine=self.racine))

        # le sel temporaire de la fixture sert à prouver l'absence ; sa
        # valeur n'est jamais affichée, y compris en cas d'échec
        sel = (
            self.privee / M.RELATIF_MATERIEL_VERROU / M.NOM_SEL_VERROU
        ).read_bytes()
        publics = {
            "manifeste": self.chemin_manifeste.read_bytes(),
            "controle": self.chemin_controle.read_bytes(),
            "engagement": self.chemin_engagement.read_bytes(),
            "page": (self.racine / M.CHEMIN_PAGE).read_bytes(),
            "sortie_commande": sortie.getvalue().encode("utf-8"),
        }
        manifeste = json.loads(self.chemin_manifeste.read_text(encoding="utf-8"))
        for entree in manifeste["dossiers"]:
            publics[f"dossier:{entree['item']}"] = (
                self.racine / entree["fichier"]
            ).read_bytes()
        for nom, contenu in publics.items():
            if sel in contenu or sel.hex().encode("utf-8") in contenu:
                self.fail(f"sel privé présent dans l'artefact public : {nom}")

    def _sortie_avec_fuite(self) -> str:
        return _sortie_acceptable().replace(
            "- Aucun secret, identifiant ou jeton d'accès. [sources: N-G]",
            "- Aucun secret, identifiant ou jeton d'accès zai-glm-5-3. "
            "[sources: N-G]",
            1,
        )

    def test_regeneration_lot_vide_purge_les_dossiers_perimes(self):
        adresse = self._deposer_et_valider("zai-glm-5-3", _sortie_acceptable())
        code, _ = self._dossiers()
        self.assertEqual(0, code)
        manifeste = json.loads(self.chemin_manifeste.read_text(encoding="utf-8"))
        self.assertEqual(1, len(manifeste["dossiers"]))
        fichier = self.racine / manifeste["dossiers"][0]["fichier"]
        self.assertTrue(fichier.exists())

        # le verdict bascule à FAIL : le lot éligible devient vide
        (self.recus / f"{adresse}.json").unlink()
        self._deposer_et_valider("zai-glm-5-3", "sortie non conforme\n")
        code, _ = self._dossiers()
        self.assertEqual(0, code)
        manifeste = json.loads(self.chemin_manifeste.read_text(encoding="utf-8"))
        self.assertEqual([], manifeste["dossiers"])
        # l'ancien dossier est purgé : le répertoire généré correspond
        # exactement au manifeste courant
        self.assertFalse(fichier.exists())
        repertoire = self.repertoire_dossiers / "dossiers"
        presents = (
            list(repertoire.iterdir()) if repertoire.exists() else []
        )
        self.assertEqual([], presents)

    def test_fuite_apres_lot_pass_ne_laisse_aucun_etat_presentable(self):
        adresse = self._deposer_et_valider("zai-glm-5-3", _sortie_acceptable())
        code, _ = self._dossiers()
        self.assertEqual(0, code)
        manifeste = json.loads(self.chemin_manifeste.read_text(encoding="utf-8"))
        fichier = self.racine / manifeste["dossiers"][0]["fichier"]
        self.assertTrue(fichier.exists())

        # la sortie revalidée contient une fuite : génération refusée
        (self.recus / f"{adresse}.json").unlink()
        self._deposer_et_valider("zai-glm-5-3", self._sortie_avec_fuite())
        code, sortie = self._dossiers()
        self.assertNotEqual(0, code)
        self.assertIn("fuite", sortie.lower())
        # aucun dossier antérieur ne reste présentable
        self.assertFalse(fichier.exists())
        # l'état antérieur n'est plus présentable comme courant : la
        # restitution refuse l'incohérence manifeste ↔ fichiers
        self.assertEqual(1, M.principal(["restituer"], racine=self.racine))
        self.assertEqual(
            1, M.principal(["verifier-restitution"], racine=self.racine)
        )

    def test_fichier_inattendu_dans_dossiers_refuse_sans_suppression(self):
        self._deposer_et_valider("zai-glm-5-3", _sortie_acceptable())
        code, _ = self._dossiers()
        self.assertEqual(0, code)
        inattendu = self.repertoire_dossiers / "dossiers" / "notes-operateur.txt"
        inattendu.write_text("annotation humaine\n", encoding="utf-8")
        code, sortie = self._dossiers()
        self.assertNotEqual(0, code)
        self.assertIn("inattendu", sortie.lower())
        # jamais de suppression silencieuse
        self.assertTrue(inattendu.exists())

    def test_coherence_dossiers_egalite_exacte_fichiers_declares(self):
        self._deposer_et_valider("zai-glm-5-3", _sortie_acceptable())
        code, _ = self._dossiers()
        self.assertEqual(0, code)
        # un dossier présent mais non déclaré rend l'état non conforme
        extra = self.repertoire_dossiers / "dossiers" / "ITEM-999.md"
        extra.write_bytes(b"contenu non declare\n")
        self.assertEqual(1, M.principal(["restituer"], racine=self.racine))
        self.assertEqual(
            1, M.principal(["verifier-restitution"], racine=self.racine)
        )

    def test_lot_vide_manifeste_zero_dossier_cause_exacte_sans_verdict(self):
        # sortie non conforme → verdict automatique FAIL ; l'autre
        # acquisition reste sans reçu : le lot éligible est vide
        self._deposer_et_valider("zai-glm-5-3", "sortie non conforme\n")
        code, _ = self._dossiers()
        self.assertEqual(0, code)

        manifeste = json.loads(self.chemin_manifeste.read_text(encoding="utf-8"))
        self.assertEqual([], manifeste["dossiers"])
        self.assertEqual(
            "aucune_sortie_pass", manifeste["lot_vide"]["cause"]
        )
        self.assertEqual(
            {"FAIL": 1}, manifeste["lot_vide"]["comptage_statuts"]
        )
        # aucun verdict de qualité dans le manifeste
        self.assertNotIn("verdict", manifeste)
        # aucun dossier écrit
        self.assertFalse((self.repertoire_dossiers / "dossiers").exists())
        # l'engagement d'ordre et le contrôle restent produits et cohérents
        engagement = json.loads(
            self.chemin_engagement.read_text(encoding="utf-8")
        )
        self.assertEqual(2, engagement["cardinalite_revue"])
        controle = json.loads(self.chemin_controle.read_text(encoding="utf-8"))
        self.assertEqual(
            "CONFORME_SUR_CATEGORIES_COUVERTES", controle["resultat"]
        )
        self.assertEqual([], controle["dossiers"])

    def test_restitution_alimentee_et_verifiee(self):
        adresse = self._deposer_et_valider("zai-glm-5-3", _sortie_acceptable())
        self._deposer_et_valider(
            "claude-code-opus-5", "sortie non conforme\n", predecesseur=adresse
        )
        code, sortie = self._dossiers()
        self.assertEqual(0, code)
        # RG-07 : la sortie de la commande est lisible et nomme les
        # exclusions avec leur cause
        self.assertIn("1 dossier", sortie)
        self.assertIn("1 exclusion", sortie)
        self.assertIn("claude-code-opus-5", sortie)
        self.assertIn("G-001", sortie)

        self.assertEqual(0, M.principal(["restituer"], racine=self.racine))
        page = (self.racine / M.CHEMIN_PAGE).read_text(encoding="utf-8")
        # la restitution affiche le nombre de dossiers, le nombre
        # d'exclusions et leur cause
        self.assertIn('id="dossiers-revue-aveugle"', page)
        self.assertIn("1 dossier", page)
        self.assertIn("1 exclusion", page)
        self.assertIn("G-001", page)
        self.assertEqual(
            0, M.principal(["verifier-restitution"], racine=self.racine)
        )


if __name__ == "__main__":
    unittest.main()
