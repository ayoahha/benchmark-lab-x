# benchmark-lab-x — amener la V0 à un classement défendable

## Ce qu'est le projet

Un banc d'essai privé qui classe des LLM **par le code seul** : aucun juge humain et aucun juge LLM au moment de la notation. Un modèle reçoit une carte, rend une réponse, un vérificateur déterministe la note sur une échelle de paliers ordonnés.

Dépôt : `/Users/ayo/Projects/benchmark-lab-x`, branche `docs/relecture-v0`, dernier commit `d1a9744`.

## Objectif

Le premier classement complet existe : 19 candidats, 76 runs, 19,40 $, dans `runs/2026-08-06-reference-v2/`. **Il n'est pas publiable en l'état.** Trois modèles externes interrogés séparément — Kimi K3, Grok 4.5, DeepSeek V4 Flash — convergent : les extrêmes portent un signal réel, les places 3 à 19 sont du bruit et des artefacts de mesure. Leurs avis complets sont dans `runs/2026-08-06-reference-v2/consolidation-avis-*.md`.

Ta mission est de rendre ce classement défendable en améliorant l'outil. **Terminé quand** : une campagne produit un classement dont chaque position s'explique par une propriété du modèle et non par un artefact de l'instrument, et dont les limites sont écrites sur la page.

## Lis d'abord, dans cet ordre

1. `docs/RULES.md` — 33 règles, le contrat opposable. **Son §5 est une matrice de conformité** qui dit pour chaque règle à quelle version son automatisation est due. Une règle due en V1 ou V4 et non implémentée est un jalon, pas un défaut. N'annonce jamais un écart sans sa version cible.
2. `runs/2026-08-06-reference-v2/consolidation-avis-*.md` — les trois critiques externes.
3. `~/.claude/projects/-Users-ayo-Projects-benchmark-lab-x/memory/` — 12 mémoires, dont `harnais-avant-modele` qui recense seize artefacts de mesure trouvés en trois jours.
4. `docs/ARD.md` §2.2 pour les manifestes et empreintes, `docs/PRD.md` pour les jalons.

## Les quatre défauts établis, avec leur preuve, mais qui sont tout de même à vérifier

**Huit paliers sur 51 sont morts.** Cinq runs de trois candidats différents rendent exactement `5.1178986216292804e-17` d'écart à l'oracle : c'est le plancher du `float64`, pas une prouesse. Le palier 44 exige `3e-17`. Comme le niveau est le plus grand préfixe passant et que les six paliers d'horizon long sont placés **après** les crans de précision dans `tools/verifier_pentagone.py:237-242`, ils ne sont jamais évalués. La tenue à 35, 55 et 75 secondes était la raison d'être déclarée de `verify-v3`.

**Un critère éliminatoire n'est pas dans les consignes.** La vérification est bornée à 180 s de temps mural, écrit ligne 101 de `tasks/dev/pentagone-rotatif/task.md`, côté juge. Les consignes visibles ne mentionnent aucun budget. Un intégrateur à pas fixe recalculant depuis zéro — lecture honnête de la consigne — est éliminé. C'est ce qui met DeepSeek V4 Flash dernier alors que son meilleur run vaut la sixième place. R-018 exige pourtant que les erreurs éliminatoires soient annoncées dans la tâche.

**Le dépassement est consigné sous une cause fausse.** Il apparaît avec la frontière `A1_api_totale`, « l'interface n'a pas répondu ». Trois causes distinctes finissent au même niveau 0 sans se distinguer : temps dépassé, aucune page produite (`A0_page`, cas de MiniMax M3), et bug de dépendance à l'ordre des appels.

**Le scalaire publié est indéfendable.** Le troisième meilleur de quatre est une règle de sélection correcte mais un estimateur à variance énorme avec n=4. GPT 5.6-sol seul, selon son bouton d'effort, ressort à 43, 20 ou 12. L'ordre des places 3 à 19 change si un seul run change.

## Ce qui n'est pas un défaut

Opus 5 devant Fable 5 est le signal le plus solide du tableau : inspection du code rendu, Fable emploie un pas fixe avec décalage `epsilon` de `1e-9`, Opus une détection d'événement dans deux runs sur quatre. Ne le « corrige » pas forcément, s'il s'agit du fonctionnement intrinsèque du modèle ; et dans ce cas, il faudra le justifier en dessous du classement.

Mistral Medium 3.5 à 3 paliers, stable sur quatre runs, sans jeton de raisonnement, est un vrai bas de tableau.

## Contraintes que le code ne révèle pas

