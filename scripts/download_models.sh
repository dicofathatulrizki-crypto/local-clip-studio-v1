#!/usr/bin/env bash
set -euo pipefail

# AI Model download script for Local Clip Studio
# Usage: ./download_models.sh [model_category]
#   Categories: whisper, yolo, llm, all
#   Default: all

MODELS_DIR="${HOME}/.localclip/models"

# Model definitions
declare -A MODELS
MODELS["whisper-large-v3"]="whisper|large-v3|https://huggingface.co/guillaumeklf/faster-whisper-large-v3|3100"
MODELS["whisper-medium"]="whisper|medium|https://huggingface.co/guillaumeklf/faster-whisper-medium|1500"
MODELS["yolov8n-face"]="yolo|yolov8n-face|https://github.com/akanametov/yolov8-face/releases/download/v0.0.0/yolov8n-face.pt|6"
MODELS["all-MiniLM-L6-v2"]="embeddings|all-MiniLM-L6-v2|https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2|80"

download_hf_model() {
    local model_id="$1"
    local target_dir="$2"
    echo "Downloading ${model_id}..."
    python3 -c "
import os, sys
try:
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id='${model_id}', local_dir='${target_dir}', local_dir_use_symlinks=False)
    print('Download complete.')
except ImportError:
    print('huggingface_hub not installed. Install with: pip install huggingface_hub')
    sys.exit(1)
"
}

download_direct() {
    local url="$1"
    local target="$2"
    echo "Downloading ${target}..."
    mkdir -p "$(dirname "$target")"
    if command -v wget &> /dev/null; then
        wget -O "$target" "$url"
    elif command -v curl &> /dev/null; then
        curl -L -o "$target" "$url"
    else
        echo "Neither wget nor curl found. Install one of them."
        exit 1
    fi
}

download_model() {
    local name="$1"
    local entry="${MODELS[$name]:-}"
    if [ -z "$entry" ]; then
        echo "Unknown model: $name"
        echo "Available: ${!MODELS[*]}"
        return 1
    fi

    IFS='|' read -r category model_id url size_mb <<< "$entry"
    local target_dir="${MODELS_DIR}/${category}"

    if [ -f "${target_dir}/${model_id}/.downloaded" ]; then
        echo "  [SKIP] ${name} already downloaded."
        return 0
    fi

    echo ""
    echo "Downloading ${name} (~${size_mb} MB)..."
    mkdir -p "$target_dir"

    case "$category" in
        whisper|embeddings)
            download_hf_model "$url" "${target_dir}/${model_id}"
            ;;
        yolo)
            download_direct "$url" "${target_dir}/${model_id}.pt"
            ;;
    esac

    touch "${target_dir}/${model_id}/.downloaded" 2>/dev/null || true
    echo "  [DONE] ${name}"
}

main() {
    mkdir -p "$MODELS_DIR"
    local category="${1:-all}"

    case "$category" in
        all)
            for model in "${!MODELS[@]}"; do
                download_model "$model"
            done
            ;;
        whisper)
            download_model "whisper-large-v3"
            download_model "whisper-medium"
            ;;
        yolo)
            download_model "yolov8n-face"
            ;;
        llm)
            echo "LLM models require manual download. See documentation."
            ;;
        *)
            download_model "$category"
            ;;
    esac

    echo ""
    echo "Download complete. Models stored in: ${MODELS_DIR}"
    du -sh "$MODELS_DIR" 2>/dev/null || true
}

main "$@"
