---
style_gate: pass
---

# Carte d’usage : <nom lisible>

Ce gabarit décrit une carte compatible avec `benchmark-lab-x/protocol/v2`. Supprimer les exemples et compléter chaque champ obligatoire avant qualification.

| Champ | Valeur |
|---|---|
| Identifiant | `<slug>` |
| Statut | `brouillon` / `en qualification` / `qualifiée` / `retirée` |
| Domaine | `<domaine d’usage>` |
| Mode | `direct` / `agent` |
| Profondeur locale | `courant` / `exigeant` / `frontière` |
| Patron technique | `F1` / `F2` / `F3` / `F4` / `autre` |
| Version de tâche | `task-v<N>` |
| Version de vérification | `verify-v<M>` |
| Contrat de vérification | `<chemin versionné>` |
| Protocole | `benchmark-lab-x/protocol/v2` |
| Régime | `exposé` / `retenu` |

`N` et `M` sont des compteurs entiers indépendants. Après `task-v9` vient `task-v10`. Ils ne sont pas des versions sémantiques.

## 1. Scénario et décision

### Travail réel

<Qui fait quoi, dans quel contexte et pour quel résultat utile ?>

### Décision éclairée

<Quel choix concret ce résultat doit-il aider à prendre ?>

### Conséquences d’une erreur

<Que se passe-t-il si la recommandation est fausse, incomplète ou périmée ?>

### Stimulus distinct

<Pourquoi cette carte représente-t-elle un stimulus et une décision distincts des autres cartes ?>

## 2. Entrées visibles

### Consigne envoyée

<Texte exact ou chemin versionné>

### Liste d’autorisation

| Chemin relatif | Rôle | Envoyé au candidat |
|---|---|:---:|
| `<fichier>` | <entrée> | oui |

Tout fichier absent de cette liste, lien symbolique, chemin externe ou actif côté juge est refusé.

### Format de sortie

<Octets ou artefact attendu, encodage, noms de fichiers et interface>

### Besoin de sortie

| Champ | Valeur et justification |
|---|---|
| `max_tokens` | <besoin propre à cette carte ou route> |
| Paramètres obligatoires | <liste exacte> |
| Paramètres interdits | <liste exacte> |

Il n’existe aucun plancher universel. La campagne gèle les valeurs résolues avant appel.

## 3. Axes de score

Une carte peut porter plusieurs axes sans compter comme plusieurs cartes d’usage.

| Axe | Effet observable | Oracle ou référence | Verdict ou paliers | Limite principale |
|---|---|---|---|---|
| `<axe>` | <effet> | <calcul déterministe> | <règle> | <limite> |

Préciser les actifs juge partagés : leur modification peut changer plusieurs `verify_hash`.

## 4. Run design

| Champ | Valeur |
|---|---|
| Type | `répétition du même stimulus` / `instances distinctes` / `run unique déterministe` |
| Nombre de runs | <valeur justifiée> |
| Source de variation | <seed, échantillonnage, instance ou aucune> |
| Agrégation | <règle préenregistrée> |
| Revendication permise | <répétabilité, robustesse sur instances ou aucune> |

Sous le plan de répétition du protocole v2, utiliser six runs et le quatrième meilleur. Un run unique ne permet aucune revendication de répétabilité, sauf déterminisme de bout en bout justifié ci-dessous.

### Justification du déterminisme ou des variations

<Ce qui reste fixe, ce qui varie et pourquoi>

## 5. Ressources et environnement

Toutes les limites qui influencent la mesure sont versionnées.

Lorsqu’un artefact candidat est exécuté, le contrat de vérification fixe la frontière observable de préparation du harnais, le budget propre à l’artefact et l’enveloppe distincte de watchdog et teardown. Pour task-v5 / verify-v7, utiliser le [contrat dédié](../docs/VERIFY-V7.md) et conserver la carte au statut `brouillon` tant que sa limite numérique n’est pas qualifiée et approuvée.

| Ressource | Limite | Effet attendu en cas de dépassement |
|---|---:|---|
| Temps | <valeur> | <état et cause> |
| Mémoire | <valeur> | <état et cause> |
| CPU | <valeur> | <état et cause> |
| Processus | <valeur> | <état et cause> |
| Disque | <valeur> | <état et cause> |
| Réseau | <politique> | <refus ou état> |
| Navigateur | <version et politique> | <preuve> |
| Solveur | <version et borne> | <preuve> |

