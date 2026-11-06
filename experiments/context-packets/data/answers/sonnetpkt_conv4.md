It's the timezone thing you mentioned earlier. This isn't flaky at all, it's deterministic, and none of the earlier mock/await stuff has anything to do with it.

`toLocaleString()` with no `timeZone` option renders in whatever zone the process is running in:

- **Your laptop (US Central, CDT = UTC-5):** `2026-11-01T03:30:00Z` → **Oct 31, 10:30 PM**
- **CI (`TZ=UTC` in the workflow env):** same instant → **Nov 1, 3:30 AM**

Those are exactly your Expected and Received. Priya's expected string was produced on a Central-time machine (hers or yours), so the test passes for anyone in Central and fails anywhere else, every time. And she picked a timestamp that crosses midnight, so the zone even changes the *day*, which is why it looks so wrong. (DST ending Nov 1 doesn't matter here, it's still CDT at 03:30Z.)

**Fix: make the test independent of the machine's timezone.** Two ways to do it:

1. **Pin the zone where the date gets formatted** (best if the component should show a specific zone):
   ```ts
   date.toLocaleString('en-US', { timeZone: 'America/Chicago', dateStyle: 'medium', timeStyle: 'short' })
   ```
   Or, if the component deliberately uses the user's local zone, keep it as is and fix the test instead (option 2).

2. **Pin TZ for the whole jest run** so laptops behave like CI. In billing-ui's jest config, add a `globalSetup` that does `process.env.TZ = 'UTC'`. Then change the expected value to `"Nov 1, 2026, 3:30 AM"`. Do it in globalSetup, not in a test file, because by then Node may already have cached the zone.

I'd go with 2 at minimum, and also pin `'en-US'` while you're in there. That's the same locale bug your teammate hit with the date range picker. To be honest, this is also why I said to pin timezone there too: that one only passed because everybody running it happened to be in the same zone.

You can confirm it in 5 seconds locally: `TZ=UTC npx jest InvoiceTable` should fail on your laptop the same way CI does.

It's a work repo, so put this up as a PR and maybe tag Priya so she knows why it broke.
