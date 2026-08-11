# Vérification — réponse à un incident — verify-v2

## Liste de contrôle binaire

- [ ] [S] 1. La sortie contient uniquement le corps du courriel entre `<email>` et `</email>`.
- [ ] [C] 2. Le corps du courriel ne dépasse pas 200 mots.
- [ ] [C] 3. La cause est exacte : le script de migration a laissé des verrous sur la table des sessions.
- [ ] [C] 4. La cause est exacte : la réserve de connexions a ensuite été saturée.
- [ ] [C] 5. La mesure corrective convenue est exacte : un contrôle de libération des verrous a été ajouté à la procédure de migration.
- [ ] [C] 6. La mesure corrective convenue est exacte : une alerte dédiée aux verrous résiduels a été créée.
- [ ] [C] 7. Un geste commercial est explicitement proposé.
- [ ] [C] 8. Le geste commercial n'est pas présenté comme déjà décidé dans les documents fournis.
- [ ] [C] 9. Aucun délai chiffré de résolution n'est promis.
- [ ] [C] 10. Le courriel ne reconnaît aucune faute contractuelle.
- [ ] [C] 11. Le courriel explique que les verrous empêchent temporairement d'autres opérations de modifier les mêmes données.
- [ ] [C] 12. Le courriel explique que la réserve de connexions est l'ensemble des connexions à la base de données disponibles pour la plateforme.
- [ ] [C] 13. Aucun fait, horaire, engagement ou état d'avancement ne contredit les documents fournis.
- [ ] [S] 14. Qualité — aptitude à l'envoi au destinataire : niveau non insuffisant (voir la rubrique de qualité Q2).

## Rubrique de qualité

Deux dimensions au plus. Chaque dimension notée **insuffisant** compte comme un item `[S]` échoué (jamais `[C]`). Les niveaux acceptable et excellent valident tous deux l'item. Les niveaux reposent sur des propriétés observables par rapport aux ancrages.

La dimension Q1 (clarté technique) a été retirée dans `verify-v2` : elle faisait double emploi avec le contrôle en langage courant, désormais exprimé par les items 11 et 12 sous forme de prédicats observables tirés d'`anchor-pass.md`.

### Q2. Aptitude à l'envoi au destinataire [S] (item 14)

- **insuffisant** : le ton est défensif, désinvolte ou centré sur des considérations internes ; ou le courriel ne peut pas être envoyé en l'état (comme dans `anchor-fail.md` : il reconnaît une faute, garantit un délai chiffré de correction et présente un remboursement comme déjà approuvé).
- **acceptable** : le ton est neutre et professionnel ; le courriel peut être envoyé au client sans réécriture du registre (comme dans `anchor-pass.md`).
- **excellent** : le registre reste tourné vers le client de bout en bout, comme dans `anchor-pass.md`, avec une prochaine étape explicite (par exemple, une prise de contact séparée sur les modalités du geste commercial) et sans formulation interne résiduelle.

## Faits de référence

| Élément | Référence |
| --- | --- |
| Indisponibilité totale | 14 avril 2026, de 6 h 40 à 10 h 47, soit 4 heures et 7 minutes |
| Première alerte interne | 6 h 12 ; la plateforme était encore accessible |
| Cause profonde | Verrous non libérés par le script de migration sur la table des sessions ; saturation de la réserve de connexions pendant le pic matinal |
| Rétablissement | Verrous entièrement supprimés à la main et redémarrage contrôlé à 10 h 47 |
| Mesure convenue le 15 avril | Contrôle de libération des verrous dans la procédure de migration et alerte dédiée |
| Première notification au client | 8 h 15, plus d'une heure après le début de l'indisponibilité totale à 6 h 40 ; le délai contractuel n'a pas été respecté, même avec ce point de départ prudent |
| Points d'avancement | Aucun entre 8 h 15 et le courriel de rétablissement à 11 h 30 |
| Maintenance | Le client n'a pas reçu de préavis de 72 heures concernant la migration ; elle ne peut donc pas être exclue du calcul en tant que maintenance programmée au titre de la clause 12.1 |
| Disponibilité mensuelle calculée | 99,43 % pour avril 2026, sous le seuil contractuel de 99,5 %, en supposant qu'aucune autre interruption ne s'est produite ce mois-là ; cette hypothèse de référence ne doit pas être exigée du candidat |
| Geste commercial | Aucun geste n'est convenu dans les documents fournis ; toute formulation doit rester une proposition |
