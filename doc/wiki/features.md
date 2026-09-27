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

## Advertisers
- `/ads/`: dashboard showing company details. Campaigns are not built yet.
- Advertisers can't use the social area (403), have no profile page, and can't be followed.

## Admin (`/admin/`)
- Users (filter by role), follows, advertiser profiles, posts (with comments inline), likes, and comments.
