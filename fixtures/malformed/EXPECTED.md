# Expected: malformed

- `kaapi check fixtures/malformed/settings.json` emits a safe configuration
  parse error with source line/column and exits 3.
- No configuration value is echoed.
