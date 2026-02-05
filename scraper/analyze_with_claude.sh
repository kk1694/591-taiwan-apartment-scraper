#!/bin/bash
#
# Analyze apartment listings using Claude Code
# Each listing is analyzed in a separate Claude instance for clean context
# Resumable - tracks progress in a checkpoint file
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/../data"
IMAGES_DIR="$DATA_DIR/images"
LISTINGS_FILE="$DATA_DIR/listings.json"
CHECKPOINT_FILE="$DATA_DIR/analysis_checkpoint.json"
RESULTS_DIR="$DATA_DIR/analysis_results"

# Create results directory
mkdir -p "$RESULTS_DIR"

# Initialize checkpoint if it doesn't exist
if [[ ! -f "$CHECKPOINT_FILE" ]]; then
    echo '{"analyzed_ids": []}' > "$CHECKPOINT_FILE"
fi

# Get list of already analyzed IDs
get_analyzed_ids() {
    jq -r '.analyzed_ids[]' "$CHECKPOINT_FILE" 2>/dev/null || echo ""
}

# Mark a listing as analyzed
mark_analyzed() {
    local listing_id="$1"
    local tmp_file=$(mktemp)
    jq --arg id "$listing_id" '.analyzed_ids += [$id] | .analyzed_ids |= unique' "$CHECKPOINT_FILE" > "$tmp_file"
    mv "$tmp_file" "$CHECKPOINT_FILE"
}

# Get listing count
get_listing_count() {
    jq '.listings | length' "$LISTINGS_FILE"
}

# Get listing by index
get_listing() {
    local index="$1"
    jq ".listings[$index]" "$LISTINGS_FILE"
}

# Get listing ID by index
get_listing_id() {
    local index="$1"
    jq -r ".listings[$index].id" "$LISTINGS_FILE"
}

# Check if listing has images
has_images() {
    local listing_id="$1"
    local img_dir="$IMAGES_DIR/$listing_id"
    [[ -d "$img_dir" ]] && [[ -n "$(ls -A "$img_dir" 2>/dev/null)" ]]
}

