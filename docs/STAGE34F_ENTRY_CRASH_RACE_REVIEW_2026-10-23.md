# Stage34F — independent local entry-path and crash/race review

Branch chatgpt/atlas-rebuild-v1,HEAD f9df47b4cd80dd647d85043aba617cf00c4e6dc0; extensive dirty work preserved. Reviewed34D/34E source/reports/tests. Only frontend AGENTS applies outside changed test scope. Independent here means a fresh local review path, not third-party security certification.

| Entry | Coverage | Decision/limit |
|---|---|---|
| Windows manager Start | parent unconditional assertion before root/runtime setup,locks,worker creation | GUARDED refusal-only |
| Direct manager Worker | independent entry assertion plus first worker-function statement | GUARDED refusal-only before dependencies/API |
| Worker function | unconditional assertion before ownership reads | GUARDED if normal imported refusal module intact |
| GUI Run/Gaming | existing conservative refusal and downstream manager guard | GUARDED; GUI native acceptance separate |
| Gaming wrapper | manager delegation | GUARDED downstream; wrapper configuration is not authority |
| Atlas-Launch.ps1 | legacy error/exit before operational code | INTENTIONALLY DISABLED |
| ATLAS.bat/start-atlas.bat | delegate disabled legacy launcher; batch has later stop-script call | NOT ENDORSED; not executed; stop-script safety outside this admission scope |
| Direct API lifespan | independent Python unconditional production lock | GUARDED at lifespan; import-time effects not universally excluded |
| Manual Docker/arbitrary writer/utilities | not comprehensively integrated | UNGUARDED by this foundation; prohibited/outside demonstrated boundary |

New tests tests/test_stage34f_security.py: concurrent separate SQLite connections consume same token once; fixture subprocess abrupt os._exit before commit rolls back (token remains unused); abrupt exit after committed consumption makes replay refuse; backward/expired/bool/nonfinite clock input refuses; two parallel Start and two parallel Worker requests refuse with forged env flag and authorization-file path; partial SQLite header refuses without reconstruction or changed bytes. Process exit targets only fixture subprocess itself, not any external PID. Existing34D cases cover missing/malformed/expired/run/identity/corrupt/absent evidence and replay. Existing34E tests cover ordering before operational paths. No generic kill/cleanup/recovery operations added. CLI evidence arguments do not exist on manager; parameter binding or unconditional guards refuse, not accepted as authority.

Final30 passed,0 failed/skipped in5.63s:10 new34F cases+20 retained34D/E/lock cases. Logs logs/diagnostics/stage34f-tests.txt. Targeted Ruff,compile,diff and PowerShell parsing passed. No production code correction demonstrated or made. No original failures in this selection. No deadlines changed. No production startup,operational worker,dependencies,API,Docker,Genesis,database,collector,PAPER,trading,Discord or external writer action. Actual manager tests terminate at refusal assertions before operational work.

Residual security limits: supplied identity callback/clock/issued envelope remain trusted caller assumptions in offline prototype. Windows-native independent process observation, protected SQLite namespace/sidecars,VFS identity-before-access,anti-rollback custody,issuer authority and monotonic/witnessed time unaccepted. Full-machine/privileged compromise and external writers not excluded. Same-store replay protection cannot survive adversarial store replacement/rollback. Crash before commit is not a durable startup intent; production never consumes these receipts. Arbitrary Python import-time effects and standalone writer inventory need separate review before enabling. No claim of exhaustively testing all absent services or every CLI/env combination. Recovery is not implemented and no uncertain fence is cleared.

Files changed this stage: new tests/test_stage34f_security.py; this report; master roadmap checkpoint/diagnostics. Existing unrelated files preserved. No staging/commits/push/reset/cleanup.

Next recommended Stage34G: narrowly scoped production-integration prerequisite decision for native identity, trusted authority/clock and protected durable intent storage, reusing prior R7E47 security findings. Keep refusal-only paths intact. Do not build or enable a bypass, replay unsafe registry state or start services. Separate entry pre-import side-effect inventory and isolated crash-intent tests may proceed offline. Native GUI defects and Stage32 remain unaccepted. AFI1–10 PENDING,accepted0/10,Phase2 HOLD,Phase3 BLOCKED,production NO-GO,all21 decisions unchanged.
