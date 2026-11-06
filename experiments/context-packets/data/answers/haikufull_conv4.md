Ok, this one is a different animal, and the numbers basically tell you what happened.

Work the math on the two strings. `2026-11-01T03:30:00Z` is 3:30 AM UTC on Nov 1. Your laptop is on central time, and DST ends on Nov 1 this year, so at that instant your laptop is still on CDT (UTC-5). 3:30 AM UTC minus 5 hours is 10:30 PM on Oct 31. That's exactly the Expected string, so the expected value was written from a run on a machine in Central time.

The Received string is 3:30 AM Nov 1, which is the same instant rendered in UTC. CI sets `TZ=UTC` in the workflow env block, which is the thing you noticed a while back. So CI is formatting in UTC and the test hardcodes Central.

Why it fails every time and isn't flaky: both environments are fixed. Your laptop is always Central, CI is always UTC, so the output never changes between runs. It only looks random because it passed on your machine.

Why it passed for you: the test's expected string only matches when the machine's zone is Central during that DST period. Priya almost certainly wrote it on her laptop, and it passes there.

To confirm before changing anything, run it locally with the CI zone:

`TZ=UTC yarn jest InvoiceTable -t "formats the due date column"`

If it fails with the same Expected and Received lines, that's the whole story.

Fix options, in order of what I'd do:

1. Pin the zone in the test so it doesn't depend on the machine. Pass `timeZone` to `toLocaleString`, for example `{ timeZone: 'UTC' }` with the expected `"Nov 1, 2026, 3:30 AM"`. Pinning `locale: 'en-US'` too is a good idea for the same reason your teammate's date picker test needed it.
2. If the component is supposed to show the user's local time, then the zone is a real product decision. Pin it in the test with a `TZ` setup in jest globalSetup, or pass an explicit zone from the component, so the test checks intended behavior and not whatever the runner happens to be.

Either way, the expected string should come from the zone you're asserting on, not from whichever laptop wrote the test. I'd also mention it to Priya, since she may not know the CI zone is UTC, and the same thing will bite any other test that formats dates without a zone.

One caveat: I'm going off the two strings and your description, not the test file itself, so check that the test really calls `toLocaleString()` with no options before you commit to the fix.
