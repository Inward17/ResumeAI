import React from 'react';
import { FileSearch, ShieldCheck, ListChecks } from 'lucide-react';
import BrandMark from '../BrandMark';

const POINTS = [
  { Icon: FileSearch, text: 'Parses every resume and scores it against your job description.' },
  { Icon: ShieldCheck, text: 'Checks claims against GitHub, LinkedIn and the web.' },
  { Icon: ListChecks, text: 'Generates tailored interview questions for each candidate.' },
];

/** Two-column layout shared by the sign-in and sign-up pages */
export const AuthShell = ({ title, subtitle, children, footer }) => (
  <div className="flex min-h-screen bg-page">
    <aside className="relative hidden w-[44%] max-w-xl flex-col justify-between overflow-hidden bg-brand-gradient p-10 text-white lg:flex">
      <BrandMark inverted />
      <div>
        <h2 className="font-display text-3xl font-extrabold leading-tight">Screen resumes with evidence, not guesswork.</h2>
        <ul className="mt-8 space-y-4">
          {POINTS.map(({ Icon, text }) => (
            <li key={text} className="flex items-start gap-3 text-indigo-100">
              <Icon className="mt-0.5 h-5 w-5 shrink-0 text-brand-cyan" aria-hidden="true" />
              <span>{text}</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="text-xs text-indigo-200">© {new Date().getFullYear()} ResumeAI</p>
      <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-white/5" aria-hidden="true" />
    </aside>

    <main className="flex flex-1 items-center justify-center p-4 sm:p-8">
      <div className="w-full max-w-md">
        <BrandMark className="mb-8 lg:hidden" />
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-slate-600">{subtitle}</p>}
          <div className="mt-6">{children}</div>
        </div>
        {footer && <p className="mt-6 text-center text-sm text-slate-600">{footer}</p>}
      </div>
    </main>
  </div>
);

export const authInput = 'w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm text-slate-900 placeholder:text-slate-500 outline-none transition focus:border-brand-accent focus:ring-2 focus:ring-brand-soft';

export const GoogleIcon = () => (
  <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
  </svg>
);

export const Divider = () => (
  <div className="relative my-5">
    <div className="absolute inset-0 flex items-center"><span className="w-full border-t border-slate-200" /></div>
    <div className="relative flex justify-center text-xs uppercase"><span className="bg-white px-2 text-slate-500">or</span></div>
  </div>
);
