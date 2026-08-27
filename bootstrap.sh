#!/usr/bin/env bash
# Turn this template into a real paper repository.
#
#   ./bootstrap.sh
#
# Names the project, renames the example document, wires up the link back to the
# template, and deletes itself. Run it once, right after cloning or after "Use
# this template" on GitHub.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -f references.bib ] || [ ! -d docs ]; then
  echo "error: run this from the repository root" >&2
  exit 1
fi

# --- portability: BSD sed (macOS) and GNU sed disagree about -i --------------
sed_i() {
  if sed --version >/dev/null 2>&1; then sed -i "$@"; else sed -i '' "$@"; fi
}

# ask <prompt> [default]  — re-asks until non-empty when there is no default.
ask() {
  local prompt="$1" default="${2:-}" reply
  if [ -n "$default" ]; then
    read -r -p "$prompt [$default]: " reply || true
    echo "${reply:-$default}"
  else
    while :; do
      read -r -p "$prompt: " reply || { echo ""; return; }
      [ -n "$reply" ] && { echo "$reply"; return; }
    done
  fi
}

ask_yes_no() {
  local reply
  read -r -p "$1 [y/N]: " reply || true
  case "${reply:-n}" in [yY]*) return 0 ;; *) return 1 ;; esac
}

slugify() {
  echo "$1" | tr '[:upper:] ' '[:lower:]-' | tr -cd '[:alnum:]-' | sed 's/--*/-/g;s/^-//;s/-$//'
}

echo
echo "Paper repository — bootstrap"
echo "----------------------------"
echo

PROJECT_NAME=$(ask "Project name (human readable)" "$(basename "$PWD")")
AUTHOR_NAME=$(ask "Author name" "$(git config user.name 2>/dev/null || echo '')")
AUTHOR_EMAIL=$(ask "Author email" "$(git config user.email 2>/dev/null || echo '')")
AFFILIATION=$(ask "Affiliation" "Institution")

echo
PAPER_TITLE=$(ask "Paper title" "$PROJECT_NAME")
PAPER_SLUG=$(ask "Directory name under docs/" "paper-$(slugify "$PROJECT_NAME")")

echo
echo "The paper's numbers come from a Weights & Biases project."
WANDB_ENTITY=$(ask "W&B entity" "$(git config user.name 2>/dev/null | tr '[:upper:] ' '[:lower:]-' || echo 'your-entity')")
WANDB_PROJECT=$(ask "W&B project" "$(slugify "$PROJECT_NAME")")

echo
CODE_REPO=$(ask "Code repository this paper reports on (URL, or blank)" "the experiment repository")

echo
echo "The template ships a worked example — a two-page paper with a figure and a"
echo "table built from synthetic data committed under data/. It costs nothing to"
echo "keep, and lets you verify the whole chain before pointing it at your runs."
KEEP_EXAMPLE=0
if ask_yes_no "Keep the worked example?"; then KEEP_EXAMPLE=1; fi

YEAR=$(date +%Y)
PROJECT_SLUG=$(slugify "$PROJECT_NAME")
CITE_KEY="$(echo "$AUTHOR_NAME" | awk '{print tolower($NF)}')${YEAR}${PROJECT_SLUG%%-*}"
TEMPLATE_URL=$(sed -n 's/^upstream: *//p' .template-upstream.yml)

# --- link the template history ----------------------------------------------
#
# Done FIRST, while the tree is still pristine and identical to the template.
# "Use this template" copies a tree, not a history: this repository shares no
# commit with the template, so a later `git merge template/main` would refuse as
# unrelated. Record the merge base now — an `ours` merge that changes not one
# file and exists purely so the two histories become relatable.
#
# Inline git rather than `tools/template_sync.py link`, because the environment
# does not exist yet and because that command (rightly) refuses a dirty tree,
# which is exactly what the renaming below is about to create.
#
# See tools/template_sync.py and docs/documentation/README.md.
TEMPLATE_BRANCH=$(sed -n 's/^branch: *//p' .template-upstream.yml 2>/dev/null | head -1)
TEMPLATE_BRANCH=${TEMPLATE_BRANCH:-main}

