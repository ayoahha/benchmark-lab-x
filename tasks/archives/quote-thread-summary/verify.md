# Vérification — synthèse d'un fil de courriels — verify-v2

## Liste de contrôle binaire

- [ ] [S] 1. La sortie contient exactement les quatre sections `## Décisions`, `## Montant`, `## Échéances` et `## Points ouverts`.
- [ ] [C] 2. Les décisions confirmées sont attribuées à la bonne date et distinguées des demandes ou annonces non confirmées.
- [ ] [C] 3. L'acceptation par la cliente des pages « Réalisations » et « Matériaux » le 9 février 2026 est rapportée comme une décision confirmée.
- [ ] [C] 4. Le montant définitif est de 4 850 € HT.
- [ ] [C] 5. Le montant initial de 4 200 € HT est qualifié d'obsolète dans le cadre d'une révision résolue, et non de contradiction encore ouverte.
- [ ] [C] 6. La révision du montant est expliquée : l'ancien montant réapparaît dans le bon de commande interne avant d'être rejeté par la confirmation finale.
- [ ] [C] 7. La livraison définitive des maquettes est fixée au 20 mars 2026.
- [ ] [C] 8. Le 13 mars 2026 est présenté comme la date initiale remplacée.
- [ ] [C] 9. Le changement de date des maquettes est présenté comme une révision résolue, et non comme une contradiction encore ouverte.
- [ ] [S] 10. Les autres échéances valides sont rapportées, notamment l'envoi du devis à la comptable avant le 21 février 2026.
- [ ] [S] 11. Aucune date cible ou de validité n'est présentée comme un événement accompli.
- [ ] [S] 12. Le virement de l'acompte annoncé pour le 21 février 2026 n'est pas présenté comme effectué.
- [ ] [C] 13. L'absence d'information sur l'hébergement de la première année et le nom de domaine est signalée comme un point ouvert.
- [ ] [C] 14. Aucun fait, accord, montant, délai ou réponse absent du fil n'est inventé.
- [ ] [S] 15. Qualité — clarté des décisions et des statuts : niveau non insuffisant (voir la rubrique de qualité Q1).
- [ ] [S] 16. Qualité — rigueur sur les montants et les échéances : niveau non insuffisant (voir la rubrique de qualité Q2).

## Rubrique de qualité

Deux dimensions au plus. Chaque dimension notée **insuffisant** compte comme un item `[S]` échoué (jamais `[C]`). Les niveaux acceptable et excellent valident tous deux l'item. Les niveaux reposent sur des propriétés observables par rapport aux ancrages.

### Q1. Clarté des décisions et des statuts [S] (item 15)

- **insuffisant** : les décisions confirmées, les demandes et les annonces sont mélangées sans date ni statut, si bien que le lecteur ne peut pas déterminer ce qui a été convenu (contraire à la rigueur de la section Décisions d'`anchor-pass.md` ; voir aussi `anchor-fail.md`).
- **acceptable** : chaque décision listée comporte une date et un statut confirmé ; les demandes et annonces non confirmées ne sont pas présentées comme des accords (comme dans `anchor-pass.md`).
- **excellent** : la liste des décisions est aussi facile à parcourir que celle d'`anchor-pass.md` ; chaque entrée est datée, les révisions sont signalées au bon endroit, par exemple le déplacement des maquettes les 13 et 14 février, sans masquer l'état définitif convenu.

### Q2. Rigueur sur les montants et les échéances [S] (item 16)

- **insuffisant** : des montants obsolètes ou des dates remplacées sont présentés comme actuels sans mention de la révision, ou des objectifs ouverts sont décrits comme des événements accomplis (défauts illustrés dans les sections Montant et Échéances d'`anchor-fail.md`).
- **acceptable** : le montant définitif et la date définitive des maquettes sont explicites ; les valeurs obsolètes n'apparaissent qu'en tant qu'historique ; les objectifs et virements annoncés ne sont pas marqués comme réalisés (comme dans `anchor-pass.md`).
- **excellent** : chaque ligne comportant une somme ou une date indique son statut en une proposition courte, comme dans `anchor-pass.md` (définitif, obsolète, annoncé ou visé), sans ambiguïté résiduelle.

## Faits de référence

### Ordre chronologique

B → E → H → D → F → A → G → L → C → I → J → K.

### Décisions confirmées

| Date | Décision ou statut fiable |
| --- | --- |
| 9 février 2026 | La cliente a accepté l'ajout des pages « Réalisations » et « Matériaux » ; la fourniture des textes avant le 27 février a été annoncée |
| 11 février 2026 | Devis V2 formalisé pour sept pages avec un montant révisé |
| 12 février 2026 | La cliente a approuvé le montant de la V2 et un démarrage pendant la semaine du 2 mars |
| 13 février 2026 | Livraison des maquettes déplacée du 13 au 20 mars |
| 14 février 2026 | La cliente a accepté la nouvelle date du 20 mars |
| 19 février 2026 | PDF de la V2 à signer envoyé avec le montant et les dates arrêtés |
| 20 février 2026 | Devis signé ; virement de l'acompte annoncé pour le 21 février |
| 20 février 2026 | Confirmation définitive que le montant de la V2 s'applique et que le montant initial est obsolète |

### Montants et échéances

| Élément | Valeur fiable |
| --- | --- |
| Montant initial | 4 200 € HT, obsolète |
| Montant définitif | 4 850 € HT |
| Acompte | 40 %, annoncé mais paiement non confirmé |
| Validité du devis | 28 février 2026 |
| Démarrage | Semaine du 2 mars 2026 |
| Livraison des maquettes | 20 mars 2026 |
| Mise en ligne visée | 3 avril 2026 |
| Textes de la cliente | Avant le 27 février 2026 |
| Virement annoncé | 21 février 2026 |
| Transmission interne à la comptable | Avant le 21 février 2026 |

### Révisions résolues et point ouvert

- La révision du montant, de 4 200 € HT à 4 850 € HT, est résolue par la confirmation finale malgré la réapparition de l'ancien montant dans le bon de commande interne.
- La révision de la date des maquettes, du 13 au 20 mars 2026, a été acceptée le 14 février.
- Les deux révisions doivent être rapportées avec leur valeur définitive et leur historique, et non classées comme des contradictions encore ouvertes.
- Le seul manque volontaire concerne l'inclusion de l'hébergement de la première année et du nom de domaine, ou leur facturation séparée.
