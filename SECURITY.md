# Security Policy

## Supported versions

Security fixes are applied to the latest release and the default branch.

## Reporting a vulnerability

Do not open a public issue for suspected vulnerabilities. Use GitHub's private
vulnerability reporting for this repository when available, or contact the
maintainer through the account listed on the repository.

Include:

- the affected version or commit;
- minimal reproduction steps using synthetic data;
- impact and realistic attack conditions;
- suggested mitigations, if known.

Never include live credentials, customer data, proprietary prompts, or production
traces in a report. Reports will be acknowledged as soon as practical and handled
according to severity and reproducibility.

## Scope notes

Agent Quality Gate evaluates provider responses. It does not enforce provider-side
network isolation, secret storage, identity controls, or tool sandboxing. Those
controls remain the responsibility of the deployed agent platform.
