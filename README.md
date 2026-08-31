---
style_gate: pass
---

# Benchmark Lab-X

Benchmark Lab-X aide à choisir un modèle pour une tâche précise à partir de preuves lisibles. Le produit met le modèle en avant, mais son verdict porte sur la configuration observée sous les conditions de test communes, Pi compris.

Les décisions ci-dessous ont été prises par Ayo. Ce worktree n'est pas intégré ; il n'autorise ni campagne, ni publication, ni canonisation d'un nom de version.

## Question active

> Pour une tâche précise et un contrat de réussite fixé avant l'exécution, quelles configurations associant un modèle à un accès direct ou API accomplissent la tâche sous le même Pi ? Parmi les configurations `SATISFAIT`, laquelle ou lesquelles coûtent le moins, et quels bénéfices prévus une option plus chère apporte-t-elle ?

Le modèle est l'objet produit présenté. La [configuration observée](CONTEXT.md#configuration-observée) est l'unité de preuve ; les [conditions de test communes](CONTEXT.md#conditions-de-test-communes), Pi, environnement et date de gel, sont déclarées une fois pour toutes les configurations comparées.

Le verdict ne permet pas d'isoler causalement le modèle. Il décrit la configuration observée sous les conditions communes déclarées et n'attribue pas au seul modèle un effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer.

## Accès et vocation publique

**DÉCISION PROPRIÉTAIRE** : l'accès et l'utilisation commencent avec la communauté Lab X afin d'éprouver le produit et d'y contribuer. Le produit a ensuite vocation à devenir public et accessible à tous.

Cette vocation ne signifie pas que Benchmark Lab-X est déjà publié. Tout merge, publication ou changement d'accès exige une autorité distincte.

## Premier prototype

Le premier prototype est volontairement étroit :

- une tâche possède un contrat de réussite préparé et approuvé par le responsable de campagne avant toute exécution
- seuls les modèles accessibles directement ou par API sont comparés
- Pi est le harnais obligatoire et constant
- l'état de Pi appartient aux conditions de test communes déclarées avant le premier candidat ; son état relevé le 30 août 2026 est détaillé dans l'[ARD](docs/specification/ARD.md#31-état-de-pi-relevé-le-30-août-2026)
- les erreurs éliminatoires précèdent le verdict d'admissibilité
- le coût n'est comparé qu'entre les configurations `SATISFAIT`
- les bénéfices d'une option admissible plus chère se limitent aux critères prévus dans le contrat

Le contrat et les trois verdicts sont définis dans le [glossaire](CONTEXT.md). Le [gabarit de carte](tasks/TEMPLATE.md) sert à les préparer.

## Restitution

Une restitution publique comporte exactement deux étapes :

1. admissibilité : chaque configuration comparée reçoit son verdict et un motif synthétique ;
2. comparaison économique : coût observé et bénéfices prévus parmi les seules configurations `SATISFAIT`.

Critères, preuves, incidents, inconnues et conditions de test communes restent accessibles sur demande ; leur ouverture n'est pas une troisième étape. Elle ne produit ni score global, ni podium général, ni meilleur modèle absolu, ni graphique trompeur. Toute conclusion reste bornée à la tâche, au contrat, au panel, à la date et à la configuration observée sous les conditions communes.

## Éléments différés

Les abonnements, les produits agentiques, la comparaison de harnais, les autres harnais dépouillés, OrbStack et `perso-hermes` ne font pas partie du premier prototype. Ils pourront être étudiés dans une itération ultérieure seulement si un besoin observé le justifie, selon la règle KISS des [règles](docs/specification/RULES.md#11-kiss-et-évolution).

Le scénario `quote-thread-summary` sert uniquement à une maquette réversible. Il ne devient pas la tâche canonique d'un futur benchmark.

## État historique établi

### V0

**FAIT ÉTABLI** : la campagne V0 a porté sur deux configurations API, Grok et Kimi, avec une acquisition prévue par configuration et sans répétition. Une seule sortie candidate a été obtenue. La sortie Grok a échoué au contrôle `G-001`. Kimi a fini en `HARNESS_ERROR`. Aucun dossier de revue humaine ni verdict humain n'a été produit. La couverture est restée à `1/2`, le coût total `INCONNU`, le coût par sortie acceptable `NON_DEFINI`, et la restitution a conclu à l'abstention. Les preuves locales de préparation ou de qualification de l'instrument ne changent pas ce bilan produit.

### V1

**FAIT ÉTABLI** : la campagne V1 a porté sur sept produits d'abonnement. Elle a conservé treize reçus et six sorties sur sept configurations. Les six sorties ont échoué mécaniquement à `G-001` ; aucune n'a obtenu `PASS`, aucun dossier de revue humaine officiel n'a été constitué, et aucun verdict humain n'a été rendu. Le coût d'abonnement par sortie acceptable est `NON_DEFINI`. Aucun classement qualitatif, gagnant ou recommandation rétrospective n'est soutenu.

- [Guide d'utilisation historique de la campagne V1](tasks/dev/pre-cadrage-entretien-client/campagne-v1/guide-utilisation-v1/README.md)

**FAIT ÉTABLI** : le stimulus approuvé montre un bloc d'exemple introduit par une clôture Markdown `yaml`, tandis que `G-001` exige `---` sur la première ligne. Ce conflit explique pourquoi les six `FAIL G-001` ne peuvent pas être transformés en conclusion qualitative.

V0 et V1 restent des campagnes historiques sous leurs contrats d'origine. Elles n'établissent ni classement qualitatif, ni baseline, ni coût par résultat acceptable, ni recommandation rétrospective.

## Documents

- [PRD](docs/specification/PRD.md) : besoin, audience, périmètre actif et résultat produit
- [ARD](docs/specification/ARD.md) : objets, conditions de test communes, état de Pi, flux et frontière d'attribution
- [Règles](docs/specification/RULES.md) : invariants, ordre de décision et KISS
- [Glossaire](CONTEXT.md) : vocabulaire du domaine et des deux rôles
- [Gabarit de carte](tasks/TEMPLATE.md) : contrat d'une future tâche
- [Dossier de refondation](docs/REFONDATION-PRODUIT-2026-08-29.md) : sources, faits, conflits et décisions documentaires

## Autorité et limites

**DÉCISION PROPRIÉTAIRE** : Ayo est l'autorité actuelle du projet et des décisions documentaires. Les rôles produit, [demandeur-lecteur](CONTEXT.md#demandeur-lecteur) et [responsable de campagne](CONTEXT.md#responsable-de-campagne), ne sont liés à aucune personne, compte ou pseudonyme et peuvent être tenus par la même personne dans le premier prototype.

**FAIT ÉTABLI** : cette harmonisation ne lance aucun appel candidat, acquisition, retry, achat, dépassement, campagne ou publication. Elle ne fusionne ni ne ferme aucune Issue ou PR. Les preuves et campagnes historiques restent les sources de leurs seuls faits observés.

**FAIT ÉTABLI** : la page GitHub Pages de `main` est encore un placeholder. Les propositions de restitution ouvertes dans les PR [#94](https://github.com/ayoahha/benchmark-lab-x/pull/94) et [#151](https://github.com/ayoahha/benchmark-lab-x/pull/151) ne sont ni fusionnées ni des preuves de résultat produit.

**FAIT ÉTABLI** : l'état de travail vit dans le champ `Status` du [Project personnel #5](https://github.com/users/ayoahha/projects/5) ; cet état de suivi ne prouve jamais une réussite produit.
