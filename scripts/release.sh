#!/bin/bash
# release.sh
# Script to package and create/update a GitHub release with a locally generated conventional changelog

# Change to repository root
cd "$(dirname "$0")/.."

echo "--- Starting Ollie Release Process ---"

# 1. Determine current version
CURRENT_VERSION=$(grep -m 1 'version = "' backend/pyproject.toml | cut -d '"' -f 2)
echo "Current version in backend/pyproject.toml: $CURRENT_VERSION"
read -p "Enter version to release (default $CURRENT_VERSION): " NEW_VERSION

NEW_VERSION=${NEW_VERSION:-$CURRENT_VERSION}
TAG_NAME="v$NEW_VERSION"
ZIP_NAME="ollie-$TAG_NAME.zip"

# Check if the tag already exists
if git rev-parse "$TAG_NAME" >/dev/null 2>&1; then
    echo "⚠️ Version $TAG_NAME already exists. Re-releasing."
    RE_RELEASE=true
else
    echo "🚀 New version target: $TAG_NAME"
    RE_RELEASE=false
fi

# 2. Tagging & Push
echo "Tagging and Pushing..."
if [ "$RE_RELEASE" = true ]; then
    git tag -af "$TAG_NAME" -m "Re-release $TAG_NAME"
    git push origin "$TAG_NAME" --force
else
    git tag -a "$TAG_NAME" -m "Release $TAG_NAME"
    git push origin "$TAG_NAME"
fi

# 3. Build the Slim Release Bundle
echo "📦 Building slim release bundle..."
RELEASE_DIR="ollie"
mkdir -p "$RELEASE_DIR"
sed "s/:latest/:${TAG_NAME}/g" docker-compose.prod.yml > "$RELEASE_DIR/docker-compose.yml"
cat <<EOF > "$RELEASE_DIR/README.md"
# Ollie $TAG_NAME

To get started with Ollie, follow these steps:

1. Ensure you have Docker and Docker Compose installed.
2. Open your terminal in this folder (\`ollie\`).
3. Run the services:
   \`\`\`bash
   docker compose up -d
   \`\`\`

EOF
zip -j "$ZIP_NAME" "$RELEASE_DIR"/*

# 4. Generate Combined Release Notes
echo "Generating combined release notes..."

# A) Create the static guide part
cat <<EOF > generated_release_notes.md
## 🚀 Ollie $TAG_NAME is here!

This release includes the production-ready bundle and the Outlook manifest.

### 🛠 Installation

1. **Download the Bundle:** Download \`$ZIP_NAME\` from the assets below and extract it.
2. **Start Ollie:** Open your terminal in the extracted folder and run:
   \`\`\`bash
   docker compose up -d
   \`\`\`
3. **Outlook Integration:** Download \`manifest.prod.xml\` from the assets and upload it to your Outlook (Integrated Apps -> Add from file) or get served by your organization.

---
## 🆕 What's Changed
EOF

# B) Local Conventional Changelog Generation
echo "Generating changelog from git history..."
# Find the previous tag for the range
PREV_TAG=$(git describe --tags --abbrev=0 "${TAG_NAME}^" 2>/dev/null || echo "")

if [ -z "$PREV_TAG" ]; then
    # First release: get all commits
    LOG_RANGE="HEAD"
else
    LOG_RANGE="$PREV_TAG..HEAD"
fi

# Extract Features
echo "### 🚀 Features" >> generated_release_notes.md
git log "$LOG_RANGE" --pretty=format:"* %s (%h)" | grep -i "^* feat" >> generated_release_notes.md || echo "* No new features." >> generated_release_notes.md

# Extract Fixes
echo -e "\n### 🐛 Bug Fixes" >> generated_release_notes.md
git log "$LOG_RANGE" --pretty=format:"* %s (%h)" | grep -i "^* fix" >> generated_release_notes.md || echo "* No bug fixes." >> generated_release_notes.md

# Extract Others (Optional)
echo -e "\n### 🧰 Maintenance" >> generated_release_notes.md
git log "$LOG_RANGE" --pretty=format:"* %s (%h)" | grep -E -i "^\* (chore|docs|ci|refactor|test|style)" >> generated_release_notes.md || echo "* No maintenance changes." >> generated_release_notes.md

# 5. Create or Update GitHub Release
echo "🚢 Uploading assets to GitHub..."
gh release create "$TAG_NAME" --title "Ollie Release $TAG_NAME" --notes "" 2>/dev/null || true
gh release edit "$TAG_NAME" --notes-file generated_release_notes.md
gh release upload "$TAG_NAME" "$ZIP_NAME" "manifest/manifest.prod.xml" --clobber

# 6. Cleanup
rm -rf "$RELEASE_DIR" "$ZIP_NAME" generated_release_notes.md

echo "--- Release Process Finished ---"
echo "✅ $TAG_NAME is live with conventional changelog!"
