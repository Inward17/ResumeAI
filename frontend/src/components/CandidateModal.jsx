import React from 'react';
import {
  Github, Linkedin, Mail, Phone, Briefcase, GraduationCap, ArrowRight, AlertTriangle, CheckCircle2, CircleDashed, XCircle, Globe, Code2, Palette, Users,
} from 'lucide-react';
import Modal from './Modal';
import { CANDIDATE_STATUSES } from '../lib/statuses';
import { DEFAULT_PREFERENCES } from '../lib/preferences';
import { cn } from '../lib/utils';
import { ScoreRing, Initials, Button, Select, Tag, scoreLevel } from './common';
import ProjectReviews, { useProjectReviews } from './ProjectReviews';

const SOURCES = [
  { key: 'github', label: 'GitHub', Icon: Github },
  { key: 'linkedin', label: 'LinkedIn', Icon: Linkedin },
  { key: 'webCheck', label: 'Web check', Icon: Globe },
];

const SOURCE_STATE = {
  verified: { Icon: CheckCircle2, cls: 'text-success', text: 'Verified' },
  unverified: { Icon: XCircle, cls: 'text-danger', text: 'Not verified' },
};
// The web check only shows that the companies and colleges exist
const WEB_STATE = {
  verified: { ...SOURCE_STATE.verified, text: 'Organisation found' },
  unverified: { ...SOURCE_STATE.unverified, text: 'Not found' },
};
const NOT_CHECKED = { Icon: CircleDashed, cls: 'text-ink-3', text: 'Not checked' };

const PLATFORM_LABEL = {
  leetcode: 'LeetCode', hackerrank: 'HackerRank', hackerearth: 'HackerEarth', codeforces: 'Codeforces', codechef: 'CodeChef',
};
const PROFILE_STATE = {
  found: { ...SOURCE_STATE.verified, text: 'Found' },
  mismatch: { Icon: AlertTriangle, cls: 'text-warning', text: 'Mismatch' },
  not_found: { ...SOURCE_STATE.unverified, text: 'Not found' },
  unavailable: { ...NOT_CHECKED, text: 'Could not check' },
  not_configured: NOT_CHECKED,
};
const dash = (v) => (v == null || v === '' ? '—' : v);

// Discrepancies from the LinkedIn comparison carry no source
// Portfolios first, then community profiles
const PORTFOLIO_LABEL = {
  behance: 'Behance', dribbble: 'Dribbble', website: 'Portfolio website', kaggle: 'Kaggle', stackoverflow: 'Stack Overflow',
};
const PORTFOLIO_ICON = { behance: Palette, dribbble: Palette, website: Globe, kaggle: Users, stackoverflow: Users };
const PROFILE_SOURCE = { ...PLATFORM_LABEL, ...PORTFOLIO_LABEL };

const SOURCE_LABEL = { ...PROFILE_SOURCE, projects: 'Projects', coding_profiles: 'Coding profiles', github: 'GitHub', linkedin: 'LinkedIn', webCheck: 'Web check' };
const sourceLabel = (source) => (source ? SOURCE_LABEL[source] || String(source) : 'LinkedIn');
const SEVERITY_ORDER = { critical: 0, major: 1, minor: 2 };
const severityRank = (s) => SEVERITY_ORDER[s] ?? 2;
const isMinor = (s) => severityRank(s) >= 2;

const Discrepancies = ({ items }) => (
  <div className="mt-4">
    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-3">Discrepancies</h4>
    <ul className="space-y-2">
      {items.map((d, i) => (
        <li key={i} className={cn(
          'flex items-start gap-2 rounded-lg px-3 py-2 text-xs leading-relaxed ring-1 ring-inset',
          isMinor(d.severity) ? 'bg-surface text-ink-2 ring-line' : 'bg-warning-soft text-warning ring-warning/25',
        )}>
          {isMinor(d.severity)
            ? <CircleDashed className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-3" aria-hidden="true" />
            : <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />}
          <span>
            <span className="font-semibold">{isMinor(d.severity) ? 'Minor' : 'Major'} · {sourceLabel(d.source)}:</span> {d.description}
          </span>
        </li>
      ))}
    </ul>
  </div>
);