- **Commit et push exigent le GO explicite d'Ayo, dans son message.** Jamais de ta propre initiative, jamais pour « sauvegarder » ton travail. Une autorisation ne vaut que pour l'action nommée, cette fois-là. Quinze fichiers attendent actuellement un GO.
- **Une seconde session travaille en parallèle** sur `README.md`, `docs/PRD.md`, `docs/ARD.md` et la structure du dépôt. Ne touche pas à ses fichiers. `docs/RULES.md` t'est ouvert en partie si besoin.
- **La clé API vit dans `.env`, ignoré par git.** Jamais en argv, jamais dans un message, jamais commitée.
- **Les reçus `FAILED` sont des preuves.** On ne les supprime pas. Suppressions par `trash`, jamais `rm -rf`.
- **Tout est en français**, y compris les commentaires de code, les chaînes de caractères et les messages de commit, avec les accents corrects. Les identifiants, clés machine et motifs de recherche gardent leur forme fonctionnelle. Les commentaires de code ne se terminent jamais par un point et rien ne doit utiliser les tirets cadratins.
- **Gemini est banni comme fournisseur et peut être remplacé par Antigravuty (agy)**, quel que soit le contexte.
- Un délai sur un sous-processus ne tue pas sa descendance. Voir `~/.claude/rules/subprocess-timeouts.md` : un oubli a laissé 48 Chromium orphelins à 100 % de CPU pendant des jours.

## Discipline de mesure, non négociable

**Avant d'imputer un mauvais résultat à un modèle, ouvre son `meta.json`** et lis `finish_reason`, la répartition des jetons, les paramètres envoyés et la frontière atteinte. Seize artefacts de harnais ont produit seize faux résultats en trois jours. Le classement ne montre aucun d'eux ; les reçus les montrent tous.

**Ne fabrique aucun chiffre.** Un intervalle attendu inventé après coup, une valeur posée en constante plutôt que lue, une politique de fournisseur supposée : chacun de ces trois cas s'est déjà produit ici et a coûté une correction publique.

## Le travail, par ordre d'impact

1. **Rendre l'échelle jouable de bout en bout.** Décide si les horizons longs passent devant les crans de précision extrêmes, si l'échelle se tronque au dernier palier atteignable, ou si le vérificateur doit sortir du `float64`. Écris la décision dans la carte et incrémente `verify-vM`.
2. **Déclarer le budget de temps dans les consignes visibles**, ou le retirer comme critère éliminatoire. Puis donner au dépassement son propre état terminal, distinct de `A0_page` et de `A1_api_totale`.
3. **Séparer les axes.** La carte mesure aujourd'hui format, physique qualitative, méthode numérique et efficacité algorithmique dans une échelle conjonctive où le maillon faible décide. Décide lesquels se publient séparément.
4. **Remplacer le scalaire de titre** par ce qui est défendable à n=4, ou monter n. La page publie déjà la distribution ; c'est le titre qui ment.
5. **Recollecter** sous l'instrument corrigé, puis régénérer `runs/<campagne>/results-data.json` et `docs/index.html`.
6. **R-016, témoins indépendants.** `tools/qualifier_temoins.py` montre que même produits en aveugle, les sept témoins actuels laisseraient 31 paliers sans témoin positif. C'est un acte humain, pas du code : dis à Ayo ce qu'il doit produire.
7. Toute autre travail que tu jugeras nécessaire pour faire grimper la robustesse de cette VO à un haut niveau, et le classement modèle plus intéressant et représentatif.

## Outillage existant, à réutiliser plutôt qu'à réécrire

`tools/collect.py` collecte un appel et pose son reçu. `tools/lancer_campagne.py` orchestre, reprend, borne les tentatives, respecte les délais des fournisseurs. `tools/rapport_campagne.py` note en aveugle et agrège avec les états terminaux. `tools/choisir_provider.py` choisit la route sur critère versionné. `tools/page_resultats.py` écrit la page. `tools/qualifier_temoins.py` et `tools/audit_instrument.py` couvrent R-016 et R-026. `tools/moteur_rendu.py` épingle le Chromium. `tools/empreintes.py` est la source unique des empreintes.

Chaque fichier porte en tête ce qu'il fait et **pourquoi il a été écrit ainsi**, souvent avec l'erreur qui l'a motivé. Lis ces en-têtes avant de modifier : plusieurs choix qui paraissent arbitraires sont des corrections d'artefacts documentés.

## Autonomie

Pour une question, un diagnostic ou une analyse, inspecte et rends ton constat sans modifier. Pour une correction demandée, applique le changement dans son périmètre et lance les vérifications non destructives sans demander. Demande confirmation pour un appel API payant au-delà de quelques dollars, un changement de périmètre, ou toute action irréversible.

Ayo attend d'être contredit quand il a tort, et préfère un désaccord argumenté à un accord poli. Il travaille en POC : une règle non implémentée n'est pas un blocage, mais un chiffre faux publié en est un.

## Ce qu'Ayo refuse sur la page de résultats

Pas de colonne supplémentaire, pas de paragraphe explicatif sous le tableau, pas de bandes de couleur. Six propositions ont été refusées avant d'arriver là ; la lisibilité gagne systématiquement contre la rigueur d'affichage.
