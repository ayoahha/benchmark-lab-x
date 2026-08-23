# /// script
# requires-python = ">=3.12"
# ///
"""Restitution humaine V1 vide et vérification de fidélité page/sources.

Interface figée :
- uv run tools/campagne_v1.py restituer
- uv run tools/campagne_v1.py verifier-restitution
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

VERSION_VUE = "restitution-humaine-v1/vue/1"

_RACINE_CAMPAGNE_V1 = Path("tasks/dev/pre-cadrage-entretien-client/campagne-v1")
CHEMIN_ETAT = _RACINE_CAMPAGNE_V1 / "etat-v1.json"
CHEMIN_PAGE = _RACINE_CAMPAGNE_V1 / "restitution-humaine-v1" / "index.html"

# Sources autorisées de la restitution, avec la section qui fait autorité.
SOURCES_AUTORISEES = (
    ("docs/PRD.md", "section 14"),
    ("docs/ARD.md", "section 7"),
    ("docs/RULES.md", "document entier"),
    ("tasks/dev/pre-cadrage-entretien-client/manifeste-paquet.json", "instantané immuable"),
    (
        "tasks/dev/pre-cadrage-entretien-client/campagne-v0/rapport-decision-m10-2-v1/rapport-interne.md",
        "antériorité V0 séparée",
    ),
)

CLASSES_MSW = ("fait", "deduction", "planifie")

# La page produite est autonome : aucune de ces séquences n'y est tolérée.
SEQUENCES_DISTANTES = (
    "http://",
    "https://",
    "src=",
    "<script",
    "<link",
    "<img",
    "@import",
    "url(",
)

JETONS_NORMATIFS = ("INCONNU", "NON_DEFINI", "HARNESS_ERROR", "ABSTENTION")

# Étapes futures dérivées des sources normatives, toutes marquées à venir.
ETAPES_FUTURES = (
    (
        "panel-abonnement",
        "Alimenter le panel abonnement avec des identités complètes : "
        "produit, plan, quotas, resets, interface, harnais et intervention humaine.",
        "docs/PRD.md",
        "section 14",
    ),
    (
        "qualification-independante",
        "Qualifier le profil abonnement indépendamment des profils API et "
        "auto-hébergé, sans comparaison inter-profils sans contrat commun explicite.",
        "docs/ARD.md",
        "section 7",
    ),
    (
        "approbation-empreintes",
        "Faire approuver par un humain, via des empreintes, les objets versionnés "
        "nécessaires au profil abonnement.",
        "docs/RULES.md",
        "U-009",
    ),
    (
        "recus-immuables",
        "Écrire un reçu immuable pour chaque acquisition du profil abonnement.",
        "docs/RULES.md",
        "U-010",
    ),
    (
        "acceptabilite-officielle",
        "Établir chaque acceptabilité officielle par la formule PASS automatique "
        "plus ACCEPTABLE humain, sous revue humaine aveugle.",
        "docs/RULES.md",
        "U-013 et U-014",
    ),
    (
        "restitution-ou-abstention",
        "Restituer les mesures centrales avec leurs dénominateurs et leurs "
        "manquants, ou prononcer l'abstention correspondante.",
        "docs/RULES.md",
        "U-018 et U-019",
    ),
)


class ErreurRestitution(Exception):
    """Entrée absente, invalide ou hors du périmètre XS-01."""


def _sha256_fichier(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def _charger_etat(racine: Path) -> dict:
    chemin = racine / CHEMIN_ETAT
    try:
        etat = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erreur:
        raise ErreurRestitution(f"état V1 illisible : {chemin} ({erreur})") from erreur
    if not isinstance(etat, dict) or etat.get("schema_etat") != "campagne-v1/etat-v1/1":
        raise ErreurRestitution(f"schéma d'état V1 inattendu : {chemin}")
    if not isinstance(etat.get("panel"), list):
        raise ErreurRestitution("le champ panel de l'état V1 doit être une liste")
    if not isinstance(etat.get("repertoire_recus"), str):
        raise ErreurRestitution("le champ repertoire_recus de l'état V1 doit être une chaîne")
    return etat


def _repertoire_recus(racine: Path, etat: dict) -> Path:
    return racine / _RACINE_CAMPAGNE_V1 / etat["repertoire_recus"]


def _compter_recus(repertoire: Path) -> int:
    if not repertoire.is_dir():
        raise ErreurRestitution(f"répertoire de reçus V1 absent : {repertoire}")
    return sum(1 for _ in repertoire.iterdir())


def _jetons_attendus(etat: dict, nombre_recus: int) -> tuple[str, str, str]:
    """Recalcule les trois jetons factuels depuis l'état et les reçus."""
    if etat["panel"] or nombre_recus:
        raise ErreurRestitution(
            "état hors périmètre XS-01 : la conclusion n'est dérivable que d'un "
            "panel vide et de zéro acquisition"
        )
    return "panel: vide", f"acquisitions: {nombre_recus}", "conclusion: ABSTENTION"


