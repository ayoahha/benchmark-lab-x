# pentagone-rotatif : task-v2

- **Cohorte** : exposée
- **Régime de confidentialité** : exposé. Cette carte est conçue comme non confidentielle et destinée au dépôt public ; aucune série privée ne dépend de son secret (R-005b)
- **Statut** : en qualification, hors catalogue noté
- **Domaine d’usage** : visuel et simulation
- **Scénario d’usage** : produire une simulation déterministe interrogeable à des instants arbitraires
- **Mode d’exécution** : direct
- **Patron de mesure** : F1, rendu et comportement exécuté
- **Profondeur** : frontière dans la lignée des simulations géométriques
- **Stabilité** : générative (4 runs, niveau retenu au troisième meilleur, R-019)
- **Tolérance de reproduction (G4)** : métrique choisie = écart absolu de niveau retenu ; seuil admis = 3 paliers par candidat
- **Vérification** : `verify-v3`, 51 paliers. L’échelle mesure la précision à 24 secondes par demi-décades, de 1e+2 à 1e-17, puis la tenue à des horizons plus longs. `verify-v2` et `verify-v1` restent historiques ; leurs résultats ne se comparent pas directement à `verify-v3` (R-015)
- **Langue** : français

## Objectif utilisateur

Simuler exactement une balle qui rebondit dans un pentagone en rotation, et pouvoir donner sa position à n'importe quel instant.

## Décision visée

Choisir une configuration capable de produire une simulation déterministe et interrogeable, au niveau de précision requis par l’usage, puis départager les configurations admissibles par coût ou durée si la campagne le prévoit.

## Contexte et fichiers visibles

- `donnees.md` : la géométrie du pentagone, sa rotation, l'état initial de la balle, et les lois du vol et du choc écrites explicitement

Données 100 % synthétiques.

## Consignes visibles par le modèle (verbatim)

> À partir de `donnees.md`, produis une page HTML autonome qui simule le système décrit.
>
> La page doit définir une fonction globale `simulate(t)` qui rend la position de la balle à l'instant `t`, exprimé en secondes depuis le départ, sous la forme d'un tableau `[x, y]` de deux nombres. Cette fonction sera appelée pour des instants que nous choisissons entre 0 et 90 secondes, dans un ordre quelconque, et elle doit rendre la même valeur quel que soit l'ordre des appels.
>
> La page doit aussi dessiner, dans un élément `<canvas>` de 800 par 500, le pentagone et la balle tels qu'ils se trouvent à l'instant 0.
>
> Interdits : aucun accès réseau, aucune bibliothèque externe, aucune horloge, aucun tirage aléatoire. Deux exécutions successives de la page doivent produire exactement les mêmes valeurs.
>
> Sortie : uniquement le code HTML, entre les balises `<html>` et `</html>`. Aucun texte avant ou après, aucun bloc de code markdown.

## Résultat attendu

Une page dont `simulate(t)` reproduit la trajectoire exacte du système, aussi longtemps que la précision de son implémentation le permet.

## Paliers ou verdicts

`verify-v3` comporte 51 paliers. La note est le plus grand `k` tel que les paliers 1 à `k` passent tous. Le run vaut `PASS` si toute l’échelle passe et `FAIL` sinon ; le niveau conserve le gradient utilisé pour classer.

| Groupe | Nombre | Épreuve | Tolérance | Témoin positif | Témoin négatif |
|---|---:|---|---|---|---|
| `A0`, `A1`, `I0` | 3 | page exécutable, API totale et déterministe, état initial conforme | forme et déterminisme exacts ; état initial à 1e-9 m | `anchor-T5-reference.md`, à qualifier | `anchor-T0-sans-simulate.md`, matrice à compléter |
| `C2`, `C10`, `C20` | 3 | confinement jusqu’à 2, 10 puis 20 secondes | 2 mm vers l’extérieur | `anchor-T5-reference.md`, à qualifier | `anchor-T1-parabole.md` et `anchor-T2-mur-fixe.md`, à qualifier |
| `P…` | 39 | précision à 24 secondes, de 1e+2 à 1e-17 m par demi-décades | seuil propre à chaque palier | `anchor-T5-reference.md`, à qualifier | témoins de frontière à produire ou qualifier |
| `C35/E35`, `C55/E55`, `C75/E75` | 6 | confinement et précision à 35, 55 et 75 secondes | 2 mm de confinement ; 1 cm de précision | `anchor-T5-reference.md`, à qualifier | témoins de frontière à produire ou qualifier |

Les confinements courts précèdent l’échelle de précision à 24 s. Les trois horizons longs viennent ensuite, avec confinement puis précision. Une trajectoire qui quitte le pentagone tard conserve ainsi le crédit obtenu sur la précision antérieure.

