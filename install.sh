#!/usr/bin/env bash
# One-command deploy on a clean Ubuntu (22.04+). Safe to re-run. See docs/adr/0008-deployment.md.
set -euo pipefail

MIN_COMPOSE_VERSION=2.39.0  # build `provenance` in compose.yaml

log() { printf '\n==> %s\n' "$*"; }
die() {
  printf '\nError: %s\n' "$*" >&2
  exit 1
}
warn() { printf '\nWarning: %s\n' "$*" >&2; }

# Root runs commands directly; other users go through sudo.
SUDO=()
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null || die "Run as root or install sudo."
  SUDO=(sudo)
fi

# Docker's official apt steps: https://docs.docker.com/engine/install/ubuntu/
install_docker() {
  # shellcheck source=/dev/null
  . /etc/os-release
  [ "${ID:-}" = ubuntu ] || die "Docker is missing. Auto-install supports Ubuntu only: install Docker Engine with the compose plugin, then re-run."

  log "Installing Docker Engine from Docker's apt repository"
  local apt=("${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a apt-get -y -q)
  "${apt[@]}" update
  "${apt[@]}" install ca-certificates curl
  "${SUDO[@]}" install -m 0755 -d /etc/apt/keyrings
  "${SUDO[@]}" curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  "${SUDO[@]}" chmod a+r /etc/apt/keyrings/docker.asc
  "${SUDO[@]}" tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  "${apt[@]}" update
  "${apt[@]}" install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

# Use plain `docker` if this user can reach the daemon, else `sudo docker`.
# We don't add the user to the docker group: it is root-equivalent and needs a re-login anyway.
DOCKER=(docker)
pick_docker_command() {
  if docker info >/dev/null 2>&1; then
    DOCKER=(docker)
  elif [ ${#SUDO[@]} -gt 0 ] && sudo docker info >/dev/null 2>&1; then
    DOCKER=(sudo docker)
  else
    die "Docker daemon is not running. Start it (sudo systemctl start docker) and re-run."
  fi
}

check_compose() {
  local version
  version=$("${DOCKER[@]}" compose version --short 2>/dev/null) ||
    die "Docker Compose plugin is missing. Install docker-compose-plugin and re-run."
  version=${version#v}
  # sort -V -C succeeds only if the minimum sorts before (or equals) the installed version.
  printf '%s\n%s\n' "$MIN_COMPOSE_VERSION" "$version" | sort -V -C ||
    die "Docker Compose $version is too old: need $MIN_COMPOSE_VERSION or newer."
}

random_secret() { od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; }

# Never overwrite .env: the database and storage keep the passwords from the first start.
create_env() {
  if [ -f .env ]; then
    log "Keeping existing .env"
    return
  fi
  log "Creating .env with random secrets"
  local line
  (
    umask 077
    while IFS= read -r line || [ -n "$line" ]; do
      if [[ $line == *=change-me ]]; then
        printf '%s=%s\n' "${line%%=*}" "$(random_secret)"
      else
        printf '%s\n' "$line"
      fi
    done <.env.example >.env.tmp
  )
  mv .env.tmp .env # atomic: a failed run never leaves a half-written .env behind
}

# The demo videos aren't in git, and the backend has no internet (ADR 0008). Without them the site
# still works: the seed skips the missing ones, and a re-run adds them.
download_demo_videos() {
  log "Downloading the demo videos"
  if ! command -v python3 >/dev/null; then
    warn "python3 is missing, so there are no demo videos. Install it and re-run to add them."
    return
  fi
  python3 demo-data/download.py || warn "Could not download the demo videos. Re-run later to add them."
}

start_stack() {
  log "Building and starting the stack (the first run takes a few minutes)"
  "${DOCKER[@]}" compose up -d --build --wait ||
    die "Some services did not start. Check: ${DOCKER[*]} compose ps, then ${DOCKER[*]} compose logs <service>"
}

# --wait checks each container, not the nginx -> api path. After api is recreated,
# nginx needs a few seconds to resolve its new address.
wait_for_site() {
  local _
  for _ in $(seq 30); do
    "${DOCKER[@]}" compose exec -T nginx wget -q -O /dev/null http://127.0.0.1:8080/api/health 2>/dev/null && return
    sleep 1
  done
  die "The site does not answer. Check: ${DOCKER[*]} compose logs nginx api"
}

# Not part of `up`: `up --wait` fails on a job that exits fast with nothing depending on it.
seed_demo_data() {
  log "Adding the demo data (the first run waits for the worker to process the videos)"
  # --no-deps: `up --wait` has started them all; a plain `run` would run the migrate job again.
  "${DOCKER[@]}" compose run --rm --no-deps seed ||
    die "The demo data was not added. Check: ${DOCKER[*]} compose logs worker; re-run ./install.sh to go on"
}

print_summary() {
  local port host url password
  port=$(sed -n 's/^HTTP_PORT=//p' .env)
  password=$(sed -n 's/^DEMO_PASSWORD=//p' .env)
  host=$(hostname -I 2>/dev/null | awk '{print $1}')
  url="http://${host:-localhost}"
  [ "${port:-80}" = 80 ] || url="$url:$port"

  log "ViTube is running"
  printf '  Site:      %s/\n' "$url"
  printf '  API docs:  %s/docs\n' "$url"
  printf '  Demo:      admin@example.com (admin), moderator@example.com (moderator),\n'
  printf '             anna@example.com (user); all accounts are in README.md\n'
  printf '  Password:  %s\n' "$password"
  printf '  Stop:      %s compose down\n' "${DOCKER[*]}"
}

main() {
  cd "$(dirname "$0")"
  command -v docker >/dev/null || install_docker
  pick_docker_command
  check_compose
  create_env
  download_demo_videos
  start_stack
  wait_for_site
  seed_demo_data
  print_summary
}

# Run only when executed, not when sourced (tests call single functions).
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  main "$@"
fi
