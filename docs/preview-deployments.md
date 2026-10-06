# Production and PR previews

Production remains https://chikausa14.github.io/immersive-message-maker/ and always
uses `main`. An open same-repository PR targeting `main` is published at:

`https://chikausa14.github.io/immersive-message-maker/previews/pr-N/`

For PR #1: https://chikausa14.github.io/immersive-message-maker/previews/pr-1/

Opening, updating, reopening, or closing a PR triggers **Publish production and PR
previews** in Actions. Main pushes also deploy. Allow the workflow to finish, then
reload the preview (mobile browsers may need a refresh). The build summary lists
the preview links and exact deployed commits. Closing or merging a PR removes its
directory on the next successful deployment. A daily run reconciles missed events;
**Actions → Publish production and PR previews → Run workflow → main** can also
refresh everything. No changes to the feature branch are needed to enable previews.

## One-time hosting setup

The workflow and builder must be on `main`; `pull_request_target` deliberately uses
trusted base-branch automation, not the PR's workflow or scripts.

In **Settings → Pages → Build and deployment → Source**, select **GitHub Actions**.
The previous setting was **Deploy from a branch → main → / (root)**. This switch
keeps the existing live deployment until the workflow publishes its replacement.
The new deployment includes the same production app files plus the preview
directories. Keep the existing `github-pages` environment restricted to `main`.
After installation, run the workflow on `main` once to include already-open PRs.

Pages can publish only one complete site at a time. Separate per-PR deployments
would overwrite production or one another. This workflow instead rebuilds one
artifact from current `main` and every eligible open PR and serializes deployments.
No hosting branch, paid service, personal access token, or repository secret is
needed. The automatically provided `GITHUB_TOKEN` reads source; a separate deploy
job gets only `pages: write` and `id-token: write` permissions.

## Source fidelity and safety

- The builder reads regular Git blobs at immutable commit SHAs. It never checks
  out PR files, executes PR scripts, installs PR dependencies, or runs a build.
  `index.html`, relative asset paths, binary files, and hidden assets are copied
  byte-for-byte. Only `.github/` automation metadata is omitted. Production also
  gets an empty `.nojekyll` marker if it does not already have one.
- Use relative asset URLs for previews. Absolute `/...` URLs retain their original
  meaning; files and URLs are not rewritten. This is a static-site workflow, not
  an LFS, submodule, or framework build pipeline.
- `previews/` is reserved at the production root. A conflicting production tree,
  missing production `index.html`, or API/fetch failure aborts deployment and
  preserves the current live site. PRs missing `index.html` or containing symlinks
  or submodules are omitted and reported in the build summary.
- Previews are separate directories, **not separate browser origins**. They share
  cookies/localStorage and may contain unfinished JavaScript. Only same-repository
  PRs from trusted collaborators are published automatically, including draft PRs.
  Fork PRs are excluded; review their code before bringing it onto a trusted branch.
  Use a private browser window if you want to keep preview edits separate from
  production drafts. Nothing is injected into the app or its storage keys.
- The site and previews are public. Do not commit private data or credentials.
  No PR comments or other write permissions are required. Actions are pinned to
  immutable commits, and the deployment job never has repository write access.

## Validation and rollback

Run `python3 -m unittest discover -s tests -p 'test_pages.py' -v` for offline
assembly/security tests. After deployment, verify the production HTML still matches
`main`, the PR HTML matches its head, and the preview loads on desktop and mobile.

To return to the original setup, first disable **Publish production and PR previews**
in Actions, then set **Settings → Pages → Source → Deploy from a branch → main →
/ (root)** and save. The next branch deployment restores production without preview
directories. This does not merge or change any feature PR.
