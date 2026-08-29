---
style_gate: pass
---

# Guide d'utilisation de la campagne V1

Ce guide décrit le parcours en six étapes du profil abonnement, dans l'ordre. Chaque étape donne les commandes exactes, ce que chaque commande rend comme code de sortie, et ce qu'elle engage en autorisation, en dépense et en quota.

Point d'entrée unique, depuis la racine du dépôt :

```
uv run tools/campagne_v1.py <sous-commande> [options]
```

## Comment lire les codes de sortie

Le contrat de la surface figée (section 5.4) donne trois codes, les mêmes pour toutes les sous-commandes sans exception : `0` en succès, `1` sur un refus fail-closed nommé, `2` sur un `HOLD`. Pour `preflight`, ce contrat se lit verdict par verdict : `READY` rend `0`, `UNAVAILABLE` rend `1`, `HOLD` rend `2`.

Ce contrat ne connaît pas de code d'usage. Aucune sous-commande, y compris `enregistrer`, `panel` et `autorisations`, ne porte ici un contrat réduit ou particulier : la colonne « code contractuel » répète la même triade pour toutes. Ce que le parseur d'arguments fait d'une invocation malformée n'est pas documenté par ce guide, faute d'observation consignée ; cette absence n'est pas comblée par déduction.

Un code contractuel n'est pas une observation. Ce guide sépare donc deux colonnes :

- **code contractuel** : ce que la section 5.4 impose, identique pour toutes les sous-commandes ;
- **code relevé** : ce qu'une exécution réellement effectuée a rendu, sur l'invocation exacte citée, avec la source qui l'atteste.

Quand aucune exécution n'a consigné le code, la case porte `non consigné`. Cette absence est conservée telle quelle et n'est jamais remplacée par le code contractuel.

## Comment chaque commande est vérifiée

Deux classes de preuve, et une seule règle pour les séparer : l'effet de la commande, jamais la localité de sa route.

**Rejeu local V1-XS-15.** Une commande locale, sans dépense, sans consommation de quota et sans écriture de reçu est rejouée par ce ticket sur une racine temporaire jetable, et son code est relevé dans [`journal-rejeu-local.json`](journal-rejeu-local.json). Huit sous-commandes relèvent de ce cas : `restituer`, `verifier-restitution`, `enregistrer`, `panel`, `autorisations`, `etat`, `metriques`, `cout`.

**Sur pièces.** Une acquisition ou une commande distante n'est jamais relancée pour documenter le parcours : son invocation et son code sont repris du journal GitHub du ticket qui l'a exécutée. `acquerir --local --configuration <id>` relève de ce cas malgré sa route locale, parce qu'elle exécute une route et écrit un reçu append-only. La relancer écrirait un reçu de plus pour documenter une commande déjà exécutée.

Les commandes locales dont l'artefact est append-only et déjà engagé se vérifient de la même façon : `qualifier`, `verrouiller`, `valider`, `dossiers`, `geler`.

## Étape 1. Enregistrer une configuration

Une configuration abonnement est un fichier TOML lisible par un humain, au format de la section 5.5. L'enregistrer l'ajoute au panel déclaré.

```
uv run tools/campagne_v1.py enregistrer --fichier <chemin-de-la-configuration>
uv run tools/campagne_v1.py panel
```

| Sous-commande | Code contractuel | Code relevé | Source |
|---|---|---|---|
| `enregistrer [--registre <chemin>] --fichier <chemin>` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | `0` dans les deux contextes rejoués | rejeu local V1-XS-15, contextes `refus-provenance-de-prix` et `ajout-puis-regeneration` |
| `panel [--registre <chemin>]` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | `0` | rejeu local V1-XS-15, contextes `lecture-seule` et `ajout-puis-regeneration` |

Autorisation : aucune. Dépense : aucune. Quota : aucun. Aucune action distante, aucune authentification, aucune lecture de compte.

Le drapeau `--registre` existe pour `enregistrer` et `panel`, et pour elles seules. Sans lui, la commande vise le registre officiel de campagne V1. Avec `--registre <chemin>`, elle vise exactement ce registre de travail, et lui seul : elle n'écrit ni ne lit le registre officiel. Le registre visé se lit donc dans la commande, jamais dans un répertoire courant ou une convention implicite.

Deux refus attendus, dont un seul est relevé par le rejeu local :

