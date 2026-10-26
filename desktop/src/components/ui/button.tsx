import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-bold ' +
    'border-[3px] border-ink shadow-stickerSm btn-pop transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
  {
    variants: {
      variant: {
        default: 'bg-paper2 hover:bg-cream text-ink',
        lime: 'bg-lime hover:bg-limeDark text-ink',
        pink: 'bg-pink text-white hover:bg-pink/85',
        cyan: 'bg-cyan text-ink hover:bg-cyan/80',
        dark: 'bg-ink text-paper hover:bg-ink2',
        ghost: 'bg-transparent border-transparent shadow-none hover:bg-ink/5 text-ink',
        outline: 'bg-white hover:bg-cream text-ink',
      },
      size: {
        default: 'h-11 px-5',
        sm: 'h-9 px-3 text-[13px]',
        lg: 'h-13 px-7 text-base',
        icon: 'h-10 w-10',
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

export { buttonVariants }
