---
style_gate: pass
---

# Contrat figé du pilote Graph Engineering V1

## Identité et arrêt

- dépôt : `benchmark-lab-x`
- base : `81c217e0a585e89c0151090d6cef9581b8a2c741`
- branche locale : `experiment/graph-engineering-pilot-v1`
- verdict vert : `PASS_PILOTE_LOCAL`
- tout écart : `HOLD_PILOTE_LOCAL`
- aucun push, merge, appel candidat, réseau, dépense, effet externe ou mutation globale
- un seul écrivain dans le worktree

Le pilote prouve des propriétés locales d'exécution. Il ne prouve ni garantie `exactly-once`, ni reprise après écriture arbitrairement interrompue, ni sûreté multi-écrivains, ni avantage global.

## Graphe déclaré

Le graphe est codé en dur. Il ne constitue pas un moteur générique.

```text
           ┌── S ───────┐
D ─────────┤             ├── J
           └── A ou B ──┘
```

Arêtes attendues pour une exécution : `D→S`, `D→branche`, `S→J`, `branche→J`.

| Nœud | Entrée | Sortie | Évaluateur | Écriture |
|---|---|---|---|---|
| `D` | genèse canonique et route demandée | exactement `A` ou `B` | recalcule la route et l'ensemble sélectionné | son reçu seulement |
| `S` | reçu `D` évalué `PASS` | empreintes des sources U-025 V3 | vérifie les sources verrouillées | son reçu seulement |
| `A` | reçu `D` évalué `PASS`, route `A` | racine de la preuve U-025 V3 canonique | exécute le vérificateur U-025 V3 en lecture seule | son reçu seulement |
| `B` | reçu `D` évalué `PASS`, route `B` | racine d'une reconstruction U-025 V3 isolée | reconstruit, vérifie et compare la preuve U-025 V3 | son reçu et son sous-répertoire U-025 |
| `J` | reçus `S` et branche sélectionnée, tous deux évalués `PASS` | agrégat dépendant des deux sorties | exige exactement deux parents distincts et quatre arêtes consommées | son reçu seulement |

Chaque reçu lie le nœud, la tentative, les parents consommés, les entrées et sorties hachées, le contrat d'évaluation, le verdict local, le temps, le coût observable, l'effet `none`, le propriétaire et le périmètre d'écriture. Un reçu fermé est immuable.

Le runner ne rend jamais le verdict terminal. Une commande séparée et en lecture seule vérifie la genèse, les reçus, les évaluations, la branche sélectionnée, la jointure, les arêtes consommées et l'absence d'état ambigu.

## Scénarios autorisés

1. `S1` : route `A` nominale. Les nœuds sélectionnés sont `D`, `S`, `A`, `J`. Aucun reçu `B` n'existe. Le vérificateur terminal doit rendre `PASS`.
2. `S2` : route `B`. Un premier processus s'arrête après le reçu évalué de `S`. Le vérificateur doit rendre `HOLD`. Un second processus reprend sur `B`, sans réécrire ni réexécuter `D` et `S`, puis exécute `J`. Le résultat sémantique doit égaler un contrôle direct non interrompu.
3. `S3` : matrice de fausses fins dérivée d'une trace valide. Chaque altération est entièrement locale et doit être refusée.

La matrice `S3` couvre au minimum : nœud sélectionné absent ; branche non sélectionnée présente ou double branche ; état `pending`, `running` ou non évalué ; parent ou arête erroné ; reçu ou chaînage invalide ; contenu faux mais rehashé ; effet ambigu ou externe ; marqueur terminal forgé.

## Critère binaire

La commande ciblée rend `0` uniquement si :

- les cinq contrats de nœud sont testés ;
- chaque exécution sélectionne exactement quatre nœuds ;
- `J` consomme `S` et la branche sélectionnée ;
- la route évaluée sélectionne exactement une branche ;
- le verdict avant reprise de `S2` est `HOLD` ;
- la reprise commence sur `B` ;
- aucun reçu validé n'est réécrit et aucun nœud validé n'est réexécuté ;
- l'état final de `S2` égale le contrôle direct non interrompu ;
- toutes les fausses fins sont rejetées et `false_passes == 0` ;
- le périmètre reste local, mono-écrivain et sans effet externe.

## Mesures obligatoires

Le rapport du pilote conserve : exactitude terminale ; fausses fins ; temps mural et CPU ; coût externe observable ; interventions humaines ; reprise ; champs de contexte manquants ou altérés ; nombre d'écrivains et conflits observés ; nombre de processus ; octets de preuves ; comparaison descriptive avec l'exécution directe U-025.

Les temps et tailles sont des observations. Ils ne deviennent pas des portes de réussite.
