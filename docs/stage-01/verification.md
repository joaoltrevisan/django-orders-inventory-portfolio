# Stage 1: verification and review record

Date: 2026-10-26. This delivery contains design documents and Git ignore rules only. Application tests, SQL queries, migrations, and performance experiments have not run in this new repository.

## Executed inspection commands

Commands were executed from the workspace or the related project as appropriate. Locations are described without publishing private home-directory paths.

| Command | Actual result |
| --- | --- |
| `pwd`, `ls -la`, filtered `rg --files` | Identified unrelated workspace artifacts and the existing `loja-pedidos-estoque` project before creating files |
| Ancestor `AGENTS.md` checks and related-project file inventory | No applicable instructions found |
| `git -C loja-pedidos-estoque status --short --branch` | `main...origin/main`, no working-tree changes |
| `git -C loja-pedidos-estoque remote -v` | Origin points to the existing GitHub project |
| `git -C loja-pedidos-estoque log -1 --format='%h %ad' --date=iso-strict` | `21b5b17 2026-10-24T20:01:56-03:00` |
| Source/configuration/document reads and `rg` inspections | Reuse candidates and gaps recorded in the assessment |
| `python3 --version` | Python 3.14.7 on the host |
| Related `.venv/bin/python` with `platform.python_version()` and `importlib.metadata.version()` | Python 3.12.15; installed package versions recorded in the assessment |
| Related `.venv/bin/python -m pip check` | Exit 0, `No broken requirements found.` A pip-cache permission warning disabled caching; it did not fail the check |
| `docker --version` | Docker 29.9.2, build `a82e528` |
| `docker compose version` | Docker Compose v5.6.1 |
| `docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}'` | Exit 1, sandbox permission denied on Docker socket; running services and server versions not verified |
| `gh repo view joaoltrevisan/loja-pedidos-estoque --json nameWithOwner,url,visibility,defaultBranchRef` | After network escalation, exit 0; existing public repository, default branch `main` |
| `gh api user --jq .login` | After network escalation, exit 0; authenticated as `joaoltrevisan` |
| New local directory existence check and `gh repo view joaoltrevisan/django-orders-inventory-portfolio --json nameWithOwner,url` | No existing local directory or accessible repository found before creation |
| `mkdir django-orders-inventory-portfolio` and `git -C django-orders-inventory-portfolio init -b main` | Exit 0; created a separate repository |
| `gh repo create joaoltrevisan/django-orders-inventory-portfolio --public --description 'Django REST API portfolio: PostgreSQL modeling, transactional orders, inventory audit, SQL, testing, and measured query optimization.' --source . --remote origin` | Exit 0; new public repository created at the requested account |

The first GitHub read attempts failed because sandbox network access was unavailable. Retrying the same read operations with approved network access succeeded. Docker access was not escalated or retried because running containers is unnecessary for the Stage 1 design. No database was changed.

## Initial publication verification

Checks ran from the new repository using Python standard-library heredocs and Git. They verified documentation structure and publication scope, not application behavior.

The counts below describe the initial six-file delivery in commit `7a2a149`, before the independent-review workflow and review record were added.

| Executed command/check | Actual result |
| --- | --- |
| `python3` heredoc: inspect Markdown local links and fenced blocks | Exit 0; 5 Markdown files, 4 local links resolved, balanced fenced blocks |
| Same heredoc: ordered business-rule IDs and Mermaid source blocks | Exit 0; BR-01 through BR-24 present once in order; 2 Mermaid source blocks |
| Same heredoc: targeted private-path/token/key-header scan of documentation and ignore rules | Exit 0; no matches; this is not a comprehensive secret audit |
| `python3` heredoc invoking `git check-ignore -q` on 5 private/local path probes and `.env.example` | Exit 0; all 5 private/local paths ignored; `.env.example` remains eligible for tracking |
| `git -C ../loja-pedidos-estoque status --porcelain=v1` | Exit 0, no output; original working tree still clean |
| `git -C ../loja-pedidos-estoque rev-parse --short HEAD` | Exit 0, `21b5b17`; original HEAD unchanged |
| `git add .gitignore README.md docs/stage-01/assessment.md docs/stage-01/requirements.md docs/stage-01/data-model.md docs/stage-01/verification.md` | Exit 0; only the six intended files staged |
| `git diff --cached --check` | Exit 0, no whitespace errors |
| `git diff --cached --stat` and `git status --short` | Exit 0; six newly added documentation/ignore files; no application or secret files |

