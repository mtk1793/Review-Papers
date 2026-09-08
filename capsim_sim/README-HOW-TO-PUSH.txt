CAPSM push bundle — how to use it
==================================

You're receiving two files:

  1. capsim-patch-only.zip  (47 KB)  — the 24 new/changed files from commit 1435b97
  2. capsim-commit-1435b97.patch (107 KB) — a git patch you can apply with `git am`

Pick ONE of the three methods below. All three result in the same commit
on your local clone, ready to push to GitHub.

-------------------------------------------------------------------------------

METHOD A — Drop the files over an existing clone (easiest, no git surgery)
-------------------------------------------------------------------------------

1. On your local machine, clone (or pull) the existing repo:
       git clone https://github.com/mtk1793/PhD-Thesis.git
       cd PhD-Thesis

2. Unzip the bundle at the repo root so the paths line up:
       unzip /path/to/capsim-patch-only.zip -d .

   This overwrites the 7 modified files and adds the 17 new files.

3. Stage and commit:
       git add -A
       git commit -m "Phase A+B+C+D: thesis-grade rebuild, dashboard, installable package, Docker, CI"

4. Push:
       git push origin master

-------------------------------------------------------------------------------

METHOD B — Apply the git patch (preserves my commit message + SHA)
-------------------------------------------------------------------------------

1. On your local machine:
       git clone https://github.com/mtk1793/PhD-Thesis.git
       cd PhD-Thesis

2. Apply the patch:
       git am /path/to/capsim-commit-1435b97.patch

   This creates the same commit (1435b97) on your local master branch.

3. Push:
       git push origin master

-------------------------------------------------------------------------------

METHOD C — Pull directly from a local copy (most foolproof)
-------------------------------------------------------------------------------

If you want zero ambiguity about file paths:

1. Clone a fresh copy on your machine:
       git clone https://github.com/mtk1793/PhD-Thesis.git capsm-clean
       cd capsm-clean

2. Unzip the bundle into a staging directory:
       mkdir /tmp/staging && cd /tmp/staging
       unzip /path/to/capsim-patch-only.zip

3. Copy each file into the clean clone (preserves directory structure):
       cp -r PhD-Thesis/.github .
       cp -r PhD-Thesis/.gitignore .
       cp -r PhD-Thesis/CITATION.cff .
       cp -r PhD-Thesis/CODE_OF_CONDUCT.md .
       cp -r PhD-Thesis/LICENSE .
       cp -r PhD-Thesis/README.md .
       cp -r PhD-Thesis/docker-compose.yml .
       cp -r PhD-Thesis/capsim_sim/.dockerignore capsim_sim/
       cp -r PhD-Thesis/capsim_sim/.gitignore capsim_sim/
       cp -r PhD-Thesis/capsim_sim/CHANGELOG.md capsim_sim/
       cp -r PhD-Thesis/capsim_sim/Dockerfile capsim_sim/
       cp -r PhD-Thesis/capsim_sim/Makefile capsim_sim/
       cp -r PhD-Thesis/capsim_sim/README.md capsim_sim/
       cp -r PhD-Thesis/capsim_sim/pyproject.toml capsim_sim/
       cp -r PhD-Thesis/capsim_sim/requirements.txt capsim_sim/
       cp -r PhD-Thesis/capsm/cli.py capsm_sim/capsm/
       cp -r PhD-Thesis/capsim_sim/capsm/grid/__init__.py capsim_sim/capsm/grid/
       cp -r PhD-Thesis/capsim_sim/capsm/plotting.py capsim_sim/capsm/
       cp -r PhD-Thesis/capsim_sim/scripts/dashboard.py capsim_sim/scripts/
       cp -r PhD-Thesis/capsim_sim/scripts/generate_thesis_artifacts.py capsim_sim/scripts/
       cp -r PhD-Thesis/capsim_sim/scripts/phase1_data.py capsim_sim/scripts/
       cp -r PhD-Thesis/capsim_sim/scripts/phase2_grid.py capsim_sim/scripts/
       cp -r PhD-Thesis/capsim_sim/scripts/phase3_baselines.py capsim_sim/scripts/
       cp -r PhD-Thesis/capsim_sim/scripts/run_all.py capsim_sim/scripts/

   (Method A does this automatically with `unzip -d .`.)

4. Commit and push:
       git add -A
       git commit -m "Phase A+B+C+D: thesis-grade rebuild, dashboard, installable package, Docker, CI"
       git push origin master

-------------------------------------------------------------------------------

WHAT'S IN THE BUNDLE (24 files changed in commit 1435b97)

  New top-level files (5):
    .gitignore, CITATION.cff, CODE_OF_CONDUCT.md, LICENSE, README.md

  New capsim_sim files (12):
    .dockerignore, Dockerfile, Makefile, pyproject.toml
    capsm/cli.py, capsm/grid/__init__.py, capsm/plotting.py
    scripts/dashboard.py, scripts/generate_thesis_artifacts.py, scripts/run_all.py

  Modified capsim_sim files (7):
    .gitignore, CHANGELOG.md, README.md, requirements.txt
    scripts/phase1_data.py, scripts/phase2_grid.py, scripts/phase3_baselines.py

  New CI workflow (1):
    .github/workflows/ci.yml

  New docker-compose.yml (1, at repo root)

-------------------------------------------------------------------------------

AFTER YOU PUSH

1. Wait ~20 min for the GitHub Actions CI run to finish. The badge at the
   top of the README will turn green.
2. Visit https://github.com/mtk1793/PhD-Thesis/actions to see the run.
3. The `reproduce` job uploads a `capsim-results` artifact containing
   results/SUMMARY.md and all thesis_artifacts/ — useful for sharing with
   your committee without them having to run anything.
4. Consider creating a GitHub Release v1.0.0, tagging commit 1435b97, and
   attaching the capsim-results artifact as the release payload.

-------------------------------------------------------------------------------

IF YOU WANT EVERYTHING (NOT JUST MY CHANGES)

If for some reason you want the entire PhD-Thesis tree as a ZIP (including
all the chapter PDFs, the HIL_Project, etc.), let me know and I'll generate
a 200+ MB bundle. The patch-only bundle is what you actually need to push.
