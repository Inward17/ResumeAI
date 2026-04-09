import React, { useState } from 'react';
import {
  X, Github, MapPin, Briefcase, GraduationCap,
  CheckCircle, ExternalLink, Star, ChevronDown, Zap, ArrowUpRight
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import { C } from '../theme';

const STATUSES = ['New', 'Reviewing', 'Shortlisted', 'Interview', 'Offer', 'Hired', 'Rejected'];

/* ── Score ring ── */
const Ring = ({ value, label, sub, large }) => {
  const r = large ? 36 : 22;
  const circ = 2 * Math.PI * r;
  const dash  = (value / 100) * circ;
  const size  = large ? 90 : 56;
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg viewBox={`0 0 ${large ? 80 : 50} ${large ? 80 : 50}`} width={size} height={size} className="-rotate-90">
          <circle cx={large ? 40 : 25} cy={large ? 40 : 25} r={r} fill="none" stroke="#e0e7ff" strokeWidth={large ? 6 : 4}/>
          <circle cx={large ? 40 : 25} cy={large ? 40 : 25} r={r} fill="none" stroke={C.accent} strokeWidth={large ? 6 : 4}
            strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"/>
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span style={{ fontSize: large ? 16 : 11, fontWeight: 900, color: C.primary }}>{value}%</span>
        </div>
      </div>
      <span className="text-[11px] text-slate-500 font-semibold text-center">{label}</span>
      {sub && <span className="text-[10px] text-slate-400 text-center leading-tight">{sub}</span>}
    </div>
  );
};

