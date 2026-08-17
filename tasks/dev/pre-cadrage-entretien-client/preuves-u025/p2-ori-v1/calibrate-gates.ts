// Calibration hors ori eval : projections G-001..G-005 contre l'oracle P1.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { evaluateAutomatic } from "./local-gates.ts";

const DIR = dirname(fileURLToPath(import.meta.url));
const PACKAGE_DIR = join(DIR, "../..");
const fixtures = JSON.parse(readFileSync(join(DIR, "case-fixtures.json"), "utf8")) as {
  cases: Array<{
    case_id: string;
    candidate: string;
    candidate_sha256: string;
    empreinte_manifeste_approuvee: string;
    expected: {
      automatic: string;
      gates: Array<[string, boolean]>;
    };
  }>;
};

const rows = [];
let mismatches = 0;
for (const rec of fixtures.cases) {
  const auto = evaluateAutomatic({
    text: rec.candidate,
    packageDir: PACKAGE_DIR,
    empreinteManifesteApprouvee: rec.empreinte_manifeste_approuvee,
    approbateur: "Ayo",
    verdictApprobation: "APPROUVE",
  });
  const match =
    auto.status === rec.expected.automatic &&
    JSON.stringify(auto.gates) === JSON.stringify(rec.expected.gates);
  if (!match) mismatches += 1;
  rows.push({
    case_id: rec.case_id,
    observed_status: auto.status,
    expected_status: rec.expected.automatic,
    observed_gates: auto.gates,
    expected_gates: rec.expected.gates,
    match,
    reason: auto.reason,
  });
}

const receipt = {
  schema_version: "u025/p2-ori-calibration/v1",
  proof_id: "U025-P2-ORI-V1",
  instrument: "local-gates.ts port of tools/validateur_pre_cadrage_v0.py",
  validator_sha256: "e631184b84270c4b3dbf931910436ad65b7d08c02016c94d2dfe53e27ead2056",
  oracle_sha256: "fb6df05fb033a3e4839fe140f4bc325e84ee68f09bff75771b2efad7e5b97124",
  matched: fixtures.cases.length - mismatches,
  total: fixtures.cases.length,
  status: mismatches === 0 ? "CALIBRATION_OK" : "CALIBRATION_FAIL",
  rows,
};

const out = join(DIR, "calibration-receipt.json");
writeFileSync(out, JSON.stringify(receipt, null, 2) + "\n");
if (mismatches !== 0) {
  console.error("CALIBRATION_FAIL", mismatches);
  process.exit(1);
}
console.log("CALIBRATION_OK", receipt.matched + "/" + receipt.total);
