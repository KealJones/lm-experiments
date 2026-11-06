It's timezones. Not flaky, not your code. The test is just reading whatever timezone the machine it runs on is set to.

`toLocaleString()` with no `timeZone` option uses the process's local timezone. Your laptop is on US Central and CI sets `TZ=UTC` in the workflow env. So the same instant, `2026-11-01T03:30:00Z`, comes out as:

- **Your laptop (CDT, UTC-5):** Oct 31, 2026, 10:30 PM, which is what the test expects
- **CI (UTC):** Nov 1, 2026, 3:30 AM, which is what CI got

The expected string was hardcoded from a Central-time machine, so it can only pass in Central. (DST doesn't end until 07:00 UTC that day, so it's still -5 at 03:30.) That's also why the commit before Priya's test was green: nothing else formats dates. So that "TZ=UTC doesn't matter" thing from earlier doesn't hold anymore.

**One thing to do right now** to prove it:

```
TZ=UTC npx jest InvoiceTable
```

If it fails locally with the exact same Expected/Received, that's confirmed.

**Then the fix.** Make the test stop depending on the machine. Pick one:

1. **Pin it in the formatting** (my pick): `toLocaleString('en-US', { timeZone: 'America/Chicago' })` or `'UTC'`, whichever the product actually wants. Adding `'en-US'` also heads off the locale problem your teammate hit with the date picker.
2. **Pin it for the whole package:** set `process.env.TZ = 'UTC'` in a `globalSetup` in billing-ui's `jest.config.ts`, then update the expected string to `Nov 1, 2026, 3:30 AM`. Local and CI will match from then on.

Before you just flip the expected string, though, ask Priya one question: is the due date supposed to show in the viewer's local time? Right now a Central user sees the invoice as due **Oct 31** and a UTC user sees **Nov 1**. If a due date is really a calendar day, that's arguably a product bug and not only a test bug, and option 1 with an explicit zone is the real fix.