Supprimer les lignes sans objet et expliquer pourquoi elles n’influencent pas la mesure.

## 6. Représentativité et panel

### Usage représenté

<Pourquoi le stimulus représente-t-il le travail réel ?>

### Constitution du panel

<Configurations incluses, critères de sélection et principales absences>

### Conclusion permise

<Formulation exacte autorisée, limitée à ce panel, cette date et ce contexte>

### Limites du proxy

<Ce que la carte récompense, pénalise ou ne mesure pas>

## 7. Instrument

### Prédicats

| ID | Effet unique | Méthode déterministe | Cause d’échec |
|---|---|---|---|
| `<id>` | <effet> | <exécution, comptage, motif, contrainte ou écart> | `<cause_code>` |

### Mécanisme discriminant

<Bon chemin, erreurs attendues, voie de moindre résistance et ce que les axes distinguent>

Pour une carte adversariale, ajouter `trap_triggered` et un critère de qualification ou de retrait justifié en collectes indépendantes. Ne pas appliquer de seuil universel.

### Refus, vide et troncature

<Comportement attendu de l’adaptateur et de la notation, sans supposer une sémantique provider universelle>

## 8. Témoins et couverture

| Prédicat | Témoin positif | Témoin négatif | Producteur indépendant | Attente |
|---|---|---|---|---|
| `<id>` | `<fichier>` | `<fichier>` | <type et provenance> | <résultats> |

Un nouveau `verify_hash` ou environnement exige un nouveau reçu de couverture. Les octets témoins peuvent être réutilisés seulement si les prédicats sont inchangés.

## 9. Plan d’audit fondé sur le risque

| Champ | Plan préenregistré |
|---|---|
| Classes et frontières | <zones à examiner> |
| Anomalies et causes | <cas particuliers> |
| Sélection aveugle | <méthode> |
| Taille | <valeur et justification> |
| Conclusion permise | <portée limitée à l’échantillon> |

L’auditeur ne voit pas l’identité du candidat et ne modifie aucune note.

## 10. Actifs juge et exposition

| Actif | Statut avant première publication | Statut après publication | Envoyé au candidat |
|---|---|---|:---:|
| `<actif>` | `embargo` / `retenu` | `public rejouable` / `retenu` | non |

Pour une carte exposée, préciser le paquet rejouable, le risque de contamination, le renouvellement et le retrait. Pour une carte retenue, préciser accès, sauvegarde, restauration, exposition et condition d’invalidation.

## 11. Politique de données et sécurité

| Champ | Valeur |
|---|---|
| Données synthétiques | <preuve> |
| Politique demandée | <valeur> |
| Routes inéligibles | <critère> |
| Outils exécutés | <aucun ou manifeste> |
| Permissions | <droits minimaux> |
| Secrets disponibles | `aucun` |
| Cible réelle accessible | `non` |

Les exigences d’isolation outillée s’appliquent seulement si des outils sont exécutés.

## 12. Cycle de vie

| Événement | Critère préenregistré | Action |
|---|---|---|
| Qualification | <preuves attendues> | entrée au catalogue |
| Révision de tâche | <contenu visible changé> | incrémenter `task-vN` |
| Révision de vérification | <instrument changé> | incrémenter `verify-vM`, couvrir et renoter |
| Exposition | <premier résultat> | publier le paquet rejouable |
| Retrait | <proxy inutile, fuite, contamination ou obsolescence> | consigner `RETIRE` sans effacer les preuves |

## 13. Checklist de qualification

- [ ] décision, stimulus et conséquences d’erreur explicites
- [ ] carte distincte des entrées existantes
- [ ] axes et run design préenregistrés
- [ ] besoin de sortie et ressources justifiés
- [ ] panel, représentativité et limites du proxy documentés
- [ ] tous les points comptés décidables par code
- [ ] témoins indépendants et reçu de couverture acceptés
- [ ] plan d’audit fondé sur le risque approuvé
- [ ] actifs juge exclus du prompt
- [ ] politique de données et isolation conformes
- [ ] hashes et reçus produits sous les schémas attendus
- [ ] conclusion limitée au panel, au contexte et à la date
