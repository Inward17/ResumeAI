import React, { useState, useEffect } from 'react';
import { Plus, X } from 'lucide-react';
import { cn } from '../lib/utils';
import { JOB_STATUSES } from '../lib/statuses';
import Modal from './Modal';
import { Button, Field, Input, Select, Textarea } from './common';

const JOB_TYPES = ['Full-time', 'Part-time', 'Contract', 'Internship'];
const DEPARTMENTS = ['Engineering', 'Design', 'Product', 'Marketing', 'Sales', 'HR', 'Finance', 'Operations', 'Other'];
const EXP_LEVELS = ['Entry Level', 'Mid Level', 'Senior Level', 'Lead', 'Executive'];

/** Single-choice chip group (radio semantics) */
const ChoiceGroup = ({ label, options, value, onChange, allowNone = false }) => (
  <fieldset>
    <legend className="mb-1.5 text-sm font-medium text-ink-2">{label}</legend>
    <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label={label}>
      {options.map((opt) => {
        const active = value === opt;
        return (
          <button
            key={opt}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(active && allowNone ? '' : opt)}
            className={cn(
              'h-8 rounded-lg border px-3 text-sm font-medium transition-colors',
              active ? 'border-primary bg-primary-soft text-primary-soft-fg' : 'border-line-strong bg-surface text-ink-2 hover:bg-subtle',
            )}
          >
            {opt}
          </button>
        );
      })}
    </div>
  </fieldset>
);

/** Tag list editor for required / preferred skills */
const SkillsInput = ({ id, label, hint, skills, onChange, optional }) => {
  const [value, setValue] = useState('');
  const add = () => {
    const parts = value.split(',').map((s) => s.trim()).filter(Boolean);
    const next = [...skills];
    parts.forEach((p) => { if (!next.some((s) => s.toLowerCase() === p.toLowerCase())) next.push(p); });
    onChange(next);
    setValue('');
  };
  return (
    <Field label={label} htmlFor={id} hint={hint} optional={optional}>
      <div className="flex min-h-9 flex-wrap items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-2 py-1.5 shadow-sm focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20">
        {skills.map((skill) => (
          <span key={skill} className="inline-flex items-center gap-1 rounded-md bg-primary-soft py-0.5 pl-2 pr-1 text-xs font-medium text-primary-soft-fg">
            {skill}
            <button type="button" onClick={() => onChange(skills.filter((s) => s !== skill))} aria-label={`Remove ${skill}`}
              className="rounded p-0.5 opacity-70 hover:bg-primary/10 hover:opacity-100">
              <X className="h-3 w-3" aria-hidden="true" />
            </button>
          </span>
        ))}
        <input
          id={id}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(); }
            else if (e.key === 'Backspace' && !value && skills.length) onChange(skills.slice(0, -1));
          }}
          onBlur={() => value.trim() && add()}
          placeholder={skills.length ? 'Add another…' : 'Type a skill, press Enter'}
          className="h-6 min-w-[9rem] flex-1 bg-transparent px-1 text-sm text-ink outline-none placeholder:text-ink-3"
        />
        {value.trim() && (
          <button type="button" onClick={add} className="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-white" aria-label="Add skill">
            <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        )}
      </div>
    </Field>
  );
};

const Section = ({ title, children }) => (
  <section className="space-y-4">
    <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-3">{title}</h3>
    {children}
  </section>
);

const EMPTY = {
  title: '', description: '', requirements: [], preferredSkills: [],
  employmentType: 'Full-time', location: '', department: '', experienceLevel: '',
  status: 'Active', salaryMin: '', salaryMax: '',
};

