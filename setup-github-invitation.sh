#!/bin/bash

# GitHub Invitation Script - Pipe Joint Inspection App (Bash version)
# This script invites collaborators and configures permissions
# Usage: bash setup-github-invitation.sh

# Configuration
REPO_OWNER="Ifeoyewole"  # Change to your GitHub organization
REPO_NAME="Don-t"
MAVIS_USERNAME="MAVIS-creator"
MAVIS_EMAIL="akintunde.dolapo1@gmail.com"
MAIN_OWNER="Ifeoyewole"
IFEOYEWOLE_USERNAME="Ifeoyewole"  # Frontend developer

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}🚀 Pipe Joint Inspection App - GitHub Setup Script${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Verify GitHub CLI is installed
echo -e "${YELLOW}📋 Checking GitHub CLI installation...${NC}"
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ GitHub CLI not found. Please install it first:${NC}"
    echo -e "${RED}   https://cli.github.com/${NC}"
    exit 1
fi

GH_VERSION=$(gh --version 2>/dev/null)
echo -e "${GREEN}✅ GitHub CLI found: $GH_VERSION${NC}"

echo ""
echo -e "${YELLOW}📍 Repository: $REPO_OWNER/$REPO_NAME${NC}"
echo ""

# Step 1: Verify authentication
echo -e "${YELLOW}🔐 Verifying GitHub authentication...${NC}"
if gh auth status &> /dev/null; then
    AUTH_USER=$(gh api user --jq '.login' 2>/dev/null)
    echo -e "${GREEN}✅ Authenticated as: $AUTH_USER${NC}"
else
    echo -e "${RED}❌ Not authenticated. Please run: gh auth login${NC}"
    exit 1
fi

echo ""

# Step 2: Invite Mavis as collaborator
echo -e "${YELLOW}👤 Inviting $MAVIS_USERNAME as collaborator...${NC}"
echo -e "${YELLOW}   Role: Maintainer (can review PRs and merge)${NC}"

if gh repo invite "$REPO_OWNER/$REPO_NAME" "$MAVIS_USERNAME" --permission maintain 2>/dev/null; then
    echo -e "${GREEN}✅ Invitation sent to $MAVIS_USERNAME${NC}"
else
    echo -e "${YELLOW}⚠️  Could not invite $MAVIS_USERNAME (may already have access)${NC}"
fi

echo ""

# Step 3: Verify both developers have access
echo -e "${YELLOW}👤 Verifying $IFEOYEWOLE_USERNAME frontend access...${NC}"
if gh repo invite "$REPO_OWNER/$REPO_NAME" "$IFEOYEWOLE_USERNAME" --permission maintain 2>/dev/null; then
    echo -e "${GREEN}✅ Invitation sent to $IFEOYEWOLE_USERNAME${NC}"
else
    echo -e "${GREEN}✅ $IFEOYEWOLE_USERNAME already has access${NC}"
fi

echo ""

# Step 4: Configure branch protections
echo -e "${YELLOW}🔒 Configuring branch protections...${NC}"

# Protect main branch
echo -e "${YELLOW}   Setting up 'main' branch protection...${NC}"
cat > /tmp/main-protection.json << 'EOF'
{
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1
  },
  "required_status_checks": {
    "strict": true,
    "contexts": ["build", "test", "lint"]
  }
}
EOF

if gh api repos/$REPO_OWNER/$REPO_NAME/branches/main/protection --input /tmp/main-protection.json 2>/dev/null; then
    echo -e "${GREEN}✅ 'main' branch protected${NC}"
else
    echo -e "${YELLOW}⚠️  Could not set main branch protection (may already be configured)${NC}"
fi

# Protect develop branch
echo -e "${YELLOW}   Setting up 'develop' branch protection...${NC}"
cat > /tmp/develop-protection.json << 'EOF'
{
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 0
  },
  "required_status_checks": {
    "strict": true,
    "contexts": ["build", "test", "lint"]
  }
}
EOF

if gh api repos/$REPO_OWNER/$REPO_NAME/branches/develop/protection --input /tmp/develop-protection.json 2>/dev/null; then
    echo -e "${GREEN}✅ 'develop' branch protected${NC}"
else
    echo -e "${YELLOW}⚠️  Could not set develop branch protection (may already be configured)${NC}"
fi

# Cleanup
rm -f /tmp/main-protection.json /tmp/develop-protection.json

echo ""

# Step 5: Summary
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ GitHub Setup Complete!${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${CYAN}📊 Configuration Summary:${NC}"
echo "   Repository: $REPO_OWNER/$REPO_NAME"
echo "   Main Owner: $MAIN_OWNER"
echo "   Backend Dev: $MAVIS_USERNAME ($MAVIS_EMAIL)"
echo "   Frontend Dev: $IFEOYEWOLE_USERNAME"
echo ""

echo -e "${CYAN}🔐 Branch Protection:${NC}"
echo -e "   ✅ main: Requires PR review + status checks + code owner review"
echo -e "   ✅ develop: Requires PR + status checks"
echo -e "   ⚪ mavis-backend: Unprotected (developer can push)"
echo -e "   ⚪ vikky-frontend: Unprotected (developer can push)"
echo ""

echo -e "${CYAN}👥 Code Ownership:${NC}"
echo "   Backend (src/services/, src/db/, etc.) → $MAVIS_USERNAME + $MAIN_OWNER review"
echo "   Frontend (src/pages/, src/components/, etc.) → $IFEOYEWOLE_USERNAME"
echo "   Shared files (src/hooks/, src/types/, etc.) → Both developers"
echo "   Project config → $MAIN_OWNER review required"
echo ""

echo -e "${CYAN}📝 Next Steps:${NC}"
echo "   1. $MAVIS_USERNAME will receive invitation email"
echo "   2. They should accept the invitation to access the repository"
echo "   3. Set default branch to 'develop' in GitHub repo settings"
echo "   4. Enable branch protection rules in GitHub (admin settings)"
echo "   5. Both developers can clone and start working"
echo ""

echo -e "${GREEN}🚀 Ready to go! Happy coding! 🎉${NC}"
echo ""
