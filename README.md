# agent-canary-data

**Canary *data* as the agent-authorization tripwire.**

When AI agents go rogue, nobody detects it — incidents surface only because the attacker confesses. So stop trying to detect misbehavior: plant canary records (realistic-but-fake customers, files, credentials) the agent should never touch. **Any read of a canary = AUTHORIZATION-EXCEEDED.**

Canary tokens exist for infrastructure; canary *data* for agent authorization boundaries is the new primitive.

## The insight

Behavioral detection tries to recognize "bad behavior" in an infinite space of agent actions. That's a losing game. `agent-canary-data` flips it: define the authorization boundary *positively* with data that legitimate work never touches, and treat any contact as proof of violation. One tripwire read is evidence no log analysis can produce — the agent didn't wander into a gray area, it touched something that had no reason to exist in its world.

## Install

```bash
pip install -e .
# stdlib only — zero third-party dependencies, Python 3.11+
```

## Usage

Three CLI commands:

```bash
# 1. plant — generate realistic fake records into the target datastore
canary plant --count 3
canary plant --types customer,credential --count 2 --seed 42

# 2. monitor — run a watched agent session; flags any read of a canary
canary monitor --mode clean --task "summarize top customers"
canary monitor --mode snooping --agent-id agent-7

# 3. report — list tripped canaries with record id + accessor context
canary report
canary report --json
```

Use `--backend sqlite --sqlite-path canaries.db` for the SQLite datastore instead of the default JSON-file datastore.

## Example output

```
$ canary monitor --mode snooping --agent-id agent-7
Monitor session complete: 6 tripwire event(s).
  TRIPPED canary-09oafx1e9fsg by agent-7 @ 2026-10-17T02:44:33+00:00
  ...

$ canary report
6 tripwire event(s) — AUTHORIZATION EXCEEDED:

  record_id : canary-09oafx1e9fsg
  accessor  : agent-7
  context   : task='summarize top customers' mode=snooping
  timestamp : 2026-10-17T02:44:33+00:00
  query     : SELECT * FROM customers (unscoped dump)
  verdict   : AUTHORIZATION-EXCEEDED
```

A clean agent — one that stays inside its task scope — trips nothing, and `canary report` prints an empty report. That asymmetry is the entire point: **zero false positives by construction**. If it trips, authorization was exceeded. Full stop.

## Programmatic API

```python
from canary import MonitoredStore, plant_canaries
from canary.adapters import SqliteAdapter
from canary.demo import MockAgent

# Plant canaries into any datastore adapter
adapter = SqliteAdapter("prod-canaries.db")
for record in plant_canaries(count=3, seed=42):
    adapter.write_record(record)

# Wrap with the watch layer — every read is tripwired
store = MonitoredStore(adapter)
store.read_record("canary-xyz...", accessor="support-agent-3",
                  accessor_context="task='refund customer' role=support",
                  query="get_customer(canary-xyz...)")

# Report
for event in store.events():
    print(event.record_id, event.accessor, event.verdict)
```

## Datastore adapters

Implement the duck-typed `DatastoreAdapter` interface to plug in any datastore:

```python
from canary import DatastoreAdapter

class PostgresAdapter(DatastoreAdapter):
    def write_record(self, record): ...          # persist + register canary id
    def read_record(self, record_id, accessor, accessor_context="", query=""): ...
    def list_records(self, accessor, accessor_context="", query=""): ...
    def canary_ids(self): ...                    # set of planted canary ids
```

Then wrap it in `MonitoredStore` — you don't re-implement the tripwire check; the watch layer does it for every read. Ships with `JsonFileAdapter` (zero-setup flat files) and `SqliteAdapter` (stdlib sqlite3, transactional).

A tripwire event carries: **record id**, **accessor identity**, **accessor context** (task, role, tool), **timestamp**, and **the query that touched it**.

## Tests

```bash
pytest -q
```

9 tests: clean agent trips nothing, snooping agent trips canaries, report carries record id + accessor context, JSON/SQLite adapter round-trips, deterministic generation, event serialization.

## License

MIT — see [LICENSE](LICENSE).

---

## Built by Ingenious AI

**agent-canary-data** is built by **Ingenious AI**. Explore the full platform suite:

- [DisclosureGuard](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20DisclosureGuard)
- [ModelMinder](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20ModelMinder)
- [TermsWatch](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20TermsWatch)
- [Vibe-Code Audit](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20Vibe-Code%20Audit)
- [Rogue-Agent Defense](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20Rogue-Agent%20Defense)
- [BreachHunter](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20BreachHunter)
- [ChatBreaker](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20ChatBreaker)
- [Agent Flight Recorder](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20Agent%20Flight%20Recorder)
- [Agent Auth Gateway](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20Agent%20Auth%20Gateway)
- [DomainGuard](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20DomainGuard)
- [ContentCraft AI](https://wa.me/5016691053?text=Hi%20Ingenious%20AI!%20I%20want%20early%20access%20to%20ContentCraft%20AI)


> Built by Ingenious AI
