# /// script
# requires-python = ">=3.12"
# ///
"""Contrôles XS-04 : harnais local borné et reçu V1 abonnement append-only."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE / "tools"))

import campagne_v1 as M  # noqa: E402

from tests._helpers_v1 import retirer_couverture_publiee  # noqa: E402

CONFIGURATION_LOCALE = (
    RACINE
    / "tasks/dev/pre-cadrage-entretien-client/campagne-v1/configurations-locales"
    / "local-system-wc.toml"
)
CHEMIN_STIMULUS = "tasks/dev/pre-cadrage-entretien-client/stimulus.md"
# Taille indépendante du stimulus approuvé : sortie attendue de /usr/bin/wc -c.
OCTETS_STIMULUS = 4273

_SOURCES_RECU = (
    "tasks/dev/pre-cadrage-entretien-client/brief-proprietaire.md",
    "tasks/dev/pre-cadrage-entretien-client/manifeste-paquet.json",
    CHEMIN_STIMULUS,
    M.CHEMIN_ETAT.as_posix(),
)


def _principal(arguments: list[str], racine: Path) -> tuple[int, str]:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = M.principal(arguments, racine=racine)
    return code, sortie.getvalue()


class BaseXS04(unittest.TestCase):
    """Racine isolée : sources du reçu, état V1 et configuration locale."""

    def setUp(self):
        self._temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporaire.cleanup)
        self.racine = Path(self._temporaire.name)
        for relatif in _SOURCES_RECU:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        retirer_couverture_publiee(self.racine / M.CHEMIN_ETAT)
        self.locales = self.racine / M.CONFIGURATIONS_LOCALES
        self.locales.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(
            CONFIGURATION_LOCALE, self.locales / CONFIGURATION_LOCALE.name
        )
        self.recus = (
            self.racine
            / "tasks/dev/pre-cadrage-entretien-client/campagne-v1/recus-v1"
        )

    def _acquerir(self) -> tuple[int, str]:
        return _principal(
            ["acquerir", "--local", "--configuration", "local-system-wc"],
            self.racine,
        )

    def _lire_seul_recu(self) -> tuple[Path, dict]:
        fichiers = sorted(self.recus.glob("*.json"))
        self.assertEqual(len(fichiers), 1, fichiers)
        return fichiers[0], json.loads(fichiers[0].read_text(encoding="utf-8"))


class AcquisitionLocaleTests(BaseXS04):
    def test_succes_local_rend_zero_et_cree_exactement_un_recu(self):
        code, sortie = self._acquerir()
        self.assertEqual(code, 0, sortie)
        chemin, recu = self._lire_seul_recu()
        self.assertEqual(recu["schema_version"], M.SCHEMA_RECU)
        charge = recu["payload"]
        self.assertEqual(charge["measurement_profile"], "subscription")
        execution = charge["execution"]
        self.assertEqual(execution["etat"], "OBSERVED")
        self.assertEqual(execution["code_sortie"], 0)
        # Fait observé indépendant : wc -c compte les octets du stimulus approuvé.
        self.assertEqual(int(execution["sortie"]["stdout"].strip()), OCTETS_STIMULUS)

    def test_recu_porte_les_champs_requis_sans_promotion(self):
        code, sortie = self._acquerir()
        self.assertEqual(code, 0, sortie)
        _, recu = self._lire_seul_recu()
        charge = recu["payload"]
        for nom, relatif in (
            ("carte", "tasks/dev/pre-cadrage-entretien-client/brief-proprietaire.md"),
            ("paquet", "tasks/dev/pre-cadrage-entretien-client/manifeste-paquet.json"),
            ("stimulus", CHEMIN_STIMULUS),
        ):
            source = charge[nom]
            self.assertEqual(source["chemin"], relatif)
            self.assertEqual(
                source["sha256"],
                hashlib.sha256((self.racine / relatif).read_bytes()).hexdigest(),
            )
        configuration = charge["configuration"]
        self.assertEqual(configuration["identifiant"], "local-system-wc")
        self.assertEqual(
            configuration["sha256"],
            hashlib.sha256(CONFIGURATION_LOCALE.read_bytes()).hexdigest(),
        )
        self.assertEqual(charge["plan_declare"]["etat"], "DECLARE")
        self.assertEqual(charge["plan_declare"]["champs"]["prix_montant"], "INCONNU")
        self.assertEqual(charge["interface_declaree"]["champs"]["type"], "cli")
        # INCONNU reste INCONNU : aucune valeur absente n'est promue.
        self.assertEqual(charge["quota_observe"], "INCONNU")
        self.assertEqual(charge["provenance_servie"], "INCONNU")
        requete = charge["requete"]
        self.assertEqual(requete["argv_resolu"], ["/usr/bin/wc", "-c"])
        self.assertEqual(requete["mode_stdin"], "__PROMPT_FILE__")
        self.assertEqual(requete["espace_de_travail"], "__ISOLATED_WORKSPACE__")

    def test_rejouer_le_meme_creneau_rend_un_sans_modifier_le_recu(self):
        code, _ = self._acquerir()
        self.assertEqual(code, 0)
        chemin, _ = self._lire_seul_recu()
        octets_avant = chemin.read_bytes()
        code, sortie = self._acquerir()
        self.assertEqual(code, 1)
        self.assertIn("créneau", sortie)
        self.assertEqual(sorted(self.recus.glob("*.json")), [chemin])
        self.assertEqual(chemin.read_bytes(), octets_avant)

    def test_forme_cli_hors_contrat_rend_deux(self):
        for arguments in (
            ["acquerir"],
            ["acquerir", "--local"],
            ["acquerir", "--configuration", "local-system-wc"],
            ["acquerir", "--local", "--configuration"],
            ["acquerir", "--configuration", "local-system-wc", "--local"],
            ["acquerir", "--local", "--configuration", "local-system-wc", "extra"],
        ):
            with self.subTest(arguments=arguments):
                code, sortie = _principal(arguments, self.racine)
                self.assertEqual(code, 2)
                self.assertIn("usage", sortie)

    def test_configuration_absente_rend_un_et_nomme_la_configuration(self):
        code, sortie = _principal(
            ["acquerir", "--local", "--configuration", "configuration-fantome"],
            self.racine,
        )
        self.assertEqual(code, 1)
        self.assertIn("configuration-fantome", sortie)
        self.assertFalse(self.recus.exists())

    def test_identifiant_traversee_refuse_avant_toute_resolution(self):
        # Cible extérieure au répertoire local, atteignable par traversée : son
        # contenu invalide rendrait toute lecture observable dans le message
        exterieur = self.racine / "tasks/dev/pre-cadrage-entretien-client/exterieur"
        exterieur.mkdir(parents=True)
        (exterieur / "local-system-wc.toml").write_text(
            "contenu TOML invalide {{{", encoding="utf-8"
        )
        for identifiant in (
            "../../exterieur/local-system-wc",
            "/etc/local-system-wc",
            "sous/chemin",
        ):
            with self.subTest(identifiant=identifiant):
                code, sortie = _principal(
                    ["acquerir", "--local", "--configuration", identifiant],
                    self.racine,
                )
                self.assertEqual(code, 1)
                # Le refus vise l'identifiant lui-même, avant toute lecture :
                # aucun chemin de fichier résolu ni trace d'illisibilité de la
                # cible extérieure n'apparaît dans le fait nommé
                self.assertIn(identifiant, sortie)
                self.assertIn("configuration_id", sortie)
                self.assertNotIn("illisible", sortie)
                self.assertNotIn(".toml", sortie)
        self.assertFalse(self.recus.exists())

    def test_acquerir_local_ne_resout_pas_le_registre_officiel(self):
        officiel = self.racine / M.REGISTRE_OFFICIEL
        officiel.mkdir(parents=True)
        shutil.copyfile(
            RACINE / M.REGISTRE_OFFICIEL / "claude-code-fable-5.toml",
            officiel / "claude-code-fable-5.toml",
        )
        code, sortie = _principal(
            ["acquerir", "--local", "--configuration", "claude-code-fable-5"],
            self.racine,
        )
        self.assertEqual(code, 1)
        self.assertIn("claude-code-fable-5", sortie)
        self.assertFalse(self.recus.exists())


def _adresse_selon_convention(charge: dict) -> str:
    """Adresse recalculée depuis la convention canonique documentée."""
    octets = (
        json.dumps(
            charge,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )
    return hashlib.sha256(octets).hexdigest()


class AdressageEtChainageTests(BaseXS04):
    def _seconde_configuration(self, identifiant: str) -> None:
        texte = CONFIGURATION_LOCALE.read_text(encoding="utf-8").replace(
            'configuration_id = "local-system-wc"',
            f'configuration_id = "{identifiant}"',
        )
        (self.locales / f"{identifiant}.toml").write_text(texte, encoding="utf-8")

    def test_adresse_canonique_et_nom_du_fichier(self):
        code, _ = self._acquerir()
        self.assertEqual(code, 0)
        chemin, recu = self._lire_seul_recu()
        adresse = _adresse_selon_convention(recu["payload"])
        self.assertEqual(recu["content_address"], {"algorithm": "SHA256", "sha256": adresse})
        self.assertEqual(chemin.name, f"{adresse}.json")

    def test_premier_recu_null_puis_chainage_au_predecesseur(self):
        code, _ = self._acquerir()
        self.assertEqual(code, 0)
        _, premier = self._lire_seul_recu()
        self.assertIsNone(premier["payload"]["predecesseur_adresse_contenu"])
        self._seconde_configuration("local-system-wc-bis")
        code, sortie = _principal(
            ["acquerir", "--local", "--configuration", "local-system-wc-bis"],
            self.racine,
        )
        self.assertEqual(code, 0, sortie)
        fichiers = sorted(self.recus.glob("*.json"))
        self.assertEqual(len(fichiers), 2)
        seconds = [
            json.loads(fichier.read_text(encoding="utf-8"))
            for fichier in fichiers
        ]
        second = next(
            recu
            for recu in seconds
            if recu["payload"]["predecesseur_adresse_contenu"] is not None
        )
        self.assertEqual(
            second["payload"]["predecesseur_adresse_contenu"],
            premier["content_address"]["sha256"],
        )

    def _alterer_seul_recu(self, transformation) -> Path:
        chemin, recu = self._lire_seul_recu()
        transformation(recu)
        chemin.write_text(
            json.dumps(recu, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return chemin

    def test_refus_adresse_alteree(self):
        self.assertEqual(self._acquerir()[0], 0)

        def alterer(recu):
            recu["content_address"]["sha256"] = "0" * 64

        chemin = self._alterer_seul_recu(alterer)
        chemin.rename(chemin.with_name("0" * 64 + ".json"))
        self._seconde_configuration("local-system-wc-bis")
        code, sortie = _principal(
            ["acquerir", "--local", "--configuration", "local-system-wc-bis"],
            self.racine,
        )
        self.assertEqual(code, 1)
        self.assertIn("adresse", sortie)

    def test_refus_schema_altere(self):
        self.assertEqual(self._acquerir()[0], 0)

        def alterer(recu):
            recu["schema_version"] = "campaign-v0-acquisition-receipt/v1"

        self._alterer_seul_recu(alterer)
        self._seconde_configuration("local-system-wc-bis")
        code, sortie = _principal(
            ["acquerir", "--local", "--configuration", "local-system-wc-bis"],
            self.racine,
        )
        self.assertEqual(code, 1)
        self.assertIn("schema_version", sortie)

    def test_refus_predecesseur_altere(self):
        self.assertEqual(self._acquerir()[0], 0)

        def alterer(recu):
            recu["payload"]["predecesseur_adresse_contenu"] = "f" * 64
            recu["content_address"]["sha256"] = _adresse_selon_convention(
                recu["payload"]
            )

        chemin = self._alterer_seul_recu(alterer)
        recu = json.loads(chemin.read_text(encoding="utf-8"))
        chemin.rename(
            chemin.with_name(recu["content_address"]["sha256"] + ".json")
        )
        self._seconde_configuration("local-system-wc-bis")
        code, sortie = _principal(
            ["acquerir", "--local", "--configuration", "local-system-wc-bis"],
            self.racine,
        )
        self.assertEqual(code, 1)
        self.assertIn("prédécesseur", sortie)


class IncidentsEtEtatsTests(BaseXS04):
    """Vocabulaire incident fermé et refus d'OBSERVED sans preuve locale."""

    def _recrire_seul_recu(self, transformer) -> None:
        """Réécrit le seul reçu avec un payload transformé et une adresse valide."""
        chemin, recu = self._lire_seul_recu()
        transformer(recu["payload"])
        adresse = _adresse_selon_convention(recu["payload"])
        recu["content_address"]["sha256"] = adresse
        chemin.unlink()
        (self.recus / f"{adresse}.json").write_bytes(M.octets_canoniques(recu))

    def _acquerir_apres_recu_prealable(self) -> tuple[int, str]:
        """Couture publique : acquerir valide le répertoire de reçus existant."""
        texte = CONFIGURATION_LOCALE.read_text(encoding="utf-8").replace(
            'configuration_id = "local-system-wc"',
            'configuration_id = "local-system-wc-bis"',
        )
        (self.locales / "local-system-wc-bis.toml").write_text(texte, encoding="utf-8")
        return _principal(
            ["acquerir", "--local", "--configuration", "local-system-wc-bis"],
            self.racine,
        )

    def _executions_incident(self) -> dict[str, dict]:
        return {
            "PROVIDER_FAILURE": {
                "etat": "INCIDENT",
                "incident": "PROVIDER_FAILURE",
                "fait": "échec d'opération attribué au fournisseur",
                "preuve_attribuable": "réponse d'erreur signée conservée au reçu",
            },
            "HARNESS_ERROR": {
                "etat": "INCIDENT",
                "incident": "HARNESS_ERROR",
                "fait": "échec local du harnais : lancement impossible",
            },
            "IDENTITY_MISMATCH": {
                "etat": "INCIDENT",
                "incident": "IDENTITY_MISMATCH",
                "fait": "identité servie en conflit avec le verrou",
                "preuve_attribuable": "identité servie divergente citée au reçu",
            },
            "MISSING_OBSERVATION": {
                "etat": "INCIDENT",
                "incident": "MISSING_OBSERVATION",
                "fait": "observation obligatoire absente : sortie non capturée",
            },
            "QUOTA_EXHAUSTED": {
                "etat": "INCIDENT",
                "incident": "QUOTA_EXHAUSTED",
                "fait": "refus explicite pour quota épuisé",
                "preuve_attribuable": "réponse de refus de quota citée au reçu",
            },
        }

    def test_les_cinq_incidents_du_vocabulaire_sont_acceptes(self):
        executions = self._executions_incident()
        self.assertEqual(sorted(executions), sorted(M.INCIDENTS_V1))
        for nom, execution in executions.items():
            with self.subTest(incident=nom):
                for fichier in self.recus.glob("*.json") if self.recus.is_dir() else []:
                    fichier.unlink()
                (self.locales / "local-system-wc-bis.toml").unlink(missing_ok=True)
                self.assertEqual(self._acquerir()[0], 0)
                self._recrire_seul_recu(
                    lambda charge, execution=execution: charge.update(
                        {"execution": execution}
                    )
                )
                code, sortie = self._acquerir_apres_recu_prealable()
                self.assertEqual(code, 0, sortie)

    def test_incident_hors_vocabulaire_rend_un_et_nomme_le_fait(self):
        self.assertEqual(self._acquerir()[0], 0)
        self._recrire_seul_recu(
            lambda charge: charge.update(
                {
                    "execution": {
                        "etat": "INCIDENT",
                        "incident": "TIMEOUT_LOCAL",
                        "fait": "état inventé hors vocabulaire",
                    }
                }
            )
        )
        code, sortie = self._acquerir_apres_recu_prealable()
        self.assertEqual(code, 1)
        self.assertIn("hors", sortie)
        self.assertIn("TIMEOUT_LOCAL", sortie)

    def test_incident_attribuable_sans_preuve_est_refuse(self):
        for nom in M.INCIDENTS_ATTRIBUABLES:
            with self.subTest(incident=nom):
                for fichier in self.recus.glob("*.json") if self.recus.is_dir() else []:
                    fichier.unlink()
                (self.locales / "local-system-wc-bis.toml").unlink(missing_ok=True)
                self.assertEqual(self._acquerir()[0], 0)
                self._recrire_seul_recu(
                    lambda charge, nom=nom: charge.update(
                        {
                            "execution": {
                                "etat": "INCIDENT",
                                "incident": nom,
                                "fait": "aucun fait attribuable, simple absence",
                            }
                        }
                    )
                )
                code, sortie = self._acquerir_apres_recu_prealable()
                self.assertEqual(code, 1, sortie)

    def test_refus_quota_observe_sans_preuve(self):
        self.assertEqual(self._acquerir()[0], 0)
        self._recrire_seul_recu(
            lambda charge: charge.update(
                {"quota_observe": {"etat": "OBSERVED", "valeur": 100, "preuve": ""}}
            )
        )
        code, sortie = self._acquerir_apres_recu_prealable()
        self.assertEqual(code, 1)
        self.assertIn("quota_observe", sortie)
        self.assertIn("OBSERVED sans preuve", sortie)

    def test_refus_provenance_servie_promue_sans_preuve(self):
        self.assertEqual(self._acquerir()[0], 0)
        self._recrire_seul_recu(
            lambda charge: charge.update(
                {"provenance_servie": {"etat": "OBSERVED", "valeur": "wc", "preuve": ""}}
            )
        )
        code, sortie = self._acquerir_apres_recu_prealable()
        self.assertEqual(code, 1)
        self.assertIn("provenance_servie", sortie)

    def test_refus_execution_observee_sans_capture(self):
        self.assertEqual(self._acquerir()[0], 0)
        self._recrire_seul_recu(
            lambda charge: charge.update(
                {"execution": {"etat": "OBSERVED", "code_sortie": 0, "latence_ms": 1}}
            )
        )
        code, sortie = self._acquerir_apres_recu_prealable()
        self.assertEqual(code, 1)
        self.assertIn("execution", sortie)

    def test_commande_introuvable_produit_un_recu_harness_error(self):
        texte = CONFIGURATION_LOCALE.read_text(encoding="utf-8").replace(
            'argv = ["/usr/bin/wc", "-c"]',
            'argv = ["/chemin/inexistant/aucun-binaire"]',
        )
        (self.locales / "local-system-wc.toml").write_text(texte, encoding="utf-8")
        code, sortie = self._acquerir()
        self.assertEqual(code, 0, sortie)
        self.assertIn("HARNESS_ERROR", sortie)
        _, recu = self._lire_seul_recu()
        execution = recu["payload"]["execution"]
        self.assertEqual(execution["etat"], "INCIDENT")
        self.assertEqual(execution["incident"], "HARNESS_ERROR")
        self.assertIn("lancement", execution["fait"])