def _empreintes_sources(racine: Path, etat_relatif: str) -> dict[str, str]:
    empreintes: dict[str, str] = {}
    for chemin, _ in SOURCES_AUTORISEES:
        empreintes[chemin] = _sha256_fichier(racine / chemin)
    empreintes[etat_relatif] = _sha256_fichier(racine / etat_relatif)
    return empreintes


def _span_source(chemin: str, sha256: str, section: str) -> str:
    return (
        f'<span class="source" data-chemin="{chemin}" data-sha256="{sha256}">'
        f"source : <code>{chemin}</code> ({section}) · SHA-256 <code>{sha256}</code></span>"
    )


def _article(classe: str, contenu: str, attributs: str = "") -> str:
    return f'<article class="affirmation" data-classe="{classe}"{attributs}>{contenu}</article>'


def _rendre_page(racine: Path) -> bytes:
    etat = _charger_etat(racine)
    repertoire = _repertoire_recus(racine, etat)
    nombre_recus = _compter_recus(repertoire)
    jeton_panel, jeton_acquisitions, jeton_conclusion = _jetons_attendus(etat, nombre_recus)
    etat_relatif = CHEMIN_ETAT.as_posix()
    empreintes = _empreintes_sources(racine, etat_relatif)

    def src(chemin: str, section: str) -> str:
        return _span_source(chemin, empreintes[chemin], section)

    prd = "docs/PRD.md"
    ard = "docs/ARD.md"
    rules = "docs/RULES.md"
    manifeste = "tasks/dev/pre-cadrage-entretien-client/manifeste-paquet.json"
    rapport_v0 = (
        "tasks/dev/pre-cadrage-entretien-client/campagne-v0/"
        "rapport-decision-m10-2-v1/rapport-interne.md"
    )
    chemin_recus = (_RACINE_CAMPAGNE_V1 / etat["repertoire_recus"]).as_posix()

    sections: list[str] = []

    sections.append(
        "<section id=\"mesure-v1\"><h2>Ce que la V1 abonnement mesure</h2>"
        + _article(
            "fait",
            "<p>La V1 ajoute le profil de mesure abonnement, qui compare l'expérience "
            "réelle de produits par abonnement. L'identité comprend le produit, le plan, "
            "les quotas, les resets, l'interface, le harnais et l'intervention humaine. "
            "Un même modèle dans deux produits ou plans ne crée pas une identité "
            "commune.</p>" + src(prd, "section 14"),
        )
        + _article(
            "fait",
            "<p>Les versions produit sont cumulatives et les profils de mesure sont "
            "parallèles. Chaque profil est qualifié indépendamment. Aucune comparaison "
            "inter-profils n'est permise sans contrat commun explicite.</p>"
            + src(ard, "section 7"),
        )
        + "</section>"
    )

    sections.append(
        "<section id=\"question-decision\"><h2>Question et décision V1</h2>"
        + _article(
            "fait",
            "<p>Question V1 : quelle expérience réelle offrent les produits par "
            "abonnement du panel, sous les identités complètes du profil abonnement ? "
            "La décision servie est le choix d'une configuration abonnement, ou "
            "l'abstention correspondante lorsque les preuves manquent.</p>"
            + src(prd, "section 14")
            + src(rules, "U-018"),
        )
        + "</section>"
    )

    sections.append(
        "<section id=\"etat-v1\"><h2>État V1 courant</h2>"
        + _article(
            "fait",
            f"<p><code id=\"jeton-panel\">{jeton_panel}</code> — l'état V1 versionné ne "
            "déclare aucune configuration abonnement.</p>"
            + src(etat_relatif, "état V1 versionné"),
        )
        + _article(
            "fait",
            f"<p><code id=\"jeton-acquisitions\">{jeton_acquisitions}</code> — le "
            f"répertoire de reçus V1 <code>{chemin_recus}</code> existe et ne contient "
            "aucun reçu.</p>" + src(etat_relatif, "état V1 versionné"),
        )
        + _article(
            "deduction",
            f"<p><code id=\"jeton-conclusion\">{jeton_conclusion}</code> — déduction "
            "raisonnée : le panel est vide et aucune acquisition n'existe ; une absence "
            "de preuve n'est jamais transformée en résultat favorable, donc la seule "
            "conclusion dérivable est l'abstention. Aucune valeur de remplacement n'est "
            "créée.</p>" + src(rules, "U-018"),
            ' data-premisses="panel vide selon l\'état V1 versionné ; zéro reçu dans le '
            "répertoire de reçus V1 ; règle U-018 de docs/RULES.md\"",
        )
        + "</section>"
    )

    sections.append(
        "<section id=\"inconnues\"><h2>Ce qui reste inconnu</h2>"
        + _article(
            "fait",
            "<p>Aucune identité abonnement n'est déclarée : produit, plan, quotas, "
            "resets, interface, harnais et intervention humaine restent "
            "<code>INCONNU</code> pour tout candidat futur.</p>"
            + src(etat_relatif, "état V1 versionné"),
        )
        + _article(
            "fait",
            "<p>Aucun reçu V1 n'existe : expérience réelle, coûts, latences et "
            "couverture restent <code>INCONNU</code>. Aucune sortie acceptable "
            "n'existant, tout coût par sortie officiellement acceptable serait "
            "<code>NON_DEFINI</code>.</p>"
            + src(etat_relatif, "état V1 versionné")
            + src(rules, "U-020"),
        )
        + _article(
            "fait",
            "<p>Les contrats et politiques versionnés propres au profil abonnement ne "
            "sont pas encore déclarés dans l'état V1.</p>"
            + src(etat_relatif, "état V1 versionné")
            + src(ard, "section 7"),
        )
        + "</section>"
    )

    lignes_etapes = "".join(
        _article(
            "planifie",
            f"<p>Étape {rang} — {texte} <strong>à venir</strong></p>"
            + src(chemin, section),
            f' data-marqueur="a-venir" data-etape="{nom}"',
        )
        for rang, (nom, texte, chemin, section) in enumerate(ETAPES_FUTURES, start=1)
    )
    sections.append(
        "<section id=\"etapes-futures\"><h2>Six étapes futures</h2>"
        "<p>Éléments planifiés, tous marqués à venir. Aucun n'est commencé ni "
        "prouvé.</p>" + lignes_etapes + "</section>"
    )

    sections.append(
        "<section id=\"vocabulaire\"><h2>Vocabulaire normatif</h2>"
        "<p>Ces jetons appartiennent au vocabulaire normatif du dépôt. Aucun d'eux ne "
        "décrit un incident V1 observé : la V1 n'a rien observé.</p>"
        + _article(
            "fait",
            "<p><code>INCONNU</code> : valeur littérale d'une observation absente. "
            "Elle reste littérale et n'est jamais remplacée par une valeur "
            "inventée.</p>"
            + src(rapport_v0, "antériorité V0 séparée")
            + src(rules, "U-018"),
        )
        + _article(
            "fait",
            "<p><code>NON_DEFINI</code> : en l'absence de sortie acceptable, la mesure "
            "de coût par sortie officiellement acceptable est signalée comme non "
            "définie, les coûts engagés restant visibles.</p>" + src(rules, "U-020"),
        )
        + _article(
            "fait",
            "<p><code>HARNESS_ERROR</code> : défaut du harnais. Il ne pénalise pas la "
            "configuration, réduit la couverture, reste visible et empêche toute "
            "conclusion dépendant de la mesure manquante.</p>" + src(rules, "U-017"),
        )
        + _article(
            "fait",
            "<p><code>ABSTENTION</code> : une identité, une provenance, une fraîcheur, "
            "une comparabilité ou une préférence insuffisante impose l'abstention "
            "correspondante.</p>" + src(rules, "U-018"),
        )
        + "</section>"
    )

    sections.append(
        "<section id=\"anteriorite-v0\"><h2>Antériorité V0 séparée</h2>"
        + _article(
            "fait",
            "<p>Le rapport interne V0 M10.2, produit sous le profil API, s'est conclu "
            "par une abstention. Cette antériorité V0 reste séparée : une preuve "
            "historique établit seulement les propriétés de son propre contrat et ne "
            "constitue jamais un fait V1.</p>"
            + src(rapport_v0, "antériorité V0 séparée")
            + src(rules, "U-011"),
        )
        + _article(
            "fait",
            "<p>Le manifeste du paquet V0 porte les valeurs d'instantané "
            "<code>qualification_status: en attente d'approbation</code> et "
            "<code>approbation.statut: absente</code>, immuables depuis sa création. "
            "L'état courant de qualification relève d'une approbation humaine externe "
            "liée aux empreintes, qui seule fait autorité. Ces deux autorités sont "
            "distinctes et ne se contredisent pas.</p>"
            + src(manifeste, "instantané immuable")
            + src(rules, "U-009"),
        )
        + "</section>"
    )

    sections.append(
        "<section id=\"limites\"><h2>Limites</h2>"
        + _article(
            "fait",
            "<p>Cette page est une vue régénérable. Sa lisibilité n'améliore aucune "
            "preuve. Elle ne produit aucun appel candidat, aucune acquisition, aucune "
            "dépense, aucun classement, aucun gagnant et aucune recommandation. Aucune "
            "hypothèse non vérifiée n'est présente : aucune n'était nécessaire, et "
            "aucune n'est créée pour remplir une catégorie.</p>"
            + src(rules, "U-010 et U-026"),
        )
        + "</section>"
    )

    corps = "".join(sections)
    provenance = "".join(
        f"<li><code>{chemin}</code> ({section}) · SHA-256 "
        f"<code>{empreintes[chemin]}</code></li>"
        for chemin, section in (*SOURCES_AUTORISEES, (etat_relatif, "état V1 versionné"))
    )
    page = (
        "<!DOCTYPE html>\n"
        '<html lang="fr">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        "<title>Restitution humaine V1 — profil abonnement — état vide</title>\n"
        "<style>\n"
        "body{font-family:Georgia,serif;max-width:52rem;margin:2rem auto;"
        "padding:0 1rem;line-height:1.5;color:#1a1a1a;background:#fdfdfb}\n"
        "h1{font-size:1.5rem}h2{font-size:1.15rem;margin-top:1.6rem;"
        "border-bottom:1px solid #ccc}\n"
        "article.affirmation{margin:0.7rem 0;padding:0.5rem 0.8rem;"
        "border-left:4px solid #999;background:#f6f6f2}\n"
        'article.affirmation[data-classe="fait"]{border-left-color:#2e6e3e}\n'
        'article.affirmation[data-classe="deduction"]{border-left-color:#2e4e7e}\n'
        'article.affirmation[data-classe="planifie"]{border-left-color:#8a6d1a}\n'
        "article.affirmation::before{display:block;font-size:0.75rem;"
        "letter-spacing:0.05em;color:#555;text-transform:uppercase}\n"
        'article.affirmation[data-classe="fait"]::before{content:"fait établi"}\n'
        'article.affirmation[data-classe="deduction"]::before'
        '{content:"déduction raisonnée"}\n'
        'article.affirmation[data-classe="planifie"]::before'
        '{content:"planifié — à venir"}\n'
        "span.source{display:block;font-size:0.8rem;color:#555;"
        "overflow-wrap:anywhere}\n"
        "code{background:#eee;padding:0 0.2rem}\n"
        "footer{margin-top:2rem;font-size:0.8rem;color:#555}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        "<h1>Restitution humaine V1 — profil abonnement — état vide</h1>\n"
        f"<p>Vue <code>{VERSION_VUE}</code>, autonome et hors ligne, régénérée de "
        "façon déterministe depuis les seules sources listées en pied de page. Chaque "
        "affirmation porte sa classe : fait établi, déduction raisonnée ou élément "
        "planifié à venir.</p>\n"
        f"{corps}\n"
        "<footer><p>Sources exactes de cette vue :</p>"
        f"<ul>{provenance}</ul></footer>\n"
        "</body>\n"
        "</html>\n"
    )
    return page.encode("utf-8")


