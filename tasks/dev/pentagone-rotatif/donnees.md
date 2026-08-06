# Instance et lois du système

Toutes les grandeurs sont en unités du système international : mètres, secondes, radians.

## Le pentagone

Un pentagone convexe, plein, dont les sommets au repos sont, dans cet ordre :

| Sommet | x | y |
| ---: | ---: | ---: |
| 0 | 1.00 | 0.00 |
| 1 | 0.25 | 0.95 |
| 2 | -0.85 | 0.52 |
| 3 | -0.78 | -0.62 |
| 4 | 0.40 | -0.88 |

Il tourne autour de l'origine `(0, 0)` à la vitesse angulaire constante **ω = 0.7 rad/s**, dans le sens direct. À l'instant `t`, le sommet `S` occupe donc la position `R(ω·t)·S`, où `R(θ)` est la rotation d'angle `θ`.

Le pentagone ne se déforme pas et ne se déplace pas : il tourne, c'est tout.

## La balle

Une balle **ponctuelle**, sans rayon, sans masse à considérer, sans frottement et sans traînée.

- position initiale : `p(0) = (0.10, 0.30)`
- vitesse initiale : `v(0) = (1.70, 0.00)`

## Les lois

**Vol libre.** Entre deux chocs, la seule force est la gravité `g = (0, −9.81)`. Le mouvement est donc exactement parabolique :

```
p(t₀ + τ) = p(t₀) + v(t₀)·τ + ½·g·τ²
v(t₀ + τ) = v(t₀) + g·τ
```

**Choc.** Le choc se produit à l'instant exact où la balle atteint une paroi. Il est **parfaitement élastique** et se produit contre une paroi **en mouvement**. Soit `n` la normale intérieure unitaire de la paroi touchée à l'instant du choc, et `u` la vitesse d'entraînement du point de contact, qui vaut `u = ω × r` où `r` est le vecteur allant du centre de rotation au point de contact. En deux dimensions :

```
u = ω · (−r_y, r_x)
```

La vitesse après le choc est :

```
v' = v − 2·((v − u)·n)·n
```

Cette formule est donnée pour lever toute ambiguïté. La négliger, ou utiliser la formule du mur fixe `v' = v − 2·(v·n)·n`, produit une trajectoire fausse dès le premier choc.

**Pas d'amortissement** : le coefficient de restitution vaut exactement 1.

## Ce que le système fait

La balle reste indéfiniment à l'intérieur du pentagone. Le système est **chaotique** : deux trajectoires dont les états initiaux diffèrent d'une quantité `ε` s'écartent d'environ `ε·e^(1,06·t)`. Ce fait est communiqué délibérément, il fait partie de l'énoncé.
