#!/usr/bin/env bash
# bootstrap.sh: take a fresh Mac or Debian-family Linux machine to a running
# Claude Code with the lastmilefirst plugin installed, then print what to do by
# hand next. It knows nothing about any org, workspace, or account; the one
# private thing a new machine needs (the repository holding your workspace
# CLAUDE.md) enters in the printed handoff, by your hand.
#
# Fetch and run (pin the tag you trust):
#   curl -fsSL https://raw.githubusercontent.com/GruntworkAI/gruntwork-lastmilefirst/<tag>/plugins/lastmilefirst/skills/organize-device/scripts/bootstrap.sh | bash
# Or run it as a file:
#   bash bootstrap.sh
#
# Every step checks before it acts, so a rerun on a set-up machine changes
# nothing. It never logs in, never makes or uploads a key, and never reads a
# secret.
#
# The whole script is one function called on the last line, so when it is
# piped into bash nothing runs until the full text has arrived, and a child
# process that reads stdin cannot swallow the rest of the script.

set -euo pipefail

# ---------------------------------------------------------------------------
# Baseline tools, one row per tool: name, command to look for, Homebrew
# formula, apt package. The plugin's own scripts need all of these.
# ---------------------------------------------------------------------------
BASELINE_TOOLS="
git      git      git      git
gh       gh       gh       gh
jq       jq       jq       jq
python3  python3  python   python3
node     node     node     nodejs
ripgrep  rg       ripgrep  ripgrep
"

# The public marketplace this script installs from. These are the only
# coordinates it names.
MARKETPLACE_SOURCE="GruntworkAI/gruntwork-lastmilefirst"
MARKETPLACE_NAME="gruntwork-lastmilefirst"
PLUGIN_ID="lastmilefirst@gruntwork-lastmilefirst"

# Claude Code native installer for macOS, Linux, and WSL, verified 2026-10-09
# against https://code.claude.com/docs/en/setup (the old
# docs.claude.com/en/docs/claude-code/setup address redirects there). It puts
# the launcher at ~/.local/bin/claude.
CLAUDE_INSTALLER_URL="https://claude.ai/install.sh"

# Homebrew's documented installer, from https://brew.sh.
HOMEBREW_INSTALLER_URL="https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"

# Where GitHub documents its own apt repository for gh. Some distributions
# package a gh too old for the plugin (see GH_MIN_MAJOR below).
GH_APT_REPO_URL="https://github.com/cli/cli/blob/trunk/docs/install_linux.md"

# gh 2.40 added `gh auth token --user`, which the device audit and the
# session-start check use to look up each account's login.
GH_MIN_MAJOR=2
GH_MIN_MINOR=40

# Fetch limits for the installer downloads, in seconds.
CURL_LIMITS="--connect-timeout 15 --max-time 300"

PLATFORM=""
SUDO=""
WARNINGS=""
PLUGIN_FALLBACK=""

say()  { printf '%s\n' "$*"; }
step() { printf '\n== %s\n' "$*"; }
warn() { WARNINGS="${WARNINGS}  - $*"$'\n'; printf 'WARNING: %s\n' "$*" >&2; }
die()  { printf 'STOP: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

usage() {
  cat <<'USAGE'
Usage: bootstrap.sh [--help]

Installs a package manager (Homebrew on macOS), the baseline tools (git, gh,
jq, python3, node, ripgrep), Claude Code, and the lastmilefirst plugin, then
prints the steps that need you. Safe to rerun.
USAGE
}

# Read stdin from the terminal when there is one, so installers that ask a
# question (a sudo password, a confirmation) can ask it even when this script
# arrived through a pipe. Otherwise read nothing.
from_tty() {
  if [ -r /dev/tty ] && { : </dev/tty; } 2>/dev/null; then
    "$@" </dev/tty
  else
    "$@" </dev/null
  fi
}

# ---------------------------------------------------------------------------
# Step 1: platform
# ---------------------------------------------------------------------------
detect_platform() {
  step "Platform"
  local kernel
  kernel="$(uname -s)"
  case "$kernel" in
    Darwin)
      PLATFORM="macos"
      ;;
    Linux)
      if [ -r /proc/version ] && grep -qi microsoft /proc/version \
         && ! grep -qi wsl /proc/version; then
        die "unsupported; use WSL2 and run this inside it."
      fi
      if have apt-get; then
        PLATFORM="apt"
      else
        local wanted="an unknown package manager"
        if have dnf; then wanted="dnf"
        elif have yum; then wanted="yum"
        elif have pacman; then wanted="pacman"
        elif have zypper; then wanted="zypper"
        elif have apk; then wanted="apk"
        fi
        die "this Linux uses ${wanted}; this script supports apt (Debian, Ubuntu, and their relatives) only."
      fi
      ;;
    MSYS*|MINGW*|CYGWIN*)
      die "unsupported; use WSL2 and run this inside it."
      ;;
    *)
      die "unsupported platform '${kernel}'. Supported: macOS, and Linux with apt."
      ;;
  esac
  say "Detected: ${PLATFORM} ($(uname -m))"
}

