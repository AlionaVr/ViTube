import { createContext, useContext } from 'react'

/** Filled by ToastProvider (components/Toast.tsx), which Layout puts around every page. */
export const ToastContext = createContext<(message: string) => void>(() => {})

/** `toast(message)`: one short line at the bottom left; replaces any toast on screen. */
export function useToast() {
  return useContext(ToastContext)
}
