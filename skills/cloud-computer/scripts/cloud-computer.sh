#!/usr/bin/env bash
# SSH helper for a user-owned cloud computer. It deploys static sites and
# manages a Caddy entrypoint on the remote host without storing credentials.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_ROOT="$(cd "$SKILL_DIR/../.." && pwd)"

DRY_RUN=0

log(){ printf '[cloud-computer] %s\n' "$*" >&2; }
warn(){ printf '[cloud-computer] WARN %s\n' "$*" >&2; }
die(){ printf '[cloud-computer] ERROR %s\n' "$*" >&2; exit 1; }
have(){ command -v "$1" >/dev/null 2>&1; }

usage(){
  cat <<'EOF'
Usage:
  cloud-computer.sh [--dry-run] [--host HOST] [--user USER] [--port PORT] [--key PATH] <command> [args]

Commands:
  doctor                         Check local config and remote Docker/Caddy prerequisites
  ssh [args...]                   Open an interactive SSH session
  run <remote-command>            Run a command on the cloud computer
  deploy-static <dir> [domain]    Upload a static site and serve it with Caddy
  expose-service <name> <domain> <upstream>
                                  Reverse proxy a remote service, e.g. 3000 or 127.0.0.1:3000
  status                          Show Caddy compose status
  logs                            Show recent Caddy logs

Environment:
  CLOUD_COMPUTER_HOST             Required host/IP
  CLOUD_COMPUTER_USER             SSH user, default root
  CLOUD_COMPUTER_PORT             SSH port, default 22
  CLOUD_COMPUTER_SSH_KEY          Optional SSH private key path
  CLOUD_COMPUTER_PASSWORD         Optional SSH password; requires sshpass for non-interactive commands
  CLOUD_COMPUTER_REMOTE_ROOT      Remote hosting root, default /srv/cloud-computer
  CLOUD_COMPUTER_DOMAIN           Default domain for deploy-static
  CLOUD_COMPUTER_HTTP_PORT        Host HTTP port, default 80
  CLOUD_COMPUTER_HTTPS_PORT       Host HTTPS port, default 443
  CLOUD_COMPUTER_CADDY_CONTAINER  Container name, default cloud-computer-caddy
  CLOUD_COMPUTER_STRICT_HOST_KEY_CHECKING  OpenSSH setting, default accept-new
EOF
}

load_env(){
  if [ -f "$WORKSPACE_ROOT/.env.local" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$WORKSPACE_ROOT/.env.local"
    set +a
  fi
  local tenant="${TENANT:-}"
  if [ -n "$tenant" ] && [ -f "$WORKSPACE_ROOT/.env.$tenant.local" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$WORKSPACE_ROOT/.env.$tenant.local"
    set +a
  fi
}

expand_path(){
  local p="${1:-}"
  case "$p" in
    "~") printf '%s\n' "$HOME" ;;
    "~/"*) printf '%s/%s\n' "$HOME" "${p#~/}" ;;
    *) printf '%s\n' "$p" ;;
  esac
}

shell_quote(){
  local s="${1:-}"
  printf "'%s'" "$(printf '%s' "$s" | sed "s/'/'\\\\''/g")"
}

slugify(){
  local raw="${1:-site}"
  printf '%s' "$raw" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's#[^a-z0-9._-]+#-#g; s#^-+##; s#-+$##; s#\.+#.#g' \
    | cut -c1-80
}

load_env

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --host) CLOUD_COMPUTER_HOST="${2:?--host needs HOST}"; shift 2 ;;
    --user) CLOUD_COMPUTER_USER="${2:?--user needs USER}"; shift 2 ;;
    --port) CLOUD_COMPUTER_PORT="${2:?--port needs PORT}"; shift 2 ;;
    --key) CLOUD_COMPUTER_SSH_KEY="${2:?--key needs PATH}"; shift 2 ;;
    --remote-root) CLOUD_COMPUTER_REMOTE_ROOT="${2:?--remote-root needs PATH}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    -*) die "unknown option: $1" ;;
    *) break ;;
  esac
done

