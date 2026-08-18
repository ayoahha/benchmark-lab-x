import { setupAgent } from "ori/eval";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const DIR = dirname(fileURLToPath(import.meta.url));
const ROOT = join(DIR, "..");
const STIMULUS = join(ROOT, "..", "..", "stimulus.md");
const STIMULUS_SHA256 = "20f0be450640704b0c467eee57ca2ea58a4d629e63eba3efccbc6f68440e07e4";
const BUN_SHA256 = "e0c90ec15d33363e6b70713d56bc3b2c7585c17f40a0fe0f8fd9305901d4e233";

export const p3Agent = setupAgent({
  harness: {
    name: "u025-p3-locked-native-wrapper",
    init(registrar) {
      registrar.registerPrompt(async function* (options) {
        const runtimeDigest = createHash("sha256").update(readFileSync(process.execPath)).digest("hex");
        if (process.versions.bun !== "1.3.14" || runtimeDigest !== BUN_SHA256) {
          throw new Error("HARNESS_ERROR: runtime Bun non figé");
        }
        const prompt = options.prompt;
        const digest = createHash("sha256").update(Buffer.from(prompt, "utf8")).digest("hex");
        if (digest !== STIMULUS_SHA256 || readFileSync(STIMULUS, "utf8") !== prompt) {
          throw new Error("HARNESS_ERROR: prompt Ori hors lock");
        }
        const child = spawnSync(
          "/opt/homebrew/bin/python3",
          [
            join(DIR, "shared_acquisition.py"),
            "--authorization", process.env.P3_AUTHORIZATION || "",
            "--path", "ori",
            "--configuration", process.env.P3_CONFIGURATION || "",
            "--stage", process.env.P3_STAGE || "",
          ],
          { encoding: "utf8", env: process.env, shell: false },
        );
        if (child.status !== 0) {
          throw new Error((child.stderr || "HARNESS_ERROR: acquisition refusée").trim());
        }
        const envelope = JSON.parse(child.stdout);
        yield { type: "assistant.text.delta", payload: { delta: envelope.output } };
        yield { type: "session.succeeded", payload: {} };
      });
    },
  },
});
