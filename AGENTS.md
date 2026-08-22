# Project instructions

- The canonical repository is `teddy920810/media-download-service`; reject similarly named checkouts whose `origin` does not match.
- Before editing, report the normalized path, `origin`, branch, HEAD, and working-tree status. Preserve unrelated user changes.
- Read this file, `README.md`, and `pyproject.toml` before implementing.
- Keep the service private. Never expose internal tokens, proxy credentials, R2 credentials, signed URLs, or full user data.
- Preserve the public-only, single-video, no-DRM, no-cookie, 720p, 10-minute, and 500 MB MVP boundaries.
- Keep implementation, tests, and helper scripts cross-platform. Prefer Python modules and package tooling over shell-specific logic.
- For behavior changes, add a failing test first, make the smallest change, run the targeted test, then run `python -m pytest` in the activated project environment.

## Delivery and release gates

- Classify the request as read-only diagnosis, local iteration, or delivery to `main`. If an implementation target is unclear, verify locally but do not commit, push, merge, or deploy.
- Separate account, billing, secret-manager permission, proxy purchase, and trial-consuming steps from work Codex can complete automatically.
- Report code verification, repository/PR state, container build, Cloud Run service/job deployment, R2 delivery, and end-to-end web flow as separate gates.
- Never bypass authentication, platform access controls, rate limits, DRM, or source-site restrictions.
- If failures vary across deployments or repositories, classify provider, network/proxy, local process, and application causes before changing code or repeatedly deploying.