Les instants d’évaluation ne figurent pas dans le prompt officiel. Sur le jeu exposé, le vérificateur peut être public : ces instants ne sont donc pas considérés confidentiels. Coder une table de positions exige néanmoins d’avoir calculé la trajectoire, ce qui est l’épreuve elle-même.

## Mécanisme discriminant

- **Bon chemin** : intégrer le mouvement événement par événement, résoudre chaque collision avec une paroi en rotation et conserver assez de précision numérique pour répondre à des instants arbitraires sans dépendre de l’ordre des appels
- **Mode d’échec attendu** : un pas de temps fixe, une paroi traitée comme immobile, une recherche de collision trop grossière ou un arrondi précoce accumule une erreur qui finit par franchir un seuil de précision ou de confinement
- **Ce que les paliers distinguent** : l’interface et le déterminisme, le confinement initial, la précision numérique à 24 secondes, puis la tenue aux horizons de 35, 55 et 75 secondes

L’amplification chaotique a été mesurée sur cette instance : `lambda ≈ 1,06 s⁻¹`. La version précédente regardait trop peu la zone où les implémentations se séparent. La mesure à 24 s ordonne désormais la précision par demi-décades, avant de tester la tenue à 35, 55 et 75 s.

### Qualification de `verify-v3`

La carte reste hors classement publiable jusqu’à la preuve de témoins positifs et négatifs pour chaque prédicat, la création des reçus de score sous l’empreinte de `verify-v3`, la renotation de la population compatible et l’audit humain R-026.

La matrice de témoins n’est pas encore complète. Aucun prédicat n’est considéré qualifié sans un témoin positif, un témoin négatif et la provenance du producteur aveugle au vérificateur.

## Refus du candidat

Un refus après appel vaut `FAIL`. Le diagnostic informatif `model_refusal` exige un signal structuré du fournisseur ou un constat humain consigné ; le vérificateur ne l’infère pas du texte. Refuser n’est pas le comportement correct de cette carte.

## Erreurs éliminatoires

Une page qui ne définit pas `simulate` ; deux exécutions qui divergent ; un accès réseau ou une bibliothèque externe ; l'usage d'une horloge ou d'un tirage aléatoire.

## Vérification

- vérificateur : `tools/verifier_pentagone.py`
- oracle : `tools/oracle_pentagone.py`
- cache d’oracle figé : `tasks/dev/pentagone-rotatif/oracle-cache.json`
- témoins exposés existants : `tasks/dev/pentagone-rotatif/anchor-*.md` ; la matrice positive et négative complète reste à qualifier
- `verify-v3` : 51 paliers, ordre et seuils versionnés dans le vérificateur

La page est chargée hors ligne dans le Chromium épinglé de l’environnement de mesure : Playwright 1.62.0, Chromium 151.0.7922.34. L’épingle est vérifiée au lancement et le vérificateur refuse de noter sous un autre moteur, plutôt que de comparer deux campagnes sous des rendus différents. Relever l’épingle incrémente `verify-vM` (R-015). `simulate` est appelée aux instants d'évaluation, deux fois, dans deux ordres différents. Les positions sont comparées à l'oracle `tools/oracle_pentagone.py`, qui résout le système événement par événement en précision arbitraire. Le canevas est rendu pour la galerie mais ne compte pas dans la note.

Pour une notation éligible, le rapporteur présente la sortie sous un chemin neutre selon R-010. L’invocation directe depuis `runs/`, utile au diagnostic actuel, conserve un chemin porteur de l’alias et ne suffit pas à qualifier la carte. Le vérificateur n’utilise ni identité ni métadonnées dans le calcul.

## Revue humaine

Aucune intervention humaine dans la note. Avant publication, l’audit R-026 vérifie que le verdict et le niveau du code décrivent correctement les sorties échantillonnées ; un défaut corrige l’instrument et déclenche une renotation, jamais une modification manuelle du score.

## Limites et sécurité

Un appel modèle par tentative, sans relance automatique du collecteur. Un échec d’infrastructure ne crée une tentative numérotée distincte que dans la limite fixée par la campagne ; V0 n’autorise qu’une tentative par run. La borne opposable est de 180 secondes de temps mural pour la vérification complète, appliquée par `tools/rapport_campagne.py` ; son dépassement donne `FAIL` au niveau 0. Le réglage interne de 120 secondes borne seulement les attentes interruptibles de Playwright, pas un JavaScript synchrone bloqué.

## Variante ou remplacement

Même système, autre pentagone, autre vitesse de rotation, autre état initial, et les instants d'évaluation redéfinis après mesure de l'amplification sur la nouvelle instance.
