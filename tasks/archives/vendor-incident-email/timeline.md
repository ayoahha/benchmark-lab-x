# Chronologie de l'incident INC-2084

Fournisseur : Systèmes Belrive SAS (éditeur de la plateforme de facturation en ligne FactureClair)
Client : Fournitures Électriques Atlantique SAS (distributeur de composants électriques, 34 salariés)

## Déroulement des événements

- **Lundi 13 avril 2026, 23 h 40** : l'équipe d'exploitation de Systèmes Belrive lance la migration programmée de la base de données principale (version 14.2 vers 14.3). Les clients n'ont reçu aucun préavis concernant cette migration interne.
- **Mardi 14 avril 2026, 0 h 15** : la migration est déclarée terminée. Les contrôles automatisés habituels sont au vert.
- **Mardi 14 avril 2026, 6 h 12** : la supervision interne détecte une hausse anormale du nombre de connexions ouvertes à la base de données principale pendant le pic d'activité matinal. La plateforme reste accessible.
- **Mardi 14 avril 2026, 6 h 40** : la plateforme devient inaccessible pour tous les clients (erreurs 503), dont Fournitures Électriques Atlantique.
- **Mardi 14 avril 2026, 7 h 05** : l'ingénieur d'astreinte ouvre l'incident INC-2084 et mobilise l'équipe chargée de la base de données.
- **Mardi 14 avril 2026, 7 h 50** : l'équipe repère des verrous résiduels laissés par le script de migration sur la table des sessions.
- **Mardi 14 avril 2026, 8 h 15** : Systèmes Belrive publie un message sur sa page d'état et envoie un premier courriel de notification à Fournitures Électriques Atlantique. Il s'agit de la première communication adressée au client.
- **Mardi 14 avril 2026, 9 h 10** : la première tentative de suppression des verrous échoue partiellement : la réserve de connexions est de nouveau saturée.
- **Mardi 14 avril 2026, 10 h 20** : la cause profonde est confirmée. Le script de migration n'a pas libéré les verrous à la fin de son exécution.
- **Mardi 14 avril 2026, 10 h 47** : les verrous sont entièrement supprimés à la main et un redémarrage contrôlé est effectué. Le service est rétabli et vérifié.
- **Mardi 14 avril 2026, 11 h 30** : un courriel de rétablissement du service est envoyé aux clients. Aucun autre point d'avancement n'a été transmis entre 8 h 15 et 11 h 30.
- **Mercredi 15 avril 2026, 14 h 00** : pendant la réunion de retour d'expérience, l'équipe décide d'ajouter à la procédure de migration un contrôle de libération des verrous et de créer une alerte dédiée aux verrous résiduels.
