#!/usr/bin/env python3
"""Keep a paper repository in touch with the paper template it came from.

# The problem

GitHub's "Use this template" copies a tree, not a history. The resulting
repository shares no commit with the template, so `git merge template/main`
reports "refusing to merge unrelated histories", and forcing it turns every
file into an add/add conflict. On top of that `bootstrap.sh` renamed the example
document and rewrote its metadata, so the two trees no longer even agree on path
names.

This matters more here than it looks. The tooling in `tools/`, the Makefile and
the LaTeX templates are shared infrastructure: a fix you make to them while
writing *this* paper should reach the next one. Without a return path, every
paper repository silently forks the toolchain on the day it is created.

# The fix

    link      once:  declare "my tree already contains the template as of <ref>"
    update    often: an ordinary three-way merge carrying only what came after
    contribute        replay a generic fix onto the template and open a PR

`link` records the merge base with an `ours` merge — a commit that changes not
one file and exists purely so the histories become relatable.

# Commands

    template_sync.py link [--ref <commit>]   # once, after "Use this template"
    template_sync.py update                  # pull template improvements in
    template_sync.py contribute --branch fix-x <commit>...
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (
    ensure_remote,
    git,
    read_yaml,
    repo_root,
    require_clean_tree,
)

CONFIG = ".template-upstream.yml"
REMOTE = "template"
BASE_REF = "refs/template/base"


def read_config(root: Path) -> dict:
    path = root / CONFIG
    config = read_yaml(path)
    if not config.get("upstream"):
        raise SystemExit(
            f"error: {CONFIG} is missing or has no `upstream:` URL.\n"
            f"Create it at the repository root with:\n\n"
            f"  upstream: https://github.com/<owner>/<template-repo>.git\n"
            f"  branch: main\n\n"
            f"See README.md, 'Staying in sync with upstreams'."
        )
    config.setdefault("branch", "main")
    return config


def fetch(config: dict, root: Path) -> str:
    """Point the `template` remote at the configured URL and fetch it."""
    ensure_remote(REMOTE, config["upstream"], root)
    git("fetch", REMOTE, config["branch"], cwd=root)
    return f"{REMOTE}/{config['branch']}"


def is_linked(root: Path) -> bool:
    return bool(git("rev-parse", "-q", "--verify", BASE_REF, cwd=root, check=False))


CONFLICT_HELP = """
Conflicts are expected in the files bootstrap.sh rewrote for this project — the
renamed document under docs/, its metadata.tex, wandb.yml and the root
README.md. Keep your version in those; the substance of a template update lives
in tools/, Makefile, src/paperkit/ and .github/. The template's
handbook arrives as an edit to docs/documentation/README.md, which bootstrap.sh
moved there unchanged so that this merge stays clean; your own root README.md is
never touched.

  git status                 # see what conflicted
  git mergetool              # or edit the files by hand
  git add <files> && git commit

To abandon the merge:  git merge --abort

For a single upstream fix rather than everything, abort and cherry-pick it:
  git log --oneline HEAD..{ref}
  git cherry-pick -x <commit>
