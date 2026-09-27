# Plan: UI/UX Redesign
- **Date:** 2026-09-27 18:44
- **Study:** [../study/2026-09-27-1844-ui-ux-overhaul.md](../study/2026-09-27-1844-ui-ux-overhaul.md)
- **Status:** awaiting-rendezvous

Boundary: **no changes** to any `models.py`, `views.py`, `urls.py`, `forms.py`, `admin.py`, or `config/settings/*`. New Python is limited to `templatetags/`. Test edits are limited to (a) markup → `data-testid` decoupling and (b) query-count constants +2.

## Tasks
- [x] 1. **Decouple tests from markup.** Add `data-testid` hooks to the current `_post_card.html` (like button state and count), `_follow_button.html`, and the profile header follow control. Switch the ~6 markup-matching assertions to these hooks. → `test: decouple ui assertions from markup`
- [x] 2. **Design system foundation.** Rewrite `base.html`: Inter font, `@theme` tokens (brand, sage), component layer (`.card`, `.btn*`, `.field`/`.input`, `.chip`, `.nav-link*`, `.table`), keeping the legacy class names working. Add `components/icon.html`, `avatar.html`, `button.html`, `badge.html`, `messages.html`, `empty_state.html`, and `accounts/templatetags/ui.py` (`avatar_tone`, `initials`). → `refactor(ui): establish design system and base components`
- [x] 3. **Forms.** `components/form.html` + `components/form_field.html`. Replace every `form.as_p`. → `refactor(ui): add form field components`
- [x] 4. **Public layout.** `layouts/public.html`. Redesign `landing.html`, `registration/login.html`, `accounts/signup.html`, and `403.html` (layout adapts to the viewer). Add `404.html`. → `refactor(ui): implement public layout and auth pages`
  - _Adjustment (task 8):_ 403/404 pick their layout from the viewer's role via a `ui|error_layout` filter: public for visitors, social for regular users, portal for advertisers. `{% extends %}` must be the first tag, so `403.html`/`404.html` are thin wrappers that include `errors/40x_page.html`, which extends the chosen layout.
- [x] 5. **Social layout.** `layouts/social.html` (sidebar, right rail, mobile top bar + bottom nav). `posts/templatetags/social_widgets.py` (`who_to_follow`, `trending_posts`) + widget partials. Query constants +2. → `refactor(ui): implement social layout and navigation`
- [x] 6. **Feed and cards.** `posts/_composer.html`, `posts/_post_card.html`, `posts/_comment.html`, `ads/_ad_card.html` (same contract), `components/pagination.html`, `posts/feed.html`, `posts/detail.html`. → `refactor(ui): redesign post cards, ad cards and feed`
- [x] 7. **Profiles and people.** `components/follow_button.html` (with `posts/_follow_button.html` kept as a wrapper), `posts/profile.html`, `posts/people.html`. → `refactor(ui): redesign profiles and people discovery`
- [x] 8. **Portal layout.** `layouts/portal.html` (sidebar with campaign list via the existing context, top header, mobile `<details>` menu), `components/page_header.html`, `components/metric_card.html`. → `refactor(ui): implement advertiser portal layout`
- [x] 9. **Portal pages.** `ads/dashboard.html` (+ `ads/_campaign_row.html`), `campaign_detail.html` (+ `ads/_ad_stats.html`), `campaign_form.html`, `adunit_form.html`, `components/confirm_delete.html` used by both delete pages, `ads/_state_badge.html` → badge. Delete the obsolete `partials/nav.html` and `posts/_pagination.html`.
  - _Adjustments:_ the delete pages share an **extendable** base, `ads/_confirm_delete_base.html` (blocks work better than include parameters for rich messages). `posts/_pagination.html` was removed in task 6, when the feed moved to `components/pagination.html`. The legacy `.form-stack` CSS and the fallback shell in `base.html` were removed once no page used them. → `refactor(ui): redesign advertiser dashboard, campaigns and ad forms`
- [x] 10. **Visual QA.** Headless-Chrome screenshots (390 px and 1440 px) of every key page for each role. Fix issues → `fix(ui): …` commits as needed.
- [x] 11. **Verify.** Full suite green. `git diff <pre-overhaul>..HEAD --stat` shows no backend Python changes outside `templatetags/` and the tests. `check`. Live HTTP smoke test (pages 200, CSS classes present).

## Verification results
- **288/288 tests pass.** `check` is clean and `makemigrations --check` shows no changes.
- **Boundary:** `git diff 7b155fc..HEAD` touches no `models/views/urls/forms/admin/settings/migrations`. New Python is only `accounts/templatetags/ui.py` (avatar tone, initials, domain, error_layout) and `posts/templatetags/social_widgets.py`. Test edits: the 5 markup assertions → `data-testid` (commit `test: decouple ui assertions from markup`), and the query constants +2 for the right rail (feed 8, profile 9, detail 6, people 6; with ads 7/8/10).
- **Visual QA** (headless Chrome, 390 px and 1440 px, scratch harness with seeded data): landing, login, signup (both), signup errors, feed (+ ad injection, tall), empty feed, post detail, profile (other/own), people, 403 in the social layout, dashboard, campaign detail (tall), campaign form + errors, ad form, delete confirmation.
  - **Found and fixed:** error outlines didn't show on invalid fields (CSS specificity) → `fix(ui): …`. On mobile the composer's file input truncated to "N…n", so it moved to its own row.
  - Harness note: headless Chrome has a ~500 px minimum window, so phones are emulated with a 390 px iframe.
- **Live dev server:** every page is 200 for its role and 403 for the other role, each inside the correct layout. **Adding new template-tag libraries requires restarting `runserver`**: the first live pass returned 500 ("'ui' is not a registered tag library") until a restart. Probe impressions were removed.

## Blocked On
Nothing.
