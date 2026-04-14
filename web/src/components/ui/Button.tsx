import { type ButtonHTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-blue)] disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-[var(--color-blue)] text-white hover:bg-[var(--color-blue)]/80',
        primary: 'bg-[var(--color-blue)] text-white hover:bg-[var(--color-blue)]/80',
        secondary: 'bg-[var(--bg-hover)] text-[var(--text-primary)] hover:bg-[var(--border)]',
        danger: 'bg-[var(--color-loss)] text-white hover:bg-[var(--color-loss)]/80',
        destructive: 'bg-[var(--color-loss)] text-white hover:bg-[var(--color-loss)]/80',
        ghost: 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]',
        outline:
          'border border-[var(--border)] text-[var(--text-primary)] hover:bg-[var(--bg-hover)]',
      },
      size: {
        default: 'h-9 px-4 text-sm',
        xs: 'h-6 px-2 text-[11px]',
        sm: 'h-8 px-3 text-xs',
        md: 'h-9 px-4 text-sm',
        lg: 'h-10 px-6 text-base',
        icon: 'h-9 w-9',
        'icon-xs': 'h-6 w-6',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
    },
  },
);

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({ className, variant, size, asChild: _asChild, ...props }: ButtonProps) {
  return (
    <button className={cn(buttonVariants({ variant, size, className }))} {...props} />
  );
}