# Build the analysis prompt for a listing
build_prompt() {
    local listing_id="$1"
    local listing_json="$2"
    local img_dir="$IMAGES_DIR/$listing_id"

    # Extract listing details
    local district=$(echo "$listing_json" | jq -r '.district // "Unknown"')
    local size_ping=$(echo "$listing_json" | jq -r '.size_ping // "?"')
    local size_sqm=$(echo "$listing_json" | jq -r '.size_sqm // "?"')
    local floor=$(echo "$listing_json" | jq -r '.floor // "Unknown"')
    local layout=$(echo "$listing_json" | jq -r '.layout // "Unknown"')
    local price=$(echo "$listing_json" | jq -r '.base_rent_nt // "?"')
    local description=$(echo "$listing_json" | jq -r '.description_zh // ""')
    local url=$(echo "$listing_json" | jq -r '.url // ""')

    # Build image reading commands
    local image_prompt=""
    if [[ -d "$img_dir" ]]; then
        local images=($(ls "$img_dir"/*.jpg 2>/dev/null | head -5))
        if [[ ${#images[@]} -gt 0 ]]; then
            image_prompt="First, read and analyze these apartment images:"
            for img in "${images[@]}"; do
                image_prompt="$image_prompt
- $img"
            done
            image_prompt="$image_prompt

"
        fi
    fi

    cat << EOF
${image_prompt}Analyze this Taiwan apartment listing for a foreign couple expecting a baby.

Listing ID: $listing_id
URL: $url

Metadata:
- District: $district
- Size: $size_ping ping ($size_sqm sqm)
- Floor: $floor
- Layout: $layout
- Price: NT\$$price/month

Chinese description:
$description

Based on the images (if any) and description above, provide your analysis as JSON with these fields:

1. is_modern (Y/N/?): Modern fixtures, clean condition, updated appliances?
2. has_elevator (Y/N/?): Does the building have an elevator? Look for clues in images/description.
3. is_flat (Y/N/?): Is this a residential apartment? (not a store, garage, office, or commercial space)
4. location (string or null): Any specific location info (road name, building name, nearby landmark)?
5. notes (string): 2-3 sentences in English summarizing: condition, baby safety concerns (balcony railings, stairs, sharp corners), natural light, cleanliness, any red flags.

IMPORTANT: Respond with ONLY valid JSON, no markdown code blocks, no other text:
{"is_modern": "Y", "has_elevator": "Y", "is_flat": "Y", "location": "Example Road", "notes": "Your notes here"}
EOF
}

# Analyze a single listing with Claude
analyze_listing() {
    local listing_id="$1"
    local listing_json="$2"
    local result_file="$RESULTS_DIR/${listing_id}.json"

    # Build the prompt
    local prompt=$(build_prompt "$listing_id" "$listing_json")

    # Call Claude Code with the prompt
    # Using --print to get just the response, -p for prompt mode
    local response
    response=$(echo "$prompt" | claude --print 2>/dev/null) || {
        echo "  Error: Claude analysis failed"
        return 1
    }

    # Try to extract JSON from response (handle potential markdown wrapping)
    local json_result
    json_result=$(echo "$response" | grep -o '{[^}]*}' | head -1) || json_result="$response"

    # Validate it's valid JSON
    if echo "$json_result" | jq . >/dev/null 2>&1; then
        echo "$json_result" > "$result_file"
        echo "  Saved result to $result_file"
        return 0
    else
        # Save raw response for debugging
        echo "$response" > "$result_file.raw"
        echo "  Warning: Could not parse JSON, saved raw response to $result_file.raw"
        return 1
    fi
}

# Main loop
main() {
    echo "========================================"
    echo "591 Listing Analyzer with Claude Code"
    echo "========================================"
    echo ""

    if [[ ! -f "$LISTINGS_FILE" ]]; then
        echo "Error: $LISTINGS_FILE not found"
        echo "Run extract_details.py first"
        exit 1
    fi

    local total=$(get_listing_count)
    local analyzed_ids=$(get_analyzed_ids)
    local analyzed_count=$(echo "$analyzed_ids" | grep -c . || echo 0)

    echo "Total listings: $total"
    echo "Already analyzed: $analyzed_count"
    echo "Remaining: $((total - analyzed_count))"
    echo ""
    echo "Press Ctrl+C to stop (progress is saved)"
    echo ""

    # Process each listing
    for ((i=0; i<total; i++)); do
        local listing_id=$(get_listing_id "$i")

        # Skip if already analyzed
        if echo "$analyzed_ids" | grep -q "^${listing_id}$"; then
            continue
        fi

        local listing_json=$(get_listing "$i")
        local current=$((analyzed_count + 1))

        echo "[$current/$total] Analyzing listing $listing_id..."

        # Check if has images or description
        local has_img=false
        local has_desc=false

        if has_images "$listing_id"; then
            has_img=true
        fi

        local desc=$(echo "$listing_json" | jq -r '.description_zh // ""')
        if [[ -n "$desc" && "$desc" != "null" ]]; then
            has_desc=true
        fi

        if [[ "$has_img" == "false" && "$has_desc" == "false" ]]; then
            echo "  Skipping: no images or description"
            mark_analyzed "$listing_id"
            analyzed_count=$((analyzed_count + 1))
            continue
        fi

        # Analyze with Claude
        if analyze_listing "$listing_id" "$listing_json"; then
            mark_analyzed "$listing_id"
            analyzed_count=$((analyzed_count + 1))
        else
            echo "  Failed to analyze, will retry on next run"
        fi

        # Small delay between API calls
        sleep 1
    done

    echo ""
    echo "========================================"
    echo "Analysis complete!"
    echo "Results saved in: $RESULTS_DIR"
    echo ""
    echo "Next step: Run merge_analysis.py to update listings.json"
    echo "========================================"
}

# Handle Ctrl+C gracefully
trap 'echo ""; echo "Interrupted. Progress saved. Run again to resume."; exit 0' INT

main "$@"
