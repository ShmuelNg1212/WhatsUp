# Study: Advertiser Portal & Campaign Creation (Slice 3)
- **Date:** 2026-09-27 17:52
- **Request:** Build the advertiser-only workspace. Advertisers manage **Campaigns** (name, total budget, start/end dates, active/inactive status), which belong strictly to the advertiser who created them. Inside each campaign they create **Ad Units** (headline, body, optional image, target URL). Full create/read/update/delete for both. Regular users must be refused (403 or redirect). Serving ads in the feed is a later slice.

## Intended Outcome
An advertiser can log in and:
- See a dashboard listing **their own** campaigns (status, dates, budget, number of ads).
- Create a campaign, edit it, and delete it after a confirmation step.
- Open a campaign and see its parameters plus its ad units, each **previewed as it will look in the feed**.
- Create, edit, and delete ad units within a campaign, with an optional image.

No one else can see or change those campaigns and ads: not regular users, not anonymous visitors, and **not other advertisers**.

**Acceptance criteria**
- [ ] Every portal route: anonymous → login redirect, regular user → **403**, advertiser → allowed.
- [ ] Advertiser B opening, editing, or deleting advertiser A's campaign or ad unit by ID gets **404** and nothing changes.
- [ ] Posting a different owner or campaign in form data is ignored (no mass-assignment).
- [ ] Invalid business data is rejected with clear messages: budget ≤ 0, end date before start date, a start date in the past on a new campaign, a non-http(s) target URL, or an image over 5 MB.
- [ ] Deleting a campaign deletes its ad units, after a confirmation page that says so.
- [ ] Dashboard and campaign pages run a fixed number of SQL queries.
- [ ] The full test suite passes.

## Current State
See [wiki/architecture.md](../wiki/architecture.md) and [wiki/data-models.md](../wiki/data-models.md).
- `ads` app: `AdvertiserProfile` (OneToOne → User) and a `dashboard` function view at `/ads/`, gated with `@role_required(ADVERTISER)`.
- Role gating (`accounts/permissions.py`) already covers **who is logged in and their role**. It does **not** check **which records a user owns**, and that is the new security problem in this slice.
- Media uploads are configured (Slice 2): Pillow, `MEDIA_ROOT`, dev serving, and a 5 MB validator pattern in `posts/forms.py`.

## Data Relationship Analysis

### What a Campaign belongs to
| Option | Pros | Cons |
|---|---|---|
| **A. `Campaign.advertiser` FK → `User`** | Ownership checks compare directly with `request.user` (`advertiser=request.user`) with no join. Works even if a profile is missing, which can happen when an account is made in the admin. Matches the request's wording ("tied to the specific advertiser who created them"). | If several staff at one company later share campaigns ("team seats"), ownership has to move to a company or organization model, which means a data migration |
| B. `Campaign.advertiser` FK → `AdvertiserProfile` | Campaigns hang off the business entity, which suits future billing and teams | Every ownership check needs a join or a profile lookup. Profile-less advertisers can't create campaigns. Owner scoping becomes indirect (`advertiser__user=request.user`), which is easier to get wrong. |

**Recommendation: A.** It is the simplest and most direct ownership rule, and security code should be boring. `limit_choices_to={"role": ADVERTISER}` protects the admin, and `Campaign.clean()` rejects non-advertiser owners. Team accounts are a known future migration, noted below.

### Campaign → AdUnit
One-to-many via `AdUnit.campaign` FK, with **CASCADE** delete. An ad unit's owner is **derived** as `ad_unit.campaign.advertiser` and is never stored twice. A duplicate `advertiser` column on `AdUnit` could drift out of step with the campaign, and a mismatch would be a security bug.

```
User (ADVERTISER) 1 ──── * Campaign 1 ──── * AdUnit
        │
        └─ 0..1 AdvertiserProfile (company details, unchanged)
```