FIXTURE_DESCENDANT = (
    RACINE / "tests/fixtures/campagne-v1/harnais/descendant-dort.sh"
)


class TimeoutGroupeTests(BaseXS04):
    """Au délai, le groupe de processus entier disparaît, descendants compris."""

    def test_timeout_tue_le_groupe_et_le_descendant_consigne_disparait(self):
        fichier_pid = self.racine / "descendant.pid"
        texte = CONFIGURATION_LOCALE.read_text(encoding="utf-8").replace(
            'argv = ["/usr/bin/wc", "-c"]',
            f'argv = ["/bin/sh", "{FIXTURE_DESCENDANT}", "{fichier_pid}"]',
        ).replace("delai_secondes = 30", "delai_secondes = 1")
        (self.locales / "local-system-wc.toml").write_text(texte, encoding="utf-8")
        code, sortie = self._acquerir()
        self.assertEqual(code, 0, sortie)
        _, recu = self._lire_seul_recu()
        execution = recu["payload"]["execution"]
        self.assertEqual(execution["etat"], "INCIDENT")
        self.assertEqual(execution["incident"], "HARNESS_ERROR")
        self.assertIn("délai", execution["fait"])
        self.assertIn("groupe", execution["fait"])
        # La fixture a consigné le PID de son descendant avant le délai.
        pid = int(fichier_pid.read_text(encoding="utf-8").strip())
        # La disparition du seul parent ne suffit pas : le PID descendant
        # lui-même ne doit plus exister après la terminaison du groupe.
        limite = time.monotonic() + 5.0
        vivant = True
        while time.monotonic() < limite:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                vivant = False
                break
            time.sleep(0.05)
        self.assertFalse(vivant, f"descendant {pid} encore vivant après timeout")


