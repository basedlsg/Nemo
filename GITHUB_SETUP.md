# GitHub Repository Setup Guide

This guide will help you push the Chinese Energy Compliance Assistant to a private GitHub repository.

## 📋 Prerequisites

- **GitHub Account**: Create one at [github.com](https://github.com) if you don't have one
- **Git**: Install from [git-scm.com](https://git-scm.com)
- **GitHub CLI** (optional): Install from [cli.github.com](https://cli.github.com)

## 🚀 Quick Setup Using GitHub CLI

### 1. Install GitHub CLI (Recommended)
```bash
# Windows (using winget)
winget install GitHub.cli

# macOS (using Homebrew)
brew install gh

# Linux
# Follow instructions at https://github.com/cli/cli#installation
```

### 2. Authenticate with GitHub
```bash
gh auth login
```
Follow the prompts to authenticate with your GitHub account.

### 3. Create Private Repository
```bash
gh repo create chinese-energy-compliance-assistant --private --description "Enhanced AI assistant for Chinese energy compliance with metadata-first retrieval" --source=. --remote=origin --push
```

This command will:
- Create a private repository named `chinese-energy-compliance-assistant`
- Set it as the remote origin
- Push all files to the repository

## 🔧 Manual Setup (Without GitHub CLI)

### 1. Initialize Git Repository
```bash
# Initialize git in your project directory
git init

# Add all files
git add .

# Commit the files
git commit -m "Initial commit: Chinese Energy Compliance Assistant v2.0"
```

### 2. Create Repository on GitHub
1. Go to [github.com](https://github.com) and sign in
2. Click the **"+"** button in the top right corner
3. Select **"New repository"**
4. Repository name: `chinese-energy-compliance-assistant`
5. Description: `Enhanced AI assistant for Chinese energy compliance with metadata-first retrieval`
6. **Check "Private"**
7. **Do NOT** initialize with README, .gitignore, or license (we already have these)
8. Click **"Create repository"**

### 3. Connect Local Repository to GitHub
```bash
# Add the remote repository (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/chinese-energy-compliance-assistant.git

# Push to GitHub
git push -u origin main
```

## 📁 What Gets Pushed

The following files and directories will be included in your repository:

### Core Application Files
- `main.py` - Application entry point
- `services/` - Core application modules
- `requirements.txt` - Python dependencies
- `README.md` - Project documentation
- `.gitignore` - Git ignore rules

### Configuration Templates
- `.env.example` - Environment configuration template
- `deploy.sh` / `deploy.bat` - Deployment scripts

### Testing & Documentation
- `test_six_queries.py` - Comprehensive test suite
- `ENHANCED_SYSTEM_TEST_REPORT.md` - Detailed test results
- `CHIEF_ARCHITECT_REPORT.md` - Architecture documentation
- `GITHUB_SETUP.md` - This guide

### Enhanced Features
- `services/core/query_normalize.py` - Query normalization
- `services/core/metadata_extractor.py` - Chinese document parsing
- `data/registry/sources.yaml` - Canonical source registry
- `data/storage/migrations/002_metadata_fields.sql` - Database schema

## 🔒 Security Considerations

### 1. API Keys Protection
⚠️ **Important**: Never commit actual API keys to the repository!

The `.gitignore` file already excludes:
- `.env` (contains actual API keys)
- Any files with `secret`, `key`, or `credential` in the name

### 2. Verify .gitignore is Working
```bash
# Check what will be committed
git status --porcelain

# Should NOT show:
# .env
# Any files containing API keys
```

### 3. Environment Setup
After cloning the repository, users should:
```bash
# Copy template and add their own keys
cp .env.example .env
# Edit .env with actual API keys
```

## 🔧 Repository Configuration

### 1. Branch Protection (Recommended)
1. Go to your repository on GitHub
2. Click **Settings** → **Branches**
3. Click **"Add rule"**
4. Branch name pattern: `main`
5. Enable:
   - ✅ Require pull request reviews
   - ✅ Require status checks to pass
   - ✅ Require branches to be up to date

### 2. Add Collaborators
1. Go to your repository on GitHub
2. Click **Settings** → **Collaborators and teams**
3. Add team members or individual collaborators

### 3. Enable Features
In repository settings, consider enabling:
- ✅ Issues (for bug tracking)
- ✅ Discussions (for team communication)
- ✅ Wiki (for documentation)
- ✅ Projects (for project management)

## 🚀 Deployment Options

### Option 1: Direct Server Deployment
```bash
# On your server
git clone https://github.com/YOUR_USERNAME/chinese-energy-compliance-assistant.git
cd chinese-energy-compliance-assistant
bash deploy.sh  # or deploy.bat on Windows
python main.py
```

### Option 2: Docker Deployment
Create a `Dockerfile` and `docker-compose.yml` for containerized deployment.

### Option 3: Cloud Deployment
- **Heroku**: Add `Procfile` and deploy
- **AWS**: Use Elastic Beanstalk or ECS
- **Azure**: Use App Service or Container Instances
- **GCP**: Use Cloud Run or App Engine

## 📊 Repository Statistics

After pushing, your repository will contain:
- **~20 Python files** with enhanced retrieval logic
- **6 comprehensive test queries** for validation
- **Complete documentation** and setup guides
- **Production-ready deployment** scripts
- **Metadata-first retrieval system** implementation

## 🎯 Next Steps

1. **Push to GitHub** using one of the methods above
2. **Configure API keys** in your local `.env` file
3. **Test the system** with the provided test suite
4. **Set up CI/CD** for automated testing and deployment
5. **Invite collaborators** and start development

## 📞 Support

If you encounter issues:
1. Check the **Issues** tab in your GitHub repository
2. Create a new issue with detailed information
3. Reference this setup guide if needed

---

**Repository**: `chinese-energy-compliance-assistant`
**Status**: Ready for deployment
**Enhanced Features**: Metadata-first retrieval, Chinese document support, comprehensive testing
