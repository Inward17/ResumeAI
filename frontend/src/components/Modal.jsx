/**
 * Accessible modal built on Radix Dialog: Esc and overlay click close it,
 * focus is trapped inside, and it is announced as a dialog.
 * Bottom sheet on phones, centred panel from md up.
 */
import React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { cn } from '../lib/utils';

const Modal = ({ open, onOpenChange, title, description, headerExtra, footer, maxWidth = 'md:max-w-3xl', children }) => (
  <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-slate-950/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0" />
      <DialogPrimitive.Content
        className={cn(
          'fixed inset-x-0 bottom-0 z-50 flex max-h-[92vh] flex-col overflow-hidden rounded-t-3xl bg-white shadow-2xl outline-none',
          'md:inset-auto md:left-1/2 md:top-1/2 md:max-h-[88vh] md:w-[calc(100%-2rem)] md:-translate-x-1/2 md:-translate-y-1/2 md:rounded-2xl',
          'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:slide-in-from-bottom-4 md:data-[state=open]:zoom-in-95 md:data-[state=open]:slide-in-from-bottom-0',
          maxWidth,
        )}
      >
        <div className="flex flex-col gap-3 border-b border-slate-100 bg-slate-50 px-5 py-4 md:flex-row md:items-center md:justify-between md:px-6">
          <div className="flex min-w-0 items-start justify-between gap-3">
            <div className="min-w-0">
              <DialogPrimitive.Title className="truncate text-lg font-extrabold text-slate-900">{title}</DialogPrimitive.Title>
              {description ? (
                <DialogPrimitive.Description className="mt-0.5 text-sm text-slate-600">{description}</DialogPrimitive.Description>
              ) : (
                <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
              )}
            </div>
            <DialogPrimitive.Close className="rounded-xl p-2 text-slate-500 transition-colors hover:bg-slate-200 hover:text-slate-800 md:hidden" aria-label="Close">
              <X className="h-5 w-5" aria-hidden="true" />
            </DialogPrimitive.Close>
          </div>
          <div className="flex items-center gap-2">
            {headerExtra}
            <DialogPrimitive.Close className="hidden rounded-xl p-2 text-slate-500 transition-colors hover:bg-slate-200 hover:text-slate-800 md:block" aria-label="Close">
              <X className="h-5 w-5" aria-hidden="true" />
            </DialogPrimitive.Close>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">{children}</div>
        {footer && <div className="border-t border-slate-100 px-5 py-4 md:px-6">{footer}</div>}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  </DialogPrimitive.Root>
);

export default Modal;
