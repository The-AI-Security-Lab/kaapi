# P1 Codex adapter

## Scope

P1 adds deterministic analysis for explicit Codex `config.toml` files and
conservative system/user discovery. It uses Python `tomllib`; it does not
launch Codex, inspect credentials, connect to MCP servers, execute hooks or
commands, call a model, or access the network.

Supported observed surfaces are:

- `approval_policy` and `approvals_reviewer`;
- `sandbox_mode` and classic `sandbox_workspace_write` settings;
- `web_search` and `features.network_proxy`;
- `allow_login_shell` is parsed and validated, but does not currently
  materially affect resolution or findings;
- `mcp_servers`, retaining counts and approval metadata while omitting
  commands, URLs, headers, arguments, environment values, and tokens.

Permission profiles, Codex hooks, apps, plugins, skills, and unmodelled feature
flags are classified as not evaluated. Their presence prevents a clean PASS.

## Precedence and trust

System config is lower precedence than user config. Project config is loaded by
Codex only for a trusted project, so automatic discovery detects but does not
apply project TOML while trust is unobserved. Supplying that project TOML as an
explicit path analyzes it reproducibly as one observed document.

## Normalization

The adapter maps platform-specific facts into the shared resolution shape:
configured approval behavior, shell/read/write state, sandbox boundary,
command-network and web-search potential, MCP count, and sorted capability
tokens. It uses the Codex baseline projection 0.4.0 with OpenAI provenance.
It never claims that configured enforcement succeeded or that an action,
connection, escalation, review, or MCP tool call occurred.

## Authoritative sources

Verified 2026-08-30:

- [Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
- [Config basics](https://learn.chatgpt.com/docs/config-file/config-basic)
- [Advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced)
- [Agent approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security)
- [Decision log](../../Decisions.MD)
