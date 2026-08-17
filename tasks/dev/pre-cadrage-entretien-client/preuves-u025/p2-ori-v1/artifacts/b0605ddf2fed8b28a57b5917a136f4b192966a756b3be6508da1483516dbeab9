// U025-P2-ORI-V1 — portes G-001..G-005, port fidèle de
// tools/validateur_pre_cadrage_v0.py
// (sha256 e631184b84270c4b3dbf931910436ad65b7d08c02016c94d2dfe53e27ead2056).
// Court-circuit identique à valider_pre_cadrage_v0 : G-005 puis G-001..G-004.
// Aucun réseau. Aucun modèle. Aucun juge.

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const NOM = "PRECADRAGE-ENTRETIEN-CLIENT-V0";
const VERSION = "V0";
const FICHIERS_PAQUET = [
  "brief-proprietaire.md",
  "registre-verite.md",
  "stimulus.md",
  "temoins-qualification.md",
] as const;
const CHAMPS = [
  "artifact_type",
  "version",
  "scenario",
  "client_ready",
  "qualification",
  "conformite",
] as const;
const SECTIONS = [
  "Périmètre",
  "Faits établis",
  "Contraintes critiques",
  "Inconnues",
  "Hypothèses conditionnelles",
  "Contradictions à arbitrer",
  "Risques prioritaires",
  "Questions prioritaires pour l'entretien",
  "Prochaine action",
  "Exclusions",
] as const;

const ANCRE_STIMULUS = /`\[(N-[A-Z]+)\]`/g;
const SOURCES = /\[sources: (N-[A-Z]+(?:, N-[A-Z]+)*)\]$/;
const ID_REGISTRE = /^- ID: ([A-Z][A-Z0-9-]*-\d+)$/gm;
const ID_VISIBLE = /(?<![A-Z0-9-])([A-Z][A-Z0-9-]*-\d+)(?![A-Z0-9-])/g;
const ELEMENT_LISTE = /^(?:[-*] |\d+\. )/;

export type AutomaticStatus = "PASS" | "FAIL" | "HARNESS_ERROR";

export type GatePair = [string, boolean];

export type AutomaticResult = {
  status: AutomaticStatus;
  origin: "CANDIDATE_ERROR" | "HARNESS_ERROR" | null;
  gates: GatePair[];
  reason: string;
};

export type EvaluateInput = {
  text: string;
  packageDir: string;
  empreinteManifesteApprouvee: string;
  approbateur: string;
  verdictApprobation: string;
};

export function sha256Bytes(data: Uint8Array | string): string {
  return createHash("sha256").update(data).digest("hex");
}

function pySplitlines(texte: string): string[] {
  const lignes = texte.split("\n");
  if (lignes.length && lignes[lignes.length - 1] === "") lignes.pop();
  return lignes;
}

function parserG001(texte: string): Record<string, string> | null {
  const lignes = pySplitlines(texte);
  if (!lignes.length || lignes[0] !== "---") return null;
  let finFrontmatter = -1;
  for (let i = 1; i < lignes.length; i += 1) {
    if (lignes[i] === "---") {
      finFrontmatter = i;
      break;
    }
  }
  if (finFrontmatter === -1) return null;
  const champs: Record<string, string> = {};
  const ordre: string[] = [];
  for (const ligne of lignes.slice(1, finFrontmatter)) {
    if (!ligne.includes(":")) return null;
    const idx = ligne.indexOf(":");
    const cle = ligne.slice(0, idx);
    const valeur = ligne.slice(idx + 1);
    if (!(CHAMPS as readonly string[]).includes(cle) || Object.prototype.hasOwnProperty.call(champs, cle)) {
      return null;
    }
    champs[cle] = valeur.startsWith(" ") ? valeur.slice(1) : valeur;
    ordre.push(cle);
  }
  if (JSON.stringify(ordre) !== JSON.stringify(CHAMPS)) return null;
  const titres = lignes
    .slice(finFrontmatter + 1)
    .filter((l) => l.startsWith("# "))
    .map((l) => l.slice(2));
  if (JSON.stringify(titres) !== JSON.stringify(SECTIONS)) return null;
  return champs;
}

