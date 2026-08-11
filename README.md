# Benchmark Lab-X

**Le banc d’essai des systèmes d’IA. Des preuves, pas des promesses.**

Chaque semaine, un modèle promet de tout changer, et des équipes engagent des budgets sur la foi de démos et de classements qui ne mesurent jamais leur travail. La vraie question n’est pas de savoir qui gagne le classement du mois. C’est de savoir si l’offre la plus chère du marché sert à ce que vous faites : beaucoup d’équipes paient tous les mois une puissance qu’elles n’utilisent jamais, pendant que d’autres économisent et livrent du faux.

Le piège est plus profond qu’un mauvais choix de marque : vous ne déployez pas un modèle, vous déployez une configuration. Un modèle, une infrastructure, un fournisseur, un niveau d’effort, des réglages. Deux équipes qui achètent le même nom n’obtiennent ni la même fiabilité, ni le même prix.

> Pour ce travail, à ce niveau attendu, sous ces contraintes de coût, de délai et de données, quelle configuration choisir ?

Benchmark Lab-X construit l’instrument qui tranche cette question. Il fait exécuter des travaux inspirés de projets réels, puis fait vérifier chaque résultat par un programme, jamais par une impression ni par un autre modèle. Le programme qui corrige ne sait pas quel système a produit la réponse qu’il note. Ce qui a réussi, ce que ça a coûté, le temps que ça a pris et dans quelles conditions : tout est publié, avec ses limites et sa date.

La discipline est le produit. Aucun vainqueur universel, aucune note globale, aucun résultat retouché à la main. Un classement par type de travail, valable pour ce qui a été mesuré, dans ce contexte, à cette date. Et quand la preuve manque, le banc s’abstient au lieu de conclure.

Le projet naît au sein du collectif français Lab-X. Il a vocation à devenir public et réutilisable hors du collectif.

## Pourquoi Benchmark Lab-X ?