def restituer(racine: Path) -> int:
    etat = _charger_etat(racine)
    repertoire = _repertoire_recus(racine, etat)
    repertoire.mkdir(parents=True, exist_ok=True)
    contenu = _rendre_page(racine)
    chemin_page = racine / CHEMIN_PAGE
    chemin_page.parent.mkdir(parents=True, exist_ok=True)
    chemin_page.write_bytes(contenu)
    print(f"page écrite : {CHEMIN_PAGE.as_posix()} ({len(contenu)} octets)")
    print(
        f"répertoire de reçus V1 : {repertoire.relative_to(racine).as_posix()} "
        f"({_compter_recus(repertoire)} reçu)"
    )
    return 0


_MOTIF_ARTICLE = re.compile(
    r'<article class="affirmation"([^>]*)>(.*?)</article>', re.DOTALL
)
_MOTIF_CLASSE = re.compile(r' data-classe="([^"]*)"')
_MOTIF_SOURCE = re.compile(r'<span class="source" data-chemin="([^"]+)" data-sha256="([a-f0-9]{64})">')
_MOTIF_PREMISSES = re.compile(r' data-premisses="([^"]+)"')
_MOTIF_ETAPE = re.compile(r' data-etape="([^"]+)"')


def verifier_restitution(racine: Path) -> int:
    echecs: list[str] = []
    chemin_page = racine / CHEMIN_PAGE
    try:
        page = chemin_page.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as erreur:
        print(f"ECHEC page illisible : {erreur}")
        return 1

    # Attendus recalculés depuis les entrées, indépendamment du rendu.
    etat = _charger_etat(racine)
    repertoire = _repertoire_recus(racine, etat)
    nombre_recus = _compter_recus(repertoire)
    jetons_factuels = _jetons_attendus(etat, nombre_recus)
    etat_relatif = CHEMIN_ETAT.as_posix()
    empreintes = _empreintes_sources(racine, etat_relatif)

    page_basse = page.lower()
    for sequence in SEQUENCES_DISTANTES:
        if sequence in page_basse:
            echecs.append(f"ressource distante interdite présente : {sequence!r}")

    for jeton in (*jetons_factuels, *JETONS_NORMATIFS):
        if jeton not in page:
            echecs.append(f"jeton attendu absent : {jeton!r}")

    for chemin, sha256 in empreintes.items():
        if f'data-chemin="{chemin}" data-sha256="{sha256}"' not in page:
            echecs.append(
                f"source infidèle ou absente : {chemin} attendu avec SHA-256 {sha256}"
            )

    articles = _MOTIF_ARTICLE.findall(page)
    if page.count('<article class="affirmation"') != len(articles):
        echecs.append("article d'affirmation mal formé")
    etapes: list[str] = []
    for attributs, contenu in articles:
        classe = _MOTIF_CLASSE.search(attributs)
        if classe is None or classe.group(1) not in CLASSES_MSW:
            echecs.append(f"affirmation sans classe MSW valide : {contenu[:60]!r}")
            continue
        sources = _MOTIF_SOURCE.findall(contenu)
        if classe.group(1) in {"fait", "deduction"} and not sources:
            echecs.append(
                f"affirmation {classe.group(1)} sans chemin ni empreinte de source : "
                f"{contenu[:60]!r}"
            )
        for chemin, sha256 in sources:
            if empreintes.get(chemin) != sha256:
                echecs.append(f"empreinte citée divergente pour {chemin}")
        if classe.group(1) == "deduction" and not _MOTIF_PREMISSES.search(attributs):
            echecs.append(f"déduction sans prémisses visibles : {contenu[:60]!r}")
        if classe.group(1) == "planifie":
            etape = _MOTIF_ETAPE.search(attributs)
            if (
                etape is None
                or ' data-marqueur="a-venir"' not in attributs
                or "à venir" not in contenu
            ):
                echecs.append(f"étape planifiée sans marqueur à venir : {contenu[:60]!r}")
            else:
                etapes.append(etape.group(1))

    noms_attendus = [nom for nom, _, _, _ in ETAPES_FUTURES]
    if etapes != noms_attendus:
        echecs.append(
            f"six étapes futures attendues {noms_attendus}, trouvées {etapes}"
        )

    if echecs:
        for echec in echecs:
            print(f"ECHEC {echec}")
        return 1
    print("verification-restitution : conforme")
    return 0


def principal(arguments: list[str]) -> int:
    racine = Path(__file__).resolve().parent.parent
    if arguments == ["restituer"]:
        try:
            return restituer(racine)
        except ErreurRestitution as erreur:
            print(f"ECHEC {erreur}")
            return 1
    if arguments == ["verifier-restitution"]:
        try:
            return verifier_restitution(racine)
        except ErreurRestitution as erreur:
            print(f"ECHEC {erreur}")
            return 1
    print("usage : campagne_v1.py restituer | verifier-restitution")
    return 2


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