function evaluerG003(texte: string, cheminStimulus: string, cheminRegistre: string): boolean {
  const stimulus = readFileSync(cheminStimulus, "utf8");
  const registre = readFileSync(cheminRegistre, "utf8");
  const ancresAutorisees = new Set(Array.from(stimulus.matchAll(ANCRE_STIMULUS), (m) => m[1]));
  const identifiantsInternes = new Set(Array.from(registre.matchAll(ID_REGISTRE), (m) => m[1]));
  const lignes = pySplitlines(texte);
  let finFrontmatter = -1;
  for (let i = 1; i < lignes.length; i += 1) {
    if (lignes[i] === "---") {
      finFrontmatter = i;
      break;
    }
  }
  if (finFrontmatter === -1) return false;
  const blocs: string[] = [];
  let courant: string[] = [];
  for (const ligne of lignes.slice(finFrontmatter + 1)) {
    if (!ligne || ligne.startsWith("# ")) {
      if (courant.length) {
        blocs.push(courant.join(" "));
        courant = [];
      }
      continue;
    }
    if (ELEMENT_LISTE.test(ligne) && courant.length) {
      blocs.push(courant.join(" "));
      courant = [];
    }
    courant.push(ligne);
  }
  if (courant.length) blocs.push(courant.join(" "));
  for (const bloc of blocs) {
    const correspondance = SOURCES.exec(bloc);
    SOURCES.lastIndex = 0;
    if (!correspondance) return false;
    const ancres = correspondance[1].split(", ");
    if (ancres.some((ancre) => !ancresAutorisees.has(ancre))) return false;
    const visibles = Array.from(bloc.matchAll(ID_VISIBLE), (m) => m[1]);
    if (visibles.some((id) => identifiantsInternes.has(id))) return false;
  }
  return blocs.length > 0;
}

function evaluerG005(input: EvaluateInput): { ok: boolean; reason: string } {
  const { packageDir, empreinteManifesteApprouvee, approbateur, verdictApprobation } = input;
  const cheminManifeste = join(packageDir, "manifeste-paquet.json");
  if (!cheminManifeste || !empreinteManifesteApprouvee || !approbateur || verdictApprobation !== "APPROUVE") {
    return { ok: false, reason: "G-005 approbation absente, illisible ou invalide" };
  }
  let contenu: Buffer;
  try {
    contenu = readFileSync(cheminManifeste);
  } catch (e) {
    const code = e && typeof e === "object" && "code" in e ? String((e as { code: unknown }).code) : "ERR";
    return { ok: false, reason: `G-005 manifeste illisible (${code})` };
  }
  const empreinteObservee = sha256Bytes(contenu);
  if (empreinteObservee !== empreinteManifesteApprouvee) {
    return {
      ok: false,
      reason:
        "G-005 empreinte approuvée non concordante (approuvée=" +
        empreinteManifesteApprouvee +
        ", observée=" +
        empreinteObservee +
        ")",
    };
  }
  let manifeste: unknown;
  try {
    manifeste = JSON.parse(contenu.toString("utf8"));
  } catch {
    return { ok: false, reason: "G-005 manifeste non analysable" };
  }
  if (typeof manifeste !== "object" || manifeste === null || Array.isArray(manifeste)) {
    return { ok: false, reason: "G-005 manifeste non conforme" };
  }
  const rec = manifeste as Record<string, unknown>;
  const fichiers = rec.fichiers;
  const chemins = Array.isArray(fichiers)
    ? fichiers.map((f) => (f && typeof f === "object" && "chemin" in f ? (f as { chemin: unknown }).chemin : null))
    : null;
  if (
    rec.paquet !== NOM ||
    rec.product_version !== VERSION ||
    !Array.isArray(fichiers) ||
    JSON.stringify(chemins) !== JSON.stringify(FICHIERS_PAQUET)
  ) {
    return { ok: false, reason: "G-005 identité du paquet non conforme" };
  }
  const attendus = FICHIERS_PAQUET.map((nom, i) => [
    nom,
    (fichiers[i] as { sha256: unknown }).sha256,
  ]);
  let observes: Array<[string, string]>;
  try {
    observes = FICHIERS_PAQUET.map((nom) => [
      nom,
      sha256Bytes(readFileSync(join(packageDir, nom))),
    ]);
  } catch (e) {
    const code = e && typeof e === "object" && "code" in e ? String((e as { code: unknown }).code) : "ERR";
    return { ok: false, reason: `G-005 fichier du paquet illisible (${code})` };
  }
  if (JSON.stringify(observes) !== JSON.stringify(attendus)) {
    return { ok: false, reason: "G-005 empreintes du paquet non concordantes" };
  }
  return { ok: true, reason: "G-005 PASS" };
}

