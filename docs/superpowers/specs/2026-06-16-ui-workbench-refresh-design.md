# UI Workbench Refresh Design

## Goal
Refresh the WebUI around direction A: a modern workbench with a dark fixed sidebar, calm light content surface, denser operational controls, and a polished media wall for discovery. The UI should feel consistent across task list, configuration, Telegram settings, tables, modals, calendar, logs, and discovery.

## Visual Language
- Use a restrained admin palette: slate sidebar, white content panels, blue primary actions, teal accents, amber warning, rose danger.
- Keep cards and controls at 8-14px radius, with quiet borders and subtle shadows.
- Avoid decorative blobs and heavy gradients in ordinary panels. Use one strong dark hero only where it helps orientation.
- Use icons for compact actions and preserve existing Bootstrap Icons.

## Layout
- Desktop uses a fixed rounded sidebar and a single large work surface.
- Collapsed sidebar remains compact and usable.
- Mobile keeps the existing top navigation pattern, with improved spacing and control sizing.
- Content sections should look like a unified workbench, not nested random cards.

## Components
- Task dashboard: clearer header, compact metric blocks, tighter filters, more polished task rows.
- Forms: consistent input height, label treatment, focus state, grouped sections.
- Tables: calmer header, better row hover, consistent rounded container.
- Buttons: unified icon button sizing, primary/secondary/danger styles.
- Telegram and source panels: reduce visual bulk and align with the same panel system.
- Discovery: keep the large search/header area, improve poster grid spacing, overlay, ratings, and action buttons.
- Modals/toasts/logs: same radius, borders, and shadow language as the rest of the app.

## Acceptance Criteria
- The main pages no longer look like separate visual systems.
- TG notification UI does not look oversized or detached from surrounding settings.
- Discovery page feels like a real media wall and still supports search/create actions.
- No text overflow or obvious overlap at desktop width and mobile width.
- Version is bumped after implementation.
