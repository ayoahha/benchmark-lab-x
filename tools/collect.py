# /// script
# requires-python = ">=3.12"
# dependencies = ["requests"]
# ///
"""Collecteur d'un appel direct, selon R-004.

Charge les consignes et entrées d'une carte, effectue un appel OpenRouter sur
un provider épinglé, écrit la réponse et son reçu, puis s'arrête. Il ne note
pas, ne boucle pas et ne relance pas.

Codes de sortie stables :
    0  succès
    1  arguments invalides
    2  clé API absente
    3  dossier de carte invalide
    4  assemblage du prompt impossible
    5  erreur HTTP ou transport
    6  erreur renvoyée par l'API
    7  réponse structurellement invalide
    8  modèle ou provider servi différent du pin
    9  dossier de run déjà présent
   10  erreur d'entrée-sortie après réservation
   11  route non conforme au pré-vol, INELIGIBLE sans appel (R-004, R-025)
   12  métadonnées de route inatteignables, INFRA_ERROR sans appel (R-013)

Usage:
    uv run tools/collect.py tasks/dev/<slug> \
        --model openai/gpt-5.6-sol --provider openai --run 1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

import requests

sys.path.insert(0, str(Path(__file__).parent))
from empreintes import empreinte  # noqa: E402

API_URL = "https://openrouter.ai/api/v1/chat/completions"
# Judge-side files never sent to the model
EXCLUDED = {"task.md", "verify.md", "prompt.txt"}
# Files matching these prefixes are also never sent
EXCLUDED_PREFIXES = ("anchor-",)

# Backend réellement traversé. Constante aujourd'hui, mais consignée : R-003
# distingue deux backends comme deux candidats, ce qui suppose que le reçu
# nomme celui qui a servi au lieu de le laisser implicite dans le code
BACKEND = "openrouter"
# Le protocole désigne l'ensemble indissociable collecte + notation (ARD §2.2) :
# tout changement de l'une des deux parties l'incrémente
PROTOCOLE_VERSION = "benchmark-lab-x/protocol/v1"
COLLECTEUR_VERSION = "collect.py/v2"
SCHEMA_MANIFESTE = "benchmark-lab-x/execution-manifest/v1"

# Stable exit codes
EXIT_OK = 0
EXIT_USAGE = 1
EXIT_NO_KEY = 2
EXIT_BAD_TASK = 3
EXIT_PROMPT = 4
EXIT_HTTP = 5
EXIT_API_ERROR = 6
EXIT_VALIDATION = 7
EXIT_ROUTE_MISMATCH = 8
EXIT_EXISTS = 9
EXIT_IO = 10
EXIT_INELIGIBLE = 11
EXIT_INFRA = 12


def die(code: int, msg: str) -> NoReturn:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def load_dotenv_key() -> str | None:
    """Read OPENROUTER_API_KEY from a repo-local .env (gitignored), if any"""
    env_file = Path(".env")
    if not env_file.is_file():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("OPENROUTER_API_KEY="):
            value = line.split("=", 1)[1].strip().strip("'\"")
            return value or None
    return None


def preflight_key() -> str:
    """Require a key; repo-local .env (dedicated campaign key) wins over the
    shell environment. Never print its value"""
    key = load_dotenv_key()
    if key:
        print("key source: .env (repo-local, gitignored)", file=sys.stderr)
        return key
    key = os.environ.get("OPENROUTER_API_KEY")
    if key is None or not str(key).strip():
        die(EXIT_NO_KEY, "OPENROUTER_API_KEY not set (env var or repo .env; never displayed)")
    print("key source: environment variable", file=sys.stderr)
    return str(key).strip()


def is_excluded(name: str) -> bool:
    if name in EXCLUDED:
        return True
    return any(name.startswith(p) for p in EXCLUDED_PREFIXES)


def assemble_prompt(task_dir: Path) -> tuple[str, dict[str, str], list[str]]:
    """Assembler le message utilisateur sans réécrire les entrées de la carte

    Les consignes viennent de prompt.txt ou du bloc cité sous
    « Consignes visibles par le modèle » dans task.md. Seul le préfixe de
    citation est retiré. Chaque fichier Markdown non exclu est ensuite ajouté
    dans l’ordre lexical. Retourne le prompt, les entrées et les avertissements
    """
    warnings: list[str] = []
    override = task_dir / "prompt.txt"
    if override.exists():
        # Canonical override: raw bytes decoded, no newline translation
        instructions = override.read_bytes().decode("utf-8").strip()
        if not instructions:
            die(EXIT_PROMPT, "prompt.txt is empty")
    else:
        card = (task_dir / "task.md").read_bytes().decode("utf-8")
        # Les cartes sont en français ; le titre suit le contrat tasks/TEMPLATE.md
        m = re.search(
            r"^## Consignes visibles par le modèle.*?\n(.*?)(?=^## )",
            card,
            re.DOTALL | re.MULTILINE,
        )
        if not m:
            die(EXIT_PROMPT, "no 'Consignes visibles par le modèle' section in task.md")

        def dequote(line: str) -> str:
            # Remove exactly one "> " (or bare ">") quote prefix, nothing else
            return line[2:] if line.startswith("> ") else line[1:]

        quoted = [line for line in m.group(1).splitlines() if line.startswith(">")]
        instructions = "\n".join(dequote(line) for line in quoted).strip()
        if not instructions:
            die(EXIT_PROMPT, "empty instructions block in task.md")

    inputs: dict[str, str] = {}
    for f in sorted(task_dir.glob("*.md")):
        if is_excluded(f.name):
            continue
        if f.is_symlink():
            warnings.append(f"symlink refused, not sent to model: {f.name}")
            continue
        # Byte-faithful read: raw bytes decoded, no newline translation, no rewrite
        inputs[f.name] = f.read_bytes().decode("utf-8")

    # Warn about non-md files and other paths not covered by the send set
    covered = set(inputs) | EXCLUDED | {override.name if override.exists() else ""}
    for path in sorted(task_dir.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        if name in covered or is_excluded(name):
            continue
        if name.startswith("."):
            continue
        warnings.append(f"file not sent to model (not in input manifest): {name}")

    parts = [instructions]
    for name, content in inputs.items():
        parts.append(f"\n--- FILE: {name} ---\n{content}")
    return "\n".join(parts), inputs, warnings


def redact_http_body(text: str) -> str:
    """Strip Authorization-like secrets from an error body before disk write"""
    redacted = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)\S+",
        r"\1[REDACTED]",
        text,
    )
    redacted = re.sub(
        r"(?i)(api[_-]?key\s*[:=]\s*)\S+",
        r"\1[REDACTED]",
        redacted,
    )
    # OpenRouter sk-or-... style tokens if they leaked into the body
    redacted = re.sub(r"\bsk-[a-zA-Z0-9_-]{8,}\b", "[REDACTED]", redacted)
    return redacted


def normalize_cost_usd(usage: Any) -> float | None:
    """Coût réel de l'appel, en dollars.

    `cost` vaut 0 sur les routes facturées en direct par le fournisseur plutôt
    qu'en crédits OpenRouter (`is_byok`). Le coût réel est alors dans
    `cost_details.upstream_inference_cost`, et retenir le zéro fausserait le
    diagnostic de coût publié au titre de R-021. Observé le 2026-08-05 sur la
    route de premier rang de DeepSeek : `cost = 0` pour 0,0176 $ réellement dus
    """
    if not isinstance(usage, dict):
        return None
    facture = None
    for key in ("cost", "total_cost", "cost_usd"):
        val = usage.get(key)
        if val is None:
            continue
        try:
            facture = float(val)
            break
        except (TypeError, ValueError):
            continue
    amont = None
    details = usage.get("cost_details")
    if isinstance(details, dict):
        try:
            amont = float(details.get("upstream_inference_cost"))
        except (TypeError, ValueError):
            amont = None
    if facture is not None and facture > 0:
        return facture
    if amont is not None and amont > 0:
        return amont
    return facture


def extract_provider_served(data: dict[str, Any]) -> str | None:
    """Best-effort provider id from a chat-completions payload"""
    raw = data.get("provider")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, dict):
        for key in ("slug", "id", "name"):
            val = raw.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def validate_response(data: Any) -> tuple[str, dict[str, Any]]:
    """Exiger choices et extraire content

    Une sortie vide est un défaut d’infrastructure, sauf si finish_reason vaut
    length. Dans ce cas, elle est conservée et son imputabilité est décidée par
    le contrôle de conformité selon R-013 et R-025
    """
    if not isinstance(data, dict):
        die(EXIT_VALIDATION, "response is not a JSON object")
    if "error" in data and data["error"]:
        # Caller should have branched earlier; treat as validation miss
        die(EXIT_API_ERROR, "response contains error object")
    choices = data.get("choices")
    if not isinstance(choices, list) or len(choices) == 0:
        die(EXIT_VALIDATION, "choices missing or empty")
    first = choices[0]
    if not isinstance(first, dict):
        die(EXIT_VALIDATION, "choices[0] is not an object")
    message = first.get("message")
    if not isinstance(message, dict):
        die(EXIT_VALIDATION, "choices[0].message missing or not an object")
    if first.get("error"):
        die(EXIT_API_ERROR, "choices[0] carries an error object (HTTP 200 masking a failure)")
    if first.get("finish_reason") == "error":
        die(EXIT_API_ERROR, "finish_reason=error (HTTP 200 masking a failure)")
    content = message.get("content")
    finish_reason = first.get("finish_reason")
    # Une sortie vide avec finish_reason=length reste COMPLETE ; R-013 décide l’imputabilité
    if content is None:
        if finish_reason == "length":
            return "", first
        die(EXIT_VALIDATION, "choices[0].message.content is null (infrastructure invalid)")
    if not isinstance(content, str):
        die(EXIT_VALIDATION, "choices[0].message.content is not a string")
    if not content.strip():
        if finish_reason == "length":
            return content, first
        die(EXIT_VALIDATION, "choices[0].message.content is empty or whitespace (infrastructure invalid)")
    return content, first


def atomic_write_text(path: Path, text: str) -> None:
    """Write via sibling tmp + os.replace"""
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


# Request summary appended to every FAILED receipt so failed runs keep their
# parameters (timeout, reasoning cap, hashes); set once in main after the
# request body is final, empty before that point
REQUEST_NOTE: str = ""


def mark_failed(out: Path, reason: str, detail: str | None = None) -> None:
    """Leave a single FAILED marker file carrying reason and redacted receipt.

    One file, not a sibling directory: on case-insensitive filesystems (APFS)
    a 'failed/' directory would collide with the 'FAILED' marker
    """
    try:
        body = reason + "\n"
        if detail is not None:
            body += "\n" + redact_http_body(detail) + "\n"
        if REQUEST_NOTE:
            body += "\nrequest: " + REQUEST_NOTE + "\n"
        (out / "FAILED").write_text(body, encoding="utf-8")
    except OSError as exc:
        print(f"warning: could not write FAILED receipt: {exc}", file=sys.stderr)


def cleanup_or_fail(out: Path, reason: str, detail: str | None = None) -> None:
    """On post-reservation failure: mark FAILED (keep dir for diagnosis)"""
    mark_failed(out, reason, detail)


def marquer_etat(out: Path, etat: str, motif: str, detail: dict[str, Any]) -> None:
    """Poser un marqueur d'état terminal R-013, lisible par machine.

    `FAILED` reste la preuve brute d'un appel qui a mal tourné ; il ne dit pas
    dans quel état R-013 termine le run attendu. `INELIGIBLE` et `INFRA_ERROR`
    sont ces états, et ils se distinguent : le premier signifie que la route
    était non conforme avant toute tentative et vaut pour tous les runs du
    couple carte-configuration, le second qu'aucune tentative autorisée n'a
    abouti. Le corps est du JSON pour que l'agrégateur n'ait rien à deviner
    """
    corps = {"etat": etat, "motif": motif, "date": datetime.now(timezone.utc).isoformat()}
    corps.update(detail)
    try:
        (out / etat).write_text(
            json.dumps(corps, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        print(f"warning: could not write {etat} receipt: {exc}", file=sys.stderr)


def regime_de_la_carte(task_md: Path) -> str | None:
    """Régime de confidentialité déclaré par la carte, s'il l'est.

    Le régime est une propriété de la carte, pas de la ligne de commande : une
    carte du jeu retenu ne doit pas pouvoir être collectée sous un régime
    permissif par oubli d'un drapeau. La ligne de commande ne peut que durcir
    """
    try:
        texte = task_md.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"^-\s*\*\*Régime de confidentialité\*\*\s*:\s*(\w+)", texte, re.M)
    if not m:
        return None
    valeur = m.group(1).lower()
    return {"exposé": "expose", "expose": "expose", "retenu": "retenu"}.get(valeur)


def version_de_la_carte(task_md: Path) -> str | None:
    """Étiquette `task-vN` déclarée par la carte (R-015).

    Le reçu de collecte doit la conserver : sans elle, deux campagnes séparées
    par une réécriture des consignes se comparent sans que rien ne le signale
    """
    try:
        texte = task_md.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"\btask-v(\d+)\b", texte)
    return f"task-v{m.group(1)}" if m else None


# Le budget de sortie doit laisser de la place au prompt : sur certaines routes
# `max_completion_tokens` égale `context_length`, et demander tout le budget en
# sortie fait dépasser le contexte total. Constaté le 2026-08-05 sur tencent/hy3,
# qui déclare 262144 pour les deux : quatre runs perdus
MARGE_PROMPT = 8192


def _endpoint_epingle(endpoints: list[dict[str, Any]], provider: str) -> dict[str, Any] | None:
    """Retrouver l'endpoint réellement épinglé parmi ceux du modèle.

    Le pin de `models.toml` est un slug (`modal`, `xai`) ; l'API rend un nom
    d'affichage (`Modal`, `xAI`) et une étiquette éventuellement suffixée par
    la quantification (`modal/mxfp4`). Les trois formes sont rapprochées
    """
    cible = re.sub(r"[\s_]+", "-", provider.strip().lower())
    for e in endpoints:
        noms = {
            re.sub(r"[\s_]+", "-", str(e.get("provider_name") or "").strip().lower()),
            str(e.get("tag") or "").strip().lower(),
            str(e.get("tag") or "").strip().lower().split("/")[0],
        }
        if cible in noms:
            return e
    return None


def resoudre_budget(
    model: str, provider: str, plancher: int, plafond: int, tentatives: int, pause: float = 3.0
) -> dict[str, Any]:
    """Budget de sortie résolu avant l'appel depuis ce que la route déclare (R-025).

    Rend un verdict, jamais un nombre nu, parce que trois issues sont possibles
    et qu'une seule autorise l'appel :

    - `ok` : la route déclare une limite exploitable, bornée par le plafond
    - `ineligible` : la route déclare moins que le plancher, ou n'existe pas.
      R-025 l'exige sans appel. La version précédente faisait `max(plancher,
      brut)` puis appelait quand même, ce qui envoyait au modèle un budget que
      sa route n'accorde pas : le stimulus mesuré n'était plus celui déclaré
    - `infra` : les métadonnées de route sont restées inatteignables après les
      tentatives autorisées. Retomber sur le plancher reviendrait à inventer un
      nombre sans source, ce que R-025 interdit tout autant

    La résolution porte sur l'endpoint épinglé et sur lui seul. Prendre le
    maximum sur tous les endpoints, comme le faisait la version précédente,
    pouvait tirer le budget d'un fournisseur que l'appel ne traverse jamais
    """
    url = f"https://openrouter.ai/api/v1/models/{model}/endpoints"
    dernier = ""
    for essai in range(1, max(1, tentatives) + 1):
        try:
            r = requests.get(url, headers={"Accept": "application/json"}, timeout=15)
            # Un 4xx autre que 429 est une non-conformité permanente, pas une
            # panne : le modèle n'existe pas sous cet identifiant, et relancer
            # trois fois ne le fera pas apparaître. R-004 en fait un INELIGIBLE
            # au pré-vol, pas un INFRA_ERROR
            if 400 <= r.status_code < 500 and r.status_code != 429:
                return {"etat": "ineligible", "motif": "modele_inconnu_du_backend",
                        "detail": f"HTTP {r.status_code} sur {model}"}
            r.raise_for_status()
            data = r.json().get("data", {})
            break
        except Exception as e:
            dernier = f"{type(e).__name__}: {str(e)[:120]}"
            if essai < tentatives:
                print(f"  métadonnées de route indisponibles ({dernier}), "
                      f"tentative {essai}/{tentatives}", file=sys.stderr)
                time.sleep(pause * essai)
    else:
        # Cette requête est une lecture de métadonnées publiques : elle ne
        # consomme aucun jeton et ne coûte rien. La borne protège la durée de
        # la campagne, pas son budget
        return {"etat": "infra", "motif": "metadonnees_route_inatteignables",
                "detail": dernier, "tentatives": tentatives}

    endpoints = data.get("endpoints") or []
    ep = _endpoint_epingle(endpoints, provider)
    if ep is None:
        connus = sorted({str(e.get("tag") or e.get("provider_name")) for e in endpoints})
        return {"etat": "ineligible", "motif": "provider_epingle_absent_de_la_route",
                "detail": f"pin {provider!r} introuvable ; endpoints déclarés : {connus}"}

    mc, ctx = ep.get("max_completion_tokens"), ep.get("context_length")
    if isinstance(mc, int) and mc > 0:
        brut, origine = mc, "max_completion_tokens"
    elif isinstance(ctx, int) and ctx > 0:
        # Source secondaire assumée et nommée : certains endpoints ne déclarent
        # pas de limite de complétion mais bien un contexte total. Le nombre a
        # alors une source vérifiable, ce que le plancher n'avait pas
        brut, origine = ctx, "context_length"
    else:
        return {"etat": "ineligible", "motif": "route_sans_limite_declaree",
                "detail": f"{ep.get('tag')} ne déclare ni max_completion_tokens ni context_length"}

    if isinstance(ctx, int) and ctx > 0:
        brut = min(brut, ctx - MARGE_PROMPT)

    # `model_id` de l'endpoint est le seul identifiant daté qu'OpenRouter expose
    # (`moonshotai/kimi-k3-20260715`) : c'est ce qui se rapproche le plus d'une
    # révision au sens R-004. Il ne prouve pas un binaire, seulement un endpoint
    # observé sous cette étiquette à cette date
    # Quand l'endpoint répète l'identifiant demandé, il n'apporte aucune
    # révision : consigner cette chaîne la ferait passer pour une information
    # que le fournisseur n'a pas donnée
    mid = ep.get("model_id")
    # La quantification servie est une propriété structurelle de la route, au
    # même titre que l'effort de raisonnement : elle change les poids réellement
    # évalués. Elle entre donc au manifeste d'exécution, sans quoi deux mesures
    # du même modèle en `bf16` et en `mxfp4` porteraient la même identité de
    # configuration
    commun = {"endpoint": ep.get("tag") or ep.get("provider_name"),
              "quantization": ep.get("quantization") or "non déclarée",
              "revision": mid if (mid and mid != model) else "opaque",
              "declare": {"max_completion_tokens": mc, "context_length": ctx},
              "marge_prompt": MARGE_PROMPT}
    if brut < plancher:
        return {"etat": "ineligible", "motif": "budget_de_route_sous_le_plancher",
                "detail": f"la route accorde {brut} jetons de sortie, plancher {plancher}",
                **commun}
    budget = min(brut, plafond)
    source = (f"route/{origine} ({brut})" if budget == brut
              else f"plafond de campagne (la route accorde {brut} via {origine})")
    return {"etat": "ok", "budget": budget, "source": source, **commun}


def main() -> None:
    ap = argparse.ArgumentParser(description="benchmark-lab-x call collector")
    ap.add_argument("task_dir", type=Path)
    ap.add_argument("--model", help="OpenRouter model id (or use --alias)")
    ap.add_argument("--provider", help="pinned provider (provider.only) (or use --alias)")
    ap.add_argument(
        "--alias",
        default=None,
        help="model alias resolved from models.toml (fields: model, provider, expect_provider)",
    )
    ap.add_argument(
        "--models-file",
        type=Path,
        default=Path("models.toml"),
        help="registry used by --alias (default: ./models.toml)",
    )
    ap.add_argument("--run", type=int, default=1, help="numéro de run, de 1 à 4")
    ap.add_argument("--attempt", type=int, default=1, help="attempt number after a FAILED run (evidence is never deleted)")
    ap.add_argument("--temperature", type=float, default=0.0)
    # Le budget de sortie n'est plus une constante. À 16384 puis à 65536, des
    # modèles ont consommé tout le budget en raisonnement et rendu zéro octet :
    # le classement mesurait le plafond, pas les modèles. Or aucune route du
    # panel ne descend en dessous de 128000 jetons de complétion, et deux en
    # déclarent 1048576. Le plafond ne protégeait donc rien, il bloquait
    # `auto` résout le budget avant l'appel, depuis ce que la route déclare :
    # pas de relance, pas d'escalade, et le modèle reçoit d'emblée le maximum
    # que son fournisseur autorise, borné par --plafond-tokens
    ap.add_argument("--max-tokens", default="auto",
                    help="budget de sortie : 'auto' (défaut, résolu depuis la route) ou un entier")
    ap.add_argument("--plancher-tokens", type=int, default=65536,
                    help="budget minimal exigé de la route ; en dessous, INELIGIBLE (défaut: 65536)")
    ap.add_argument("--budget-tentatives", type=int, default=3,
                    help="lectures des métadonnées de route avant INFRA_ERROR ; "
                         "requête gratuite, la borne protège la durée (défaut: 3)")
    # Régime de confidentialité, R-005 scindée le 2026-08-05
    # `retenu` (défaut) : seules les routes qui ne s'entraînent pas sur les
    # requêtes sont acceptables. C'est le régime des cartes du jeu retenu, dont
    # une fuite ne coûte pas une carte mais toute la série de régression
    # `expose` : les routes qui s'entraînent sur les requêtes sont acceptées,
    # parce que la carte est déjà publique dans le dépôt et que la protection
    # serait une ligne Maginot. Le provider servi reste consigné
    ap.add_argument("--regime", choices=("retenu", "expose"), default="retenu",
                    help="régime de confidentialité de la carte (défaut: retenu, le plus strict)")
    ap.add_argument("--plafond-tokens", type=int, default=262144,
                    help="budget maximal, borne le coût du pire cas (défaut: 262144)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="HTTP timeout in seconds (default: 600)",
    )
    ap.add_argument(
        "--expect-provider",
        default=None,
        help="expected provider display name when it differs from the pin slug (e.g. pin google-vertex, served Google)",
    )
    ap.add_argument("--out-root", type=Path, default=Path("runs") / date.today().isoformat())
    args = ap.parse_args()

    reasoning_max_tokens: int | None = None
    reasoning_effort: str | None = None
    if args.alias:
        if args.model or args.provider:
            die(EXIT_USAGE, "--alias replaces --model/--provider; do not mix them")
        if not args.models_file.is_file():
            die(EXIT_USAGE, f"{args.models_file} not found (needed by --alias)")
        import tomllib

        try:
            registry = tomllib.loads(args.models_file.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            die(EXIT_USAGE, f"invalid {args.models_file}: {exc}")
        entry = registry.get(args.alias)
        if not isinstance(entry, dict) or "model" not in entry or "provider" not in entry:
            known = ", ".join(sorted(k for k, v in registry.items() if isinstance(v, dict)))
            die(EXIT_USAGE, f"alias {args.alias!r} not in {args.models_file} (known: {known})")
        args.model = entry["model"]
        args.provider = entry["provider"]
        if not args.expect_provider and entry.get("expect_provider"):
            args.expect_provider = entry["expect_provider"]
        omit_params = entry.get("omit_params", [])
        if omit_params and not isinstance(omit_params, list):
            die(EXIT_USAGE, "omit_params must be a list of parameter names")
        raw_rmt = entry.get("reasoning_max_tokens")
        if raw_rmt is not None:
            if not isinstance(raw_rmt, int) or isinstance(raw_rmt, bool) or raw_rmt < 1:
                die(EXIT_USAGE, "reasoning_max_tokens must be a positive integer")
            reasoning_max_tokens = raw_rmt
        raw_eff = entry.get("reasoning_effort")
        if raw_eff is not None:
            # Liste blanche retirée le 2026-08-05 : elle refusait `max`, une
            # valeur que certains fournisseurs exposent réellement, et le refus
            # venait de nous et non de l'API. Une liste blanche locale sur un
            # espace de valeurs que nous ne contrôlons pas rend certains
            # candidats intestables sans qu'aucune mesure le justifie
            # Le vrai garde-fou est ailleurs : une valeur peut être acceptée
            # puis ignorée en silence, et seule la comparaison de consommation
            # de jetons de raisonnement entre deux efforts le montre (R-003)
            if not isinstance(raw_eff, str) or not raw_eff.strip():
                die(EXIT_USAGE, "reasoning_effort must be a non-empty string")
            reasoning_effort = raw_eff.strip()
    else:
        omit_params = []
    if not args.model or not args.provider:
        die(EXIT_USAGE, "--model and --provider are required (or --alias)")

    # Quatre runs par candidat depuis le 2026-08-05 : le niveau retenu est le
    # troisième meilleur des quatre (R-019), ce qui tolère un mauvais tirage
    if args.run not in (1, 2, 3, 4):
        die(EXIT_USAGE, "--run must be between 1 and 4 (campaign invariant)")
    if args.attempt < 1:
        die(EXIT_USAGE, "--attempt must be >= 1")
    if args.timeout < 1:
        die(EXIT_USAGE, "--timeout must be >= 1")
    declare = regime_de_la_carte(Path(args.task_dir) / "task.md")
    if declare == "retenu" and args.regime == "expose":
        die(EXIT_USAGE, "la carte déclare le régime retenu : --regime expose est refusé (R-005a)")
    if declare and args.regime == "retenu":
        args.regime = declare
    print(f"régime de confidentialité: {args.regime}"
          f"{' (déclaré par la carte)' if declare else ' (défaut, la carte ne déclare rien)'}",
          file=sys.stderr)

    if args.max_tokens != "auto":
        try:
            int(args.max_tokens)
        except ValueError:
            die(EXIT_USAGE, "--max-tokens must be 'auto' or an integer")
    if args.budget_tentatives < 1:
        die(EXIT_USAGE, "--budget-tentatives must be >= 1")
    if args.temperature != 0.0 or args.seed != 42:
        print(
            "avertissement : les paramètres d'échantillonnage divergent du contrat "
            "de campagne (température 0, seed 42) ; l'écart est consigné dans meta.json",
            file=sys.stderr,
        )

    key = preflight_key()

    if not args.task_dir.is_dir():
        die(EXIT_BAD_TASK, f"{args.task_dir} is not a directory")
    if not (args.task_dir / "task.md").exists():
        die(EXIT_BAD_TASK, f"{args.task_dir} is not a task folder (missing task.md)")

    try:
        prompt, inputs, warnings = assemble_prompt(args.task_dir)
    except SystemExit:
        raise
    except OSError as exc:
        die(EXIT_PROMPT, f"failed to read task files: {exc}")

    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)

    slug = args.task_dir.name
    # Le candidat est le couple (modèle, route, effort de raisonnement), pas le
    # seul modèle : deux alias du même modèle à des efforts différents sont deux
    # candidats. Nommer le dossier sur le modèle seul les faisait entrer en
    # collision et le second run était refusé
    model_slug = re.sub(r"[^a-zA-Z0-9.-]+", "-", args.alias or args.model)
    suffix = f"__a{args.attempt}" if args.attempt > 1 else ""
    out = args.out_root / f"{slug}__{model_slug}__r{args.run}{suffix}"
    if out.exists():
        hint = (
            "previous attempt is FAILED evidence, keep it and pass --attempt "
            f"{args.attempt + 1}"
            if (out / "FAILED").exists()
            else "runs are never overwritten or deleted"
        )
        die(EXIT_EXISTS, f"{out} already exists ({hint})")

    # P0: reserve the run directory before the network call
    try:
        out.mkdir(parents=True)
    except OSError as exc:
        die(EXIT_IO, f"could not reserve {out}: {exc}")

    # Le budget se résout après la réservation du dossier et avant l'appel : les
    # deux verdicts d'arrêt de R-025 sont des états terminaux R-013 et doivent
    # laisser un reçu quelque part. « Avant toute tentative » qualifie l'appel
    # au modèle, pas la création du dossier
    if args.max_tokens == "auto":
        verdict = resoudre_budget(args.model, args.provider, args.plancher_tokens,
                                  args.plafond_tokens, args.budget_tentatives)
        if verdict["etat"] == "ineligible":
            marquer_etat(out, "INELIGIBLE", verdict["motif"],
                         {"regle": "R-025", "modele": args.model, "provider": args.provider,
                          **{k: v for k, v in verdict.items() if k not in ("etat", "motif")}})
            die(EXIT_INELIGIBLE,
                f"route inéligible sans appel : {verdict['motif']} — {verdict.get('detail')}")
        if verdict["etat"] == "infra":
            marquer_etat(out, "INFRA_ERROR", verdict["motif"],
                         {"regle": "R-013", "modele": args.model, "provider": args.provider,
                          **{k: v for k, v in verdict.items() if k not in ("etat", "motif")}})
            die(EXIT_INFRA,
                f"métadonnées de route inatteignables après {args.budget_tentatives} "
                f"tentatives : {verdict.get('detail')}")
        budget, source_budget = verdict["budget"], verdict["source"]
        budget_route = {k: verdict.get(k) for k in
                        ("endpoint", "quantization", "revision", "declare", "marge_prompt")}
    else:
        budget, source_budget = int(args.max_tokens), "imposé en ligne de commande"
        budget_route = {"endpoint": None, "quantization": "opaque", "revision": "opaque",
                        "declare": None, "marge_prompt": None}
    args.max_tokens = budget
    print(f"budget de sortie: {budget} jetons, source: {source_budget}", file=sys.stderr)

    if reasoning_max_tokens is not None and reasoning_max_tokens >= args.max_tokens:
        marquer_etat(out, "INELIGIBLE", "reasoning_max_tokens_superieur_au_budget",
                     {"regle": "R-025", "reasoning_max_tokens": reasoning_max_tokens,
                      "max_tokens": args.max_tokens, "source_budget": source_budget})
        die(EXIT_INELIGIBLE,
            f"reasoning_max_tokens ({reasoning_max_tokens}) >= budget résolu "
            f"({args.max_tokens}) : la configuration ne laisse aucun jeton de réponse")

    body: dict[str, Any] = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": args.temperature,
        "top_p": 1,
        "max_tokens": args.max_tokens,
        "seed": args.seed,
        "provider": {
            "only": [args.provider],
            "allow_fallbacks": False,
            "require_parameters": True,
            "data_collection": "allow" if args.regime == "expose" else "deny",
        },
        "usage": {"include": True},
    }
    if reasoning_max_tokens is not None:
        body["reasoning"] = {"max_tokens": reasoning_max_tokens}
    # effort and max_tokens are mutually exclusive on OpenRouter's reasoning
    # object: effort wins when the registry sets it
    if reasoning_effort is not None:
        body["reasoning"] = {"effort": reasoning_effort}
    # Documented deviation: some pinned endpoints reject require_parameters
    # when a sampling knob is unsupported (e.g. seed); the registry may omit
    # those knobs explicitly and the omission is recorded in meta.json
    allowed_omissions = {"seed", "top_p", "temperature"}
    for name in omit_params:
        if name not in allowed_omissions:
            die(EXIT_USAGE, f"omit_params entry {name!r} not allowed (only {sorted(allowed_omissions)})")
        body.pop(name, None)
        print(f"warning: parameter {name!r} omitted for this endpoint (declared in registry)", file=sys.stderr)
    # Canonical JSON for payload hash (stable separators, sorted keys)
    payload_bytes = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    payload_hash = hashlib.sha256(payload_bytes).hexdigest()

    global REQUEST_NOTE
    REQUEST_NOTE = json.dumps(
        {
            "model": args.model,
            "provider": args.provider,
            "regime_confidentialite": args.regime,
        "params": {k: body[k] for k in ("temperature", "top_p", "max_tokens", "seed", "reasoning") if k in body},
            "timeout_s": args.timeout,
            "budget_sortie": {"max_tokens": args.max_tokens, "source": source_budget},
            "payload_hash": payload_hash,
        },
        ensure_ascii=False,
    )

    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    try:
        resp = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            data=payload_bytes,
            timeout=args.timeout,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        cleanup_or_fail(out, "http_transport", redact_http_body(str(exc)))
        die(EXIT_HTTP, f"HTTP transport failed: {redact_http_body(str(exc))}")

    if resp.is_redirect or resp.is_permanent_redirect:
        cleanup_or_fail(out, f"http_redirect_{resp.status_code}")
        die(EXIT_HTTP, f"unexpected redirect HTTP {resp.status_code} (single-request contract)")

    duration = time.monotonic() - t0

    if not resp.ok:
        cleanup_or_fail(
            out,
            f"http_{resp.status_code}",
            redact_http_body(resp.text),
        )
        die(EXIT_HTTP, f"HTTP {resp.status_code} (redacted receipt in {out / 'FAILED'})")

    # Empty/whitespace HTTP body is infrastructure-invalid (never judged)
    if not resp.text or not resp.text.strip():
        cleanup_or_fail(out, "empty_body", "(empty or whitespace HTTP body)")
        die(EXIT_VALIDATION, "response body is empty or whitespace (infrastructure invalid)")

    try:
        data = resp.json()
    except ValueError:
        cleanup_or_fail(out, "invalid_json", redact_http_body(resp.text))
        die(EXIT_VALIDATION, "response body is not valid JSON")

    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        # Never dump secrets; serialize error object only
        detail = redact_http_body(json.dumps(err, ensure_ascii=False, indent=2))
        cleanup_or_fail(out, "api_error", detail)
        die(EXIT_API_ERROR, "API returned error object (see FAILED receipt)")

    try:
        content, first_choice = validate_response(data)
    except SystemExit:
        # Full raw payload preserved as evidence (redacted), no truncation
        cleanup_or_fail(
            out,
            "validation",
            redact_http_body(json.dumps(data, ensure_ascii=False, indent=2)),
        )
        raise

    model_served = data.get("model") if isinstance(data.get("model"), str) else None
    provider_served = extract_provider_served(data)

    # OpenRouter returns the provider as a display name ("OpenAI") while the
    # pin is a slug ("openai"): compare on a normalized form, still fail-closed
    def normalize_route(value: str | None) -> str | None:
        if value is None:
            return None
        return re.sub(r"[\s_]+", "-", value.strip().lower())

    expected_providers = {normalize_route(args.provider)}
    if args.expect_provider:
        expected_providers.add(normalize_route(args.expect_provider))
    provider_ok = normalize_route(provider_served) in expected_providers
    model_ok = normalize_route(model_served) == normalize_route(args.model)

    if not model_ok or not provider_ok:
        cleanup_or_fail(
            out,
            "route_mismatch",
            (
                f"model_requested={args.model!r} model_served={model_served!r}\n"
                f"provider_pinned={args.provider!r} provider_served={provider_served!r}\n"
                "full raw response:\n"
                + redact_http_body(json.dumps(data, ensure_ascii=False, indent=2))
            ),
        )
        die(
            EXIT_ROUTE_MISMATCH,
            (
                f"route mismatch: model_served={model_served!r} "
                f"(wanted {args.model!r}), provider_served={provider_served!r} "
                f"(wanted {args.provider!r}); run invalid: "
                f"folder marked FAILED under {out}"
            ),
        )

    finish_reason = first_choice.get("finish_reason")
    if finish_reason == "length":
        print(
            "warning: finish_reason=length; R-013 tranche à la notation en "
            "comparant completion_tokens au budget RÉSOLU, pas au plancher : "
            "au-dessus ou égal, le budget est prouvé épuisé et le run vaut FAIL ; "
            "en dessous, le fournisseur a coupé tôt et le run vaut UNKNOWN",
            file=sys.stderr,
        )

    usage = data.get("usage")
    cost_usd = normalize_cost_usd(usage)

    # An empty output can only be attributed with the usage token split as
    # evidence; without it the run is infrastructure-invalid, not judgeable
    if finish_reason == "length" and not content.strip() and not isinstance(usage, dict):
        cleanup_or_fail(out, "length_without_usage")
        die(
            EXIT_VALIDATION,
            "empty output with finish_reason=length but no usage data: "
            "attribution cannot be evidenced (infrastructure invalid)",
        )

    # Input fidelity manifest: every file body actually placed in the prompt
    input_manifest = {
        name: {
            "sha256_16": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
            "bytes": len(text.encode("utf-8")),
        }
        for name, text in inputs.items()
    }

    params: dict[str, Any] = {
        k: body[k]
        for k in ("temperature", "top_p", "max_tokens", "seed")
        if k in body
    }
    if "reasoning" in body:
        params["reasoning"] = body["reasoning"]

    # Politique de données : R-004 demande de la consigner, mais l'API
    # `/endpoints` d'OpenRouter n'expose plus `data_policy` par endpoint. Nous
    # consignons donc ce que nous contrôlons réellement, la valeur demandée, et
    # marquons `opaque` ce que le fournisseur ne publie plus. Voir le point
    # ouvert de l'audit du 2026-08-06 : c'est la règle qui doit bouger, pas le
    # code, si l'on veut mieux qu'un `opaque` ici
    politique_donnees = {
        "demandee": body["provider"]["data_collection"],
        "route": "opaque",
        "regime": args.regime,
    }
    # Chaque paramètre porte sa provenance (ARD §2.2) : `campaign` pour un
    # réglage de campagne, `candidate` pour ce que le registre attache au
    # candidat, `route_default` pour ce que la route impose
    def provenance(nom: str) -> str:
        if nom == "max_tokens":
            return "route_default" if source_budget.startswith("route/") else "campaign"
        return "candidate" if nom == "reasoning" else "campaign"

    manifeste = {
        "schema_version": SCHEMA_MANIFESTE,
        "mode": "direct",
        "model": {
            "requested": args.model,
            "served": model_served,
            "revision": budget_route.get("revision") or "opaque",
        },
        "route": {
            "backend": BACKEND,
            "provider_requested": args.provider,
            "provider_served": provider_served,
            "quantization": budget_route.get("quantization") or "opaque",
        },
        "reasoning": {
            "effort": reasoning_effort,
            "max_tokens": reasoning_max_tokens,
        },
        "system_prompt_hash": None,  # aucun message système en mode direct
        "parameters": {k: {"value": v, "source": provenance(k)} for k, v in params.items()},
        "data_policy": politique_donnees,
        "runner_version": COLLECTEUR_VERSION,
        "protocol_version": PROTOCOLE_VERSION,
        # L'environnement d'exécution du candidat est celui du fournisseur : il
        # n'est pas observable depuis ici. `opaque` est la valeur prévue par
        # l'ARD pour une information non publiée, et vaut mieux qu'un descripteur
        # de notre hôte, qui décrirait la mauvaise machine
        "environment_hash": "opaque",
        "tools": [],
        "agent": None,
    }

    meta = {
        "task": slug,
        "task_version": version_de_la_carte(args.task_dir / "task.md") or "inconnue",
        "run": args.run,
        "date": started.isoformat(),
        "duration_s": round(duration, 2),
        "backend": BACKEND,
        "model_requested": args.model,
        "model_served": model_served,
        "revision": budget_route.get("revision") or "opaque",
        "provider_pinned": args.provider,
        "provider_served": provider_served,
        "quantization_servie": budget_route.get("quantization") or "opaque",
        "regime_confidentialite": args.regime,
        "politique_donnees": politique_donnees,
        "params": params,
        "params_omitted": sorted(omit_params),
        # R-025 : la valeur ne suffit pas, sa provenance fait partie du reçu.
        # Sans elle, un budget égal au plancher est indiscernable d'un budget
        # relevé de force, et douze runs de la campagne de référence sont
        # restés ambigus pour cette seule raison
        "budget_sortie": {
            "max_tokens": args.max_tokens,
            "source": source_budget,
            "plancher": args.plancher_tokens,
            "plafond": args.plafond_tokens,
            **budget_route,
        },
        "timeout_s": args.timeout,
        "usage": usage,
        "cost_usd": cost_usd,
        "finish_reason": finish_reason,
        "input_manifest": input_manifest,
        # Kept for older grid readers; same hashes as input_manifest
        "input_hashes": {name: info["sha256_16"] for name, info in input_manifest.items()},
        # Empreintes complètes, 64 hexadécimaux, comme l'exige l'ARD §2.2. Les
        # reçus antérieurs au 2026-08-06 les portent tronquées à 16 : elles ne
        # se comparent pas entre les deux formats, ce que la version de
        # protocole signale
        "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "payload_hash": payload_hash,
        "execution_manifest": manifeste,
        "execution_manifest_hash": empreinte(manifeste),
        "protocol_version": PROTOCOLE_VERSION,
        "runner_version": COLLECTEUR_VERSION,
        "files_sent": sorted(input_manifest.keys()),
        "assembly": (
            "prompt.txt override"
            if (args.task_dir / "prompt.txt").exists()
            else "task.md instructions block + FILE sections"
        ),
    }
    # Invariant: meta/raw never hold the API key
    meta_text = json.dumps(meta, indent=2, ensure_ascii=False)
    raw_text = json.dumps(data, indent=2, ensure_ascii=False)
    if key in meta_text or key in raw_text or key in content:
        cleanup_or_fail(out, "key_leak_guard", "API key appeared in payload to write")
        die(EXIT_IO, "refusing to write: API key would appear in run artifacts")

    try:
        atomic_write_text(out / "response.md", content)
        atomic_write_text(out / "raw.json", raw_text + "\n")
        atomic_write_text(out / "meta.json", meta_text + "\n")
        # Run-level commit marker, written last: a folder without COMPLETE
        # was interrupted and must not be judged
        atomic_write_text(out / "COMPLETE", started.isoformat() + "\n")
    except OSError as exc:
        cleanup_or_fail(out, "write_failed", str(exc))
        die(EXIT_IO, f"failed to write run artifacts: {exc}")

    print(
        f"{out}  provider_served={provider_served}  "
        f"model_served={model_served}  {meta['duration_s']}s  cost_usd={cost_usd}"
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001, voie ultime pour les dossiers réservés
        print(f"error: unexpected: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_IO) from exc
