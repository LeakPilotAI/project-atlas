# Offline conditional scenario command

This is assumption-driven illustrative index research. It is not a fitted forecast, asset price, probability, calibrated interval, entitlement or trading authority. Production remains NO-GO.

Use the existing backend Python environment with backend on PYTHONPATH. The output directory must already exist and be an explicitly chosen disposable/research directory, never protected runtime state.

`python -m app.backtest.forecast_cli scenarios --plan <explicit-plan.json> --output-root <existing-output-directory>`

Exact request format (illustrative assumptions only):

```json
{"schema":"AFI_ASSUMPTION_SCENARIO_REQUEST_V1","base_year":2026,"milestones":[2030,2040,2050],"annual_assumptions":{"bear":-0.02,"base":0.02,"bull":0.05}}
```

Only these fields are supported. Existing engine bounds apply: ordered bear/base/bull rates greater than -1 through 0.5, unique future milestones within100 years, explicit baseyear1900–2100. Input is bounded32KiB and parsed with existing duplicate-key/nonfinite refusal. Unsupported positive numeric range, including underflow, refuses before publication.

Successful stdout identifies content-addressed JSON and scriptless HTML, exact request hash and scenario commitment. The index starts at100, has no asset identity, prices or probability. Structural breaks, inflation, dividends, fees and taxes are not modeled. Read assumptions and uncertainty before using any long horizon.

Exit0 is returned only after both artifact readbacks. Exit2 means refused input/publication; preserve any partial files. This is not a multi-file atomic transaction. Exact retry uses existing immutable publisher; do not delete or overwrite evidence to force success. Hashes establish supplied-byte consistency, not source authenticity or hardware durability. A successfully built HTML is not native browser acceptance.

No provider, runtime, Docker, database, broker, Discord or trading connection is created. Existing forecast/replay CLI modes are unchanged.
