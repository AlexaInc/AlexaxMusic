#!/usr/bin/env bash
# Install the exact AlexaInc/ytdlgo release used by this project.
set -euo pipefail

VERSION="${YTDLGO_VERSION:-1.0.0}"
INSTALL_DIR="${1:-$(pwd)/bin}"
BASE_URL="https://github.com/AlexaInc/ytdlgo/releases/download/${VERSION}"

# GitHub release 1.0.0 publishes Linux x86-64 executables only.
case "$(uname -m)" in
  x86_64|amd64) ;;
  *)
    echo "ytdlgo ${VERSION} has no release binary for $(uname -m); an x86-64 host is required." >&2
    exit 1
    ;;
esac

if [[ "$VERSION" != "1.0.0" ]]; then
  echo "Unsupported YTDLGO_VERSION=${VERSION}. This installer is checksum-pinned to 1.0.0." >&2
  exit 1
fi

YTDL_SHA256="${YTDLGO_YTDL_SHA256:-26c6517d19793f06a461564badafde00a84b3e0603fadd406a48324183c1387a}"
XET_SHA256="${YTDLGO_XET_SHA256:-e11684ee5ea9b787329e8ef1da1ad459a41d226bf351648b36eafed96b4f0420}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

for asset in ytdl xet-upload; do
  echo "Downloading ${BASE_URL}/${asset}"
  curl --fail --show-error --location \
    --retry 5 --retry-all-errors --connect-timeout 20 \
    --output "${tmp_dir}/${asset}" "${BASE_URL}/${asset}"
done

printf '%s  %s\n' "$YTDL_SHA256" "${tmp_dir}/ytdl" | sha256sum --check --status
printf '%s  %s\n' "$XET_SHA256" "${tmp_dir}/xet-upload" | sha256sum --check --status

mkdir -p "$INSTALL_DIR"
install -m 0755 "${tmp_dir}/ytdl" "${INSTALL_DIR}/ytdl"
install -m 0755 "${tmp_dir}/xet-upload" "${INSTALL_DIR}/xet-upload"

echo "Installed ytdlgo ${VERSION} in ${INSTALL_DIR} (checksums verified)."
