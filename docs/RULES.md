---
style_gate: pass
---

# Règles de Benchmark Lab-X

Décisions propriétaires intégrées : 31 août 2026

**FAIT ÉTABLI** : ces règles ne modifient pas les contrats historiques de V0 ou V1 et n'autorisent aucune exécution.

## 1. Autorité et preuve

**Autorité exacte.** Aucune tâche, contrat, campagne, acquisition, retry, dépense ou publication n'acquiert autorité sans décision explicite qui nomme son périmètre.

**Aucune promotion implicite.** Une Issue fermée, un statut `Done`, une PR verte, un document présent ou un test réussi ne prouve ni satisfaction du contrat, ni autorisation d'exécuter.

**Statut lisible.** Une affirmation durable est un `FAIT ÉTABLI`, une `DÉCISION PROPRIÉTAIRE`, une `DÉDUCTION RAISONNÉE` ou une `HYPOTHÈSE NON VÉRIFIÉE`. Une déduction nomme ses prémisses ; une hypothèse nomme la preuve attendue.

## 2. Objet produit et unité de preuve

**Modèle mis en avant.** Le premier prototype répond à une question sur les modèles.

**Configuration observée.** Le modèle est l'identifiant principal présenté ; le verdict porte sur sa configuration observée sous les conditions de test communes, jamais sur le nom du modèle seul.

**Attribution bornée.** Aucune restitution n'attribue au seul modèle un effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer, ni n'affirme que le modèle isolé aurait produit le même résultat sous un autre harnais, fournisseur, contexte ou environnement.

**Conclusion située.** Toute conclusion nomme la tâche, le contrat, les configurations, les conditions de test communes, les preuves et la date.

## 3. Périmètre actif

**Accès direct ou API.** Le premier prototype compare uniquement des modèles accessibles directement ou par API.

**Pi obligatoire.** Pi est le harnais constant de ce prototype. Son choix n'est pas rouvert par une revue de configuration.

**Conditions de test communes.** Pi (paquet ou fork, version, paquets, outils, skills, contexte, réglages par défaut), l'environnement et la date de gel forment un objet unique, déclaré avant le premier candidat et référencé par toutes les configurations comparées ; ils sont présentés une fois, jamais répétés par modèle. Chaque valeur porte son statut, déclarée, configurée, active ou observée ; une valeur absente reste `INCONNU`. Une condition commune modifiée ouvre une nouvelle comparaison.

**Éléments différés.** Abonnements, produits agentiques, comparaison de harnais, autres harnais dépouillés, OrbStack et `perso-hermes` restent hors du premier prototype.

## 4. Contrat avant exécution

**Rôles génériques.** Le produit connaît deux rôles : le demandeur-lecteur, qui exprime son besoin et lit la restitution, et le responsable de campagne, qui prépare et approuve le contrat de réussite avant toute exécution, déclare les conditions communes et répond des verdicts. Les deux rôles peuvent être tenus par la même personne dans le premier prototype. Aucun rôle n'est lié à une personne, un compte, une organisation ou un pseudonyme ; Ayo reste l'autorité actuelle du projet et des décisions documentaires, jamais une identité produit.

**Préparation et approbation.** Le demandeur-lecteur n'invente ni seuil ni méthode de jugement ; le responsable de campagne fixe le contrat avant toute exécution.

**Contenu minimal.** Le contrat contient un résultat attendu, des obligations, des erreurs éliminatoires, les trois verdicts permis et au maximum deux critères secondaires, chacun avec unité et sens favorable s'il doit départager. Il fixe aussi le périmètre d'attribution du coût, les tentatives comptées, l'unité commune et, si nécessaire, la règle de conversion.

**Gel.** Une modification après observation d'une sortie crée un nouveau contrat. Elle ne requalifie pas la sortie antérieure.

**Aucune métrique hors contrat.** Qualité, stabilité, répétitions ou statistiques ne sont ajoutées que si la tâche les définit avant l'exécution et si un besoin observé les justifie.

