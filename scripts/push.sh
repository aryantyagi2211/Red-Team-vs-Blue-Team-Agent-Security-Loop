#!/usr/bin/env bash
set -eu

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(dirname "$script_dir")"
remote_file="$repo_root/git_remote.txt"
remote_url=""

while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
        ""|\#*) continue ;;
        *)
            remote_url="$line"
            break
            ;;
    esac
done < "$remote_file"

if [ -z "$remote_url" ]; then
    echo "No remote set in git_remote.txt, skipping push"
    exit 0
fi

if ! git -C "$repo_root" remote get-url origin >/dev/null 2>&1; then
    git -C "$repo_root" remote add origin "$remote_url"
fi

git -C "$repo_root" push -u origin HEAD
