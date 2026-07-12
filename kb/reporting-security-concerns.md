# Reporting a security concern

If you suspect unauthorized access to your account, a leaked credential or API key, phishing
impersonating Northbeam, or any other security issue, flag it immediately — this is not a
standard-priority ticket category.

## What to flag

- Unrecognized login sessions or devices (Account → Security → Active Sessions shows all
  current sessions).
- A password or API key you believe was exposed (e.g., accidentally committed to a public
  repo, phished).
- Suspicious emails claiming to be from Northbeam asking for credentials or payment.
- Any account activity you didn't perform (settings changes, data exports, new API keys).

## Immediate steps you can take yourself

1. If you still have access: change your password immediately (see "Resetting your password
   and unlocking your account") and revoke any API keys you don't recognize (Account →
   Developer → API Keys).
2. End all other active sessions: Account → Security → Active Sessions → End All Other
   Sessions.
3. Enable multi-factor authentication if it isn't already on: Account → Security → MFA.

## What happens after you submit this

Security submissions are triaged with priority regardless of your plan -- this category is
never subject to the standard queue. Depending on severity, we may temporarily lock the
account (you'll be guided through re-verification) while we investigate. We do not disclose
details of other customers' accounts or our internal security tooling in ticket responses.

## What not to do

Don't post account details, API keys, or suspected vulnerabilities in public channels
(social media, public forums, GitHub issues) -- send them to us directly so they can be
addressed before wider disclosure.

## When to contact support

Submit this the moment you notice something, don't wait -- even if you're not certain
something is wrong. Include what you observed, when, and any relevant session/login details
you can see under Active Sessions.
