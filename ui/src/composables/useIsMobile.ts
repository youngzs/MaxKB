/**
 * Reactive viewport detection for mobile breakpoints.
 *
 * Used across the finance pages so dialogs and grids can adapt to narrow
 * screens (e.g. flipping `el-dialog` to fullscreen on mobile). The default
 * breakpoint matches the SCSS `@media (max-width: 640px)` rules in
 * `views/finance/finance.scss` — keep these two values in lock-step.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

export function useIsMobile(breakpoint = 640) {
  const isMobile = ref(false)

  const check = () => {
    if (typeof window === 'undefined') return
    isMobile.value = window.innerWidth <= breakpoint
  }

  onMounted(() => {
    check()
    window.addEventListener('resize', check)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('resize', check)
  })

  return { isMobile }
}

export default useIsMobile
