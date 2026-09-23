# Public FOR'EST launch boundary

`/start.html` is an informational homepage. It does not accept signups, payments, or user data. The existing `/` app and its two PIN-protected profiles remain private and unchanged.

## Before enabling public accounts

1. Deploy a separate service and empty database/volume for new accounts. Do not connect the existing `/data` volume or import either current profile.
2. Implement individual user registration with verified email, strong password hashing, session rotation, login throttling and recovery. New users must never see `/api/profiles` or choose an existing profile ID.
3. Scope every course, document, upload, recording, analysis job, export and deletion to the authenticated account on the server. Test cross-account reads and writes, including guessed IDs and concurrent requests.
4. Select a payment provider that accepts the seller in their jurisdiction. Obtain approval for the seller account and set prices and cancellation/refund terms before displaying a checkout button.
5. Activate access only after a verified server-side payment webhook. Check webhook signatures, event idempotency, subscription state, retries, cancellations and refunds. A browser redirect alone must never grant access.
6. Put strict per-account AI usage limits and cost alerts in place before public signup. Test backup/restore and retention policy without using existing user data.

No public checkout or account registration should be announced as available until these checks pass on the separate service.
