---
style_gate: pass
---

# Benchmark Lab-X

Benchmark Lab-X mesure des configurations de modèles sur des cartes d’usage. Une série scientifique peut réunir plusieurs lots techniques lorsque leurs acquisitions satisfont le même contrat de compatibilité.

## Langage

**Identité de modèle** :
Le modèle canonique demandé et sa révision déclarée.
_À éviter_ : candidat, provider

**Identité de route** :
Le backend, le provider et l’endpoint qui servent une acquisition.
_À éviter_ : identité de modèle

**Configuration scientifique** :
L’identité de modèle, la quantification, l’effort, les paramètres, le contexte et la politique de données dont l’égalité autorise une comparaison.
_À éviter_ : nom du modèle seul

**Slot** :
L’emplacement unique d’une acquisition dans une série, identifié par un alias et un index de run.
_À éviter_ : tentative, réponse

**Acquisition** :
Un artefact candidat accepté avec sa chaîne de reçus, son coût et sa route observée.
_À éviter_ : tentative, score

**Lot d’acquisition** :
Un ensemble technique de slots soumis sous un même lock et un même registre budgétaire.
_À éviter_ : série, classement

**Source de collecte** :
Le commit qui fournit le lanceur, l’adaptateur de route et la machine d’état d’un lot.
_À éviter_ : source de l’instrument

**Source de l’instrument** :
Le commit qui fournit la tâche et les actifs couverts par les `verify_hash` réutilisés.
_À éviter_ : source de collecte

**Série de mesure** :
La grille scientifique complète de slots compatibles, composée depuis un ou plusieurs lots d’acquisition.
_À éviter_ : lot, exécution

**Fallback de route** :
La route secondaire préenregistrée d’une configuration scientifique, utilisable dans un nouveau lot après épuisement de la route primaire sans artefact accepté.
_À éviter_ : bascule silencieuse, retry de provider