# ---------------------------------------------------------------------------
# Step 1b: package manager ready
# ---------------------------------------------------------------------------
load_brew_env() {
  local candidate
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew /home/linuxbrew/.linuxbrew/bin/brew; do
    if [ -x "$candidate" ]; then
      eval "$("$candidate" shellenv)"
      return 0
    fi
  done
  return 1
}

# Put Homebrew's bin directory first on PATH for the rest of the run, so its
# current python3 wins over the older /usr/bin/python3 that macOS ships.
prefer_brew_path() {
  local prefix
  prefix="$(brew --prefix 2>/dev/null)" || return 0
  PATH="${prefix}/bin:${PATH}"
  export PATH
  hash -r
}

prepare_package_manager() {
  step "Package manager"
  if [ "$PLATFORM" = "macos" ]; then
    if have brew || load_brew_env; then
      prefer_brew_path
      say "Homebrew present: $(command -v brew)"
    else
      say "Installing Homebrew (it may ask for your password and to press RETURN)."
      local installer
      # shellcheck disable=SC2086  # CURL_LIMITS is split into flags on purpose
      installer="$(curl -fsSL $CURL_LIMITS "$HOMEBREW_INSTALLER_URL")" \
        || die "could not download the Homebrew installer; check the network and rerun."
      from_tty /bin/bash -c "$installer" \
        || die "the Homebrew installer did not finish; check the network and rerun."
      load_brew_env || die "Homebrew installed but brew was not found; open a new terminal and rerun."
      prefer_brew_path
      say "Homebrew installed. Add it to your shell profile as Homebrew's own output describes."
    fi
  else
    if [ "$(id -u)" -ne 0 ]; then
      have sudo || die "not running as root and sudo is not installed."
      SUDO="sudo"
    fi
    say "Refreshing the apt package list."
    # shellcheck disable=SC2086  # SUDO is empty or one word, on purpose
    from_tty $SUDO apt-get update \
      || warn "apt-get update did not finish, so packages may come from an old list; check the network, then run 'sudo apt-get update' and rerun."
  fi
}

# ---------------------------------------------------------------------------
# Step 2: baseline tools
# ---------------------------------------------------------------------------
install_package() {
  local brew_pkg="$1" apt_pkg="$2"
  if [ "$PLATFORM" = "macos" ]; then
    brew install "$brew_pkg" </dev/null
  else
    # shellcheck disable=SC2086  # SUDO is empty or one word, on purpose
    from_tty $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y "$apt_pkg"
  fi
}

# The audit reads TOML with the standard library's tomllib, which needs
# Python 3.11 or newer.
python_ok() {
  have python3 && python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'
}

python_version() {
  python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo unknown
}

ensure_python() {
  local brew_pkg="$1" apt_pkg="$2"
  if python_ok; then
    say "present: python3 $(python_version)"
    return 0
  fi
  if [ "$PLATFORM" = "macos" ]; then
    if have python3; then
      say "python3 $(python_version) is older than 3.11; installing Homebrew's python"
    else
      say "installing: python3"
    fi
    if install_package "$brew_pkg" "$apt_pkg"; then
      prefer_brew_path
    fi
    if python_ok; then
      say "using: $(command -v python3) $(python_version)"
    else
      warn "python3 3.11 or newer is still not first on PATH (found $(python_version)); the device audit will refuse to run below 3.11. Run 'brew install python' and put $(brew --prefix 2>/dev/null || echo Homebrew)/bin first on PATH."
    fi
    return 0
  fi
  if ! have python3; then
    say "installing: python3"
    install_package "$brew_pkg" "$apt_pkg" || true
    hash -r
  fi
  if python_ok; then
    say "present: python3 $(python_version)"
  elif have python3; then
    warn "python3 is $(python_version); the device audit will refuse to run below 3.11. Install a newer Python by hand: this distribution's python3.12 package if it has one (sudo apt-get install python3.12), or the deadsnakes PPA on Ubuntu."
  else
    warn "could not install python3; the device audit needs Python 3.11 or newer."
  fi
}

