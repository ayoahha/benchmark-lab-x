---
style_gate: pass
---

# Carte de workflow : <nom lisible>

Ce gabarit décrit une décision réelle et le contrat hybride qui permet d’évaluer une sortie. Supprimer les aides entre chevrons avant approbation. Ne fixer aucun nombre, seuil ou délai sans en citer l’autorité ou la justification mesurée.

## 1. Identité et autorité

| Champ | Valeur |
|---|---|
| Identifiant | `<slug>` |
| Version de carte (`card_version`) | `<version>` |
| `qualification_status` | `brouillon` / `en attente d'approbation` / `qualifiée` / `retirée` |
| `execution_status` | `non exécutée` / `exécutée` |
| Propriétaire de la décision | `<rôle humain>` |
| Date de référence | `<date>` |
| Empreinte du registre | `<sha256>` |
| Approbation humaine liée à l’empreinte | `<référence ou absente>` |

Une consolidation par plusieurs humains ou LLM produit un brouillon. Seule l’approbation humaine liée aux empreintes qualifie la carte.

## 2. Besoin et décision réelle

### Workflow exact

<Qui accomplit quel travail, dans quel contexte réel ?>

### Décision éclairée

<Quel choix concret la comparaison doit-elle permettre ?>

### Sortie attendue

<Quel artefact utilisable doit être produit ?>

### Conséquences d’une sortie inacceptable

<Risques, reprises ou mauvaises décisions possibles>

### Conclusion permise

<Formulation exacte, limitée à ce workflow, au panel, à la date et aux contraintes>

### Hors périmètre

<Ce que cette carte ne mesure pas et les généralisations interdites>

## 3. Stimulus candidat-visible

### Consigne exacte

<Texte exact ou chemin versionné>

### Entrées autorisées

| Chemin ou objet | Rôle | Empreinte | Visible par le candidat |
|---|---|---|:---:|
| `<entrée>` | `<rôle>` | `<sha256>` | oui / non |

Tout objet absent de cette liste est refusé. Les actifs juge et les témoins restent invisibles au candidat.

### Interface de sortie

<Format, encodage, fichiers attendus, structure et contraintes entièrement décidables>

### Paramètres et ressources

| Élément | Valeur | Autorité ou justification | Conséquence observable |
|---|---|---|---|
| `<paramètre ou ressource>` | `<valeur>` | `<source>` | `<effet>` |

Supprimer les lignes sans effet sur la mesure. Ne pas ajouter de valeur par défaut sans autorité.

## 4. Politique de données et sécurité

| Exigence | Preuve ou règle |
|---|---|
| Données synthétiques ou publiques réutilisables | `<provenance>` |
| Donnée client réelle | `aucune` |
| Secret | `aucun` |
| Connecteur de production | `aucun` |
| Action externe | `interdite` |
| Outils et permissions | `<aucun ou manifeste minimal>` |
| Réseau | `<interdit ou destination explicitement autorisée>` |

## 5. Contrat de sortie acceptable

Une sortie est officiellement acceptable si, et seulement si, elle obtient :

`PASS automatique + ACCEPTABLE humain`

### 5.1 Contrôles automatiques

Chaque ligne porte sur une propriété entièrement décidable par code.

| ID | Propriété observable | Méthode déterministe | Preuve attendue | Verdict d’échec |
|---|---|---|---|---|
| `<AUTO-ID>` | `<propriété unique>` | `<exécution, parsing, comptage, contrainte ou oracle>` | `<reçu ou artefact>` | `FAIL` |

Une propriété qui exige une interprétation humaine est retirée de ce tableau et placée dans la rubrique humaine.

### 5.2 Rubrique humaine aveugle

| Dimension | Question de jugement | Signes d’acceptabilité | Motifs de refus | Limites |
|---|---|---|---|---|
| `<dimension>` | `<question>` | `<signes observables>` | `<défauts matériels>` | `<ce que la rubrique ne tranche pas>` |

Verdicts autorisés :

- `ACCEPTABLE` : la sortie satisfait la rubrique pour l’usage déclaré
- `NOT_ACCEPTABLE` : un défaut matériel empêche cet usage
- `UNABLE_TO_JUDGE` : les éléments disponibles ne permettent pas un jugement fiable

La présentation masque l’identité de la configuration, son coût et toute métadonnée susceptible de la révéler. La rubrique et l’ordre de présentation sont gelés avant la revue officielle.

### 5.3 Juge fantôme

| Champ | Valeur |
|---|---|
| Activé | oui / non |
| Moment | après gel du verdict humain |
| Effet officiel | aucun |
| Identité et paramètres | `<si activé>` |

## 6. Témoins et qualification de l’instrument

| Contrôle ou dimension | Témoin | Attente | Producteur et provenance | Empreinte |
|---|---|---|---|---|
| `<ID>` | `<positif, négatif ou cas frontière>` | `<résultat attendu>` | `<source indépendante>` | `<sha256>` |

### Indépendance

<Ce que le producteur des témoins pouvait voir et ce qui lui était interdit>

### Limites de qualification

<Ce que les témoins prouvent et ce qu’ils ne prouvent pas>

## 7. Plan de mesure

| Champ | Valeur et justification |
|---|---|
| Unité d’acquisition | `<définition>` |
| Type de variation | `<aucune, répétition, instances distinctes ou autre>` |
| Nombre d’acquisitions | `<valeur décidée ou à décider, avec autorité>` |
| Ordre et aveuglement | `<règle>` |
| Arrêt anticipé | `<condition autorisée ou aucune>` |
| Fraîcheur requise | `<condition et justification>` |
| Agrégation | `<règle préenregistrée>` |
| Revendication permise | `<portée exacte>` |

