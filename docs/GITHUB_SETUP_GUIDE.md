# GitHub Invitation & Setup Scripts

## Overview

These scripts automate the GitHub repository setup for the Pipe Joint Inspection App, including:

- ✅ Inviting collaborators (MAVIS-creator, Vikky)
- ✅ Assigning maintainer roles
- ✅ Configuring branch protections
- ✅ Setting code ownership rules
- ✅ Enabling CI/CD status checks

## Prerequisites

### 1. Install GitHub CLI

**Windows:**
```powershell
winget install GitHub.cli
# OR
choco install gh
```

**macOS:**
```bash
brew install gh
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt install gh

# Fedora
sudo dnf install gh
```

**Verify Installation:**
```bash
gh --version
```

### 2. Create Repository on GitHub

1. Go to [GitHub.com](https://github.com)
2. Click "New repository"
3. Fill in:
   - **Repository name:** `pipe-joint-inspect`
   - **Description:** Pipe Joint Inspection Application
   - **Visibility:** Private (recommended)
   - **DO NOT initialize** with README/gitignore
4. Click "Create repository"

### 3. Authenticate with GitHub CLI

```bash
gh auth login
# Follow prompts:
# - Select "GitHub.com"
# - Select "HTTPS"
# - Select "Y" for git credential manager
# - Complete browser authentication
```

Verify authentication:
```bash
gh auth status
```

## Configuration

Before running the script, update these values in the script file:

### PowerShell Script (`setup-github-invitation.ps1`)

```powershell
$REPO_OWNER = "yourorg"           # Change to your GitHub organization/username
$REPO_NAME = "pipe-joint-inspect"  # Your repository name
$MAVIS_USERNAME = "MAVIS-creator"  # Mavis's GitHub username (Backend)
$MAVIS_EMAIL = "akintunde.dolapo1@gmail.com"  # Mavis's email
$MAIN_OWNER = "Ifeoyewole"         # Main owner's GitHub username (Frontend)
$IFEOYEWOLE_USERNAME = "Ifeoyewole"  # Frontend developer
```

### Bash Script (`setup-github-invitation.sh`)

```bash
REPO_OWNER="yourorg"           # Change to your GitHub organization/username
REPO_NAME="pipe-joint-inspect"  # Your repository name
MAVIS_USERNAME="MAVIS-creator"  # Mavis's GitHub username (Backend)
MAVIS_EMAIL="akintunde.dolapo1@gmail.com"  # Mavis's email
MAIN_OWNER="Ifeoyewole"         # Main owner's GitHub username (Frontend)
IFEOYEWOLE_USERNAME="Ifeoyewole"  # Frontend developer
```

## Usage

### Option 1: PowerShell (Windows)

```powershell
# Navigate to project directory
cd c:\Users\toyew\Documents\Don-t

# Edit the script to set your org/username
notepad setup-github-invitation.ps1

# Run the script
.\setup-github-invitation.ps1
```

### Option 2: Bash (macOS/Linux/WSL)

```bash
# Navigate to project directory
cd ~/path/to/pipe-joint-inspect

# Edit the script to set your org/username
nano setup-github-invitation.sh
# OR
code setup-github-invitation.sh

# Make it executable
chmod +x setup-github-invitation.sh

# Run the script
bash setup-github-invitation.sh
# OR
./setup-github-invitation.sh
```

## What the Scripts Do

### Step 1: Verify GitHub CLI
Ensures GitHub CLI is installed and authenticated.

### Step 2: Invite Collaborators
Sends invitations to:
- **MAVIS-creator** — Maintainer role (backend development)
- **vikky** — Maintainer role (frontend development)

### Step 3: Configure Branch Protections

**Main Branch (`main`):**
- ✅ Requires pull request before merge
- ✅ Requires 1 approval
- ✅ Requires code owner review
- ✅ Requires status checks (build, test, lint)
- ✅ Enforced for administrators

**Develop Branch (`develop`):**
- ✅ Requires pull request before merge
- ✅ Requires status checks (build, test, lint)
- ⚪ No approval requirement (faster integration)
- ⚪ Not enforced for admins

**Backend Branch (`mavis-backend`):**
- ⚪ No protection (developer can push directly)

**Frontend Branch (`vikky-frontend`):**
- ⚪ No protection (developer can push directly)

### Step 4: Output Configuration Summary
Shows the complete setup including:
- Repository details
- Team member assignments
- Branch protection rules
- Code ownership matrix

## Expected Output

```
🚀 Pipe Joint Inspection App - GitHub Setup Script
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Checking GitHub CLI installation...
✅ GitHub CLI found: gh version 2.x.x (2024-01-01)

📍 Repository: yourorg/pipe-joint-inspect

🔐 Verifying GitHub authentication...
✅ Authenticated as: ifeoyewole

👤 Inviting MAVIS-creator as collaborator...
   Role: Maintainer (can review PRs and merge)
✅ Invitation sent to MAVIS-creator

👤 Verifying Ifeoyewole frontend access...
✅ Ifeoyewole already has access

🔒 Configuring branch protections...
   Setting up 'main' branch protection...
✅ 'main' branch protected
   Setting up 'develop' branch protection...
✅ 'develop' branch protected

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ GitHub Setup Complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Configuration Summary:
   Repository: yourorg/pipe-joint-inspect
   Main Owner: Ifeoyewole
   Backend Dev: MAVIS-creator (akintunde.dolapo1@gmail.com)
   Frontend Dev: Ifeoyewole

🔐 Branch Protection:
   ✅ main: Requires PR review + status checks + code owner review
   ✅ develop: Requires PR + status checks
   ⚪ mavis-backend: Unprotected (developer can push)
   ⚪ vikky-frontend: Unprotected (developer can push)

👥 Code Ownership:
   Backend → MAVIS-creator + Ifeoyewole review
   Frontend → Ifeoyewole
   Shared files → Both developers
   Project config → Ifeoyewole review required

📝 Next Steps:
   1. MAVIS-creator will receive invitation email
   2. They should accept the invitation to access the repository
   3. Set default branch to 'develop' in GitHub repo settings
   4. Enable branch protection rules in GitHub (admin settings)
   5. Both developers can clone and start working

🚀 Ready to go! Happy coding! 🎉
```

## Manual Steps After Script

Even though the script automates most tasks, verify these in GitHub:

### 1. Accept Invitations
- MAVIS-creator will receive an email invitation
- They should accept it to get repository access

### 2. Set Default Branch
1. Go to **Settings → Repositories**
2. Under "Default branch", select **`develop`**
3. Click **Update**

### 3. Enable Branch Protection Rules

The script attempts to set these automatically, but manually verify:

1. Go to **Settings → Branches**
2. For `main` branch:
   - ✅ Require pull request reviews before merging
   - ✅ Require 1 approval
   - ✅ Require review from code owners
   - ✅ Require status checks to pass (build, test, lint)
   - ✅ Require branches to be up to date
   - ✅ Enforce for administrators
   - ✅ Require conversation resolution

3. For `develop` branch:
   - ✅ Require pull request before merging
   - ✅ Require status checks to pass (build, test, lint)
   - ✅ Require branches to be up to date

### 4. Verify CODEOWNERS
1. Go to **.github/CODEOWNERS**
2. Verify it contains:
   ```
   # Backend - Mavis (requires Ifeoyewole review)
   src/services/                   @MAVIS-creator @Ifeoyewole
   src/db/                         @MAVIS-creator @Ifeoyewole
   ...
   ```
3. GitHub will automatically request reviews from these users

### 5. Configure CI/CD
The `.github/workflows/ci.yml` file is already included. Verify it runs by:
1. Creating a test PR to `develop`
2. Watching the "Actions" tab for workflow execution

## Troubleshooting

### Script Won't Run (PowerShell)

**Error:** "cannot be loaded because running scripts is disabled"

**Solution:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup-github-invitation.ps1
```

### Script Won't Run (Bash)

**Error:** "Permission denied"

**Solution:**
```bash
chmod +x setup-github-invitation.sh
./setup-github-invitation.sh
```

### GitHub CLI Not Authenticated

**Error:** "not authenticated"

**Solution:**
```bash
gh auth logout
gh auth login
```

### Repository Not Found

**Error:** "repository not found"

**Causes:**
- Repository doesn't exist yet (create it first)
- Wrong organization/username in script
- Not authenticated with correct account

**Solution:**
```bash
# Verify repo exists
gh repo view yourorg/pipe-joint-inspect

# Check authentication
gh auth status
```

### Already Have Collaborator

If user already has access, script outputs:
```
⚠️  Could not invite MAVIS-creator (may already have access)
```

This is normal and not an error. Verify manually in GitHub:
1. Go to **Settings → Collaborators**
2. Check if user is listed

## Manual Alternative (No Script)

If you prefer to set up everything manually via GitHub UI:

### Add Collaborators
1. Go to **Settings → Collaborators**
2. Click **Add people**
3. Search for username and add with **Maintain** role

### Create Branch Protections
1. Go to **Settings → Branches**
2. Click **Add rule** for each branch
3. Configure as shown above

### Setup CODEOWNERS
1. Create `.github/CODEOWNERS` file
2. Add code ownership rules (already in repository)
3. Commit and push

### Enable CI/CD
The workflow file is already configured in `.github/workflows/ci.yml`

## Success Criteria

After running the script and completing manual steps:

- ✅ MAVIS-creator receives and accepts invitation
- ✅ Vikky has access to repository
- ✅ Default branch is set to `develop`
- ✅ `main` branch is protected with review requirements
- ✅ `develop` branch is protected with status checks
- ✅ CODEOWNERS file is recognized by GitHub
- ✅ CI/CD workflow runs on PRs
- ✅ Both developers can clone and work

## Next Steps

1. Both developers clone the repository:
   ```bash
   git clone https://github.com/yourorg/pipe-joint-inspect.git
   cd pipe-joint-inspect
   ```

2. Checkout their respective branches:
   ```bash
   # Mavis
   git checkout mavis-backend
   
   # Vikky
   git checkout vikky-frontend
   ```

3. Follow [DEVELOPMENT_SETUP.md](../DEVELOPMENT_SETUP.md) for daily workflow

4. Start implementing features!

---

**Last Updated:** May 17, 2026  
**Version:** 1.0.0
