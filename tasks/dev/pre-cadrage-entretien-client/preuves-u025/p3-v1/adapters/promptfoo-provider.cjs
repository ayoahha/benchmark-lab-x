"use strict";

const { createHash } = require("node:crypto");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { spawnSync } = require("node:child_process");

const ROOT = join(__dirname, "..");
const STIMULUS = join(ROOT, "..", "..", "stimulus.md");
const STIMULUS_SHA256 = "20f0be450640704b0c467eee57ca2ea58a4d629e63eba3efccbc6f68440e07e4";
const NODE_SHA256 = "1ef99ea25fe70c9b67e7efe768ef8ee22148d3cabc703db6131b57aeb617d040";

class P3LockedProvider {
  id() {
    return `p3-locked:${process.env.P3_CONFIGURATION || "unset"}`;
  }

  async callApi(prompt) {
    const runtimeDigest = createHash("sha256").update(readFileSync(process.execPath)).digest("hex");
    if (process.version !== "v26.7.0" || runtimeDigest !== NODE_SHA256) {
      throw new Error("HARNESS_ERROR: runtime Node non figé");
    }
    const digest = createHash("sha256").update(Buffer.from(prompt, "utf8")).digest("hex");
    if (digest !== STIMULUS_SHA256 || readFileSync(STIMULUS, "utf8") !== prompt) {
      throw new Error("HARNESS_ERROR: prompt Promptfoo hors lock");
    }
    const child = spawnSync(
      "/opt/homebrew/bin/python3",
      [
        join(__dirname, "shared_acquisition.py"),
        "--authorization", process.env.P3_AUTHORIZATION || "",
        "--path", "promptfoo",
        "--configuration", process.env.P3_CONFIGURATION || "",
        "--stage", process.env.P3_STAGE || "",
      ],
      { encoding: "utf8", env: process.env, shell: false },
    );
    if (child.status !== 0) {
      throw new Error((child.stderr || "HARNESS_ERROR: acquisition refusée").trim());
    }
    const envelope = JSON.parse(child.stdout);
    return {
      output: envelope.output,
      tokenUsage: envelope.receipt.cost.usage,
      metadata: {
        receipt_sha256: envelope.receipt_sha256,
        raw_response_sha256: envelope.raw_response_sha256,
        candidate_output_sha256: envelope.candidate_output_sha256,
        raw_store_required: envelope.storage_action,
      },
    };
  }
}

module.exports = P3LockedProvider;
