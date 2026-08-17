"use strict";
// U025-P2-PROMPTFOO-V1 — assertions natives promptfoo (type "javascript", forme file://gates.js:gXXX).
// Port fidèle des portes G-001..G-005 de tools/validateur_pre_cadrage_v0.py
// (sha256 e631184b84270c4b3dbf931910436ad65b7d08c02016c94d2dfe53e27ead2056), sans réécriture des règles.
// Canal des états : porte non conforme -> pass:false (ResultFailureReason.ASSERT = FAIL candidat) ;
// dispositif indécidable (G-005) -> exception (ResultFailureReason.ERROR = HARNESS_ERROR), conformément
// au traitement natif promptfoo 0.122.0 des exceptions d'assertion javascript file:// (evaluator, applyGradingError).
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const NOM = "PRECADRAGE-ENTRETIEN-CLIENT-V0";
const VERSION = "V0";
const FICHIERS_PAQUET = [
  "brief-proprietaire.md",
  "registre-verite.md",
  "stimulus.md",
  "temoins-qualification.md",
];
const CHAMPS = [
  "artifact_type",
  "version",
  "scenario",
  "client_ready",
  "qualification",
  "conformite",
];
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
];
const ANCRE_STIMULUS = /`\[(N-[A-Z]+)\]`/g;
const SOURCES = /\[sources: (N-[A-Z]+(?:, N-[A-Z]+)*)\]$/;
const ID_REGISTRE = /^- ID: ([A-Z][A-Z0-9-]*-\d+)$/gm;
const ID_VISIBLE = /(?<![A-Z0-9-])([A-Z][A-Z0-9-]*-\d+)(?![A-Z0-9-])/g;
const ELEMENT_LISTE = /^(?:[-*] |\d+\. )/;

function sha256(donnees) {
  return crypto.createHash("sha256").update(donnees).digest("hex");
}

// Équivalent de str.splitlines() de Python pour un texte dont les seuls
// séparateurs sont "\n" (propriété vérifiée sur les 16 fixtures figées).
function pySplitlines(texte) {
  const lignes = texte.split("\n");
  if (lignes.length && lignes[lignes.length - 1] === "") lignes.pop();
  return lignes;
}

function packageDir(context) {
  return path.resolve(__dirname, String(context.vars.package_dir));
}

function texteCandidate(output) {
  return typeof output === "string" ? output : null;
}

