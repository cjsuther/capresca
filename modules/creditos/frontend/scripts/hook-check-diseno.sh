#!/usr/bin/env bash
# Hook PostToolUse (Write|Edit): corre el candado de diseño sobre el archivo editado si es una página
# del frontend. Si viola el principio «tabla única», sale 2 → Claude Code bloquea y muestra el motivo.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"

input="$(cat)"
fp="$(printf '%s' "$input" | python3 -c 'import sys,json
try:
    d=json.load(sys.stdin); print((d.get("tool_input") or {}).get("file_path","") or "")
except Exception:
    print("")' 2>/dev/null || true)"

# Sólo aplica a páginas del frontend; cualquier otra edición pasa sin ruido.
case "$fp" in
  */frontend/src/pages/*.tsx) ;;
  *) exit 0 ;;
esac

command -v node >/dev/null 2>&1 || exit 0   # sin node no bloqueamos (no romper edición)
if ! node "$here/check-diseno.mjs" "$fp" 1>&2; then
  exit 2   # violación → feedback bloqueante a Claude
fi
exit 0
