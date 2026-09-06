# setup

drop everything into your `kelyonn/kelyonn` repo, keeping the folder structure:

    README.md
    SETUP.md
    refresh.sh
    assets/banner-dark.svg
    assets/banner-light.svg
    scripts/generate.py
    scripts/config.json
    .github/workflows/readme.yml

## 1. edit config

`scripts/config.json` is the only file you touch by hand. bio, stack, socials,
footer. everything else (pinned repos, descriptions, stars, languages, accent
colours) is pulled live from the github api at run time.

## 2. give the workflow write access

settings -> actions -> general -> workflow permissions -> read and write.
without this the bot cannot push the regenerated svgs back.

## 3. run it once

actions tab -> "refresh profile" -> run workflow.

the svgs shipped here contain placeholder repo data. the first run overwrites
them with your real pinned repos and fills the link row inside README.md.
github strips anchors out of svgs in profile readmes, which is why the links
live in markdown below the image instead of inside it.

## triggers

- hourly cron at :23
- the run workflow button
- any push to `scripts/`
- `repository_dispatch` with event type `refresh`, for instant updates

for the instant one: make a classic PAT with `repo` scope, then

    export GH_PAT=ghp_xxx
    ./refresh.sh

run it right after you change your pins. works as an ios shortcut too.

## local preview

    python scripts/generate.py --sample     # fake repos, no token needed
    GITHUB_TOKEN=ghp_xxx python scripts/generate.py

## notes

- free on public repos. unlimited actions minutes, one graphql query per run.
- github disables scheduled workflows after 60 days of no repo activity. the
  bot commit resets that clock, but only when something actually changed.
  re-enable from the actions tab if it ever goes quiet.
- accent colours come from each repo's github language colour, nudged toward
  the theme background until they clear a 3.2:1 contrast check. that is why
  rust tan and shell green darken in the light banner.
