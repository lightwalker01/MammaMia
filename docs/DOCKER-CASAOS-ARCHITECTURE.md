# MammaMia — Docker / CasaOS fork technical documentation

> Status: documentation for the `lightwalker01/MammaMia` fork, updated November 15, 2026. This is an **unofficial packaging fork**, not a functional fork. The application code and the add-on concept belong to [UrloMythus/MammaMia](https://github.com/UrloMythus/MammaMia). This document explains how to understand and reconstruct the container distribution; it does not replace runtime testing on the server.

## 1. Goals and scope

- Preserve the upstream source code in the fork (even if the original repository becomes temporarily unavailable).
- Synchronize upstream updates once per day **without force-pushing** or removing custom files.
- Build using GitHub Actions, publish to `ghcr.io/lightwalker01/mammamia`, and run on CasaOS without a local source checkout.
- Support **linux/amd64 only**, preferring a small, compatible base image over Alpine.
- Avoid modifying original application files in Git: visual customizations are applied **only at build time**.
- Keep `config.json` editable and persistent in AppData, with automatic first-run initialization.
- The add-on is not offline: calls to providers, TMDB, Kitsu, EPG services, etc. still require Internet access. Only the application's general interface graphics are hosted locally.

## 2. Repository layout and components

| Path | Responsibility |
| --- | --- |
| `Dockerfile.ghcr` | AMD64 image build, Python dependencies, Tesseract, configuration setup, and packaging-only patching |
| `Dockerfile.ghcr.dockerignore` | Dockerfile-specific build-context exclusions |
| `docker-entrypoint.sh` | At first startup, copies the default configuration into the bind mount without overwriting later changes |
| `docker-assets/patch_branding.py` | Rewrites image references and the manifest logo **inside the image** |
| `docker-assets/pizza.png` | Historical pizza icon recovered by the user via Wayback Machine and resized for packaging |
| `docker-assets/background.png` | Original 800×800 background recovered by the user; an optimized 256×256, three-color-palette PNG derivative to reduce image size. The original artwork is retained, but not its original image fidelity |
| `compose.casaos.yml` | CasaOS Compose file with `x-casaos` metadata, bind mounts, and settings |
| `.github/workflows/sync-upstream.yml` | Scheduled or manual fetch/merge from upstream |
| `.github/workflows/publish-ghcr.yml` | PR builds; image build and GHCR push after changes to main, manual dispatch, or successful synchronization |
| `README.md` | Notice about the fork's limited purpose and links to the Compose file and this document |
| `run.py`, `static/*`, `Src/*` | Upstream application sources, kept unchanged in the fork unless upstream itself changes them |

History: PR #1 added Docker and CasaOS packaging; PR #2 introduced locally hosted graphics (pizza icon and background) and the build-time branding patch.

## 3. Docker design decisions

- Base image: `python:3.11-slim-bookworm`. Debian Slim uses glibc, which is compatible with precompiled Python wheels, particularly for `curl_cffi` and `lxml`. Alpine might be smaller in isolation, but could require compilation and musl-specific workarounds; distroless would make Tesseract integration more complex.
- `apt-get install --no-install-recommends tesseract-ocr ca-certificates`: the project needs the Tesseract executable; `libtesseract-dev` development headers are not needed at runtime when using `pytesseract`.
- Install with `pip install -r requirements.txt pytesseract` without a persistent pip cache.
- Copy `requirements.txt` before the rest of the sources to improve dependency-layer cache reuse.
- Application port: 8080. The application obtains its listening port from the upstream `config.json` (and can override it using `PORT_ENV` when supported).
- The Docker Buildx workflow targets `linux/amd64` only. No ARM64 build is configured.
- Publishing a new `latest` image to GHCR does **not** update an already-running container. A pull and recreation through CasaOS or a dedicated updater are required.

## 4. Persistent configuration and first startup

The upstream application reads `/app/config.json`. To preserve this interface without overwriting application code or requiring the host file to be created manually:

1. The Dockerfile copies the original default configuration to `/app/defaults/config.json`.
2. It removes `/app/config.json` and creates the **symbolic link** `/app/config.json -> /app/data/config.json`.
3. Compose bind-mounts `/DATA/AppData/mammamia` onto `/app/data` without mounting over `/app`, which contains the application sources.
4. The entrypoint creates `/app/data/config.json` from the default **only if it does not already exist**, then runs `python run.py`.
5. Image updates preserve the host's configuration. New upstream settings are **not** automatically merged into an existing configuration; if upstream changes the JSON schema, compare the default file and migrate settings manually.

The entrypoint aborts startup if `/app/data/config.json` is a directory, making an otherwise confusing error explicit.

**Why a directory bind mount?** Mounting the entire host directory as `/DATA/AppData/mammamia:/app` would hide the source code bundled in the image, preventing startup. Bind-mounting an individual *nonexistent file* can instead cause Docker to create a directory at that path, which also fails. Therefore the deployment mounts a dedicated data directory.

## 5. CasaOS integration

`compose.casaos.yml` specifies:

- Compose project `name: mammamia`, service `services.mammamia`, explicit `container_name: mammamia`, and image `ghcr.io/lightwalker01/mammamia:latest`.
- Explicit app identifier: `x-casaos.store_app_id: lightwalker01-mammamia`. Visible app name: `MammaMia`; architecture: `amd64`; port: 8080; launch path: `/configure`.
- CasaOS icon and thumbnail use the PNG stored in the **GitHub fork** (CasaOS cannot rely on the URL of a local instance that is not known at import time). Internal web images, by contrast, are served by the **container**.
- `TMDB_KEY`: set a valid value in CasaOS rather than committing it to the repository. The `TZ` environment variable is set to `Europe/Rome`.
- `restart: unless-stopped`, `init: true`, `no-new-privileges:true`, and `json-file` log rotation (10 MiB × 3 files).
- Persistent data: `/DATA/AppData/mammamia/config.json`. The actual location of the imported Compose file depends on the CasaOS release and import procedure. `/var/lib/casaos/apps/...` is common, but the exact directory name is not guaranteed by `store_app_id` alone.

The CasaOS host does not need a Git checkout. For anonymous pulls, make the GHCR package public in GitHub Packages; a private package requires Docker authentication.

## 6. Self-hosted graphics and build-time patching

External upstream image URLs:

- Pizza icon: `https://creazilla-store.fra1.digitaloceanspaces.com/emojis/49647/pizza-emoji-clipart-md.png` (now returns `AccessDenied`).
- Background: `https://i.postimg.cc/ry3p76HY/italian-seamless-free-vector-pattern3.png`.

PR #2 preserves these images under `docker-assets`. The user-supplied original 800×800 background was downsampled to 256×256 and quantized to a three-color palette to keep the repository and container compact. The artwork is the original pattern, although resolution and some tonal detail are reduced.

After `COPY . ./`, `Dockerfile.ghcr` runs `python3 /app/docker-assets/patch_branding.py`. This modifies **only the files copied into the Docker image**, and never commits modifications to the upstream application sources:

- `static/static.py` and `static/configure.py`: replace the pizza URL with `/icon.png`, the background URL with `/background.png`, and the favicon content type with `image/png`.
- `static/uprot.html`: apply the same URL replacements to the CAPTCHA page.
- `run.py`: add the FastAPI endpoints `/icon.png` and `/background.png` using `FileResponse`.
- Stremio manifest: set the `logo` field to an absolute URL pointing at the **requesting instance**, built from its protocol/hostname and applicable reverse-proxy forwarding headers. Example values: `http://192.168.1.20:8080/icon.png` or `https://mammamia.example.com/icon.png`.
- CasaOS still uses the GitHub Raw URL for `docker-assets/pizza.png`.
- The patch checks significant structural anchors, such as the FastAPI response import, `/configure` route, and manifest function. Incompatible upstream refactoring can make the build fail rather than silently producing an incorrectly patched image.

**Reverse-proxy trust:** ensure forwarded host and protocol headers are set or sanitized by a trusted reverse proxy, rather than blindly accepting arbitrary values from Internet clients. Stremio can load `/icon.png` only when it can reach the instance; an IP address on a private LAN will not work outside that LAN.

The patch deliberately affects presentation and the manifest only; it does not change streaming providers or stream extraction behavior.

## 7. Upstream synchronization

The `sync-upstream.yml` workflow is scheduled using cron `23 3 * * *` (UTC), and can also be run manually. In essence it performs:

```sh
git fetch upstream main
git merge --no-edit upstream/main
git push origin HEAD:main  # only when there is a new commit
```

It does not run `git reset --hard` or `git push --force`. If upstream disappears or merging creates a conflict, the workflow fails and leaves the fork's remote `main` untouched. Fork-specific files are not intentionally deleted, although conflicts remain possible if upstream later introduces files at the same paths.

**Backup limitation:** a GitHub fork is not an independent off-site backup. To guard against the fork itself being deleted or removed, periodically run `git clone --mirror` to a separate provider or private backup. If upstream disappears but the fork survives, images can still be built using the copy of the code retained in the fork.

The previous inherited `sync-build.yml` workflow, which force-reset the branch and published to a third party's Docker Hub, and `update_domains.yml` were removed in PR #1. Domain updates can be managed via the container's persistent `config.json`; upstream's `/update` endpoint calls an external service and may modify this file.

## 8. GHCR build and publishing pipeline

`publish-ghcr.yml` runs on:

- Push to `main`: build and publish the image.
- Pull request targeting `main`: **build without publishing**, to check dependency installation (no smoke tests are configured).
- `workflow_dispatch`: manual build and publish.
- Successful `workflow_run` event after an upstream sync: build and publish the updated branch.

The last trigger matters because a push performed using `GITHUB_TOKEN` does not necessarily start another workflow via `push`. The publishing job has `packages: write`, logs into GHCR with `GITHUB_TOKEN`, uses `docker/build-push-action`, and caches build layers with `type=gha`.

Image tags: `ghcr.io/lightwalker01/mammamia:latest` and `ghcr.io/lightwalker01/mammamia:sha-<12-character-revision>`. A SHA tag allows rollback to a specific version if the registry retains it; the mutable `latest` tag does not automatically update running containers.

The workflow publishes to an Internet-accessible registry but never bakes the TMDB API key into the image.

## 9. Rebuilding the entire setup from scratch

Prerequisites: a GitHub account with the fork/source history, enabled GitHub Actions, `contents: write` permissions for synchronization and `packages: write` for GHCR, a `linux/amd64` CasaOS host running Docker, and a TMDB API key.

1. Fork `UrloMythus/MammaMia`, or restore the source and Git history from a backup.
2. Add all packaging files listed in section 2, copying them from this fork or its commits. Do not permanently rewrite the upstream `run.py` or `static/` files.
3. Enable GitHub Actions. Trigger the publish workflow on `main`; check that the Actions build succeeds and creates a GHCR package.
4. Make the package public if CasaOS will perform anonymous pulls.
5. Import `compose.casaos.yml` into CasaOS, set a real `TMDB_KEY` value, and confirm host port 8080 is available. Change the **published** host port if required.
6. Start the container and check `/configure`, `/icon.png`, `/background.png`, and `/manifest.json` (the latter may redirect to a parameterized manifest).
7. Verify that `/DATA/AppData/mammamia/config.json` was created automatically; back it up.
8. After future image updates, pull the new image and recreate the container while preserving the bind mount. Use the CasaOS UI or run `docker compose pull && docker compose up -d` from the directory holding the applicable Compose file.

## 10. Diagnostics and troubleshooting

```sh
docker ps --filter name=mammamia
docker logs --tail=100 mammamia
docker inspect mammamia --format '{{ .Config.Image }}'
curl -I http://YOUR_SERVER_IP:8080/icon.png
curl -I http://YOUR_SERVER_IP:8080/background.png
```

`curl -I` sends an HTTP HEAD request. If a FastAPI endpoint only accepts GET, it might return 405; in that case use `curl -o /dev/null -w '%{http_code}' http://YOUR_SERVER_IP:8080/icon.png` instead. Follow redirects when checking the manifest.

- **CasaOS icon is missing:** verify the GitHub Raw URL and CasaOS UI cache. Refreshing or reimporting Compose metadata, or clearing the relevant cache, may be required.
- **Web icon is missing:** request `/icon.png` in a client browser and inspect the browser's network errors; also check that the running container uses the updated image.
- **Configuration is missing:** inspect bind-mount permissions and the entrypoint logs.
- **Synchronization fails:** review the GitHub Actions log and resolve any fork-side merge conflict manually, without rewriting history.
- **Build fails:** examine changed upstream file layout, updated Python dependencies, and changes to the branding script's anchor text.
- **Manifest contains the wrong URL:** inspect Host, `X-Forwarded-Proto`, `X-Forwarded-Host`, and the reverse-proxy setup.
- **CasaOS cannot pull the package:** inspect GHCR visibility and Docker authentication.

## 11. Security decisions and limitations

- The packaging does not make the service offline. Metadata providers, EPG services, TV-channel images, streaming providers, and video streams can still contact external websites.
- There are no additional databases or data volumes. The configuration file is the only persisted resource under the current application design.
- If the service must be accessible from the Internet, use a correctly configured HTTPS reverse proxy. Assess the security implications of the upstream `/update` endpoint before exposing it publicly.
- Automatically building upstream commits requires trust in maintainers and dependencies. Updates can change behavior or break functionality. Monitor GitHub Actions results and keep SHA-tagged images for rollback.
- Verify the original asset licenses before redistributing images retrieved from archives. Their presence in upstream or on Wayback Machine does not prove that redistribution is permitted.
- CI compiles the image but does not launch it. Smoke testing was intentionally excluded: the owner performs manual verification on CasaOS.

## 12. References

- [Upstream repository](https://github.com/UrloMythus/MammaMia)
- [Container packaging fork](https://github.com/lightwalker01/MammaMia)
- [GHCR packages](https://github.com/lightwalker01?tab=packages)
- [PR #1](https://github.com/lightwalker01/MammaMia/pull/1) — Docker/CasaOS infrastructure
- [PR #2](https://github.com/lightwalker01/MammaMia/pull/2) — locally hosted graphics
- [CasaOS AppManagement source](https://github.com/IceWhaleTech/CasaOS-AppManagement)
- [Docker Compose file reference](https://docs.docker.com/reference/compose-file/)
