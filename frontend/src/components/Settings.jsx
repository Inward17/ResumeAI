import React, { useState } from 'react';
import { Sliders, Users, CreditCard, Plug, KeyRound, Palette, RotateCcw } from 'lucide-react';
import { Slider } from './ui/slider';
import { useToast } from '../hooks/use-toast';
import { DEFAULT_PREFERENCES, loadPreferences, savePreferences } from '../lib/preferences';
import { Card, CardHeader, PageContainer, PageHeader, PrimaryButton, SecondaryButton, ComingSoon } from './common';

const THRESHOLDS = [
  {
    key: 'matchThreshold',
    label: 'Strong role match',
    hint: 'Candidates at or above this role match are counted as strong matches in each pipeline.',
  },
  {
    key: 'verificationThreshold',
    label: 'Verification review threshold',
    hint: 'Candidates whose credibility score is below this are flagged for manual review.',
  },
];

const UPCOMING = [
  { Icon: Users, title: 'Team members', body: 'Invite colleagues and share job postings with roles such as recruiter and hiring manager.' },
  { Icon: CreditCard, title: 'Plans & billing', body: 'Usage limits and invoices for your workspace.' },
  { Icon: Plug, title: 'Integrations', body: 'Send candidates to your ATS, calendar and chat tools.' },
  { Icon: KeyRound, title: 'API keys', body: 'Programmatic access for your own tools and automations.' },
  { Icon: Palette, title: 'Branding', body: 'Your company logo and colours on shared pages.' },
];

const Settings = () => {
  const { toast } = useToast();
  const [prefs, setPrefs] = useState(loadPreferences);
  const [saved, setSaved] = useState(loadPreferences);
  const dirty = THRESHOLDS.some(({ key }) => prefs[key] !== saved[key]);

  const handleSave = () => {
    if (savePreferences(prefs)) {
      setSaved(prefs);
      toast({ title: 'Thresholds saved', description: 'Pipelines use the new values from now on.' });
    } else {
      toast({ title: 'Could not save thresholds', description: 'Your browser blocked local storage.', variant: 'destructive' });
    }
  };

  return (
    <PageContainer>
      <PageHeader eyebrow="Settings" title="Workspace settings" description="Tune how candidates are highlighted. More workspace features are on the way." />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader
            title="Scoring thresholds"
            subtitle="Saved in this browser and applied to pipelines and candidate dossiers."
            action={<Sliders className="h-5 w-5 text-slate-500" aria-hidden="true" />}
          />
          <div className="space-y-8 p-5 md:p-6">
            {THRESHOLDS.map(({ key, label, hint }) => (
              <div key={key}>
                <div className="mb-1 flex items-center justify-between">
                  <p id={`${key}-label`} className="text-sm font-semibold text-slate-900">{label}</p>
                  <span className="text-sm font-bold text-brand-accent">{prefs[key]}%</span>
                </div>
                <p className="mb-4 text-sm text-slate-600">{hint}</p>
                <Slider
                  value={[prefs[key]]}
                  onValueChange={([v]) => setPrefs((p) => ({ ...p, [key]: v }))}
                  min={0}
                  max={100}
                  step={5}
                  thumbLabel={label}
                  aria-labelledby={`${key}-label`}
                />
              </div>
            ))}
            <div className="flex flex-wrap justify-end gap-3">
              <SecondaryButton onClick={() => setPrefs(DEFAULT_PREFERENCES)}>
                <RotateCcw className="h-4 w-4" aria-hidden="true" /> Reset to defaults
              </SecondaryButton>
              <PrimaryButton onClick={handleSave} disabled={!dirty}>Save thresholds</PrimaryButton>
            </div>
          </div>
        </Card>

        <div className="space-y-3">
          <h2 className="px-1 text-sm font-bold uppercase tracking-wider text-slate-600">Coming next</h2>
          {UPCOMING.map(({ Icon, title, body }) => (
            <Card key={title} className="flex items-start gap-3 p-4" aria-disabled="true">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100">
                <Icon className="h-4 w-4 text-slate-500" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-900">{title}</p>
                  <ComingSoon />
                </div>
                <p className="mt-0.5 text-sm text-slate-600">{body}</p>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </PageContainer>
  );
};

export default Settings;
