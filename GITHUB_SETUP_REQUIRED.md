# GitHub setup required

`git remote -v` returns nothing: this repository has **no remote**. No GitHub
repository was created, because publishing requires your account and your
explicit approval.

## Current state

| Item | Value |
| --- | --- |
| Branch | `master` |
| Local commits | 4 (`083ac7b`, `c511a1a`, `aa1fbf5`, `905ce5c`) plus staged/uncommitted docs |
| Remote | **none** |
| Visibility | not applicable until a repository exists |
| Pushed | no |

## Option A — create the repository with the GitHub CLI

```bat
gh auth login
cd "S:\BiztelAI Technologies. Assesment"
gh repo create factoryassist-ai --private --source=. --remote=origin
git push -u origin master
```

`--private` keeps the plant SOP PDFs and assessment material out of public view.
Use `--public` only if you are sure the corpus may be published.

## Option B — create it in the browser, then connect

1. GitHub → **New repository**.
2. Name it (for example `factoryassist-ai`), choose **Private**, and do **not**
   add a README, `.gitignore` or licence — the local repository already has
   history and adding files would create an unrelated first commit.
3. Connect and push:

```bat
cd "S:\BiztelAI Technologies. Assesment"
git remote add origin https://github.com/<your-account>/factoryassist-ai.git
git branch -M master
git push -u origin master
```

SSH alternative:

```bat
git remote add origin git@github.com:<your-account>/factoryassist-ai.git
git push -u origin master
```

## Verify without publishing

These commands inspect the remote configuration and confirm reachability without
uploading anything:

```bat
git remote -v
git ls-remote origin
```

`git ls-remote` fails on an empty private repository until the first push, which
is expected.

## Before the first push

- Confirm `git log -1 --format="%an <%ae>"` shows your real address
  (see `GIT_SETUP_REQUIRED.md`).
- Confirm the working tree contains no `.env`, PDFs, `data/processed/`,
  `vector_store/chroma_db/`, `.venv/` or logs — all are ignored and were verified
  during this audit.
- If your organisation requires a signed commit or an internal remote, add that
  configuration first.

## What was deliberately not done

- No repository was created or initialised on GitHub.
- No remote was added, so no credentials were used.
- Nothing was pushed or made public.
