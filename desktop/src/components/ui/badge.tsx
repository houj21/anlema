import * as React from 'react'
import { cn } from '@/lib/utils'

export function Badge({
  className,
  tone = 'cream',
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: 'cream' | 'lime' | 'pink' | 'cyan' | 'dark' }) {
  const tones = {
    cream: 'bg-cream text-ink',
    lime: 'bg-lime text-ink',
    pink: 'bg-pink text-white',
    cyan: 'bg-cyan text-ink',
    dark: 'bg-ink text-paper',
  }
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border-2 border-ink px-2.5 py-0.5 text-[12px] font-bold',
        tones[tone],
        className
      )}
      {...props}
    />
  )
}
