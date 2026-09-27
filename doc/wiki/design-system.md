# Design System

The single source of truth for how WhatsUp looks. **New templates must use these tokens, components, and layouts** instead of inventing new styles. If something is missing, add it here and to `templates/base.html` or `templates/components/` first, then use it.

- **Where it lives:** `templates/base.html` holds the tokens (`@theme`) and the CSS component layer (`@layer components`). `templates/components/` holds reusable partials, and `templates/layouts/` holds the three page shells.
- **Tooling:** Tailwind CSS v4 **browser CDN** (compiles in the page). It's fine for development. **Before production:** switch to a compiled build (Node v24 is available). Move the `@theme` and `@layer components` blocks unchanged into `input.css` and run the Tailwind CLI to produce a static stylesheet.
- **No JavaScript.** Every interaction is a link or a form POST. Menus use native `<details>/<summary>`.
- Background: the [UI/UX overhaul study](../study/2026-09-27-1844-ui-ux-overhaul.md).

---

## 1. Principles
1. **Calm and minimal.** Lots of whitespace, one accent color, soft shadows, rounded corners.
2. **One vibrant color.** Brand pink is for **primary actions, the active state, likes, and focus**. Don't use it for decoration or body text.
3. **Neutrals are sage.** Every gray is from the sage ramp (never Tailwind `slate`/`gray`), so the UI has one warm undertone.
4. **Readable first.** Body text is `sage-900`, secondary text is `sage-700` (≥ 4.5:1). `sage-600` is only for large or decorative text and placeholders.
5. **Sponsored content is always labelled** with the Tea Green Sponsored pill and must mirror the organic post card.

## 2. Tokens (`@theme` in `base.html`)

### Color: brand (the one vibrant accent, from the mockups)
| Token | Hex | Use |
|---|---|---|
| `brand-50` | `#FDF2F7` | Active nav background, subtle highlights |
| `brand-100`/`200` | `#FCE4EF` / `#F9C9DE` | Avatar tone, atmosphere blobs |
| `brand-500` | `#E0266F` | Icons and accents only (**4.49:1**, below AA for text) |
| **`brand-600`** | **`#D91F68`** | **Primary buttons, links (white text 4.83:1 ✓)** |
| `brand-700` | `#BE1A5A` | Hover, active-nav text, `.link` |
| `brand-800`/`900` | `#9C184C` / `#821944` | Rare: pressed or dark text on a brand tint |

### Color: sage (neutrals, from the palette `DEF2C8 · C5DAC1 · BCD0C7 · A9B2AC · 898980`)
| Token | Hex | Use |
|---|---|---|
| `sage-50` | `#F6F9F3` | **Page background**, table headers, subtle fills |
| `sage-100` | `#EEF4E8` | Hover fills, avatar or icon chips |
| `sage-200` | `#DEF2C8` *(Tea Green)* | **Sponsored pill**, sponsor avatar, success tints |
| `sage-300` | `#C5DAC1` *(Tea Green)* | **Borders and rings** (often `/50`), input rings |
| `sage-400` | `#BCD0C7` *(Ash Grey)* | Dashed empty-state borders |
| `sage-500` | `#A9B2AC` *(Ash Grey)* | Decorative only |
| `sage-600` | `#898980` *(Grey Olive)* | Placeholders, large or decorative text (3.53:1) |
| `sage-700` | `#5E625C` | **Secondary text** (6.2:1) |
| `sage-800` | `#3C403B` | Strong secondary text |
| `sage-900` | `#232622` | **Body text and headings** (15.3:1) |

### Status colors (Tailwind defaults, used only through `components/badge.html` and messages)
`emerald` = live/success · `sky` = scheduled/info · `amber` = inactive/warning · `red` = errors/destructive.

### Type, radius, shadow
| Token / convention | Value |
|---|---|
| Font | `--font-sans`: **Inter** 400/500/600/700 (Google Fonts), falling back to system-ui |
| Page title | `text-2xl font-bold tracking-tight` (landing hero: `text-4xl…6xl`) |
| Section title | `text-lg font-semibold` |
| Body | `text-[15px] leading-relaxed` in cards, `text-sm` in UI chrome |
| Meta / help | `text-xs text-sage-700` · eyebrow: `.eyebrow` |
| Radius | Cards `rounded-2xl` · controls `rounded-xl` · small buttons `rounded-lg` · pills and avatars `rounded-full` |
| Shadow | `shadow-card` (resting), `shadow-card-hover` (with `.card-hover`) |
| Spacing | Card padding `p-4 sm:p-5` (feed) or `p-6 sm:p-8` (forms) · stack gap `space-y-4` (feed), `gap-4` (grids), `mt-8`–`mt-10` between sections |