# gh prints "gh version 2.23.0 (2023-02-14)"; this prints "2.23".
gh_version() {
  gh --version 2>/dev/null | sed -n 's/^gh version \([0-9][0-9]*\.[0-9][0-9]*\).*/\1/p' | head -n 1 || true
}

# Succeeds when gh is at least GH_MIN_MAJOR.GH_MIN_MINOR, or when its version
# cannot be read (then there is nothing to warn about with confidence).
gh_new_enough() {
  local version major minor
  version="$(gh_version)"
  [ -n "$version" ] || return 0
  major="${version%%.*}"
  minor="${version#*.}"
  if [ "$major" -gt "$GH_MIN_MAJOR" ]; then return 0; fi
  if [ "$major" -lt "$GH_MIN_MAJOR" ]; then return 1; fi
  [ "$minor" -ge "$GH_MIN_MINOR" ]
}

check_gh_version() {
  [ "$PLATFORM" = "apt" ] || return 0
  have gh || return 0
  if ! gh_new_enough; then
    warn "gh is $(gh_version), older than ${GH_MIN_MAJOR}.${GH_MIN_MINOR}, which the device audit needs to look up each account's login. Install a current gh from GitHub's apt repository (${GH_APT_REPO_URL})."
  fi
}

install_baseline() {
  step "Baseline tools"
  local name cmd brew_pkg apt_pkg
  while read -r name cmd brew_pkg apt_pkg; do
    [ -n "$name" ] || continue
    if [ "$name" = "python3" ]; then
      ensure_python "$brew_pkg" "$apt_pkg"
      continue
    fi
    if have "$cmd"; then
      say "present: ${name}"
      continue
    fi
    say "installing: ${name}"
    if ! install_package "$brew_pkg" "$apt_pkg"; then
      if [ "$name" = "git" ]; then
        die "could not install git, which the plugin install needs."
      fi
      if [ "$name" = "gh" ] && [ "$PLATFORM" = "apt" ]; then
        warn "could not install gh from this distribution's packages; add GitHub's apt repository (${GH_APT_REPO_URL}) and install gh."
      else
        warn "could not install ${name}; install it by hand."
      fi
    fi
  done <<TABLE
$BASELINE_TOOLS
TABLE
  check_gh_version
}

# ---------------------------------------------------------------------------
# Step 3: Claude Code
# ---------------------------------------------------------------------------
install_claude() {
  step "Claude Code"
  case ":${PATH}:" in
    *":${HOME}/.local/bin:"*) ;;
    *) PATH="${HOME}/.local/bin:${PATH}"; export PATH ;;
  esac
  if have claude; then
    say "present: $(claude --version 2>/dev/null || echo claude)"
    return 0
  fi
  say "Installing Claude Code with the native installer."
  local installer
  # shellcheck disable=SC2086  # CURL_LIMITS is split into flags on purpose
  installer="$(curl -fsSL $CURL_LIMITS "$CLAUDE_INSTALLER_URL")" \
    || die "could not download the Claude Code installer; check the network and rerun."
  bash -c "$installer" </dev/null \
    || die "the Claude Code installer did not finish; check the network and rerun."
  have claude || die "Claude Code installed but claude is not on PATH; open a new terminal and rerun."
  say "installed: $(claude --version 2>/dev/null || echo claude)"
}

