import React from 'react';
import {
  Github, Linkedin, Mail, Phone, Briefcase, GraduationCap, ArrowUpRight, AlertTriangle, CheckCircle2, CircleDashed, XCircle,
} from 'lucide-react';
import Modal from './Modal';
import { CANDIDATE_STATUSES } from '../lib/statuses';
import { DEFAULT_PREFERENCES } from '../lib/preferences';
import { cn } from '../lib/utils';
import { ScoreRing, Initials, PrimaryButton } from './common';

const SOURCE_LABELS = { github: 'GitHub', linkedin: 'LinkedIn', webCheck: 'Web check' };

const SourceStatus = ({ label, state }) => {
  const cfg = {
    verified: { Icon: CheckCircle2, cls: 'text-emerald-700 bg-emerald-50 ring-emerald-200', text: 'Verified' },
    unverified: { Icon: XCircle, cls: 'text-red-700 bg-red-50 ring-red-200', text: 'Not verified' },
  }[state] || { Icon: CircleDashed, cls: 'text-slate-600 bg-slate-50 ring-slate-200', text: 'Not checked' };
  return (
    <div className={cn('flex items-center justify-between rounded-xl px-3 py-2 text-sm ring-1 ring-inset', cfg.cls)}>
      <span className="font-semibold">{label}</span>
      <span className="flex items-center gap-1.5 text-xs font-semibold"><cfg.Icon className="h-4 w-4" aria-hidden="true" />{cfg.text}</span>
    </div>
  );
};

const Section = ({ title, Icon, items, empty }) => (
  <section>
    <h3 className="mb-2 text-xs font-bold uppercase tracking-widest text-brand-accent">{title}</h3>
    {items.length === 0 ? (
      <p className="text-sm text-slate-500">{empty}</p>
    ) : (
      <ul className="space-y-2.5">
        {items.map((text, i) => (
          <li key={i} className="flex items-start gap-3 text-sm text-slate-800">
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
            <span className="leading-relaxed">{text}</span>
          </li>
        ))}
      </ul>
    )}
  </section>
);

