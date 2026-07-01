import { type ReactNode } from 'react'
import { clsx } from 'clsx'

export function PageHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-6">
      <h2 className="text-xl font-bold text-slate-800">{title}</h2>
      {sub && <p className="text-sm text-slate-500 mt-0.5">{sub}</p>}
    </div>
  )
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={clsx('bg-white rounded-lg border border-slate-200 shadow-sm', className)}>
      {children}
    </div>
  )
}

export function Badge({ children, variant = 'default' }: { children: ReactNode; variant?: 'default' | 'green' | 'red' | 'gray' }) {
  const cls = {
    default: 'bg-blue-100 text-blue-800',
    green: 'bg-green-100 text-green-800',
    red: 'bg-red-100 text-red-800',
    gray: 'bg-slate-100 text-slate-500',
  }[variant]
  return <span className={clsx('inline-flex items-center px-2 py-0.5 rounded text-xs font-medium', cls)}>{children}</span>
}

export function Button({
  children,
  onClick,
  type = 'button',
  variant = 'primary',
  disabled,
  className,
}: {
  children: ReactNode
  onClick?: () => void
  type?: 'button' | 'submit'
  variant?: 'primary' | 'secondary' | 'danger'
  disabled?: boolean
  className?: string
}) {
  const cls = {
    primary: 'bg-brand text-white hover:bg-blue-900',
    secondary: 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50',
    danger: 'bg-red-600 text-white hover:bg-red-700',
  }[variant]
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
        cls,
        className
      )}
    >
      {children}
    </button>
  )
}

export function Input({ label, error, ...props }: { label: string; error?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        {...props}
        className={clsx(
          'mt-1 block w-full rounded-md border px-3 py-1.5 text-sm shadow-sm outline-none focus:ring-2 focus:ring-brand/40',
          error ? 'border-red-400' : 'border-slate-300'
        )}
      />
      {error && <p className="mt-0.5 text-xs text-red-600">{error}</p>}
    </label>
  )
}

export function Select({ label, children, ...props }: { label: string } & React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <select
        {...props}
        className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm shadow-sm outline-none focus:ring-2 focus:ring-brand/40"
      >
        {children}
      </select>
    </label>
  )
}

export function Spinner() {
  return (
    <div className="flex justify-center py-12">
      <div className="h-7 w-7 animate-spin rounded-full border-2 border-brand border-t-transparent" />
    </div>
  )
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
      {message}
    </div>
  )
}