# ---------------------------------------------------------------------------
# Step 4: marketplace and plugin
# ---------------------------------------------------------------------------
# Both subcommands take no prompt for this marketplace (it declares no install
# command), and stdin is closed so nothing can wait on a question. If either
# fails for any reason, the handoff prints the two commands to run by hand.
install_plugin() {
  step "lastmilefirst plugin"
  if ! have jq; then
    PLUGIN_FALLBACK=1
    warn "jq is missing, so the plugin step was skipped; run the two commands in the handoff."
    return 0
  fi

  local known
  known="$(claude plugin marketplace list --json </dev/null 2>/dev/null \
    | jq -r --arg n "$MARKETPLACE_NAME" '[.[] | select(.name == $n)] | length' 2>/dev/null || echo error)"
  if [ "$known" = "error" ] || [ -z "$known" ]; then
    PLUGIN_FALLBACK=1
    warn "could not list marketplaces; run the two commands in the handoff."
    return 0
  fi
  if [ "$known" -gt 0 ]; then
    say "marketplace present: ${MARKETPLACE_NAME}"
  else
    say "adding marketplace: ${MARKETPLACE_SOURCE}"
    if ! claude plugin marketplace add "$MARKETPLACE_SOURCE" </dev/null; then
      PLUGIN_FALLBACK=1
      warn "marketplace add did not complete; run the two commands in the handoff."
      return 0
    fi
  fi

  local installed
  installed="$(claude plugin list --json </dev/null 2>/dev/null \
    | jq -r --arg id "$PLUGIN_ID" '[.[] | select(.id == $id)] | length' 2>/dev/null || echo error)"
  if [ "$installed" = "error" ] || [ -z "$installed" ]; then
    PLUGIN_FALLBACK=1
    warn "could not list plugins; run the two commands in the handoff."
    return 0
  fi
  if [ "$installed" -gt 0 ]; then
    say "plugin present: ${PLUGIN_ID}"
  else
    say "installing plugin: ${PLUGIN_ID}"
    if ! claude plugin install "$PLUGIN_ID" </dev/null; then
      PLUGIN_FALLBACK=1
      warn "plugin install did not complete; run the two commands in the handoff."
    fi
  fi
}

# ---------------------------------------------------------------------------
# Step 5: handoff
# ---------------------------------------------------------------------------
print_handoff() {
  local config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/lastmilefirst"
  local n=1

  step "Done. The rest needs you."

  if [ -n "$WARNINGS" ]; then
    say ""
    say "Warnings from this run:"
    printf '%s' "$WARNINGS"
  fi

  say ""
  if [ -n "$PLUGIN_FALLBACK" ]; then
    say "${n}. Install the plugin:"
    say "     claude plugin marketplace add ${MARKETPLACE_SOURCE}"
    say "     claude plugin install ${PLUGIN_ID}"
    n=$((n + 1))
  fi

  if [ -f "${HOME}/.ssh/id_ed25519" ]; then
    say "${n}. SSH key: ~/.ssh/id_ed25519 already exists; make sure it is added on GitHub."
  else
    say "${n}. Make one SSH key for your default GitHub account (a new key for each device):"
    say "     ssh-keygen -t ed25519 -C \"<your account email>\" -f ~/.ssh/id_ed25519"
  fi
  n=$((n + 1))

  say "${n}. Add it on GitHub: log in with gh, then upload the public half"
  say "   (or paste it at https://github.com/settings/keys):"
  say "     gh auth login"
  say "     gh auth refresh -h github.com -s admin:public_key"
  say "     gh ssh-key add ~/.ssh/id_ed25519.pub --title \"<this device>\""
  n=$((n + 1))

  say "${n}. Clone the repository that holds your workspace CLAUDE.md into your workspace root:"
  say "     git clone git@github.com:<owner>/<repo>.git <workspace root>"
  n=$((n + 1))

  say "${n}. If you carried a device.toml over from another machine, put it in place:"
  say "     mkdir -p \"${config_dir}\" && cp <path to>/device.toml \"${config_dir}/\""
  n=$((n + 1))

  say "${n}. Start Claude in your workspace root and run the device audit:"
  say "     claude"
  say "     /run-organize-device"
  say ""
  say "If claude is not found in a new terminal, add ~/.local/bin to your PATH."
}

main() {
  case "${1:-}" in
    -h|--help) usage; return 0 ;;
    "") ;;
    *) usage >&2; die "unknown argument: $1" ;;
  esac
  detect_platform
  prepare_package_manager
  install_baseline
  install_claude
  install_plugin
  print_handoff
}

main "$@"
