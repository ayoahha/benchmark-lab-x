<email>
Hello,

We are sorry for the disruption caused by the outage on 14 April.

Our investigation confirmed that the database migration script left locks on the sessions table. These locks, which temporarily prevent other operations from changing the same data, exhausted the connection pool during the morning peak. The connection pool is the set of database connections available to the platform.

We completely cleared the locks and performed a controlled restart. Service was restored and verified at 10:47.

We have added a lock-release check to the migration procedure and a dedicated alert for residual locks so that this condition is detected immediately.

As a goodwill gesture, we propose a credit toward a future invoice. We will contact you separately to agree its terms.

Regards,

Northbridge Systems
</email>

