import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { missingFirebaseConfig } from '../firebase';
import BrandMark from './BrandMark';

/** Shown instead of a blank page when the Firebase settings are not provided */
const ConfigMissing = () => (
  <div className="flex min-h-screen items-center justify-center bg-canvas p-4">
    <div className="w-full max-w-lg rounded-lg border border-line bg-surface p-8">
      <BrandMark />
      <div className="mt-6 flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" aria-hidden="true" />
        <div>
          <h1 className="text-lg font-semibold text-ink">Configuration missing</h1>
          <p className="mt-1 text-sm text-ink-3">
            ResumeAI can&apos;t start because these settings are not set in <code className="rounded bg-subtle px-1">frontend/.env</code>:
          </p>
          <ul className="mt-3 space-y-1">
            {missingFirebaseConfig.map((name) => (
              <li key={name}>
                <code className="rounded bg-subtle px-1.5 py-0.5 text-xs text-ink">{name}</code>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-sm text-ink-3">
            Copy <code className="rounded bg-subtle px-1">frontend/.env.example</code> to{' '}
            <code className="rounded bg-subtle px-1">.env</code>, fill in the values from Firebase console → Project
            settings → Your apps, then restart the dev server or rebuild.
          </p>
        </div>
      </div>
    </div>
  </div>
);

export default ConfigMissing;
