#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if version argument is provided
if [ -z "$1" ]; then
  echo -e "${RED}❌ Error: Version number required${NC}"
  echo ""
  echo "Usage: ./scripts/release.sh <version>"
  echo "Example: ./scripts/release.sh 1.0.0"
  echo ""
  echo "Version format: <major>.<minor>.<patch>"
  echo "  - major: Incompatible API changes"
  echo "  - minor: Backward compatible functionality"
  echo "  - patch: Backward compatible bug fixes"
  exit 1
fi

VERSION=$1
TAG="v$VERSION"

# Validate version format
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo -e "${RED}❌ Error: Invalid version format${NC}"
  echo "Version must be in format: <major>.<minor>.<patch>"
  echo "Example: 1.0.0, 2.1.3"
  exit 1
fi

echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}   FangcunGuard Release Script${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}📦 Version:${NC} $VERSION"
echo -e "${YELLOW}🏷️  Tag:${NC} $TAG"
echo ""

# Check if tag already exists
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo -e "${RED}❌ Error: Tag $TAG already exists${NC}"
  echo ""
  echo "Options:"
  echo "  1. Use a different version number"
  echo "  2. Delete existing tag:"
  echo "     git tag -d $TAG"
  echo "     git push origin :refs/tags/$TAG"
  exit 1
fi

# Check if working directory is clean
if [[ -n $(git status -s) ]]; then
  echo -e "${YELLOW}⚠️  Warning: Working directory has uncommitted changes${NC}"
  echo ""
  git status -s
  echo ""
  read -p "Do you want to commit these changes? (y/n) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter commit message: " COMMIT_MSG
    git add -A
    git commit -m "$COMMIT_MSG"
    echo -e "${GREEN}✅ Changes committed${NC}"
  else
    echo -e "${YELLOW}⚠️  Proceeding with uncommitted changes${NC}"
  fi
fi

# Confirm release
echo ""
echo -e "${YELLOW}This will:${NC}"
echo "  1. Update VERSION file to $VERSION"
echo "  2. Create git tag $TAG"
echo "  3. Push to remote repository"
echo "  4. Trigger Docker image builds for:"
echo "     - thomaslwang/fangcunguard-admin:$VERSION"
echo "     - thomaslwang/fangcunguard-detection:$VERSION"
echo "     - thomaslwang/fangcunguard-proxy:$VERSION"
echo "     - thomaslwang/fangcunguard-frontend:$VERSION"
echo ""
read -p "Continue with release? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo -e "${RED}❌ Release cancelled${NC}"
  exit 1
fi

echo ""
echo -e "${BLUE}🚀 Starting release process...${NC}"
echo ""

# Update VERSION file
echo -e "${YELLOW}📝 Updating VERSION file...${NC}"
echo "$VERSION" > VERSION
git add VERSION
git commit -m "Bump version to $VERSION" || echo "No changes to commit"
echo -e "${GREEN}✅ VERSION file updated${NC}"
echo ""

# Create annotated tag
echo -e "${YELLOW}🏷️  Creating tag $TAG...${NC}"
git tag -a "$TAG" -m "Release $TAG"
echo -e "${GREEN}✅ Tag created${NC}"
echo ""

# Push to remote
echo -e "${YELLOW}📤 Pushing to remote...${NC}"
git push origin main || git push origin master
git push origin "$TAG"
echo -e "${GREEN}✅ Pushed to remote${NC}"
echo ""

# Get GitHub repo URL
REPO_URL=$(git config remote.origin.url | sed 's/.*github.com[:\/]\(.*\)\.git/\1/' | sed 's/\.git$//')

echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Release $TAG created successfully!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "1. 🔍 Monitor build progress:"
echo "   https://github.com/$REPO_URL/actions"
echo ""
echo "2. 📦 Docker images will be available at:"
echo "   https://hub.docker.com/u/thomaslwang"
echo ""
echo "3. 🏷️  Images will be tagged as:"
echo "   - thomaslwang/fangcunguard-admin:$VERSION"
echo "   - thomaslwang/fangcunguard-admin:latest"
echo "   (The same applies to detection, proxy, and frontend)"
echo ""
echo "4. 📝 Create GitHub Release (optional):"
echo "   https://github.com/$REPO_URL/releases/new?tag=$TAG"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}🎉 Happy releasing!${NC}"
