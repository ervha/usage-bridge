# Usage Bridge quota checks

## When to use this

- Use this skill when the user asks how much quota is left on any AI
  subscription, when you are about to choose a model for a task, and
  whenever a decision depends on remaining quota rather than used quota.

- Read the quotas live through usage-bridge instead of answering from
  memory or from a dashboard screenshot. Quotas move during the day,
  and a stale number leads to a wrong model choice.

## How to read the quotas

- Call the usage-bridge MCP server the user configured for you
  (`POST http://<PC tailnet IPv4>:8787/mcp`, Bearer token from your
  secret store). Two tools exist: `usage_all` for every provider, and
  `usage_provider` with a provider id such as `claude`, `codex`,
  `antigravity`, or `grok` for one.

- Parse the JSON inside the tool result's text content. Each provider
  has a display name, a plan, and lines: progress lines carry the used
  percentage and a reset timestamp (UTC); text lines carry extras such
  as rate-limit reset counts and credit balances.

- Respect the `stale` flag and `fetchedAt`. If `stale` is true, say the
  reading may be out of date and give its time. The server caches for
  5 minutes, so repeated calls inside a few minutes return the same
  snapshot — do not re-query in a loop.

## Token handling — hard rule

- Never print the bridge token in chat, logs, files, commits, or
  screenshots. Keep it in your secret store and let your MCP client
  attach it.

- Never test the endpoint by hand with the real token in a shell
  command if your environment protects secret values; use your MCP
  client's normal call path instead.

## Presenting the snapshot

- Convert every reset timestamp to the user's local timezone and
  present per provider: session and weekly percentages, the reset
  date and time, and any reset-credit counts.

- Flag the pools that shape decisions: exhausted (100%) first, then
  nearly full (80% or more), with the reset time that relieves each
  one.

## First run: ask how the user wants quotas allocated

- Do this once, when the bridge is first connected (or on first use of
  this skill), before giving routing advice. Ask the user, in one short
  round of questions:
  - Which pools are for bulk work (first-pass reading, research, test
    generation)?
  - Which models or pools should be preserved, and for what kind of
    work?
  - Any hard rules? (For example: never spend a given pool on routine
    tasks, or keep a reserve for the end of the week.)

- Record the answers as the user's routing policy in your long-term
  memory or user configuration, and read back a one-paragraph summary
  for confirmation. That policy — not your own taste — is what later
  recommendations apply.

- Do not re-ask every session. Revisit the policy only when the user
  adds or drops a subscription, or says the allocation should change.

- If the user has no preference, say so and use the default below
  (roomiest pool first, scarcest preserved) until they set one.

## Turning numbers into model choices

- Treat each provider's quota as an independent pool. Spending one
  never pressures another.

- Prefer the pool with the most room for bulk work (first-pass
  reading, research, test generation), and preserve scarce pools for
  the work that actually needs them.

- When the user's routing policy names specific pools or models,
  apply that policy to the live numbers; do not invent a policy.
  State the recommendation as: which pool does the work, which pool
  is preserved, and what changes at the next reset time.

## When the bridge does not answer

- Treat a timeout or connection error as “the PC is asleep, off, or
  the server is stopped” unless the result says otherwise. Report
  that plainly, once, and offer to check again later.

- Never invent numbers to fill a gap, and never present an old
  snapshot as current. If a previous snapshot exists, label it with
  its fetch time.
