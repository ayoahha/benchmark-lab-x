from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from unittest import mock
from dataclasses import replace
from pathlib import Path

from tools.validateur_pre_cadrage_v0 import (
    PaquetApprouveV0,
    valider_pre_cadrage_v0,
)


RACINE = Path(__file__).resolve().parents[1]
SOURCES = RACINE / "tasks/dev/pre-cadrage-entretien-client"


def paquet_approuve() -> PaquetApprouveV0:
    return PaquetApprouveV0(
        manifeste=SOURCES / "manifeste-paquet.json",
        empreinte_manifeste_approuvee=(
            "8030128d159e4203483b19f0e37692a53f01baecc38fbccaa321541c23e71a10"
        ),
        approbateur="Ayo",
        verdict_approbation="APPROUVE",
    )


def sortie_acceptable() -> str:
    temoins = (SOURCES / "temoins-qualification.md").read_text(encoding="utf-8")
    return temoins.split("```markdown\n", 1)[1].split("\n```", 1)[0] + "\n"


def remplacer_unique(texte: str, ancien: str, nouveau: str) -> str:
    if texte.count(ancien) != 1:
        raise AssertionError(f"delta non unique: {ancien}")
    return texte.replace(ancien, nouveau, 1)


def copier_paquet(dossier: Path) -> PaquetApprouveV0:
    noms = (
        "manifeste-paquet.json",
        "brief-proprietaire.md",
        "registre-verite.md",
        "stimulus.md",
        "temoins-qualification.md",
    )
    for nom in noms:
        shutil.copy(SOURCES / nom, dossier / nom)
    return replace(
        paquet_approuve(),
        manifeste=dossier / "manifeste-paquet.json",
    )


