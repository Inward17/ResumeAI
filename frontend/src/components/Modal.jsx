/**
 * Accessible modal built on Radix Dialog: Esc and overlay click close it,
 * focus is trapped inside, and it is announced as a dialog.
 * Bottom sheet on phones, centred panel from md up.
 */
import React, { useState } from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { AlertTriangle, X } from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from './common';

const Modal = ({ open, onOpenChange, title, description, headerExtra, footer, maxWidth = 'md:max-w-2xl', children }) => (
  <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0 dark:bg-black/60" />
      <DialogPrimitive.Content
        className={cn(
          'fixed inset-x-0 bottom-0 z-50 flex max-h-[92vh] flex-col overflow-hidden rounded-t-xl border border-line bg-surface shadow-pop outline-none',
          'md:inset-auto md:left-1/2 md:top-1/2 md:max-h-[88vh] md:w-[calc(100%-2rem)] md:-translate-x-1/2 md:-translate-y-1/2 md:rounded-lg',
          'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:slide-in-from-bottom-4 md:data-[state=open]:zoom-in-95 md:data-[state=open]:slide-in-from-bottom-0',
          maxWidth,
        )}
      >
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <DialogPrimitive.Title className="truncate font-serif text-[1.75rem] leading-tight text-ink">{title}</DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className="mt-0.5 text-sm text-ink-3">{description}</DialogPrimitive.Description>
            ) : (
              <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {headerExtra}
            <DialogPrimitive.Close className="-mr-1.5 rounded-lg p-1.5 text-ink-3 transition-colors hover:bg-subtle hover:text-ink" aria-label="Close">
              <X className="h-5 w-5" aria-hidden="true" />
            </DialogPrimitive.Close>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">{children}</div>
        {footer && <div className="border-t border-line bg-subtle/50 px-5 py-3">{footer}</div>}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  </DialogPrimitive.Root>
);

/**
 * Replaces window.confirm: says what happens and names the action on the button.
 * `onConfirm` may be async; the dialog stays open (button busy) until it settles.
 */
export const ConfirmDialog = ({ open, onOpenChange, title, description, confirmLabel = 'Confirm', danger = true, onConfirm }) => {
  const [busy, setBusy] = useState(false);
  const confirm = async () => {
    setBusy(true);
    try {
      await onConfirm();
      onOpenChange(false);
    } finally {
      setBusy(false);
    }
  };
  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0 dark:bg-black/60" />
        <DialogPrimitive.Content
          role="alertdialog"
          className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border border-line bg-surface p-5 shadow-pop outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
        >
          <div className="flex gap-3">
            {danger && (
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-danger-soft">
                <AlertTriangle className="h-4 w-4 text-danger" aria-hidden="true" />
              </div>
            )}
            <div className="min-w-0">
              <DialogPrimitive.Title className="text-base font-semibold text-ink">{title}</DialogPrimitive.Title>
              <DialogPrimitive.Description className="mt-1 text-sm text-ink-3">{description}</DialogPrimitive.Description>
            </div>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <DialogPrimitive.Close asChild>
              <Button variant="secondary" disabled={busy}>Cancel</Button>
            </DialogPrimitive.Close>
            <Button variant={danger ? 'danger' : 'primary'} onClick={confirm} disabled={busy}>
              {busy ? 'Working…' : confirmLabel}
            </Button>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
};

export default Modal;
