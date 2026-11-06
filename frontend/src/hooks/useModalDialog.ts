import { type RefObject, useEffect } from 'react'

/** Opens and closes a <dialog> as a modal to follow `open`. */
export function useModalDialog(ref: RefObject<HTMLDialogElement | null>, open: boolean) {
  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [ref, open])
}