### Campaign fields
| Field | Type | Rules |
|---|---|---|
| `advertiser` | FK → User, CASCADE, `related_name="campaigns"` | Set from `request.user` only. Never a form field. |
| `name` | CharField(120) | Required. **Unique per advertiser**: two advertisers may both have a "Summer Sale", but one advertiser can't have two. |
| `budget` | DecimalField(12, 2) | **> 0**, enforced by a DB CHECK and a form min value. Decimal, never float, because it is money. Currency is **USD** (assumption). |
| `start_date`, `end_date` | DateField | DB CHECK **end ≥ start**. The form also rejects a **past start date when creating**, but allows it when editing, since a running campaign's start date is naturally in the past. |
| `status` | TextChoices `ACTIVE` / `INACTIVE`, default **`INACTIVE`** | DB CHECK on the allowed values. The default is inactive so nothing will serve until the advertiser deliberately switches it on. A text field rather than a boolean leaves room to add `DRAFT`, `ENDED`, and so on without a schema change. |
| `created_at`, `updated_at` | auto | |

A computed property, `is_live`, is true when status = ACTIVE **and** start ≤ today ≤ end. The feed-injection slice will use it (as a queryset filter) to decide what can be served. The portal shows it as a badge: *Live / Scheduled / Ended / Inactive*.

### AdUnit fields
| Field | Type | Rules |
|---|---|---|
| `campaign` | FK → Campaign, CASCADE, `related_name="ad_units"` | Taken from the URL after checking ownership. Never a form field. |
| `headline` | CharField(90) | Required, not empty (DB CHECK) |
| `body` | TextField, max **300** characters (model validator) | Required. Short, like typical native ad copy. |
| `image` | ImageField, `upload_to="ads/%Y/%m/"` | Optional. Pillow checks it is really an image. Max 5 MB, reusing the Slice 2 limit. |
| `target_url` | URLField(500) | Required. **Only `http` / `https` are allowed**, because Django's default `URLValidator` also accepts `ftp`/`ftps`, and this link will be shown to users. |
| `created_at`, `updated_at` | auto | |

Index `(campaign, created_at)` serves listing units in a campaign.

## Permission Enforcement: the most secure approach

Access has two layers, and both must hold on **every** view:

1. **Role (authentication and authorization):** is this a logged-in `ADVERTISER`? Already solved by `RoleRequiredMixin`.
2. **Object ownership (preventing IDOR):** does *this* record belong to *this* advertiser? IDOR ("insecure direct object reference") means reaching someone else's record by changing an ID in the URL. This is the new risk.

### Options for ownership
| Option | How | Verdict |
|---|---|---|
| a. Check after fetching: `obj = get_object_or_404(Campaign, pk=pk); if obj.advertiser != request.user: raise PermissionDenied` | An explicit check in every view | **Rejected.** It's easy to forget in one view out of eight. Returning 403 on someone else's ID also reveals that the ID exists. |
| b. Django's object permissions (`has_perm(obj)` with a custom backend or django-guardian) | Per-object permission rows | **Rejected.** Adds a dependency and a table of permission rows for something that ownership already expresses. Overkill. |
| **c. Queryset scoping in one mixin** | Every portal view gets objects **only** from `Campaign.objects.filter(advertiser=request.user)` (and `AdUnit.objects.filter(campaign__advertiser=request.user, campaign_id=<url>)`). Django's generic views call `get_queryset()` → `get_object()`, so an ID outside that queryset is simply **404**. | **Chosen.** This is Django's standard pattern for generic views. Unowned records are never loaded, so there is nothing to forget to check afterwards. The 404 reveals nothing. |

### The design
```python
class AdvertiserRequiredMixin(RoleRequiredMixin):           # layer 1
    allowed_roles = (User.Role.ADVERTISER,)

class OwnedCampaignMixin(AdvertiserRequiredMixin):          # layer 2
    def get_queryset(self):
        return Campaign.objects.filter(advertiser=self.request.user)

class OwnedAdUnitMixin(AdvertiserRequiredMixin):            # layer 2 (nested)
    def get_campaign(self):   # parent from URL, scoped to owner → 404 otherwise
        return get_object_or_404(Campaign, pk=self.kwargs["campaign_pk"], advertiser=self.request.user)
    def get_queryset(self):
        return AdUnit.objects.filter(campaign=self.get_campaign())
```
The role check sits in `dispatch()`, which runs **before** any query. The ownership filter sits in `get_queryset()`, which every generic view uses to fetch records.