- un identifiant déjà présent dans le registre visé rend `1` avec le nom du champ fautif, `champ 'configuration_id'`. Ce refus est celui que la commande porte ; aucune exécution ne l'a consigné dans le rejeu local de ce ticket, donc son code relevé reste `non consigné` ;
- une configuration dont la provenance de prix reste `INCONNU` s'enregistre avec `0`, puis bloque l'étape 5 : `restituer` rend `1` sur `champ 'plan' : source incomplète, provenance de prix absente`. Ce second refus est bien relevé, contexte `refus-provenance-de-prix`. La provenance de prix vit dans `sources-plans-v1.toml`, séparée de la déclaration D-V1-01 ; l'enregistrement seul ne la fournit pas.

## Étape 2. Comprendre les autorisations

Avant toute action distante, cette étape montre ce que chaque configuration engagerait.

```
uv run tools/campagne_v1.py autorisations
uv run tools/campagne_v1.py autorisations --configuration <id>
```

| Sous-commande | Code contractuel | Code relevé | Source |
|---|---|---|---|
| `autorisations [--configuration <id>]` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | `0` dans les deux formes | rejeu local V1-XS-15, contextes `lecture-seule` et `ajout-puis-regeneration` |

Autorisation : aucune. Dépense : aucune. Quota : aucun. La commande le dit elle-même en première ligne : aperçu avant toute action distante, sans authentification, sans lecture de compte, sans inspection de facturation.

Ce que la sortie donne reste déclaré et non mesuré. Un plan, un quota ou une identité que les preuves versionnées n'établissent pas reste littéralement `INCONNU`.

## Étape 3. Lancer le benchmark

C'est la seule étape qui touche un compte, un quota ou une route distante. Aucune de ses commandes n'est rejouée par ce guide.

```
uv run tools/campagne_v1.py qualifier
uv run tools/campagne_v1.py preflight --configuration <id>
uv run tools/campagne_v1.py verrouiller
uv run tools/campagne_v1.py acquerir --local --configuration <id>
uv run tools/campagne_v1.py acquerir --configuration <id>
```

La forme de surface figée en 5.4 pour la sonde est `preflight [--configuration <id>]`. Toutes les invocations relevées ci-dessous portent l'argument, une configuration à la fois ; la ligne d'usage du fichier `tools/campagne_v1.py` publie de son côté `preflight --configuration <id>`, sans crochets. Cet écart entre la surface figée et l'usage implémenté est consigné comme limite héritée, pas corrigé par ce guide.

