#!/usr/bin/env bash
# One-time setup of the GitHub repository for the team. Run it ONCE, by the repo owner.
#   1. Install GitHub CLI:  https://cli.github.com   then run:  gh auth login
#   2. Push the code to GitHub first (main branch), then from the repo folder run:
#        bash scripts/setup-github.sh
# It creates the `dev` branch, the labels, and protects `main` and `dev`
# (pull request + 1 approval + "CI Passed" check, no force-push).
# NOTE: branch protection needs a PUBLIC repo, or GitHub Pro / Student Pack for private repos.
set -euo pipefail

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "Configuring $REPO"

# --- dev branch --------------------------------------------------------
if gh api "repos/$REPO/branches/dev" > /dev/null 2>&1; then
  echo "dev branch already exists"
else
  SHA=$(gh api "repos/$REPO/git/ref/heads/main" -q .object.sha)
  gh api "repos/$REPO/git/refs" -f ref=refs/heads/dev -f sha="$SHA" > /dev/null
  echo "created dev branch"
fi

# --- labels ------------------------------------------------------------
label() { gh label create "$1" --color "$2" --description "$3" --force > /dev/null; }
label backend     1d76db "booking-service / API / database"
label frontend    a2eeef "web pages"
label devops      0e8a16 "CI/CD, Terraform, GitHub setup"
label docker      0052cc "Dockerfiles, compose, registry"
label ux          d93f0b "research, Figma, usability"
label docs        c5def5 "documentation"
echo "labels ready"

# --- branch protection ---------------------------------------------------
protect() {
  gh api -X PUT "repos/$REPO/branches/$1/protection" --input - > /dev/null <<JSON
{
  "required_status_checks": { "strict": false, "contexts": ["CI Passed"] },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
  echo "protected branch: $1"
}
protect main
protect dev

echo "Done. Now invite your teammates: Settings > Collaborators (give them Write access)."
