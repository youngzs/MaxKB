import { h } from 'vue'

// Finance/wallet icon — briefcase + coin glyph in currentColor.
// 24x24 viewBox, single-color, no external refs.
export default {
  'app-finance': {
    iconReader: () => {
      return h('i', [
        h(
          'svg',
          {
            style: { height: '100%', width: '100%' },
            viewBox: '0 0 24 24',
            version: '1.1',
            xmlns: 'http://www.w3.org/2000/svg',
          },
          [
            // Briefcase outline
            h('path', {
              d: 'M9 4h6a1 1 0 0 1 1 1v2h4a2 2 0 0 1 2 2v3H2V9a2 2 0 0 1 2-2h4V5a1 1 0 0 1 1-1zm5 3V5h-4v2h4z',
              fill: 'currentColor',
            }),
            h('path', {
              d: 'M2 13h8v1.5a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1V13h8v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z',
              fill: 'currentColor',
            }),
            // Coin / $ symbol overlaid on briefcase clasp
            h('path', {
              d: 'M12 8.25c.41 0 .75.34.75.75v.25h.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0 0 .5h1a1.25 1.25 0 0 1 0 2.5h-.25v.25a.75.75 0 0 1-1.5 0V13.75h-.5a.75.75 0 0 1 0-1.5h1.5a.25.25 0 0 0 0-.5h-1a1.25 1.25 0 0 1 0-2.5h.25V9c0-.41.34-.75.75-.75z',
              fill: 'currentColor',
              opacity: '0.0',
            }),
          ],
        ),
      ])
    },
  },
  'app-finance-active': {
    iconReader: () => {
      return h('i', [
        h(
          'svg',
          {
            style: { height: '100%', width: '100%' },
            viewBox: '0 0 24 24',
            version: '1.1',
            xmlns: 'http://www.w3.org/2000/svg',
          },
          [
            // Solid/filled briefcase
            h('path', {
              d: 'M9 4h6a1 1 0 0 1 1 1v2h4a2 2 0 0 1 2 2v3h-8v-1a1 1 0 0 0-1-1h-2a1 1 0 0 0-1 1v1H2V9a2 2 0 0 1 2-2h4V5a1 1 0 0 1 1-1zm5 3V5h-4v2h4z',
              fill: 'currentColor',
            }),
            h('path', {
              d: 'M2 13h8v1.5a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1V13h8v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z',
              fill: 'currentColor',
            }),
          ],
        ),
      ])
    },
  },
}
