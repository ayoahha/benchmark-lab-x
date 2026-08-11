# Vérification — choix d'une complémentaire santé — verify-v2

## Liste de contrôle binaire

Chaque item reçoit `PASS`, `FAIL` ou `N/A (justifié)`. `UNKNOWN` est réservé à une cause externe conformément à la règle R-013. Un item `[C]` en `FAIL` entraîne un verdict global `FAIL` ; sans `[C]` en `FAIL`, tout `[S]` en `FAIL` entraîne `PARTIAL` ; si tous les items sont en `PASS` ou en `N/A (justifié)`, le verdict global est `PASS`.

- [ ] [S] 1. La sortie contient exactement les sections `## Recommandation`, `## Points de vigilance` et `## Informations inconnues`.
- [ ] [C] 2. Soit l'offre B est recommandée sous l'hypothèse de calcul explicite « part de l'assurance maladie obligatoire pour l'optique = 0 € », soit le classement est déclaré indéterminé parce que cette part n'est pas chiffrée. Recommander l'offre A ou C sans énoncer l'hypothèse numérique qui le justifie fait échouer cet item.
- [ ] [C] 3. Si un score est calculé sous l'hypothèse de référence « part de l'assurance maladie obligatoire pour l'optique = 0 € », le score global de l'offre B est de 83,27 points ; l'absence de score exact est acceptable lorsque la composante manquante est signalée comme inconnue.
- [ ] [C] 4. La sortie donne trois raisons comparatives fondées sur le profil.
- [ ] [C] 5. Chaque raison comparative comporte une citation qui figure mot pour mot dans le document cité.
- [ ] [C] 6. Chaque citation étaye l'affirmation à laquelle elle est rattachée.
- [ ] [C] 7. L'exclusion défavorable de l'offre C est repérée : aucun remboursement des lentilles pendant les onze premiers mois malgré le forfait affiché.
- [ ] [C] 8. L'effet de l'exclusion sur la première année est appliqué ; sous l'hypothèse de référence, le reste à charge optique de l'offre C est de 350 €, et non de 100 €. Ne pas le calculer est acceptable si la composante manquante est explicitement signalée.
- [ ] [C] 9. L'absence, dans les trois offres, d'un chiffrage de la part de l'assurance maladie obligatoire pour l'optique est signalée comme une information inconnue.
- [ ] [C] 10. Le filtre budgétaire est appliqué : toute offre dépassant 280 €/mois est exclue de la comparaison.
- [ ] [C] 11. Le filtre relatif au délai de carence en hospitalisation est appliqué : toute offre dépassant trois mois est exclue de la comparaison.
- [ ] [C] 12. Les garanties et les délais de carence sont comparés sans ajout de données externes.
- [ ] [C] 13. Aucun montant, aucune garantie, aucune exclusion, aucun délai ni aucune citation absents du corpus ne sont inventés.
- [ ] [S] 14. Qualité — facilité de vérification des citations : niveau non insuffisant (voir la rubrique de qualité Q1).
- [ ] [S] 15. Qualité — transparence de la recommandation : niveau non insuffisant (voir la rubrique de qualité Q2).

## Rubrique de qualité

Deux dimensions au maximum. Chaque dimension notée **insuffisante** compte comme un item `[S]` en `FAIL` (jamais `[C]`). Les niveaux acceptable et excellent donnent tous deux un `PASS` à cet item. Les niveaux reposent sur des propriétés observables par rapport aux ancrages.

### Q1. Facilité de vérification des citations [S] (item 14)

- **insuffisant** : les affirmations comparatives n'indiquent pas le document ou le passage citable, ou les citations sont paraphrasées et ne peuvent donc pas être vérifiées dans le corpus ; ne respecte pas la discipline de citation d'`anchor-pass.md`.
- **acceptable** : chaque raison comparative cite un document et un passage que la personne chargée du jugement peut y retrouver mot pour mot ; correspond à la section Recommandation d'`anchor-pass.md`.
- **excellent** : chaque raison comparative comporte une courte citation exacte placée à côté de l'affirmation, comme dans la section Recommandation d'`anchor-pass.md` ; aucune citation décorative ou hors sujet, contrairement aux citations non probantes d'`anchor-fail.md`.

### Q2. Transparence de la recommandation [S] (item 15)