"""


def cmd_link(args, root: Path) -> int:
    """Declare the template commit this project started from. Run once."""
    config = read_config(root)

    if is_linked(root):
        base = git("rev-parse", BASE_REF, cwd=root)
        print(f"already linked at {base[:12]} — nothing to do.")
        print("Run `make template-update` to pull in what came after it.")
        return 0

    require_clean_tree(root, "`link`")
    ref = fetch(config, root)

    target = args.ref or ref
    resolved = git("rev-parse", "--verify", f"{target}^{{commit}}", cwd=root, check=False)
    if not resolved:
        raise SystemExit(
            f"error: '{target}' is not a commit in the template.\n"
            f"List the candidates with:  git log --oneline {ref}"
        )

    if not args.ref:
        print(
            f"\nwarning: no --ref given, so linking at the CURRENT tip of {ref}.\n"
            f"         Every template improvement made before now is treated as\n"
            f"         already present and will never be offered by `update`.\n"
            f"         If this project was copied from an older commit, abort and\n"
            f"         re-run with --ref <that commit> instead. Find it with:\n"
            f"             git log --oneline {ref}\n"
        )
        confirm = input("link at the current tip anyway? [y/N] ") if sys.stdin.isatty() else "y"
        if confirm.strip().lower() not in ("y", "yes"):
            print("aborted — nothing was changed.")
            return 1

    print(f"linking template history at {resolved[:12]} ...")

    # An `ours` merge: takes the whole of our tree, records the template commit
    # as a second parent, changes no file. From here on the template and this
    # project have a merge base, so `update` is an ordinary three-way merge that
    # only ever carries the delta since this point.
    git("merge", "-s", "ours", "--no-commit", "--allow-unrelated-histories", resolved, cwd=root)
    git(
        "commit",
        "--no-verify",
        "-m",
        f"Link template history at {resolved[:12]}\n"
        f"\n"
        f"Establishes the merge base between this project and the template it\n"
        f"was generated from. Changes no files. See README.md, 'Staying in sync\n"
        f"with upstreams'.\n"
        f"\n"
        f"template-upstream: {config['upstream']}\n"
        f"template-commit: {resolved}\n",
        cwd=root,
    )
    git("update-ref", BASE_REF, resolved, cwd=root)

    print("  linked. Now run: make template-update")
    return 0


def cmd_update(args, root: Path) -> int:
    """Merge template improvements made since the link into this project."""
    config = read_config(root)

    if not is_linked(root):
        raise SystemExit(
            "error: this project has no template merge base yet, so a merge would\n"
            "report 'unrelated histories' and conflict on every file.\n"
            "Run `make template-link` first (with REF=<commit> if you know which\n"
            "template commit this project was copied from)."
        )

    require_clean_tree(root, "`update`")
    ref = fetch(config, root)

    pending = git("log", "--oneline", f"HEAD..{ref}", cwd=root)
    if not pending:
        print(f"up to date with {ref} — nothing to merge.")
        return 0

    print("template commits not yet in this project:\n")
    print(pending)
    print()

    result = git(
        "merge",
        "--no-edit",
        "-m",
        f"Merge template updates from {ref}",
        ref,
        cwd=root,
        check=False,
    )
    print(result)

    if git("ls-files", "--unmerged", cwd=root):
        print(CONFLICT_HELP.format(ref=ref))
        return 1

    git("update-ref", BASE_REF, git("rev-parse", ref, cwd=root), cwd=root)
    print(
        "\nmerged. Next: `make check` — a template update often touches tools/ or\n"
        "the Makefile, and that is exactly what check exercises."
    )
    return 0


def cmd_contribute(args, root: Path) -> int:
    """Replay generic commits onto the template and print the PR command."""
    config = read_config(root)
    require_clean_tree(root, "`contribute`")
    ref = fetch(config, root)

    if git("rev-parse", "-q", "--verify", args.branch, cwd=root, check=False):
        raise SystemExit(
            f"error: branch '{args.branch}' already exists. Pick another name, or\n"
            f"delete it with:  git branch -D {args.branch}"
        )

    for commit in args.commits:
        if not git("rev-parse", "--verify", f"{commit}^{{commit}}", cwd=root, check=False):
            raise SystemExit(f"error: '{commit}' is not a commit in this repository")

    original = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root)

    # Branch off the template tip, not off our work: our commits carry this
    # paper's prose, figures and W&B cache, which have no business upstream.
    # Only the named commits are replayed, and `-x` records where each came from.
    print(f"branching '{args.branch}' off {ref} and replaying {len(args.commits)} commit(s) ...")
    git("checkout", "-b", args.branch, ref, cwd=root)

    for commit in args.commits:
        result = git("cherry-pick", "-x", commit, cwd=root, check=False)
        print(result)
        if git("ls-files", "--unmerged", cwd=root):
            print(
                f"\nCherry-pick of {commit[:12]} conflicted — the template's version of\n"
                f"these files differs from this project's. Resolve, then:\n"
                f"    git add <files> && git cherry-pick --continue\n"
                f"To give up:\n"
                f"    git cherry-pick --abort && git checkout {original} "
                f"&& git branch -D {args.branch}\n"
            )
            return 1

    upstream = config["upstream"]
    print(
        f"\ndone — '{args.branch}' now contains only your change, on top of the template.\n"
        f"\n"
        f"Review it:\n"
        f"    git log --oneline {ref}..{args.branch}\n"
        f"    git diff {ref}..{args.branch}\n"
        f"\n"
        f"Then push to your fork of the template and open the PR:\n"
        f"    gh repo fork {upstream} --remote-name fork --clone=false\n"
        f"    git push fork {args.branch}\n"
        f"    gh pr create --repo {upstream} --head <your-gh-user>:{args.branch}\n"
        f"\n"
        f"Back to your work when you are done:\n"
        f"    git checkout {original}\n"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_link = sub.add_parser("link", help=(cmd_link.__doc__ or "").splitlines()[0])
    p_link.add_argument(
        "--ref",
        help="the template commit this project was copied from "
        "(default: the current tip of the template branch)",
    )
    p_link.set_defaults(handler=cmd_link)

    p_update = sub.add_parser("update", help=(cmd_update.__doc__ or "").splitlines()[0])
    p_update.set_defaults(handler=cmd_update)

    p_contribute = sub.add_parser(
        "contribute", help=(cmd_contribute.__doc__ or "").splitlines()[0]
    )
    p_contribute.add_argument("--branch", required=True, help="name for the contribution branch")
    p_contribute.add_argument("commits", nargs="+", help="commits to replay onto the template")
    p_contribute.set_defaults(handler=cmd_contribute)

    args = parser.parse_args(argv)
    return args.handler(args, repo_root())


if __name__ == "__main__":
    raise SystemExit(main())
