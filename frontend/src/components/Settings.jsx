import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Sun, Moon, Monitor } from 'lucide-react';
import { Slider } from './ui/slider';
import { useToast } from '../hooks/use-toast';
import { useTheme } from '../lib/theme';
import { cn } from '../lib/utils';
import { DEFAULT_PREFERENCES, loadPreferences, savePreferences } from '../lib/preferences';
import { Card, CardHeader, PageContainer, PageHeader, Button } from './common';
import { TeamSettings, ApiKeysSettings, UsageSettings } from './WorkspaceSettings';

const THRESHOLDS = [
  {
    key: 'matchThreshold',
    label: 'Strong role match',
    hint: (v) => `Candidates scoring ${v}% or more against the job are counted as strong matches and shown in green.`,
  },
  {
    key: 'verificationThreshold',
    label: 'Manual review below',
    hint: (v) => `Candidates whose credibility is under ${v}% get a warning flag so you check them by hand.`,
  },
];

const THEME_OPTIONS = [
  { id: 'system', label: 'System', Icon: Monitor },
  { id: 'light', label: 'Light', Icon: Sun },
  { id: 'dark', label: 'Dark', Icon: Moon },
];

const GeneralSettings = () => {
  const { toast } = useToast();
  const { theme, setTheme } = useTheme();
  const [prefs, setPrefs] = useState(loadPreferences);
  const [saved, setSaved] = useState(loadPreferences);
  const dirty = THRESHOLDS.some(({ key }) => prefs[key] !== saved[key]);
  const isDefault = THRESHOLDS.every(({ key }) => prefs[key] === DEFAULT_PREFERENCES[key]);

  const handleSave = () => {
    if (savePreferences(prefs)) {
      setSaved(prefs);
      toast({ title: 'Thresholds saved', description: 'Pipelines use the new values from now on.' });
    } else {
      toast({ title: 'Could not save thresholds', description: 'Your browser blocked local storage.', variant: 'destructive' });
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Appearance" subtitle="System follows your device's light or dark setting." />
        <div className="grid grid-cols-3 gap-2 p-5" role="radiogroup" aria-label="Theme">
          {THEME_OPTIONS.map(({ id, label, Icon }) => {
            const active = theme === id;
            return (
              <button
                key={id}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => setTheme(id)}
                className={cn(
                  'flex flex-col items-center gap-2 rounded-lg border px-3 py-4 text-sm font-medium transition-colors',
                  active ? 'border-primary bg-primary-soft text-primary-soft-fg ring-1 ring-primary' : 'border-line-strong text-ink-2 hover:bg-subtle',
                )}
              >
                <Icon className="h-5 w-5" aria-hidden="true" />
                {label}
              </button>
            );
          })}
        </div>
      </Card>

      <Card>
        <CardHeader title="Scoring thresholds" subtitle="Applied to pipelines, interview cards and candidate dossiers." />
        <div className="divide-y divide-line">
          {THRESHOLDS.map(({ key, label, hint }) => (
            <div key={key} className="p-5">
              <div className="mb-3 flex items-center justify-between gap-4">
                <p id={`${key}-label`} className="text-sm font-medium text-ink">{label}</p>
                <span className="min-w-[3.5rem] rounded-md bg-subtle px-2 py-0.5 text-center text-sm font-semibold tabular-nums text-ink">
                  {prefs[key]}%
                </span>
              </div>
              <Slider
                value={[prefs[key]]}
                onValueChange={([v]) => setPrefs((p) => ({ ...p, [key]: v }))}
                min={0}
                max={100}
                step={5}
                thumbLabel={label}
                aria-labelledby={`${key}-label`}
              />
              <p className="mt-3 text-sm text-ink-3">{hint(prefs[key])}</p>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-subtle/50 px-5 py-3">
          <Button variant="ghost" size="sm" onClick={() => setPrefs(DEFAULT_PREFERENCES)} disabled={isDefault}>
            Reset to defaults
          </Button>
          <div className="flex items-center gap-3">
            {dirty && <span className="text-xs text-ink-3">Unsaved changes</span>}
            <Button onClick={handleSave} disabled={!dirty}>Save</Button>
          </div>
        </div>
      </Card>
    </div>
  );
};

const SECTIONS = [
  { id: 'general', label: 'General', description: 'Appearance and scoring, saved in this browser.', Component: GeneralSettings },
  { id: 'team', label: 'Team', description: 'Members of this workspace and invitations.', Component: TeamSettings },
  { id: 'api-keys', label: 'API keys', description: 'Keys for calling the ResumeAI API.', Component: ApiKeysSettings },
  { id: 'usage', label: 'Plan & usage', description: 'Workspace usage and the live limits of the services ResumeAI runs on.', Component: UsageSettings },
];

const Settings = () => {
  const [params, setParams] = useSearchParams();
  const current = SECTIONS.find((x) => x.id === params.get('tab')) || SECTIONS[0];
  const { Component } = current;

  return (
    <PageContainer>
      <PageHeader title="Settings" description={current.description} />
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[11rem_minmax(0,1fr)] lg:gap-10">
        <nav aria-label="Settings sections"
          className="no-scrollbar -mx-4 flex gap-1 overflow-x-auto border-b border-line px-4 lg:sticky lg:top-6 lg:mx-0 lg:flex-col lg:border-0 lg:px-0">
          {SECTIONS.map(({ id, label }) => {
            const active = id === current.id;
            return (
              <button key={id} type="button" aria-current={active ? 'page' : undefined}
                onClick={() => setParams(id === 'general' ? {} : { tab: id })}
                className={cn(
                  'whitespace-nowrap px-3 py-2 text-left text-sm transition-colors',
                  'border-b-2 lg:rounded-md lg:border lg:border-transparent',
                  active
                    ? 'border-ink font-medium text-ink lg:border-line lg:bg-surface lg:shadow-[0_1px_2px_rgb(0_0_0/0.05)]'
                    : 'border-transparent text-ink-3 hover:text-ink lg:hover:bg-subtle',
                )}>
                {label}
              </button>
            );
          })}
        </nav>
        <div className="max-w-3xl"><Component /></div>
      </div>
    </PageContainer>
  );
};

export default Settings;
