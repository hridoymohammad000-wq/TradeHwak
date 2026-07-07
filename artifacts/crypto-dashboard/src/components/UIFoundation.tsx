/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { Power, Info, AlertTriangle, ShieldCheck } from 'lucide-react';

// PAGE HEADER
interface PageHeaderProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function PageHeader({ title, description, action }: PageHeaderProps) {
  return (
    <div className="flex flex-col md:flex-row md:items-center md:justify-between pb-6 border-b border-slate-800/80 mb-6 gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white font-sans">{title}</h1>
        {description && (
          <p className="text-sm text-slate-400 mt-1">{description}</p>
        )}
      </div>
      {action && <div className="flex items-center gap-3">{action}</div>}
    </div>
  );
}

// SECTION HEADER
interface SectionHeaderProps {
  title: string;
  action?: React.ReactNode;
  className?: string;
}

export function SectionHeader({ title, action, className = '' }: SectionHeaderProps) {
  return (
    <div className={`flex items-center justify-between py-2 mb-3 border-b border-slate-800/50 ${className}`}>
      <h2 className="text-base font-bold uppercase tracking-wider text-slate-300 font-mono flex items-center gap-2">
        <span className="w-1.5 h-3.5 bg-indigo-500 rounded-sm inline-block"></span>
        {title}
      </h2>
      {action && <div className="flex items-center gap-2">{action}</div>}
    </div>
  );
}

// CARD
interface CardProps {
  children: React.ReactNode;
  title?: string;
  action?: React.ReactNode;
  className?: string;
  footer?: React.ReactNode;
}

export function Card({ children, title, action, className = '', footer }: CardProps) {
  return (
    <div className={`bg-slate-900/60 border border-slate-800/80 rounded-lg p-5 flex flex-col justify-between hover:border-indigo-500/30 transition-all duration-200 ${className}`}>
      <div>
        {(title || action) && (
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-800/40">
            {title && (
              <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200 font-mono">
                {title}
              </h3>
            )}
            {action && <div>{action}</div>}
          </div>
        )}
        <div className="text-slate-300">{children}</div>
      </div>
      {footer && (
        <div className="mt-4 pt-3 border-t border-slate-800/40 flex items-center justify-between text-xs text-slate-400 font-mono">
          {footer}
        </div>
      )}
    </div>
  );
}

// BUTTON
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'success' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
  className?: string;
  disabled?: boolean;
  onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
}

export function Button({
  variant = 'secondary',
  size = 'md',
  children,
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  const baseStyles = 'inline-flex items-center justify-center font-medium font-sans rounded transition-all duration-150 focus:outline-none focus:ring-1 focus:ring-offset-1 focus:ring-offset-slate-950 disabled:opacity-40 disabled:cursor-not-allowed';
  
  const variants = {
    primary: 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-950/40 focus:ring-indigo-500 border border-indigo-500/30',
    secondary: 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/80 focus:ring-slate-500',
    outline: 'bg-transparent hover:bg-slate-800/50 text-slate-300 border border-slate-700/80 focus:ring-slate-500',
    success: 'bg-emerald-650 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-950/20 border border-emerald-500/20',
    danger: 'bg-rose-650 hover:bg-rose-600 text-white shadow-lg shadow-rose-950/40 border border-rose-500/20 focus:ring-rose-500',
    ghost: 'bg-transparent hover:bg-slate-800/40 text-slate-400 hover:text-slate-200',
  };

  const sizes = {
    sm: 'text-xs px-2.5 py-1.5 gap-1.5',
    md: 'text-sm px-4 py-2 gap-2',
    lg: 'text-base px-5 py-2.5 gap-2.5',
  };

  return (
    <button
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}

// BADGE
interface BadgeProps {
  children: React.ReactNode;
  variant?: 'purple' | 'blue' | 'gray' | 'danger' | 'success' | 'warning';
  className?: string;
}

export function Badge({ children, variant = 'gray', className = '' }: BadgeProps) {
  const colors = {
    purple: 'bg-purple-950/40 text-purple-400 border-purple-800/40',
    blue: 'bg-blue-950/40 text-blue-400 border-blue-800/40',
    gray: 'bg-slate-850 text-slate-400 border-slate-750',
    danger: 'bg-rose-950/40 text-rose-400 border-rose-850/50',
    success: 'bg-emerald-950/40 text-emerald-400 border-emerald-850/50',
    warning: 'bg-amber-950/30 text-amber-400 border-amber-900/30',
  };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold font-mono border ${colors[variant]} ${className}`}>
      {children}
    </span>
  );
}

// STATUS BADGE
interface StatusBadgeProps {
  status: 'active' | 'inactive' | 'pending' | 'danger';
  label: string;
  className?: string;
}

export function StatusBadge({ status, label, className = '' }: StatusBadgeProps) {
  const styles = {
    active: {
      dot: 'bg-emerald-500 animate-pulse',
      bg: 'bg-emerald-950/25 text-emerald-400 border-emerald-800/30',
    },
    inactive: {
      dot: 'bg-slate-500',
      bg: 'bg-slate-900 text-slate-400 border-slate-800',
    },
    pending: {
      dot: 'bg-amber-500 animate-pulse',
      bg: 'bg-amber-950/25 text-amber-400 border-amber-800/30',
    },
    danger: {
      dot: 'bg-rose-500',
      bg: 'bg-rose-950/25 text-rose-400 border-rose-800/30',
    },
  };

  const current = styles[status] || styles.inactive;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold font-mono border ${current.bg} ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${current.dot}`}></span>
      {label}
    </span>
  );
}

