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
        # Large databases (dbNSFP is ~47 GB) come from servers that drop long connections every few
        # minutes; -c resumes from the byte reached, so allow many resumes. A Nextflow-level retry
        # would instead restart from zero in a new work directory.
        wget --no-check-certificate -c --tries=100 --waitretry=30 --retry-connrefused --timeout=60 \
            "$url" -O "$out" || status=$?
    elif [ "$method" == "curl" ]; then
        # Retry here, not with curl's --retry: that one discards the bytes an attempt received and
        # does not retry a transfer cut mid-way. -C - resumes from the bytes already on disk.
        local attempt http_errors=0
        for attempt in $(seq 1 100); do
            status=0
            # --speed-limit/--speed-time: a stalled connection (open, no bytes) would otherwise hang
            # curl forever; abort it after 2 min below 1 kB/s so the loop resumes it.
            curl -L --fail -C - --connect-timeout 60 --speed-limit 1024 --speed-time 120 \
                -o "$out" "$url" || status=$?
            case "$status" in
                0) break ;;
                22)                      # HTTP >= 400: retry a transient 5xx, not a 403/404 forever
                    http_errors=$((http_errors + 1))
                    if [ "$http_errors" -ge 3 ]; then break; fi ;;
                33) rm -f "$out" ;;      # server does not accept ranges: restart from zero
            esac
            echo "[WARN] curl exit status $status (attempt $attempt/100); resuming in 30 s" >&2
            sleep 30
        done
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
    match_data_dir_owner "$target_dir"
    echo "[INFO] installed $target_dir"
}

# ---------------------------------------------------------------------------------------
# match_data_dir_owner <path>...
#
# Give each path, and any directory created between it and /data, to the owner of the data
# dir. The docker and podman profiles run tasks as root (--user root), so anything a task
# installs under /data is otherwise owned by root on the host: the user cannot update or
# delete it without sudo, and Nextflow, which publishes as the launching user, fails with
# "Failed to publish file" when a later step (GEN_DBNSFP_ALIGNED_COLUMNS) writes into it.
# No-op under singularity, where tasks already run as the user.
# ---------------------------------------------------------------------------------------
match_data_dir_owner() {
    local owner path dir
    owner=$(stat -c '%u:%g' /data)
    if [[ "$(id -u)" == "${owner%%:*}" ]]; then
        return 0
    fi
    for path in "$@"; do
        chown -R "$owner" "$path"
        dir=$(dirname "$path")
        while [[ "$dir" != "/data" && "$dir" != "/" ]]; do
            chown "$owner" "$dir"
            dir=$(dirname "$dir")
        done
    done
}
