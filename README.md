# CBSUA Helpdesk

CBSUA-maintained fork of [Frappe Helpdesk](https://github.com/frappe/helpdesk), the primary ticketing and service-request application in the CBSUA Helpdesk platform.

This repository contains the Helpdesk application itself, including its agent workspace, customer-facing portal, ticket lifecycle, and native service-desk capabilities. It is not the deployment repository; image assembly, Compose configuration, release promotion, and operational runbooks live in [cbsua-app-helpdesk-deployment](https://github.com/AgeReapor/cbsua-app-helpdesk-deployment).

## Position in the CBSUA stack

| Layer | Repository | Responsibility |
|---|---|---|
| Framework | [cbsua-app-frappe](https://github.com/AgeReapor/cbsua-app-frappe) | Shared Frappe platform |
| Dependency | [cbsua-app-telephony](https://github.com/AgeReapor/cbsua-app-telephony) | Telephony integration required by Helpdesk |
| Ticketing application | This repository | Helpdesk tickets, agent/customer interfaces, and service-desk behavior |
| UI library | [cbsua-app-frappe-ui](https://github.com/AgeReapor/cbsua-app-frappe-ui) | Forked Frappe UI submodule used by the frontend |
| Local development | [cbsua-app-pilot](https://github.com/AgeReapor/cbsua-app-pilot) | Bench lifecycle and local Admin UI |
| Container build definitions | [cbsua-app-frappe-docker](https://github.com/AgeReapor/cbsua-app-frappe-docker) | Reusable Frappe image and Compose build infrastructure |
| Release orchestration | [cbsua-app-helpdesk-deployment](https://github.com/AgeReapor/cbsua-app-helpdesk-deployment) | CBSUA image workflow, Compose stack, and deployment documentation |

## CBSUA customization principles

- Preserve native Frappe Helpdesk functionality wherever possible.
- Keep CBSUA-specific branding, boot data, defaults, office configuration, and verified institutional workflow changes explicit and documented.
- Prefer configuration over custom code; add code only for a confirmed requirement that native Helpdesk cannot satisfy safely.
- Treat office/team authorization as a security boundary that must be tested, not inferred from assignment.
- Keep the framework and application refs compatible and record exact SHAs in the deployment source lock.

The exact current build refs are defined by the deployment workflow and its configuration, not by this README. The deployment baseline currently uses the CBSUA fork branches selected there; do not assume that upstream release branch guidance automatically describes the CBSUA deployment image.

## Local development with Pilot

The following is the CBSUA Pilot-oriented workflow used for local prototyping. Run commands from the environment where Pilot is installed:

```bash
pilot new cbsua-app-bench
pilot -b cbsua-app-bench start
```

Open the Pilot Admin UI at the URL printed by Pilot (the local development setup commonly exposes `http://[::1]:7000/sites`).

Fetch the CBSUA forks:

```bash
pilot get-app https://github.com/AgeReapor/cbsua-app-telephony
pilot get-app https://github.com/AgeReapor/cbsua-app-helpdesk
```

Install the application dependency before Helpdesk:

```bash
pilot --site cbsua-helpdesk.localhost install-app telephony
pilot --site cbsua-helpdesk.localhost install-app helpdesk
```

Build the Helpdesk frontend:

```bash
pilot build --app helpdesk
```

These commands assume the site already exists and that the bench has been initialized with the compatible CBSUA Frappe fork. Follow Pilot's own setup prompts and the deployment repository's current compatibility/source-lock baseline. Do not treat this short sequence as a complete production deployment guide.

## Feature documentation

- [Anonymous ticket submission and email communication](docs/features/anonymous-ticket-submission.md)
- [CBSUA office-aware Helpdesk architecture](docs/architecture/office-aware-helpdesk.md)
- [All documentation](docs/README.md)

## Production image and deployment

Use [cbsua-app-helpdesk-deployment](https://github.com/AgeReapor/cbsua-app-helpdesk-deployment) for:

- canonical application refs and source locks;
- building and publishing the combined image;
- local Docker Compose testing of the published image;
- production Compose configuration, migrations, backups, rollback, and release validation.

The reusable Docker build system is maintained in [cbsua-app-frappe-docker](https://github.com/AgeReapor/cbsua-app-frappe-docker).

## Development and contribution

Before changing Helpdesk:

1. Read the deployment repository's architecture and SRS to understand CBSUA requirements.
2. Check whether the desired behavior already exists in native Helpdesk.
3. Identify the correct layer for the change (framework, UI library, Helpdesk, or deployment configuration).
4. Document the change and compatibility impact.
5. Run relevant backend/frontend tests and validate the combined image before release.

## Upstream relationship

This is a fork of Frappe Helpdesk. Keep upstream attribution and licensing intact. Review upstream changes deliberately, preserve CBSUA-specific changes, and record significant divergences so future rebases and upgrades remain understandable.

## License

See [LICENSE](LICENSE) and upstream notices for licensing terms.
