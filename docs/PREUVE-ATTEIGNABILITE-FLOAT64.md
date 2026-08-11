---
title: "Atteignabilité du seuil float64 à 24 secondes"
date: 2026-08-08
status: "preuve numérique forte, certification formelle en HOLD"
---

# Atteignabilité du seuil float64 à 24 secondes

## Verdict

`B0-01` reste inchangée. Le seuil euclidien de `1e-16 m` à `t=24 s` est soutenu par une preuve numérique indépendante, reproductible et dotée d'une marge de `4,8818020905080329e-17 m`.

Cette preuve n'est pas une certification formelle de la trajectoire. Le calcul à intervalles dirigés s'arrête à l'événement 57, car son enveloppe ne permet plus de démontrer la transversalité du contact. Le verdict opposable est donc :

`PREUVE_NUMERIQUE_FORTE_MAIS_NON_CERTIFIEE`

R-016 reste en `HOLD`. Aucun nouveau témoin positif n'est qualifié par ce document et aucune attente n'est modifiée après observation du juge.

## Sources indépendantes

| Source | SHA-256 |
|---|---|
| `tasks/dev/pentagone-rotatif/task-v3.md` | `7acfb34a2e4e68d5fe8b75d2972cc97bb949f99d36e92b12e80de1339e9a77bf` |
| `tasks/dev/pentagone-rotatif/donnees.md` | `2f4dd0872b4377ea61df278396898f4cd7354d1bfa2a105ef6bfe1cdd3c77045` |

Le producteur du calcul a reçu uniquement ces deux sources. Il a déclaré n'avoir lu ni vérificateur, ni oracle, ni cache, ni témoin, ni reçu, ni lock, ni résultat de campagne. Les scripts ont été produits sous `/tmp` et n'entrent pas dans le jeu qualifiant.

## Faits établis

### Calcul événementiel

Deux calculs décimaux utilisent les équations visibles de `donnees.md` :

| Calcul | Précision | Fenêtre initiale | Collisions |
|---|---:|---:|---:|
| A | 80 chiffres | `0,05 s` | 59 |
| B | 130 chiffres | `0,017 s` | 59 |

Écart entre les positions finales :

- `|Δx| = 4,5586298549034954e-53 m`
- `|Δy| = 2,4123871214969631e-52 m`

Autres contrôles du calcul B :

- résidu maximal sur l'arête : `1,5746215186160775e-112 m`
- vol le plus court : `0,002037176462030931 s`
- plus faible vitesse normale d'impact : `0,6462737896521839 m/s`
- séparation minimale entre événements candidats retenus : `0,001669318906415484 s`

Position numérique de référence à `t=24 s` :

- `x = -0,7689532740342942028969638091271932367…`
- `y = -0,0463601387956409773695186554260133045…`

La reproduction locale a rendu les mêmes octets que la production indépendante :

| Artefact temporaire | SHA-256 |
|---|---|
| `reproduce.py` | `25bd27336f40d583127eda878c71f45e01e9e59e84736d0b307ab9157813c8ff` |
| `output.txt` | `00b698174b2673d5e95ec28ae5c9e38f967df62b72194e86c31ae8b132c5a552` |
| `events.tsv` | `4164f14c5666b28fdc023b1a9d8b541deffa3ac624adb691800186d9ad569726` |

### Arrondi binary64

Les nombres binary64 les plus proches de la position numérique de référence sont :

| Coordonnée | Valeur hexadécimale | Bits |
|---|---|---|
| `x64` | `-0x1.89b43e5842435p-1` | `bfe89b43e5842435` |
| `y64` | `-0x1.7bc841fee3ba6p-5` | `bfa7bc841fee3ba6` |

Erreurs par coordonnée :

- `|x64-x| = 5,1160933623958407e-17 m`
- `|y64-y| = 1,4676017163100780e-18 m`

Distance euclidienne :

`5,1181979094919670e-17 m`

Marge sous `1e-16 m` :

`4,8818020905080330e-17 m`

Les voisins binary64 immédiats de chaque coordonnée ont été contrôlés. Le couple retenu est le plus proche de la position numérique de référence.

## Limite de preuve

L'accord entre 80 et 130 chiffres ne borne pas, à lui seul, l'erreur par rapport à la trajectoire vraie. Les deux calculs peuvent partager le même défaut d'algorithme. La première recherche de racines peut aussi abandonner un intervalle très étroit sans exclure formellement une tangence ou une paire de racines.

Une revue indépendante classe donc le résultat comme preuve numérique forte, sans certification.

## Tentative de certification à intervalles

Un second calcul utilise :

- des intervalles `Decimal` à 180 chiffres avec arrondis dirigés
- des séries de Taylor de degré 240 avec reste de Lagrange
- l'isolation des racines et le contrôle des demi-plans, du segment de contact et de la vitesse normale relative

Le calcul progresse jusqu'au début de l'événement 57. L'enveloppe accumulée est alors trop large :

- largeur de temps : `0,083380000000000000000000000133… s`
- dérivée normale : intervalle contenant zéro, de `-0,6377672866…` à `1,9479671647…`

La transversalité n'est plus démontrée. Le script s'arrête du côté sûr avec `HOLD_CERTIFICATION` et le code retour `2`.

Reproduction finale du HOLD :

| Artefact temporaire | SHA-256 |
|---|---|
| `certificate.py` | `a7fdfea1b8090a49e3b40a95689f3889b88f91a983f3a988af84f8c80ebdecff` |
| `certificate.txt` | `891a256923f34c952f524352b2899b19ae5e08d32aa69e38d6821a1fc2028ca1` |

## Conséquences

1. L'échec du témoin `pos-01` à environ `8,47e-5 m` ne démontre pas que `1e-16 m` est inaccessible. Il démontre que ce témoin ne reproduit pas la trajectoire avec la précision annoncée.
2. Les données numériques ne justifient aucune modification de B0-01.
3. Elles ne suffisent pas à qualifier R-016 ou à adapter les attentes du témoin observé.
4. Une preuve formelle exige une propagation validée qui maîtrise l'effet de dépendance des intervalles jusqu'à `24 s`, par subdivision de l'état, arithmétique affine ou modèles de Taylor.
5. Tout nouveau témoin doit être produit et préenregistré indépendamment avant un nouveau passage Chromium.

## Portes

- `GO` : conserver localement B0-01 et le seuil `1e-16` comme décision approuvée.
- `GO` : corriger le pipeline de reçu R-016 hors Chromium.
- `HOLD` : déclarer la trajectoire formellement certifiée.
- `HOLD` : produire ou qualifier un nouveau témoin positif.
- `HOLD` : relancer Chromium, collecter, engager B0-10, commit, push ou publication.
