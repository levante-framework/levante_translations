#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV_DIR="$ROOT_DIR/.venv-validate-audio"

ensure_venv() {
	if [[ ! -d "$VENV_DIR" || ! -f "$VENV_DIR/bin/activate" ]]; then
		echo "ℹ️  Setting up validate-audio virtual environment..."
		npm run validate:audio:setup
	fi
	# shellcheck disable=SC1090
	source "$VENV_DIR/bin/activate"
}

parse_lang_and_args() {
	local expect_value="false"
	LANG_INPUT="${npm_config_lang:-}"
	EXTRA_ARGS=()

	for arg in "$@"; do
		if [[ "$expect_value" == "true" ]]; then
			LANG_INPUT="$arg"
			expect_value="false"
			continue
		fi

		case "$arg" in
			--lang=*)
				LANG_INPUT="${arg#--lang=}"
				;;
			--lang)
				expect_value="true"
				;;
			*)
				EXTRA_ARGS+=("$arg")
				;;
		esac
	done

	if [[ "$expect_value" == "true" ]]; then
		echo "Usage: npm run validate:audio:lang -- --lang=<code> [validator options]" >&2
		exit 2
	fi

	if [[ -z "${LANG_INPUT:-}" ]]; then
		echo "Usage: npm run validate:audio:lang -- --lang=<code> [validator options]" >&2
		exit 2
	fi
}

ensure_venv
parse_lang_and_args "$@"

LANG_BASE="${LANG_INPUT%%-*}"
if [[ -z "$LANG_BASE" ]]; then
	LANG_BASE="$LANG_INPUT"
fi

TARGET_DIR="audio_files/${LANG_INPUT}"

if [[ ! -d "$TARGET_DIR" ]]; then
	echo "❌ Missing directory: ${TARGET_DIR}" >&2
	exit 2
fi

CMD=(python -m validate_audio.cli "$TARGET_DIR" --language "$LANG_BASE" --web-dashboard)
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
	CMD+=("${EXTRA_ARGS[@]}")
fi

echo "▶️  Running: ${CMD[*]}"
"${CMD[@]}"

