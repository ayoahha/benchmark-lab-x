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

**Conditions de test communes.** L’objet défini par l’[ARD](ARD.md#42-conditions-de-test-communes) est gelé avant le premier candidat et référencé par toutes les configurations comparées. Une condition commune modifiée ouvre une nouvelle comparaison. Un paramètre propre au candidat ne doit pas être présenté comme une condition partagée.

**Périmètre décidé.** Le périmètre, le panel nominal et les exclusions appartiennent au [PRD](PRD.md#5-périmètre-produit). Choisir un panel ne prouve ni la disponibilité des configurations ni l’autorisation de les appeler.

## 4. Contrat avant exécution

**Rôles génériques.** Le produit connaît deux rôles : le demandeur-lecteur, qui exprime son besoin et lit la restitution, et le responsable de campagne, qui prépare et approuve le contrat de réussite avant toute exécution, déclare les conditions communes et répond des verdicts. Les deux rôles peuvent être tenus par la même personne si le besoin le permet. Aucun rôle produit n'est lié à une personne ou à un compte nommé. Les décisions du propriétaire restent distinctes des rôles du produit.

**Préparation et approbation.** Le demandeur-lecteur n'invente ni seuil ni méthode de jugement ; le responsable de campagne fixe le contrat avant toute exécution.

**Contenu minimal.** Le contrat contient un résultat attendu, des obligations, des erreurs éliminatoires, une référence de jugement, une méthode d’évaluation, les trois verdicts permis et au maximum deux critères secondaires, chacun avec unité et sens favorable s'il doit départager. Il fixe aussi le périmètre d'attribution du coût, les tentatives comptées, l'unité commune et, si nécessaire, la règle de conversion.

**Usage et tolérances.** Chaque obligation justifie son utilité pour le résultat demandé. Le contrat décrit l’intervention humaine qui reste nécessaire et les variations recevables de forme, de contenu ou de méthode de calcul pour chaque critère concerné, dans le respect des exigences de la tâche. Une reformulation correcte ne devient pas une erreur parce qu’elle diffère d’un exemple ; une correction de fond ne devient pas une simple relecture. Aucun seuil de similarité ni tolérance numérique universelle n’est déduit de ces principes.

**Référence de jugement.** La référence relie les attendus aux faits, passages, calculs ou contraintes qui les justifient. Elle prévoit les réponses alternatives recevables, les informations insuffisantes et les désaccords possibles ; un texte idéal ou une liste de sources attendues ne suffit pas à rejeter une solution différente mais étayée. Une source métier précise sa version, sa date, son périmètre d’application et ses droits d’usage ; un référentiel inventé permet un exercice de raisonnement, sans prouver une connaissance du droit, de la santé ou des pratiques professionnelles réels. La consigne expose les exigences nécessaires au travail et les informations normalement accessibles dans l’usage visé. Le contrat distingue les ressources accessibles au candidat des éléments réservés à l’évaluation. Si une référence lui est montrée, cette exposition et ce qu’elle change à la mesure sont déclarés.

**Gel.** Chaque version de tâche identifie son contrat, ses cas, les octets des entrées initiales, la référence de jugement et la méthode d’évaluation. Le contrat approuvé est immuable ; une modification crée une nouvelle version et ne requalifie pas les sorties antérieures. Le contrat fixe l’accès et les preuves à conserver pour une consultation externe ; les résultats effectivement obtenus sont des observations, sans promesse de stabilité des sources. Chaque campagne fige la sélection de cas, le plan des tentatives et les conditions communes avant exécution.

**Agrégation explicite.** La règle fixe la forme et la portée du résultat, les cas et tentatives pris en compte, leur dénominateur et le traitement des manquants, incidents et verdicts `INDETERMINE`. Sans règle préalable, seuls les verdicts par cas et tentative sont permis. Aucune sélection après coup des meilleurs cas ou essais ne peut soutenir une conclusion globale ; les observations exclues et leur motif restent visibles.

**Charge, difficulté et portée.** La charge décrit une quantité de travail dans une unité déclarée ; la difficulté décrit les contraintes du cas qui peuvent rendre sa résolution délicate. Un volume supérieur ne prouve pas à lui seul une difficulté supérieure. Si le contrat emploie des niveaux, il définit leurs dimensions et critères avant exécution, dans le périmètre de la tâche ; aucun nombre de niveaux ni échelle universelle n’est imposé. Une réussite au niveau le plus élevé testé ne prouve ni une capacité maximale ni la réussite de tous les niveaux inférieurs non testés. Un libellé de famille ou de difficulté ne suffit pas à rendre des cas comparables ou à produire des statistiques générales : les règles d’agrégation et de représentativité restent applicables.

**Méthode vérifiable.** Chaque obligation et erreur éliminatoire nomme le contrôle, sa version, ses preuves attendues et le responsable du jugement. Un contrôle automatique ne prouve que les propriétés qu’il sait décider, avec des témoins adaptés. Une évaluation humaine ou assistée conserve ses constats et les décisions requises ; la seule présence d’un commentaire ou d’un nom de rôle ne prouve pas son approbation.

**Qualification de l’épreuve.** Avant l’approbation du contrat, le responsable vérifie la cohérence entre besoin, consigne, cas, référence et contrôles : exactitude des sources et calculs, solution recevable, défauts ciblés et situations ambiguës lorsque le contrat en comporte. Des témoins adaptés vérifient aussi qu’une alternative valable peut être acceptée lorsqu’il en existe, et qu’un défaut pertinent peut être détecté ; leur nombre dépend de ce qui doit être contrôlé. Les preuves et limites de cette qualification restent consultables. Elles référencent l’empreinte du contrat candidat sans entrer dans son calcul ; l’approbation lie ensuite cette même empreinte aux preuves de qualification. Si la préparation change le contrat candidat, la qualification doit porter sur les octets finalement soumis à l’approbation. Une préparation exploratoire sert à corriger l’épreuve ; ses résultats ne deviennent pas implicitement ceux d’une comparaison sous contrat gelé.

**Revue assistée et compétence métier.** Un modèle généraliste ou spécialisé peut proposer des cas, critiquer la référence ou assister le jugement. Son avis doit être confronté aux sources et aux contrôles ; ni son statut de modèle frontière, ni sa spécialisation, ni l’accord de plusieurs modèles ne prouvent la justesse de l’attendu. Consigner la configuration et les consignes utilisées, les sources consultées, les constats, les désaccords et leur arbitrage. Une relecture critique distincte de la rédaction réduit la dépendance au premier avis sans prouver l’indépendance des erreurs des modèles. Lorsqu’un assistant et un candidat partagent un modèle ou un fournisseur, ce lien et le risque d’auto-préférence sont déclarés ; des identités différentes ne prouvent pas l’indépendance. Une revue professionnelle n’est pas obligatoire pour toute tâche : sa présence, sa phase, son périmètre ou son absence sont déclarés. En son absence, limiter les conclusions aux propriétés dont les preuves permettent effectivement le jugement. L’approbation du responsable engage sa décision ; elle ne transforme pas un avis incertain en fait métier ni en certification.

**Aucune métrique hors contrat.** Qualité, stabilité, répétitions ou statistiques ne sont ajoutées que si la tâche les définit avant l’exécution et si un besoin observé les justifie.

**Représentativité et biais.** La conclusion expose pourquoi les cas ont été choisis, les difficultés et populations d’usage non couvertes, la nature synthétique ou réelle des entrées, les conditions d’ordre, de contexte et de jugement susceptibles d’influencer le résultat. Une exposition antérieure possible des données aux modèles ou aux évaluateurs est signalée lorsqu’elle est connue ; son absence de preuve ne démontre pas l’absence de contamination. Le responsable documente les protections retenues et les limites restantes. Répétitions, ordre ou randomisation, aveuglement et protocole statistique restent des choix à approuver, sans nombre ni seuil imposé ici. Sans répétition décidée et observée, aucune stabilité n’est démontrée ; lorsqu’il y en a, les essais individuels et leur variabilité restent visibles selon la règle préenregistrée.

## 5. Sortie et provenance

**Sortie brute.** La sortie candidate obtenue est conservée telle quelle, avant correction, transformation ou jugement.

**Demande et observation séparées.** L'identité demandée et l'identité observée restent distinctes. Une observation absente vaut `INCONNU`.

**Reçus reliés.** Demande, observation, tentative, sortie, contrôle, évaluation et conclusion restent distincts et reliés par des identités vérifiables. La provenance précise le producteur, la date, la source et la transformation éventuelle. Une empreinte vérifie des octets ; elle ne prouve ni l’authenticité du producteur, ni l’approbation, ni la justesse du jugement.

**Révision imposée.** Lorsqu'une révision de modèle est exigée, un alias mobile ne la remplace pas sans preuve de correspondance. Une identité non vérifiable bloque son utilisation sous cette identité ; aucune substitution implicite n'est permise.

**Pas de fallback silencieux.** Un changement de modèle, fournisseur, route, paramètres ou effort de raisonnement change la configuration observée ; les valeurs demandées et observées de fournisseur, modèle, route et effort sont relevées par candidat. Une valeur non prouvée reste `INCONNU`. Un changement de Pi, paquet, outil, skill, contexte ou environnement modifie les conditions communes.

## 6. Erreurs et verdict

**Erreurs éliminatoires d'abord.** Une erreur éliminatoire établie interdit `SATISFAIT`, quel que soit le coût.

**Trois verdicts.** Le verdict est exactement `SATISFAIT`, `NE SATISFAIT PAS` ou `INDETERMINE`.

**Application des verdicts.** Sur une observation intègre et attribuable, une erreur éliminatoire ou une obligation non remplie établie donne `NE SATISFAIT PAS`, même si un autre contrôle manque. `SATISFAIT` exige le résultat et toutes les obligations prouvés, sans erreur éliminatoire. Si l’intégrité, l’attribution ou les preuves nécessaires ne permettent ni réussite ni défaut établi, le verdict est `INDETERMINE`. Une panne technique seule ne prouve pas une erreur de contenu ; son éventuel effet sur une obligation de service doit être prévu par le contrat.

**Référence insuffisante.** Une incertitude portant sur l’attendu ou le contrôle se distingue d’une erreur candidate. Avant la comparaison, une obligation ou une erreur éliminatoire sans méthode suffisamment étayée empêche d’approuver la tâche en l’état ; reformuler le travail ou différer le cas permet de poursuivre la préparation sans fabriquer de certitude. Si le problème apparaît après acquisition, conserver les observations, expliciter la limite et appliquer les trois verdicts : un défaut prouvé indépendamment reste `NE SATISFAIT PAS` ; sinon une preuve nécessaire incertaine interdit `SATISFAIT` et conduit à `INDETERMINE`. Corriger la référence suit les règles de versionnement du contrat, sans réécrire l’histoire.

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

**Base de coût gelée.** Avant l’exécution, le contrat fixe le périmètre d’attribution, les tentatives comptées, l’unité commune et la conversion éventuelle. Les quantités de travail, cas et règles d’agrégation doivent être comparables : le total d’une couverture réduite ne démontre pas qu’une configuration est moins chère sur le travail complet.

**Coût observable.** Le coût comprend les tentatives imputables selon cette base. Une valeur absente reste `INCONNU` : ni zéro, ni estimation, ni maximum. Seuls les coûts connus et comparables peuvent ordonner les configurations `SATISFAIT`.

**Conclusion économique incomplète.** Si le coût d'au moins une configuration `SATISFAIT` est `INCONNU` ou non comparable, elle reste admissible sur les critères non économiques et les coûts connus restent visibles, mais aucune option n'est déclarée globalement moins chère. La conclusion économique porte la mention `INCOMPLETE`, qui n'est pas un quatrième verdict. Si le coût est une obligation figée avant exécution, un coût `INCONNU` interdit de la déclarer satisfaite.

**Préparation et jugement.** Les dépenses observées de création du corpus et d’évaluation sont identifiées séparément des appels candidats, avec le périmètre du relevé. Le temps humain n’est pas monétisé sans méthode décidée et mesure correspondante. Leur inclusion éventuelle dans une base de coût est déclarée avant comparaison, avec une imputation commune ; elles ne sont ni dissimulées dans le coût du modèle ni réputées nulles. Une revue assistée exige sa propre autorité d’appel et de dépense.

**Contrôle de dépense.** L’autorisation nomme les tentatives et l’enveloppe. Prévision, réservation avant appel, coût observé et limite du fournisseur restent distincts. Les réservations et dépenses actives sont prises en compte ensemble ; aucune même enveloppe ne peut être allouée deux fois. Un coût manquant ne libère pas une réservation et ne reconstitue pas un solde connu. Un contrôle d’admission ne prouve pas un plafond absolu de facturation. Un coût local n’est pas nul par défaut.

**Ensemble admissible.** Sans configuration `SATISFAIT`, la comparaison économique est sans objet et la restitution le dit explicitement. Avec une seule configuration admissible et un coût complet, elle peut être décrite comme seule admissible du périmètre, sans gain comparatif inventé.

**Co-moins-chères.** Des coûts observés égaux restent une égalité et donnent plusieurs options co-moins-chères ; aucune heuristique ne les départage. Un arrondi d’affichage ne crée pas une égalité de calcul.

**Bénéfice prévu.** L'intérêt d'une configuration `SATISFAIT` plus chère se limite aux critères secondaires déclarés avant l'exécution. Un critère ne départage que s'il est comparable, avec une unité et un sens favorable fixés avant l'exécution ; sinon il reste descriptif.

**Dépense visible.** Le coût consommé par une configuration non admissible reste visible comme dépense ; il est exclu de la recommandation économique. Un total auquel manque une dépense nécessaire reste inconnu ; la somme des montants connus est identifiée comme sous-total. Un coût manquant hors de l’ensemble admissible ne devient pas un critère de classement, mais peut bloquer l’admission du prochain appel si le budget restant n’est plus établi.

**Aucun score global.** Admissibilité, coût et bénéfices ne sont ni moyennés, ni pondérés, ni fusionnés, ni réduits en note unique. Aucun meilleur modèle absolu, podium général ou classement universel n'est produit.

## 9. Incidents et inconnues

**Causalité prouvée.** Un incident n'est attribué au fournisseur, au modèle ou à Pi que si le reçu ou l'environnement autorisé l'établit.

**Valeurs littérales.** `INCONNU`, `INDETERMINE` et `HARNESS_ERROR` ne sont remplacés ni par zéro, ni par moyenne, ni par estimation.

**Couverture visible.** Toute conclusion indique les cas, configurations et tentatives prévus, observés ou manquants. Une campagne partielle conserve les preuves acquises ; une cellule manquante n’est pas un échec attribué au modèle. L’agrégation ne conclut que sur la couverture permise par le contrat. La consultation d’une autre campagne n’autorise aucune fusion de cas ou comparaison de totaux incompatibles.

**Admission avant appel.** L’exécuteur vérifie les identités et empreintes gelées, la disponibilité du canal exact, l’environnement exigé, le stockage des preuves, les autorités et le budget restant. Une inconnue requise, une dérive ou une tentative active ou ambiguë empêchant cette admission bloque le nouvel appel. Un champ non observable que le contrat n’exige pas comme condition d’admission reste explicitement `INCONNU`, avec sa limite d’attribution.

**Reprise sans replay implicite.** Une intention d’appel doit être enregistrée avant émission. Après interruption, l’exécuteur rapproche intentions, reçus et dépenses avant d’admettre une cellule encore autorisée. Une tentative partie aux effets inconnus reste ambiguë ; ni redémarrage, restauration ni déploiement n’autorise son rejeu. Une nouvelle tentative exige une identité propre et l’autorité correspondante, sans effacer la précédente. Le détail de la procédure de reprise est à décider dans le contrat d’exploitation.

## 10. Restitution

**Lecture publique.** Le parcours et ses critères d’accessibilité sont définis par le [PRD](PRD.md#10-restitution-publique). L’ordre de calcul reste celui de la section 7, quel que soit l’agencement des écrans.

**Minimum accessible.** La restitution contient la tâche, le contrat, les configurations, les conditions de test communes, les verdicts et leurs motifs, les coûts observés de toutes les configurations avec leur statut économique, les bénéfices prévus, les incidents, les inconnues, les limites et les preuves nécessaires. Contenu présent ne signifie pas contenu affiché d'emblée.

**Aucun visuel trompeur.** Aucun podium général, score global ou graphique n'implique un classement, une échelle ou une précision absents du contrat.

**Preuves accessibles.** Une pièce publiée relie l’entrée, la sortie et les passages justifiant le verdict. La sortie exacte reste privée tant que sa publication n’est pas autorisée ; un extrait, masquage ou résumé publié est identifié comme dérivé, avec son lien à la source. Une empreinte ne remplace pas une pièce accessible. La restriction et son effet sur la vérification publique sont signalés. Un scénario de maquette ne devient pas implicitement une tâche du catalogue.

**Publication explicite.** L’approbation lie les octets de la projection et les pièces publiables à leur périmètre. Elle ne publie pas les données privées acquises ensuite. Une modification de la projection exige l’autorité correspondante et conserve la traçabilité de la version remplacée. Une page locale, une CI verte ou une PR ouverte ne constitue pas une publication officielle. Intégration Git, exécution produit, appels candidats et budget, provisionnement et publication gardent des autorités distinctes.

## 11. KISS et évolution

**Règle KISS.** Une complexité entre seulement lorsqu'une itération antérieure démontre le besoin qu'elle résout.

**Résultat suffisant.** Livrer les capacités nécessaires au catalogue et aux campagnes décidés. Une démonstration du moteur ne remplace pas les résultats réels attendus.

**Pas d'anticipation.** Réutiliser les primitives retenues dans l'ARD. Aucun microservice, Kubernetes, bus de messages, système de plugins, moteur multicritère ou abstraction spéculative n'est ajouté sans besoin démontré. Les contributions publiques et leur gestion de comptes ne sont pas construites par anticipation.

**Évolution traçable.** Lorsqu'un besoin est observé, l'itération suivante nomme la preuve, la complexité ajoutée et la condition de retrait ou de révision.

## 12. Histoire

**Campagnes immuables.** Les campagnes, preuves et reçus historiques gardent leur identité, leur sémantique et leurs verdicts d'origine. Leur historique documentaire appartient à Git.

**Aucune requalification rétrospective.** Les campagnes et prototypes historiques conservent leurs contrats et conclusions d’origine. La spécification courante ne crée pour ces campagnes aucune qualification, baseline, mesure ou recommandation absente de leur contrat et de leurs preuves.

**Preuve technique bornée.** Un `PASS` de témoin, transport, qualification, verrou ou préparation prouve seulement son objet technique.

**Artefacts historiques non normatifs.** Les générateurs et restitutions historiques restent sous leurs contrats d'origine. Leurs anciennes références ne sont pas remappées implicitement et leur vocabulaire ne remplace pas la spécification courante.

## 13. Arrêt

À l'épuisement de l'autorité ou en présence d'une preuve bloquante, la tranche s'arrête en `HOLD` sans retry, fallback, dépense ou extension implicite.

## 14. Versionnement du produit

**Version unique.** Benchmark Lab-X adopte [Semantic Versioning 2.0.0](https://semver.org/lang/fr/) sous la forme `MAJOR.MINOR.PATCH`. Une version identifie le produit du monorepo, frontend et backend ensemble. Les versions de Pi, de Graph Engineering Tool, de l’infrastructure, des modèles, des tâches et des schémas de données restent distinctes.

**Jalon initial.** `0.1.0` désigne le périmètre approuvé dans le [PRD](PRD.md#51-périmètre-010), avec ses critères d’acceptation. Ce numéro ne requalifie aucun prototype ni résultat historique et ne prouve aucune livraison. Aucun autre jalon chiffré n’est déduit de cette décision.

**Compatibilité publique.** Le contrat de compatibilité couvre les commandes, options et codes de sortie documentés, les interfaces publiques documentées et les formats de données exposés. Les détails internes ne constituent pas une interface publique. Une modification de schéma possède sa propre identité et explicite les lecteurs compatibles, la migration éventuelle et ses limites ; le numéro du produit ne remplace pas cette information.

**Avant 1.0.0.** La version majeure zéro indique un développement initial. Pour ce projet, un correctif compatible incrémente `PATCH` ; une fonctionnalité ou une rupture du contrat public incrémente `MINOR` et remet `PATCH` à zéro. Une rupture doit être documentée, même sous zéro. À partir de `1.0.0`, une rupture incrémente `MAJOR`, une fonctionnalité compatible `MINOR`, et un correctif compatible `PATCH`, selon SemVer. Un éventuel suffixe de préversion qualifie une version précise et exige une décision de livraison ; il ne crée pas un jalon concurrent.

**Identification d’une livraison.** Une version publiée est reliée à un commit et à des artefacts identifiés, dont le contenu ne change plus sous ce numéro. Un checkout sans version publiée s’identifie par son commit et ses modifications locales ; il ne s’annonce pas automatiquement comme la version cible. Le périmètre et les critères vivent dans le PRD, l’avancement dans GitHub, et la preuve livrée dans les artefacts et reçus. Choisir un numéro n’autorise ni tag, ni release, ni déploiement, ni publication.

**Historique et migration.** La documentation courante emploie les numéros de produit décidés et des noms techniques sans phase de livraison. Les identifiants présents dans les contrats et preuves scellés restent exacts. Leur reconnaissance explicite par un lecteur compatible n’autorise ni réécriture des preuves ni reprise d’une ancienne acquisition ; une nouvelle préparation et ses autorités restent nécessaires.
