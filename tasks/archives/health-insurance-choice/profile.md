# Profil du foyer — exercice de comparaison de complémentaires santé

**Document synthétique — ne décrit aucune personne réelle.**

---

## Membres du foyer

| Membre | Lien | Âge | Statut |
| --- | --- | --- | --- |
| Emma Meunier | Adulte 1 (titulaire du contrat) | 41 | Salariée du secteur privé, régime général de l'assurance maladie obligatoire |
| Daniel Meunier | Adulte 2 (conjoint) | 44 | Salarié du secteur privé, régime général de l'assurance maladie obligatoire |
| Sophie Meunier | Enfant | 12 | Élève |
| Léo Meunier | Enfant | 8 | Élève |

Adresse synthétique : 17 allée des Peupliers, 44100 Nantes.
Date de prise d'effet souhaitée : **1er juin 2026**.

---

## Antécédents et besoins déclarés

1. **Optique** — Emma porte des verres progressifs et prévoit de les remplacer fin 2026 (devis estimatif de l'opticien : 180 € pour la monture + 420 € pour les verres progressifs, soit **600 €** pour un équipement complet). Daniel porte des lentilles mensuelles (**environ 25 €/mois**, soit 300 €/an). Les deux enfants ont un examen ophtalmologique annuel et n'ont actuellement besoin d'aucune correction.
2. **Hospitalisation** — Daniel a subi une arthroscopie du genou en 2024. Le couple souhaite une chambre particulière lors de toute hospitalisation et une forte couverture des dépassements d'honoraires dans une clinique privée (secteur 2).
3. **Budget** — Cotisation maximale acceptable pour l'ensemble du foyer : **280 €/mois**. Toute offre dépassant ce montant est rejetée, même si ses garanties sont meilleures.
4. **Délais de carence** — Le foyer rejette toute offre dont le délai de carence en **hospitalisation** dépasse **3 mois**. Des délais de carence allant jusqu'à 6 mois en optique et en dentaire sont acceptables.

---

## Critères de sélection pondérés

Le foyer a défini la grille de notation suivante pour les offres **éligibles** après application des filtres de budget et de délai de carence en hospitalisation :

| Code | Critère | Poids | Règle de notation |
| --- | --- | --- | --- |
| K1 | Reste à charge du foyer en optique (année du remplacement des lunettes d'Emma et des lentilles de Daniel) | **35 %** | Un reste à charge annuel estimé plus faible est préférable. Score 100 si le reste à charge = 0 € ; score 0 si le reste à charge ≥ 800 € ; interpolation linéaire entre les deux. |
| K2 | Niveau d'hospitalisation (chambre particulière + dépassements d'honoraires) | **30 %** | Score 100 si la chambre particulière ≥ 80 €/nuit **et** les honoraires ≥ 200 % BR ; score 50 si une seule condition est remplie ; score 0 si aucune ne l'est. |
| K3 | Respect du budget (cotisation mensuelle du foyer) | **20 %** | Score 100 si la cotisation ≤ 220 €/mois ; score 0 si la cotisation = 280 €/mois ; interpolation linéaire entre 220 € et 280 €. Une offre > 280 € est **inéligible** et exclue de la comparaison. |
| K4 | Délai de carence en hospitalisation | **15 %** | Score 100 si le délai = 0 mois ; score 60 s'il est de 1 à 2 mois ; score 20 s'il est de 3 mois ; offre **inéligible** au-delà de 3 mois. |

Score global = 0,35×K1 + 0,30×K2 + 0,20×K3 + 0,15×K4.

Si les scores sont à égalité à une décimale près, retenir l'offre dont la cotisation mensuelle est la plus faible.

---

## Hypothèses de calcul imposées

- Pour les prestations d'hospitalisation de référence de cet exercice, **ne pas recalculer** la base de remboursement (BR) de l'assurance maladie obligatoire ; utiliser uniquement les pourcentages et forfaits indiqués dans chaque offre.
- Pour Emma : une paire complète de lunettes à verres progressifs pendant l'année, d'un coût de **600 €** (180 € + 420 €).
- Pour Daniel : **300 €/an** de lentilles de contact.
- Les garanties destinées aux enfants qui ne diffèrent pas explicitement des garanties pour adultes s'appliquent à Sophie et Léo au même niveau que pour les adultes, sauf indication contraire d'une offre.
- Comparer une **année complète** de cotisations et les exemples de prestations ci-dessus.