export function evaluateAutomatic(input: EvaluateInput): AutomaticResult {
  const g005 = evaluerG005(input);
  if (!g005.ok) {
    return {
      status: "HARNESS_ERROR",
      origin: "HARNESS_ERROR",
      gates: [["G-005", false]],
      reason: g005.reason,
    };
  }
  const champs = parserG001(input.text);
  if (champs === null) {
    return {
      status: "FAIL",
      origin: "CANDIDATE_ERROR",
      gates: [
        ["G-005", true],
        ["G-001", false],
      ],
      reason: "G-001 FAIL origine CANDIDATE_ERROR: enveloppe, schéma ou sections non conformes",
    };
  }
  if (champs.client_ready !== "false" || champs.conformite !== "NON_EVALUEE") {
    return {
      status: "FAIL",
      origin: "CANDIDATE_ERROR",
      gates: [
        ["G-005", true],
        ["G-001", true],
        ["G-002", false],
      ],
      reason:
        "G-002 FAIL origine CANDIDATE_ERROR: valeur fermée interdite (client_ready=" +
        champs.client_ready +
        ", conformite=" +
        champs.conformite +
        ")",
    };
  }
  const gates: GatePair[] = [
    ["G-005", true],
    ["G-001", true],
    ["G-002", true],
  ];
  let conformeG003: boolean;
  try {
    conformeG003 = evaluerG003(
      input.text,
      join(input.packageDir, "stimulus.md"),
      join(input.packageDir, "registre-verite.md"),
    );
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return {
      status: "HARNESS_ERROR",
      origin: "HARNESS_ERROR",
      gates: [...gates, ["G-003", false]],
      reason: "HARNESS_ERROR: G-003 entrée de référence illisible (" + message + ")",
    };
  }
  if (!conformeG003) {
    return {
      status: "FAIL",
      origin: "CANDIDATE_ERROR",
      gates: [...gates, ["G-003", false]],
      reason:
        "G-003 FAIL origine CANDIDATE_ERROR: référence absente, mal formée, inconnue ou ID interne visible",
    };
  }
  gates.push(["G-003", true]);
  if (
    champs.artifact_type !== "pre_cadrage_entretien_client" ||
    champs.version !== "V0" ||
    champs.scenario !== "synthetique" ||
    !["QUALIFIABLE", "NON_QUALIFIABLE"].includes(champs.qualification)
  ) {
    return {
      status: "FAIL",
      origin: "CANDIDATE_ERROR",
      gates: [...gates, ["G-004", false]],
      reason: "G-004 FAIL origine CANDIDATE_ERROR: valeur contrôlée hors vocabulaire fermé",
    };
  }
  return {
    status: "PASS",
    origin: null,
    gates: [...gates, ["G-004", true]],
    reason: "PASS G-001..G-005",
  };
}
