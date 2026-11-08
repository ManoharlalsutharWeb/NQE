# NQ / Gold Event Desk — GitHub Pages edition

A static web dashboard for upcoming BLS/BEA macro events relevant to Nasdaq futures and Gold. GitHub Actions fetches official calendar feeds and publishes an updated static JSON/site; GitHub Pages serves the HTML/JS. No paid API, database server, or third-party Python package is used.

## Automatic vs. manual data

- Automatic: upcoming/very recent relevant events, event title/category, scheduled time, official source and sync status from BLS and BEA iCalendar schedules.
- Manual: market consensus, actual release value, prior revision, analyst reading and notes. Those values are saved only in the current browser's local storage; use the backup button to export them. They do not follow you to another device.
- Not included: live NQ/Gold prices, a paid consensus feed, automatic breaking-news monitoring or order execution.
- GitHub scheduled Actions can be delayed during high load, so this is not a guaranteed instant alert or real-time trading system.

## Publish on GitHub Pages

1. Create a **public** GitHub repository (for example, `nq-gold-event-desk`) and upload all files/folders in this ZIP to the repository's `main` branch. Public-repository publication makes the source and schedule data visible; do not add secrets or private notes.
2. In the repository go to **Settings → Pages → Build and deployment → Source** and choose **GitHub Actions**.
3. Open the **Actions** tab. The initial push should trigger the workflow. If it has not run, choose **Update calendar and publish site → Run workflow**.
4. After a successful Pages deployment, GitHub shows a site URL similar to `https://YOUR-USERNAME.github.io/YOUR-REPOSITORY/` in the Pages settings/deployment.
5. The workflow re-fetches official calendars on a six-hour schedule and can also be triggered manually from Actions. The schedule workflow file must remain on the default branch.

The first deployment needs internet access for the GitHub Actions runner. If a feed fetch fails, the workflow retains previously published events for that source and publishes an error status rather than silently replacing it with empty data.

## Privacy and safety

GitHub Pages is static hosting, not a Python backend. The public page and event schedule are visible to anyone with the URL. Personal consensus/actual/notes entered in the page are kept in that browser's local storage, not uploaded to the repository; clearing browser data can remove them, so export a backup. This is an educational scenario/journal tool, not financial advice or a live signal.

## Official calendar inputs

- BLS release calendar/ICS: https://www.bls.gov/schedule/news_release/
- BEA release schedule/ICS: https://www.bea.gov/news/schedule

## Tests

Run `python -m unittest discover -s tests -v` locally. GitHub Actions runs these tests before each deployment.