Les benchmarks généralistes donnent une référence commune. [SWE-bench](https://github.com/SWE-bench/SWE-bench) évalue la résolution de problèmes issus de dépôts logiciels. [Terminal-Bench](https://github.com/laude-institute/terminal-bench) mesure des agents dans un terminal. Ces travaux sont utiles, mais ils ne tranchent pas la décision locale posée plus haut.

Benchmark Lab-X part donc de cas d’usage concrets, en français, et mesure des effets observables : un artefact fonctionne, une contrainte est respectée, un calcul est juste, une provenance est fournie ou un objectif mesurable est atteint. Le score vient de code déterministe. Le projet publie les distributions, les limites du proxy et les conditions de la mesure, pas seulement un rang.

Chaque axe qualifié produit son propre classement. Il n’existe aucun vainqueur universel entre des domaines différents. Plusieurs axes ne sont réunis que dans un profil d’usage préenregistré, avec des minima, des contraintes et une règle d’abstention explicites.

## Ce qui est réellement comparé

Une identité de base directe comprend :

1. le **modèle demandé**, par exemple `anthropic/claude-sonnet-4.5`
2. le **backend et le provider épinglés**, par exemple `OpenRouter → Anthropic`
3. l’**effort déclaré**, par exemple `default`, `high` ou `xhigh`

Une configuration mesurée ajoute les paramètres exacts de l’appel, le budget de sortie, la politique de données demandée, la version de l’adaptateur et l’environnement qui influence l’exécution. Son `execution_manifest_hash` identifie cet ensemble. Deux configurations peuvent donc partager un libellé lisible sans être fusionnées.

La piste des agents outillés reste séparée. L’identité de base ajoute alors le nom et la version de l’agent ; la configuration précise aussi ses instructions, outils, permissions, mémoire, limites et environnement. Un résultat d’agent n’est jamais fusionné avec un classement d’appels directs.

## Carte d’usage et axes

Une **carte d’usage** représente un travail réel, son stimulus, la décision qu’il doit éclairer et son contrat de mesure. Elle peut produire plusieurs **axes de score** déterministes à partir d’un même artefact.

`pentagone-rotatif`, par exemple, reste une seule carte d’usage même si le même programme est évalué sur cinq axes : interface, déterminisme, confinement court, précision à 24 secondes et horizons longs. Un seul appel produit l’artefact ; les cinq notations ne multiplient ni les appels ni le coût de collecte.

Les cartes vivent sous `tasks/`. Ce nom correspond à l’objet manipulé par l’outillage ; le gabarit précise le contrat complet attendu.

## Fonctionnement cible

1. définir la décision, les cartes, les configurations et les contraintes
2. figer les routes, paramètres, tarifs, quotas et collectes dans un lock
3. collecter sans fallback silencieux
4. conserver un reçu de collecte distinct de la notation
5. noter chaque axe avec un vérificateur déterministe et aveugle à l’identité du candidat
6. contrôler les identités, empreintes, états et preuves
7. produire `results.html` avec le statut propre à chaque axe
8. auditer l’instrument selon un plan fondé sur le risque
9. valider uniquement les axes dont toutes les preuves requises sont acceptées

`results.html` est le seul rapport de campagne destiné à l’utilisateur. Les réponses, reçus et données intermédiaires restent sous `runs/`, hors Git.

## Trajectoire

- **V0, POC** : trois cartes d’usage exposées et qualifiées, couvrant au moins deux domaines, avec une démonstration rejouable
- **V1, prototype public** : dix cartes d’usage, reprise de campagne, reproduction externe et premiers retours de décisions réelles
- **V2, couverture directe** : matrice complète des domaines et scénarios prioritaires, dont un pilote cyber défensif synthétique
- **V3, agents outillés** : piste distincte avec outils et environnements isolés ; toute extension offensive exige une validation de sécurité séparée
- **V4, benchmark vivant** : suivi longitudinal pilote sur des cartes retenues et renouvellement des cartes exposées
- **V5, consultation** : recommandations depuis des candidats de profil compatibles, assez frais et dont les axes obligatoires sont valides, avec abstention si la preuve manque
- **V6, studio de tâche** : transformation contrôlée d’un besoin utilisateur en brouillon de carte, puis instrumentation et validation humaine avant toute mesure

V0 doit démontrer l’idée rapidement. V1 doit prouver qu’elle devient un produit reproductible. Les jalons suivants élargissent la couverture sans confondre ambition et preuve acquise.

## État actuel

Le dépôt contient un prototype technique actif et une première chaîne verticale. Les contrats et l’implémentation évoluent encore ; des défauts subsistent et aucun classement courant n’est garanti publiable. Les documents de référence décrivent séparément l’objectif, les invariants de mesure et l’architecture cible.

## Démarrage

### Prérequis

- [`uv`](https://docs.astral.sh/uv/)
- Python 3.11 ou plus récent, requis pour `tomllib` et résolu par `uv`
- un compte OpenRouter et une clé dédiée avec plafond de dépense
- Chromium pour les cartes rendues

```sh
git clone https://github.com/ayoahha/benchmark-lab-x.git
cd benchmark-lab-x
cp .env.example .env
uv run --with playwright playwright install chromium
```

Placer la clé dans `.env` sous `OPENROUTER_API_KEY`. Ne jamais la transmettre dans un argument, un chat, un ticket public ou une sortie publiée.

Le dépôt n’a pas encore de licence. Le clonage permet l’évaluation locale ; les droits de réutilisation et de redistribution seront précisés avant la première publication officielle.

Les configurations sont déclarées dans [`models.toml`](models.toml). OpenRouter est le backend primaire actuel. Groq ne peut servir qu’après qualification comme backend distinct, dans une nouvelle campagne et sous un nouveau lock. Il ne remplace jamais silencieusement une route indisponible.

### Exercer la chaîne actuelle

```sh
uv run tools/collect.py tasks/dev/pentagone-rotatif \
  --alias deepseek-v4-flash --run 1

uv run tools/verifier_pentagone.py \
  runs/<date>/pentagone-rotatif__deepseek-v4-flash__r1/response.md
```

Le collecteur écrit un dossier sous `runs/`. L’invocation directe d’un vérificateur reste diagnostique : elle ne suffit pas à produire un classement publiable.

## Organisation du dépôt

```text
docs/                  PRD, ARD et règles de mesure
tasks/TEMPLATE.md      contrat réutilisable d’une carte d’usage
tasks/dev/             cartes en développement ou hors catalogue
tasks/archives/        cartes retirées, conservées comme preuves
tools/                 collecte, adaptateurs, oracles et vérificateurs
models.toml            registre des configurations lisibles
runs/                  campagnes et résultats locaux, hors Git
```

## Documents de référence

- [`docs/PRD.md`](docs/PRD.md) : problème, valeur, utilisateurs, exigences produit, périmètre et jalons
- [`docs/ARD.md`](docs/ARD.md) : objets, identités, flux, états, sécurité et preuves techniques
- [`docs/RULES.md`](docs/RULES.md) : invariants d’éligibilité, de notation, d’agrégation et de publication
- [`tasks/TEMPLATE.md`](tasks/TEMPLATE.md) : gabarit d’une carte d’usage

Les décisions de produit et d’architecture restent dans le PRD ou l’ARD. Le dépôt ne multiplie pas les documents de décision ou d’exploitation.
