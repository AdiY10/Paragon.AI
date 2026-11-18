# Interrupted-job recovery

The scheduler leader runs a bounded recovery sweep each tick. Operators may also
run `python backend/manage.py recover_jobs`. Recovery uses row locks and preserves
the original JobRun, requester, and schedule lineage.

- Intact queued messages and active attempt leases are left alone.
- A missing queued message becomes eligible after a real 30-second grace period.
- Expired attempts are fenced before their receipt is released or replaced.
- Retry backoff is respected. A locked retry receipt is released only after a new
  transport failure is recorded; a worker's prefetched message is not mistaken for
  a failure. A recent-recovery cooldown prevents competing sweeps from releasing
  a newly created receipt again.
- Domain execution remains limited to three attempts. Repeated transport loss has
  a separate six-recovery ceiling; exhausted jobs become visibly failed.
- Replacement enqueue, attempt fencing, and the recovery event commit atomically.
  Queue errors roll back all three. Terminal jobs require an explicit admin rerun.

Recovery events retain reason, outcome, actual recovery time, and old/replacement
transport identifiers. Admin job logs expose recovery count and last-recovered time.
Handlers still must make source writes idempotent: queue recovery cannot guarantee
exactly-once external side effects.

Verification includes concurrent recovery sweeps, intact/prefetched-message guards,
active/expired leases, exhausted attempts, rollback, starvation prevention, and
bounded repeated message loss. A real local catalog job had only its queue message
removed for fault injection. After the actual grace period, one replacement was
created, the real worker completed the original job, and its recovery event remained.
No source metrics or check dates were fabricated for this verification.
