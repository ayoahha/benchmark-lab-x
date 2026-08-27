# /// script
# requires-python = ">=3.12"
# ///
"""Commande etat V1-XS-12A au seam public, sans appel distant.

Chaque test passe par `principal(["etat"])` avec une racine de dépôt
temporaire : les preuves versionnées réelles y sont copiées, ou des
doubles locaux valides y sont construits pour les causes absentes du lot
réel (QUOTA_EXHAUSTED attribuable ou non prouvé, UNABLE_TO_JUDGE humain,
créneau sans aucune preuve). La couverture attendue du lot réel est 2/7 :
deux décisions officielles CANDIDATE_NOT_ACCEPTABLE et cinq causes
MISSING_OBSERVATION prouvées par les préflights HOLD. Aucun appel
candidat, aucune acquisition et aucune dépense n'ont lieu.
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
_ACQUISES = ("antigravity-gemini-3-7-flash", "zai-glm-5-3")
_NON_ACQUISES = tuple(ident for ident in _PANEL if ident not in _ACQUISES)


def _sortie_acceptable() -> str:
    temoins = (_SOURCES_PAQUET / "temoins-qualification.md").read_text(
        encoding="utf-8"
    )
    return temoins.split("```markdown\n", 1)[1].split("\n```", 1)[0] + "\n"


def _execution_observee(stdout: str) -> dict:
    return {
        "etat": "OBSERVED",
        "sortie": {"stdout": stdout, "stderr": ""},
        "code_sortie": 0,
        "latence_ms": 1,
    }


def _execution_incident(
    incident: str, fait: str, preuve_attribuable: str | None = None
) -> dict:
    execution = {"etat": "INCIDENT", "incident": incident, "fait": fait}
    if preuve_attribuable is not None:
        execution["preuve_attribuable"] = preuve_attribuable
    return execution


def _enveloppe_recu(
    identifiant: str,
    execution: dict,
    predecesseur: str | None,
    stimulus_sha: str,
) -> tuple[str, dict]:
    chemin_configuration = (
        f"{M.REGISTRE_OFFICIEL.as_posix()}/{identifiant}.toml"
    )
    charge = {
        "carte": {"chemin": M.CHEMIN_CARTE, "sha256": "0" * 64},
        "configuration": {
            "identifiant": identifiant,
            "chemin": chemin_configuration,
            "sha256": hashlib.sha256(
                (RACINE / chemin_configuration).read_bytes()
            ).hexdigest(),
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


class _EtatBase:
    racine: Path
    chemin_etat: Path

    def _etat(self) -> tuple[int, str]:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = M.principal(["etat"], racine=self.racine)
        return code, sortie.getvalue()

    def _creneaux(self) -> dict[str, dict]:
        etat = json.loads(self.chemin_etat.read_text(encoding="utf-8"))
        return {
            entree["configuration_id"]: entree
            for entree in etat["couverture"]["creneaux"]
        }

    def _couverture(self) -> dict:
        etat = json.loads(self.chemin_etat.read_text(encoding="utf-8"))
        return etat["couverture"]


class _ArbrePreuvesReelles(_EtatBase):
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
        self.chemin_etat = self.racine / M.CHEMIN_ETAT
        self.page = self.racine / M.CHEMIN_PAGE

    def _substituer_triplet(
        self, identifiant_cible: str, **mutations: str
    ) -> None:
        """Injecte une substitution de triplet configuration dans un reçu
        officiel -001, puis réaligne chaînage et registre de validation :
        la seule divergence restante porte sur le triplet lui-même."""
        repertoire = self.racine / _CAMPAGNE / "recus-v1"
        enveloppes = {
            chemin.name: json.loads(chemin.read_text(encoding="utf-8"))
            for chemin in repertoire.iterdir()
        }
        cible = next(
            nom
            for nom, enveloppe in enveloppes.items()
            if enveloppe["payload"]["configuration"]["identifiant"]
            == identifiant_cible
            and "recuperation" not in enveloppe["payload"]
        )
        cible_configuration = enveloppes[cible]["payload"]["configuration"]
        ancien_creneau = enveloppes[cible]["payload"]["creneau"]
        cible_configuration.update(mutations)
        if "identifiant" in mutations:
            stimulus = enveloppes[cible]["payload"]["stimulus"]["sha256"]
            enveloppes[cible]["payload"]["creneau"] = (
                f"{cible_configuration['identifiant']}:{stimulus}"
            )
        successeurs = {
            enveloppe["payload"]["predecesseur_adresse_contenu"]: nom
            for nom, enveloppe in enveloppes.items()
        }
        ordre = [
            next(
                nom
                for nom, enveloppe in enveloppes.items()
                if enveloppe["payload"]["predecesseur_adresse_contenu"] is None
            )
        ]
        while enveloppes[ordre[-1]]["content_address"]["sha256"] in successeurs:
            ordre.append(
                successeurs[
                    enveloppes[ordre[-1]]["content_address"]["sha256"]
                ]
            )
        nouvelles_adresses: dict[str, str] = {}
        reecritures: dict[str, tuple[str, str]] = {}
        rang_cible = ordre.index(cible)
        for nom in ordre[rang_cible:]:
            enveloppe = enveloppes[nom]
            predecesseur = enveloppe["payload"][
                "predecesseur_adresse_contenu"
            ]
            if predecesseur in nouvelles_adresses:
                enveloppe["payload"]["predecesseur_adresse_contenu"] = (
                    nouvelles_adresses[predecesseur]
                )
            adresse = M.adresse_canonique(enveloppe["payload"])
            enveloppe["content_address"]["sha256"] = adresse
            octets = M.octets_canoniques(enveloppe)
            anciene_adresse = nom[: -len(".json")]
            (repertoire / nom).unlink()
            (repertoire / f"{adresse}.json").write_bytes(octets)
            nouvelles_adresses[anciene_adresse] = adresse
            relatif = f"{_CAMPAGNE.as_posix()}/recus-v1/{nom}"
            reecritures[relatif] = (
                f"{_CAMPAGNE.as_posix()}/recus-v1/{adresse}.json",
                hashlib.sha256(octets).hexdigest(),
            )
        registre_chemin = self.racine / M.CHEMIN_REGISTRE_VALIDATION
        registre = json.loads(registre_chemin.read_text(encoding="utf-8"))
        for entree in registre["entrees"]:
            if entree["recu"] in reecritures:
                entree["recu"], entree["recu_sha256"] = reecritures[
                    entree["recu"]
                ]
                if (
                    "identifiant" in mutations
                    and entree["configuration_id"] == identifiant_cible
                    and entree["creneau"] == ancien_creneau
                ):
                    entree["creneau"] = enveloppes[cible]["payload"][
                        "creneau"
                    ]
        registre_chemin.write_bytes(M.octets_canoniques(registre))


class EtatPreuvesReellesTests(_ArbrePreuvesReelles, unittest.TestCase):
    """Arbre de preuves réel copié : le lot versionné tel quel."""

    def _instantane(self) -> dict[str, str]:
        return {
            chemin.relative_to(self.racine).as_posix(): hashlib.sha256(
                chemin.read_bytes()
            ).hexdigest()
            for chemin in sorted(self.racine.rglob("*"))
            if chemin.is_file()
        }

    def test_etat_nomme_acquisitions_incidents_manquantes_et_couverture(self):
        code, sortie = self._etat()
        self.assertEqual(0, code, sortie)
        self.assertTrue(sortie.strip())
        for attendu in (
            "Acquisitions",
            "Incidents",
            "données manquantes",
            "Couverture",
        ):
            self.assertIn(attendu, sortie)
        # Fraction exacte du lot réel : deux décisions officielles sur les
        # sept configurations déclarées
        self.assertIn("2/7", sortie)
        for ident in _PANEL:
            self.assertIn(ident, sortie)
        # Jetons littéraux préservés : incidents HARNESS_ERROR historiques,
        # causes MISSING_OBSERVATION prouvées, décisions FAIL gelées
        self.assertIn("HARNESS_ERROR", sortie)
        self.assertIn("MISSING_OBSERVATION", sortie)
        self.assertIn("CANDIDATE_NOT_ACCEPTABLE", sortie)
        # Aucune preuve de quota épuisé dans le lot réel : le jeton ne
        # peut pas apparaître
        self.assertNotIn("QUOTA_EXHAUSTED", sortie)

    def test_etat_etend_etat_v1_sans_seconde_source_de_verite(self):
        # La copie part d'un état sans couverture pour éprouver l'extension,
        # que le fichier versionné porte ou non déjà la clé
        contenu = json.loads(self.chemin_etat.read_text(encoding="utf-8"))
        contenu.pop("couverture", None)
        self.chemin_etat.write_text(
            json.dumps(contenu, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        avant = self._instantane()
        code, sortie = self._etat()
        self.assertEqual(0, code, sortie)
        apres = self._instantane()
        # Aucun fichier créé ni supprimé, seul l'état V1 est étendu
        self.assertEqual(set(avant), set(apres))
        modifies = [chemin for chemin in avant if avant[chemin] != apres[chemin]]
        self.assertEqual([M.CHEMIN_ETAT.as_posix()], modifies)

        etat = json.loads(self.chemin_etat.read_text(encoding="utf-8"))
        # Le contrat existant est préservé à l'identique
        self.assertEqual("campagne-v1/etat-v1/1", etat["schema_etat"])
        self.assertEqual("V1", etat["product_version"])
        self.assertEqual("abonnement", etat["measurement_profile"])
        self.assertEqual([], etat["panel"])
        self.assertEqual("recus-v1", etat["repertoire_recus"])

        couverture = etat["couverture"]
        self.assertEqual(2, couverture["numerateur"])
        self.assertEqual(7, couverture["denominateur"])
        self.assertEqual("2/7", couverture["fraction"])
        self.assertEqual(
            list(_PANEL),
            [entree["configuration_id"] for entree in couverture["creneaux"]],
        )
        creneaux = self._creneaux()
        for ident in _ACQUISES:
            self.assertTrue(creneaux[ident]["couvert"], ident)
            self.assertEqual(
                "CANDIDATE_NOT_ACCEPTABLE", creneaux[ident]["decision"]
            )
            self.assertIsNone(creneaux[ident]["cause"])
            self.assertEqual(["HARNESS_ERROR"], creneaux[ident]["incidents"])
        for ident in _NON_ACQUISES:
            self.assertFalse(creneaux[ident]["couvert"], ident)
            self.assertIsNone(creneaux[ident]["decision"])
            self.assertEqual("MISSING_OBSERVATION", creneaux[ident]["cause"])
        # Chaque créneau porte ses preuves : fichiers réels, empreintes exactes
        for entree in couverture["creneaux"]:
            self.assertTrue(entree["preuves"], entree["configuration_id"])
            for preuve in entree["preuves"]:
                octets = (self.racine / preuve["chemin"]).read_bytes()
                self.assertEqual(
                    hashlib.sha256(octets).hexdigest(), preuve["sha256"]
                )

    def test_etat_idempotent_octets_identiques(self):
        code, sortie = self._etat()
        self.assertEqual(0, code, sortie)
        octets = self.chemin_etat.read_bytes()
        code, sortie = self._etat()
        self.assertEqual(0, code, sortie)
        self.assertEqual(octets, self.chemin_etat.read_bytes())

    def test_creneau_sans_preuve_reste_preuve_manquante_jamais_echec(self):
        # grok-build-grok-4-6 perd son reçu de préflight dans la copie :
        # plus aucune preuve ne couvre son créneau
        (
            self.racine
            / _CAMPAGNE
            / "preflights-v1"
            / "grok-build-grok-4-6.json"
        ).unlink()
        code, sortie = self._etat()
        self.assertEqual(0, code, sortie)
        grok = self._creneaux()["grok-build-grok-4-6"]
        self.assertFalse(grok["couvert"])
        self.assertIsNone(grok["decision"])
        self.assertEqual("PREUVE_MANQUANTE", grok["cause"])
        lignes = [
            ligne
            for ligne in sortie.splitlines()
            if "grok-build-grok-4-6" in ligne
        ]
        self.assertTrue(any("preuve manquante" in ligne for ligne in lignes))
        self.assertFalse(
            any("CANDIDATE_NOT_ACCEPTABLE" in ligne for ligne in lignes)
        )
        self.assertFalse(any("FAIL" in ligne for ligne in lignes))

    def test_restitution_affiche_etat_et_couverture_litteralement(self):
        code, sortie = self._etat()
        self.assertEqual(0, code, sortie)
        self.assertEqual(0, M.principal(["restituer"], racine=self.racine))
        page = self.page.read_text(encoding="utf-8")
        self.assertIn('data-couverture-v1="section"', page)
        self.assertIn("2/7", page)
        for ident in _PANEL:
            self.assertIn(f'data-couverture-creneau="{ident}"', page)
        self.assertIn("MISSING_OBSERVATION", page)
        self.assertIn("CANDIDATE_NOT_ACCEPTABLE", page)
        self.assertEqual(
            0, M.principal(["verifier-restitution"], racine=self.racine)
        )

    def test_restitution_porte_le_canon_exact_de_couverture(self):
        code, _ = self._etat()
        self.assertEqual(0, code)
        self.assertEqual(0, M.principal(["restituer"], racine=self.racine))
        page = self.page.read_text(encoding="utf-8")
        # Canon exact du contrat, valeurs attendues indépendantes 2/7
        self.assertIn(
            "Panel abonnement : 2 décisions disponibles sur 7 ; "
            "aucune sortie officiellement acceptable",
            page,
        )
        # Les formulations globales devenues fausses ont disparu
        self.assertNotIn("panel déclaré, aucune mesure", page)
        self.assertNotIn(
            "panel: 7 configurations déclarées, non mesurées", page
        )
        self.assertNotIn("aucune n'est mesurée", page)
        # Le marquage des cinq configurations sans observation est conservé
        self.assertEqual(
            5,
            page.count(
                'non couvert : cause prouvée <code>MISSING_OBSERVATION</code>'
            ),
        )
        self.assertEqual(
            2,
            page.count("couvert : décision <code>CANDIDATE_NOT_ACCEPTABLE</code>"),
        )
        self.assertEqual(
            0, M.principal(["verifier-restitution"], racine=self.racine)
        )

    def test_lot_humain_vide_reste_un_cas_valide(self):
        # L'arbre réel porte le gel du lot éligible vide : aucune sortie
        # PASS, aucune intervention humaine, aucune révélation
        code, sortie = self._etat()
        self.assertEqual(0, code, sortie)
        self.assertIn(
            "- revue humaine : lot éligible vide — 0 verdict humain "
            "requis, aucune intervention du relecteur",
            sortie,
        )
        self.assertEqual(0, M.principal(["restituer"], racine=self.racine))
        self.assertEqual(
            0, M.principal(["verifier-restitution"], racine=self.racine)
        )

    def test_canon_refuse_une_sortie_officiellement_acceptable(self):
        code, _ = self._etat()
        self.assertEqual(0, code)
        contenu = json.loads(self.chemin_etat.read_text(encoding="utf-8"))
        antigravity = next(
            creneau
            for creneau in contenu["couverture"]["creneaux"]
            if creneau["configuration_id"] == "antigravity-gemini-3-7-flash"
        )
        antigravity["decision"] = "OFFICIALLY_ACCEPTABLE"
        self.chemin_etat.write_bytes(M.octets_canoniques(contenu))
        avec_contexte = io.StringIO()
        with contextlib.redirect_stdout(avec_contexte):
            code = M.principal(["restituer"], racine=self.racine)
        self.assertEqual(1, code)
        self.assertIn(
            "sortie officiellement acceptable présente", avec_contexte.getvalue()
        )

    def test_verifier_restitution_detecte_conversion_dans_la_couverture(self):
        code, sortie = self._etat()
        self.assertEqual(0, code, sortie)
        self.assertEqual(0, M.principal(["restituer"], racine=self.racine))
        page = self.page.read_text(encoding="utf-8")

        def verifier() -> tuple[int, str]:
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                code = M.principal(["verifier-restitution"], racine=self.racine)
            return code, sortie.getvalue()

        # Conversion de jeton dans la seule section de couverture
        tete, separateur, queue = page.partition('data-couverture-v1="section"')
        self.assertTrue(separateur)
        self.page.write_text(
            tete
            + separateur
            + queue.replace("MISSING_OBSERVATION", "QUOTA_EXHAUSTED", 1),
            encoding="utf-8",
        )
        code, sortie = verifier()
        self.assertEqual(1, code)
        self.assertIn("couverture", sortie)
        # Conversion de la fraction exacte
        self.page.write_text(page.replace("2/7", "3/7"), encoding="utf-8")
        code, sortie = verifier()
        self.assertEqual(1, code)
        self.assertIn("couverture", sortie)
        # Restauration : la page fidèle est à nouveau conforme
        self.page.write_text(page, encoding="utf-8")
        code, _ = verifier()
        self.assertEqual(0, code)


class EtatTripletRegistreRecuTests(_ArbrePreuvesReelles, unittest.TestCase):
    """Recoupement fail-closed du triplet {chemin, identifiant, sha256}
    embarqué dans chaque reçu officiel avec le fichier courant du registre."""

    def test_divergence_chemin_refusee_de_facon_nommee(self):
        self._substituer_triplet(
            "antigravity-gemini-3-7-flash",
            chemin=(
                f"{M.REGISTRE_OFFICIEL.as_posix()}/"
                "antigravity-gemini-3-7-flash.renomme.toml"
            ),
        )
        code, sortie = self._etat()
        self.assertEqual(1, code)
        self.assertIn("chemin de configuration divergent", sortie)

    def test_divergence_identifiant_refusee_de_facon_nommee(self):
        self._substituer_triplet(
            "antigravity-gemini-3-7-flash",
            identifiant="claude-code-fable-5",
        )
        code, sortie = self._etat()
        self.assertEqual(1, code)
        self.assertIn("identifiant de configuration divergent", sortie)

    def test_divergence_sha256_refusee_de_facon_nommee(self):
        self._substituer_triplet(
            "antigravity-gemini-3-7-flash",
            sha256="b" * 64,
        )
        code, sortie = self._etat()
        self.assertEqual(1, code)
        self.assertIn(
            "SHA-256 de configuration divergent du fichier courant", sortie
        )

    def test_substitution_refusee_avant_restitution_et_publication(self):
        self._substituer_triplet(
            "antigravity-gemini-3-7-flash",
            identifiant="claude-code-fable-5",
        )
        for arguments in ("restituer", "verifier-restitution"):
            avec_contexte = io.StringIO()
            with contextlib.redirect_stdout(avec_contexte):
                code = M.principal([arguments], racine=self.racine)
            self.assertEqual(1, code, arguments)
            self.assertIn(
                "identifiant de configuration divergent",
                avec_contexte.getvalue(),
            )

    def test_couverture_stockee_divergente_detectee_par_verifier(self):
        code, _ = self._etat()
        self.assertEqual(0, code)
        contenu = json.loads(self.chemin_etat.read_text(encoding="utf-8"))
        couverture = contenu["couverture"]
        antigravity = next(
            creneau
            for creneau in couverture["creneaux"]
            if creneau["configuration_id"] == "antigravity-gemini-3-7-flash"
        )
        antigravity.update(
            couvert=False, decision=None, cause="MISSING_OBSERVATION"
        )
        couverture["numerateur"] = 1
        couverture["fraction"] = "1/7"
        self.chemin_etat.write_bytes(M.octets_canoniques(contenu))
        # La page est rendue depuis la couverture stockée altérée : seule la
        # redérivation indépendante peut détecter la divergence
        self.assertEqual(0, M.principal(["restituer"], racine=self.racine))
        code, sortie = self._verifier()
        self.assertEqual(1, code)
        self.assertIn("couverture stockée divergente", sortie)

    def _verifier(self) -> tuple[int, str]:
        avec_contexte = io.StringIO()
        with contextlib.redirect_stdout(avec_contexte):
            code = M.principal(
                ["verifier-restitution"], racine=self.racine
            )
        return code, avec_contexte.getvalue()


class EtatDoublesLocauxTests(_EtatBase, unittest.TestCase):
    """Doubles locaux valides pour les causes absentes du lot réel."""

    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        for nom in _FICHIERS_PAQUET:
            destination = (
                self.racine / _SOURCES_PAQUET.relative_to(RACINE) / nom
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_SOURCES_PAQUET / nom, destination)
        validateur = self.racine / M.CHEMIN_VALIDATEUR
        validateur.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RACINE / M.CHEMIN_VALIDATEUR, validateur)
        self.chemin_etat = self.racine / M.CHEMIN_ETAT
        self.chemin_etat.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RACINE / M.CHEMIN_ETAT, self.chemin_etat)
        shutil.copytree(
            RACINE / _CAMPAGNE / "registre-panel-v1",
            self.racine / _CAMPAGNE / "registre-panel-v1",
        )
        shutil.copytree(
            RACINE / _CAMPAGNE / "preflights-v1",
            self.racine / _CAMPAGNE / "preflights-v1",
        )
        self.recus = self.racine / _CAMPAGNE / "recus-v1"
        self.recus.mkdir(parents=True, exist_ok=True)
        self.stimulus_sha = hashlib.sha256(
            (self.racine / M.CHEMIN_STIMULUS).read_bytes()
        ).hexdigest()

    def _deposer_recu(self, adresse: str, enveloppe: dict) -> None:
        chemin = self.recus / f"{adresse}.json"
        chemin.write_text(
            json.dumps(enveloppe, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

    def _valider(self) -> tuple[int, str]:
        # Frontière système simulée à un CPython 3.12 concret, à l'identique
        # de la fixture de qualification : le pin de production reste intact
        sortie = io.StringIO()
        with (
            contextlib.redirect_stdout(sortie),
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
            code = M.principal(["valider"], racine=self.racine)
        return code, sortie.getvalue()

    def _reecrire_preflight(self, identifiant: str, **modifications) -> None:
        chemin = (
            self.racine / _CAMPAGNE / "preflights-v1" / f"{identifiant}.json"
        )
        recu = json.loads(chemin.read_text(encoding="utf-8"))
        recu.update(modifications)
        chemin.write_text(
            json.dumps(recu, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

    def test_preflight_quota_exhausted_attribue_couvre_le_creneau(self):
        # Double local : préflight UNAVAILABLE de cause QUOTA_EXHAUSTED,
        # attribution prouvée par le reçu de préflight lui-même
        self._reecrire_preflight(
            "claude-code-fable-5",
            verdict="UNAVAILABLE",
            cause="QUOTA_EXHAUSTED",
            fait=(
                "quota de l'abonnement observé épuisé par les sondes non "
                "génératives : la route n'est pas utilisable"
            ),
        )
        code, sortie = self._etat()
        self.assertEqual(0, code, sortie)
        self.assertIn("QUOTA_EXHAUSTED", sortie)
        fable = self._creneaux()["claude-code-fable-5"]
        self.assertTrue(fable["couvert"])
        self.assertEqual("QUOTA_EXHAUSTED", fable["decision"])
        self.assertIsNone(fable["cause"])
        self.assertEqual("1/7", self._couverture()["fraction"])

    def test_preflight_hold_mentionnant_quota_reste_missing_observation(self):
        # Le fait libre mentionne un quota épuisé sans le prouver : la cause
        # affichée reste la cause réellement prouvée, jamais QUOTA_EXHAUSTED
        chemin = (
            self.racine
            / _CAMPAGNE
            / "preflights-v1"
            / "claude-code-fable-5.json"
        )
        recu = json.loads(chemin.read_text(encoding="utf-8"))
        self._reecrire_preflight(
            "claude-code-fable-5",
            fait=recu["fait"] + " ; le quota semble épuisé, sans observation",
        )
        code, sortie = self._etat()
        self.assertEqual(0, code, sortie)
        self.assertNotIn("QUOTA_EXHAUSTED", sortie)
        fable = self._creneaux()["claude-code-fable-5"]
        self.assertFalse(fable["couvert"])
        self.assertEqual("MISSING_OBSERVATION", fable["cause"])

    def test_preflight_ready_sans_acquisition_reste_preuve_manquante(self):
        # antigravity-gemini-3-7-flash a un préflight READY mais aucun reçu
        # d'acquisition : la preuve de décision manque
        code, sortie = self._etat()
        self.assertEqual(0, code, sortie)
        antigravity = self._creneaux()["antigravity-gemini-3-7-flash"]
        self.assertFalse(antigravity["couvert"])
        self.assertIsNone(antigravity["decision"])
        self.assertEqual("PREUVE_MANQUANTE", antigravity["cause"])
        self.assertEqual("0/7", self._couverture()["fraction"])

    def test_incident_quota_exhausted_sans_attribution_prouvee_refuse(self):
        # Un incident attribuable sans fait attribuable est invalide :
        # refus fail-closed, jamais de conversion ni de réparation
        adresse, enveloppe = _enveloppe_recu(
            "zai-glm-5-3",
            _execution_incident(
                "QUOTA_EXHAUSTED",
                "quota épuisé au lancement du créneau, sans sortie candidate",
            ),
            None,
            self.stimulus_sha,
        )
        self._deposer_recu(adresse, enveloppe)
        code, sortie = self._etat()
        self.assertEqual(1, code)
        self.assertIn("ECHEC", sortie)
        self.assertIn("preuve_attribuable", sortie)

    def test_incident_quota_exhausted_attribue_couvre_le_creneau(self):
        adresse, enveloppe = _enveloppe_recu(
            "zai-glm-5-3",
            _execution_incident(
                "QUOTA_EXHAUSTED",
                "quota de l'abonnement observé épuisé au lancement du "
                "créneau, sans sortie candidate",
                "réponse d'épuisement de quota du client consignée dans "
                "l'espace réel privé",
            ),
            None,
            self.stimulus_sha,
        )
        self._deposer_recu(adresse, enveloppe)
        code, sortie = self._valider()
        self.assertEqual(0, code, sortie)
        code, sortie = self._etat()
        self.assertEqual(0, code, sortie)
        self.assertIn("QUOTA_EXHAUSTED", sortie)
        zai = self._creneaux()["zai-glm-5-3"]
        self.assertTrue(zai["couvert"])
        self.assertEqual("QUOTA_EXHAUSTED", zai["decision"])
        self.assertIsNone(zai["cause"])
        self.assertEqual("1/7", self._couverture()["fraction"])


class EtatChaineVerdictsTests(_EtatBase, unittest.TestCase):
    """Chaîne complète jusqu'au gel : verdicts humains dans la couverture."""

    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        for nom in _FICHIERS_PAQUET:
            destination = (
                self.racine / _SOURCES_PAQUET.relative_to(RACINE) / nom
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_SOURCES_PAQUET / nom, destination)
        validateur = self.racine / M.CHEMIN_VALIDATEUR
        validateur.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RACINE / M.CHEMIN_VALIDATEUR, validateur)
        for relatif in (
            M.CHEMIN_ETAT,
            M.CHEMIN_SOURCES_PLANS,
            *[Path(chemin) for chemin in _SOURCES_AUTORISEES],
        ):
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        self.chemin_etat = self.racine / M.CHEMIN_ETAT
        shutil.copytree(
            RACINE / _CAMPAGNE / "registre-panel-v1",
            self.racine / _CAMPAGNE / "registre-panel-v1",
        )
        shutil.copytree(
            RACINE / _CAMPAGNE / "preflights-v1",
            self.racine / _CAMPAGNE / "preflights-v1",
        )
        self.recus = self.racine / _CAMPAGNE / "recus-v1"
        self.recus.mkdir(parents=True, exist_ok=True)
        self.stimulus_sha = hashlib.sha256(
            (self.racine / M.CHEMIN_STIMULUS).read_bytes()
        ).hexdigest()
        self._prive = tempfile.TemporaryDirectory()
        self.addCleanup(self._prive.cleanup)
        self.privee = Path(self._prive.name)
        self.assertEqual(
            0,
            M.principal(
                ["verrouiller"], racine=self.racine, racine_privee=self.privee
            ),
        )
        self.chemin_manifeste = self.racine / M.CHEMIN_MANIFESTE_DOSSIERS
        self.chemin_revelation = (
            self.racine / M.CHEMIN_REVELATION_CORRESPONDANCE
        )

    def _deposer_et_valider(
        self, identifiant: str, stdout: str, predecesseur: str | None = None
    ) -> str:
        adresse, enveloppe = _enveloppe_recu(
            identifiant,
            _execution_observee(stdout),
            predecesseur,
            self.stimulus_sha,
        )
        chemin = self.recus / f"{adresse}.json"
        chemin.write_text(
            json.dumps(enveloppe, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        sortie = io.StringIO()
        with (
            contextlib.redirect_stdout(sortie),
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
            code = M.principal(["valider"], racine=self.racine)
        self.assertEqual(0, code, sortie.getvalue())
        return adresse

    def _dossiers(self) -> None:
        self.assertEqual(
            0,
            M.principal(
                ["dossiers"], racine=self.racine, racine_privee=self.privee
            ),
        )

    def _saisir(self, item: str, verdict: str, justification: str) -> None:
        saisie = (
            self.racine / M.REPERTOIRE_SAISIE_VERDICTS / f"{item}.json"
        )
        saisie.parent.mkdir(parents=True, exist_ok=True)
        saisie.write_text(
            json.dumps(
                {
                    "schema_version": M.SCHEMA_SAISIE_VERDICT_HUMAIN,
                    "item": item,
                    "verdict": verdict,
                    "justification": justification,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def _geler(self) -> tuple[int, str]:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = M.principal(
                ["geler"], racine=self.racine, racine_privee=self.privee
            )
        return code, sortie.getvalue()

    def test_verdicts_humains_unable_to_judge_et_acceptable(self):
        adresse = self._deposer_et_valider(
            "zai-glm-5-3", _sortie_acceptable()
        )
        self._deposer_et_valider(
            "antigravity-gemini-3-7-flash",
            _sortie_acceptable(),
            predecesseur=adresse,
        )
        self._dossiers()
        manifeste = json.loads(
            self.chemin_manifeste.read_text(encoding="utf-8")
        )
        dossiers = manifeste["dossiers"]
        self.assertEqual(2, len(dossiers))
        self._saisir(
            dossiers[0]["item"],
            "UNABLE_TO_JUDGE",
            "Le dossier ne permet pas de trancher pour cet item",
        )
        self._saisir(
            dossiers[1]["item"],
            "ACCEPTABLE",
            "Le pré-cadrage est utilisable tel quel pour cet item",
        )
        code, sortie = self._geler()
        self.assertEqual(0, code, sortie)
        revelation = json.loads(
            self.chemin_revelation.read_text(encoding="utf-8")
        )
        par_config = {
            entree["configuration_id"]: entree
            for entree in revelation["etats_officiels"]
        }

        code, sortie = self._etat()
        self.assertEqual(0, code, sortie)
        self.assertIn("UNABLE_TO_JUDGE", sortie)
        creneaux = self._creneaux()
        for ident, entree in par_config.items():
            if entree["etat_officiel"] == "UNABLE_TO_JUDGE":
                self.assertFalse(creneaux[ident]["couvert"], ident)
                self.assertEqual("UNABLE_TO_JUDGE", creneaux[ident]["cause"])
                self.assertIsNone(creneaux[ident]["decision"])
            else:
                self.assertEqual(
                    "OFFICIALLY_ACCEPTABLE", entree["etat_officiel"]
                )
                self.assertTrue(creneaux[ident]["couvert"], ident)
                self.assertEqual(
                    "OFFICIALLY_ACCEPTABLE", creneaux[ident]["decision"]
                )
        self.assertEqual("1/7", self._couverture()["fraction"])


class EtatRederivationRevelationTests(_EtatBase, unittest.TestCase):
    """Redérivation indépendante des états révélés dans le chemin etat."""

    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        for nom in _FICHIERS_PAQUET:
            destination = (
                self.racine / _SOURCES_PAQUET.relative_to(RACINE) / nom
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_SOURCES_PAQUET / nom, destination)
        validateur = self.racine / M.CHEMIN_VALIDATEUR
        validateur.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RACINE / M.CHEMIN_VALIDATEUR, validateur)
        for relatif in (
            M.CHEMIN_ETAT,
            M.CHEMIN_SOURCES_PLANS,
            *[Path(chemin) for chemin in _SOURCES_AUTORISEES],
        ):
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        shutil.copytree(
            RACINE / _CAMPAGNE / "registre-panel-v1",
            self.racine / _CAMPAGNE / "registre-panel-v1",
        )
        shutil.copytree(
            RACINE / _CAMPAGNE / "preflights-v1",
            self.racine / _CAMPAGNE / "preflights-v1",
        )
        self.recus = self.racine / _CAMPAGNE / "recus-v1"
        self.recus.mkdir(parents=True, exist_ok=True)
        self.stimulus_sha = hashlib.sha256(
            (self.racine / M.CHEMIN_STIMULUS).read_bytes()
        ).hexdigest()
        self._prive = tempfile.TemporaryDirectory()
        self.addCleanup(self._prive.cleanup)
        self.privee = Path(self._prive.name)
        self.assertEqual(
            0,
            M.principal(
                ["verrouiller"], racine=self.racine, racine_privee=self.privee
            ),
        )
        self.chemin_manifeste = self.racine / M.CHEMIN_MANIFESTE_DOSSIERS
        self.chemin_revelation = (
            self.racine / M.CHEMIN_REVELATION_CORRESPONDANCE
        )

    def _acquerir_valider_dossiers_geler(self) -> None:
        adresse, enveloppe = _enveloppe_recu(
            "zai-glm-5-3",
            _execution_observee(_sortie_acceptable()),
            None,
            self.stimulus_sha,
        )
        (self.recus / f"{adresse}.json").write_text(
            json.dumps(enveloppe, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        sortie = io.StringIO()
        with (
            contextlib.redirect_stdout(sortie),
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
            self.assertEqual(
                0,
                M.principal(["valider"], racine=self.racine),
                sortie.getvalue(),
            )
        avec_contexte = io.StringIO()
        with contextlib.redirect_stdout(avec_contexte):
            self.assertEqual(
                0,
                M.principal(
                    ["dossiers"], racine=self.racine, racine_privee=self.privee
                ),
                avec_contexte.getvalue() + "<SORTIE>" + sortie.getvalue(),
            )
        manifeste = json.loads(self.chemin_manifeste.read_text(encoding="utf-8"))
        item = manifeste["dossiers"][0]["item"]
        saisie = self.racine / M.REPERTOIRE_SAISIE_VERDICTS / f"{item}.json"
        saisie.parent.mkdir(parents=True, exist_ok=True)
        saisie.write_text(
            json.dumps(
                {
                    "schema_version": M.SCHEMA_SAISIE_VERDICT_HUMAIN,
                    "item": item,
                    "verdict": "ACCEPTABLE",
                    "justification": "Le dossier permet de trancher",
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        avec_contexte = io.StringIO()
        with contextlib.redirect_stdout(avec_contexte):
            self.assertEqual(
                0,
                M.principal(
                    ["geler"], racine=self.racine, racine_privee=self.privee
                ),
            )

    def test_etat_refuse_etat_revele_divergent_de_sa_rederivation(self):
        self._acquerir_valider_dossiers_geler()
        revelation = json.loads(
            self.chemin_revelation.read_text(encoding="utf-8")
        )
        for entree in revelation["etats_officiels"]:
            if entree["etat_officiel"] == "OFFICIALLY_ACCEPTABLE":
                entree["etat_officiel"] = "CANDIDATE_NOT_ACCEPTABLE"
        self.chemin_revelation.write_bytes(M.octets_canoniques(revelation))
        code, sortie = self._etat()
        self.assertEqual(1, code)
        self.assertIn(
            "états officiels de la révélation divergents", sortie
        )


if __name__ == "__main__":
    unittest.main()
