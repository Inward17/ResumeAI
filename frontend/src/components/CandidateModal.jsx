import React from 'react';
import {
  Github, Linkedin, Mail, Phone, Briefcase, GraduationCap, ArrowRight, AlertTriangle, CheckCircle2, CircleDashed, XCircle, Globe,
} from 'lucide-react';
import Modal from './Modal';
import { CANDIDATE_STATUSES } from '../lib/statuses';
import { DEFAULT_PREFERENCES } from '../lib/preferences';
import { cn } from '../lib/utils';
import { ScoreRing, Initials, Button, Select, Tag, scoreLevel } from './common';

const SOURCES = [
  { key: 'github', label: 'GitHub', Icon: Github },
  { key: 'linkedin', label: 'LinkedIn', Icon: Linkedin },
  { key: 'webCheck', label: 'Web check', Icon: Globe },
];

const SOURCE_STATE = {
  verified: { Icon: CheckCircle2, cls: 'text-success', text: 'Verified' },
  unverified: { Icon: XCircle, cls: 'text-danger', text: 'Not verified' },
};
const NOT_CHECKED = { Icon: CircleDashed, cls: 'text-ink-3', text: 'Not checked' };

const Section = ({ title, Icon, items, empty }) => (
  <section>
    <h3 className="mb-2.5 text-sm font-semibold text-ink">{title}</h3>
    {items.length === 0 ? (
      <p className="text-sm text-ink-3">{empty}</p>
    ) : (
      <ul className="space-y-2.5">
        {items.map((text, i) => (
          <li key={i} className="flex items-start gap-3 text-sm text-ink-2">
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-ink-3" aria-hidden="true" />
            <span className="leading-relaxed">{text}</span>
          </li>
        ))}
      </ul>
    )}
  </section>
);

const SKILL_BAR = { good: 'bg-success', fair: 'bg-primary', low: 'bg-warning', none: 'bg-line-strong' };