const CodingProfiles = ({ profiles, notes = {} }) => (
  <section>
    <h3 className="mb-2.5 text-sm font-semibold text-ink">Coding profiles</h3>
    <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
      {profiles.map((p) => {
        const st = PROFILE_STATE[p.status === 'found' && p.issues.length ? 'mismatch' : p.status] || NOT_CHECKED;
        const label = PLATFORM_LABEL[p.platform] || p.platform;
        const rating = p.rating == null ? null : (p.maxRating != null && p.maxRating !== p.rating ? `${p.rating} (max ${p.maxRating})` : p.rating);
        return (
          <li key={p.platform} className="space-y-2 px-3 py-2.5 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="flex min-w-0 items-center gap-2 text-ink-2">
                <Code2 className="h-4 w-4 shrink-0 text-ink-3" aria-hidden="true" />
                <span className="shrink-0">{label}</span>
                {p.profileUrl ? (
                  <a href={p.profileUrl} target="_blank" rel="noreferrer" className="truncate font-medium text-primary-text hover:underline">{p.handle}</a>
                ) : <span className="truncate">{p.handle}</span>}
              </span>
              <span className={cn('flex shrink-0 items-center gap-1.5 text-xs font-medium', st.cls)}>
                <st.Icon className="h-4 w-4" aria-hidden="true" />{st.text}
              </span>
            </div>
            {p.status === 'found' && (
              <dl className="grid grid-cols-3 gap-2 text-xs">
                <div><dt className="text-ink-3">Rating</dt><dd className="tabular-nums text-ink">{dash(rating)}</dd></div>
                <div><dt className="text-ink-3">Title</dt><dd className="truncate capitalize text-ink">{dash(p.title)}</dd></div>
                <div><dt className="text-ink-3">Solved</dt><dd className="tabular-nums text-ink">{dash(p.problemsSolved)}</dd></div>
              </dl>
            )}
            {p.issues.map((issue) => (
              <p key={issue} className="flex items-start gap-2 rounded-lg bg-warning-soft px-2.5 py-1.5 text-xs leading-relaxed text-warning ring-1 ring-inset ring-warning/25">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />{issue}
              </p>
            ))}
            {(notes[p.platform] || []).map((note) => (
              <p key={note} className="flex items-start gap-2 text-xs leading-relaxed text-ink-3">
                <CircleDashed className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />{note}
              </p>
            ))}
          </li>
        );
      })}
    </ul>
  </section>
);

const hostOf = (url, fallback) => {
  try { return new URL(url).hostname; } catch { return fallback; }
};
const listCounts = (o) => Object.entries(o).map(([k, v]) => `${v} ${k}`).join(' · ');

const Stat = ({ label, value, className }) => (
  <div className="min-w-0"><dt className="text-ink-3">{label}</dt><dd className={cn('truncate text-ink', className)}>{dash(value)}</dd></div>
);

const PortfolioStats = ({ p }) => {
  if (p.platform === 'stackoverflow') {
    return (
      <dl className="grid grid-cols-3 gap-2 text-xs">
        <Stat label="Reputation" value={p.reputation?.toLocaleString()} className="tabular-nums" />
        <Stat label="Badges" value={listCounts(p.badges)} />
        <Stat label="Top tags" value={p.topTags.slice(0, 4).join(', ')} />
      </dl>
    );
  }
  if (p.platform === 'kaggle') {
    return (
      <dl className="grid grid-cols-3 gap-2 text-xs">
        <Stat label="Tiers" value={Object.entries(p.tiers).map(([k, v]) => `${k} ${v}`).join(', ')} className="capitalize" />
        <Stat label="Medals" value={listCounts(p.medals)} />
        <Stat label="Competitions" value={p.competitions} className="tabular-nums" />
      </dl>
    );
  }
  return (
    <>
      {(p.followers != null || p.appreciations != null) && (
        <dl className="grid grid-cols-3 gap-2 text-xs">
          <Stat label="Followers" value={p.followers?.toLocaleString()} className="tabular-nums" />
          <Stat label="Appreciations" value={p.appreciations?.toLocaleString()} className="tabular-nums" />
        </dl>
      )}
      {p.projects.length > 0 && (
        <ul className="space-y-1 text-xs">
          {p.projects.slice(0, 3).map((pr, i) => (
            <li key={i} className="text-ink-2">
              {pr.url ? <a href={pr.url} target="_blank" rel="noreferrer" className="font-medium text-primary-text hover:underline">{pr.title}</a>
                : <span className="font-medium text-ink">{pr.title}</span>}
              {pr.dates && <span className="text-ink-3"> · {pr.dates}</span>}
              {pr.tools.length > 0 && <span className="text-ink-3"> · {pr.tools.slice(0, 5).join(', ')}</span>}
            </li>
          ))}
        </ul>
      )}
    </>
  );
};

