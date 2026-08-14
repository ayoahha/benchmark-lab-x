---
style_gate: pass
---

# Notes brutes pour un pré-cadrage avant entretien

## Contexte du cabinet

`[N-A]` L'Atelier Sillage IA-Cyber est un petit cabinet fictif qui accompagne des PME B2B sur des sujets d'intelligence artificielle et de cybersécurité. Camille Rive, persona fictif, doit préparer un entretien avec une entreprise prospecte. Le document produit restera un support interne et sera relu par Camille avant l'entretien.

## Note de prise de contact

`[N-B]` La Manufacture Boréale Synthétique est une PME B2B fictive de composants industriels. La personne qui a pris contact évoque deux besoins : aider l'équipe commerciale à préparer les demandes entrantes et aider l'équipe support à trier les demandes reçues.

`[N-C]` Elle mentionne des exports du suivi commercial, des messages de support et des clauses contractuelles. Aucun exemple n'a encore été transmis. Le besoin prioritaire n'est pas indiqué. Les critères qui permettraient de décider si la démarche mérite d'être poursuivie ne sont pas définis.

## Note commerciale

`[N-D]` L'équipe commerciale imagine une démonstration branchée directement sur la messagerie de production pour montrer le flux réel. Elle affirme aussi que tous les contenus reçus peuvent être réutilisés librement, puisque l'entreprise les détient déjà.

`[N-E]` Le rôle des personnes qui reliraient ou corrigeraient une proposition n'est pas précisé. La note ne dit pas qui pourrait autoriser l'accès aux sources.

## Note du responsable informatique

`[N-F]` Aucun accès ni connecteur de production ne doit être utilisé pendant le pré-cadrage. Un corpus synthétique convient pour une première démonstration interne. Les règles d'hébergement, de conservation et d'outillage n'ont pas encore été communiquées.

`[N-G]` Les données réelles de clients et de prospects, les secrets, les identifiants et les jetons d'accès sont exclus de la qualification. La localisation exacte des sources et l'autorité capable d'en permettre l'usage restent à clarifier.

## Note de l'équipe support

`[N-H]` Les messages de support peuvent contenir des noms de clients, des descriptions d'incident et des éléments couverts par des clauses contractuelles. L'équipe ne sait pas si ces clauses permettent une réutilisation pour ce projet. Elle ne précise pas non plus qui validerait une proposition avant usage.

## Demandes reçues avant l'entretien

`[N-I]` Une personne demande que le pré-cadrage garantisse la conformité réglementaire et l'absence de risque cyber. Une autre attend déjà une architecture de production, un budget et un délai ferme.

`[N-J]` Aucune pièce ne permet de répondre à ces demandes. Elles doivent être qualifiées comme excessives ou non établies, sans inventer de réponse.

## Consigne de production

`[N-K]` À partir de ces notes, rédige un pré-cadrage structuré destiné à la revue du consultant avant l'entretien. La sortie doit être autonome, interne et marquée `client_ready: false`.

Utilise cette enveloppe :

```yaml
artifact_type: pre_cadrage_entretien_client
version: V0
scenario: synthetique
client_ready: false
qualification: QUALIFIABLE | NON_QUALIFIABLE
conformite: NON_EVALUEE
```

Présente ensuite, dans cet ordre :

- `Périmètre`
- `Faits établis`
- `Contraintes critiques`
- `Inconnues`
- `Hypothèses conditionnelles`
- `Contradictions à arbitrer`
- `Risques prioritaires`
- `Questions prioritaires pour l'entretien`
- `Prochaine action`
- `Exclusions`

`[N-L]` Distingue les faits, les inconnues et les hypothèses. Signale les contradictions sans les résoudre. La prochaine action reste la revue du consultant. Ne prononce aucun verdict de conformité, n'invente aucun budget ni délai et ne déclenche aucune action externe.

Chaque repère `N-*` préfixe le paragraphe qui le suit. Ces ancres neutres localisent les fragments des notes sans indiquer le contenu attendu ni son verdict. Termine chaque élément structuré dérivé des notes par ses ancres, sous la forme `[sources: N-A]` ou `[sources: N-A, N-B]`. N'utilise aucun autre système d'identifiants. La présence d'une ancre sera contrôlée automatiquement ; la fidélité et l'utilité du contenu seront évaluées par une revue humaine aveugle.
