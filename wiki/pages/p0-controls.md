# P0 controls and provenance

P0 evaluates the versioned AI Security Lab Coding-Agent Security Baseline
loaded from `kaapi/data/baseline-0.3.1.json`. The actual loaded rule count and
baseline version are reported by `kaapi version` and `check`.

Controls are grouped around the configured capabilities that matter for the
P0 posture: permissions, sandboxing, network, hooks, MCP, unknown fields, and
observed-source bypass behavior. Each evaluated finding carries a stable ID,
severity, observed evidence, inference, remediation, and resource references.

## Evaluation boundary

The controls describe what the observed configuration permits or exposes. They
do not claim that a command ran, a network connection succeeded, a hook was
invoked, or an MCP server was contacted.

Unknown or unsupported fields are surfaced according to the v1.3 contract;
they are not silently treated as safe. Secret-bearing values are redacted.

## Provenance

Rule provenance identifies the baseline name/version and the source control
metadata used for a finding. Baseline snapshots are secret-safe and include
schema and Kaapi versions so `verify` can reject incompatible inputs.

