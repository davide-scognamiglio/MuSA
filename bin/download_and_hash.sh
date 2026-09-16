#!/usr/bin/env bash
set -euo pipefail

# Usage:
# sha=$(download_and_compute_sha "https://example.com/file.gz" curl "file.gz")
# echo "SHA256: $sha"

download_and_compute_sha() {
    local url="$1"
    local method="${2:-wget}"
    local out="$3"

    echo "[INFO] URL: $url" >&2
    echo "[INFO] METHOD: $method" >&2
    echo "[INFO] OUTPUT: $out" >&2

    # ---------------------------
    # Download
    # ---------------------------
    echo "[INFO] Starting download..." >&2
    local status=0
    if [ "$method" == "wget" ]; then
        wget --no-check-certificate -c --tries=5 --timeout=60 "$url" -O "$out" || status=$?
    elif [ "$method" == "curl" ]; then
        curl -L --fail --retry 5 --retry-delay 5 --retry-max-time 300 -o "$out" "$url" || status=$?
    elif [ "$method" == "gdown" ]; then
        if ! command -v gdown >/dev/null 2>&1; then
            echo "[ERROR] gdown not found in PATH" >&2
            return 1
        fi
        gdown --no-cookies --id "$url" -O "$out" || status=$?
    else
        echo "[ERROR] Unknown method: $method" >&2
        return 1
    fi

    # Check the download explicitly rather than relying on `set -e`: this function runs inside a
    # command substitution (`sha=$(download_and_compute_sha ...)`), where a failing command does not
    # reliably abort the calling script. Without these checks a blocked or refused download left a
    # 0-byte file that was hashed, recorded in the manifest and installed as if it were the database.
    if [ "$status" -ne 0 ]; then
        echo "[ERROR] Download of $url failed ($method exit status $status)" >&2
        return 1
    fi
    if [ ! -s "$out" ]; then
        echo "[ERROR] Download of $url produced no data ($out is missing or empty)" >&2
        return 1
    fi

    # ---------------------------
    # Compute SHA256
    # ---------------------------
    echo "[INFO] Computing SHA256..." >&2
    if ! command -v sha256sum >/dev/null 2>&1; then
        echo "[ERROR] sha256sum not found in PATH" >&2
        return 1
    fi

    local sha
    sha=$(sha256sum "$out" | awk '{print $1}')
    echo "[INFO] SHA256 of $out: $sha" >&2

    # Return SHA256
    echo "$sha"
}

# ---------------------------------------------------------------------------------------
# install_into_data <source_dir> <target_dir>
#
# Move a freshly downloaded directory out of the task work dir and into the data directory,
# which every setup task sees bind-mounted read-write at /data (nextflow.config, docker/
# podman/singularity containerOptions).
#
# Not publishDir: publishDir only publishes files a process DECLARES as outputs, so a folder
# built by the script and named only in `pattern:` is silently never published -- the bug that
# left every fresh setup between 2026-07-14 and 1.2 with its downloads stranded in the work
# dir. Declaring these trees as outputs instead would also copy tens of GB a second time
# (26 GB VEP cache, 45 GB dbNSFP), and publishDir could not handle the cache's nested path.
#
# The move lands on a staging name first and is renamed into place afterwards, so an
# interrupted install cannot leave a half-populated directory where the next run's
# should_skip_module would mistake it for a complete one.
# ---------------------------------------------------------------------------------------
install_into_data() {
    local source_dir="$1"
    local target_dir="$2"

    if [[ ! -d "$source_dir" ]]; then
        echo "[ERROR] install_into_data: $source_dir does not exist" >&2
        return 1
    fi

    local staging="${target_dir}.incoming"
    mkdir -p "$(dirname "$target_dir")"
    rm -rf "$staging"
    mv "$source_dir" "$staging"
    rm -rf "$target_dir"
    mv "$staging" "$target_dir"
    echo "[INFO] installed $target_dir"
}
