import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { missingFirebaseConfig } from '../firebase';
import BrandMark from './BrandMark';

/** Shown instead of a blank page when the Firebase settings are not provided */
const ConfigMissing = () => (
  <div className="flex min-h-screen items-center justify-center bg-page p-4">
    <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
      <BrandMark />
      <div className="mt-6 flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" aria-hidden="true" />
        <div>
          <h1 className="text-lg font-bold text-slate-900">Configuration missing</h1>
          <p className="mt-1 text-sm text-slate-600">
            ResumeAI can&apos;t start because these settings are not set in <code className="rounded bg-slate-100 px-1">frontend/.env</code>:
          </p>
          <ul className="mt-3 space-y-1">
            {missingFirebaseConfig.map((name) => (
              <li key={name}>
                <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-800">{name}</code>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-sm text-slate-600">
            Copy <code className="rounded bg-slate-100 px-1">frontend/.env.example</code> to{' '}
            <code className="rounded bg-slate-100 px-1">.env</code>, fill in the values from Firebase console → Project
            settings → Your apps, then restart the dev server or rebuild.
          </p>
        </div>
      </div>
    </div>
  </div>
);

export default ConfigMissing;