## 3. CSS component classes (`@layer components`)
| Class | What it is |
|---|---|
| `.card` | White surface, `rounded-2xl`, sage border, `shadow-card`. **Every panel is a card.** |
| `.card-hover` | Adds a hover lift (clickable cards, e.g. People) |
| `.btn` + `.btn-primary` / `.btn-secondary` / `.btn-ghost` / `.btn-danger` | Buttons. Add `.btn-sm` for compact. Prefer `components/button.html`. |
| `.input` | Standalone input (e.g. the inline comment box) |
| `.field` (wrapper) | Styles any `input`/`select`/`textarea`/file input inside it. `.field-invalid` adds the red ring. `.field-label`, `.field-help`, `.field-error`. |
| `.chip` | Small outlined pill (landing tagline) |
| `.nav-link` / `.nav-link-active` | Sidebar and menu items |
| `.table` | Data table (sage header, row hover) |
| `.link` | Inline text link (brand-700) |
| `.eyebrow` | Tiny uppercase label |

## 4. Components (`templates/components/`)
Include small components with `only` so page variables can't leak in: `{% include "components/x.html" with … only %}`. Components that render a **form** (follow button) need `request`/`csrf_token`, so they're included **without** `only`.

| Component | Parameters | Notes |
|---|---|---|
| `icon.html` | `name`, `cls` (default `h-5 w-5`), `solid` | Inline Heroicons (outline). Names: building, calendar, chart, chat, check, check-circle, chevron-down/left/right, cursor, dollar, exclamation-circle, external, eye, fire, heart, home, info, link, logout, megaphone, menu, pencil, photo, plus, search, send, shield, sparkles, squares, trash, user, users, x. **Add new icons here**, not inline. |
| `avatar.html` | `user`, `size` (`xs` `sm` md `lg` `xl`) | Initials on a stable tone (`ui` filters `initials`, `avatar_tone`). There's no image upload. |
| `button.html` | `label`, `variant`, `href` or `type`, `icon`, `size`, `full`, `extra`, `testid` | Renders `<a>` when `href` is set, otherwise `<button>` |
| `badge.html` | `label`, `tone` (brand/sage/green/sky/amber/red/slate), `dot`, `state`, `testid` | Status pills |
| `form.html` | `form` | Non-field errors, hidden fields, then `form_field` for each field. **Always use this instead of `form.as_p`.** |
| `form_field.html` | `field` | Label (+ "(optional)"), widget, help (HTML allowed, lists styled), errors, `field-invalid` state |
| `messages.html` | — | Flash messages. Included once by every layout. |
| `empty_state.html` | `title`, `text`, `icon`, `action_label`, `action_href`, `action_icon`, `testid` | Dashed placeholder with an optional CTA |
| `page_header.html` | `title`, `subtitle`, `back_href`, `back_label` | App page headings. Put actions beside it in a flex row. |
| `metric_card.html` | `label`, `value`, `prefix`, `icon`, `tone`, `hint`, `small`, `testid` | KPI tiles (portal) |
| `pagination.html` | `page_obj` | Newer/Older |
| `follow_button.html` | `target`, `following`, `size`, `testid` | POST toggle (`posts/_follow_button.html` is a legacy wrapper) |
| `logo.html` | `href`, `compact` | Brand mark + wordmark |

App partials: `posts/_post_card.html`, `posts/_comment.html`, `posts/_composer.html`, `posts/_feed_item.html`, `posts/widgets/*`, `ads/_ad_card.html`, `ads/_ad_stats.html`, `ads/_campaign_row.html`, `ads/_state_badge.html`, `ads/_confirm_delete_base.html` (extend it; blocks `confirm_title`, `confirm_body`, `cancel_url`).

