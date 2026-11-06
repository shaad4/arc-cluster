# ARC development guidelines

ARC is a self-hosted Distributed Compute Control Plane for the existing five-node
Ray cluster (20 vCPUs, approximately 39 GiB physical RAM), deployed on InstaBox
box1 over Tailscale. Repository: `shaad4/arc-cluster`.

## Architecture and safety

- Use a lightweight, modular FastAPI/Python backend and React/TypeScript/Vite
  frontend with Tailwind CSS and shadcn/ui.
- Keep backend configuration, API routes, and typed response models separate.
- Use real metrics only. Use Ray APIs for membership and resource information.
- Distinguish machine reachability, Ray membership, and application health.
- Never rebuild, restart, or modify running Ray infrastructure without explicit
  user approval. Never modify `/data/cluster/venv`; use a dedicated backend venv.
- Do not assume SSH access between nodes. Document safe remote metrics and
  management mechanisms before implementing them; allowlist management actions.
- No application login is required. Bind to localhost by default and never expose
  administrative endpoints publicly.
- Respect InstaBox resource limits. Avoid unnecessary databases, microservices,
  and heavyweight infrastructure.
- Never commit credentials, tokens, SSH keys, environment secrets, dependencies,
  or runtime logs. Do not print secrets during inspection.

## Design standards

Use original ARC branding with a minimal Vercel-inspired dashboard: Geist type,
dark monochrome colors, black and near-black backgrounds, thin neutral borders,
compact metric cards, clean tables, subtle status indicators, minimal charts,
Lucide icons, consistent spacing, and responsive layouts. Avoid generic admin
templates, colorful gradients, glassmorphism, oversized cards, excessive motion,
and fabricated dashboard data.

## Incremental workflow

1. Inspect relevant files and Git status before each task.
2. Implement the smallest useful, independently testable change.
3. Run relevant tests, linting, or validation.
4. Review the diff and stage only intended files; never blindly `git add .`.
5. Commit immediately after completing each task, before starting the next one.
   Local commits are authorized. Keep the working tree clean between tasks.
6. Use conventional prefixes: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`,
   `chore:`, or `style:`. Never combine unrelated work or commit broken changes.
7. Never rewrite history or force-push. Do not push without user approval.

## Full implementation scope

Build the complete seven-page React application and FastAPI control plane in small
validated commits. Reuse the existing `backend/arc` package. Keep Ray isolated in
a persistent bridge using `/data/cluster/venv/bin/python`; never install ARC
packages there. Sampling is centralized, bounded, and independent of browsers.
Missing or stale observations must remain explicit, never become zero or healthy.

Protect mutations with host/origin validation and confirmation. Agent credentials
are service-only secrets outside Git. Controls must fail closed when connectivity,
membership, process state, or workload checks are unavailable. Head controls are
disabled. Never execute example jobs or change worker state during development.

Serve the production frontend through FastAPI on loopback port 8000. Provide
unprivileged deployment scripts and optional systemd units; do not enable
privileged services or install worker agents without approval. Access is through
an SSH tunnel. No public hosting, tunnels, application login, or wildcard CORS.
Run backend tests, frontend tests, TypeScript, ESLint, and production build.
Document deployment gaps honestly. Continue independent work when a remote
agent or infrastructure permission is unavailable.