CMD="${1:-help}"
[ $# -gt 0 ] && shift || true

CLOUD_COMPUTER_USER="${CLOUD_COMPUTER_USER:-root}"
CLOUD_COMPUTER_PORT="${CLOUD_COMPUTER_PORT:-22}"
CLOUD_COMPUTER_REMOTE_ROOT="${CLOUD_COMPUTER_REMOTE_ROOT:-/srv/cloud-computer}"
CLOUD_COMPUTER_HTTP_PORT="${CLOUD_COMPUTER_HTTP_PORT:-80}"
CLOUD_COMPUTER_HTTPS_PORT="${CLOUD_COMPUTER_HTTPS_PORT:-443}"
CLOUD_COMPUTER_CADDY_CONTAINER="${CLOUD_COMPUTER_CADDY_CONTAINER:-cloud-computer-caddy}"
CLOUD_COMPUTER_STRICT_HOST_KEY_CHECKING="${CLOUD_COMPUTER_STRICT_HOST_KEY_CHECKING:-accept-new}"

require_host(){
  [ -n "${CLOUD_COMPUTER_HOST:-}" ] || die "CLOUD_COMPUTER_HOST is not set"
}

ssh_target(){
  require_host
  if [ -n "${CLOUD_COMPUTER_USER:-}" ]; then
    printf '%s@%s\n' "$CLOUD_COMPUTER_USER" "$CLOUD_COMPUTER_HOST"
  else
    printf '%s\n' "$CLOUD_COMPUTER_HOST"
  fi
}

ssh_args(){
  local key
  printf '%s\0' -p "$CLOUD_COMPUTER_PORT" \
    -o "StrictHostKeyChecking=$CLOUD_COMPUTER_STRICT_HOST_KEY_CHECKING" \
    -o ServerAliveInterval=30
  if [ -n "${CLOUD_COMPUTER_SSH_KEY:-}" ]; then
    key="$(expand_path "$CLOUD_COMPUTER_SSH_KEY")"
    printf '%s\0' -i "$key"
  fi
}

ssh_command_args(){
  if [ -n "${CLOUD_COMPUTER_PASSWORD:-}" ]; then
    have sshpass || die "CLOUD_COMPUTER_PASSWORD is set but sshpass is missing. Install sshpass or use CLOUD_COMPUTER_SSH_KEY."
    printf '%s\0%s\0%s\0' sshpass -e ssh
  else
    printf '%s\0' ssh
  fi
  ssh_args
}

run_remote(){
  local remote cmd
  remote="$(ssh_target)"
  cmd="$1"
  if [ "$DRY_RUN" = "1" ]; then
    log "dry-run ssh $remote: $cmd"
    return 0
  fi
  local -a args=()
  while IFS= read -r -d '' arg; do args+=("$arg"); done < <(ssh_command_args)
  SSHPASS="${CLOUD_COMPUTER_PASSWORD:-}" "${args[@]}" "$remote" "$cmd"
}

ssh_interactive(){
  local remote
  remote="$(ssh_target)"
  if [ "$DRY_RUN" = "1" ]; then
    log "dry-run ssh $remote $*"
    return 0
  fi
  local -a args=()
  while IFS= read -r -d '' arg; do args+=("$arg"); done < <(ssh_command_args)
  SSHPASS="${CLOUD_COMPUTER_PASSWORD:-}" exec "${args[@]}" "$remote" "$@"
}

remote_compose_prefix(){
  cat <<'EOF'
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "Docker Compose is missing. Install Docker with compose plugin, then retry." >&2
  exit 42
fi
EOF
}

ensure_proxy(){
  local root http https container qroot
  root="$CLOUD_COMPUTER_REMOTE_ROOT"
  http="$CLOUD_COMPUTER_HTTP_PORT"
  https="$CLOUD_COMPUTER_HTTPS_PORT"
  container="$CLOUD_COMPUTER_CADDY_CONTAINER"
  qroot="$(shell_quote "$root")"

  run_remote "$(cat <<EOF
set -e
mkdir -p $qroot/sites
cd $qroot
if [ ! -f compose.yml ]; then
  cat > compose.yml <<'YAML'
services:
  caddy:
    image: caddy:2-alpine
    container_name: $container
    restart: unless-stopped
    ports:
      - "$http:80"
      - "$https:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./sites:/srv/sites:ro
      - caddy_data:/data
      - caddy_config:/config
volumes:
  caddy_data:
  caddy_config:
YAML
fi
touch Caddyfile
EOF
)"
}

