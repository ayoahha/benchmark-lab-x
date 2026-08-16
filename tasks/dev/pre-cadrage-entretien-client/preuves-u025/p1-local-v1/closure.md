---
style_gate: pass
---

# Fermeture P1 U-025

Verdict : `PASS`

- Paquet : cinq empreintes conformes à D1 et M2.1
- Cas : 16 témoins exacts, contenus et SHA-256 dans `case-index.json`
- Voies : 3 rejeux locaux déterministes
- Reçus : 48 reçus complets, reproductibles et chaînés
- Registre : 93 entrées append-only chaînées
- Effort : 42 faits, sept composantes, trois voies, initial et récurrent
- Appels candidats : 0
- Dépense fournisseur : 0
- Rapport : trois rapports P1 avec coût, latence, couverture, provenance, inconnues et abstention
- Portée : mécanismes P1 seulement ; aucune intégration réelle Promptfoo ou Ori, aucun comportement fournisseur et aucune preuve V0 exécutée

Reproduction :

```text
python3 tools/preuve_u025_p1.py verify
python3 -m unittest tests.test_preuve_u025_p1 tests.test_validateur_pre_cadrage_v0
```