echo
echo "-> setting the merge=ours driver (per-clone; cannot be committed)"
git config merge.ours.driver true

if [ -n "$TEMPLATE_URL" ]; then
  echo "-> linking the template history ($TEMPLATE_URL)"
  if [ -z "$(git log --oneline -1 2>/dev/null)" ]; then
    git add -A && git commit -qm "Initial commit from paper-template"
  fi
  git remote remove template >/dev/null 2>&1 || true
  if git remote add template "$TEMPLATE_URL" &&
     git fetch -q template "$TEMPLATE_BRANCH" 2>/dev/null; then
    TEMPLATE_BASE=$(git rev-parse "template/$TEMPLATE_BRANCH")
    if git merge-base --is-ancestor "$TEMPLATE_BASE" HEAD 2>/dev/null; then
      # Already relatable — this repository was cloned from the template rather
      # than generated from it, so the merge base exists and an `ours` merge
      # would be an empty commit. Just record the ref.
      git update-ref refs/template/base "$TEMPLATE_BASE"
      echo "   already shares history with the template at ${TEMPLATE_BASE:0:12}"
      TEMPLATE_BASE=""
    fi
    if [ -n "$TEMPLATE_BASE" ]; then
    git merge -s ours --no-commit --allow-unrelated-histories -q "$TEMPLATE_BASE"
    git commit -q --no-verify -m "Link template history at ${TEMPLATE_BASE:0:12}

Establishes the merge base between this paper and the template it was
generated from. Changes no files. See docs/documentation/README.md,
'Staying in sync with the template'.

template-upstream: $TEMPLATE_URL
template-commit: $TEMPLATE_BASE"
    git update-ref refs/template/base "$TEMPLATE_BASE"
    echo "   linked at ${TEMPLATE_BASE:0:12} — 'make template-update' works from here on"
    fi
  else
    echo "   warning: could not reach the template. Link it later with:"
    echo "              make template-link REF=<the template commit you copied>"
  fi
fi

echo
echo "-> renaming docs/paper-example to docs/$PAPER_SLUG"
if [ -d docs/paper-example ] && [ "$PAPER_SLUG" != "paper-example" ]; then
  git mv docs/paper-example "docs/$PAPER_SLUG" 2>/dev/null || mv docs/paper-example "docs/$PAPER_SLUG"
  # Every config names its target document; without this they would render into
  # a directory that no longer exists.
  grep -rl 'paper-example' figures/ tables/ 2>/dev/null | while read -r f; do
    sed_i "s|paper-example|$PAPER_SLUG|g" "$f"
  done
fi

echo "-> filling in docs/$PAPER_SLUG/metadata.tex"
META="docs/$PAPER_SLUG/metadata.tex"
sed_i "s|{An Example Paper for the Paper Template}|{$PAPER_TITLE}|" "$META"
sed_i "s|{Paper Template}|{$PROJECT_NAME}|" "$META"
sed_i "s|{Author Name}|{$AUTHOR_NAME}|g" "$META"
sed_i "s|{Institution}|{$AFFILIATION}|" "$META"
sed_i "s|{author@example.org}|{$AUTHOR_EMAIL}|" "$META"

if [ "$KEEP_EXAMPLE" -eq 1 ]; then
  # Deliberately NOT rewriting entity/project here. The shipped data is
  # synthetic; data/wandb.lock.yml records the query that produced it, and
  # `make check-generated` compares the two. Stamping your project name onto a
  # lock entry for data that never came from it would make the provenance file
  # say something untrue — and fail the check immediately. Point paper.yml at
  # your runs when you replace the example, not before.
  echo "-> keeping the worked example; paper.yml still describes its synthetic data"