One documentation-check rerun exited 1 after embedding the checker itself in this file: its naive count included a triple-backtick string inside the Python example. The check was corrected to count only fence delimiters at the start of a line; the corrected command below was then executed successfully. This was a verification-script false positive, not an application test failure.

To repeat the local-link and fence check from the repository root:

```bash
python3 - <<'PY'
from pathlib import Path
import re

files = sorted(Path('.').rglob('*.md'))
count = 0
for file in files:
    source = file.read_text(encoding='utf-8')
    assert len(re.findall(r'^```', source, flags=re.MULTILINE)) % 2 == 0, file
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', source):
        if target.startswith(('https://', 'http://', '#', 'mailto:')):
            continue
        assert (file.parent / target.split('#', 1)[0]).is_file(), (file, target)
        count += 1
print(f'PASS: {len(files)} Markdown files; {count} local links; balanced fences.')
PY
git diff --cached --check
```

The diagrams were reviewed as Mermaid source, not rendered. No Docker/API/SQL tests were run. The related project's successful `pip check` is recorded only as dependency-inspection evidence.

## Independent-review revision verification

An independent reviewer completed Stage 1 review with no material findings. The reviewer executed separate documentation checks; their scope and limitations are recorded in `docs/stage-01/review.md`.

After adding the workflow and review record, the implementer executed a Python standard-library heredoc checking local Markdown links, line-anchored fences, the 24 rule IDs, targeted private-content patterns, and Git ignore probes. Actual result: exit 0; **7 Markdown files, 11 resolved local links, balanced fences, 24 ordered rule IDs, no targeted private-content matches, 5 private/local paths ignored, and `.env.example` eligible for tracking**. `git diff --check` also exited 0. A final original-repository status check produced no output, confirming it remains clean.

The initial published repository was also fetched directly through GitHub's API: its description, commit subject, and all six then-published files were English. No original-project files were translated, changed, committed, or published to this new repository.

## Files delivered

- `.gitignore`: excludes local secrets, environments, caches, and private database copies.
- `README.md`: English project entry point, current status, design summary, and six-stage roadmap.
- `docs/stage-01/assessment.md`: initial inventory, reuse decisions, missing work, versions, support references, and compatibility qualification.
- `docs/stage-01/requirements.md`: business rules, roles, lifecycle, stock/locking strategy, API/security conventions, SQL/benchmark contract, and stage acceptance plan.
- `docs/stage-01/data-model.md`: Mermaid ER diagram, tables, relationships, keys, checks, indexes, snapshots, and database artifact plan.
- `docs/stage-01/verification.md`: actual commands/results and review boundary.
- `docs/review-process.md`: required independent review, corrections, verification, and user approval checkpoints for every stage.
- `docs/stage-01/review.md`: independent Stage 1 findings, actual reviewer checks, and retained implementation gates.

## Limitations and outstanding work

- Design has not been implemented or approved. No passing-test count or speed improvement is claimed.
- The PostgreSQL image tag was inspected, but no live PostgreSQL server version was queried.
- SimpleJWT's published matrix does not establish upstream-tested DRF 3.18 compatibility; resolve or explicitly qualify that combination before implementing authentication.
- Mermaid diagrams are supplied as source. Rendering validation, if unavailable during these checks, must not be claimed.
- New migrations, schema export/restoration checks, Docker setup, `.env.example`, services, API, data generators, SQL outputs, and performance plans belong to later stages.
- Application services enforce cross-table integrity; the proposed database constraints alone cannot protect every invariant from privileged arbitrary SQL writes.
- No public application deployment is included. GitHub publication contains source/design artifacts only.

## Technical review checkpoint

Review the lifecycle and pending-only cancellation, owner/administrator permissions, simulated-payment scope, purchase/address snapshots, deletion policy, cancellation-headroom rule, lock ordering, service/database integrity boundary, selected runtime families, and the test/SQL/experiment contracts.

Stage 1 ends here. Wait for the user's technical review before starting Stage 2. Incremental commits and publication are authorized; later-stage implementation is not yet authorized by a Stage 1 approval.
