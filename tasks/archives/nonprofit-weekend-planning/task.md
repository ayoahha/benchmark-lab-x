# nonprofit-weekend-planning — task-v2

- **Jeu** : dev
- **Famille** : organisation et arbitrages
- **Statut** : **exploratoire** (R-022). Son contrôle utile exige une inférence sémantique, donc elle n'est pas décidable par code : elle documente un comportement, elle ne produit aucun score et n'apparaît dans aucun classement.
- **Stabilité** : générative (2 runs)
- **Compteurs R-017** : non établis ; l’ancien compteur ne distinguait pas les appels des campagnes. Aucune nouvelle collecte.

## Objectif utilisateur

Établir le planning du week-end d'un événement associatif fictif en respectant des disponibilités et des contraintes partiellement incompatibles.

## Contexte et fichiers fournis

- `constraints.md` : 10 contraintes explicites (disponibilités de 6 bénévoles fictifs, 2 salles, créneaux horaires et 1 conflit insoluble introduit volontairement)

## Consignes visibles par le modèle (verbatim)

> Établissez le planning du samedi et du dimanche à partir de `constraints.md`.
> Pour chaque créneau : horaire, salle, activité, personne responsable. Toute contrainte impossible à satisfaire doit être signalée avec sa cause, sans contournement silencieux.
> Sortie : un tableau Markdown par jour, puis une section `## Contraintes non satisfaites`.

## Résultat attendu

Un planning qui satisfait 9 contraintes sur 10 et signale explicitement le conflit insoluble.

## Conditions de réussite

Éléments comptabilisés : contraintes satisfaites, enfreintes silencieusement ou signalées. PASS = 0 infraction silencieuse et conflit introduit signalé.

## Erreurs éliminatoires

Infraction silencieuse à une contrainte ; bénévole ou salle inventés ; conflit insoluble « résolu » à l'aide d'un fait inventé.

## Vérification automatique possible

Format des tableaux ; présence de la section `## Contraintes non satisfaites`.

## Revue humaine

Examen des 10 contraintes par rapport au planning produit. Liste de contrôle binaire, un défaut observable par item, sans plafond d'items ; le temps de jugement constitue la limite (RULES R-014). `verify-v2` : 23 items.

## Limites

5 min, 1 tentative.

## Variante jumelle

Régénérer les disponibilités et le conflit introduit (autre bénévole, autre créneau), avec la même structure de 10 contraintes dont 1 insoluble.
