#!/usr/bin/env pwsh

# GitHub Invitation Script - Pipe Joint Inspection App
# This script invites collaborators and configures permissions

# Configuration
$REPO_OWNER = "yourorg"  # Change to your GitHub organization
$REPO_NAME = "pipe-joint-inspect"
$MAVIS_USERNAME = "MAVIS-creator"
$MAVIS_EMAIL = "akintunde.dolapo1@gmail.com"
$MAIN_OWNER = "Ifeoyewole"
$IFEOYEWOLE_USERNAME = "Ifeoyewole"  # Frontend developer

Write-Host "🚀 Pipe Joint Inspection App - GitHub Setup Script" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# Verify GitHub CLI is installed
Write-Host "📋 Checking GitHub CLI installation..." -ForegroundColor Yellow
try {
    $ghVersion = gh --version 2>$null
    if ($?) {
        Write-Host "✅ GitHub CLI found: $ghVersion" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ GitHub CLI not found. Please install it first:" -ForegroundColor Red
    Write-Host "   https://cli.github.com/" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "📍 Repository: $REPO_OWNER/$REPO_NAME" -ForegroundColor Yellow
Write-Host ""

# Step 1: Verify authentication
Write-Host "🔐 Verifying GitHub authentication..." -ForegroundColor Yellow
$authStatus = gh auth status 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Authenticated as: $(gh api user --jq '.login')" -ForegroundColor Green
} else {
    Write-Host "❌ Not authenticated. Please run: gh auth login" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 2: Invite Mavis as collaborator
Write-Host "👤 Inviting $MAVIS_USERNAME as collaborator..." -ForegroundColor Yellow
Write-Host "   Role: Maintainer (can review PRs and merge)" -ForegroundColor Gray

try {
    gh repo invite "$REPO_OWNER/$REPO_NAME" "$MAVIS_USERNAME" --permission maintain
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Invitation sent to $MAVIS_USERNAME" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Could not invite $MAVIS_USERNAME (may already have access)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  Error inviting $MAVIS_USERNAME: $_" -ForegroundColor Yellow
}

Write-Host ""

# Step 3: Verify both developers have access
Write-Host "👤 Verifying $IFEOYEWOLE_USERNAME frontend access..." -ForegroundColor Yellow
try {
    gh repo invite "$REPO_OWNER/$REPO_NAME" "$IFEOYEWOLE_USERNAME" --permission maintain 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Invitation sent to $IFEOYEWOLE_USERNAME" -ForegroundColor Green
    } else {
        Write-Host "✅ $IFEOYEWOLE_USERNAME already has access" -ForegroundColor Green
    }
} catch {
    Write-Host "✅ $IFEOYEWOLE_USERNAME already has access" -ForegroundColor Green
}

Write-Host ""

# Step 4: Configure branch permissions
Write-Host "🔒 Configuring branch protections..." -ForegroundColor Yellow

# Protect main branch
Write-Host "   Setting up 'main' branch protection..." -ForegroundColor Gray
try {
    gh api repos/$REPO_OWNER/$REPO_NAME/branches/main/protection `
        --input - << 'EOF'
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
    Write-Host "✅ 'main' branch protected" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Could not set main branch protection (may already be configured)" -ForegroundColor Yellow
}

Write-Host ""

# Protect develop branch
Write-Host "   Setting up 'develop' branch protection..." -ForegroundColor Gray
try {
    gh api repos/$REPO_OWNER/$REPO_NAME/branches/develop/protection `
        --input - << 'EOF'
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
    Write-Host "✅ 'develop' branch protected" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Could not set develop branch protection (may already be configured)" -ForegroundColor Yellow
}

Write-Host ""

# Step 5: Summary
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "✅ GitHub Setup Complete!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

Write-Host "📊 Configuration Summary:" -ForegroundColor Cyan
Write-Host "   Repository: $REPO_OWNER/$REPO_NAME" -ForegroundColor White
Write-Host "   Main Owner: $MAIN_OWNER" -ForegroundColor White
Write-Host "   Backend Dev: $MAVIS_USERNAME ($MAVIS_EMAIL)" -ForegroundColor White
Write-Host "   Frontend Dev: $IFEOYEWOLE_USERNAME" -ForegroundColor White
Write-Host ""

Write-Host "🔐 Branch Protection:" -ForegroundColor Cyan
Write-Host "   ✅ main: Requires PR review + status checks + code owner review" -ForegroundColor White
Write-Host "   ✅ develop: Requires PR + status checks" -ForegroundColor White
Write-Host "   ⚪ mavis-backend: Unprotected (developer can push)" -ForegroundColor White
Write-Host "   ⚪ vikky-frontend: Unprotected (developer can push)" -ForegroundColor White
Write-Host ""

Write-Host "👥 Code Ownership:" -ForegroundColor Cyan
Write-Host "   Backend (src/services/, src/db/, etc.) → $MAVIS_USERNAME + $MAIN_OWNER review" -ForegroundColor White
Write-Host "   Frontend (src/pages/, src/components/, etc.) → $IFEOYEWOLE_USERNAME" -ForegroundColor White
Write-Host "   Shared files (src/hooks/, src/types/, etc.) → Both developers" -ForegroundColor White
Write-Host "   Project config → $MAIN_OWNER review required" -ForegroundColor White
Write-Host ""

Write-Host "📝 Next Steps:" -ForegroundColor Cyan
Write-Host "   1. $MAVIS_USERNAME will receive invitation email" -ForegroundColor White
Write-Host "   2. They should accept the invitation to access the repository" -ForegroundColor White
Write-Host "   3. Set default branch to 'develop' in GitHub repo settings" -ForegroundColor White
Write-Host "   4. Enable branch protection rules in GitHub (admin settings)" -ForegroundColor White
Write-Host "   5. Both developers can clone and start working" -ForegroundColor White
Write-Host ""

Write-Host "🚀 Ready to go! Happy coding! 🎉" -ForegroundColor Green
Write-Host ""
