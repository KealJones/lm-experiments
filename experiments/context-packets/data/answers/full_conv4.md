It's the timezone thing you mentioned yesterday. Your CI workflow sets `TZ=UTC` and your laptop is on Central, and this is the first test today that actually touches dates.

`new Date('2026-11-01T03:30:00Z')` is one fixed instant. `toLocaleString()` with no `timeZone` formats it in whatever timezone the process is running in:

- **Your laptop (Central):** 03:30 UTC minus 5 hours (it's still CDT, since DST doesn't end until 2 AM local that morning) = **Oct 31, 10:30 PM**. That's the expected value.
- **CI (UTC):** no conversion, so you get **Nov 1, 3:30 AM**. That's the received value.

That's also why it fails every time instead of 1 in 4. Nothing is racing. It's the same input in a different environment, so you get the same wrong answer on every run. Priya almost certainly wrote the expected string by running it on her own machine in a US Central timezone. She also picked a timestamp a few hours after midnight UTC, so the date changes when you switch timezones, which makes the mismatch really obvious.

Reproduce it first, same as you did with the mock thing:

```
TZ=UTC yarn jest InvoiceTable -t "formats the due date column"
```

That should fail locally with the exact same diff.

Then the fix depends on what the column is *supposed* to show:

1. **Due dates should show in the viewer's local time** (probably the case): the component is fine and the test is what's wrong. Make the timezone deterministic for the tests, e.g. put `process.env.TZ = 'UTC'` in a `globalSetup` file, or set `TZ=UTC` in the package's test script so local and CI always match. Then change the expected value to `"Nov 1, 2026, 3:30 AM"`.
2. **Due dates should always show in one specific zone** (like a billing timezone): that's an actual product bug. The component should pass `timeZone` explicitly to `toLocaleString` / `Intl.DateTimeFormat`, and the test should assert against that zone.

While you're in there, also pin the locale (`'en-US'`) if the call doesn't pass one, because that's the exact bug your teammate just hit in the date picker. My guess is his tests are only safe right now because CI happens to be on UTC.

Before you change the expected string, ask Priya which one she meant, because that decides whether this is a one-line test fix or a bug in the component.
