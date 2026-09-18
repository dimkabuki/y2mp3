#!/usr/bin/env bash
# Called only after the release workflow's quality and package jobs pass.
set -euo pipefail

fail() { echo "ERROR: $*" >&2; exit 1; }

if [[ "$GITHUB_EVENT_NAME" == workflow_dispatch ]]; then
  [[ "${RELEASE_ACTION:-}" == 'Publish release' ]] || fail 'Publishing was not selected.'
  [[ "$GITHUB_REF" == "refs/heads/$DEFAULT_BRANCH" ]] || fail 'Publish from the default branch.'
elif [[ "$GITHUB_EVENT_NAME" != push || "$GITHUB_REF" != refs/tags/v* ]]; then
  fail 'Unsupported release event.'
fi

[[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" ]] || fail 'Checkout differs from the tested commit.'
version="$(dpkg-deb --field dist/y2mp3.deb Version)"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail 'Invalid package version.'
tag="v$version"
if [[ "$GITHUB_EVENT_NAME" == push ]]; then
  [[ "$GITHUB_REF" == "refs/tags/$tag" ]] || fail 'Tag and package versions differ.'
fi
(cd dist && sha256sum --check SHA256SUMS)

# checkout fetches all tags. Never move an existing tag or replace release assets.
tag_exists=false
if git show-ref --verify --quiet "refs/tags/$tag"; then
  tag_exists=true
  [[ "$(git rev-parse "$tag^{commit}")" == "$GITHUB_SHA" ]] || fail 'Tag points to another commit.'
elif [[ "$GITHUB_EVENT_NAME" == push ]]; then
  fail 'Pushed tag is missing from checkout.'
fi
if gh release view "$tag" --repo "$GH_REPO" >/dev/null 2>&1; then
  fail "Release $tag already exists. Increment the project version for a new release."
fi
if [[ "$tag_exists" == false ]]; then
  # Atomic create fails if another actor created the tag; no force updates.
  gh api --method POST "repos/$GH_REPO/git/refs" \
    -f "ref=refs/tags/$tag" -f "sha=$GITHUB_SHA"
fi
gh release create "$tag" --repo "$GH_REPO" --verify-tag --generate-notes \
  --title "y2mp3 $tag" ./dist/y2mp3.deb ./dist/SHA256SUMS

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  printf 'Download: [y2mp3.deb](https://github.com/%s/releases/download/%s/y2mp3.deb)\n' \
    "$GH_REPO" "$tag" >> "$GITHUB_STEP_SUMMARY"
fi
