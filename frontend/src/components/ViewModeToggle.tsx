import { FileText, Columns2, File } from 'lucide-react'
import clsx from 'clsx'
import type { ViewMode } from '@/hooks/useViewMode'

interface ViewModeToggleProps {
  mode: ViewMode
  onModeChange: (mode: ViewMode) => void
  className?: string
  disabled?: boolean
}

const modes: { value: ViewMode; icon: typeof FileText; label: string; shortcut: string }[] = [
  { value: 'text', icon: FileText, label: 'Solo texto', shortcut: 'T' },
  { value: 'split', icon: Columns2, label: 'Texto y PDF', shortcut: 'S' },
  { value: 'pdf', icon: File, label: 'Solo PDF', shortcut: 'P' },
]

export default function ViewModeToggle({ mode, onModeChange, className, disabled }: ViewModeToggleProps) {
  return (
    <div className={clsx('inline-flex rounded-lg bg-gray-100 dark:bg-gray-800 p-1', className)}>
      {modes.map(({ value, icon: Icon, label, shortcut }) => (
        <button
          key={value}
          onClick={() => onModeChange(value)}
          disabled={disabled}
          title={`${label} (${shortcut})`}
          className={clsx(
            'flex items-center justify-center w-9 h-9 rounded-md transition-all duration-200',
            mode === value
              ? 'bg-white dark:bg-gray-700 text-primary-600 dark:text-primary-400 shadow-sm'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
        >
          <Icon className="h-5 w-5" />
        </button>
      ))}
    </div>
  )
}
