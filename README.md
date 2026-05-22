# GateInDesk

White-label fork of [RustDesk](https://github.com/rustdesk/rustdesk) for private remote support deployment.

## Build

CI builds Windows installer automatically on push to `main`. See [`.github/workflows/build-windows.yml`](.github/workflows/build-windows.yml).

Deployment-specific values (server hostname, public key, branding URL) are not committed to source — they are injected from repository secrets at build time.

## License

AGPL-3.0 (inherited from upstream rustdesk).
