import React, { useState, useEffect } from 'react';
import { X, ChevronDown, Zap, Plus, MapPin } from 'lucide-react';
import { C } from '../theme';

const JOB_TYPES  = ['Full-time', 'Contract', 'Part-time'];
const LOCATIONS  = ['On-site', 'Hybrid', 'Remote'];
const DEPARTMENTS = ['Engineering', 'Design', 'Product', 'Marketing', 'Sales', 'HR', 'Finance', 'Operations', 'Other'];
const STATUSES    = ['Active', 'Draft', 'Closed'];
const EXP_LEVELS = ['Entry Level', 'Mid Level', 'Senior Level', 'Lead', 'Executive'];

/* ── Inline pill toggle (unselected = light border, selected = navy filled) ── */
const PillToggle = ({ label, active, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    className="px-3.5 py-1.5 rounded-lg text-xs font-semibold border transition-all duration-150"
    style={active
      ? { background: C.primary, color: '#fff', borderColor: C.primary }
      : { background: '#f8fafc', color: '#64748b', borderColor: '#e2e8f0' }
    }
  >
    {label}
  </button>
);

/* ── Light select-style dropdown ── */
const FSelect = ({ label, id, value, onChange, options }) => (
  <div>
    {label && (
      <label htmlFor={id} className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
        {label}
      </label>
    )}
    <div className="relative">
      <select
        id={id}
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full appearance-none px-3 py-2 rounded-xl border border-slate-200 bg-white text-sm text-slate-800 outline-none focus:ring-2 focus:ring-indigo-200 pr-8 transition cursor-pointer"
      >
        <option value="">Select…</option>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
    </div>
  </div>
);

/* ── Text input ── */
const FInput = ({ label, id, required, ...props }) => (
  <div>
    {label && (
      <label htmlFor={id} className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
        {label}{required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
    )}
    <input
      id={id}
      {...props}
      className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white text-sm text-slate-800 placeholder:text-slate-300 outline-none focus:ring-2 focus:ring-indigo-200 transition"
    />
  </div>
);

const EMPTY = {
  title: '', description: '', requirements: [],
  employmentType: 'Full-time', location: 'Remote', locationText: '',
  department: '', experienceLevel: '', status: 'Active',
  salaryMin: '', salaryMax: '',
};

const JobModal = ({ isOpen, onClose, job, onSave }) => {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving]     = useState(false);
  const [skillInput, setSkillInput] = useState('');
  const isEditing = !!job;

  useEffect(() => {
    if (isOpen) {
      setForm(job ? {
        title:           job.title           || '',
        description:     job.description     || '',
        requirements:    job.requirements    || [],
        employmentType:  job.employmentType  || 'Full-time',
        location:        job.location        || 'Remote',
        locationText:    job.locationText    || '',
        department:      job.department      || '',
        experienceLevel: job.experienceLevel || '',
        status:          job.status          || 'Active',
        salaryMin:       job.salaryMin       || '',
        salaryMax:       job.salaryMax       || '',
      } : EMPTY);
      setSkillInput('');
    }
  }, [isOpen, job]);

  if (!isOpen) return null;

  const set = (key, val) => setForm(f => ({ ...f, [key]: val }));

  const addSkill = () => {
    const s = skillInput.trim();
    if (s && !form.requirements.includes(s)) {
      set('requirements', [...form.requirements, s]);
    }
    setSkillInput('');
  };

  const removeSkill = (skill) => set('requirements', form.requirements.filter(r => r !== skill));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.title.trim() || !form.description.trim()) return;
    setSaving(true);
    try {
      await onSave({ ...form });
    } finally {
      setSaving(false);
    }
  };

  // Predicted candidate count
  const predicted = Math.max(12, Math.min(200, Math.round(form.description.length / 5)));

  return (
    <div
      className="fixed inset-0 z-50 flex items-end md:items-center justify-center md:p-4 p-0"
      style={{ background: 'rgba(15,14,42,0.45)', backdropFilter: 'blur(6px)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="bg-white md:rounded-2xl rounded-t-3xl shadow-2xl w-full max-w-[800px] flex flex-col overflow-hidden h-[95vh] md:h-auto md:max-h-[92vh]"
      >
        {/* ── Modal Header ── */}
        <div className="px-6 pt-6 pb-4 relative">
          {/* AI badge */}
          <div className="flex items-center gap-2 mb-3">
            <span
              className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full"
              style={{ background: '#ccfbf1', color: '#0f766e' }}
            >
              <Zap className="h-3 w-3" /> AI Optimised Listing
            </span>
          </div>
          <h2 className="text-xl font-black text-slate-900 leading-tight">
            {isEditing ? 'Edit Job Posting' : 'Create Job Posting'}
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            {isEditing
              ? 'Refine requirements and AI will re-curate your candidate pool.'
              : 'Define the role and let our AI curate the perfect candidates.'}
          </p>
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-5 right-5 h-8 w-8 flex items-center justify-center rounded-xl hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
          >
            <X className="h-4.5 w-4.5" />
          </button>
        </div>

        {/* ── Divider ── */}
        <div className="h-px bg-slate-100 mx-6" />

        {/* ── Form ── */}
        <form id="job-form" onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-6 py-4 space-y-4">

          {/* Row 1: Job Title + Department + Status */}
          <div className="flex flex-col md:grid md:grid-cols-[1fr_auto_auto] gap-4 md:gap-3 md:items-end">
            <FInput
              id="job-title"
              label="Job Title"
              required
              placeholder="e.g. Senior Product Designer"
              value={form.title}
              onChange={e => set('title', e.target.value)}
            />
            <div className="w-full md:w-32">
              <FSelect
                id="department"
                label="Department"
                value={form.department}
                onChange={v => set('department', v)}
                options={DEPARTMENTS}
              />
            </div>
            <div className="w-full md:w-28">
              <FSelect
                id="status"
                label="Status"
                value={form.status}
                onChange={v => set('status', v)}
                options={STATUSES}
              />
            </div>
          </div>

          {/* Row 2: Job Type pills + Experience Level pills */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">Job Type</p>
              <div className="flex flex-wrap gap-1.5">
                {JOB_TYPES.map(t => (
                  <PillToggle
                    key={t}
                    label={t}
                    active={form.employmentType === t}
                    onClick={() => set('employmentType', t)}
                  />
                ))}
              </div>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">Experience Level</p>
              <div className="flex flex-wrap gap-1.5">
                {EXP_LEVELS.map(l => (
                  <PillToggle
                    key={l}
                    label={l}
                    active={form.experienceLevel === l}
                    onClick={() => set('experienceLevel', form.experienceLevel === l ? '' : l)}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Location — text input + work-type pills */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">Location</p>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                <input
                  id="location-text"
                  value={form.locationText}
                  onChange={e => set('locationText', e.target.value)}
                  placeholder="e.g. San Francisco, CA"
                  className="w-full pl-8 pr-3 py-2 rounded-xl border border-slate-200 bg-white text-sm text-slate-800 placeholder:text-slate-300 outline-none focus:ring-2 focus:ring-indigo-200 transition"
                />
              </div>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">Work Preference</p>
              <div className="flex flex-wrap gap-1.5">
                {LOCATIONS.map(l => (
                  <PillToggle
                    key={l}
                    label={l}
                    active={form.location === l}
                    onClick={() => set('location', l)}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Job Description */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label htmlFor="job-description" className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Job Description <span className="text-red-400">*</span>
              </label>
              <span className="text-[10px] text-slate-300 flex items-center gap-1">
                <Zap className="h-3 w-3" style={{ color: C.cyan }} />
                AI generate with description
              </span>
            </div>
            <textarea
              id="job-description"
              rows={5}
              value={form.description}
              onChange={e => set('description', e.target.value)}
              placeholder="Describe the role, responsibilities, and cultural fit…"
              className="w-full px-3 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-sm text-slate-800 placeholder:text-slate-300 outline-none focus:ring-2 focus:ring-indigo-200 transition resize-none"
            />
          </div>

          {/* Required Skills */}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">Required Skills</p>
            <div className="flex flex-wrap gap-2 items-center min-h-[36px] p-2.5 rounded-xl border border-slate-200 bg-slate-50">
              {/* Existing skill pills (dark navy) */}
              {form.requirements.map(skill => (
                <span
                  key={skill}
                  className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-lg font-bold text-white"
                  style={{ background: C.primary }}
                >
                  {skill}
                  <button
                    type="button"
                    onClick={() => removeSkill(skill)}
                    className="hover:opacity-70 transition-opacity text-white/70 hover:text-white"
                  >
                    ×
                  </button>
                </span>
              ))}
              {/* Inline input */}
              <div className="flex items-center gap-1.5 flex-1 min-w-[120px]">
                <input
                  placeholder="+ Add Skill"
                  value={skillInput}
                  onChange={e => setSkillInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }}
                  className="flex-1 bg-transparent text-sm text-slate-600 placeholder:text-slate-400 outline-none min-w-0"
                />
                {skillInput.trim() && (
                  <button
                    type="button"
                    onClick={addSkill}
                    className="h-6 w-6 rounded-md flex items-center justify-center text-white transition-colors"
                    style={{ background: C.accent }}
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Salary range (optional) */}
          <div className="grid grid-cols-2 gap-3">
            <FInput id="salary-min" label="Salary Min (USD)" type="number"
              placeholder="e.g. 60,000"
              value={form.salaryMin}
              onChange={e => set('salaryMin', e.target.value)} />
            <FInput id="salary-max" label="Salary Max (USD)" type="number"
              placeholder="e.g. 120,000"
              value={form.salaryMax}
              onChange={e => set('salaryMax', e.target.value)} />
          </div>
        </form>

        {/* ── Footer ── */}
        <div className="h-px bg-slate-100 mx-6" />
        <div className="px-6 py-4 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="text-sm font-semibold text-slate-500 hover:text-slate-800 transition-colors"
          >
            Cancel
          </button>

          <div className="flex items-center gap-3">
            {/* Predicted match */}
            {form.description.length > 20 && (
              <div className="text-right">
                <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400">Predicted Match</p>
                <p className="text-sm font-black" style={{ color: C.primary }}>{predicted}+ Candidates</p>
              </div>
            )}

            <button
              type="submit"
              form="job-form"
              disabled={saving || !form.title.trim() || !form.description.trim()}
              className="px-6 py-2.5 rounded-xl text-sm font-bold text-white transition-all hover:opacity-90 disabled:opacity-40"
              style={{ background: C.primary }}
            >
              {saving
                ? (isEditing ? 'Saving…' : 'Creating…')
                : (isEditing ? 'Save Changes' : 'Create Job')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default JobModal;