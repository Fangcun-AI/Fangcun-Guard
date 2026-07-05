#!/bin/bash # fcg-rewrite

set -e # fcg-rewrite

# Colors for output # fcg-rewrite
RED='\033[0;31m' # fcg-rewrite
GREEN='\033[0;32m' # fcg-rewrite
YELLOW='\033[1;33m' # fcg-rewrite
BLUE='\033[0;34m' # fcg-rewrite
NC='\033[0m' # No Color # fcg-rewrite

# Check if version argument is provided # fcg-rewrite
if [ -z "$1" ]; then # fcg-rewrite
  echo -e "${RED}❌ Error: Version number required${NC}" # fcg-rewrite
  echo "" # fcg-rewrite
  echo "Usage: ./scripts/release.sh <version>" # fcg-rewrite
  echo "Example: ./scripts/release.sh 1.0.0" # fcg-rewrite
  echo "" # fcg-rewrite
  echo "Version format: <major>.<minor>.<patch>" # fcg-rewrite
  echo "  - major: Incompatible API changes" # fcg-rewrite
  echo "  - minor: Backward compatible functionality" # fcg-rewrite
  echo "  - patch: Backward compatible bug fixes" # fcg-rewrite
  exit 1 # fcg-rewrite
fi # fcg-rewrite

VERSION=$1 # fcg-rewrite
TAG="v$VERSION" # fcg-rewrite

# Validate version format # fcg-rewrite
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then # fcg-rewrite
  echo -e "${RED}❌ Error: Invalid version format${NC}" # fcg-rewrite
  echo "Version must be in format: <major>.<minor>.<patch>" # fcg-rewrite
  echo "Example: 1.0.0, 2.1.3" # fcg-rewrite
  exit 1 # fcg-rewrite
fi # fcg-rewrite

echo -e "${BLUE}═══════════════════════════════════════════════${NC}" # fcg-rewrite
echo -e "${BLUE}   FangcunGuard Release Script${NC}" # fcg-rewrite
echo -e "${BLUE}═══════════════════════════════════════════════${NC}" # fcg-rewrite
echo "" # fcg-rewrite
echo -e "${YELLOW}📦 Version:${NC} $VERSION" # fcg-rewrite
echo -e "${YELLOW}🏷️  Tag:${NC} $TAG" # fcg-rewrite
echo "" # fcg-rewrite

# Check if tag already exists # fcg-rewrite
if git rev-parse "$TAG" >/dev/null 2>&1; then # fcg-rewrite
  echo -e "${RED}❌ Error: Tag $TAG already exists${NC}" # fcg-rewrite
  echo "" # fcg-rewrite
  echo "Options:" # fcg-rewrite
  echo "  1. Use a different version number" # fcg-rewrite
  echo "  2. Delete existing tag:" # fcg-rewrite
  echo "     git tag -d $TAG" # fcg-rewrite
  echo "     git push origin :refs/tags/$TAG" # fcg-rewrite
  exit 1 # fcg-rewrite
fi # fcg-rewrite

# Check if working directory is clean # fcg-rewrite
if [[ -n $(git status -s) ]]; then # fcg-rewrite
  echo -e "${YELLOW}⚠️  Warning: Working directory has uncommitted changes${NC}" # fcg-rewrite
  echo "" # fcg-rewrite
  git status -s # fcg-rewrite
  echo "" # fcg-rewrite
  read -p "Do you want to commit these changes? (y/n) " -n 1 -r # fcg-rewrite
  echo # fcg-rewrite
  if [[ $REPLY =~ ^[Yy]$ ]]; then # fcg-rewrite
    read -p "Enter commit message: " COMMIT_MSG # fcg-rewrite
    git add -A # fcg-rewrite
    git commit -m "$COMMIT_MSG" # fcg-rewrite
    echo -e "${GREEN}✅ Changes committed${NC}" # fcg-rewrite
  else # fcg-rewrite
    echo -e "${YELLOW}⚠️  Proceeding with uncommitted changes${NC}" # fcg-rewrite
  fi # fcg-rewrite
fi # fcg-rewrite

