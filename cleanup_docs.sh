#!/bin/bash

# Cleanup Script - Remove Redundant Documentation Files
# All information has been consolidated into MASTER_DOCUMENTATION.md

echo "================================================"
echo "  Documentation Cleanup Script"
echo "================================================"
echo ""
echo "This script will DELETE the following markdown files:"
echo ""
echo "  - ANSWERS.md"
echo "  - BUGFIX_NODE_NAMES.md"
echo "  - CONTROL_GUIDE.md"
echo "  - FINAL_CONFIGURATION.md"
echo "  - FINAL_SETUP.md"
echo "  - IMPROVEMENTS.md"
echo "  - ISSUE_RESOLVED.md"
echo "  - QUICK_REFERENCE.md"
echo "  - QUICK_RUN.md"
echo "  - QUICK_START_CARD.md"
echo "  - RUN_GUIDE.md"
echo ""
echo "The following files will be KEPT:"
echo ""
echo "  ✓ MASTER_DOCUMENTATION.md (NEW - contains everything)"
echo "  ✓ README.md (project overview)"
echo "  ✓ docs/SETUP_GUIDE.md (detailed setup)"
echo "  ✓ docs/architecture.md (technical architecture)"
echo ""
echo "================================================"
echo ""

# Ask for confirmation
read -p "Do you want to proceed? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted. No files were deleted."
    exit 0
fi

echo ""
echo "Deleting redundant files..."

# Array of files to delete
files_to_delete=(
    "ANSWERS.md"
    "BUGFIX_NODE_NAMES.md"
    "CONTROL_GUIDE.md"
    "FINAL_CONFIGURATION.md"
    "FINAL_SETUP.md"
    "IMPROVEMENTS.md"
    "ISSUE_RESOLVED.md"
    "QUICK_REFERENCE.md"
    "QUICK_RUN.md"
    "QUICK_START_CARD.md"
    "RUN_GUIDE.md"
)

deleted_count=0
not_found_count=0

for file in "${files_to_delete[@]}"; do
    if [ -f "$file" ]; then
        rm "$file"
        echo "  ✓ Deleted: $file"
        deleted_count=$((deleted_count + 1))
    else
        echo "  ⚠ Not found: $file"
        not_found_count=$((not_found_count + 1))
    fi
done

echo ""
echo "================================================"
echo "  Cleanup Complete!"
echo "================================================"
echo ""
echo "  Files deleted: $deleted_count"
echo "  Files not found: $not_found_count"
echo ""
echo "  ✓ MASTER_DOCUMENTATION.md contains all information"
echo "  ✓ README.md still available for quick reference"
echo ""
echo "  You can now refer to MASTER_DOCUMENTATION.md for"
echo "  complete project documentation."
echo ""