const Portfolios = ({ profiles, evidence, notes = {} }) => (
  <section>
    <h3 className="mb-2.5 text-sm font-semibold text-ink">Portfolios &amp; communities</h3>
    <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface">
      {profiles.map((p) => {
        const st = PROFILE_STATE[p.status === 'found' && p.issues.length ? 'mismatch' : p.status] || NOT_CHECKED;
        const Icon = PORTFOLIO_ICON[p.platform] || Globe;
        const shown = p.platform === 'website' ? hostOf(p.profileUrl, p.handle) : p.handle;
        const extraNotes = [...(notes[p.platform] || []), ...(p.status !== 'found' && p.note ? [p.note] : [])];
        return (
          <li key={p.platform} className="space-y-2 px-3 py-2.5 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="flex min-w-0 items-center gap-2 text-ink-2">
                <Icon className="h-4 w-4 shrink-0 text-ink-3" aria-hidden="true" />
                <span className="shrink-0">{PORTFOLIO_LABEL[p.platform] || p.platform}</span>
                {p.profileUrl ? (
                  <a href={p.profileUrl} target="_blank" rel="noreferrer" className="truncate font-medium text-primary-text hover:underline">{shown}</a>
                ) : <span className="truncate">{shown}</span>}
              </span>
              <span className={cn('flex shrink-0 items-center gap-1.5 text-xs font-medium', st.cls)}>
                <st.Icon className="h-4 w-4" aria-hidden="true" />{st.text}
              </span>
            </div>
            {p.status === 'found' && (
              <>
                {(p.name || p.headline) && (
                  <p className="truncate text-xs text-ink-2">{[p.name, p.headline].filter(Boolean).join(' · ')}</p>
                )}
                <PortfolioStats p={p} />
              </>
            )}
            {p.issues.map((issue) => (
              <p key={issue} className="flex items-start gap-2 rounded-lg bg-warning-soft px-2.5 py-1.5 text-xs leading-relaxed text-warning ring-1 ring-inset ring-warning/25">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />{issue}
              </p>
            ))}
            {extraNotes.map((note) => (
              <p key={note} className="flex items-start gap-2 text-xs leading-relaxed text-ink-3">
                <CircleDashed className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />{note}
              </p>
            ))}
          </li>
        );
      })}
    </ul>
    {evidence.length > 0 && (
      <p className="mt-2 text-xs leading-relaxed text-ink-3">
        <span className="font-medium text-ink-2">Job skills shown here:</span>{' '}
        {evidence.map((e) => `${e.skill} (${e.sources.map((s) => PORTFOLIO_LABEL[s] || s).join(', ')})`).join(', ')}.
        {' '}Evidence only; not part of the role match.
      </p>
    )}
  </section>
);

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
  // Hooks before the early return; only fetched while the dossier is open
  const projectReviews = useProjectReviews(open && job?.id, open && candidate?.id);
  if (!candidate) return null;

  const verificationStatus = candidate.verificationStatus || {};
  const skillMatches = [...(candidate.skillMatches || [])].sort((a, b) => (b.score || 0) - (a.score || 0));
  const needsReview = candidate.verificationScore != null && candidate.verificationScore < prefs.verificationThreshold;
  const skills = candidate.skills || [];
  // Coding-platform and portfolio discrepancies show under their profile, everything else in one list
  const allDiscrepancies = [...(verificationStatus.discrepancies || []), ...(projectReviews.data?.discrepancies || [])];
  const discrepancies = allDiscrepancies
    .filter((d) => !PROFILE_SOURCE[d.source])
    .sort((a, b) => severityRank(a.severity) - severityRank(b.severity));
  const profileNotes = {};
  allDiscrepancies.filter((d) => PROFILE_SOURCE[d.source] && (d.field === 'coding_profile' || d.field === 'portfolio_profile'))
    .forEach((d) => { (profileNotes[d.source] ||= []).push(d.description); });
  const portfolioOrder = Object.keys(PORTFOLIO_LABEL);
  const portfolios = [...(candidate.portfolios || [])]
    .sort((a, b) => portfolioOrder.indexOf(a.platform) - portfolioOrder.indexOf(b.platform));

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
            <div className="flex items-center gap-3">
              {candidate.interviewScore != null && (
                <span className="text-sm text-ink-3">
                  Interview <span className="font-medium tabular-nums text-ink">{candidate.interviewScore}%</span>
                </span>
              )}
              <Button onClick={() => onTakeInterview(candidate)}>
                {candidate.interviewScore != null ? 'Open interview' : 'Start interview'} <ArrowRight aria-hidden="true" />
              </Button>
            </div>
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

          {job?.id && <ProjectReviews jobId={job.id} candidateId={candidate.id} state={projectReviews} />}
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
                const st = (key === 'webCheck' ? WEB_STATE : SOURCE_STATE)[verificationStatus[key]] || NOT_CHECKED;
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
            {discrepancies.length > 0 && <Discrepancies items={discrepancies} />}
          </section>

          {candidate.codingProfiles?.length > 0 && <CodingProfiles profiles={candidate.codingProfiles} notes={profileNotes} />}

          {portfolios.length > 0 && (
            <Portfolios profiles={portfolios} evidence={candidate.portfolioSkillEvidence || []} notes={profileNotes} />
          )}

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
