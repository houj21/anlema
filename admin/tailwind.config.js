/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#171310',
        ink2: '#2A231E',
        paper: '#FFF6E5',
        paper2: '#FFEFD3',
        lime: '#C8F94A',
        limeDark: '#A6DC22',
        pink: '#FF5FA2',
        cyan: '#35E0E8',
        orange: '#FF8A3D',
        cream: '#FFE9BE',
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', '"ZCOOL KuaiLe"', '"PingFang SC"', 'sans-serif'],
        fun: ['"ZCOOL KuaiLe"', '"Bricolage Grotesque"', '"PingFang SC"', 'sans-serif'],
        body: ['"Noto Sans SC"', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'Consolas', 'Menlo', 'monospace'],
      },
      boxShadow: {
        sticker: '4px 4px 0 0 #171310',
        stickerSm: '2px 2px 0 0 #171310',
      },
      spacing: { 13: '3.25rem' },
      keyframes: {
        pop: { '0%': { transform: 'scale(0.95)', opacity: '0' }, '100%': { transform: 'scale(1)', opacity: '1' } },
        slideUp: { '0%': { transform: 'translateY(10px)', opacity: '0' }, '100%': { transform: 'translateY(0)', opacity: '1' } },
      },
      animation: { pop: 'pop .2s ease-out', slideUp: 'slideUp .3s ease-out both' },
    },
  },
  plugins: [],
}
