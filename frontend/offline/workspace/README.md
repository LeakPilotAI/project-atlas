# Atlas offline evidence workspace

This is static artifact packaging. It does not open a browser, start Atlas/Docker,
connect a provider, import data, authorize trading or bypass the startup lock.
The native browser file-URL test was blocked by the tool's URL security policy;
no alternate surface, HTTP server, raw browser commands or policy workaround was
attempted. Native visual/CSP acceptance remains unestablished.

Build an explicit **new** folder with the installed Node runtime:

`node frontend/offline/workspace/build.mjs <new-directory>`

The builder reuses the existing market and forecast viewers, writes a script-free
navigation page and instructions, then publishes a non-activating manifest last.
Nothing is preloaded. All paths/links in the package are fixed relative members.
The generated pages are self-contained; future development changes do not replace
an existing bundle or hot-reload it. The source code is not independently signed.

Retain the returned manifest SHA-256 separately. Verify supplied bytes offline:

`node frontend/offline/workspace/build.mjs --verify <directory> --expected-manifest-sha256 <retained-sha256>`

Verification checks exact members/lengths/hashes, denied permissions and fixed
source schemas, without extracting/executing pages or granting browser acceptance.
A rehashed manifest cannot turn production or native acceptance on. Hashes do not
establish provider provenance, licensing, hardware durability or source truth.

A failed build preserves partial evidence and never overwrites/deletes it. Do not
reuse that directory. A failure late in publication can leave a manifest; only a
completed build receipt and explicit verification establish supplied-byte success,
and neither grants production authority. Use a new path after investigating the
failure. Cooperative path/file identity checks do not exclude privileged actors,
full-machine rollback or every concurrent namespace mutation.

No real datasets, credentials, PAPER state, databases, backup/restore, deployment,
shortcut integration or protected production storage is included. Production NO-GO
and all 21 release decisions remain unchanged.

## Reading the market page

Choose an explicitly supplied JSON export; selecting a file never starts data
collection. Supported modes include completed bars, quote quality, session-window
quality with recorded lifecycle context, descriptive research and paired replays.
The report clock is fixed evidence, not the current wall clock.

Session quality describes only first-to-last observed bars. Interior missing
minutes are not proof of missed market events. Empty observations establish no
coverage, and truncated history excludes earlier evidence. Past-session rows do
not establish current freshness. Recorded lifecycle is unauthenticated and cannot
prove that Atlas is running/stopped or grant startup/recovery permission.

Clear removes the displayed model. A refused replacement clears earlier content;
late file reads cannot restore it. Files are not uploaded, persisted or preloaded.
This workspace is an offline evidence viewer, not the authorized live dashboard.

## Explicit V2 workspace with comparison packets

V1 remains the default, with its original dependency set and manifest contract.
Build the separate V2 profile explicitly:

`node frontend/offline/workspace/build-v2.mjs <new-v2-directory>`

V2 adds `comparison.html` and a third navigation link. It contains exactly five
hashed content members plus `manifest.json`; no reports, packets or credentials
are included. Store supplied JSON outside the immutable bundle. The comparison
page requires matching source pins, not trust claims from an imported packet.

Retain the returned manifest SHA-256 separately. The schema-aware existing verifier
checks either version without changing it:

`node frontend/offline/workspace/build.mjs --verify <directory> --expected-manifest-sha256 <retained-sha256>`

The V2 entry point also supports that verification form and requires a V2 schema.
Old V1 folders continue to verify. Pre/post V1 builds under identical viewer source
were byte-identical across all members, including the manifest. New V2 navigation
never silently upgrades a V1 directory or rewrites existing evidence.

V2 explicitly rejects raw UTF-8/BOM normalization, extra/missing/reordered/linked
members and authority/data/native-acceptance claims. Partial failures remain on
disk; a manifest alone is not proof of a successful build receipt. Hash checks do
not attest licensing, data authenticity, runtime authority or hardware durability.
Native browser visual/security acceptance remains NOT_ESTABLISHED. No server or
browser automation workaround is started by either profile.

Packet source/build refusal explains that a matching archived viewer is required;
never edit verification pins/manifests to force acceptance. A mismatch does not
establish whether the supplied packet is valid. Malformed/authority claims remain
generic refusals; private reader errors are not echoed. All failures clear any
previous comparison. Previously generated pages are immutable and retain their
original messages; regenerate an explicitly new artifact to obtain updated UI.


## Conditional scenario research is separate

The existing offline forecast CLI also supports explicit assumption-driven scenarios:
see [command and request format](../../../docs/AFI_CONDITIONAL_SCENARIO_COMMAND.md).
It publishes separate content-addressed JSON and scriptless HTML for illustrative
2030/2040/2050 paths. Open that HTML independently; scenario plans/results are not
accountability exports and must not be loaded or scored as forecasts here.
Selection refuses and clears prior evidence. No probability, calibrated interval,
market-price accuracy or trading authority is implied. Older immutable workspace
bundles retain their original messages; use a new explicit build for new guidance.

## Packaged forecast-history onboarding

New V2 builds link their bundled README.txt from index.html. The walkthrough distinguishes producer requests, browser_export envelopes, current/prior reports, and source-pinned comparison packets. It preserves pending/resolved/corrected original identities, explains explicit cohort selection and unavailable values, and keeps preview separate from publication. Producer creation/update instructions remain in the matching source archive at scripts/observation_runtime/DAILY_FORECAST_WORKFLOW.md; the static package does not run those commands or include datasets. Existing V1 and historical V2 bundles remain unchanged.
