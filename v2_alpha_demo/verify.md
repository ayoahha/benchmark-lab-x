---
style_gate: pass
---

# Vérification locale

Commande contractuelle, hors ligne :

```bash
python3 -B -m unittest v2_alpha_demo.test_demo -v
```

Les tests créent un dépôt et des runs temporaires, utilisent un faux exécutable Pi local, traversent les quatre interfaces publiques et suppriment leurs artefacts à la fin. Ils ne construisent aucun reçu ni aucune collection à la place de `collect`.

Un résultat vert prouve le bundle local et ses protections testées. Il ne prouve aucun appel candidat, résultat réel, jugement réel, publication ou déploiement.
