---
style_gate: pass
---

# Micro-pilote Graph Engineering V2.2

## Tâche

Remplace l’unique ligne `PENDING` de `target.txt` par `READY`.

## Périmètre

Lis et écris uniquement `target.txt`. Laisse l’index, `HEAD` et tous les autres fichiers inchangés.

## Preuve d’arrêt

Exécute :

```text
python3 -c "from pathlib import Path; assert Path('target.txt').read_bytes() == b'READY\\n'"
```

La tâche est terminée lorsque cette commande sort avec le code 0. Arrête-toi alors.