## 5. Sortie et provenance

**Sortie brute.** La sortie candidate obtenue est conservée telle quelle, avant correction, transformation ou jugement.

**Demande et observation séparées.** L'identité demandée et l'identité observée restent distinctes. Une observation absente vaut `INCONNU`.

**Reçus reliés.** Configuration, acquisition, sortie, contrôle et verdict restent des preuves distinctes reliées par des identités vérifiables.

**Pas de fallback silencieux.** Un changement de modèle, fournisseur, route, paramètres ou effort de raisonnement change la configuration observée ; les valeurs demandées et observées de fournisseur, modèle, route et effort sont relevées par candidat. Une valeur non prouvée reste `INCONNU`. Un changement de Pi, paquet, outil, skill, contexte ou environnement modifie les conditions communes.

## 6. Erreurs et verdict

**Erreurs éliminatoires d'abord.** Une erreur éliminatoire établie interdit `SATISFAIT`, quel que soit le coût.

**Trois verdicts.** Le verdict est exactement `SATISFAIT`, `NE SATISFAIT PAS` ou `INDETERMINE`.

**Preuve insuffisante.** Une preuve absente, contradictoire ou inutilisable produit `INDETERMINE`, jamais un succès ou un échec inventé.

**Erreur du harnais séparée.** `HARNESS_ERROR` empêche l'attribution et réduit la couverture. Il ne devient pas automatiquement `NE SATISFAIT PAS`.

**Verdict explicable.** Tout verdict publiable porte sa valeur, un motif court intelligible, les critères ou constats concernés, les références de preuve et son responsable. Les obligations prouvées expliquent `SATISFAIT` ; une erreur éliminatoire ou une obligation non remplie explique `NE SATISFAIT PAS` ; une preuve insuffisante explique `INDETERMINE`. Aucune taxonomie exhaustive de motifs ni entrepôt de preuves n'est requis.

## 7. Ordre de décision

L'ordre est obligatoire :

1. erreurs éliminatoires ;
2. obligations et preuve ;
3. verdict d'admissibilité ;
4. exclusion de `NE SATISFAIT PAS` et `INDETERMINE` de la recommandation économique ;
5. coût connu et comparable entre les seuls `SATISFAIT` ;
6. bénéfices prévus des options `SATISFAIT` plus chères.

Le coût ne compense jamais une non-admissibilité. Ces six opérations internes ne sont pas les deux étapes visibles de la restitution.

## 8. Coût et bénéfices

**Base de coût gelée.** Avant l'exécution, le contrat fixe le périmètre d'attribution, les tentatives comptées, l'unité commune et, si nécessaire, la règle de conversion.

**Coût observable.** Le coût comprend les tentatives imputables selon cette base. Une valeur absente reste `INCONNU` : ni zéro, ni estimation, ni maximum. Seuls les coûts connus et comparables peuvent ordonner les configurations `SATISFAIT`.

**Conclusion économique incomplète.** Si le coût d'au moins une configuration `SATISFAIT` est `INCONNU` ou non comparable, elle reste admissible sur les critères non économiques et les coûts connus restent visibles, mais aucune option n'est déclarée globalement moins chère. La conclusion économique porte la mention `INCOMPLETE`, qui n'est pas un quatrième verdict. Si le coût est une obligation figée avant exécution, un coût `INCONNU` interdit de la déclarer satisfaite.

**Co-moins-chères.** Des coûts observés égaux restent une égalité et donnent plusieurs options co-moins-chères ; aucune heuristique ne les départage.

**Bénéfice prévu.** L'intérêt d'une configuration `SATISFAIT` plus chère se limite aux critères secondaires déclarés avant l'exécution. Un critère ne départage que s'il est comparable, avec une unité et un sens favorable fixés avant l'exécution ; sinon il reste descriptif.

**Dépense visible.** Le coût consommé par une configuration non admissible peut rester visible comme dépense ; il est exclu de la recommandation économique.

