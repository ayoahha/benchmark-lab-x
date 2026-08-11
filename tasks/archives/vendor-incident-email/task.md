# vendor-incident-email — task-v2

- **Jeu** : dev
- **Famille** : rédaction contrainte
- **Statut** : **exploratoire** (R-022). Son contrôle utile exige une inférence sémantique, donc elle n'est pas décidable par code : elle documente un comportement, elle ne produit aucun score et n'apparaît dans aucun classement.
- **Stabilité** : générative (2 runs)
- **Compteurs R-017** : non établis ; l’ancien compteur ne distinguait pas les appels des campagnes. Aucune nouvelle collecte.

## Objectif utilisateur

Rédiger la réponse d'un fournisseur à un client après une interruption de service, prête à être envoyée.

## Contexte et fichiers fournis

- `timeline.md` : chronologie factuelle fictive de l'incident (1 page)
- `commitments.md` : 3 clauses contractuelles fictives

## Consignes visibles par le modèle (verbatim)

> Rédigez le courriel de réponse au client à partir de `timeline.md` et de `commitments.md`.
> Contraintes : 200 mots maximum. Éléments obligatoires : la cause identifiée, la mesure corrective et le geste commercial proposé. Interdictions : promettre un délai chiffré de résolution, reconnaître une faute contractuelle ou employer un terme technique sans l'expliquer.
> Sortie : uniquement le corps du courriel, entre les balises `<email>` et `</email>`. Rien d'autre.

## Résultat attendu

Un courriel factuel, au ton neutre, conforme aux 3 obligations et aux 3 interdictions.

## Conditions de réussite

Les 3 éléments obligatoires sont présents et conformes à la chronologie ; aucune interdiction n'est enfreinte ; le corps compte au plus 200 mots ; les balises sont respectées.

## Erreurs éliminatoires

Un fait absent de la chronologie ; un délai chiffré ; une reconnaissance de faute ; un dépassement supérieur à 10 %.

## Vérification automatique possible

Comptage des mots ; présence des balises ; motif nombre + unité de temps à proximité de « résolu » ou « rétabli ».

## Revue humaine

Liste de contrôle binaire, un défaut observable par item, sans plafond d'items ; le temps de jugement constitue la limite (RULES R-014). `verify-v2` : 14 items couvrant les obligations, les interdictions, le format de sortie, la longueur, l'exactitude factuelle, les explications en langage courant et une dimension de qualité. Ancrages : `anchor-pass.md`, `anchor-fail.md`.

## Limites

5 min, 1 tentative.

## Variante jumelle

Même liste de contrôle, autre incident (retard de livraison au lieu d'une interruption), clauses renumérotées.
