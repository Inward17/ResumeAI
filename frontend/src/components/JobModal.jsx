import React, { useState, useEffect } from 'react';
import { Plus, X } from 'lucide-react';
import { cn } from '../lib/utils';
import { JOB_STATUSES } from '../lib/statuses';
import Modal from './Modal';
import { PrimaryButton, SecondaryButton } from './common';

const JOB_TYPES = ['Full-time', 'Part-time', 'Contract', 'Internship'];
const DEPARTMENTS = ['Engineering', 'Design', 'Product', 'Marketing', 'Sales', 'HR', 'Finance', 'Operations', 'Other'];
const EXP_LEVELS = ['Entry Level', 'Mid Level', 'Senior Level', 'Lead', 'Executive'];

const fieldLabel = 'mb-1.5 block text-xs font-bold uppercase tracking-wider text-slate-600';
const fieldInput = 'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-500 outline-none transition focus:border-brand-accent focus:ring-2 focus:ring-brand-soft';

const PillToggle = ({ label, active, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    aria-pressed={active}
    className={cn(
      'rounded-lg border px-3.5 py-1.5 text-xs font-semibold transition-colors',
      active ? 'border-brand bg-brand text-white' : 'border-slate-200 bg-slate-50 text-slate-600 hover:border-slate-300',
    )}
  >
    {label}
  </button>
);

/** Tag list editor for required / preferred skills */
const SkillsInput = ({ id, label, skills, onChange, tone = 'brand' }) => {
  const [value, setValue] = useState('');
  const add = () => {
    const parts = value.split(',').map((s) => s.trim()).filter(Boolean);
    const next = [...skills];
    parts.forEach((p) => { if (!next.some((s) => s.toLowerCase() === p.toLowerCase())) next.push(p); });
    onChange(next);
    setValue('');
  };
  return (
    <div>
      <label htmlFor={id} className={fieldLabel}>{label}</label>
      <div className="flex min-h-[44px] flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 p-2 focus-within:border-brand-accent focus-within:ring-2 focus-within:ring-brand-soft">
        {skills.map((skill) => (
          <span key={skill} className={cn(
            'inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-semibold',
            tone === 'brand' ? 'bg-brand text-white' : 'bg-brand-light text-brand',
          )}>
            {skill}
            <button type="button" onClick={() => onChange(skills.filter((s) => s !== skill))} aria-label={`Remove ${skill}`}
              className="rounded opacity-70 hover:opacity-100">
              <X className="h-3 w-3" aria-hidden="true" />
            </button>
          </span>
        ))}
        <input
          id={id}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(); } }}
          onBlur={() => value.trim() && add()}
          placeholder={skills.length ? 'Add another…' : 'Type a skill and press Enter'}
          className="min-w-[10rem] flex-1 bg-transparent px-1 text-sm text-slate-900 outline-none placeholder:text-slate-500"
        />
        {value.trim() && (
          <button type="button" onClick={add} className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-accent text-white" aria-label="Add skill">
            <Plus className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
};

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
      title={isEditing ? 'Edit job posting' : 'Create job posting'}
      description="Candidates are scored against the description and skills below."
      footer={(
        <div className="flex items-center justify-end gap-3">
          <SecondaryButton onClick={onClose}>Cancel</SecondaryButton>
          <PrimaryButton type="submit" form="job-form" disabled={!canSave}>
            {saving ? (isEditing ? 'Saving…' : 'Creating…') : (isEditing ? 'Save changes' : 'Create job')}
          </PrimaryButton>
        </div>
      )}
    >
      <form id="job-form" onSubmit={handleSubmit} className="space-y-5 px-5 py-5 md:px-6">
        {error && <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_11rem_9rem]">
          <div>
            <label htmlFor="job-title" className={fieldLabel}>Job title <span className="text-red-600">*</span></label>
            <input id="job-title" required className={fieldInput} placeholder="e.g. Senior Backend Engineer"
              value={form.title} onChange={(e) => set('title', e.target.value)} />
          </div>
          <div>
            <label htmlFor="department" className={fieldLabel}>Department</label>
            <select id="department" className={fieldInput} value={form.department} onChange={(e) => set('department', e.target.value)}>
              <option value="">Not set</option>
              {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="status" className={fieldLabel}>Status</label>
            <select id="status" className={fieldInput} value={form.status} onChange={(e) => set('status', e.target.value)}>
              {JOB_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <p className={fieldLabel}>Job type</p>
            <div className="flex flex-wrap gap-1.5">
              {JOB_TYPES.map((t) => <PillToggle key={t} label={t} active={form.employmentType === t} onClick={() => set('employmentType', t)} />)}
            </div>
          </div>
          <div>
            <p className={fieldLabel}>Experience level</p>
            <div className="flex flex-wrap gap-1.5">
              {EXP_LEVELS.map((l) => (
                <PillToggle key={l} label={l} active={form.experienceLevel === l}
                  onClick={() => set('experienceLevel', form.experienceLevel === l ? '' : l)} />
              ))}
            </div>
          </div>
        </div>

        <div>
          <label htmlFor="location" className={fieldLabel}>Location</label>
          <input id="location" className={fieldInput} placeholder="e.g. Pune, India (Hybrid) or Remote"
            value={form.location} onChange={(e) => set('location', e.target.value)} />
        </div>

        <div>
          <label htmlFor="job-description" className={fieldLabel}>Job description <span className="text-red-600">*</span></label>
          <textarea id="job-description" rows={5} required className={cn(fieldInput, 'resize-y bg-slate-50')}
            placeholder="Responsibilities, must-haves and what success looks like…"
            value={form.description} onChange={(e) => set('description', e.target.value)} />
        </div>

        <SkillsInput id="required-skills" label="Required skills" skills={form.requirements} onChange={(v) => set('requirements', v)} />
        <SkillsInput id="preferred-skills" label="Preferred skills (optional)" tone="light" skills={form.preferredSkills} onChange={(v) => set('preferredSkills', v)} />

        <div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="salary-min" className={fieldLabel}>Salary min (annual)</label>
              <input id="salary-min" type="number" min="0" inputMode="numeric" className={fieldInput} placeholder="Optional"
                value={form.salaryMin} onChange={(e) => set('salaryMin', e.target.value)} />
            </div>
            <div>
              <label htmlFor="salary-max" className={fieldLabel}>Salary max (annual)</label>
              <input id="salary-max" type="number" min="0" inputMode="numeric" className={fieldInput} placeholder="Optional"
                value={form.salaryMax} onChange={(e) => set('salaryMax', e.target.value)} />
            </div>
          </div>
          {salaryInvalid && <p className="mt-1.5 text-xs text-red-700">Minimum salary is higher than the maximum.</p>}
        </div>
      </form>
    </Modal>
  );
};

export default JobModal;