**Aucun score global.** Admissibilité, coût et bénéfices ne sont ni moyennés, ni pondérés, ni fusionnés, ni réduits en note unique. Aucun meilleur modèle absolu, podium général ou classement universel n'est produit.

## 9. Incidents et inconnues

**Causalité prouvée.** Un incident n'est attribué au fournisseur, au modèle ou à Pi que si le reçu ou l'environnement autorisé l'établit.

**Valeurs littérales.** `INCONNU`, `INDETERMINE` et `HARNESS_ERROR` ne sont remplacés ni par zéro, ni par moyenne, ni par estimation.

**Couverture visible.** Toute conclusion indique les configurations exclues et la raison de leur exclusion.

## 10. Restitution

**Deux étapes publiques.** La restitution comporte exactement deux étapes visibles : admissibilité de toutes les configurations avec verdict et motif synthétique, puis coût observé et bénéfices prévus parmi les seules configurations `SATISFAIT`. Lorsque la conclusion économique est `INCOMPLETE`, les coûts connus restent visibles sans option déclarée globalement moins chère. Critères, preuves, incidents, inconnues et conditions communes s'ouvrent sur demande ; leur ouverture n'est pas une troisième étape.

**Minimum accessible.** La restitution contient la tâche, le contrat, les configurations, les conditions de test communes, les verdicts et leurs motifs, les coûts admissibles, les bénéfices prévus, les incidents, les inconnues, les limites et les preuves nécessaires. Contenu présent ne signifie pas contenu affiché d'emblée.

**Aucun visuel trompeur.** Aucun podium général, score global ou graphique n'implique un classement, une échelle ou une précision absents du contrat.

**Aucune tâche canonisée par la maquette.** `quote-thread-summary` reste un scénario réversible de compréhension ; la variante A de maquette reste une direction réversible de présentation, pas une architecture canonique.

**Publication explicite.** Une page locale, une CI verte ou une PR ouverte ne constitue pas une publication officielle.

## 11. KISS et évolution

**Règle KISS.** Une complexité entre seulement lorsqu'une itération antérieure démontre le besoin qu'elle résout.

**Première réponse suffisante.** Une tâche, un contrat minimal, Pi constant, trois verdicts et une restitution située suffisent au premier prototype.

**Pas d'anticipation.** Aucun profil d'abonnement, autre harnais, conteneur OrbStack, service `perso-hermes`, backend, base de données, répétition, statistique, score, rôle supplémentaire, compte, permission, schéma de données, moteur multicritère, formule de retour sur investissement ou heuristique de départage n'est conçu pour un besoin futur supposé.

**Évolution traçable.** Lorsqu'un besoin est observé, l'itération suivante nomme la preuve, la complexité ajoutée et la condition de retrait ou de révision.

## 12. Histoire

**Campagnes immuables.** V0, V1, preuves U-025 et reçus gardent leur identité, leur sémantique et leurs verdicts d'origine. Leur historique documentaire appartient à Git.

**Aucune requalification rétrospective.** Les campagnes historiques ne deviennent ni classement qualitatif, ni baseline, ni coût par résultat acceptable, ni recommandation.

**Preuve technique bornée.** Un `PASS` de témoin, transport, qualification, verrou ou préparation prouve seulement son objet technique.

**Artefacts V1 non normatifs.** Le générateur et la restitution de la campagne V1 restent inchangés sous leur identité d'origine. Ils sont non normatifs et sémantiquement incompatibles avec la spécification courante ; leurs anciennes références documentaires ne sont pas remappées et leur vocabulaire n'est pas repris.

**Phase V2-alpha.** `V2-alpha` nomme la prochaine phase. Ce nom ne valide ni architecture, ni découpage, ni panel, ni campagne, ni exécution ; ces décisions exigent une autorité explicite.

## 13. Arrêt

À l'épuisement de l'autorité ou en présence d'une preuve bloquante, la tranche s'arrête en `HOLD` sans retry, fallback, dépense ou extension implicite.
