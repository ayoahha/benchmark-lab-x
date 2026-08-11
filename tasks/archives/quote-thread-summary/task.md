# quote-thread-summary — task-v2

- **Jeu** : dev
- **Famille** : synthèse documentaire
- **Statut** : **exploratoire** (R-022). Son contrôle utile exige une inférence sémantique, donc elle n'est pas décidable par code : elle documente un comportement, elle ne produit aucun score et n'apparaît dans aucun classement.
- **Stabilité** : générative (2 runs)
- **Compteurs R-017** : non établis ; l’ancien compteur ne distinguait pas les appels des campagnes. Aucune nouvelle collecte.

## Objectif utilisateur

Extraire d'un fil de courriels désordonné la liste fiable des décisions, des montants et des échéances afin de préparer une réponse à propos d'un devis.

## Contexte et fichiers fournis

- `mail-thread.md` : 12 messages fictifs présentés dans le désordre, avec 2 contradictions historiques introduites volontairement (un montant révisé et une date déplacée) ainsi qu'une information délibérément manquante

## Consignes visibles par le modèle (verbatim)

> À partir de `mail-thread.md`, produisez : 1) la liste des décisions prises avec leur date, 2) le montant définitif convenu, 3) les prochaines échéances, 4) les points encore ouverts ou contradictoires.
> Si une information manque ou se contredit, signalez-le explicitement au lieu de choisir une version sans l'expliquer.
> Sortie : exactement 4 sections intitulées `## Décisions`, `## Montant`, `## Échéances` et `## Points ouverts`.

## Résultat attendu

Une synthèse exacte qui repère les 2 révisions contradictoires, restitue leur résolution et signale l'information manquante.

## Conditions de réussite

Vérité de référence connue du concepteur : décisions correctement datées ; dernier montant retenu et historique de sa révision explicité ; deux révisions repérées avec leur état résolu ; information manquante signalée ; aucun fait inventé.

## Erreurs éliminatoires

Un montant obsolète présenté comme définitif sans mention de la révision ; un fait inventé ; une révision contradictoire résolue silencieusement ou présentée à tort comme encore ouverte.

## Vérification automatique possible

Présence des 4 sections ; présence des montants et dates attendus selon des motifs exacts.

## Revue humaine

Comparaison avec la fiche de vérité de référence (`verify.md`). Liste de contrôle binaire, un défaut observable par item, sans plafond d'items ; le temps de jugement constitue la limite (RULES R-014). `verify-v2` : 16 items.

## Limites

5 min, 1 tentative.

## Variante jumelle

Même générateur de fil (12 messages, 2 contradictions, 1 manque), autre sujet (location de salle au lieu d'un devis de rénovation), pièges déplacés.
