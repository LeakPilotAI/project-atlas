# R7E46T — real-container lifecycle acceptance plan (NOT AUTHORIZED)

Atlas stays STOPPED during T. This document grants no operational permission. Production release remains NO-GO. Stop if any identity, persistence, backup, provider, or lifecycle prerequisite is ambiguous. Never inspect unrelated/Genesis resources, enumerate all containers, start/stop Docker Desktop/Engine, force-kill a process, delete/reset records, or remove Docker objects.

## A. Read-only prerequisite evidence

1. Record operator approval scope, local/CDT and UTC timestamps, branch/HEAD, dirty-tree inventory and candidate hashes. Preserve source, journals/independent commitments, lifecycle files and failure artifacts. Confirm supported Status is STOPPED; no active owner/start/stop/recovery lock or conflicting Atlas API. Status can archive conclusively dead metadata: if records are present or ambiguous, first perform a separate read-only forensic review rather than assume Status is inert.
2. Docker must already be available under separate operator control. The launcher must not manage the Engine. Read its selected endpoint and refuse anything except the supported local named pipe. Record Docker/Compose versions and local context. Exact-name inspection is discovery only, never sufficient ownership proof.
3. Inspect only atlas-postgres and atlas-redis, then their full 64-character IDs. Capture allowlisted ID/name/image digest, Compose project (atlas/projectatlas, same for both), service, working_dir exactly D:\Work\Project Atlas, exactly one matching docker-compose.yml, oneoff=False, stop signal, Running/Status/Health, restart count/policy and mount metadata. Do not dump Config.Env, credentials or global container inventories. Reject missing/foreign/mixed labels, replacement IDs, unknown signals, contradictory state or unavailable inspection.
4. Verify actual pinned image/version, PID1/signal handling and exact named-volume attachment: PG data at /var/lib/postgresql/data, Redis data at /data; Compose project/volume labels must identify this Atlas project. Compare volume identity before/after; do not create or modify volumes to pass acceptance. Missing dependencies make restoration a first-install/data-recovery decision, not routine acceptance.
5. Confirm evidence-preserving, independently verified recoverable backups of Atlas persistence and the journal/commitment pair. Any new backup/snapshot operation, database connection/read-only query or container exec needs explicit approval in the acceptance scope. Redis save/AOF configuration and current persistence errors must be verified before claiming data preservation. A mounted volume alone proves neither persistence configuration nor a successful save.
6. Freeze approved exact IDs/config hashes and record known baseline service health and non-secret continuity markers (Postgres schema/data fingerprint and relevant Redis persistent-key fingerprint). No new synthetic production records. Existing stopped-service tests cannot certify backend drain or database persistence.

If the local Engine remains unavailable, record NOT TESTED and stop. Do not start it as a side effect.

## B. Separately approved mutating acceptance

Approval must specify the exact Atlas IDs, permitted initial/final state, a reversible stop/restore window, data backup prerequisites, and whether backend-running acceptance is included. Container-only testing can leave Atlas STOPPED and is insufficient to certify live API/PAPER drain. A running-path trial additionally requires separately approved Gaming startup, permitted provider access/cash scope, and blocked production research/Discord/live-capital gates.

1. Establish only the approved initial state. If restoring existing Atlas dependencies, use the supported ownership checks and full IDs; no Compose recreate/down or broad matching. The PG and Redis services have no dependency on each other; both must be healthy before any API start.
2. For a separately approved full running-path trial, invoke the supported Gaming launcher without extended-hours opt-in. Verify real API PID/run/creation time/executable/command line, actual Gaming=true, discovery >=180s/configured safe minimum, normal PAPER cadence, PAPER_ONLY/MANUAL_ONLY and production notifications disabled. Do not infer these from HTTP200.
3. Invoke the explicit Complete script once with -Complete -Json. It first validates both container identities and holds the root lifecycle gate. Backend exit is confirmed through the verified manager before dependency requests. Current deterministic dependency order is PostgreSQL then Redis; neither depends on the other. A PostgreSQL timeout does not justify force-kill; the result remains incomplete/blocked even if Redis later stops.
4. Observe exact IDs only. Inspect receipt, pending intents, CLI creation-time identities and backend final status. Require BOTH dependencies exited, unchanged IDs/mounts, no pending intents/unconfirmed CLI, backend STOPPED and exit code zero. A stopping acknowledgement, CLI success or earlier per-service observation is insufficient. Confirm service shutdown logs with an approved allowlisted tail and persist redacted evidence. Do not read unrelated logs.
5. Idempotency: only after a trustworthy completed receipt, separately approve another explicit Complete invocation against the same stopped IDs; expect no new stop calls and unchanged persistence. Do not provoke failures in production. Fault cases remain mocked unless a separate disruption plan is approved.
6. Restore only the recorded full IDs after explicit restoration approval. Do not restart the Engine/Desktop. Verify PG and Redis healthy and unchanged mounts, then optionally the separately approved Gaming API. Verify persistence markers and PAPER/journal reconciliation, actual normal PAPER cadence and no duplicate fills. If final state must be STOPPED, stopping/restoring choices must be stated in approval; do not implicitly leave an API running.

## C. Abort / rollback criteria

Abort new actions on identity/root/config/image/mount change, backend timeout/ambiguity, unexpected provider or trading/Discord activation, save/checkpoint errors, unconfirmed CLI, growing resource use, or persistence mismatch. Preserve the exact receipt and prior versions. Never delete/reset a receipt, fabricate a manifest, replay an uncertain stop, run down/prune/rm, or terminate unrelated processes.

- Backend timeout: dependencies remain untouched; retain the verified owner/stop evidence. A blocked worker requires a separately approved ownership/recovery decision.
- Partial stop: keep API stopped. Reconcile only exact pending IDs and owned CLI identities. Once the real request is independently complete and both original IDs are stopped, an explicitly approved reconciliation invocation may produce a completed receipt. Until then startup remains blocked.
- Unavailable Engine: no absent/stopped inference, no recreation. Restore Engine availability only under separate operator control, then repeat read-only identity checks.
- Lost/replaced identity, damaged receipt or persistence mismatch: stop the acceptance; use a separate forensic/data-recovery plan with backups. No automated destructive rollback.
- Successful complete stop: ordinary rollback means starting the retained services and checking health/persistence, followed only by a separately approved disabled-research Gaming API start. It is not a container/volume recreation.

## Limits and database shutdown semantics

The infinite-grace Docker stop avoids Docker's timed SIGKILL escalation; bounded CLI observation does not bound actual database exit. [Docker stop documentation](https://docs.docker.com/reference/cli/docker/container/stop/).

PostgreSQL distinguishes SIGTERM smart drain, SIGINT fast transaction abort with normal shutdown, and unsafe-for-this-workflow SIGQUIT immediate shutdown. The actual image signal/PID1 path is a required runtime check. [PostgreSQL shutdown documentation](https://www.postgresql.org/docs/current/server-shutdown.html).

Redis handles SIGTERM/SIGINT through its shutdown sequence; configured persistence matters and save failures can leave it running. No FORCE/NOSAVE override is permitted. [Redis shutdown documentation](https://redis.io/docs/latest/commands/shutdown/).

A final inspection is point-in-time evidence. The lifecycle mutex fences supported Atlas controllers, not external Docker administrators or adversarial daemon users. Labels are an operational provenance check, not a defense against a privileged actor forging labels. Controller/daemon/filesystem failure can leave uncertain operations; manual evidence-preserving reconciliation remains necessary. No unconditional no-data-loss certification is claimed.
