---
style_gate: pass
---

# Brief propriétaire minimal du pré-cadrage

Ce brief est le plus petit énoncé propriétaire durable du paquet `PRECADRAGE-ENTRETIEN-CLIENT-V0`. Il reprend uniquement des faits déjà présents dans le paquet courant et le corpus canonique, sans exigence nouvelle. Il n’emporte aucune approbation : l’approbation future est externe et liée au SHA-256 du manifeste du paquet (`manifeste-paquet.json`) ou de la PR qui le porte.

## Besoin

Qualifier la capacité d’un candidat à transformer des notes brutes synthétiques en pré-cadrage structuré, fidèle et utile, relu par le consultant avant un entretien client, pour une activité de conseil IA et cybersécurité auprès de PME.

## Cadre imposé

- Scénario entièrement synthétique : aucune donnée client réelle, aucun secret, aucun connecteur de production, aucune action externe.
- Sortie interne, jamais envoyée au client, marquée `client_ready: false`.
- Acceptabilité officielle : `PASS` automatique + `ACCEPTABLE` humain aveugle.
- La décision de poursuivre, réduire ou arrêter reste humaine.

## Hors périmètre

Mesure de performance, classement, conseil envoyé au client, verdict de conformité, décision autonome.
