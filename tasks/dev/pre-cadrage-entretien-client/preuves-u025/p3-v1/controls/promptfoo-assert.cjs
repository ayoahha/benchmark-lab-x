"use strict";

const { spawnSync } = require("node:child_process");
const { randomBytes } = require("node:crypto");
const { unlinkSync, writeFileSync } = require("node:fs");
const { tmpdir } = require("node:os");
const { join } = require("node:path");

const RUNNER = join(__dirname, "run_controls.py");
const PYTHON = "/opt/homebrew/bin/python3";
const VALIDATOR_SHA256 = "e631184b84270c4b3dbf931910436ad65b7d08c02016c94d2dfe53e27ead2056";

function runGate(output, gate) {
  const text = typeof output === "string" ? output : "";
  const tmp = join(tmpdir(), `p3-v2-${gate}-${randomBytes(8).toString("hex")}.md`);
  writeFileSync(tmp, text);
  let child;
  try {
    child = spawnSync(PYTHON, [RUNNER, "--candidate", tmp, "--gate", gate], {
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
    const reason = (child.stderr || "HARNESS_ERROR: contrôle P3 indécidable").trim();
    if (gate === "G-005") {
      throw new Error(reason);
    }
    return { pass: false, score: 0, reason };
  }
  const parsed = JSON.parse(child.stdout);
  if (parsed.validator_sha256 !== VALIDATOR_SHA256) {
    throw new Error("HARNESS_ERROR: validateur canonique non lié");
  }
  if (parsed.status === "HARNESS_ERROR") {
    throw new Error("HARNESS_ERROR: " + (parsed.origin || "contrôle indécidable"));
  }
  if (parsed.pass === true) {
    return { pass: true, score: 1, reason: gate + " PASS" };
  }
  return { pass: false, score: 0, reason: gate + " FAIL" };
}

function g005(output) {
  return runGate(output, "G-005");
}
function g001(output) {
  return runGate(output, "G-001");
}
function g002(output) {
  return runGate(output, "G-002");
}
function g003(output) {
  return runGate(output, "G-003");
}
function g004(output) {
  return runGate(output, "G-004");
}

module.exports = { g001, g002, g003, g004, g005 };
