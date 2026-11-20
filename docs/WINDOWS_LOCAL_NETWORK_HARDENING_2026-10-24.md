# Windows-local Compose network hardening — 2026-10-24

Base: `86378fcdc1c38cdc7e2b41347d8d80245269d7ec`; branch `chatgpt/atlas-rebuild-v1`. Source configuration corrected; no runtime application or operational acceptance.

## Exact change and resolution

| Atlas service | Previous published mapping | Updated published mapping | Real Compose resolved fields |
|---|---|---|---|
| PostgreSQL | `5432:5432` | `127.0.0.1:5432:5432` | host_ip `127.0.0.1`, published `5432`, target `5432`, protocol `tcp` |
| Redis | `6379:6379` | `127.0.0.1:6379:6379` | host_ip `127.0.0.1`, published `6379`, target `6379`, protocol `tcp` |

Only these two port strings change in `docker-compose.yml`. Independently parsed original/updated YAML and genuine resolved Compose configuration are identical after replacing just their port fields. Images/digests, credentials/environment expressions, container names, volumes/mounts, health checks, restart policy, services and dependencies are unchanged. No actual credentials were read or logged. Existing financial data, protected stores and original history remain untouched.

`ATLAS_DEPLOYMENT_POLICY.json` now records SOURCE_LOOPBACK_VERIFIED_RUNTIME_ACCEPTANCE_PENDING. This is configuration evidence only, not a change to any of the 21 release decisions, D1 storage authority or startup permission. The autonomous state's policy mirror/digest is updated consistently.

## Compose/override and environment inventory

One tracked operational Compose file: root `docker-compose.yml`. No additional active Atlas Compose override was found. The approved manager explicitly defines `$ComposePath = Join-Path $Root "docker-compose.yml"` and selects `--project-name atlas --file $ComposePath`; it does not rely on automatic default override discovery or inherited COMPOSE_FILE selection for this path. The two database port declarations are fixed strings, with no environment interpolation. Process COMPOSE_FILE/COMPOSE_PROFILES/COMPOSE_PROJECT_NAME/COMPOSE_PATH_SEPARATOR selectors were absent during inspection; no selector values or real dotenv contents were exposed.

Four retained Atlas sandbox copies were discovered: `.e126-sandbox/docker-compose.yml`, `.e125-sandbox/docker-compose.yml`, `.r7e41-sandbox/docker-compose.yml` and `.e135-sandbox/docker-compose.yml`. They are historical copies, not selected overrides. They retain old wildcard-style port strings and are byte-preserved; they must not be used as operational launch configurations. No additional Compose file was discovered in the inspected Atlas repository inventory. Regression coverage requires explicit review if a new root Compose file/automatic override appears or include/extends/network-mode changes bypass this contract.

Validation used the installed Docker Compose CLI with explicit Atlas file/project/project-directory and an empty test-owned `--env-file`. A filtered subprocess environment supplied only synthetic database values; COMPOSE_DISABLE_ENV_FILE was set. Inherited credentials and Compose selectors were excluded. Only `docker compose ... config --format json` was executed: no engine/container query, connection, image resolution/pull, create, up, start, stop, recreate, migration or firewall action. Full resolved credentials were not published; retained evidence includes only nonsensitive mappings and equality results. Source password expressions are unchanged.

## Atlas/Genesis separation and remaining exposure

The actual Atlas source declares only postgres/redis, `atlas-postgres`/`atlas-redis`, `atlas_pgdata`/`atlas_redis`, with no include/extends/external-network adoption. No Genesis configuration, files, processes, services or Docker resources were accessed. Consequently, actual Genesis listener settings and host-port availability/collisions are **NOT TESTED**; absence of a runtime conflict is not claimed. Preserving existing Atlas host/container port numbers introduces no new port-number allocation.

Existing containers are not recreated or reconfigured by editing YAML. Their current published listeners, firewall behavior and actual external reachability are **UNKNOWN / NOT INSPECTED**. Historical sandbox files still contain unapproved wildcard-style mappings. Future overrides, raw container commands and internal Docker-network connectivity require separate review; this source change does not isolate containers from all local clients, establish financial-writer exclusion, prove process ownership or provide independent custody. Local loopback clients, same-user/admin code and the existing C1/D1 threat-model limitations remain applicable.

No attempt was made to apply this correction. The current full startup/refusal contract and existing-container/no-recreate policy remain unchanged. Applying a changed port binding to an existing container may require a separately authorized lifecycle action; do not silently recreate containers, adopt volumes or bypass the startup lock. Before any authorized activation, independently inspect exact Atlas-owned identities, accepted data/storage state, resolved effective configuration and collision/exposure evidence within an explicit scope.

## Tests and continuation

Focused combined validation: **15 passed, 0 failed, 0 skipped**, 2.89s. Includes 7 new configuration regressions, 5 existing packaging regressions (one strengthened to require explicit loopback) and 3 production-lock regressions. The new cases assert both raw YAML and real resolved mappings, one mapping per service, unchanged owned resources, no host-network bypass, explicit reviewed root config and deployment-policy/manager consistency. Existing wildcard regression would fail if either mapping reverted. No assertions were weakened.

Targeted Ruff and in-memory compilation pass. The real CLI also resolved pre-change and post-change configuration using synthetic values and confirmed all non-port resolved fields unchanged. Static source/resource guards and checkpoint backup/read-back/historical preservation checks pass. Tests did not start Atlas, providers, databases, containers, trading, PAPER or Discord, and did not inspect financial records. No native listener/browser/operational acceptance test was performed or claimed.

Next operational-readiness step remains independent B1 selected-account and local C1/D1 ownership/custody acceptance, followed by separately authorized operational read-only composition. Before any future dependency lifecycle acceptance, approve the exact Atlas-only application of these bindings and verify accepted container/volume identity, exposure and collision checks; no lifecycle action is authorized by this commit. Provider rights and supervised E1 release remain separate.

All 21 decisions unchanged; all seven phases/history preserved: Phase 1 incomplete; Phase 2 Evidence Engine/AFI HOLD (AFI-1–10 PENDING/0 accepted); Phase 3 BLOCKED; Phase 4 Cross-Market pending; Phase 5 SaaS historical/deferred under local-only constraints; Phase 6 institutional pending; Phase 7 commercial pending. Alien-themed frontend, startup locks, legacy accounts and Genesis isolation preserved. B1/C1/D1/E1 BLOCKED. PAPER startup NO; production NO-GO.
