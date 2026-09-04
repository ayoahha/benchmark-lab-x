---
style_gate: pass
---

# Règles de Benchmark Lab-X

Ces règles préservent les contrats historiques et n'autorisent aucune exécution. Elles ne portent aucun statut de livraison des versions.

## 1. Autorité et preuve

**Autorité exacte.** Aucune tâche, contrat, campagne, acquisition, retry, dépense ou publication n'acquiert autorité sans décision explicite qui nomme son périmètre.

**Aucune promotion implicite.** Une Issue fermée, un statut `Done`, une PR verte, un document présent ou un test réussi ne prouve ni satisfaction du contrat, ni autorisation d'exécuter.

**Nature des affirmations.** Distinguer fait prouvé, décision d'Ayo, recommandation et inconnu. Une déduction nomme ses prémisses ; une recommandation ne se présente pas comme une décision. Les états de livraison vivent dans GitHub et les reçus, hors des spécifications. Les statuts d'observation d'une donnée ne sont pas des statuts de livraison.

## 2. Objet produit et unité de preuve

**Modèle mis en avant.** Le produit aide à choisir un modèle pour une tâche précise.

**Configuration observée.** Le modèle est l'identifiant principal présenté ; le verdict porte sur sa configuration observée sous les conditions de test communes, jamais sur le nom du modèle seul.

**Attribution bornée.** Aucune restitution n'attribue au seul modèle un effet que le fournisseur, l'effort, Pi ou ses réglages peuvent influencer, ni n'affirme que le modèle isolé aurait produit le même résultat sous un autre harnais, fournisseur, contexte ou environnement.

**Conclusion située.** Toute conclusion nomme la version de tâche, les cas et tentatives couverts, la campagne, le contrat, les configurations, les conditions communes, les preuves et la date. Une réussite sur un cas ne prouve pas une fiabilité générale.

## 3. Périmètre produit

**Accès direct ou API.** Le produit compare des modèles accessibles directement ou par API.

**Pi obligatoire.** Pi est le harnais commun de chaque comparaison. Son choix n'est pas rouvert par une revue de configuration.

**Conditions de test communes.** Pi (paquet ou fork, version, paquets, outils, skills, contexte, réglages par défaut), l'environnement et la date de gel forment un objet unique, déclaré avant le premier candidat et référencé par toutes les configurations comparées ; ils sont présentés une fois, jamais répétés par modèle. Chaque valeur porte son statut, déclarée, configurée, active ou observée ; une valeur absente reste `INCONNU`. Une condition commune modifiée ouvre une nouvelle comparaison.

**Périmètre décidé.** Les extensions suivent le PRD. Le lot V2 bêta ne comprend aucune contribution publique. Choisir un panel ne prouve ni la disponibilité des configurations ni l'autorisation de les appeler.

## 4. Contrat avant exécution

**Rôles génériques.** Le produit connaît deux rôles : le demandeur-lecteur, qui exprime son besoin et lit la restitution, et le responsable de campagne, qui prépare et approuve le contrat de réussite avant toute exécution, déclare les conditions communes et répond des verdicts. Les deux rôles peuvent être tenus par la même personne si le besoin le permet. Aucun rôle produit n'est lié à une personne ou à un compte nommé. Les décisions du propriétaire restent distinctes des rôles du produit.

**Préparation et approbation.** Le demandeur-lecteur n'invente ni seuil ni méthode de jugement ; le responsable de campagne fixe le contrat avant toute exécution.

**Contenu minimal.** Le contrat contient un résultat attendu, des obligations, des erreurs éliminatoires, les trois verdicts permis et au maximum deux critères secondaires, chacun avec unité et sens favorable s'il doit départager. Il fixe aussi le périmètre d'attribution du coût, les tentatives comptées, l'unité commune et, si nécessaire, la règle de conversion.

**Gel.** Chaque version de tâche identifie son contrat et ses cas. Toute agrégation de verdicts est définie avant exécution ; sans règle, seuls les verdicts par cas sont permis. Modifier le contrat ou les cas après observation crée une nouvelle version et ne requalifie pas les sorties antérieures.

**Aucune métrique hors contrat.** Qualité, stabilité, répétitions ou statistiques ne sont ajoutées que si la tâche les définit avant l'exécution et si un besoin observé les justifie.

## 5. Sortie et provenance

**Sortie brute.** La sortie candidate obtenue est conservée telle quelle, avant correction, transformation ou jugement.

**Demande et observation séparées.** L'identité demandée et l'identité observée restent distinctes. Une observation absente vaut `INCONNU`.

**Reçus reliés.** Configuration, acquisition, sortie, contrôle et verdict restent des preuves distinctes reliées par des identités vérifiables.

**Révision imposée.** Lorsqu'une révision de modèle est exigée, un alias mobile ne la remplace pas sans preuve de correspondance. Une identité non vérifiable bloque son utilisation sous cette identité ; aucune substitution implicite n'est permise.

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

Le coût ne compense jamais une non-admissibilité. Cet ordre de décision n'impose pas une succession de deux sections à l'écran.

## 8. Coût et bénéfices

**Base de coût gelée.** Avant l'exécution, le contrat fixe le périmètre d'attribution, les tentatives comptées, l'unité commune et, si nécessaire, la règle de conversion.

**Coût observable.** Le coût comprend les tentatives imputables selon cette base. Une valeur absente reste `INCONNU` : ni zéro, ni estimation, ni maximum. Seuls les coûts connus et comparables peuvent ordonner les configurations `SATISFAIT`.

