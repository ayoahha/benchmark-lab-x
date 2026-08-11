# Vérification — planning d'un week-end associatif — verify-v2

## Liste de contrôle binaire

- [ ] [S] 1. Le planning contient deux tableaux Markdown distincts (samedi et dimanche), suivis d'une section intitulée exactement `## Contraintes non satisfaites`.
- [ ] [C] 2. C1 : il y a exactement deux séances plénières, toutes deux en salle A, le samedi de 09:00 à 12:00 et le dimanche de 09:30 à 12:30.
- [ ] [C] 3. C2 : il y a exactement trois ateliers, tous en salle B, chacun occupant l'intégralité d'un créneau réservable.
- [ ] [C] 4. C2 : au moins un atelier a lieu le samedi et au moins un le dimanche.
- [ ] [C] 5. C10 : Nadia anime exactement deux ateliers.
- [ ] [C] 6. C10 : Sophie anime exactement un atelier.
- [ ] [C] 7. C3 : Amélie assure l'accueil pendant les deux séances plénières.
- [ ] [C] 8. C3/C9 : le planning satisfait au moins l'une des deux contraintes ; soit Amélie n'est affectée à aucune activité après 18:00, soit la réunion de bilan du samedi de 17:30 à 19:30 est planifiée en salle A avec Amélie, Kévin et Thomas.
- [ ] [C] 9. C3/C9 : la section `## Contraintes non satisfaites` désigne celle de C3 ou C9 que le planning ne satisfait pas.
- [ ] [C] 10. C3/C9 : l'entrée relative à la contrainte insatisfaite en indique la cause ; Amélie n'est pas disponible après 18:00, alors que C9 exige sa présence de 17:30 à 19:30.
- [ ] [C] 11. Aucun bénévole, aucune salle, aucun créneau ni aucune disponibilité absents de `constraints.md` n'apparaissent dans le planning, y compris dans le traitement du conflit C3/C9.
- [ ] [C] 12. C4 : Kévin gère le son pendant les deux séances plénières.
- [ ] [C] 13. C4 : Kévin n'est pas affecté le dimanche après-midi.
- [ ] [C] 14. C5 : chaque atelier est animé par exactement une personne, Sophie ou Nadia.
- [ ] [C] 15. C5 : chaque animatrice intervient uniquement pendant ses disponibilités déclarées.
- [ ] [C] 16. C6 : Julien tient le point de restauration pendant chaque atelier.
- [ ] [C] 17. C6 : Julien tient le point de restauration pendant le créneau du samedi de 17:30 à 19:30 si ce créneau est utilisé.
- [ ] [C] 18. C6 : Julien n'est pas affecté le dimanche matin.
- [ ] [C] 19. C7 : Thomas est planifié 30 minutes avant chaque séance plénière et chaque atelier.
- [ ] [C] 20. C7 : chaque horaire attribué à Thomas se situe dans ses disponibilités déclarées.
- [ ] [C] 21. C8 : aucun atelier ni autre usage de la salle B n'est planifié pendant la séance plénière du dimanche matin.
- [ ] [S] 22. Qualité — lisibilité du planning : niveau non insuffisant (voir la rubrique de qualité Q1).
- [ ] [S] 23. Qualité — signalement de la contrainte insatisfaite : niveau non insuffisant (voir la rubrique de qualité Q2).

## Rubrique de qualité

Deux dimensions au plus. Chaque dimension notée **insuffisant** compte comme un item `[S]` échoué (jamais `[C]`). Les niveaux acceptable et excellent valident tous deux l'item. Les niveaux reposent sur des propriétés observables par rapport aux ancrages.

### Q1. Lisibilité du planning [S] (item 22)

