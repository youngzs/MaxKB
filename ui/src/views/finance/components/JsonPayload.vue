<template>
  <!-- v-html is safe here: `highlighted` is built from JSON.stringify output
       which we first HTML-escape, then re-decorate with span tags. The only
       inserted markup is our own static `<span class="json-…">` wrappers. -->
  <pre class="json-payload" v-html="highlighted" />
</template>

<script setup lang="ts">
import { computed } from 'vue'

/**
 * Minimal in-repo JSON pretty-printer with syntax highlighting.
 *
 * We avoid pulling in a third-party JSON viewer because (a) no library is
 * currently in `package.json`, (b) the payloads are small (audit-log row
 * payloads, capped server-side), and (c) we only need 4 token colours.
 *
 * Security: `escapeHtml()` runs *before* the regex spanning step, so any
 * `<`, `>`, `&`, or quote characters inside string values are neutralised
 * before any markup is added. Token regex only matches the JSON-shaped
 * literals we emit ourselves via `JSON.stringify`, never raw user input.
 */
const props = defineProps<{
  value: unknown
  /** Optional max-height override (default 320 px in inline-row context). */
  maxHeight?: string
}>()

const escapeHtml = (s: string): string =>
  s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

/**
 * Token regex (run over already-escaped JSON text):
 *  - `&quot;(?:\\.|[^&]|&(?!quot;))*?&quot;` matches a JSON string, allowing
 *    backslash escapes. We use the escaped form because escapeHtml has
 *    already replaced `"` with `&quot;`.
 *  - `\b(true|false|null)\b` boolean / null literals.
 *  - `-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?` numeric literals.
 */
const tokenRe =
  /(&quot;(?:\\.|(?!&quot;)[^])*?&quot;)(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g

const stringify = (val: unknown): string => {
  try {
    return JSON.stringify(val ?? {}, null, 2)
  } catch {
    // Fallback if value has circular refs or BigInts — show as plain text.
    return String(val)
  }
}

const highlighted = computed<string>(() => {
  const json = stringify(props.value)
  if (!json) return ''
  const escaped = escapeHtml(json)
  return escaped.replace(
    tokenRe,
    (_match, str: string, colon: string, bool: string, num: string) => {
      if (str) {
        // If a colon follows, this string is a key, else a value.
        if (colon) {
          return `<span class="json-key">${str}</span>${colon}`
        }
        return `<span class="json-string">${str}</span>`
      }
      if (bool) {
        return `<span class="json-bool">${bool}</span>`
      }
      if (num) {
        return `<span class="json-num">${num}</span>`
      }
      return _match
    },
  )
})
</script>

<style lang="scss" scoped>
.json-payload {
  background: var(--el-fill-color-darker, #f4f4f5);
  border-radius: 4px;
  padding: 8px 12px;
  margin: 0;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  line-height: 1.55;
  color: var(--el-text-color-primary);
  max-height: v-bind('maxHeight || "320px"');
  overflow: auto;
  white-space: pre;

  :deep(.json-key) {
    color: #c0392b;
  }
  :deep(.json-string) {
    color: #27ae60;
  }
  :deep(.json-num) {
    color: #2980b9;
  }
  :deep(.json-bool) {
    color: #8e44ad;
  }
}
</style>
