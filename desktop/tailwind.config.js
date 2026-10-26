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
      spacing: {
        13: '3.25rem',
      },
      boxShadow: {
        sticker: '4px 4px 0 0 #171310',
        stickerSm: '2px 2px 0 0 #171310',
        stickerLg: '8px 8px 0 0 #171310',
      },
      keyframes: {
        wiggle: {
          '0%,100%': { transform: 'rotate(-2deg)' },
          '50%': { transform: 'rotate(2deg)' },
        },
        pop: {
          '0%': { transform: 'scale(0.9)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(12px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        march: {
          '0%': { backgroundPosition: '0 0' },
          '100%': { backgroundPosition: '56px 0' },
        },
      },
      animation: {
        wiggle: 'wiggle 1.6s ease-in-out infinite',
        pop: 'pop 0.25s cubic-bezier(.34,1.56,.64,1)',
        slideUp: 'slideUp 0.35s ease-out both',
        march: 'march 1.2s linear infinite',
      },
    },
  },
  plugins: [],
}