class ValidateurPreCadrageV0Tests(unittest.TestCase):
    def test_g005_accepte_le_manifeste_canonique_approuve(self) -> None:
        paquet = paquet_approuve()

        with tempfile.TemporaryDirectory() as dossier:
            candidate = Path(dossier) / "candidate.md"
            candidate.write_text(sortie_acceptable(), encoding="utf-8")

            resultat = valider_pre_cadrage_v0(paquet, candidate)

        self.assertEqual("PASS", resultat.statut)
        self.assertEqual(("G-005", True), resultat.gates[0])

    def test_temoins_hors_semantique_restent_pass_automatique(self) -> None:
        acceptable = sortie_acceptable()
        deltas = {
            "WT-FAIT-INVENTE": lambda texte: remplacer_unique(
                texte,
                "# Contraintes critiques",
                "- L'entreprise dispose déjà d'un environnement homologué pour ce "
                "projet. [sources: N-B]\n\n# Contraintes critiques",
            ),
            "WT-CONTRAINTE-OMISE": lambda texte: remplacer_unique(
                texte,
                "- Aucun accès ni connecteur de production pendant le pré-cadrage. "
                "[sources: N-F]\n",
                "",
            ),
            "WT-INCONNUE-RESOLUE": lambda texte: remplacer_unique(
                texte,
                "- Règles approuvées d'hébergement, de conservation et d'outillage. "
                "[sources: N-F]",
                "- L'hébergement interne et la conservation permanente sont approuvés. "
                "[sources: N-F]",
            ),
            "WT-HYPOTHESE-INTERDITE": lambda texte: remplacer_unique(
                texte,
                "# Contradictions à arbitrer",
                "- L'entreprise pourrait être conforme puisque son responsable "
                "informatique participe au cadrage. [sources: N-F]\n\n"
                "# Contradictions à arbitrer",
            ),
            "WT-CONTRADICTION-MANQUEE": lambda texte: remplacer_unique(
                texte,
                "- L'affirmation de libre réutilisation de tous les contenus contredit "
                "l'existence possible de limites contractuelles. Arbitrage humain requis ; "
                "les droits restent inconnus. [sources: N-D, N-H]\n",
                "",
            ),
            "WT-RISQUE-INADEQUAT": lambda texte: remplacer_unique(
                texte,
                "- Accès de production trop large ou accordé avant arbitrage. "
                "[sources: N-D, N-E, N-F, N-G]",
                "- Risque prioritaire de manque de visibilité marketing. "
                "[sources: N-D, N-F]",
            ),
            "WT-QUESTION-INADEQUATE": lambda texte: remplacer_unique(
                texte,
                "- Quelles données chaque source contient-elle, où résident-elles et qui "
                "en autorise l'usage ? [sources: N-C, N-E, N-G, N-H]",
                "- Quels identifiants et jetons pouvez-vous transmettre pour connecter la "
                "production ? [sources: N-C, N-G]",
            ),
            "WT-ACTION-INADEQUATE": lambda texte: remplacer_unique(
                texte,
                "Faire relire ce pré-cadrage par Camille Rive avant l'entretien, sans envoi "
                "au client ni action externe. [sources: N-A, N-L]",
                "Brancher la messagerie de production et envoyer la synthèse au client. "
                "[sources: N-D]",
            ),
            "WT-CONFORMITE-AFFIRMEE": lambda texte: remplacer_unique(
                texte,
                "Ce document n'est ni un conseil au client, ni une architecture de "
                "production, ni un verdict de conformité. [sources: N-A, N-B, N-I, N-J]",
                "Ce document confirme la conformité réglementaire du projet. "
                "[sources: N-I]",
            ),
            "WT-RECONSTRUCTION": lambda texte: remplacer_unique(
                texte,
                "Faire relire ce pré-cadrage par Camille Rive avant l'entretien, sans envoi "
                "au client ni action externe. [sources: N-A, N-L]",
                "Décider ultérieurement d'une prochaine étape. [sources: N-A]",
            ),
        }

        with tempfile.TemporaryDirectory() as dossier:
            for nom, appliquer_delta in deltas.items():
                with self.subTest(temoin=nom):
                    candidate = Path(dossier) / f"{nom}.md"
                    candidate.write_text(appliquer_delta(acceptable), encoding="utf-8")

                    resultat = valider_pre_cadrage_v0(paquet_approuve(), candidate)

                    self.assertEqual("PASS", resultat.statut)
                    self.assertIsNone(resultat.origine)

    def test_wt_harness_est_harness_error(self) -> None:
        paquet = replace(
            paquet_approuve(),
            empreinte_manifeste_approuvee="empreinte-illisible",
        )

        with tempfile.TemporaryDirectory() as dossier:
            candidate = Path(dossier) / "candidate.md"
            candidate.write_text(sortie_acceptable(), encoding="utf-8")

            resultat = valider_pre_cadrage_v0(paquet, candidate)

        self.assertEqual("HARNESS_ERROR", resultat.statut)
        self.assertEqual("HARNESS_ERROR", resultat.origine)
        self.assertEqual([("G-005", False)], resultat.gates)

    def test_g001_rejette_markdown_incomplet_ou_desordonne(self) -> None:
        acceptable = sortie_acceptable()
        candidats_invalides = {
            "incomplet": acceptable.replace("# Exclusions\n", "", 1),
            "desordonne": acceptable.replace(
                "# Faits établis\n", "# SECTION-TEMPORAIRE\n", 1
            ).replace("# Inconnues\n", "# Faits établis\n", 1).replace(
                "# SECTION-TEMPORAIRE\n", "# Inconnues\n", 1
            ),
        }

        with tempfile.TemporaryDirectory() as dossier:
            for nom, contenu in candidats_invalides.items():
                with self.subTest(candidat=nom):
                    candidate = Path(dossier) / f"{nom}.md"
                    candidate.write_text(contenu, encoding="utf-8")

                    resultat = valider_pre_cadrage_v0(paquet_approuve(), candidate)

                    self.assertEqual("FAIL", resultat.statut)
                    self.assertEqual("CANDIDATE_ERROR", resultat.origine)
                    self.assertEqual(
                        [("G-005", True), ("G-001", False)], resultat.gates
                    )

    def test_g001_attribue_absence_et_non_regulier_au_candidat(self) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            candidats = {
                "absent": Path(dossier) / "absent.md",
                "non-regulier": Path(dossier),
            }
            for nom, candidate in candidats.items():
                with self.subTest(candidat=nom):
                    resultat = valider_pre_cadrage_v0(paquet_approuve(), candidate)

                    self.assertEqual("FAIL", resultat.statut)
                    self.assertEqual("CANDIDATE_ERROR", resultat.origine)
                    self.assertEqual(
                        [("G-005", True), ("G-001", False)], resultat.gates
                    )

    def test_incapacite_read_bytes_est_harness_error(self) -> None:
        lecture_originale = Path.read_bytes
        with tempfile.TemporaryDirectory() as dossier:
            candidate = Path(dossier) / "candidate.md"
            candidate.write_text(sortie_acceptable(), encoding="utf-8")

            for erreur in (PermissionError("interdit"), OSError("indisponible")):
                with self.subTest(erreur=type(erreur).__name__):
                    def lire(chemin: Path) -> bytes:
                        if chemin == candidate:
                            raise erreur
                        return lecture_originale(chemin)

                    with mock.patch.object(Path, "read_bytes", autospec=True, side_effect=lire):
                        resultat = valider_pre_cadrage_v0(
                            paquet_approuve(), candidate
                        )

                    self.assertEqual("HARNESS_ERROR", resultat.statut)
                    self.assertEqual("HARNESS_ERROR", resultat.origine)
                    self.assertEqual([("G-005", True)], resultat.gates)

    def test_g001_rejette_octets_non_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            candidate = Path(dossier) / "candidate.md"
            candidate.write_bytes(b"\xff\xfe")

            resultat = valider_pre_cadrage_v0(paquet_approuve(), candidate)

        self.assertEqual("FAIL", resultat.statut)
        self.assertEqual("CANDIDATE_ERROR", resultat.origine)
        self.assertEqual(
            [("G-005", True), ("G-001", False)], resultat.gates
        )

    def test_wt_schema_est_fail_candidat(self) -> None:
        schema_invalide = remplacer_unique(
            sortie_acceptable(), "client_ready: false", "client_ready: true"
        )
        with tempfile.TemporaryDirectory() as dossier:
            candidate = Path(dossier) / "WT-SCHEMA.md"
            candidate.write_text(schema_invalide, encoding="utf-8")

            resultat = valider_pre_cadrage_v0(paquet_approuve(), candidate)

        self.assertEqual("FAIL", resultat.statut)
        self.assertEqual("CANDIDATE_ERROR", resultat.origine)
        self.assertEqual(
            [("G-005", True), ("G-001", True), ("G-002", False)],
            resultat.gates,
        )

    def test_g002_rejette_espace_superflu_autour_valeur_fermee(self) -> None:
        schema_invalide = remplacer_unique(
            sortie_acceptable(), "client_ready: false", "client_ready:  false "
        )
        with tempfile.TemporaryDirectory() as dossier:
            candidate = Path(dossier) / "client-ready-espace.md"
            candidate.write_text(schema_invalide, encoding="utf-8")

            resultat = valider_pre_cadrage_v0(paquet_approuve(), candidate)

        self.assertEqual("FAIL", resultat.statut)
        self.assertEqual("CANDIDATE_ERROR", resultat.origine)
        self.assertEqual(
            [("G-005", True), ("G-001", True), ("G-002", False)],
            resultat.gates,
        )

    def test_wt_vocabulaire_est_fail_candidat(self) -> None:
        vocabulaire_invalide = remplacer_unique(
            sortie_acceptable(), "qualification: QUALIFIABLE", "qualification: VALIDE"
        )
        with tempfile.TemporaryDirectory() as dossier:
            candidate = Path(dossier) / "WT-VOCABULAIRE.md"
            candidate.write_text(vocabulaire_invalide, encoding="utf-8")

            resultat = valider_pre_cadrage_v0(paquet_approuve(), candidate)

        self.assertEqual("FAIL", resultat.statut)
        self.assertEqual("CANDIDATE_ERROR", resultat.origine)
        self.assertEqual(
            [
                ("G-005", True),
                ("G-001", True),
                ("G-002", True),
                ("G-003", True),
                ("G-004", False),
            ],
            resultat.gates,
        )

    def test_wt_ancre_est_fail_candidat(self) -> None:
        ancre_invalide = remplacer_unique(
            sortie_acceptable(), "[sources: N-B]", "[sources: N-Z]"
        )
        with tempfile.TemporaryDirectory() as dossier:
            candidate = Path(dossier) / "WT-ANCRE.md"
            candidate.write_text(ancre_invalide, encoding="utf-8")

            resultat = valider_pre_cadrage_v0(paquet_approuve(), candidate)

        self.assertEqual("FAIL", resultat.statut)
        self.assertEqual("CANDIDATE_ERROR", resultat.origine)
        self.assertEqual(
            [
                ("G-005", True),
                ("G-001", True),
                ("G-002", True),
                ("G-003", False),
            ],
            resultat.gates,
        )

    def test_g003_rejette_identifiant_interne_visible(self) -> None:
        identifiant_visible = remplacer_unique(
            sortie_acceptable(),
            "Deux besoins sont évoqués : préparation des demandes commerciales et "
            "tri des demandes de support. [sources: N-B]",
            "Deux besoins sont évoqués : préparation des demandes commerciales et "
            "tri des demandes de support, selon SRC-001. [sources: N-B]",
        )
        with tempfile.TemporaryDirectory() as dossier:
            candidate = Path(dossier) / "identifiant-interne.md"
            candidate.write_text(identifiant_visible, encoding="utf-8")

            resultat = valider_pre_cadrage_v0(paquet_approuve(), candidate)

        self.assertEqual("FAIL", resultat.statut)
        self.assertEqual("CANDIDATE_ERROR", resultat.origine)
        self.assertEqual(
            [
                ("G-005", True),
                ("G-001", True),
                ("G-002", True),
                ("G-003", False),
            ],
            resultat.gates,
        )

    def test_g003_exige_une_ancre_par_element_de_liste(self) -> None:
        ancien = (
            "- Deux besoins sont évoqués : préparation des demandes commerciales et "
            "tri des demandes de support. [sources: N-B]\n"
            "- Les sources envisagées sont des exports du suivi commercial, des messages "
            "de support et des clauses contractuelles ; aucune n'est fournie ici. "
            "[sources: N-C]"
        )
        variantes = {
            "tiret": (
                "- Deux besoins sont évoqués : préparation des demandes commerciales et "
                "tri des demandes de support.\n"
                "- Les sources envisagées sont des exports du suivi commercial, des "
                "messages de support et des clauses contractuelles ; aucune n'est "
                "fournie ici. [sources: N-C]"
            ),
            "etoile": (
                "* Deux besoins sont évoqués : préparation des demandes commerciales et "
                "tri des demandes de support.\n"
                "* Les sources envisagées sont des exports du suivi commercial, des "
                "messages de support et des clauses contractuelles ; aucune n'est "
                "fournie ici. [sources: N-C]"
            ),
            "numerotee": (
                "1. Deux besoins sont évoqués : préparation des demandes commerciales "
                "et tri des demandes de support.\n"
                "2. Les sources envisagées sont des exports du suivi commercial, des "
                "messages de support et des clauses contractuelles ; aucune n'est "
                "fournie ici. [sources: N-C]"
            ),
        }
        with tempfile.TemporaryDirectory() as dossier:
            for nom, nouveau in variantes.items():
                with self.subTest(liste=nom):
                    candidate = Path(dossier) / f"liste-{nom}.md"
                    candidate.write_text(
                        remplacer_unique(sortie_acceptable(), ancien, nouveau),
                        encoding="utf-8",
                    )

                    resultat = valider_pre_cadrage_v0(
                        paquet_approuve(), candidate
                    )

                    self.assertEqual("FAIL", resultat.statut)
                    self.assertEqual("CANDIDATE_ERROR", resultat.origine)
                    self.assertEqual(
                        [
                            ("G-005", True),
                            ("G-001", True),
                            ("G-002", True),
                            ("G-003", False),
                        ],
                        resultat.gates,
                    )

    def test_g005_a_precedence_sur_une_sortie_candidate_invalide(self) -> None:
        paquet = replace(
            paquet_approuve(),
            empreinte_manifeste_approuvee="empreinte-illisible",
        )

        with tempfile.TemporaryDirectory() as dossier:
            candidate_invalide = Path(dossier) / "absente.md"

            resultat = valider_pre_cadrage_v0(paquet, candidate_invalide)

        self.assertEqual("HARNESS_ERROR", resultat.statut)
        self.assertEqual("HARNESS_ERROR", resultat.origine)
        self.assertEqual([("G-005", False)], resultat.gates)
        self.assertIsNone(resultat.preuve["empreinte_candidate"])

    def test_g005_rejette_la_mutation_de_chaque_fichier_du_paquet(self) -> None:
        noms = (
            "brief-proprietaire.md",
            "registre-verite.md",
            "stimulus.md",
            "temoins-qualification.md",
        )
        for nom in noms:
            with self.subTest(fichier=nom), tempfile.TemporaryDirectory() as dossier:
                racine = Path(dossier)
                paquet = copier_paquet(racine)
                chemin = racine / nom
                chemin.write_text(
                    chemin.read_text(encoding="utf-8") + "\nmutation\n",
                    encoding="utf-8",
                )

                resultat = valider_pre_cadrage_v0(
                    paquet, racine / "candidate-absente.md"
                )

                self.assertEqual("HARNESS_ERROR", resultat.statut)
                self.assertEqual([("G-005", False)], resultat.gates)
                self.assertIsNone(resultat.preuve["empreinte_candidate"])

    def test_g005_rejette_identite_ou_inventaire_manifestes_divergents(
        self,
    ) -> None:
        variantes = ("paquet", "version", "inventaire")
        for variante in variantes:
            with (
                self.subTest(variante=variante),
                tempfile.TemporaryDirectory() as dossier,
            ):
                racine = Path(dossier)
                paquet = copier_paquet(racine)
                chemin = racine / "manifeste-paquet.json"
                manifeste = json.loads(chemin.read_text(encoding="utf-8"))
                if variante == "paquet":
                    manifeste["paquet"] = "AUTRE-PAQUET"
                elif variante == "version":
                    manifeste["product_version"] = "V1"
                else:
                    manifeste["fichiers"] = list(reversed(manifeste["fichiers"]))
                chemin.write_text(
                    json.dumps(manifeste, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                paquet = replace(
                    paquet,
                    empreinte_manifeste_approuvee=hashlib.sha256(
                        chemin.read_bytes()
                    ).hexdigest(),
                )

                resultat = valider_pre_cadrage_v0(
                    paquet, racine / "candidate-absente.md"
                )

                self.assertEqual("HARNESS_ERROR", resultat.statut)
                self.assertEqual([("G-005", False)], resultat.gates)
                self.assertIsNone(resultat.preuve["empreinte_candidate"])

    def test_g005_rejette_un_manifeste_json_de_structure_invalide(self) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            paquet = copier_paquet(racine)
            chemin = racine / "manifeste-paquet.json"
            chemin.write_text("[]\n", encoding="utf-8")
            paquet = replace(
                paquet,
                empreinte_manifeste_approuvee=hashlib.sha256(
                    chemin.read_bytes()
                ).hexdigest(),
            )

            resultat = valider_pre_cadrage_v0(
                paquet, racine / "candidate-absente.md"
            )

        self.assertEqual("HARNESS_ERROR", resultat.statut)
        self.assertEqual([("G-005", False)], resultat.gates)
        self.assertIsNone(resultat.preuve["empreinte_candidate"])


if __name__ == "__main__":
    unittest.main()
