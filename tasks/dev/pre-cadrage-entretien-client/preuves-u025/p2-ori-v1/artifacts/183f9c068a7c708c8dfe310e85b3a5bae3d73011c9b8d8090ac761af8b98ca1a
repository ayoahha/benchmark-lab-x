// U025-P2-ORI-V1 — eval native Ori des 16 fixtures figées.
// Transport : setupAgent({ harness }) in-process (SDK ori/eval, runViaHarness),
// réponses pré-calculées locales, zéro modèle, zéro juge, zéro catalogue.
import { test } from "bun:test";
import { setupAgent } from "ori/eval";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { evaluateAutomatic, sha256Bytes } from "./local-gates.ts";

const DIR = dirname(fileURLToPath(import.meta.url));
const PACKAGE_DIR = join(DIR, "../..");
const fixtures = JSON.parse(readFileSync(join(DIR, "case-fixtures.json"), "utf8")) as {
  cases: Array<{
    case_id: string;
    candidate: string;
    candidate_sha256: string;
    empreinte_manifeste_approuvee: string;
  }>;
};

const byId = new Map(fixtures.cases.map((c) => [c.case_id, c]));

const agent = setupAgent({
  harness: {
    name: "p2-ori-local-deterministic",
    init(registrar) {
      registrar.registerPrompt(async function* (options) {
        const rec = byId.get(options.prompt);
        if (rec === undefined) {
          throw new Error("unknown frozen case: " + options.prompt);
        }
        yield {
          type: "assistant.text.delta",
          payload: { delta: rec.candidate },
        };
        yield { type: "session.succeeded", payload: {} };
      });
    },
  },
});

for (const rec of fixtures.cases) {
  test(rec.case_id, async () => {
    const run = await agent.run(rec.case_id);
    run.toComplete();
    const got = sha256Bytes(run.text);
    if (got !== rec.candidate_sha256) {
      throw new Error(
        "CANDIDATE_ERROR: transport non byte-exact " + got + " != " + rec.candidate_sha256,
      );
    }
    if (run.costUsd !== undefined) {
      throw new Error(
        "PROVIDER_FAILURE: costUsd native reporté (" +
          String(run.costUsd) +
          ") alors qu'aucune dépense n'est autorisée",
      );
    }
    const auto = evaluateAutomatic({
      text: run.text,
      packageDir: PACKAGE_DIR,
      empreinteManifesteApprouvee: rec.empreinte_manifeste_approuvee,
      approbateur: "Ayo",
      verdictApprobation: "APPROUVE",
    });
    if (auto.status === "HARNESS_ERROR") {
      throw new Error("HARNESS_ERROR: " + auto.reason);
    }
    if (auto.status === "FAIL") {
      throw new Error("CANDIDATE_ERROR: " + auto.reason);
    }
  });
}