class FrontiereReseauTests(BaseXS04):
    """Le chemin public XS-04 n'appelle aucune primitive de connexion."""

    def test_acquerir_sans_primitive_de_connexion(self):
        import socket
        from unittest import mock

        def primitive_interdite(*args, **kwargs):
            raise AssertionError(
                "primitive de connexion appelée sur le chemin public acquerir"
            )

        with (
            mock.patch.object(socket, "socket", primitive_interdite),
            mock.patch.object(socket, "create_connection", primitive_interdite),
            mock.patch.object(socket, "getaddrinfo", primitive_interdite),
        ):
            code, sortie = self._acquerir()
            self.assertEqual(code, 0, sortie)


_SOURCES_RESTITUTION = tuple(chemin for chemin, _ in M.SOURCES_AUTORISEES) + (
    M.CHEMIN_ETAT.as_posix(),
)


class RestitutionLocaleTests(BaseXS04):
    """Section HTML d'acquisition locale, fidèle au reçu et hors panel officiel."""

    def setUp(self):
        super().setUp()
        for relatif in _SOURCES_RESTITUTION:
            destination = self.racine / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RACINE / relatif, destination)
        retirer_couverture_publiee(self.racine / M.CHEMIN_ETAT)
        shutil.copytree(
            RACINE / M.REGISTRE_OFFICIEL, self.racine / M.REGISTRE_OFFICIEL
        )
        self.page = self.racine / M.CHEMIN_PAGE

    def _restituer(self) -> str:
        code, sortie = _principal(["restituer"], self.racine)
        self.assertEqual(code, 0, sortie)
        return self.page.read_text(encoding="utf-8")

    def test_section_locale_fidele_au_recu_et_hors_panel_officiel(self):
        self.assertEqual(self._acquerir()[0], 0)
        chemin_recu, recu = self._lire_seul_recu()
        page = self._restituer()
        self.assertIn('<section id="acquisition-locale">', page)
        self.assertIn("hors panel officiel", page)
        relatif = chemin_recu.relative_to(self.racine).as_posix()
        empreinte_fichier = hashlib.sha256(chemin_recu.read_bytes()).hexdigest()
        self.assertIn(relatif, page)
        self.assertIn(empreinte_fichier, page)
        self.assertIn(recu["content_address"]["sha256"], page)
        self.assertIn(recu["payload"]["creneau"], page)
        self.assertIn("subscription", page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_section_locale_ne_change_aucune_conclusion_du_panel(self):
        self.assertEqual(self._acquerir()[0], 0)
        page = self._restituer()
        # Les conclusions du panel abonnement restent inchangées.
        self.assertIn("acquisitions: 0", page)
        self.assertIn("conclusion: ABSTENTION", page)
        self.assertIn("panel: 7 configurations déclarées, non mesurées", page)
        self.assertEqual(page.count('data-statut="declaree-non-mesuree"'), 7)
        # La section locale se déclare hors panel et sans classement ; elle ne
        # produit ni gagnant, ni recommandation, ni acquisition officielle.
        section = page.split('<section id="acquisition-locale">')[1].split(
            "</section>"
        )[0]
        self.assertIn("hors panel officiel", section)
        self.assertIn("ne classe aucune configuration", section)
        for interdit in ("classement", "gagnant", "recommand", "officielle validée"):
            self.assertNotIn(interdit, section.lower())

    def test_sans_recu_local_la_page_reste_identique_a_l_existant(self):
        page = self._restituer()
        self.assertNotIn('<section id="acquisition-locale">', page)
        # Sans reçu local, les formulations d'absence historiques demeurent
        self.assertIn("Aucun reçu V1 n'existe", page)
        self.assertIn("zéro reçu dans le répertoire de reçus V1", page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_page_avec_recu_local_qualifie_la_portee_officielle(self):
        self.assertEqual(self._acquerir()[0], 0)
        chemin_recu, _ = self._lire_seul_recu()
        page = self._restituer()
        # Plus d'affirmation littérale d'absence sans portée qualifiée
        for interdit in (
            "Aucun reçu V1 n'existe",
            "zéro reçu dans le répertoire",
            "aucune acquisition n'existe",
            "aucune acquisition et aucune mesure n'existe",
        ):
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, page)
        # La section vocabulaire remplace l'affirmation non qualifiée par un
        # fait MSW classé : exécution OBSERVED prouvée par le reçu local
        # versionné, hors panel officiel, panel officiel non mesuré
        vocabulaire = page.split('<section id="vocabulaire">', 1)[1].split(
            "</section>", 1
        )[0]
        self.assertNotIn("la V1 n'a rien observé", vocabulaire)
        self.assertIn("OBSERVED", vocabulaire)
        self.assertIn("hors panel officiel", vocabulaire)
        self.assertIn("non mesuré", vocabulaire)
        self.assertIn('data-classe="fait"', vocabulaire)
        relatif = chemin_recu.relative_to(self.racine).as_posix()
        empreinte_fichier = hashlib.sha256(chemin_recu.read_bytes()).hexdigest()
        self.assertIn(
            f'data-chemin="{relatif}" data-sha256="{empreinte_fichier}"',
            vocabulaire,
        )
        # Le reçu local est distingué de l'absence rattachée au panel officiel
        self.assertIn("aucune acquisition officielle", page)
        self.assertIn("aucun reçu rattaché au panel officiel", page)
        self.assertIn("Aucun reçu V1 rattaché au panel officiel n'existe", page)
        # ABSTENTION du panel et jetons normatifs préservés
        self.assertIn("conclusion: ABSTENTION", page)
        self.assertIn("acquisitions: 0", page)
        self.assertIn("NON_DEFINI", page)
        self.assertIn("INCONNU", page)
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_restitutions_successives_byte_identiques_avec_recu_local(self):
        self.assertEqual(self._acquerir()[0], 0)
        premiere = self._restituer()
        self.assertEqual(premiere, self._restituer())

    def test_verifier_refuse_un_recu_altere_apres_restitution(self):
        self.assertEqual(self._acquerir()[0], 0)
        self._restituer()
        chemin_recu, _ = self._lire_seul_recu()
        chemin_recu.write_bytes(chemin_recu.read_bytes() + b" ")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)

    def test_verifier_refuse_une_section_locale_alteree(self):
        self.assertEqual(self._acquerir()[0], 0)
        _, recu = self._lire_seul_recu()
        page = self._restituer()
        alteree = page.replace(recu["payload"]["creneau"], "creneau-invente", 1)
        self.assertNotEqual(alteree, page)
        self.page.write_text(alteree, encoding="utf-8")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)
        self.page.write_text(page, encoding="utf-8")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)

    def test_verifier_refuse_une_acquisition_locale_injectee(self):
        self.assertEqual(self._acquerir()[0], 0)
        page = self._restituer()
        self.page.write_text(
            page.replace(
                "</body>",
                '<article class="affirmation" data-classe="fait" '
                'data-acquisition-locale="injectee"><p>reçu inventé</p></article></body>',
            ),
            encoding="utf-8",
        )
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)

    def test_recu_invalide_dans_le_repertoire_reste_refuse(self):
        self._restituer()
        self.recus.mkdir(parents=True, exist_ok=True)
        (self.recus / "recu.json").write_text("{}", encoding="utf-8")
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 1, sortie)

    def test_les_sept_configurations_officielles_restent_byte_identiques(self):
        self.assertEqual(self._acquerir()[0], 0)
        self._restituer()
        code, sortie = _principal(["verifier-restitution"], self.racine)
        self.assertEqual(code, 0, sortie)
        copies = sorted((self.racine / M.REGISTRE_OFFICIEL).glob("*.toml"))
        self.assertEqual(len(copies), 7)
        for copie in copies:
            original = RACINE / M.REGISTRE_OFFICIEL / copie.name
            self.assertEqual(copie.read_bytes(), original.read_bytes())


if __name__ == "__main__":
    unittest.main()
