# Features

## Accounts
- Sign up as a **regular user** (username, email, password) or as an **advertiser** (plus company name and optional website).
- Log in and log out. After login, each role lands in its own area.
- Emails are unique regardless of case. Passwords go through Django's standard validators.

## Regular users: the social area
- **Feed** (`/feed/`): your own posts plus posts from people you follow, newest first, 20 per page. Each post shows its like count, comment count, and latest 3 comments.
- **Posting:** write a post (up to 2,000 characters) with an optional image (up to 5 MB) from the top of the feed.
- **Likes:** one click to like, another click to unlike. A user can like a post at most once, and can like their own posts.
- **Comments:** reply from any post card (up to 1,000 characters). Open a post (click its timestamp or "View all N comments") to see every comment.
- **Profiles** (`/u/<username>/`): a user's posts, post count, follower and following counts, and a Follow/Unfollow button. Your own profile shows "This is you".
- **People** (`/people/`): every other regular user, with their counts and a Follow/Unfollow button.
- **Following** is one-way. It needs no approval, and there is no automatic follow-back. You can't follow yourself.
- All profiles and posts are visible to every logged-in regular user. There are no private accounts or blocking yet.
- Posts and comments can't be edited or deleted yet, except by an admin.

## Advertisers: the portal (`/ads/`)
- **Dashboard:** company details, stats (number of campaigns, live now, total budget), and a table of *your* campaigns with status badge, dates, budget, and number of ads.
- **Campaigns:** create, view, edit, and delete (with a confirmation page). Fields: name (unique among your campaigns), total budget in USD, start and end dates, and Active/Inactive status (new campaigns start Inactive). A new campaign can't start in the past, and the end date can't be before the start date.
- **Status badges:** Live (active and within its dates), Scheduled (active, starts later), Ended (active, past its end date), Inactive.
- **Ad units** inside each campaign: create, edit, and delete. Fields: headline (≤ 90 characters), body text (≤ 300), optional image (≤ 5 MB), and a target URL (http/https; `https://` is added if you leave it out).
- **Previews:** every ad is shown exactly as it will look in the feed, with a "Sponsored" label and a "Learn more" button.
- **Privacy:** advertisers only ever see their own campaigns and ads. Other advertisers' records show as "Not Found".
- Budgets are **not charged yet**, and ads **don't appear in feeds yet** (next slice).
- Advertisers still can't use the social area (403), have no profile page, and can't be followed.

## Admin (`/admin/`)
- Users (filter by role), follows, advertiser profiles, campaigns (with ad units inline, filter by status), ad units, posts (with comments inline), likes, and comments.
