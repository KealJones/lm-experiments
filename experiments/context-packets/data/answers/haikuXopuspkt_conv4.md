It's not flaky. It's deterministic, and the cause is almost certainly the TZ difference.

`new Date('2026-11-01T03:30:00Z')` is 03:30 UTC. On Oct 31, US Central is still on daylight time (UTC-5), so that instant is 10:30 PM on Oct 31 on your laptop. That's exactly your expected string, so the assertion was written from a local run. CI sets TZ=UTC, so the same call gives 3:30 AM on Nov 1, which is the received value. The input never changes and the zone does, so it fails every time on CI. A flaky test would sometimes pass.

It passes locally because the expected value was written for your zone, and the test never says which zone it means. Nothing in it is random.

Two ways to fix it:

1. Pin the zone on both sides of the assertion, for example `toLocaleString('en-US', { timeZone: 'America/Chicago', ... })` with the expected string unchanged. This tests what the function is supposed to do no matter what machine runs it. I'd do this one.
2. Change the expected string to "Nov 1, 2026, 3:30 AM". That only proves UTC output and hides the problem from anyone in another zone.

Also pin the locale to en-US, since with no locale the output depends on the runtime default. That's the same thing that fixed the date range picker tests.

Before you change anything, confirm it: run `TZ=UTC` on the test locally, for example `TZ=UTC yarn jest InvoiceTable -t "formats the due date column"`. If it fails with "Nov 1, 2026, 3:30 AM", that's the proof.

The bigger question is whether `formatDate` should take a timeZone argument at all. If it doesn't, the app's output depends on whatever machine runs it, and the test is correctly showing that. Whether the UI should show the user's zone or UTC is a product call, not just a test fix. Also, Nov 1 is the US daylight-time changeover day, so a fixture near 2 AM that day would add a second trap. Paste `formatDate` and the test and I'll tell you which option fits.
