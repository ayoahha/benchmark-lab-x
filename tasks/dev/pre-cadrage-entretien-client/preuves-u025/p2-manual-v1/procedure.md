---
style_gate: pass
---

# Procédure P2 manuelle contrôlée U-025

## Identité

- preuve : `U025-P2-MANUAL-V1`
- niveau : `P2`
- voie : méthode manuelle contrôlée
- paquet : `PRECADRAGE-ENTRETIEN-CLIENT-V0`
- politique : `HYBRID_PROOFS`
- relecteur humain : Ayo
- responsable de méthode : Ayo

Cette procédure traverse les 16 fixtures exactes de P1 v2. Elle ne produit aucune sortie candidate, n'appelle aucun modèle ou fournisseur et ne constitue ni une campagne ni une preuve V0 exécutée.

## Préflight et lock

L'opérateur vérifie la base Git, les cinq empreintes du paquet, D1, M2.1, les autorités GitHub, la racine et les artefacts P1 v2, la procédure, l'instrument, le runtime, les rôles, l'ordre, le périmètre d'écriture et les interdictions. Le lock doit porter `manual_reviewer = AYO` et `manual_method_owner = AYO`.

Aucun cas ne commence avant l'écriture puis la validation complète du lock. Toute absence ou divergence produit `HOLD_MANUAL_P2_EXECUTION`.

## Ordre des cas

1. `WT-ACCEPTABLE`
2. `WT-SCHEMA`
3. `WT-ANCRE`
4. `WT-VOCABULAIRE`
5. `WT-HARNESS`
6. `WT-FAIT-INVENTE`
7. `WT-CONTRAINTE-OMISE`
8. `WT-INCONNUE-RESOLUE`
9. `WT-HYPOTHESE-INTERDITE`
10. `WT-CONTRADICTION-MANQUEE`
11. `WT-RISQUE-INADEQUAT`
12. `WT-QUESTION-INADEQUATE`
13. `WT-ACTION-INADEQUATE`
14. `WT-CONFORMITE-AFFIRMEE`
15. `WT-RECONSTRUCTION`
16. `WT-HUMAIN-INDISPONIBLE`

## Contrôles automatiques

Pour chaque cas, l'opérateur ouvre un reçu, vérifie la spécification et la fixture P1 v2, puis déclenche l'instrument local. L'instrument exécute `G-005`, puis `G-001`, `G-002`, `G-003` et `G-004` dans cet ordre tant que le contrôle précédent permet la suite. Les seuls états automatiques sont `PASS`, `FAIL` et `HARNESS_ERROR`.

L'attendu et l'observé restent séparés. Un `FAIL` attendu est une observation conforme. Toute divergence entre attendu et observé arrête la preuve.

## Contrôle réseau

Le runtime Python exact installe un hook d'audit avant la fenêtre des cas. Il bloque et consigne la création ou l'usage d'une socket, la résolution réseau et tout lancement de sous-processus. Un auto-test bloqué est enregistré avant le premier cas. L'instrument source est lié au lock et son import de modules natifs de contournement est refusé.

## Revue humaine aveugle

`WT-SCHEMA`, `WT-ANCRE`, `WT-VOCABULAIRE` et `WT-HARNESS` ne passent pas en revue humaine. Les douze autres cas produisent un objet de dossier aveugle. Onze objets sont présentés sous alias neutres. L'objet d'indisponibilité n'est pas consultable.

Chaque dossier présent contient uniquement le stimulus, la sortie sous l'alias `SORTIE-A` et la rubrique `HR-001`. La présentation exclut le case ID, la correspondance interne, l'identité de voie, le coût, l'oracle, le verdict attendu et le rapprochement avec P1.

Ayo rend pour chaque dossier `ACCEPTABLE`, `NOT_ACCEPTABLE` ou `UNABLE_TO_JUDGE`, avec une justification publique bornée à `HR-001`. Les onze verdicts et le constat d'indisponibilité sont gelés avant toute révélation de correspondance ou d'oracle.

## Combinaison mécanique

- `PASS + ACCEPTABLE` donne `OFFICIALLY_ACCEPTABLE`
- `FAIL` donne `CANDIDATE_NOT_ACCEPTABLE`
- `PASS + NOT_ACCEPTABLE` donne `CANDIDATE_NOT_ACCEPTABLE`
- `HARNESS_ERROR` donne `HARNESS_ERROR`
- `PASS + UNABLE_TO_JUDGE` donne `UNABLE_TO_JUDGE`

Aucun score global ni pouvoir discrétionnaire n'entre dans cette combinaison. Toute divergence humaine avec l'oracle reste enregistrée telle quelle et produit `HOLD_MANUAL_P2_EXECUTION`.

## Reçus, effort et fermeture

Les reçus sont append-only et chaînés. Une correction produit un nouvel objet lié au précédent. Le rapport est recalculé depuis les reçus finaux. Le registre d'effort contient les sept composantes, chacune en phase `initial` et `recurrent`, sans durée, cadence, estimation, note, pondération ni conversion monétaire.

La fermeture locale est recevable seulement avec 16 résultats conformes, 12 reçus humains, 14 faits d'effort, une chaîne et un tail valides, zéro appel candidat, zéro tentative fournisseur, une dépense nulle et un scan de secrets vide. La conclusion P2 reste `INCONNU`.

## Reprise et arrêt

Une reprise vérifie le lock, la racine de préparation et le tail avant d'ajouter un objet. Aucun reçu fermé n'est rejoué ou réécrit. Une divergence conserve les objets existants, arrête les cas restants et laisse `main` inchangée. Le rollback est l'absence de merge.

STOP avant M3.12.