const JobModal = ({ isOpen, onClose, job, onSave }) => {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const isEditing = !!job;

  useEffect(() => {
    if (!isOpen) return;
    setError('');
    setForm(job ? {
      title: job.title || '',
      description: job.description || '',
      requirements: job.requirements || [],
      preferredSkills: job.preferredSkills || [],
      employmentType: job.employmentType || 'Full-time',
      location: job.location || '',
      department: job.department || '',
      experienceLevel: job.experienceLevel || '',
      status: job.status || 'Active',
      salaryMin: job.salaryMin ?? '',
      salaryMax: job.salaryMax ?? '',
    } : EMPTY);
  }, [isOpen, job]);

  const set = (key, val) => setForm((f) => ({ ...f, [key]: val }));
  const salaryInvalid = form.salaryMin !== '' && form.salaryMax !== '' && Number(form.salaryMin) > Number(form.salaryMax);
  const canSave = form.title.trim() && form.description.trim() && !salaryInvalid && !saving;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSave) return;
    setSaving(true);
    setError('');
    try {
      await onSave({ ...form, title: form.title.trim(), description: form.description.trim(), location: form.location.trim() });
    } catch (err) {
      setError(err.message || 'Could not save the job.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={isOpen}
      onOpenChange={(open) => { if (!open) onClose(); }}
      title={isEditing ? 'Edit job' : 'New job'}
      description="Candidates are scored against the description and skills below."
      footer={(
        <div className="flex items-center justify-between gap-3">
          <p className="hidden text-xs text-ink-3 sm:block"><span className="text-danger">*</span> Required</p>
          <div className="flex flex-1 justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>Cancel</Button>
            <Button type="submit" form="job-form" disabled={!canSave}>
              {saving ? (isEditing ? 'Saving…' : 'Creating…') : (isEditing ? 'Save changes' : form.status === 'Draft' ? 'Save draft' : 'Create job')}
            </Button>
          </div>
        </div>
      )}
    >
      <form id="job-form" onSubmit={handleSubmit} className="space-y-7 px-5 py-5">
        {error && <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

        <Section title="Basics">
          <Field label="Job title" htmlFor="job-title" required>
            <Input id="job-title" required autoFocus placeholder="e.g. Senior Backend Engineer"
              value={form.title} onChange={(e) => set('title', e.target.value)} />
          </Field>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Field label="Department" htmlFor="department">
              <Select id="department" value={form.department} onChange={(e) => set('department', e.target.value)}>
                <option value="">Not set</option>
                {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
              </Select>
            </Field>
            <Field label="Location" htmlFor="location" className="sm:col-span-2">
              <Input id="location" placeholder="e.g. Pune (Hybrid) or Remote"
                value={form.location} onChange={(e) => set('location', e.target.value)} />
            </Field>
          </div>
          <ChoiceGroup label="Job type" options={JOB_TYPES} value={form.employmentType} onChange={(v) => set('employmentType', v)} />
          <ChoiceGroup label="Experience level" options={EXP_LEVELS} value={form.experienceLevel} allowNone
            onChange={(v) => set('experienceLevel', v)} />
        </Section>

        <Section title="What you're screening for">
          <Field label="Job description" htmlFor="job-description" required
            hint="Responsibilities, must-haves and what success looks like. Resumes are scored against this.">
            <Textarea id="job-description" rows={6} required
              value={form.description} onChange={(e) => set('description', e.target.value)} />
          </Field>
          <SkillsInput id="required-skills" label="Required skills" hint="Each one gets its own match score per candidate."
            skills={form.requirements} onChange={(v) => set('requirements', v)} />
          <SkillsInput id="preferred-skills" label="Preferred skills" optional
            skills={form.preferredSkills} onChange={(v) => set('preferredSkills', v)} />
        </Section>

        <Section title="Status & pay">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Field label="Status" htmlFor="status"
              hint={form.status === 'Draft' ? 'Not open to candidates yet.' : undefined}>
              <Select id="status" value={form.status} onChange={(e) => set('status', e.target.value)}>
                {JOB_STATUSES.map((st) => <option key={st} value={st}>{st}</option>)}
              </Select>
            </Field>
            <Field label="Salary min (annual)" htmlFor="salary-min" optional>
              <Input id="salary-min" type="number" min="0" inputMode="numeric"
                value={form.salaryMin} onChange={(e) => set('salaryMin', e.target.value)} />
            </Field>
            <Field label="Salary max (annual)" htmlFor="salary-max" optional
              error={salaryInvalid ? 'Lower than the minimum.' : undefined}>
              <Input id="salary-max" type="number" min="0" inputMode="numeric" aria-invalid={salaryInvalid}
                value={form.salaryMax} onChange={(e) => set('salaryMax', e.target.value)} />
            </Field>
          </div>
        </Section>
      </form>
    </Modal>
  );
};

export default JobModal;