// TOGGLE BUTTON (ON / OFF UI control)
interface ToggleButtonProps {
  checked: boolean;
  onChange: (val: boolean) => void;
  label?: string;
  id?: string;
  className?: string;
  disabled?: boolean;
}

export function ToggleButton({
  checked,
  onChange,
  label,
  id,
  className = '',
  disabled = false,
}: ToggleButtonProps) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {label && (
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono">
          {label}
        </span>
      )}
      <div className="inline-flex rounded overflow-hidden border border-slate-800">
        <button
          id={id ? `${id}-off` : undefined}
          type="button"
          onClick={() => !disabled && onChange(false)}
          className={`px-3 py-1 text-xs font-bold font-mono transition-colors ${
            !checked
              ? 'bg-slate-800 text-slate-200 border-r border-slate-950'
              : 'bg-slate-950/40 text-slate-600 hover:text-slate-400 border-r border-slate-950'
          }`}
          disabled={disabled}
        >
          OFF
        </button>
        <button
          id={id ? `${id}-on` : undefined}
          type="button"
          onClick={() => !disabled && onChange(true)}
          className={`px-3 py-1 text-xs font-bold font-mono transition-colors ${
            checked
              ? 'bg-indigo-600 text-white'
              : 'bg-slate-950/40 text-slate-600 hover:text-slate-400'
          }`}
          disabled={disabled}
        >
          ON
        </button>
      </div>
    </div>
  );
}

// TABLE
interface TableProps {
  headers: string[];
  children: React.ReactNode;
  className?: string;
}

export function Table({ headers, children, className = '' }: TableProps) {
  return (
    <div className={`w-full overflow-x-auto rounded border border-slate-800/80 bg-slate-950/10 ${className}`}>
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="bg-slate-900/80 border-b border-slate-800 text-xs font-semibold font-mono tracking-wider text-slate-400 uppercase">
            {headers.map((header, index) => (
              <th key={index} className="px-4 py-3 font-semibold">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/50 text-sm font-sans text-slate-300">
          {children}
        </tbody>
      </table>
    </div>
  );
}

// EMPTY STATE
interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  title = 'Waiting for backend integration',
  description = 'No data connected yet.',
  icon,
  className = '',
}: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center text-center p-8 bg-slate-900/20 border border-dashed border-slate-800/85 rounded-lg ${className}`}>
      <div className="p-3 bg-slate-900 rounded-full border border-slate-800 mb-3 text-slate-500">
        {icon || <Info size={24} />}
      </div>
      <h4 className="text-sm font-bold text-slate-300 uppercase tracking-wider font-mono mb-1">{title}</h4>
      <p className="text-xs text-slate-500 max-w-sm font-sans">{description}</p>
    </div>
  );
}
