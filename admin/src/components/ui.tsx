import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-bold ' +
    'border-[3px] border-ink shadow-stickerSm btn-pop transition-colors disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-paper2 hover:bg-cream text-ink',
        lime: 'bg-lime hover:bg-limeDark text-ink',
        pink: 'bg-pink text-white hover:bg-pink/85',
        cyan: 'bg-cyan text-ink hover:bg-cyan/80',
        dark: 'bg-ink text-paper hover:bg-ink2',
        outline: 'bg-white hover:bg-cream text-ink',
        ghost: 'bg-transparent border-transparent shadow-none hover:bg-ink/5 text-ink',
      },
      size: {
        default: 'h-10 px-4',
        sm: 'h-8 px-3 text-[12.5px]',
        lg: 'h-13 px-6',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  )
)
Button.displayName = 'Button'

export const Card = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('sticker', className)} {...props} />
)

export function Badge({
  className,
  tone = 'cream',
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & {
  tone?: 'cream' | 'lime' | 'pink' | 'cyan' | 'dark'
}) {
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

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'h-10 w-full rounded-xl border-[3px] border-ink bg-white px-3 text-[14px] outline-none focus:bg-lime/10',
        className
      )}
      {...props}
    />
  )
}

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        'w-full rounded-xl border-[3px] border-ink bg-white p-3 text-[13px] outline-none focus:bg-lime/10',
        className
      )}
      {...props}
    />
  )
}