compose_up(){
  local qroot prefix
  qroot="$(shell_quote "$CLOUD_COMPUTER_REMOTE_ROOT")"
  prefix="$(remote_compose_prefix)"
  run_remote "$(cat <<EOF
set -e
cd $qroot
$prefix
\$COMPOSE up -d
EOF
)"
}

update_caddy_block(){
  local marker block remote qroot remote_cmd
  marker="$1"
  block="$2"
  remote="$(ssh_target)"
  qroot="$(shell_quote "$CLOUD_COMPUTER_REMOTE_ROOT")"
  remote_cmd="$(cat <<EOF
set -e
cd $qroot
touch Caddyfile
tmp=\$(mktemp)
awk '
  \$0 == "# BEGIN cloud-computer site $marker" { skip=1; next }
  \$0 == "# END cloud-computer site $marker" { skip=0; next }
  !skip { print }
' Caddyfile > "\$tmp"
cat >> "\$tmp"
printf '\\n' >> "\$tmp"
mv "\$tmp" Caddyfile
EOF
)"

  if [ "$DRY_RUN" = "1" ]; then
    log "dry-run update $CLOUD_COMPUTER_REMOTE_ROOT/Caddyfile marker=$marker"
    printf '%s\n' "$block" >&2
    return 0
  fi

  local -a args=()
  while IFS= read -r -d '' arg; do args+=("$arg"); done < <(ssh_command_args)
  printf '%s\n' "$block" | SSHPASS="${CLOUD_COMPUTER_PASSWORD:-}" "${args[@]}" "$remote" "$remote_cmd"
}

upload_static(){
  local local_dir remote_dir remote qremote_dir remote_cmd
  local_dir="$1"
  remote_dir="$2"
  remote="$(ssh_target)"
  qremote_dir="$(shell_quote "$remote_dir")"
  remote_cmd="$(cat <<EOF
set -e
mkdir -p $qremote_dir
find $qremote_dir -mindepth 1 -maxdepth 1 -exec rm -rf {} +
tar -xzf - -C $qremote_dir
EOF
)"

  if [ "$DRY_RUN" = "1" ]; then
    log "dry-run upload $local_dir -> $remote:$remote_dir"
    return 0
  fi

  local -a args=()
  while IFS= read -r -d '' arg; do args+=("$arg"); done < <(ssh_command_args)
  tar -C "$local_dir" -czf - . | SSHPASS="${CLOUD_COMPUTER_PASSWORD:-}" "${args[@]}" "$remote" "$remote_cmd"
}

cmd_doctor(){
  local ok=1
  echo "== local =="
  have ssh && echo "ssh: ok" || { echo "ssh: missing"; ok=0; }
  have tar && echo "tar: ok" || { echo "tar: missing"; ok=0; }
  if [ -n "${CLOUD_COMPUTER_HOST:-}" ]; then
    echo "host: $CLOUD_COMPUTER_HOST"
  else
    echo "host: missing CLOUD_COMPUTER_HOST"
    ok=0
  fi
  echo "user: $CLOUD_COMPUTER_USER"
  echo "port: $CLOUD_COMPUTER_PORT"
  echo "remote_root: $CLOUD_COMPUTER_REMOTE_ROOT"
  [ -z "${CLOUD_COMPUTER_SSH_KEY:-}" ] || echo "ssh_key: $(expand_path "$CLOUD_COMPUTER_SSH_KEY")"
  if [ -n "${CLOUD_COMPUTER_PASSWORD:-}" ]; then
    if have sshpass; then echo "password_auth: configured (sshpass ok)"
    else echo "password_auth: configured but sshpass missing"; ok=0; fi
  fi

  if [ "$ok" = "1" ]; then
    echo
    echo "== remote =="
    run_remote 'set +e; hostname; uname -a; command -v docker >/dev/null && docker --version || echo "docker: missing"; docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || echo "compose: missing"; test -w "$(dirname '"$(shell_quote "$CLOUD_COMPUTER_REMOTE_ROOT")"')" && echo "remote root parent: writable" || echo "remote root parent: may need sudo or another CLOUD_COMPUTER_REMOTE_ROOT"'
  fi
  [ "$ok" = "1" ] || exit 1
}

