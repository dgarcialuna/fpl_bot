# FPL Bot

An unofficial Fantasy Premier League assistant. The goal is a Telegram bot that any manager can
use by sharing their public team ID, and that warns them **between** deadlines when something
changes: a player they should buy is about to rise in price, or one they own is out for the
season and about to fall.

> Unofficial project. Not affiliated with, endorsed by or connected to the Premier League or
> Fantasy Premier League.

## Status

Early. What exists today is the data layer that everything else depends on:

| Piece | State |
|---|---|
| Polite client for the public FPL API (spacing, backoff, `Retry-After`, caching) | done |
| SQLite history of prices, transfers and injury news (stores only changes) | done |
| `fpl-bot snapshot` collector, verified against the real API | done |
| Server install script (systemd service, daily backup) | done |
| Price-rise / price-fall estimator, calibrated on the collected history | planned |
| Long-term injury detection | planned |
| Telegram bot, multi-user (team ID, mini-leagues) | planned |
| LLM analyst + critic that can ask for a redo | planned |

**Start collecting early.** The price estimator is calibrated on history that cannot be
recovered afterwards, so the collector is the first thing worth running.

## Quick start

```bash
pip install -e ".[dev]"
pytest
fpl-bot snapshot --db data/fpl_bot.db                  # one sample
fpl-bot snapshot --db data/fpl_bot.db --loop           # every 30 min (minimum 5 min)
```

The database path can also come from `FPL_BOT_DB`.

## Running the collector on a server

On a fresh Ubuntu 24.04 server, as root:

```bash
curl -fsSL https://raw.githubusercontent.com/dgarcialuna/fpl_bot/main/deploy/install.sh | bash
```

This creates an unprivileged `fplbot` user, installs the code in `/opt/fpl-bot`, runs the
collector as a systemd service (a sample every 30 minutes, restarted automatically), schedules a
daily database backup (last 14 days kept in `/var/lib/fpl-bot/backups`), enables automatic
security updates and a firewall that only allows SSH. Running it again updates the code.
Read [`deploy/install.sh`](deploy/install.sh) before piping any script into a shell.

Check it with `systemctl status fpl-bot-snapshot` and
`sqlite3 /var/lib/fpl-bot/fpl_bot.db 'select count(*) from snapshots;'`.

## Design notes

- **One call serves everyone.** `bootstrap-static` returns every player, so the cost of the
  collector does not grow with the number of users.
- **Be polite to an undocumented API.** No rate limit is documented, so requests are spaced,
  retried with exponential backoff on 429/5xx and non-JSON replies, and `Retry-After` is honoured.
- **Store changes, not samples.** A player row is written only when something we track changed,
  which keeps a season of 30-minute sampling small.
- **Tolerant parsing.** Only the few fields that cannot be missing are required; optional ones
  become `None` instead of breaking the collector if the API shifts.
- **Core knows nothing about Telegram.** Channels will be adapters, so the same core can serve
  other front ends.

## Data and privacy

The collector stores public market data only. User-facing features will keep the minimum: a
Telegram chat ID, the public FPL team ID and preferences, with a command to delete everything.

## License

Licensed under the [Apache License 2.0](LICENSE). You may use, modify and redistribute this
software, including commercially, without asking permission. Redistributions must keep the
[NOTICE](NOTICE) file and the license text, which is how the original author is credited.
