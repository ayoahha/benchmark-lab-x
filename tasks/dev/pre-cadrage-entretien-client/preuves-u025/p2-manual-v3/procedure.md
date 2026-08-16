---
style_gate: pass
---

# Procédure de reprise sémantique P2 manuelle V3

## Objet

V3 ferme uniquement le contrôle sémantique des reçus lors d’une reprise. V1 et V2 restent byte-identiques.

## Source verrouillée

Le lock V3 lie les empreintes complètes, les racines, les locks, les registres et les tails V1 et V2. Les résultats P2 proviennent des reçus V2 adressés par contenu.

## Préfixe recevable

Chaque reçu fermé doit correspondre exactement à la source attendue à sa position : stage, nom logique, payload, empreintes source et chaîne précédente. Une omission, duplication, divergence ou suffixe inattendu arrête la reprise avant tout ajout ou retour terminal.

## Reprise

`prepare` et `finalize` conservent les reçus valides déjà fermés et reprennent au premier reçu incomplet. Aucun reçu n’est rejoué ou réécrit.

## Contre-exemples

La preuve exécute trois altérations rehashées dans des répertoires temporaires : suffixe inattendu, résultat automatique divergent et état humain divergent. Le vérificateur rejoue ces contre-exemples et compare les refus observés aux objets publiés.

## Limites

Le rapport P2 et sa conclusion `INCONNU` restent inchangés. Aucun appel candidat ou fournisseur, aucune campagne et aucune dépense ne sont exécutés.

## Arrêt

Le succès local est `PASS_PR55_V3_LOCAL_PROOF`. Toute divergence produit `HOLD_PR55_V3_CORRECTION`. Aucun merge, aucune fermeture de #53 et aucune action M3.12 ne sont autorisés.
