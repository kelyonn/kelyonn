#!/usr/bin/env bash
# fires the profile refresh immediately. needs a classic PAT with `repo` scope
# exported as GH_PAT. run it right after you change your pinned repos.
curl -sS -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GH_PAT:?export GH_PAT first}" \
  https://api.github.com/repos/kelyonn/kelyonn/dispatches \
  -d '{"event_type":"refresh"}' \
  && echo "refresh queued"
