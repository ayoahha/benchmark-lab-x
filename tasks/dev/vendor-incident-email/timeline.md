# Timeline of incident INC-2084

Provider: Northbridge Systems Ltd (publisher of the LedgerCloud online invoicing platform)  
Client: Atlantic Electrical Supply Ltd (electrical-component distributor, 34 employees)

## Sequence of events

- **Monday, 13 April 2026, 23:40**: the Northbridge Systems operations team starts the scheduled migration of the primary database (version 14.2 to 14.3). Clients received no advance notice of this internal migration.
- **Tuesday, 14 April 2026, 00:15**: the migration is declared complete. Standard automated checks are green.
- **Tuesday, 14 April 2026, 06:12**: internal monitoring detects an abnormal rise in the number of open connections to the primary database during the morning traffic peak. The platform remains accessible.
- **Tuesday, 14 April 2026, 06:40**: the platform becomes inaccessible to all clients (503 errors), including Atlantic Electrical Supply.
- **Tuesday, 14 April 2026, 07:05**: the on-call engineer opens incident INC-2084 and mobilizes the database team.
- **Tuesday, 14 April 2026, 07:50**: the team identifies residual locks left by the migration script on the sessions table.
- **Tuesday, 14 April 2026, 08:15**: Northbridge Systems posts a message on its status page and sends Atlantic Electrical Supply an initial notification email. This is the first communication to the client.
- **Tuesday, 14 April 2026, 09:10**: the first attempt to clear the locks partially fails: the connection pool becomes saturated again.
- **Tuesday, 14 April 2026, 10:20**: the root cause is confirmed. The migration script did not release the locks when it finished.
- **Tuesday, 14 April 2026, 10:47**: the locks are cleared completely by hand and a controlled restart is performed. Service is restored and verified.
- **Tuesday, 14 April 2026, 11:30**: a service-restoration email is sent to clients. No other progress update was sent between 08:15 and 11:30.
- **Wednesday, 15 April 2026, 14:00**: during the post-incident meeting, the team decides to add a lock-release check to the migration checklist and create a dedicated alert for residual locks.