### Card anatomy (post and ad must stay in step)
```
card p-4 sm:p-5
├─ header: avatar (40px) · name (font-semibold) + @handle/domain (text-sage-700) · [ad only: SPONSORED pill]
├─ body: text-[15px] leading-relaxed (ad: headline text-base font-semibold first)
├─ media: rounded-xl, max-h-[32rem], object-cover, lazy
└─ footer: post → ghost icon buttons (heart/chat/link) · ad → "Learn more ↗" bar (bg-sage-50)
```
The ad card adds `ring-1 ring-sage-200` and the **Sponsored** pill: `bg-sage-200 text-sage-800`, uppercase `text-[11px]`, sparkles icon, `data-testid="sponsored-tag"`. **Never remove or restyle the pill to look organic.**

## 5. Layouts (`templates/layouts/`)
Every page extends exactly one layout. **Never extend `base.html` directly.**

| Layout | Audience | Structure | Blocks |
|---|---|---|---|
| `public.html` | Visitors (landing, login, signup) | Top bar (logo · Log in · Sign up), soft pink/sage/violet blurred atmosphere, centered `main` | `content`, `container_class` (e.g. `max-w-md` for auth) |
| `social.html` | `REGULAR_USER` | **≥ xl:** sidebar (w-60) · main (max-w-2xl) · right rail (w-80: *Who to follow*, *Trending*). **lg:** sidebar · main. **< lg:** sticky top bar (logo · title · avatar menu) · main (`pb-28`) · **fixed bottom nav** (Feed · People · ＋Post → `/feed/#compose` · Profile). | `page_title` (mobile bar), `content`, `right_rail` |
| `portal.html` | `ADVERTISER` | **≥ lg:** fixed sidebar (w-64: Dashboard, New campaign, current campaign; company note) · sticky top header (page title · company/account menu) · content (max-w-6xl). **< lg:** header only; nav moves into the account `<details>` menu (`layouts/_portal_nav.html`). | `page_title`, `content` |

- **Active nav** is derived from `request.resolver_match.view_name`, with no view changes needed.
- **Error pages** (`403.html`, `404.html`) are wrappers. `{% load ui %}` picks the viewer's layout with `user|error_layout`, then includes `errors/40x_page.html`, which does `{% extends layout %}`.
- **Breakpoints:** `sm` 640 (forms go 2-up), `md` 768 (ad preview grid 2-up), **`lg` 1024 (sidebars appear, bottom nav disappears)**, **`xl` 1280 (right rail appears)**.
- **Wide tables** go inside `card overflow-hidden > div.overflow-x-auto > table.table.min-w-[42rem]`, so they scroll sideways on phones.

## 6. Template tags (UI-only Python)
| Library | Provides | Queries |
|---|---|---|
| `{% load ui %}` (`accounts/templatetags/ui.py`) | `avatar_tone`, `initials`, `domain` (URL → host), `error_layout` | 0 |
| `{% load social_widgets %}` (`posts/templatetags/social_widgets.py`) | `{% who_to_follow %}` (3 regular users you don't follow, by follower count) and `{% trending_posts %}` (top 3 most-liked posts of the last 7 days) | 1 each, LIMIT 3 |

The right rail adds a **constant 2 queries** to every social page, and they're included in the pinned counts. **After adding a new `templatetags` module, restart `runserver`**: Django registers tag libraries at startup, so the dev server otherwise returns 500 ("… is not a registered tag library").

## 7. Rules for new UI
1. Extend a layout. Put the page title in `page_title` (social/portal) and use `components/page_header.html` in the content.
2. Wrap every panel in `.card`. Use `components/empty_state.html` for "nothing here".
3. Forms: `{% include "components/form.html" %}` (or `form_field.html` per field for custom grids), then `components/button.html` for submit and cancel. Put `novalidate` on portal forms so server errors show in the design.
4. Buttons: exactly **one** `primary` per view region. Use `secondary`/`ghost` for the rest, and `danger` only on confirmation screens.
5. Colors: brand for action and active states, sage for everything else, status colors only through `badge`/messages. **No `slate`/`gray`/`indigo`.**
6. Icons: `components/icon.html` only. Decorative icons are `aria-hidden` (built in). Icon-only buttons need `aria-label`.
7. Give dynamic values that tests assert a `data-testid`, and keep existing ones: `like-button`/`data-liked`, `like-count`, `follow-button`/`profile-follow-button`/`data-following`, `post-count`, `follower-count`, `following-count`, `sponsored-tag`, `campaign-count`, `live-count`, `total-budget`, `ad-count`, `impressions`, `clicks`, `ctr`, `data-state`.
8. Check every page at **390 px and 1440 px** before shipping (Chrome device toolbar).