**Conclusion économique incomplète.** Si le coût d'au moins une configuration `SATISFAIT` est `INCONNU` ou non comparable, elle reste admissible sur les critères non économiques et les coûts connus restent visibles, mais aucune option n'est déclarée globalement moins chère. La conclusion économique porte la mention `INCOMPLETE`, qui n'est pas un quatrième verdict. Si le coût est une obligation figée avant exécution, un coût `INCONNU` interdit de la déclarer satisfaite.

**Contrôle de dépense.** L'autorisation nomme les tentatives et l'enveloppe. Prévision, réservation avant appel, coût observé et limite du fournisseur restent distincts. Un contrôle d'admission ne prouve pas un plafond absolu de facturation. Un coût local n'est pas nul par défaut.

**Co-moins-chères.** Des coûts observés égaux restent une égalité et donnent plusieurs options co-moins-chères ; aucune heuristique ne les départage.

**Bénéfice prévu.** L'intérêt d'une configuration `SATISFAIT` plus chère se limite aux critères secondaires déclarés avant l'exécution. Un critère ne départage que s'il est comparable, avec une unité et un sens favorable fixés avant l'exécution ; sinon il reste descriptif.

**Dépense visible.** Le coût consommé par une configuration non admissible reste visible comme dépense ; il est exclu de la recommandation économique.

**Aucun score global.** Admissibilité, coût et bénéfices ne sont ni moyennés, ni pondérés, ni fusionnés, ni réduits en note unique. Aucun meilleur modèle absolu, podium général ou classement universel n'est produit.

## 9. Incidents et inconnues

**Causalité prouvée.** Un incident n'est attribué au fournisseur, au modèle ou à Pi que si le reçu ou l'environnement autorisé l'établit.

**Valeurs littérales.** `INCONNU`, `INDETERMINE` et `HARNESS_ERROR` ne sont remplacés ni par zéro, ni par moyenne, ni par estimation.

**Couverture visible.** Toute conclusion indique les cas, configurations et tentatives prévus, observés ou manquants. Une campagne partielle conserve les preuves acquises ; une cellule manquante n'est pas un échec attribué au modèle. Les limites de la conclusion restent visibles.

**Reprise sans replay implicite.** Une intention d'appel doit être enregistrée avant émission. Une tentative partie aux effets inconnus reste ambiguë ; ni redémarrage ni déploiement n'autorise son replay. Les reprises et nouvelles tentatives exigent les preuves et l'autorité correspondantes.

## 10. Restitution

**Lecture publique.** Le parcours catalogue, tâche, campagne expose la conclusion contextualisée, un tableau commun des configurations et les preuves sur demande. L'admissibilité gouverne la recommandation économique. Une conclusion `INCOMPLETE` laisse visibles les coûts connus sans option déclarée globalement moins chère.

**Minimum accessible.** La restitution contient la tâche, le contrat, les configurations, les conditions de test communes, les verdicts et leurs motifs, les coûts observés de toutes les configurations avec leur statut économique, les bénéfices prévus, les incidents, les inconnues, les limites et les preuves nécessaires. Contenu présent ne signifie pas contenu affiché d'emblée.

**Aucun visuel trompeur.** Aucun podium général, score global ou graphique n'implique un classement, une échelle ou une précision absents du contrat.

**Preuves accessibles.** Une pièce publiée relie l'entrée, la sortie exacte et les passages justifiant le verdict. Une empreinte ne remplace pas cette pièce ; une restriction d'accès est signalée. Un scénario de maquette ne devient pas implicitement une tâche du catalogue.

**Publication explicite.** Une page locale, une CI verte ou une PR ouverte ne constitue pas une publication officielle. Intégration Git, exécution produit, appels candidats et budget, provisionnement et publication gardent des autorités distinctes.

## 11. KISS et évolution

**Règle KISS.** Une complexité entre seulement lorsqu'une itération antérieure démontre le besoin qu'elle résout.

**Résultat suffisant.** Livrer les capacités nécessaires au catalogue et aux campagnes décidés. Une démonstration du moteur ne remplace pas les résultats réels attendus.

**Pas d'anticipation.** Réutiliser les primitives retenues dans l'ARD. Aucun microservice, Kubernetes, bus de messages, système de plugins, moteur multicritère ou abstraction spéculative n'est ajouté sans besoin démontré. Les contributions publiques et leur gestion de comptes ne sont pas construites par anticipation.

**Évolution traçable.** Lorsqu'un besoin est observé, l'itération suivante nomme la preuve, la complexité ajoutée et la condition de retrait ou de révision.

## 12. Histoire

**Campagnes immuables.** Les campagnes, preuves et reçus historiques gardent leur identité, leur sémantique et leurs verdicts d'origine. Leur historique documentaire appartient à Git.

**Aucune requalification rétrospective.** Les campagnes historiques ne deviennent ni classement qualitatif, ni baseline, ni coût par résultat acceptable, ni recommandation.

**Preuve technique bornée.** Un `PASS` de témoin, transport, qualification, verrou ou préparation prouve seulement son objet technique.

**Artefacts historiques non normatifs.** Les générateurs et restitutions historiques restent sous leurs contrats d'origine. Leurs anciennes références ne sont pas remappées implicitement et leur vocabulaire ne remplace pas la spécification courante.

## 13. Arrêt

À l'épuisement de l'autorité ou en présence d'une preuve bloquante, la tranche s'arrête en `HOLD` sans retry, fallback, dépense ou extension implicite.