- **insuffisant** : la position adoptée sur le classement est enfouie, les points de vigilance omettent l'effet de l'exclusion prévue ou les informations inconnues sont remplacées par une hypothèse silencieuse ; correspond aux modes d'échec visés par `anchor-fail.md`.
- **acceptable** : la position est annoncée d'emblée sous l'une des deux formes admises, soit l'offre B sous une hypothèse déclarée, soit un classement déclaré indéterminé faute de connaître la part de l'assurance maladie obligatoire pour l'optique ; les Points de vigilance traitent l'effet de l'exclusion des lentilles de l'offre C ; les Informations inconnues mentionnent la part manquante ; correspond à `anchor-pass.md`.
- **excellent** : les trois sections présentent le même équilibre qu'`anchor-pass.md` : position d'abord, points de vigilance nommant le compromis lié à l'exclusion, puis informations inconnues exposant l'absence de la part obligatoire ; le lecteur perçoit ainsi les arbitrages et les lacunes sans devoir refaire le tableau des scores.

## Faits de référence

### Hypothèse simplificatrice et règle d'évaluation

Toute composante absente du corpus doit être traitée comme une information inconnue et signalée, et non être silencieusement remplacée par zéro. Les tableaux ci-dessous présentent des calculs de référence conditionnels : la part de l'assurance maladie obligatoire pour l'optique est fixée à 0 €. Les documents fournis n'établissent pas cette hypothèse comme un fait.

Une réponse ne doit pas être pénalisée si elle refuse de calculer un reste à charge complet ou un score exact en raison de cette composante manquante, à condition de la signaler sous `## Informations inconnues`. Si elle choisit d'effectuer le calcul sous l'hypothèse de référence, les valeurs ci-dessous s'appliquent.

### Éligibilité et scores sous l'hypothèse de référence

| Offre | Cotisation mensuelle | Délai de carence en hospitalisation | Éligible | Reste à charge optique conditionnel | Score global conditionnel |
| --- | ---: | ---: | --- | ---: | ---: |
| A | 220 € | 2 mois | Oui | 370 € | 77,81 |
| B | 240 € | 0 mois | Oui | 230 € | 83,27 |
| C | 260 € | 3 mois | Oui | 350 € | 59,35 |

Les trois offres obtiennent le score maximal pour le critère d'hospitalisation. **Sous l'hypothèse de 0 €, et uniquement sous cette hypothèse**, l'offre B se classe première grâce à son équilibre entre l'optique, l'absence de délai de carence en hospitalisation, un coût acceptable et les garanties d'hospitalisation.

**Le classement n'est pas établi comme un fait.** La part inconnue de l'assurance maladie obligatoire réduit d'un même montant le reste à charge optique de chaque offre. L'avance de 5,46 points de B sur A se réduit donc à mesure que cette part augmente : au-delà d'environ 355 €, l'offre A se classe première. Déclarer le classement indéterminé et désigner cette part comme l'information inconnue bloquante constitue donc une réponse entièrement correcte et ne doit pas être pénalisé. Il ne faut pas faire de « l'offre B l'emporte » l'unique réponse attendue.

### Calculs de référence conditionnels

| Critère | Offre A | Offre B | Offre C |
| --- | ---: | ---: | ---: |
| K1 — optique | 53,75 | 71,25 | 56,25 après application de l'exclusion |
| K2 — hospitalisation | 100 | 100 | 100 |
| K3 — budget | 100 | 66,67 | 33,33 |
| K4 — délai de carence en hospitalisation | 60 | 100 | 20 |

Formule : 0,35 × K1 + 0,30 × K2 + 0,20 × K3 + 0,15 × K4.

### Exclusion à repérer

Document : `offer-c.md`, dernière section. Passage de référence :

> **Clause de carence prolongée — lentilles.** Les forfaits lentilles ne deviennent accessibles qu'après **douze (12) mois** d'adhésion continue. Aucun remboursement de lentilles n'est dû pendant les onze premiers mois, y compris en cas de renouvellement d'une prescription. Cette disposition prévaut sur le délai de carence général de quatre mois en optique pour la seule garantie lentilles.

Le forfait lentilles de 250 € ne s'applique pas pendant la première année. Le reste à charge des lentilles est donc de 300 € et le reste à charge optique total de l'offre C, de 350 €.

### Information manquante

Aucune des trois brochures ne chiffre la part du régime obligatoire pour l'équipement optique et les lentilles. Le reste à charge complet, combinant assurance maladie obligatoire et complémentaire, ne peut donc pas être établi à l'euro près à partir des seules brochures. Le calcul du score ci-dessus suit uniquement l'hypothèse conditionnelle « part du régime obligatoire = 0 € » retenue dans le présent document de vérification.