| Sous-commande | Code contractuel | Code relevé | Source |
|---|---|---|---|
| `qualifier` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | non consigné ; verdict `PASS`, 16 témoins, CPython 3.12.13 | [journal V1-XS-05](https://github.com/ayoahha/benchmark-lab-x/issues/100#issuecomment-5401010481) |
| `preflight --configuration claude-code-fable-5` | `0` `READY`, `1` `UNAVAILABLE`, `2` `HOLD` | `2`, verdict `HOLD`, cause `MISSING_OBSERVATION` | [journal V1-XS-06A](https://github.com/ayoahha/benchmark-lab-x/issues/101#issuecomment-5411961032) |
| `preflight --configuration claude-code-opus-5` | `0` `READY`, `1` `UNAVAILABLE`, `2` `HOLD` | `2`, verdict `HOLD`, cause `MISSING_OBSERVATION` | [journal V1-XS-06A](https://github.com/ayoahha/benchmark-lab-x/issues/101#issuecomment-5411961032) |
| `preflight --configuration codex-gpt-5-6-sol` | `0` `READY`, `1` `UNAVAILABLE`, `2` `HOLD` | `2`, verdict `HOLD`, cause `MISSING_OBSERVATION` | [journal V1-XS-06B](https://github.com/ayoahha/benchmark-lab-x/issues/102#issuecomment-5415577829) |
| `preflight --configuration grok-build-grok-4-6` | `0` `READY`, `1` `UNAVAILABLE`, `2` `HOLD` | non consigné ; verdict non consigné | [journal V1-XS-06C](https://github.com/ayoahha/benchmark-lab-x/issues/103#issuecomment-5424360484) |
| `preflight --configuration cursor-kimi-k3` | `0` `READY`, `1` `UNAVAILABLE`, `2` `HOLD` | `2`, verdict `HOLD`, cause `MISSING_OBSERVATION` | [journal V1-XS-06D](https://github.com/ayoahha/benchmark-lab-x/issues/104#issuecomment-5424753213) |
| `preflight --configuration zai-glm-5-3` | `0` `READY`, `1` `UNAVAILABLE`, `2` `HOLD` | non consigné ; verdict `READY` sur les seules métadonnées observées | [journal V1-XS-06E](https://github.com/ayoahha/benchmark-lab-x/issues/105#issuecomment-5425359081) |
| `preflight --configuration antigravity-gemini-3-7-flash` | `0` `READY`, `1` `UNAVAILABLE`, `2` `HOLD` | `0`, verdict `READY`, cause nulle | [journal V1-XS-06F](https://github.com/ayoahha/benchmark-lab-x/issues/106#issuecomment-5426436645) |
| `verrouiller` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | non consigné ; revue `PASS_V1_XS_07_RECOVERY_REVIEW` | [journal V1-XS-07](https://github.com/ayoahha/benchmark-lab-x/issues/107#issuecomment-5434319584) |
| `acquerir --local --configuration local-system-wc` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | non consigné | [journal V1-XS-04](https://github.com/ayoahha/benchmark-lab-x/issues/99#issuecomment-5399227908) |
| `acquerir --configuration <id>` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | non consigné ; deux tentatives classées `INCIDENT` / `HARNESS_ERROR` | [journal V1-XS-08](https://github.com/ayoahha/benchmark-lab-x/issues/108#issuecomment-5435861811) |

### Ce que chaque commande engage

`qualifier` requalifie le harnais sur les témoins approuvés et écrit un reçu de qualification. Autorisation : aucune décision propriétaire. Dépense : aucune. Quota : aucun. Aucun modèle de benchmark n'est exécuté.

`preflight` sonde la disponibilité d'une route par des commandes non génératives, sous l'autorité de probes `D-V1-03`. Autorisation : `D-V1-03`, une seule fois pour les six tranches `V1-XS-06A` à `V1-XS-06F`. Dépense : aucune. Quota : la consommation imputable au préflight reste `INCONNU` dans tous les journaux consultés ; l'identité réellement servie aussi. Un verdict `READY` ne prouve ni une génération, ni le modèle réellement servi, ni un palier commercial.

`verrouiller` matérialise et vérifie le verrou de campagne. Autorisation : attestation propriétaire `D-V1-01`. Dépense : aucune. Quota : aucun.

`acquerir --local --configuration <id>` exécute une route locale sous délai borné et écrit un reçu append-only. Autorisation : aucune décision propriétaire, aucun compte. Dépense : aucune. Quota : aucun. C'est pourtant une acquisition, parce que le critère de classement est l'effet et non la route : elle exécute une route et écrit un reçu. Elle n'est donc jamais rejouée pour documenter le parcours, et n'apparaît pas dans le journal de rejeu local.

Ce que le journal de `V1-XS-04` établit sur cette invocation :

- reçu produit, SHA-256 `d351492a49c0ce64cfb1f0d74a3719914e4e64453d4f2d75a86a13d515ff694e`, relevé identique dans les preuves `READY_V1_XS_04_OWNER_REVIEW` et de livraison ;
- ce SHA-256 correspond dans le dépôt au fichier `recus-v1/955c15c1d635386c7a25b9b0f3013e519883326236fcc2810cb05683d859a7f9.json`, dont l'identifiant de configuration est `local-system-wc` ;
- le code de sortie de la sous-commande elle-même n'est consigné nulle part dans ce journal. Le champ `payload.execution.code_sortie` du reçu vaut `0`, mais il décrit la route `/usr/bin/wc -c`, pas la sortie de la CLI. Les deux ne sont pas confondus ici.

`acquerir --configuration <id>` exécute une acquisition autorisée sous verrou. Autorisation : décision propriétaire `D-V1-04`, qui a figé exactement deux créneaux, `ACQ-V1-ANTIGRAVITY-GEMINI-3-7-FLASH-001` et `ACQ-V1-ZAI-GLM-5-3-001`. Dépense incrémentale, achat, crédit, dépassement payant ou nouveau plan : `0`. Quota : consommation autorisée uniquement sur les abonnements existants de ces deux configurations. Reprises, fallback de modèle, de fournisseur, de route ou d'endpoint : `0`.

Trois limites que le journal de `V1-XS-08` conserve et que ce guide ne corrige pas :

- la forme réellement exécutée portait `--officiel` au lieu de la surface courte figée en 5.4. L'écart est documenté comme limite héritée non bloquante, pas comme une correction ;
- les deux clients ont échoué localement avant toute sortie candidate, avec des codes client `2` et `1`. Ces deux nombres sont les codes des clients, pas ceux de la sous-commande `acquerir` ; le code de la CLI n'est pas consigné ;
- les deux tentatives sont classées `INCIDENT` avec la cause `HARNESS_ERROR`. Identité réellement servie et quota observé restent `INCONNU`.

## Étape 4. Voir les incidents et les données manquantes

```
uv run tools/campagne_v1.py etat
```

| Sous-commande | Code contractuel | Code relevé | Source |
|---|---|---|---|
| `etat` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | `0` | rejeu local V1-XS-15, contexte `lecture-seule` |

Autorisation : aucune. Dépense : aucune. Quota : aucun. La commande lit les seules preuves versionnées et le dit en première ligne.

La sortie donne les acquisitions, les incidents, les données manquantes et la couverture. La couverture est une fraction, sans classement ni conclusion ajoutée. Les états et les causes restent littéraux : un `HARNESS_ERROR` reste un `HARNESS_ERROR` et ne devient pas un verdict candidat. Lisez les nombres dans la sortie de la commande plutôt que dans ce guide : ils changent à chaque tranche.

## Étape 5. Régénérer la restitution

```
uv run tools/campagne_v1.py restituer
uv run tools/campagne_v1.py verifier-restitution
```

| Sous-commande | Code contractuel | Code relevé | Source |
|---|---|---|---|
| `restituer` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | `0`, puis `1` sur provenance de prix absente | rejeu local V1-XS-15, contextes `lecture-seule` et `refus-provenance-de-prix` |
| `verifier-restitution` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | `0`, puis `1` sur couverture divergente | rejeu local V1-XS-15, contextes `lecture-seule` et `ajout-puis-regeneration` |

Autorisation : aucune. Dépense : aucune. Quota : aucun. Le rendu est hors ligne et déterministe : deux régénérations successives sur les mêmes sources produisent le même octet.

`restituer` écrit `restitution-humaine-v1/index.html` depuis les seules preuves présentes. `verifier-restitution` compare la page à ses sources et refuse toute affirmation qu'elles ne portent pas.

Le rejeu local montre les deux refus utiles :

- une configuration enregistrée sans provenance de prix bloque `restituer` avec `1` ;
- une configuration ajoutée au registre officiel sans mise à jour de `etat-v1.json` laisse `restituer` rendre `0`, puis fait rendre `1` à `verifier-restitution` : `couverture stockée divergente de la redérivation indépendante : 6/8 attendu, 6/7 stocké`. La couverture publiée est une source, pas un calcul du rendu ; elle ne se répare pas toute seule.

Ce `1` est le résultat attendu de cette branche, et il se lit comme un refus, pas comme un succès. La page régénérée décrit huit configurations, tandis que `etat-v1.json` porte encore une couverture calculée sur sept. `verifier-restitution` redérive la couverture depuis les preuves, constate `6/8 attendu` contre `6/7 stocké`, refuse et n'écrit rien : c'est exactement le comportement fail-closed voulu. Un `0` à cet endroit signalerait au contraire que la page a été publiée avec une couverture que ses sources ne portent pas. La suite normale du parcours est de mettre à jour la source de couverture, jamais de forcer la vérification.

## Étape 6. Mettre à jour une comparaison située

```
uv run tools/campagne_v1.py valider
uv run tools/campagne_v1.py dossiers
uv run tools/campagne_v1.py geler
uv run tools/campagne_v1.py metriques
uv run tools/campagne_v1.py cout
uv run tools/campagne_v1.py restituer
```

| Sous-commande | Code contractuel | Code relevé | Source |
|---|---|---|---|
| `valider` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | non consigné ; registre relisible, zéro verdict candidat | [journal V1-XS-09](https://github.com/ayoahha/benchmark-lab-x/issues/109#issuecomment-5437367768) |
| `dossiers` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | `0` sur les preuves versionnées | [journal V1-XS-10](https://github.com/ayoahha/benchmark-lab-x/issues/110#issuecomment-5441466154) |
| `geler` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | non consigné ; commande réussie, gel byte-identique après nouvelle exécution | [journal V1-XS-11](https://github.com/ayoahha/benchmark-lab-x/issues/111#issuecomment-5442244622) |
| `metriques` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | `0` | rejeu local V1-XS-15, contexte `lecture-seule` |
| `cout` | `0` succès, `1` refus fail-closed nommé, `2` `HOLD` | `0` | rejeu local V1-XS-15, contexte `lecture-seule` |

`valider`, `dossiers` et `geler` écrivent des artefacts append-only déjà engagés. Aucune de ces trois commandes n'est rejouée par ce guide. Dépense : aucune. Quota : aucun.

Autorisation : `valider` et `dossiers` n'en demandent aucune. `geler` s'appuie sur `D-V1-06`, qui désigne `ayoahha` comme relecteur humain aveugle et ne demande son intervention que si au moins un dossier éligible existe. Sur le lot relevé par le journal de `V1-XS-11`, ce lot était vide : zéro verdict humain, zéro reçu humain, aucune révélation d'identité.

`metriques` et `cout` sont rejouées. Autorisation : aucune. Dépense : aucune. Quota : aucun.

Trois faits de cadrage que ces commandes ne franchissent pas :

- la comparaison est strictement intra-panel abonnement, sur trois axes figés : taux de sorties officiellement acceptables à maximiser, coût d'abonnement par sortie officiellement acceptable à minimiser, latence selon la règle préenregistrée à minimiser ;
- la décision propriétaire `D_V1_02 = NON_DEFINI_V1` laisse l'axe monétaire littéralement `NON_DEFINI` en V1, que le nombre de sorties acceptables soit nul ou positif. Aucun montant de remplacement, coût nul, division ou allocation par configuration n'est calculé ;
- les montants affichés restent des tarifs catalogue standards mensuels en USD, hors taxe, remise et facturation locale. Ils ne prouvent aucun montant réellement facturé.

Un axe qui reste `NON_DEFINI` reste littéral et impose l'abstention correspondante. Aucun score global, classement universel, gagnant unique ni comparaison avec le profil API n'est produit.

Après toute mise à jour, régénérez la page par l'étape 5 : c'est `restituer` qui publie la comparaison, pas `metriques` ni `cout`.

## Ce que le rejeu local a établi

Le journal [`journal-rejeu-local.json`](journal-rejeu-local.json) porte trois contextes isolés, chacun sur une racine temporaire jetable créée par la couture publique `principal(..., racine=<temp>)`. Le registre officiel du dépôt n'est écrit dans aucun d'eux.

Faits établis par ce rejeu :

- les huit sous-commandes rejouables ont rendu `0` sur les preuves versionnées courantes ;
- l'enchaînement enregistrement puis régénération modifie la restitution, et pas seulement son empreinte. Les empreintes HTML avant et après diffèrent, mais la preuve utile est sémantique : la page régénérée porte l'affirmation opérateur `<strong>demonstration-v1-xs-15</strong> — entrée déclarée et non mesurée.`, absente de la page précédente, et le nombre d'entrées de panel rendues passe de sept à huit. La configuration ajoutée devient donc lisible pour la personne qui ouvre la page, elle ne fait pas seulement bouger un SHA-256 ;
- la vérification qui suit cette régénération rend `1`, et ce refus est conservé tel quel : `6/8 attendu, 6/7 stocké`. Voir l'étape 5 pour sa lecture ;
- le répertoire des reçus est identique avant et après chaque contexte, et identique à son empreinte d'entrée `397b868cafe2a56facc95ac8df8b772cc802fc1b89b9d94b3b2d8910da1f90ac`. Aucun reçu n'a été créé, réécrit ni supprimé ;
- le répertoire des préflights est resté identique à son empreinte d'entrée `1aeaf3102effb3bec57de722868f4067353e680db96c78687e8c4a2c0b4a6e8b` ;
- `acquerir` n'apparaît sous aucune forme dans le journal de rejeu local.

L'empreinte de répertoire se lit ainsi : pour chaque fichier trié par nom, la ligne `<sha256 du fichier>  <chemin relatif à la racine du dépôt>`, puis le SHA-256 de la concaténation de ces lignes.

## Limites de ce guide

Ce guide décrit un parcours démontré, pas un parcours prévu. Ses limites tiennent en quatre points :

- il ne produit aucun classement, aucun gagnant, aucune recommandation ni aucun score agrégé ;
- il ne transforme aucune inconnue en fait établi. Un champ que les preuves ne portent pas reste `INCONNU` ou `NON_DEFINI` ;
- les codes de sortie des commandes d'acquisition et des commandes distantes viennent des journaux de leurs tickets propriétaires. Quand un journal ne consigne pas le code, ce guide écrit `non consigné` plutôt que le code contractuel ;
- le panel officiel n'a produit aucune sortie officiellement acceptable à ce jour. L'état courant se lit par `etat`, jamais dans ce guide.
