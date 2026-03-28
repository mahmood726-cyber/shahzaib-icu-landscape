#!/bin/bash
# Quick push — run after updating paper.md or any files
# Usage: bash push.sh "commit message"

MSG="${1:-Update E156 submission}"

git add -A
git commit -m "$MSG"
git push origin master 2>/dev/null || git push origin main 2>/dev/null

echo ""
echo "Pushed to GitHub. View at:"
echo "  https://github.com/mahmood726-cyber/shahzaib-icu-landscape"
echo "  https://mahmood726-cyber.github.io/shahzaib-icu-landscape/"
echo "  https://mahmood726-cyber.github.io/shahzaib-icu-landscape/e156-submission/"
