---
style_gate: pass
---

# Consolidation P1 et P2 U-025

Verdict de tranche : `PASS_54_READY_FOR_REVIEW`.

Conclusion U-025 après P1 et P2 : `INCONNU`.

Voies survivantes :

- `PROMPTFOO_0_122_0`
- `ORI_0_7_0_F411E1A`
- `METHODE_MANUELLE_CONTROLEE`

Aucun arrêt anticipé n'est recevable. P1 et P2 n'établissent aucune perte pertinente avec un effet décisionnel éliminatoire. Ils ne prouvent pas non plus une décision V0 exécutée ni une dominance d'effort.

## Autorités et intégrité

- [Grille C01 à C12 et règle d'effort](https://github.com/ayoahha/benchmark-lab-x/issues/37#issuecomment-5303196943)
- [Contrat P1, P2 et P3](https://github.com/ayoahha/benchmark-lab-x/issues/48#issuecomment-5304014456)
- [Décision propriétaire M3.7](https://github.com/ayoahha/benchmark-lab-x/issues/48#issuecomment-5305052264)
- [Issue M3.12](https://github.com/ayoahha/benchmark-lab-x/issues/54)
- Base : `e43fb9b19165f5ee87e812f677ea2800ee52958e`
- Manifeste : `8030128d159e4203483b19f0e37692a53f01baecc38fbccaa321541c23e71a10`

| Preuve | Racine | Registre |
|---|---|---:|
| [P1 locale V2](../p1-local-v2/proof-root.json) | `e317647595665fd55a9a7850a90449e467956b0e2c231580a6b5225e83db55ad` | 93 entrées |
| [P2 Promptfoo](../p2-promptfoo-v1/proof-root.json) | `5a4fe21568a4680a81490521eb6d2cd42e7365753957cb07ba6cc3a82ae0d32c` | 49 entrées |
| [P2 Ori](../p2-ori-v1/proof-root.json) | `204e7e97369dc16beac3205659759232db8e03eaf026c0be7b0dc889f68d9809` | 37 entrées |
| [P2 manuelle V3](../p2-manual-v3/proof-root.json) | `1aa9d67b15244c547014b2b5c1062dd451369c61d43a33b8877b5e4eacbd8021` | 44 entrées |

La [matrice machine](matrix.json) lie les corps d'autorité observés, les racines, les rapports et les registres d'effort.

## Entrées et projection communes

Les quatre chemins portent les mêmes 16 tuples ordonnés `case_id`, empreinte de spécification et empreinte de sortie candidate. Empreinte normalisée :

`f87c73a16fc7c84a39382fb398a21dcc9f8bdc770ea8d9d477badd69ade90fea`

Les trois P2 ont aussi la même projection normalisée :

`c64d1c4015d8089e7e566fd63ae2e07609d7c2686a71c6de3826d4b98f484f78`

| Mesure P2 | Valeur commune |
|---|---:|
| Cas | 16 |
| Automatique | 12 `PASS`, 3 `FAIL`, 1 `HARNESS_ERROR` |
| `OFFICIALLY_ACCEPTABLE` | 1 |
| `CANDIDATE_NOT_ACCEPTABLE` | 13 |
| `HARNESS_ERROR` | 1 |
| `UNABLE_TO_JUDGE` | 1 |
| `PROVIDER_FAILURE` | 0 |
| Couverture | 14/16 |
| Dénominateur décidable | 14 |
| Taux d'acceptation officiel | 1/14 |
| Appels candidats | 0 |
| Tentatives fournisseur | 0 |
| Dépense fournisseur | 0 |

Cette égalité prouve la fidélité des trois chemins sur les fixtures. Elle ne suffit pas à établir `MEME_DECISION_ETABLIE`, car P2 n'est pas une décision V0 exécutée.

## Matrice C01 à C12

| Critère | P1 | P2 | Entrée encore nécessaire en P3 |
|---|---|---|---|
| C01 Contrat et paquet | Paquet, cas et dérives prouvés | Même paquet et mêmes cas sur trois voies | Conserver les digests dans le lock |
| C02 Identités | Schémas et refus prouvés | Outils, binaires, runtimes et instruments bornés | Modèle, fournisseur, route, paramètres et identité servis |
| C03 Intégration | Maillons locaux rejoués | Trois chemins réels traversés avec fixtures | Chaîne fournisseur et sorties réelles |
| C04 Exécution et incidents | Taxonomie sur témoins | Incidents natifs attribués, limites conservées | Pannes fournisseur et reprises autorisées |
| C05 Coûts | Formules et valeurs absentes prouvées | Zéro appel et zéro dépense prouvés | Coûts fournisseur de toutes les tentatives |
| C06 Latence | Règle sur temps figés prouvée | Exécutions P2 non comparables entre voies | Latence fournisseur et délai complet |
| C07 Contrôles | G-001 à G-005 qualifiés | Raccordement 16/16 sur trois voies | Application aux sorties réelles |
| C08 Revue aveugle | Masquage, ordre, rubrique et gel prouvés | Verdicts figés transportés, revue manuelle observée | Dossiers et verdicts sur sorties réelles |
| C09 Provenance | Schémas, chaînes et ruptures prouvés | Racines et registres complets pour les trois voies | Provenance campagne et fournisseur |
| C10 Inconnues et abstention | Cas d'absence et abstention prouvés | Inconnues conservées sans devenir des échecs | Couverture, fraîcheur et préférences réelles |
| C11 Rapport | Rapport attendu reproductible | Rapports P2 concordants | Rapport V0 ou abstention de campagne |
| C12 Maintenance | Registre ouvert, inconnues conservées | Requalification récurrente inconnue sur trois voies | Obligations récurrentes observées en campagne |

## Identités, intégrations et limites

### Promptfoo

- Identité : `0.122.0`, artefact `5a4d0821…`, entrypoint `b1f2d2cb…`, Node `v26.7.0`
- Intégration : `providerOutput` court-circuite `callActiveProvider` et alimente G-001 à G-005
- Contrôles : permissions Node sans réseau ni descendant, zéro socket observée
- Incidents conservés : exit 100 attendu, `response` absente sur `WT-HARNESS`, libellé fournisseur générique sans appel, seatbelt indisponible

### Ori

- Identité : `0.7.0+f411e1a`, binaire `775a6f3e…`, Bun `1.3.14`
- Intégration : `setupAgent` avec `runViaHarness` in-process et G-001 à G-005
- Contrôles : environnement sans clé ni proxy, zéro socket externe sur le PID Ori, loopback borné
- Incidents conservés : exit 1 attendu, fichiers junit et results temporaires détruits, télémétrie préexistante hors preuve, descendants Bun non observables

### Méthode manuelle

- Identité : instrument `u025-p2-manual-semantic-resume/3`, SHA-256 `07a67b20…`
- Intégration : procédure versionnée, G-001 à G-005, revue aveugle, reçus append-only
- Contrôles : audit réseau validé et reprise au premier reçu incomplet
- Incidents conservés : V1 et V2 byte-identiques, trois contre-exemples V3 refusés, aucun nouvel examen aveugle simulé

La limite d'observation des descendants Bun reste `INCONNU`. Aucun effet sur la décision V0 n'est démontré. Elle ne devient donc pas une perte pertinente établie.

## Comparaison des sept composantes d'effort

`I/R` désigne les états initial et récurrent.

| Composante | Promptfoo | Ori | Manuelle | Conclusion |
|---|---|---|---|---|
| Configuration | `OBSERVE/OBSERVE`, config et portes natives | `OBSERVE/OBSERVE`, eval et portes natives | `OBSERVE/OBSERVE`, contrat et fixtures | Aucune réduction stricte prouvée |
| Intégration | `OBSERVE/OBSERVE`, égalité artefact/exécutable puis revalidation | `OBSERVE/OBSERVE`, égalité acquisition/binaire puis revalidation | `OBSERVE/OBSERVE`, préparation puis transfert par les portes | Actions non comparables sans préférence |
| Exécution | `OBSERVE/OBSERVE`, environnement puis ordre figé | `OBSERVE/OBSERVE`, commande puis ordre figé | `OBSERVE/OBSERVE`, registre append-only puis ordre figé | Aucune réduction stricte prouvée |
| Revue humaine | `OBSERVE/INCONNU`, fixtures puis verdicts réels | `OBSERVE/INCONNU`, fixtures puis verdicts réels | `OBSERVE/OBSERVE`, rôle puis revue et gel | L'inconnu des outils n'est pas un zéro |
| Vérification | `OBSERVE/OBSERVE`, calibration puis comparaison | `OBSERVE/OBSERVE`, calibration puis comparaison | `OBSERVE/OBSERVE`, qualification puis comparaison | Aucune réduction stricte prouvée |
| Maintenance | `OBSERVE/INCONNU`, stack puis requalification | `OBSERVE/INCONNU`, binaire puis requalification | `OBSERVE/INCONNU`, méthode puis requalification | Charges récurrentes inconnues |
| Production du rapport | `OBSERVE/OBSERVE`, formules puis sortie native | `OBSERVE/OBSERVE`, formules puis sortie native | `OBSERVE/OBSERVE`, formules puis reçus | Aucune réduction stricte prouvée |

La règle de #37 interdit une dominance en présence d'une inconnue, d'une granularité non comparable ou d'un compromis. Aucune voie n'est donc établie comme inférieure en effort.

## Conclusions séparées

- `MEME_DECISION_ETABLIE` : non établie. La projection P2 est identique, mais les sorties candidates et la décision V0 réelles n'existent pas.
- `PERTE_PERTINENTE_ETABLIE` : non établie. Aucun écart P1 ou P2 n'a un effet éliminatoire démontré.
- `INCONNU` : conclusion actuelle. Comportement fournisseur, qualité réelle, coût, latence, revue réelle et dominance restent inconnus.

Les trois voies survivent donc vers P3. `INCONNU` n'en élimine aucune.

## Entrées exactes nécessaires avant P3

1. Lock lié au paquet, aux 16 cas et aux trois voies survivantes
2. Panel et configurations candidates exactes
3. Modèles, fournisseurs, routes, paramètres et politique de données
4. Sources de prix datées et règle de latence gelée
5. Rôles humains, masquage, rubrique et ordre gelés
6. Règles d'incident, d'attribution et de reprise
7. Registre budgétaire exact
8. Autorisations distinctes pour chaque appel candidat, la campagne et la dépense
9. Adaptateurs P3 versionnés pour les trois voies
10. Reçus immuables de toutes les tentatives

La création ou l'exécution de M3.13 et M3.14 reste hors de cette tranche.

## Racine

`root_sha256 = 641b76c4f6b09616cec52427e12bc2c8dca0df333217c6f8b63edf0107bee136`

Aucun outil évalué n'a été réexécuté. Aucun appel candidat, fournisseur, campagne, dépense, P3, merge, fermeture de #54, modification de #42 ou #16, M4 ou nettoyage.
