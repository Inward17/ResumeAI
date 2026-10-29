import React from 'react';
import { FileSearch, ShieldCheck, ListChecks } from 'lucide-react';
import BrandMark from '../BrandMark';

const POINTS = [
  { Icon: FileSearch, text: 'Parses every resume and scores it against your job description.' },
  { Icon: ShieldCheck, text: 'Checks claims against GitHub, LinkedIn and the web.' },
  { Icon: ListChecks, text: 'Generates tailored interview questions for each candidate.' },
];

// Photo by Caroline Badran on Unsplash (Unsplash License) — credited on the panel
const PHOTO = 'https://images.unsplash.com/photo-1765371512707-9e0e96fd9e5b?auto=format&fit=crop&w=1200&q=75';
const PHOTO_CREDIT = 'https://unsplash.com/photos/modern-room-with-wood-paneling-and-large-windows-agz5hQ0rXUc';

/** Two-column layout shared by the sign-in and sign-up pages */
export const AuthShell = ({ title, subtitle, children, footer }) => (
  <div className="flex min-h-[100dvh] bg-canvas">
    <aside className="relative m-3 hidden w-[44%] max-w-2xl flex-col justify-between overflow-hidden rounded-xl bg-[#2a2620] p-10 text-white lg:flex">
      <img src={PHOTO} alt="" className="absolute inset-0 h-full w-full object-cover" />
      <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/20 to-black/30" aria-hidden="true" />

      <BrandMark inverted className="relative" />
      <div className="relative">
        <h2 className="font-serif text-[2.75rem] leading-[1.05] tracking-[-0.01em]">
          Screen resumes with <em>evidence</em>, not guesswork.
        </h2>
        <ul className="mt-7 space-y-2.5 text-sm text-white/80">
          {POINTS.map(({ Icon, text }) => (
            <li key={text} className="flex items-start gap-3">
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-white/60" strokeWidth={1.75} aria-hidden="true" />
              <span>{text}</span>
            </li>
          ))}
        </ul>
        <p className="mt-10 text-[11px] text-white/50">
          Photo by <a href={PHOTO_CREDIT} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">Caroline Badran on Unsplash</a>
        </p>
      </div>
    </aside>

    <main className="flex flex-1 items-center justify-center px-4 py-10 sm:px-8">
      <div className="w-full max-w-sm">
        <BrandMark className="mb-10" />
        <h1 className="font-serif text-[2.5rem] leading-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-3">{subtitle}</p>}
        <div className="mt-8">{children}</div>
        {footer && <p className="mt-8 text-center text-sm text-ink-3">{footer}</p>}
      </div>
    </main>
  </div>
);

export const authInput = 'h-10 w-full rounded-md border border-line-strong bg-surface pl-10 pr-3 text-sm text-ink placeholder:text-ink-3 outline-none transition focus:border-primary focus:ring-[3px] focus:ring-primary/15';

export const AuthAlert = ({ tone = 'error', children }) => (
  <div role={tone === 'error' ? 'alert' : 'status'}
    className={`mb-5 flex items-start gap-2 rounded-md px-3 py-2.5 text-sm ring-1 ring-inset ${tone === 'error' ? 'bg-danger-soft text-danger ring-danger/25' : 'bg-success-soft text-success ring-success/25'}`}>
    {children}
  </div>
);

export const GoogleIcon = () => (
  <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
  </svg>
);

export const Divider = () => (
  <div className="relative my-6">
    <div className="absolute inset-0 flex items-center"><span className="w-full border-t border-line" /></div>
    <div className="relative flex justify-center text-xs"><span className="bg-canvas px-3 text-ink-3">or continue with email</span></div>
  </div>
);
