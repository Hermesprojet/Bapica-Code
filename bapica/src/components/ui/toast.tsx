// Système de toasts/notifications pour Bapica
'use client'

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

type ToastType = 'success' | 'error' | 'info' | 'warning'

interface Toast {
  id: number
  type: ToastType
  title: string
  message?: string
}

interface ToastContextType {
  toasts: Toast[]
  addToast: (type: ToastType, title: string, message?: string) => void
  removeToast: (id: number) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast doit être utilisé dans <ToastProvider>')
  return ctx
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  let nextId = 0

  const addToast = useCallback((type: ToastType, title: string, message?: string) => {
    const id = ++nextId
    setToasts(prev => [...prev, { id, type, title, message }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 4000)
  }, [])

  const removeToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const colors: Record<ToastType, { bg: string; border: string; dot: string }> = {
    success: { bg: 'bg-green-500/10', border: 'border-green-500/20', dot: 'bg-green-500' },
    error: { bg: 'bg-red-500/10', border: 'border-red-500/20', dot: 'bg-red-500' },
    info: { bg: 'bg-primary/10', border: 'border-primary/20', dot: 'bg-primary' },
    warning: { bg: 'bg-amber-500/10', border: 'border-amber-500/20', dot: 'bg-amber-500' },
  }

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      {/* Toast container */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 pointer-events-none">
        {toasts.map(toast => (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start gap-3 rounded-xl border ${colors[toast.type].border} ${colors[toast.type].bg} backdrop-blur-md px-4 py-3 shadow-2xl animate-slide-up min-w-[300px] max-w-[400px]`}
          >
            <span className={`mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full ${colors[toast.type].dot}`} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground">{toast.title}</p>
              {toast.message && (
                <p className="mt-0.5 text-xs text-muted-foreground">{toast.message}</p>
              )}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
