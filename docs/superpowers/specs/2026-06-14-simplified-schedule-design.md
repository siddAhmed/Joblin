# Simplified Schedule UI Design

**Date:** 2026-06-14
**Branch:** feat/simplified-schedule
**Status:** Approved

## Problem

The schedule configuration UI exposes a raw cron expression text input (`0 */4 * * *`). Users have to know cron syntax to configure when scans run, and there is no timezone control - the VPS runs on GMT but users want to schedule in their local time (IST).

Additionally, after the multi-user Authentik integration, the scheduler was hardcoded to `user_id=1`, meaning only one user ever received scheduled runs regardless of how many users were logged in.

## Goals

- Replace the cron text input with preset chips and contextual fields
- Add timezone support so users schedule in their local time, not the server's
- Fix the scheduler to run per-user jobs so every user gets their own independent schedule

## Out of Scope

- Changing what the pipeline does
- Per-company scheduling
- Schedule history or audit log

---

## UI Design

### Preset Chips

The schedule tab shows a row of chip buttons. Selecting one reveals a contextual panel beneath it.

Presets: **Twice daily · Daily · Every 2 days · Every 3 days · Weekly · Custom**

### Contextual Panel Per Preset

| Preset | Shows |
|---|---|
| Twice daily | Time picker (runs at HH:MM and HH+12:MM) + timezone |
| Daily | Time picker + timezone |
| Every 2 days | Time picker + timezone |
| Every 3 days | Time picker + timezone |
| Weekly | Day-of-week picker (M T W T F S S) + time picker + timezone |
| Custom | Interval builder by default, toggle to raw cron |

### Time and Timezone Fields

- Time input: HH:MM (24-hour)
- Timezone: short dropdown of common zones

| Label | IANA key |
|---|---|
| IST (UTC+5:30) | Asia/Kolkata |
| UTC | UTC |
| GMT (UTC+0) | Europe/London |
| EST (UTC-5) | America/New_York |
| CST (UTC-6) | America/Chicago |
| PST (UTC-8) | America/Los_Angeles |
| CET (UTC+1) | Europe/Berlin |
| SGT (UTC+8) | Asia/Singapore |
| JST (UTC+9) | Asia/Tokyo |
| AEST (UTC+10) | Australia/Sydney |

Default timezone: **Asia/Kolkata (IST)**

A description line below the panel confirms the schedule in plain English: _"Runs once per day at 09:00 IST."_

### Custom Mode

When Custom is selected, the panel shows an interval builder:

> Every `[4]` `[hours ▾]`

Units available: hours, days. (Weeks are not cleanly expressible in cron and are excluded.)

When unit is **days**, a time picker and timezone dropdown also appear (same as the named presets). When unit is **hours**, no time picker is shown.

A "Switch to cron expression →" link toggles to a raw cron text input. A "← Back to interval builder" link toggles back.

### Staleness Threshold

The staleness threshold field (skip if last run was within N hours) remains visible on all presets. It already exists and does not need redesign.

### Enable Toggle

The "Scheduler enabled" checkbox remains at the bottom of the panel.

---

## Data Model

Settings are already per-user (the `Setting` model has a `user_id` FK). No schema changes needed. New setting keys are added alongside the existing ones.

### New Settings Keys

| Key | Type | Default | Purpose |
|---|---|---|---|
| `schedule_preset` | string | `"custom"` | Which chip is active |
| `schedule_time` | string | `"06:00"` | HH:MM for presets that use a time |
| `schedule_day_of_week` | int | `1` | 0=Sun ... 6=Sat, used by Weekly preset |
| `schedule_timezone` | string | `"Asia/Kolkata"` | IANA timezone string |
| `schedule_custom_mode` | string | `"cron"` | `"interval"` or `"cron"` |
| `schedule_interval_value` | int | `4` | Number for interval builder |
| `schedule_interval_unit` | string | `"hours"` | `"hours"` or `"days"` |

Existing keys unchanged: `schedule_cron`, `scheduler_enabled`, `staleness_threshold_hours`.

### Migration Behavior

Existing users have no `schedule_preset` key in the DB. The defaults resolve to `"custom"` / `"cron"` mode, which shows their existing `schedule_cron` value in the cron input. Nothing breaks and no data migration is needed.

---

## Preset to Cron Conversion

Conversion is done entirely in the frontend. On save, the frontend computes `schedule_cron` from the active preset and UI state, then sends all keys (UI state + computed cron) in one PATCH `/settings` request. The scheduler continues to read only `schedule_cron`.

| Preset | Cron formula | Example (09:00) |
|---|---|---|
| Twice daily | `MM HH,HH+12 * * *` | `0 9,21 * * *` |
| Daily | `MM HH * * *` | `0 9 * * *` |
| Every 2 days | `MM HH */2 * *` | `0 9 */2 * *` |
| Every 3 days | `MM HH */3 * *` | `0 9 */3 * *` |
| Weekly (Mon) | `MM HH * * D` | `0 9 * * 1` |
| Custom interval N hours | `0 */N * * *` | `0 */4 * * *` |
| Custom interval N days | `MM HH */N * *` | `0 9 */2 * *` |
| Custom cron | stored as-is | — |

HH+12 wraps at 24 (e.g. 22:00 → 22 and 10).

---

## Per-User Scheduler (Backend)

### Problem

`scheduler.py` hardcodes `user_id=1` everywhere. Only one user ever gets scheduled runs.

### Solution: Per-User APScheduler Jobs

Each user gets their own scheduled job with ID `scrape_cron_{user_id}`. Jobs are created, replaced, or removed independently per user.

### `start_scheduler` Changes

On app startup, `start_scheduler` queries all users and for each user:
1. Reads `scheduler_enabled`, `schedule_cron`, and `schedule_timezone` from their settings
2. If enabled: adds/replaces job `scrape_cron_{user_id}` with their cron + timezone
3. If disabled: skips (or removes existing job if present)

### `_run_scrape_job(user_id)` Changes

The job function takes `user_id` as a parameter. All hardcoded `user_id=1` references become `user_id`.

### Settings Save Hook

When a user saves schedule settings via `PATCH /settings`, the settings router calls a helper that adds/replaces/removes that user's APScheduler job based on the new values. This keeps the running scheduler in sync without requiring a restart.

The running `AsyncScheduler` instance is stored in `app.state.scheduler` (set during FastAPI lifespan startup) and accessed in the router via `request.app.state.scheduler`.

### `CronTrigger` Timezone

```python
CronTrigger(
    minute=minute, hour=hour, day=day, month=month,
    day_of_week=day_of_week,
    timezone=schedule_timezone,  # e.g. "Asia/Kolkata"
)
```

APScheduler interprets the cron expression in the given timezone, so a 09:00 IST schedule fires at 03:30 UTC regardless of the server's system clock.

---

## File Changes

| File | Change |
|---|---|
| `backend/config.py` | Add 7 new default setting keys |
| `backend/scheduler.py` | Accept `user_id` param, query all users on startup, pass timezone to CronTrigger |
| `backend/routers/settings.py` | Call schedule sync helper after PATCH |
| `frontend/src/pages/Settings.tsx` | Rewrite schedule tab with chip UI |
| `frontend/src/utils/scheduleUtils.ts` | New file: `presetToCron()` and related helpers |
| `frontend/src/api/settings.ts` | No changes needed |

---

## Testing Considerations

- `presetToCron()` is a pure function - unit test all preset/time combinations
- Scheduler tests: mock `get_all_users`, verify correct job IDs are created
- Timezone: verify `CronTrigger` receives the correct IANA string
- Settings router: verify schedule sync is called after PATCH with schedule keys
