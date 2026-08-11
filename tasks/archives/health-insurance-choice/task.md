# health-insurance-choice — task-v2

- **Jeu** : dev
- **Famille** : recherche sur corpus figé
- **Statut** : **exploratoire** (R-022). Son contrôle utile exige une inférence sémantique, donc elle n'est pas décidable par code : elle documente un comportement, elle ne produit aucun score et n'apparaît dans aucun classement.
- **Stabilité** : générative (2 runs)
- **Compteurs R-017** : non établis ; l’ancien compteur ne distinguait pas les appels des campagnes. Aucune nouvelle collecte.

## Objectif utilisateur

Choisir la meilleure offre parmi trois brochures fictives de complémentaire santé pour un profil donné, preuves citées à l'appui.

## Contexte et fichiers fournis

- `profile.md` : besoins du foyer fictif (4 critères pondérés)
- `offer-a.md`, `offer-b.md`, `offer-c.md` : brochures fictives (environ 2 pages chacune), dont une comporte une exclusion dissimulée dans les clauses en petits caractères ; une information manque dans les trois offres

## Consignes visibles par le modèle (verbatim)

> Recommandez l'une des trois offres pour le profil décrit dans `profile.md`, en vous fondant UNIQUEMENT sur les documents fournis.
> Chaque affirmation comparative doit citer le document et le passage exact. Si une information nécessaire au choix manque dans les documents, signalez-la comme inconnue au lieu de la supposer.
> Sortie : `## Recommandation` (une offre + 3 raisons citées), `## Points de vigilance`, `## Informations inconnues`.

## Résultat attendu

Une recommandation défendable, l'exclusion dissimulée repérée, l'information manquante signalée comme inconnue et aucune citation inventée.

## Conditions de réussite

Chaque citation figure mot pour mot dans le document cité ; l'exclusion dissimulée apparaît dans les points de vigilance ; l'information manquante apparaît dans les informations inconnues.

## Erreurs éliminatoires

Citation inexistante ou déformée ; connaissance externe ajoutée (prix ou garantie absent du corpus) ; information inconnue « complétée » par une hypothèse silencieuse.

## Vérification automatique possible

Présence des 3 sections ; recherche mot pour mot des passages cités dans le corpus.

## Revue humaine

Vérification citation par citation (coût approximativement doublé et budgété). Liste de contrôle binaire, un défaut observable par item, sans plafond d'items ; le temps de jugement constitue la limite (RULES R-014). `verify-v2` : 15 items.

## Limites

8 min, 1 tentative.

## Variante jumelle

Régénérer les 3 offres (autres noms, autres montants), déplacer l'exclusion dissimulée et l'information manquante, conserver le même profil pondéré.
