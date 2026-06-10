# TMDB Auto Season Naming Design

## Goal
When a task uses episode naming like `Show - S01E[]`, automatically use TMDB season metadata during transfer so the saved filename season matches the task's matched season.

## Design
The transfer script will resolve a task's effective season before building episode filenames. It first trusts existing task metadata (`matched_latest_season_number` and `calendar_info.match.latest_season_number`) because the web app already stores manual corrections there. If no season is present and a TMDB API key is configured, it searches TMDB by the cleaned task title and selects the latest aired normal season. If season resolution fails, the original naming pattern is kept.

## Scope
- Only affects tasks with `use_episode_naming` enabled and an `episode_naming` pattern containing `SxxE[]`.
- Does not change normal regex naming or sequence naming.
- Does not block transfer on TMDB network failures.
- Logs the automatic rewrite when the season changes.