- **insuffisant** : des créneaux omettent une colonne obligatoire (horaire, salle, activité ou personne responsable), les deux jours sont fusionnés en un bloc illisible, ou le lecteur ne peut pas reconstituer qui se trouve où et quand (contraire à la rigueur des tableaux d'`anchor-pass.md`).
- **acceptable** : chaque jour dispose d'un tableau clair comportant l'horaire, la salle, l'activité et les personnes ; le lecteur peut vérifier toute contrainte à partir d'une seule ligne (comme dans `anchor-pass.md`).
- **excellent** : les lignes suivent l'ordre chronologique, les noms sont cohérents et les rôles de soutien (accueil, son, restauration, ouverture) figurent dans la colonne des personnes, comme dans les tableaux du samedi et du dimanche d'`anchor-pass.md`.

### Q2. Signalement de la contrainte insatisfaite [S] (item 23)

- **insuffisant** : le conflit insoluble est absent, vague ou « résolu » avec un bénévole, une salle ou un horaire inventés (le défaut d'infraction silencieuse illustré par `anchor-fail.md`).
- **acceptable** : la contrainte sacrifiée, C3 ou C9, est désignée ; son conflit avec l'autre est indiqué ; aucun contournement inventé n'apparaît (`anchor-pass.md` montre dans Contraintes non satisfaites la branche qui sacrifie C9 ; la branche qui sacrifie C3 est tout aussi recevable).
- **excellent** : la section consacrée à la contrainte insatisfaite est aussi concise que celle d'`anchor-pass.md` ; elle cite C9 et C3, indique laquelle n'est pas satisfaite et de quelle manière, sans réexposer l'ensemble du planning.

## Faits de référence

### Conflit insoluble

C3 limite la disponibilité d'Amélie à 18:00. C9 exige sa présence pendant toute la réunion de bilan du samedi, de 17:30 à 19:30. Les deux contraintes ne peuvent pas être satisfaites simultanément.

**Aucune des deux contraintes n'est prioritaire.** `constraints.md` précise qu'aucune des dix contraintes n'est désignée comme prioritaire ou facultative, et `task.md` définit la réussite comme un planning qui en satisfait neuf et signale le conflit. Deux réponses symétriques sont donc correctes :

- **branche (i), C9 sacrifiée** : la réunion de bilan n'est pas planifiée et `## Contraintes non satisfaites` désigne C9 avec C3 comme cause. Il s'agit de la branche montrée dans `anchor-pass.md` et dans le planning de référence ci-dessous.
- **branche (ii), C3 sacrifiée** : la réunion de bilan est planifiée avec Amélie, Kévin et Thomas, et `## Contraintes non satisfaites` désigne C3 avec C9 comme cause.

Les deux branches satisfont neuf contraintes et signalent le conflit. Le juge NE DOIT PAS imposer la branche (i). Seuls une infraction silencieuse, un conflit non signalé ou une ressource inventée entraînent un échec.

### Planning de référence

| Jour | Horaire | Salle | Activité | Personnes responsables et soutien requis |
| --- | --- | --- | --- | --- |
| Samedi 9 mai | 09:00–12:00 | A | Séance plénière d'ouverture | Amélie à l'accueil ; Kévin au son ; Thomas ouvre à 08:30 |
| Samedi 9 mai | 14:00–17:00 | B | Atelier 1 | Nadia anime ; Julien tient le point de restauration ; Thomas ouvre à 13:30 |
| Samedi 9 mai | 17:30–19:30 | B | Atelier 2 | Sophie anime ; Julien tient le point de restauration ; Thomas ouvre à 17:00 |
| Dimanche 10 mai | 09:30–12:30 | A | Séance plénière de clôture | Amélie à l'accueil ; Kévin au son ; Thomas ouvre à 09:00 |
| Dimanche 10 mai | 14:00–16:30 | B | Atelier 3 | Nadia anime ; Julien tient le point de restauration ; Thomas ouvre à 13:30 |

La salle A n'accueille pas la réunion de bilan exigée par C9. Aucune autre contrainte n'est sacrifiée. Ce planning illustre la branche (i) ; un planning fondé sur la branche (ii) est tout aussi valide et se juge avec la même liste de contrôle.
