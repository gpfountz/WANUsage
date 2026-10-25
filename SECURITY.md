<!-- SPDX-FileCopyrightText: 2026 Greg Pfountz -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->

# Security Policy

## System and Scope

WANUsage is a Python CLI for macOS and Linux, run interactively or by cron.
The owner-confirmed deployment has no inbound service and uses outbound
connections to OPNsense vnStat and an operator-selected SMTP server.
A trusted local user manages configuration and runs the application.

Review `src/wanusage/`, configuration templates, packaging, `scripts/`,
and `.github/workflows/`. Tests and documentation provide supporting context.
Assets include OPNsense and SMTP credentials, usage-report confidentiality
and integrity, alert delivery, and local run and alert state.

## Threat Model and Trust Boundaries

- CLI arguments, TOML settings, destinations, recipients, and the colocated
  `.env` file are selected by the trusted operator.
- Network traffic, HTTP redirects, API response bodies, and SMTP responses
  cross trust boundaries. Authenticate peers and validate incoming data;
  an operator-selected endpoint does not make every response safe to parse.
- Configuration, credentials, state, lock files, and their containing
  directories form a local filesystem boundary. The documented deployment
  uses a private runtime directory; verify actual permissions and attacker
  access when assessing a local attack.
- Repository contributions and dependency/build inputs cross a separate
  automation boundary. Changes must not expose CI credentials or grant
  untrusted contributions unintended execution privileges.

## Security Invariants

These are required properties, not assertions that every control is complete.

- Keep API and SMTP authentication secrets out of tracked configuration,
  packages, reports, and normal or debug diagnostics. Read runtime credentials
  from the selected configuration's colocated private `.env` file.
- Reject configuration and credential files accessible by group or others.
  Evaluate ownership, symlink, race, and parent-directory issues against
  realistic local attacker access; mode checks alone do not prove safety.
- Send API credentials only to the intended HTTPS origin with certificate
  and hostname validation. Endpoint paths and redirects must not leak
  credentials or permit a downgrade to cleartext transport.
- Require verified STARTTLS before SMTP authentication. A failed TLS setup
  must not fall back to cleartext authentication.
- Treat remote data as data. Parsing and error rendering must not enable
  code execution, credential disclosure, or practical resource exhaustion.
- Send reports only when requested with `--email`; send threshold alerts only
  with `--alerts`. Use operator-configured recipients.
- Serialize cooperating processes' state transactions and replace state
  atomically. Failed delivery must not mark an alert successfully sent or a
  daily workflow complete. State operations must not enable unauthorized
  file access or modification.

## Reportable Findings and Severity Context

Report reachable violations with the attacker-controlled input, required
access, affected asset, and concrete impact. Credential disclosure, unsafe
transport, unauthorized file operations, exploitable parsing, and abuse of
build or CI privileges are relevant finding classes.

Calibrate severity to this local outbound application and the privileges
actually available. Private-network placement is not a blanket mitigation.
Missing web-server or tenant controls are not findings without such a surface.
A report-formatting or date-calculation bug needs a demonstrated security
impact to count as a security finding.

## Out of Scope, Exclusions, and Accepted Risk

There are no owner-approved finding-class exclusions or accepted risks.
The confirmed trusted-operator boundary is not evidence that arbitrary local
users control runtime files. Claims requiring such control must establish it.
Compromise of the running user's account or host administrator is not by
itself a WANUsage vulnerability; app-enabled access across a boundary remains
reportable.

## Known Limitations and Compensating Controls

- API and SMTP operations currently use 30-second socket timeouts. The HTTP
  reader has no explicit response-size cap; a socket timeout is not a total
  workflow deadline or a memory bound.
- HTTP uses the standard-library opener without a custom redirect policy.
  Assess redirect credential handling rather than assuming origin confinement.
- File validation checks regular-file status and mode bits through pathname
  operations. It does not establish ownership or race-free access. Private
  directories are documented operational protection, not an enforced guarantee.
- Advisory locks coordinate cooperating local processes. Email delivery and
  state persistence are separate operations; a crash can allow repeat delivery.
- Unauthenticated SMTP with `use_tls = false` is currently permitted by code.
  No plaintext-SMTP exception is approved by this policy.
- Tests cover selected permission checks, URL validation, SMTP TLS settings,
  locking, and state behavior. They are evidence of intent, not proof of
  deployment controls or exhaustive security validation.