const CandidateModal = ({ open, candidate, job, prefs = DEFAULT_PREFERENCES, onClose, onStatusUpdate, onTakeInterview }) => {
  if (!candidate) return null;

  const verificationStatus = candidate.verificationStatus || {};
  const skillMatches = [...(candidate.skillMatches || [])].sort((a, b) => (b.score || 0) - (a.score || 0));
  const needsReview = candidate.verificationScore < prefs.verificationThreshold;

  return (
    <Modal
      open={open}
      onOpenChange={(isOpen) => { if (!isOpen) onClose(); }}
      title={candidate.name}
      description={job ? `Candidate for ${job.title}` : 'Candidate dossier'}
      maxWidth="md:max-w-4xl"
      headerExtra={(
        <>
          <label htmlFor="candidate-status" className="sr-only">Status</label>
          <select
            id="candidate-status"
            value={candidate.status}
            onChange={(e) => onStatusUpdate?.(candidate.id, e.target.value)}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-800 outline-none focus:border-brand-accent focus:ring-2 focus:ring-brand-soft"
          >
            {CANDIDATE_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          {onTakeInterview && (
            <PrimaryButton onClick={() => onTakeInterview(candidate)} className="flex-1 md:flex-none">
              <ArrowUpRight className="h-4 w-4" aria-hidden="true" /> Take interview
            </PrimaryButton>
          )}
        </>
      )}
    >
      <div className="grid grid-cols-1 md:grid-cols-[1fr_320px]">
        {/* Left: identity, scores, resume */}
        <div className="space-y-6 border-b border-slate-100 p-5 md:border-b-0 md:border-r md:p-6">
          <div className="flex items-start gap-4">
            <Initials name={candidate.name} className="h-14 w-14 rounded-2xl bg-brand-gradient text-xl" />
            <div className="min-w-0 space-y-1 text-sm text-slate-700">
              {candidate.email && <a href={`mailto:${candidate.email}`} className="flex items-center gap-2 hover:text-brand-accent"><Mail className="h-4 w-4 text-slate-500" aria-hidden="true" />{candidate.email}</a>}
              {candidate.phone && <a href={`tel:${candidate.phone}`} className="flex items-center gap-2 hover:text-brand-accent"><Phone className="h-4 w-4 text-slate-500" aria-hidden="true" />{candidate.phone}</a>}
              <div className="flex flex-wrap gap-3 pt-1">
                {candidate.githubUrl && (
                  <a href={candidate.githubUrl} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 font-semibold text-brand-accent hover:underline">
                    <Github className="h-4 w-4" aria-hidden="true" /> GitHub
                  </a>
                )}
                {candidate.linkedinUrl && (
                  <a href={candidate.linkedinUrl} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 font-semibold text-brand-accent hover:underline">
                    <Linkedin className="h-4 w-4" aria-hidden="true" /> LinkedIn
                  </a>
                )}
                {!candidate.githubUrl && !candidate.linkedinUrl && <span className="text-slate-500">No GitHub or LinkedIn on resume</span>}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <ScoreRing value={candidate.jdMatchScore} label="Role match" sublabel="Resume vs. job" size={72} stroke={6} />
            <ScoreRing value={candidate.githubScore} label="GitHub" sublabel={candidate.githubScore == null ? 'Not analysed' : 'Authenticity'} size={72} stroke={6} />
            <ScoreRing value={candidate.verificationScore} label="Credibility" sublabel="All sources" size={72} stroke={6} />
          </div>

          <Section title="Experience" Icon={Briefcase} items={candidate.experience} empty="No work experience found on the resume." />
          <Section title="Education" Icon={GraduationCap} items={candidate.education} empty="No education found on the resume." />

          <section>
            <h3 className="mb-2 text-xs font-bold uppercase tracking-widest text-brand-accent">Skills on resume</h3>
            {candidate.skills.length === 0 ? (
              <p className="text-sm text-slate-500">No skills listed on the resume.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {candidate.skills.map((s) => <span key={s} className="rounded-full bg-brand-light px-2.5 py-1 text-xs font-semibold text-brand">{s}</span>)}
              </div>
            )}
          </section>
        </div>

        {/* Right: evidence */}
        <div className="space-y-5 bg-slate-50 p-5 md:p-6">
          <section>
            <h3 className="mb-2 text-sm font-bold text-slate-900">Verification</h3>
            {needsReview && (
              <p className="mb-2 flex items-start gap-2 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-900 ring-1 ring-inset ring-amber-200">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                Credibility {candidate.verificationScore}% is below your {prefs.verificationThreshold}% threshold — review manually.
              </p>
            )}
            <div className="space-y-2">
              {Object.entries(SOURCE_LABELS).map(([key, label]) => (
                <SourceStatus key={key} label={label} state={verificationStatus[key]} />
              ))}
            </div>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-bold text-slate-900">Job skills match</h3>
            {skillMatches.length === 0 ? (
              <p className="text-sm text-slate-500">No skill scores yet.</p>
            ) : (
              <ul className="space-y-2.5">
                {skillMatches.map((m) => {
                  const score10 = Math.max(0, Math.min(10, Number(m.score) || 0));
                  return (
                    <li key={m.skill}>
                      <div className="mb-1 flex justify-between text-xs">
                        <span className="font-semibold text-slate-800">{m.skill}</span>
                        <span className="font-bold text-brand">{score10.toFixed(1)}/10</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-brand-soft">
                        <div className={cn('h-full rounded-full', score10 >= 7 ? 'bg-emerald-500' : score10 >= 4 ? 'bg-brand-accent' : 'bg-amber-500')}
                          style={{ width: `${score10 * 10}%` }} />
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>
      </div>
    </Modal>
  );
};

export default CandidateModal;
