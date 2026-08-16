---
style_gate: pass
---

# Correction P1 U-025

Verdict : `PASS`

- Historique : v1 conservée sans réécriture, supersédée par cette v2 liée au commit `6eaf1ea23d1bbcbc23d9a3b3da5354d8910f9bf1` et à sa racine d'arbre
- Paquet : cinq empreintes conformes à D1 et M2.1
- Cas : 16 témoins indexés avec contenu et SHA-256, dont dix rejets humains négatifs
- Voies : trois adaptateurs locaux distincts et 48 traces d'exécution propres
- Oracle : table attendue indépendante, liée aux témoins et au registre de vérité
- Reçus : 48 reçus complets, reproductibles et chaînés
- Graphe : registre, tail, manifeste et racine liés aux reçus, faits d'effort et rapports
- Effort : 42 faits ; `OBSERVE` seulement avec preuve distincte, sinon `INCONNU`
- Rapports : tous les champs recalculés depuis les reçus et fixtures
- Appels candidats : 0
- Dépense fournisseur : 0
- Portée : P1 local déterministe seulement ; aucune exécution réelle Promptfoo ou Ori, aucun appel modèle ou fournisseur

Reproduction :

```text
python3 tools/preuve_u025_p1_v2.py verify
python3 -m unittest tests.test_preuve_u025_p1_v2 tests.test_preuve_u025_p1 tests.test_validateur_pre_cadrage_v0
```
