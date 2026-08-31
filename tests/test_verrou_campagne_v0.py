from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from typing import Callable
import unittest

from tools.valider_verrou_campagne_v0 import (
    CHEMIN_MANIFESTE,
    ENGAGEMENTS_PRIVES_REELS,
    MANIFESTE_PAR_DEFAUT,
    RACINE,
    RECU_PAR_DEFAUT,
    VERROU_PAR_DEFAUT,
    ErreurVerrouCampagne,
    main,
    valider_verrou_campagne_v0,
)
from tests._helpers_v1 import extraire_revision_historique


def _sha256(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def _canonical(document: object) -> bytes:
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


class VerrouCampagneV0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.revision = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.revision.cleanup)
        cls.racine_historique = Path(cls.revision.name)
        extraire_revision_historique(cls.racine_historique)

    def setUp(self) -> None:
        self.verrou_public = json.loads(VERROU_PAR_DEFAUT.read_bytes())
        self.manifeste_public = json.loads(MANIFESTE_PAR_DEFAUT.read_bytes())
        self.recu_public = json.loads(RECU_PAR_DEFAUT.read_bytes())

    def _fixture(
        self,
        mutation_mapping: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, object]:
        temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(temporaire.cleanup)
        base = Path(temporaire.name)
        store = base / "private-store"
        store.mkdir(mode=0o700)
        os.chmod(store, 0o700)

        sel = bytes(range(32))
        campagne = "SYNTHETIC_TEST_CAMPAIGN"
        acquisitions = {"ACQ-GROK46-PRIMARY-001", "ACQ-KIMIK3-PRIMARY-001"}
        ordre = sorted(
            acquisitions,
            key=lambda acquisition: (
                hashlib.sha256(
                    sel + campagne.encode("utf-8") + acquisition.encode("utf-8")
                ).digest(),
                acquisition.encode("utf-8"),
            ),
        )
        mapping = {
            "algorithm": "SYNTHETIC_SHA256_SORT",
            "campaign_id": campagne,
            "cardinality": 2,
            "entries": [
                {
                    "acquisition_id": acquisition,
                    "item_id": f"ITEM-{position:03d}",
                    "position": position,
                }
                for position, acquisition in enumerate(ordre, start=1)
            ],
            "schema_version": "synthetic-private-mapping/v1",
        }
        if mutation_mapping is not None:
            mutation_mapping(mapping)
        mapping_octets = _canonical(mapping)
        engagements = [
            {
                "kind": "RANDOM_SALT_32_BYTES",
                "mode": "0600",
                "sha256": _sha256(sel),
                "size": len(sel),
            },
            {
                "kind": "BLIND_ORDER_MAPPING",
                "mode": "0600",
                "sha256": _sha256(mapping_octets),
                "size": len(mapping_octets),
            },
        ]
        for engagement, contenu in zip(
            engagements, (sel, mapping_octets), strict=True
        ):
            objet = store / str(engagement["sha256"])
            objet.write_bytes(contenu)
            os.chmod(objet, 0o600)

        verrou = deepcopy(self.verrou_public)
        verrou["private_commitments"] = engagements
        verrou_octets = _canonical(verrou)

        manifeste = deepcopy(self.manifeste_public)
        manifeste["lock_artifact"]["sha256"] = _sha256(verrou_octets)
        manifeste["private_commitments"] = engagements
        manifeste_octets = _canonical(manifeste)
        racine_verrou = _sha256(manifeste_octets)

        recu = deepcopy(self.recu_public)
        recu["private_commitments"] = engagements
        recu["lock_root"]["sha256"] = racine_verrou
        recu["public_artifacts"]["lock_sha256"] = _sha256(verrou_octets)
        recu["public_artifacts"]["manifest_sha256"] = racine_verrou
        recu["validation_results"][-1]["lock_root"] = racine_verrou
        recu_octets = _canonical(recu)

        chemins = {
            "lock": base / "verrou.json",
            "manifest": base / "manifeste.json",
            "receipt": base / "recu.json",
        }
        for nom, contenu in (
            ("lock", verrou_octets),
            ("manifest", manifeste_octets),
            ("receipt", recu_octets),
        ):
            chemins[nom].write_bytes(contenu)

        return {
            **chemins,
            "commitments": engagements,
            "lock_document": verrou,
            "manifest_document": manifeste,
            "mapping_document": mapping,
            "receipt_bytes": recu_octets,
            "receipt_document": recu,
            "root": racine_verrou,
            "store": store,
        }

    def _valider(self, fixture: dict[str, object]) -> dict[str, object]:
        return valider_verrou_campagne_v0(
            fixture["lock"],
            fixture["manifest"],
            fixture["receipt"],
            fixture["store"],
            self.racine_historique,
            fixture["commitments"],
        )

    def _rejete(self, fixture: dict[str, object]) -> None:
        with self.assertRaises(ErreurVerrouCampagne):
            self._valider(fixture)

    def _reecrire_document(
        self, fixture: dict[str, object], nom: str, document: object
    ) -> None:
        fixture[nom].write_bytes(_canonical(document))

    def test_accepte_un_store_prive_entierement_synthetique(self) -> None:
        fixture = self._fixture()

        recu = self._valider(fixture)

        self.assertEqual("VERROU_CAMPAGNE_V0_OK", recu["status"])
        self.assertEqual(fixture["root"], recu["lock_root"])
        self.assertEqual(2, recu["private_object_count"])

    def test_recu_est_canonique_sans_timestamp_et_byte_identique(self) -> None:
        fixture = self._fixture()
        avant = fixture["receipt"].read_bytes()

        self._valider(fixture)
        apres = fixture["receipt"].read_bytes()

        self.assertEqual(avant, apres)
        self.assertEqual(avant, _canonical(fixture["receipt_document"]))
        self.assertNotIn(b"timestamp", avant)
        self.assertNotIn(b"created_at", avant)

    def test_rejette_json_non_canonique_doublon_float_et_nan(self) -> None:
        contenus = (
            b'{"schema_version":"x","schema_version":"y"}\n',
            b'{"value":1.5}\n',
            b'{"value":NaN}\n',
        )
        for contenu in contenus:
            fixture = self._fixture()
            fixture["lock"].write_bytes(contenu)
            with self.subTest(contenu=contenu):
                self._rejete(fixture)

    def test_rejette_schema_ou_autorite_v1_v2_divergente(self) -> None:
        mutations = []
        champ = self._fixture()
        document = deepcopy(champ["lock_document"])
        document["unexpected"] = True
        mutations.append((champ, document))
        v1 = self._fixture()
        document = deepcopy(v1["lock_document"])
        document["owner_authorities"]["materialization_v1"]["comment_id"] = 0
        mutations.append((v1, document))
        v2 = self._fixture()
        document = deepcopy(v2["lock_document"])
        document["owner_authorities"]["continuation_v2"]["body_sha256"] = "0" * 64
        mutations.append((v2, document))

        for fixture, document in mutations:
            self._reecrire_document(fixture, "lock", document)
            self._rejete(fixture)

    def test_rejette_racine_ou_recu_divergent(self) -> None:
        fixture = self._fixture()
        recu = deepcopy(fixture["receipt_document"])
        recu["lock_root"]["sha256"] = "0" * 64
        self._reecrire_document(fixture, "receipt", recu)
        self._rejete(fixture)

        for valeur in (True, 0):
            fixture = self._fixture()
            recu = deepcopy(fixture["receipt_document"])
            recu["zero_execution_proof"]["provider_contacted"] = valeur
            self._reecrire_document(fixture, "receipt", recu)
            self._rejete(fixture)

    def test_rejette_manifeste_desordonne_ou_uri_private_comme_chemin(self) -> None:
        fixture = self._fixture()
        manifeste = deepcopy(fixture["manifest_document"])
        manifeste["predecessor_artifacts"].reverse()
        self._reecrire_document(fixture, "manifest", manifeste)
        self._rejete(fixture)

        fixture = self._fixture()
        manifeste = deepcopy(fixture["manifest_document"])
        manifeste["metadata"]["private_store_uri"] = "tasks/private-store"
        self._reecrire_document(fixture, "manifest", manifeste)
        self._rejete(fixture)

    def test_rejette_nom_mode_taille_hash_et_symlink_prives(self) -> None:
        fixture = self._fixture()
        (fixture["store"] / "objet-en-trop").write_bytes(b"x")
        self._rejete(fixture)

        fixture = self._fixture()
        sel = fixture["store"] / fixture["commitments"][0]["sha256"]
        os.chmod(sel, 0o644)
        self._rejete(fixture)

        fixture = self._fixture()
        mapping = fixture["store"] / fixture["commitments"][1]["sha256"]
        mapping.write_bytes(mapping.read_bytes() + b"x")
        self._rejete(fixture)

        fixture = self._fixture()
        mapping = fixture["store"] / fixture["commitments"][1]["sha256"]
        contenu = mapping.read_bytes()
        mapping.unlink()
        cible = Path(mapping.parent.parent) / "cible-mapping"
        cible.write_bytes(contenu)
        mapping.symlink_to(cible)
        self._rejete(fixture)

    def test_rejette_mapping_schema_positions_items_et_ordre(self) -> None:
        mutations = (
            lambda mapping: mapping.update(unexpected=True),
            lambda mapping: mapping["entries"][0].update(position=2),
            lambda mapping: mapping["entries"][0].update(item_id="ITEM-999"),
            lambda mapping: mapping["entries"].reverse(),
        )
        for mutation in mutations:
            fixture = self._fixture(mutation)
            self._rejete(fixture)

    def test_rejette_engagements_prives_publics_divergents(self) -> None:
        fixture = self._fixture()
        verrou = deepcopy(fixture["lock_document"])
        verrou["private_commitments"] = ENGAGEMENTS_PRIVES_REELS
        self._reecrire_document(fixture, "lock", verrou)
        self._rejete(fixture)

    def test_cli_echoue_fail_closed_sans_divulguer_de_valeur(self) -> None:
        fixture = self._fixture()
        fixture["lock"].write_bytes(b'{"value":NaN}\n')
        sortie, erreur = io.StringIO(), io.StringIO()

        with redirect_stdout(sortie), redirect_stderr(erreur):
            code = main(
                [
                    "--lock",
                    str(fixture["lock"]),
                    "--manifest",
                    str(fixture["manifest"]),
                    "--receipt",
                    str(fixture["receipt"]),
                    "--private-store",
                    str(fixture["store"]),
                ]
            )

        self.assertNotEqual(0, code)
        self.assertEqual("", sortie.getvalue())
        self.assertTrue(erreur.getvalue().startswith("HOLD_CAMPAIGN_LOCK:"))
        self.assertNotIn("ACQ-GROK46", erreur.getvalue())
        self.assertNotIn("ACQ-KIMIK3", erreur.getvalue())


if __name__ == "__main__":
    unittest.main()
