---
style_gate: pass
---

# Procédure de reprise P2 manuelle V2

## Objet

Cette preuve corrige uniquement la capacité de reprise de P2. Elle conserve byte-identiques l’instrument, les tests et le sous-arbre de preuve V1.

## Source verrouillée

V2 lie la racine, le lock, le registre, le tail, les onze dossiers aveugles rendus, leurs objets adressés par contenu et le `human-input` gelé de V1. Les verdicts humains sont réutilisés seulement si toutes ces empreintes correspondent.

La revue source a été gelée dans V1 avant la révélation des correspondances. V2 ne simule aucune nouvelle revue aveugle et attribue la décision propriétaire à Ayo.

## Reprise de prepare

`prepare` vérifie V1, le lock V2, le registre et son tail. Un préfixe valide est conservé. Les reçus fermés sont ignorés et le traitement reprend au premier cas incomplet. Une divergence arrête la preuve.

## Reprise de finalize

`finalize` vérifie le `human-input` V1 byte à byte, puis le préfixe des reçus humains et finaux. Les objets fermés ne sont ni rejoués ni réécrits. Le contrôle réseau V1 valide est lié sans second auto-test.

## Limites

La preuve reste locale et hors campagne. Elle ne prouve aucun comportement fournisseur, candidat réel, coût, latence ou avantage comparatif U-025. Sa conclusion demeure `INCONNU`.

## Arrêt

Le succès local est `PASS_PR55_V2_LOCAL_PROOF`. Toute divergence produit `HOLD_PR55_V2_CORRECTION`. Aucun merge, aucune fermeture de #53 et aucune action M3.12 ne sont autorisés.