**Other safeguards:**
- **No mass-assignment:** `advertiser` and `campaign` are **never** form fields. They are set on the server in `form_valid()` from `request.user` or from the ownership-checked parent. `ModelForm.Meta.fields` lists fields explicitly; `__all__` is never used.
- **Nested URLs are checked as a pair:** `/ads/campaigns/<campaign_pk>/units/<pk>/` requires the unit to belong to **that** campaign **and** the campaign to belong to the requester. Pairing A's campaign ID with B's unit ID returns 404.
- **Deletion:** Django's `DeleteView`. GET shows a confirmation page, and only POST (with a CSRF token) deletes. The confirmation page warns that deleting a campaign also deletes its N ad units.
- **Wrong role:** **403**, consistent with Slices 1–2 (the request allowed 403 or redirect).
- **Another advertiser's records:** **404**, deliberately. It doesn't reveal that the record exists.
- **Tests** cover the full matrix of `{anonymous, regular user, other advertiser, owner} × {every route} × {GET, POST}`, and check that **nothing changed in the database** after each refusal.

## CRUD with Django generic views
Use Django's defaults: `CreateView`, `DetailView`, `UpdateView`, `DeleteView`, and `ListView`-style rendering on the dashboard. Success messages come from `SuccessMessageMixin`.

| Route | View | Purpose |
|---|---|---|
| `/ads/` | `DashboardView` | Company info + **my campaigns** table (status badge, dates, budget, ad count) |
| `/ads/campaigns/new/` | `CampaignCreateView` | Create |
| `/ads/campaigns/<pk>/` | `CampaignDetailView` | Read: parameters + ad unit previews |
| `/ads/campaigns/<pk>/edit/` | `CampaignUpdateView` | Update |
| `/ads/campaigns/<pk>/delete/` | `CampaignDeleteView` | Confirm (GET) / delete (POST) |
| `/ads/campaigns/<campaign_pk>/units/new/` | `AdUnitCreateView` | Create |
| `/ads/campaigns/<campaign_pk>/units/<pk>/edit/` | `AdUnitUpdateView` | Update |
| `/ads/campaigns/<campaign_pk>/units/<pk>/delete/` | `AdUnitDeleteView` | Confirm / delete |

An ad unit is "read" as a **preview card** on its campaign's page. There is no separate page per ad unit, because a unit has no meaning outside its campaign. The preview uses a reusable partial, `ads/_ad_card.html`, styled like a feed post with a "Sponsored" label. **Slice 4 will reuse this same partial to show ads in the feed**, so what the advertiser previews is exactly what users will see.

**Queries:** the dashboard annotates `Count("ad_units")` in one query. The campaign detail page loads the campaign plus one query for its units. Both are pinned with query-count tests, as in Slice 2.

## Exogenous Inputs
| Input | Why needed | Status | Owner |
|---|---|---|---|
| None new | Budgets are stored numbers only. No money moves in this slice. | — | — |
| Payment processor (e.g. Stripe) | Charging the budget | **Needed before real ad spend** (already listed) | Gardener |
| Production media storage | Ad images outside DEBUG | Already listed | Gardener |

Nothing blocks this slice.

## Risks & Open Questions
**Product defaults assumed** (flagged at Rendezvous):
1. **The budget is a stored figure in USD, and no money is charged.** Spend tracking and billing come with the payment and ad-serving slices.
2. **New campaigns start as INACTIVE.** The advertiser flips them to Active.
3. **A new campaign can't start in the past.** An existing campaign's start date can stay in the past when editing.
4. **Ad copy limits:** headline 90 characters, body 300 characters, image 5 MB. The target URL must be http or https.
5. **Deleting is permanent,** with no archive or undo. Deleting a campaign removes its ad units.
6. **No review or approval** of ads before they would serve.

**Technical risks**
- Ownership is per user. **Team accounts** (several logins per company) would need an organization model and a migration from `Campaign.advertiser`.
- Deleted ad units leave their image files behind, the same known gap as posts. One cleanup fix can cover both later.
- Once ads serve (Slice 4), editing a live ad changes it immediately. Versioning or review may be wanted then.
