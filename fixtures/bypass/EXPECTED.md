# Expected: bypass

- `kaapi check fixtures/bypass/settings.json` reports `FAIL` and exits 1.
- `AGENT-APRV-001` is the first/headlined finding and records the observed
  settings-mode bypass with source location.
- The explicit Bash, WebFetch, and WebSearch denies remain effective despite
  bypass mode.