const CandidateModal = ({ open, candidate, job, prefs = DEFAULT_PREFERENCES, onClose, onStatusUpdate, onTakeInterview }) => {
  if (!candidate) return null;

  const verificationStatus = candidate.verificationStatus || {};
  const skillMatches = [...(candidate.skillMatches || [])].sort((a, b) => (b.score || 0) - (a.score || 0));
  const needsReview = candidate.verificationScore != null && candidate.verificationScore < prefs.verificationThreshold;
  const skills = candidate.skills || [];

  return (
    <Modal
      open={open}
      onOpenChange={(isOpen) => { if (!isOpen) onClose(); }}
      title={candidate.name}
      description={job ? `Candidate for ${job.title}` : 'Candidate dossier'}
      maxWidth="md:max-w-4xl"
      footer={(
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <label htmlFor="candidate-status" className="text-sm text-ink-3">Status</label>
            <Select id="candidate-status" value={candidate.status} className="w-40"
              onChange={(e) => onStatusUpdate?.(candidate.id, e.target.value)}>
              {CANDIDATE_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </Select>
          </div>
          {onTakeInterview && (
            <Button onClick={() => onTakeInterview(candidate)}>
              Start interview <ArrowRight aria-hidden="true" />
            </Button>
          )}
        </div>
      )}
    >
      <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_320px]">
        {/* Left: identity, scores, resume */}
        <div className="space-y-7 p-5 md:p-6">
          <div className="flex items-start gap-4">
            <Initials name={candidate.name} className="h-12 w-12 text-base" />
            <div className="min-w-0 space-y-1 text-sm">
              {candidate.email && (
                <a href={`mailto:${candidate.email}`} className="flex items-center gap-2 text-ink-2 hover:text-primary-text">
                  <Mail className="h-4 w-4 shrink-0 text-ink-3" aria-hidden="true" /><span className="truncate">{candidate.email}</span>
                </a>
              )}
              {candidate.phone && (
                <a href={`tel:${candidate.phone}`} className="flex items-center gap-2 text-ink-2 hover:text-primary-text">
                  <Phone className="h-4 w-4 shrink-0 text-ink-3" aria-hidden="true" />{candidate.phone}
                </a>
              )}
              <div className="flex flex-wrap gap-x-4 gap-y-1 pt-0.5">
                {candidate.githubUrl && (
                  <a href={candidate.githubUrl} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 font-medium text-primary-text hover:underline">
                    <Github className="h-4 w-4" aria-hidden="true" /> GitHub
                  </a>
                )}
                {candidate.linkedinUrl && (
                  <a href={candidate.linkedinUrl} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 font-medium text-primary-text hover:underline">
                    <Linkedin className="h-4 w-4" aria-hidden="true" /> LinkedIn
                  </a>
                )}
                {!candidate.githubUrl && !candidate.linkedinUrl && <span className="text-ink-3">No GitHub or LinkedIn on resume</span>}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 rounded-lg border border-line px-2 py-5">
            <ScoreRing value={candidate.jdMatchScore} label="Role match" sublabel="Resume vs. job" size={72} strong={prefs.matchThreshold} />
            <ScoreRing value={candidate.githubScore} label="GitHub" sublabel={candidate.githubScore == null ? 'Not analysed' : 'Authenticity'} size={72} />
            <ScoreRing value={candidate.verificationScore} label="Credibility" sublabel="All sources" size={72} strong={prefs.verificationThreshold} />
          </div>

          <Section title="Experience" Icon={Briefcase} items={candidate.experience || []} empty="No work experience found on the resume." />
          <Section title="Education" Icon={GraduationCap} items={candidate.education || []} empty="No education found on the resume." />

          <section>
            <h3 className="mb-2.5 text-sm font-semibold text-ink">Skills on resume</h3>
            {skills.length === 0 ? (
              <p className="text-sm text-ink-3">No skills listed on the resume.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">{skills.map((s) => <Tag key={s}>{s}</Tag>)}</div>
            )}
          </section>
        </div>

        {/* Right: evidence */}
        <div className="space-y-7 border-t border-line bg-subtle/40 p-5 md:border-l md:border-t-0 md:p-6">
          <section>
            <h3 className="mb-2.5 text-sm font-semibold text-ink">Verification</h3>
            {needsReview && (
              <p className="mb-3 flex items-start gap-2 rounded-lg bg-warning-soft px-3 py-2 text-xs leading-relaxed text-warning ring-1 ring-inset ring-warning/25">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                Credibility {candidate.verificationScore}% is below your {prefs.verificationThreshold}% threshold — review manually.
              </p>
            )}
            <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
              {SOURCES.map(({ key, label, Icon }) => {
                const st = SOURCE_STATE[verificationStatus[key]] || NOT_CHECKED;
                return (
                  <li key={key} className="flex items-center justify-between px-3 py-2.5 text-sm">
                    <span className="flex items-center gap-2 text-ink-2"><Icon className="h-4 w-4 text-ink-3" aria-hidden="true" />{label}</span>
                    <span className={cn('flex items-center gap-1.5 text-xs font-medium', st.cls)}>
                      <st.Icon className="h-4 w-4" aria-hidden="true" />{st.text}
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>

          <section>
            <h3 className="mb-2.5 text-sm font-semibold text-ink">Job skills match</h3>
            {skillMatches.length === 0 ? (
              <p className="text-sm text-ink-3">No skill scores yet.</p>
            ) : (
              <ul className="space-y-3">
                {skillMatches.map((m) => {
                  const score10 = Math.max(0, Math.min(10, Number(m.score) || 0));
                  return (
                    <li key={m.skill}>
                      <div className="mb-1 flex justify-between gap-3 text-sm">
                        <span className="truncate text-ink-2">{m.skill}</span>
                        <span className="shrink-0 font-medium tabular-nums text-ink">{score10.toFixed(1)}<span className="text-ink-3">/10</span></span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-line">
                        <div className={cn('h-full rounded-full', SKILL_BAR[scoreLevel(score10 * 10, 70)])} style={{ width: `${score10 * 10}%` }} />
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
