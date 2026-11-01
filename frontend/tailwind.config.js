/** @type {import('tailwindcss').Config} */
// Every colour is a CSS variable (src/index.css) so light and dark themes
// share the same class names. `<alpha-value>` keeps /opacity modifiers working.
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

module.exports = {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Geist', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        // Display serif for page titles and headline numbers only
        serif: ['"Instrument Serif"', 'ui-serif', 'Georgia', 'serif'],
      },
      colors: {
        btn: { DEFAULT: token('btn'), hover: token('btn-hover'), fg: token('btn-fg') },
        canvas: token('canvas'),        // page background
        surface: token('surface'),      // cards, panels, inputs
        subtle: token('subtle'),        // table headers, hover fills, wells
        line: { DEFAULT: token('line'), strong: token('line-strong') },
        ink: { DEFAULT: token('ink'), 2: token('ink-2'), 3: token('ink-3') },
        primary: {
          DEFAULT: token('primary'),
          hover: token('primary-hover'),
          text: token('primary-text'),
          soft: token('primary-soft'),
          'soft-fg': token('primary-soft-fg'),
        },
        success: { DEFAULT: token('success'), soft: token('success-soft') },
        warning: { DEFAULT: token('warning'), soft: token('warning-soft') },
        danger: { DEFAULT: token('danger'), soft: token('danger-soft') },
        info: { DEFAULT: token('info'), soft: token('info-soft') },
      },
      boxShadow: {
        card: '0 1px 2px rgb(0 0 0 / 0.04)',
        pop: '0 8px 24px -4px rgb(0 0 0 / 0.12), 0 2px 6px rgb(0 0 0 / 0.06)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