else
  echo "-> pointing paper.yml at $WANDB_ENTITY/$WANDB_PROJECT"
  sed_i "s|^  entity: .*|  entity: $WANDB_ENTITY|" paper.yml
  sed_i "s|^  project: .*|  project: $WANDB_PROJECT|" paper.yml

  echo "-> removing the worked example (data, figure, table, results section)"
  rm -f data/figures/*.csv data/tables/*.csv data/wandb.lock.yml
  rm -f "docs/$PAPER_SLUG/figures/.provenance.json" "docs/$PAPER_SLUG/figures/"*.pdf
  rm -f "docs/$PAPER_SLUG/tables/.provenance.json" "docs/$PAPER_SLUG/tables/"*.tex
  rm -f figures/generated/.provenance.json figures/generated/*.pdf
  rm -f figures/generated/*.drawio.svg figures/generated/*.drawio.png figures/generated/*.drawio.pdf
  rm -f figures/learning_curve.yml figures/architecture.drawio tables/final_scores.yml
  touch "docs/$PAPER_SLUG/figures/.gitkeep" "docs/$PAPER_SLUG/tables/.gitkeep"

  cat > "docs/$PAPER_SLUG/abstract.tex" <<'EOF'
%% The abstract, prose only — no \begin{abstract}, the template supplies that.
%% THIS FILE IS YOURS: `make set-template` never touches it.

% NOTE: write the abstract last.
EOF

  cat > "docs/$PAPER_SLUG/text.tex" <<'EOF'
%% The body of the paper — every section lives here.
%%
%% THIS FILE IS YOURS. `make set-template` rewrites main.tex but never touches
%% this file, so the same prose compiles under every template. Two rules keep
%% that true (see tools/templates/README.md):
%%
%%   * cite with \citep / \citet — every template loads natbib
%%   * anything you \begin{} must come from researchcommon.sty, not from one
%%     template's preamble

\section{Introduction}
\label{sec:introduction}

% NOTE: state the problem, the gap, and the contributions.

\section{Method}
\label{sec:method}

% NOTE: describe the method.

\section{Results}
\label{sec:results}

% NOTE: the figures and tables here are generated. Each one is a config file —
% figures/<name>.yml or tables/<name>.yml — declaring the runs it reports and
% how it is drawn. Write one, `make fetch REFRESH=1`, then `make plots`.
% See figures/README.md and docs/documentation/.

\section{Conclusion}
\label{sec:conclusion}

% NOTE: what did we learn, and what does it not answer?
EOF
  echo "   figures/ and tables/ are now empty — add a config to make your first figure."
fi

echo "-> moving this handbook to docs/documentation/README.md"
mkdir -p docs/documentation
if [ -f README.md ]; then
  git mv README.md docs/documentation/README.md 2>/dev/null || mv README.md docs/documentation/README.md
fi

echo "-> writing the project README.md"
awk '/PROJECT-README-SKELETON:START/{flag=1; next} /PROJECT-README-SKELETON:END/{flag=0} flag' \
  docs/documentation/README.md > README.md
for pair in \
  "PROJECT_NAME=$PROJECT_NAME" "PROJECT_SLUG=$PROJECT_SLUG" "PAPER_TITLE=$PAPER_TITLE" \
  "PAPER_SLUG=$PAPER_SLUG" "AUTHOR_NAME=$AUTHOR_NAME" "AFFILIATION=$AFFILIATION" \
  "WANDB_ENTITY=$WANDB_ENTITY" "WANDB_PROJECT=$WANDB_PROJECT" "CODE_REPO=$CODE_REPO" \
  "TEMPLATE_URL=$TEMPLATE_URL" "CITE_KEY=$CITE_KEY" "YEAR=$YEAR"; do
  key="${pair%%=*}"; value="${pair#*=}"
  sed_i "s|{{$key}}|${value//|/\\|}|g" README.md
done

echo "-> regenerating the document's generated files"
if command -v uv >/dev/null 2>&1; then
  uv run python tools/materialize.py >/dev/null || true
fi

echo "-> removing bootstrap.sh"
rm -- "$0"

cat <<EOF

Done. $PROJECT_NAME is ready.

Next:
  make setup                     create the environment
  make all                       build the paper end to end
  make check                     what CI checks

When your runs are in W&B:
  edit paper.yml                 point wandb.entity/project at your runs
  add figures/<name>.yml         one file per figure: its query and its styling
  export WANDB_API_KEY=...
  make fetch REFRESH=1           pull the runs in and pin the run set
  make plots && make tables      render everything

Review and commit the result — including data/ and the generated figures and
tables. They are meant to be in git; see docs/documentation/README.md.
EOF
