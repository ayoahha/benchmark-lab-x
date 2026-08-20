from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.valider_reconciliation_campagne_v0 import (
    BUDGET,
    INVENTAIRE,
    RECU,
    SOURCES,
    canonique,
    valider_reconciliation_campagne_v0,
)


RACINE = Path(__file__).resolve().parents[1]


class ReconciliationCampagneV0Tests(unittest.TestCase):
    def _copie(self) -> tempfile.TemporaryDirectory[str]:
        dossier = tempfile.TemporaryDirectory()
        cible = Path(dossier.name)
        relatifs = [str(binding["path"]) for binding in SOURCES.values()] + [INVENTAIRE, BUDGET, RECU]
        for relatif in relatifs:
            destination = cible / relatif
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(RACINE / relatif, destination)
        return dossier

    def _document(self, racine: Path, relatif: str) -> dict[str, object]:
        return json.loads((racine / relatif).read_bytes())

    def _ecrit(self, racine: Path, relatif: str, document: dict[str, object], canonique_requis: bool = True) -> None:
        contenu = canonique(document) if canonique_requis else json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        (racine / relatif).write_bytes(contenu)

    def _rejette(self, racine: Path) -> None:
        with self.assertRaises(ValueError):
            valider_reconciliation_campagne_v0(racine)

    def test_nominal(self) -> None:
        recu = valider_reconciliation_campagne_v0()
        self.assertEqual("RECONCILIATION_CAMPAGNE_V0_OK", recu["status"])
        self.assertEqual("afab0ffca694ee792534dadcf2a93f58cf451cc71fa9d9c0ddce7d99d15b2ea8", recu["reconciliation_root_sha256"])

    def test_rejette_source_mutee(self) -> None:
        with self._copie() as dossier:
            racine = Path(dossier)
            chemin = racine / SOURCES["acquisition_plan"]["path"]
            chemin.write_bytes(chemin.read_bytes() + b" ")
            self._rejette(racine)

    def test_rejette_recu_duplique_orphelin_ou_chaine_rompue(self) -> None:
        for cle, valeur in (("receipt_content_address_sha256", SOURCES["grok_receipt"]["content_address_sha256"]), ("receipt_file_sha256", "0" * 64), ("predecessor_content_address_sha256", "0" * 64)):
            with self.subTest(cle=cle), self._copie() as dossier:
                racine = Path(dossier)
                document = self._document(racine, INVENTAIRE)
                document["observed"]["slots"][1][cle] = valeur
                self._ecrit(racine, INVENTAIRE, document)
                self._rejette(racine)

    def test_rejette_slot_manquant_ou_supplementaire(self) -> None:
        for mutation in ("missing", "extra"):
            with self.subTest(mutation=mutation), self._copie() as dossier:
                racine = Path(dossier)
                document = self._document(racine, INVENTAIRE)
                slots = document["observed"]["slots"]
                if mutation == "missing":
                    slots.pop()
                else:
                    slots.append(deepcopy(slots[0]))
                self._ecrit(racine, INVENTAIRE, document)
                self._rejette(racine)

    def test_rejette_compteur_divergent(self) -> None:
        with self._copie() as dossier:
            racine = Path(dossier)
            document = self._document(racine, INVENTAIRE)
            document["observed"]["candidate_outputs_observed"] = 2
            self._ecrit(racine, INVENTAIRE, document)
            self._rejette(racine)

    def test_rejette_inconnu_impute_ou_total_numerique(self) -> None:
        for chemin, valeur in ((["grok", "provider_cost_usd"], 0), (["total_monetary_observed_usd"], 0)):
            with self.subTest(chemin=chemin), self._copie() as dossier:
                racine = Path(dossier)
                document = self._document(racine, BUDGET)
                cible = document["observed"]
                for cle in chemin[:-1]:
                    cible = cible[cle]
                cible[chemin[-1]] = valeur
                self._ecrit(racine, BUDGET, document)
                self._rejette(racine)

    def test_rejette_recu_ou_racine_divergent(self) -> None:
        for chemin, valeur in ((["reconciliation_root", "sha256"], "0" * 64), (["output_bindings", "inventory", "sha256"], "0" * 64)):
            with self.subTest(chemin=chemin), self._copie() as dossier:
                racine = Path(dossier)
                document = self._document(racine, RECU)
                cible = document
                for cle in chemin[:-1]:
                    cible = cible[cle]
                cible[chemin[-1]] = valeur
                self._ecrit(racine, RECU, document)
                self._rejette(racine)

    def test_rejette_cle_inconnue_ou_octets_non_canoniques(self) -> None:
        with self._copie() as dossier:
            racine = Path(dossier)
            document = self._document(racine, INVENTAIRE)
            document["inconnue"] = True
            self._ecrit(racine, INVENTAIRE, document)
            self._rejette(racine)
        with self._copie() as dossier:
            racine = Path(dossier)
            document = self._document(racine, INVENTAIRE)
            self._ecrit(racine, INVENTAIRE, document, canonique_requis=False)
            self._rejette(racine)


if __name__ == "__main__":
    unittest.main()
