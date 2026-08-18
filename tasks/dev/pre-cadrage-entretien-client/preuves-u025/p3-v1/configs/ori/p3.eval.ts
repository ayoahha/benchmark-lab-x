import { test } from "bun:test";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, unlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { p3Agent } from "../../adapters/ori-agent.ts";

const DIR = dirname(fileURLToPath(import.meta.url));
const ROOT = join(DIR, "../..");
const STIMULUS = join(ROOT, "..", "..", "stimulus.md");
const STIMULUS_SHA256 = "20f0be450640704b0c467eee57ca2ea58a4d629e63eba3efccbc6f68440e07e4";
const VALIDATOR_SHA256 = "e631184b84270c4b3dbf931910436ad65b7d08c02016c94d2dfe53e27ead2056";
const RUNNER = join(ROOT, "controls", "run_controls.py");
const PYTHON = "/opt/homebrew/bin/python3";

function sha256Utf8(text: string): string {
  return createHash("sha256").update(Buffer.from(text, "utf8")).digest("hex");
}

function runControls(text: string): {
  status: string;
  origin: string | null;
  gates: Array<[string, boolean]>;
  validator_sha256: string;
} {
  const tmp = join(tmpdir(), `p3-v2-ori-${sha256Utf8(text).slice(0, 16)}.md`);
  writeFileSync(tmp, text);
  let child;
  try {
    child = spawnSync(PYTHON, [RUNNER, "--candidate", tmp], {
      encoding: "utf8",
      shell: false,
    });
  } finally {
    try {
      unlinkSync(tmp);
    } catch {
      // best-effort cleanup of the temporary candidate file
    }
  }
  if (child.status !== 0) {
    throw new Error((child.stderr || "HARNESS_ERROR: contrôle P3 indécidable").trim());
  }
  return JSON.parse(child.stdout) as {
    status: string;
    origin: string | null;
    gates: Array<[string, boolean]>;
    validator_sha256: string;
  };
}

test("p3-stimulus-single", async () => {
  const stimulus = readFileSync(STIMULUS, "utf8");
  if (sha256Utf8(stimulus) !== STIMULUS_SHA256) {
    throw new Error("HARNESS_ERROR: stimulus non figé");
  }
  const run = await p3Agent.run(stimulus);
  run.toComplete();
  const auto = runControls(run.text);
  if (auto.validator_sha256 !== VALIDATOR_SHA256) {
    throw new Error("HARNESS_ERROR: validateur canonique non lié");
  }
  if (auto.status === "HARNESS_ERROR") {
    throw new Error("HARNESS_ERROR: " + String(auto.origin));
  }
  if (auto.status === "FAIL") {
    throw new Error("CANDIDATE_ERROR: G-001 à G-005");
  }
});