cmd_run(){
  [ $# -gt 0 ] || die "run needs a remote command"
  run_remote "$*"
}

cmd_deploy_static(){
  local local_dir domain slug site_dir address block
  local_dir="${1:-}"
  domain="${2:-${CLOUD_COMPUTER_DOMAIN:-}}"
  [ -n "$local_dir" ] || die "deploy-static needs a local directory"
  [ -d "$local_dir" ] || die "not a directory: $local_dir"
  [ -f "$local_dir/index.html" ] || warn "$local_dir has no index.html; Caddy will still serve files"

  slug="$(slugify "${domain:-$(basename "$local_dir")}")"
  [ -n "$slug" ] || slug="site"
  site_dir="$CLOUD_COMPUTER_REMOTE_ROOT/sites/$slug/public"
  address="${domain:-:80}"

  ensure_proxy
  upload_static "$local_dir" "$site_dir"

  block="$(cat <<EOF
# BEGIN cloud-computer site $slug
$address {
  root * /srv/sites/$slug/public
  encode zstd gzip
  file_server
}
# END cloud-computer site $slug
EOF
)"
  update_caddy_block "$slug" "$block"
  compose_up

  if [ -n "$domain" ]; then
    log "deployed. Configure DNS yourself: $domain A/AAAA -> cloud computer public IP; then open https://$domain"
  else
    log "deployed default site. Open http://${CLOUD_COMPUTER_HOST}/"
  fi
}

normalize_upstream(){
  local upstream="$1"
  case "$upstream" in
    http://*|https://*) printf '%s\n' "$upstream" ;;
    *:*) printf 'http://%s\n' "$upstream" ;;
    *[!0-9]*) die "upstream must be a port, host:port, or URL" ;;
    *) printf 'http://127.0.0.1:%s\n' "$upstream" ;;
  esac
}

cmd_expose_service(){
  local name domain upstream normalized slug block
  name="${1:-}"
  domain="${2:-}"
  upstream="${3:-}"
  [ -n "$name" ] || die "expose-service needs a service name"
  [ -n "$domain" ] || die "expose-service needs a domain"
  [ -n "$upstream" ] || die "expose-service needs an upstream, e.g. 3000"
  normalized="$(normalize_upstream "$upstream")"
  slug="$(slugify "$name-$domain")"
  [ -n "$slug" ] || slug="service"

  ensure_proxy
  block="$(cat <<EOF
# BEGIN cloud-computer site $slug
$domain {
  encode zstd gzip
  reverse_proxy $normalized
}
# END cloud-computer site $slug
EOF
)"
  update_caddy_block "$slug" "$block"
  compose_up
  log "reverse proxy configured. Configure DNS yourself: $domain A/AAAA -> cloud computer public IP; then open https://$domain"
}

cmd_status(){
  local qroot prefix
  qroot="$(shell_quote "$CLOUD_COMPUTER_REMOTE_ROOT")"
  prefix="$(remote_compose_prefix)"
  run_remote "$(cat <<EOF
set -e
cd $qroot
$prefix
\$COMPOSE ps
EOF
)"
}

cmd_logs(){
  run_remote "docker logs --tail 120 $(shell_quote "$CLOUD_COMPUTER_CADDY_CONTAINER") 2>&1 || true"
}

case "$CMD" in
  help|-h|--help) usage ;;
  doctor) cmd_doctor "$@" ;;
  ssh) ssh_interactive "$@" ;;
  run) cmd_run "$@" ;;
  deploy-static) cmd_deploy_static "$@" ;;
  expose-service) cmd_expose_service "$@" ;;
  status) cmd_status "$@" ;;
  logs) cmd_logs "$@" ;;
  *) die "unknown command: $CMD" ;;
esac