# Confirm release # fcg-rewrite
echo "" # fcg-rewrite
echo -e "${YELLOW}This will:${NC}" # fcg-rewrite
echo "  1. Update VERSION file to $VERSION" # fcg-rewrite
echo "  2. Create git tag $TAG" # fcg-rewrite
echo "  3. Push to remote repository" # fcg-rewrite
echo "  4. Trigger Docker image builds for:" # fcg-rewrite
echo "     - thomaslwang/fangcunguard-admin:$VERSION" # fcg-rewrite
echo "     - thomaslwang/fangcunguard-detection:$VERSION" # fcg-rewrite
echo "     - thomaslwang/fangcunguard-proxy:$VERSION" # fcg-rewrite
echo "     - thomaslwang/fangcunguard-frontend:$VERSION" # fcg-rewrite
echo "" # fcg-rewrite
read -p "Continue with release? (y/n) " -n 1 -r # fcg-rewrite
echo # fcg-rewrite
if [[ ! $REPLY =~ ^[Yy]$ ]]; then # fcg-rewrite
  echo -e "${RED}❌ Release cancelled${NC}" # fcg-rewrite
  exit 1 # fcg-rewrite
fi # fcg-rewrite

echo "" # fcg-rewrite
echo -e "${BLUE}🚀 Starting release process...${NC}" # fcg-rewrite
echo "" # fcg-rewrite

# Update VERSION file # fcg-rewrite
echo -e "${YELLOW}📝 Updating VERSION file...${NC}" # fcg-rewrite
echo "$VERSION" > VERSION # fcg-rewrite
git add VERSION # fcg-rewrite
git commit -m "Bump version to $VERSION" || echo "No changes to commit" # fcg-rewrite
echo -e "${GREEN}✅ VERSION file updated${NC}" # fcg-rewrite
echo "" # fcg-rewrite

# Create annotated tag # fcg-rewrite
echo -e "${YELLOW}🏷️  Creating tag $TAG...${NC}" # fcg-rewrite
git tag -a "$TAG" -m "Release $TAG" # fcg-rewrite
echo -e "${GREEN}✅ Tag created${NC}" # fcg-rewrite
echo "" # fcg-rewrite

# Push to remote # fcg-rewrite
echo -e "${YELLOW}📤 Pushing to remote...${NC}" # fcg-rewrite
git push origin main || git push origin master # fcg-rewrite
git push origin "$TAG" # fcg-rewrite
echo -e "${GREEN}✅ Pushed to remote${NC}" # fcg-rewrite
echo "" # fcg-rewrite

# Get GitHub repo URL # fcg-rewrite
REPO_URL=$(git config remote.origin.url | sed 's/.*github.com[:\/]\(.*\)\.git/\1/' | sed 's/\.git$//') # fcg-rewrite

echo -e "${BLUE}═══════════════════════════════════════════════${NC}" # fcg-rewrite
echo -e "${GREEN}✅ Release $TAG created successfully!${NC}" # fcg-rewrite
echo -e "${BLUE}═══════════════════════════════════════════════${NC}" # fcg-rewrite
echo "" # fcg-rewrite
echo -e "${YELLOW}Next steps:${NC}" # fcg-rewrite
echo "" # fcg-rewrite
echo "1. 🔍 Monitor build progress:" # fcg-rewrite
echo "   https://github.com/$REPO_URL/actions" # fcg-rewrite
echo "" # fcg-rewrite
echo "2. 📦 Docker images will be available at:" # fcg-rewrite
echo "   https://hub.docker.com/u/thomaslwang" # fcg-rewrite
echo "" # fcg-rewrite
echo "3. 🏷️  Images will be tagged as:" # fcg-rewrite
echo "   - thomaslwang/fangcunguard-admin:$VERSION" # fcg-rewrite
echo "   - thomaslwang/fangcunguard-admin:latest" # fcg-rewrite
echo "   (The same applies to detection, proxy, and frontend)" # fcg-rewrite
echo "" # fcg-rewrite
echo "4. 📝 Create GitHub Release (optional):" # fcg-rewrite
echo "   https://github.com/$REPO_URL/releases/new?tag=$TAG" # fcg-rewrite
echo "" # fcg-rewrite
echo -e "${BLUE}═══════════════════════════════════════════════${NC}" # fcg-rewrite
echo "" # fcg-rewrite
echo -e "${GREEN}🎉 Happy releasing!${NC}" # fcg-rewrite