function parserG001(texte) {
  if (texte === null) return null;
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
  const champs = {};
  const ordre = [];
  for (const ligne of lignes.slice(1, finFrontmatter)) {
    if (!ligne.includes(":")) return null;
    const idx = ligne.indexOf(":");
    const cle = ligne.slice(0, idx);
    const valeur = ligne.slice(idx + 1);
    if (!CHAMPS.includes(cle) || Object.prototype.hasOwnProperty.call(champs, cle)) return null;
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

function evaluerG003(texte, cheminStimulus, cheminRegistre) {
  const stimulus = fs.readFileSync(cheminStimulus, "utf8");
  const registre = fs.readFileSync(cheminRegistre, "utf8");
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
  const blocs = [];
  let courant = [];
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
    if (!correspondance) return false;
    const ancres = correspondance[1].split(", ");
    if (ancres.some((ancre) => !ancresAutorisees.has(ancre))) return false;
    const visibles = Array.from(bloc.matchAll(ID_VISIBLE), (m) => m[1]);
    if (visibles.some((id) => identifiantsInternes.has(id))) return false;
  }
  return blocs.length > 0;
}

function g005(_output, context) {
  const vars = context.vars;
  const echec = (motif) => {
    throw new Error("HARNESS_ERROR: G-005 " + motif);
  };
  const approuvee = vars.empreinte_manifeste_approuvee;
  const approbateur = vars.approbateur;
  const verdict = vars.verdict_approbation;
  const cheminManifeste = path.join(packageDir(context), "manifeste-paquet.json");
  if (!cheminManifeste || !approuvee || !approbateur || verdict !== "APPROUVE") {
    echec("approbation absente, illisible ou invalide");
  }
  let contenu;
  try {
    contenu = fs.readFileSync(cheminManifeste);
  } catch (e) {
    echec("manifeste illisible (" + e.code + ")");
  }
  const empreinteObservee = sha256(contenu);
  if (empreinteObservee !== approuvee) {
    echec(
      "empreinte approuvée non concordante (approuvée=" +
        approuvee +
        ", observée=" +
        empreinteObservee +
        ")"
    );
  }
  let manifeste;
  try {
    manifeste = JSON.parse(contenu.toString("utf8"));
  } catch (_e) {
    echec("manifeste non analysable");
  }
  if (typeof manifeste !== "object" || manifeste === null || Array.isArray(manifeste)) {
    echec("manifeste non conforme");
  }
  const fichiers = manifeste.fichiers;
  const chemins = Array.isArray(fichiers)
    ? fichiers.map((f) => (f && typeof f === "object" ? f.chemin : null))
    : null;
  if (
    manifeste.paquet !== NOM ||
    manifeste.product_version !== VERSION ||
    !Array.isArray(fichiers) ||
    JSON.stringify(chemins) !== JSON.stringify(FICHIERS_PAQUET)
  ) {
    echec("identité du paquet non conforme");
  }
  const attendus = FICHIERS_PAQUET.map((nom, i) => [nom, fichiers[i].sha256]);
  let observes;
  try {
    observes = FICHIERS_PAQUET.map((nom) => [
      nom,
      sha256(fs.readFileSync(path.join(packageDir(context), nom))),
    ]);
  } catch (e) {
    echec("fichier du paquet illisible (" + e.code + ")");
  }
  if (JSON.stringify(observes) !== JSON.stringify(attendus)) {
    echec("empreintes du paquet non concordantes");
  }
  const approbation = JSON.stringify({
    approbateur: approbateur,
    empreinte_manifeste: approuvee,
    verdict: verdict,
  });
  return {
    pass: true,
    score: 1,
    reason: "G-005 PASS empreinte_provenance=" + sha256(Buffer.from(approbation, "utf8")),
  };
}

function g001(output) {
  const champs = parserG001(texteCandidate(output));
  if (champs === null) {
    return {
      pass: false,
      score: 0,
      reason: "G-001 FAIL origine CANDIDATE_ERROR: enveloppe, schéma ou sections non conformes",
    };
  }
  return { pass: true, score: 1, reason: "G-001 PASS" };
}

function g002(output) {
  const champs = parserG001(texteCandidate(output));
  if (champs === null) {
    return {
      pass: false,
      score: 0,
      reason: "G-002 FAIL origine CANDIDATE_ERROR: précondition G-001 non satisfaite",
    };
  }
  if (champs.client_ready !== "false" || champs.conformite !== "NON_EVALUEE") {
    return {
      pass: false,
      score: 0,
      reason:
        "G-002 FAIL origine CANDIDATE_ERROR: valeur fermée interdite (client_ready=" +
        champs.client_ready +
        ", conformite=" +
        champs.conformite +
        ")",
    };
  }
  return { pass: true, score: 1, reason: "G-002 PASS" };
}

function g003(output, context) {
  const texte = texteCandidate(output);
  if (texte === null) {
    return {
      pass: false,
      score: 0,
      reason: "G-003 FAIL origine CANDIDATE_ERROR: sortie candidate non textuelle",
    };
  }
  const dir = packageDir(context);
  let conforme;
  try {
    conforme = evaluerG003(
      texte,
      path.join(dir, "stimulus.md"),
      path.join(dir, "registre-verite.md")
    );
  } catch (e) {
    throw new Error("HARNESS_ERROR: G-003 entrée de référence illisible (" + e.message + ")");
  }
  if (!conforme) {
    return {
      pass: false,
      score: 0,
      reason:
        "G-003 FAIL origine CANDIDATE_ERROR: référence absente, mal formée, inconnue ou ID interne visible",
    };
  }
  return { pass: true, score: 1, reason: "G-003 PASS" };
}

function g004(output) {
  const champs = parserG001(texteCandidate(output));
  if (champs === null) {
    return {
      pass: false,
      score: 0,
      reason: "G-004 FAIL origine CANDIDATE_ERROR: précondition G-001 non satisfaite",
    };
  }
  if (
    champs.artifact_type !== "pre_cadrage_entretien_client" ||
    champs.version !== "V0" ||
    champs.scenario !== "synthetique" ||
    !["QUALIFIABLE", "NON_QUALIFIABLE"].includes(champs.qualification)
  ) {
    return {
      pass: false,
      score: 0,
      reason: "G-004 FAIL origine CANDIDATE_ERROR: valeur contrôlée hors vocabulaire fermé",
    };
  }
  return { pass: true, score: 1, reason: "G-004 PASS" };
}

module.exports = { g001, g002, g003, g004, g005 };
