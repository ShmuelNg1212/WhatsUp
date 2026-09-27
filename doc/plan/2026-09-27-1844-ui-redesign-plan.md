# Plan: UI/UX Redesign
- **Date:** 2026-09-27 18:44
- **Study:** [../study/2026-09-27-1844-ui-ux-overhaul.md](../study/2026-09-27-1844-ui-ux-overhaul.md)
- **Status:** in-progress

Boundary: **no changes** to any `models.py`, `views.py`, `urls.py`, `forms.py`, `admin.py`, or `config/settings/*`. New Python is limited to `templatetags/`. Test edits are limited to (a) markup → `data-testid` decoupling and (b) query-count constants +2.

## Tasks
- [ ] 1. **Decouple tests from markup.** Add `data-testid` hooks to the current `_post_card.html` (like button state and count), `_follow_button.html`, and the profile header follow control. Switch the ~6 markup-matching assertions to these hooks. → `test: decouple ui assertions from markup`
- [ ] 2. **Design system foundation.** Rewrite `base.html`: Inter font, `@theme` tokens (brand, sage), component layer (`.card`, `.btn*`, `.field`/`.input`, `.chip`, `.nav-link*`, `.table`), keeping the legacy class names working. Add `components/icon.html`, `avatar.html`, `button.html`, `badge.html`, `messages.html`, `empty_state.html`, and `accounts/templatetags/ui.py` (`avatar_tone`, `initials`). → `refactor(ui): establish design system and base components`
- [ ] 3. **Forms.** `components/form.html` + `components/form_field.html`. Replace every `form.as_p`. → `refactor(ui): add form field components`
- [ ] 4. **Public layout.** `layouts/public.html`. Redesign `landing.html`, `registration/login.html`, `accounts/signup.html`, and `403.html` (layout adapts to the viewer). Add `404.html`. → `refactor(ui): implement public layout and auth pages`
- [ ] 5. **Social layout.** `layouts/social.html` (sidebar, right rail, mobile top bar + bottom nav). `posts/templatetags/social_widgets.py` (`who_to_follow`, `trending_posts`) + widget partials. Query constants +2. → `refactor(ui): implement social layout and navigation`
- [ ] 6. **Feed and cards.** `posts/_composer.html`, `posts/_post_card.html`, `posts/_comment.html`, `ads/_ad_card.html` (same contract), `components/pagination.html`, `posts/feed.html`, `posts/detail.html`. → `refactor(ui): redesign post cards, ad cards and feed`
- [ ] 7. **Profiles and people.** `components/follow_button.html` (with `posts/_follow_button.html` kept as a wrapper), `posts/profile.html`, `posts/people.html`. → `refactor(ui): redesign profiles and people discovery`
- [ ] 8. **Portal layout.** `layouts/portal.html` (sidebar with campaign list via the existing context, top header, mobile `<details>` menu), `components/page_header.html`, `components/metric_card.html`. → `refactor(ui): implement advertiser portal layout`
- [ ] 9. **Portal pages.** `ads/dashboard.html` (+ `ads/_campaign_row.html`), `campaign_detail.html` (+ `ads/_ad_stats.html`), `campaign_form.html`, `adunit_form.html`, `components/confirm_delete.html` used by both delete pages, `ads/_state_badge.html` → badge. Delete the obsolete `partials/nav.html` and `posts/_pagination.html`. → `refactor(ui): redesign advertiser dashboard, campaigns and ad forms`
- [ ] 10. **Visual QA.** Headless-Chrome screenshots (390 px and 1440 px) of every key page for each role. Fix issues → `fix(ui): …` commits as needed.
- [ ] 11. **Verify.** Full suite green. `git diff <pre-overhaul>..HEAD --stat` shows no backend Python changes outside `templatetags/` and the tests. `check`. Live HTTP smoke test (pages 200, CSS classes present).

## Blocked On
Nothing.