/* ── Status select ── */
const StatusSelect = ({ value, onChange }) => (
  <div className="relative inline-block">
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="appearance-none pl-3 pr-8 py-2 rounded-xl border border-slate-200 text-sm font-semibold text-slate-700 bg-white cursor-pointer focus:ring-2 focus:ring-indigo-200 outline-none"
    >
      {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
    </select>
    <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
  </div>
);

/* ── Skill tag ── */
const SkillTag = ({ skill, level }) => (
  <span className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full font-semibold"
    style={{ background: '#eef2ff', color: C.accent }}>
    {level && <span className="w-1.5 h-1.5 rounded-full inline-block" style={{
      background: level === 'Expert' ? C.accent : level === 'Advanced' ? C.cyan : '#94a3b8'
    }} />}
    {skill}
  </span>
);

const CandidateModal = ({ candidate, job, onClose, onStatusUpdate, onTakeInterview }) => {
  const [status, setStatus] = useState(candidate.status || 'Reviewing');
  const { toast } = useToast();

  if (!candidate) return null;

  const name         = candidate.name || 'Unknown Candidate';
  const title        = candidate.currentTitle || 'Professional';
  const location     = candidate.location || 'Remote';
  const matchScore   = candidate.jdMatchScore ?? candidate.matchScore ?? 0;
  const verifyScore  = candidate.verificationScore ?? 0;
  const expScore     = candidate.experienceScore ?? Math.round((matchScore + verifyScore) / 2);
  const bio          = candidate.persona || candidate.summary || candidate.aiSummary || `${name} is a highly skilled ${title} with demonstrated expertise in their field. Based on AI analysis, this candidate shows strong alignment with the role requirements.`;
  const skills       = candidate.skills || candidate.topSkills || [];
  const github       = candidate.githubProfile || candidate.githubUrl || '';
  const linkedin     = candidate.linkedinUrl || '';
  const education    = candidate.education || [];
  const experience   = candidate.workExperience || [];
  const authScore    = candidate.authenticityScore ?? (verifyScore / 10).toFixed(1);

  const handleStatusChange = async (newStatus) => {
    setStatus(newStatus);
    if (onStatusUpdate) {
      await onStatusUpdate(candidate.id, newStatus);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(15,14,42,0.7)', backdropFilter: 'blur(4px)' }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">

        {/* ── Modal header ── */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100" style={{ background: '#f8fafc' }}>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Candidate Dossier</p>
            <p className="text-sm font-semibold text-slate-700">{job?.title || 'Job Candidate'}</p>
          </div>
          <div className="flex items-center gap-3">
            <StatusSelect value={status} onChange={handleStatusChange} />
            {onTakeInterview && (
              <button
                onClick={() => onTakeInterview(candidate, job)}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold text-white transition-all hover:opacity-90 hover:scale-[1.02]"
                style={{ background: `linear-gradient(135deg, ${C.primary}, ${C.accent})` }}
              >
                <ArrowUpRight className="h-4 w-4" />
                Take Interview
              </button>
            )}
            <button onClick={onClose} className="p-2 rounded-xl hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* ── Two-column body ── */}
        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-[1fr_340px] h-full">

            {/* LEFT: identity + persona + experience */}
            <div className="p-6 border-r border-slate-100 space-y-6">
              {/* Identity */}
              <div>
                <div className="flex items-start gap-4">
                  <div className="h-16 w-16 rounded-2xl flex items-center justify-center text-2xl font-black text-white shrink-0"
                    style={{ background: `linear-gradient(135deg, ${C.primary}, ${C.accent})` }}>
                    {name.charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1">
                    <h2 className="text-xl font-black text-slate-900">{name}</h2>
                    <p className="text-sm text-slate-500">{title}</p>
                    <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-400">
                      <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{location}</span>
                      {github && <a href={github} target="_blank" rel="noreferrer" className="flex items-center gap-1 hover:text-slate-700 transition-colors"><Github className="h-3 w-3" />GitHub</a>}
                    </div>
                  </div>
                </div>
              </div>

              {/* AI Scores row */}
              <div className="flex items-center gap-6 p-4 rounded-2xl" style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                <Ring value={matchScore} label="Role Match" sub="Score" large />
                <div className="flex-1 grid grid-cols-2 gap-3">
                  <Ring value={expScore} label="Experience Depth" sub="Top 1% expertise" />
                  <Ring value={verifyScore} label="Verification" sub="GitHub verified" />
                </div>
              </div>

              {/* AI Persona */}
              <div>
                <p className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: C.accent }}>The Persona</p>
                <p className="text-sm text-slate-600 leading-relaxed">{bio}</p>
              </div>

              {/* Education */}
              {education.length > 0 && (
                <div>
                  <p className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: C.accent }}>Education</p>
                  <div className="space-y-2">
                    {education.map((edu, i) => (
                      <div key={i} className="flex items-start gap-3">
                        <GraduationCap className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-sm font-semibold text-slate-900">{edu.degree || edu}</p>
                          {edu.institution && <p className="text-xs text-slate-400">{edu.institution}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Work Experience */}
              {experience.length > 0 && (
                <div>
                  <p className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: C.accent }}>Experience</p>
                  <div className="space-y-3">
                    {experience.slice(0, 3).map((exp, i) => (
                      <div key={i} className="flex items-start gap-3">
                        <Briefcase className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-sm font-semibold text-slate-900">{exp.title || exp}</p>
                          {exp.company && <p className="text-xs text-slate-400">{exp.company} · {exp.duration || ''}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* RIGHT: AI insights + skills + github */}
            <div className="p-6 space-y-5 bg-slate-50">
              {/* GitHub Verification */}
              <div
                className="rounded-2xl p-4"
                style={{ background: `linear-gradient(135deg, ${C.primary} 0%, #312e81 60%, ${C.accent} 100%)` }}
              >
                <div className="flex items-center gap-2 mb-3">
                  <Github className="h-5 w-5 text-white" />
                  <p className="font-bold text-white text-sm">GitHub Verification</p>
                </div>
                <p className="text-xs leading-relaxed mb-3" style={{ color: '#c7d2fe' }}>
                  Verified commit history & open-source footprint analyzed across key repositories.
                </p>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider" style={{ color: '#818cf8' }}>Authenticity Score</span>
                  <span className="text-xl font-black text-white">{authScore}<span className="text-sm text-indigo-300">/10</span></span>
                </div>
              </div>

              {/* Top Skills */}
              <div className="bg-white rounded-2xl border border-slate-200 p-4">
                <div className="flex items-center justify-between mb-3">
                  <p className="font-semibold text-slate-900 text-sm">Top Skills</p>
                  <span className="text-xs text-slate-400">Last sync: 14 min ago</span>
                </div>
                {skills.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {skills.map((skill, i) => (
                      <SkillTag key={i} skill={typeof skill === 'string' ? skill : skill.name} level={skill.level} />
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">No skills data available.</p>
                )}
              </div>

              {/* AI Curation Insights */}
              <div className="bg-white rounded-2xl border border-slate-200 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Zap className="h-4 w-4" style={{ color: C.cyan }} />
                  <p className="font-semibold text-slate-900 text-sm">AI Curation Insights</p>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Role Match Score</span>
                    <span className="font-bold" style={{ color: C.accent }}>{matchScore}%</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Experience Depth</span>
                    <span className="font-bold" style={{ color: C.accent }}>{expScore}%</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Verification</span>
                    <span className="font-bold" style={{ color: C.cyan }}>{verifyScore}%</span>
                  </div>
                </div>
              </div>

              {/* Links */}
              {(github || linkedin) && (
                <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-2">
                  {github && (
                    <a href={github} target="_blank" rel="noreferrer"
                      className="flex items-center gap-2 text-sm font-semibold text-slate-700 hover:text-indigo-700 transition-colors">
                      <Github className="h-4 w-4" /> GitHub Profile <ExternalLink className="h-3.5 w-3.5 ml-auto" />
                    </a>
                  )}
                  {linkedin && (
                    <a href={linkedin} target="_blank" rel="noreferrer"
                      className="flex items-center gap-2 text-sm font-semibold text-slate-700 hover:text-indigo-700 transition-colors">
                      <ExternalLink className="h-4 w-4" /> LinkedIn <ExternalLink className="h-3.5 w-3.5 ml-auto" />
                    </a>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CandidateModal;