Ce gabarit n’impose aucun plan de répétition. Le plan retenu doit suffire à la décision visée sans revendiquer plus que ses preuves.

## 8. Panel et configurations

### Critères d’inclusion

<Compatibilité avec le besoin, disponibilité des preuves, fraîcheur et contraintes>

### Critères d’exclusion

<Motifs vérifiables et absences connues>

### Configurations fixes

| Alias aveugle | Modèle et révision | Fournisseur et route attendus | Paramètres | Politique de données | Adaptateur et harnais |
|---|---|---|---|---|---|
| `<alias>` | `<identité>` | `<identité>` | `<valeurs>` | `<politique>` | `<versions>` |

Route, fournisseur et paramètres servis doivent être observables pour un résultat officiel.

### Politiques de routage

| Alias aveugle | Politique | Contraintes | Observations requises | Condition d’admission |
|---|---|---|---|---|
| `<alias>` | `<par exemple OpenRouter Auto Router>` | `<bornes déclarées>` | `<modèle, fournisseur, route, paramètres>` | `<diagnostic et canari>` |

Une politique de routage n’est jamais présentée comme un modèle fixe.

## 9. Provenance et preuves d’acquisition

| Objet | Attendu | Observé | Source | Empreinte ou reçu |
|---|---|---|---|---|
| Carte et stimulus | `<version>` | `<version>` | `<chemin>` | `<sha256>` |
| Configuration | `<identité>` | `<identité servie>` | `<métadonnées>` | `<reçu>` |
| Paramètres | `<valeurs>` | `<valeurs observables>` | `<métadonnées>` | `<reçu>` |
| Prix | `<unité datée>` | `<coût>` | `<source officielle>` | `<reçu>` |
| Latence | `<frontières>` | `<mesure>` | `<horloge>` | `<reçu>` |

Une observation absente reste absente. Elle n’est pas déduite d’un comportement attendu.

## 10. Incidents et couverture

| Classe | Définition pour cette carte | Effet sur la décision |
|---|---|---|
| `PROVIDER_FAILURE` | `<panne de la route appartenant à la configuration>` | échec bout en bout, sans verdict de qualité |
| `HARNESS_ERROR` | `<défaut empêchant une mesure fiable>` | non pénalisant, couverture manquante visible |
| `<autre classe versionnée>` | `<définition>` | `<effet>` |

## 11. Analyse décisionnelle

| Élément | Règle préenregistrée |
|---|---|
| Taux de sorties officiellement acceptables | `<numérateur, dénominateur et états exclus>` |
| Coût fournisseur par sortie officiellement acceptable | `<dépense fournisseur incluse, traitement de zéro sortie acceptable ; effort humain et opérations consignés séparément>` |
| Latence | `<mesure et résumé>` |
| Couverture du harnais | `<mesure et condition d’abstention>` |
| Provenance | `<champs obligatoires>` |
| Budget | `<facultatif, valeur et autorité si présent>` |
| Front de Pareto | taux d'acceptation officiel maximisé, coût fournisseur par sortie officiellement acceptable minimisé, latence préenregistrée minimisée ; couverture hors axes |
| Préférence de recommandation | `<explicite ou absente>` |

Sans préférence explicite suffisante, présenter toutes les configurations compatibles et comparables, y compris les plus chères, puis le front de Pareto observé. Ne pas désigner un gagnant unique.

## 12. Sources publiques de contexte

| Source primaire | Date de publication ou de collecte | Signal utilisé | Comparabilité | Fraîcheur | Limites |
|---|---|---|---|---|---|
| `<URL>` | `<date>` | `<signal>` | `<comparable ou contexte seulement>` | `<état>` | `<limites>` |

Ne fusionner aucun score incomparable et ne créer aucun score global. Les essais Lab-X priment seulement pour le workflow exact mesuré.

## 13. Cycle de vie

| Événement | Condition | Action |
|---|---|---|
| Qualification | `<preuves et approbation liées aux empreintes>` | rendre la version admissible |
| Révision | `<stimulus, acceptabilité ou conclusion modifiés>` | créer une nouvelle version |
| Exécution | `<campagne verrouillée et autorisée>` | écrire des reçus immuables |
| Retrait | `<obsolescence, contamination, fuite ou proxy inadéquat>` | retirer sans effacer l’historique |

## 14. Checklist de qualification

- [ ] besoin exact, décision réelle et conclusion permise explicites
- [ ] stimulus et interface de sortie liés par empreinte
- [ ] aucune donnée client réelle, aucun secret, connecteur de production ou action externe
- [ ] contrôles automatiques entièrement décidables par code
- [ ] rubrique humaine aveugle versionnée
- [ ] formule `PASS automatique + ACCEPTABLE humain` appliquée
- [ ] juge fantôme placé après gel humain et sans effet officiel
- [ ] témoins, provenance, attentes et limites documentés
- [ ] plan de mesure justifié sans valeur arbitraire
- [ ] panel, configurations et politiques de routage identifiés sans ambiguïté
- [ ] incidents fournisseur et défauts du harnais séparés
- [ ] règles de coût, latence, couverture, provenance et abstention préenregistrées
- [ ] approbation humaine liée aux empreintes obtenue
