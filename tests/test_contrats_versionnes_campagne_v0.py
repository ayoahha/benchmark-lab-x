from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.valider_contrats_versionnes_campagne_v0 import (
    EMPREINTE_MATRICE_ATTENDUE,
    main,
    valider_contrats_versionnes_campagne_v0,
)


RACINE = Path(__file__).resolve().parents[1]
MATRICE = (
    RACINE
    / "tasks/dev/pre-cadrage-entretien-client/campagne-v0/contrats-versionnes-v1/contrats-versionnes.json"
)


class ContratsVersionnesCampagneV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(MATRICE.read_bytes())

    def _verifier_echec_non_nul(self, document: dict[str, object]) -> None:
        with tempfile.TemporaryDirectory() as dossier:
            matrice = Path(dossier) / "contrats-versionnes.json"
            matrice.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertNotEqual(0, main([str(matrice)]))

    def test_matrice_canonique_est_valide(self) -> None:
        recu = valider_contrats_versionnes_campagne_v0()

        self.assertEqual("CONTRATS_VERSIONNES_CAMPAGNE_V0_OK", recu["status"])
        self.assertEqual(EMPREINTE_MATRICE_ATTENDUE, recu["matrix_sha256"])
        self.assertEqual(6, recu["dimension_count"])

    def test_rejette_valeur_divergente(self) -> None:
        document = deepcopy(self.document)
        document["version_matrix"][0]["value"] = "V1"

        self._verifier_echec_non_nul(document)

    def test_rejette_confusion_de_categorie(self) -> None:
        document = deepcopy(self.document)
        document["version_matrix"][0]["category"] = "artifact"

        self._verifier_echec_non_nul(document)

    def test_rejette_reference_ou_hash_divergent(self) -> None:
        mutations = []
        reference_divergente = deepcopy(self.document)
        reference_divergente["version_matrix"][0]["contract_source_ids"][0] = (
            "contrat_absent"
        )
        mutations.append(reference_divergente)
        hash_divergent = deepcopy(self.document)
        hash_divergent["active_contracts"]["architecture"]["sha256"] = "0" * 64
        mutations.append(hash_divergent)

        for document in mutations:
            with self.subTest(document=document):
                self._verifier_echec_non_nul(document)

    def test_rejette_champ_inconnu(self) -> None:
        document = deepcopy(self.document)
        document["owner_authorities"]["acceptance"]["unexpected"] = True

        self._verifier_echec_non_nul(document)

    def test_rejette_protocole_historique_injecte(self) -> None:
        document = deepcopy(self.document)
        document["version_matrix"][2]["value"] = "benchmark-lab-x/protocol/v2"

        self._verifier_echec_non_nul(document)


if __name__ == "__main__":
    unittest.main()
