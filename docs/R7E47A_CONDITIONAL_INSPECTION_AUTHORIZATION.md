# R7E47A — conditional one-time authorization request (NOT ACTIVE)

**Real-volume inspection BLOCKED. Do not approve execution until every prerequisite below is evidenced. This document is not authorization or an executable command.**

Prerequisites: fresh reachable Docker and STOPPED Atlas/no pending lifecycle operations; exact production IDs/volumes/labels/CreatedAt/mounts and EXITED PID0/only expected exited consumers; fresh pinned imported image verification; independently reviewed execution wrapper/full-control checks/bounded output; supported lifecycle serialization plus operator-exclusive no-start/no-write/no-replacement window; protected output directory using existing acceptable access (no ACL changes here); explicit uncertain-helper ownership/recovery and permission-failure policy. No guarantee of hard40-second exit or atomic exclusion of a privileged external actor. If these guarantees are mandatory, do not authorize this method.

After all prerequisites PASS, the operator may separately authorize this exact scope, completing the placeholders:

Operation ID: [new unique ID]. Exclusive window: [start/end/timezone and responsible operator]. Evidence directory: [new exact Atlas-only protected diagnostics path]. Recovery owner: [operator]. Approval expires at [time] and is invalidated by any state/identity/control change.

One sequential attempt per volume, PostgreSQL then Redis, only after the previous helper conclusively exits and post-checks pass. Expected sources:
- c955b8647bb6c18a30e42a7506fa1b6c45f7b1837275d49297bacc6f1c0f11c1 / projectatlas/postgres / projectatlas_atlas_pgdata / production destination /var/lib/postgresql/data.
- 13617d3155a2b3f4c6184a380892acf544de02e21b7c783c85a0de4b63e9c193 / projectatlas/redis / projectatlas_atlas_redis / production destination /data.

Image sha256:2ec3306c7d7e5714f49db15ea0db636622e01d061e87ceac27d0ec2bbd1b2574, source sha256:06d1ba89a7b89d0289ea0db87d5385797536eaa5033555822cb8f5d0325fe9a6. Only one exact readonly volume-nocopy mount at /inspection. RootfsRO, networknone, no socket/host mounts/host namespaces, privilegedfalse, capdropALL, no-new-privileges, defaultseccomp,user0:0,CPU0.25,128MiB memory+swap,PID16,nofile64,pullnever,restartno,autoremovefalse. Exact entrypoint python3 -I -B /opt/atlas-inspector/helper.py postgres|redis. No environment credentials, payload/config content reads or source writes/hashes/copies. Metadata cap65536bytes, entries100000,depth32, alarm30s, observer40s. Capture only bounded metadata/control/exit evidence in approved directory; redact unknown names/targets; no sharing outside operator-approved storage.

Before creation and before start, freshly revalidate exact sources/image/fence; inspect actual helper identity/mounts/full controls before start. Missing/changed/ambiguous evidence aborts; never create a missing source. On permission failure, partial output, external links, limits, drift, malformed output or nonzero exit: INCOMPLETE/BLOCKED, no retries or privilege changes. At observer deadline: UNCERTAIN, retain exact helper/evidence, do not launch second helper, do not start Atlas/databases or release writer prohibition. No automatic stop/kill/removal; separately approved exact-helper recovery required. Review post-operation identities and confirm all created helpers EXITED before declaring bounded attempt complete.

This grants no backup creation, database restoration, production lifecycle acceptance/startup, cleanup/removal, ACL/shortcut modification, trading or Discord authority. Read-only metadata is neither snapshot nor usable-backup proof. No real operation is approved by R7E47A.
