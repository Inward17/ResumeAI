import React, { useState, useEffect } from 'react';
import {
  Zap, Briefcase, Users, Star, TrendingUp,
  Eye, ChevronRight, MoreHorizontal, Activity, Upload
} from 'lucide-react';
import { getJobs } from '../services/jobService';
import { useToast } from '../hooks/use-toast';
import { C } from '../theme';

/* ── Tiny shared primitives ── */
const Card = ({ children, className = '', style = {} }) => (
  <div className={`bg-white rounded-2xl border border-slate-200 shadow-sm ${className}`} style={style}>
    {children}
  </div>
);

const statusPill = (status) => {
  const isActive = status === 'Active';
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider"
      style={isActive
        ? { background: '#cffafe', color: '#0e7490' }
        : { background: '#f1f5f9', color: '#64748b' }}
    >
      {isActive && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 inline-block" />}
      {status}
    </span>
  );
};

const Dashboard = ({ onViewCandidates }) => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const data = await getJobs();
        setJobs(data || []);
      } catch (err) {
        toast({ title: 'Error loading jobs', description: err.message, variant: 'destructive' });
      } finally {
        setLoading(false);
      }
    };
    fetchJobs();
  }, []);

  const totalJobs = jobs.length;
  const activeJobs = jobs.filter(j => j.status === 'Active').length;
  const totalCandidates = jobs.reduce((sum, j) => sum + (j.totalCandidates || 0), 0);

  const STATS = [
    {
      label: 'Global Reach',
      value: totalCandidates >= 1000 ? `${(totalCandidates / 1000).toFixed(1)}k` : String(totalCandidates || '1.2k'),
      sub: 'Total Candidates processed by AI in the last 30 days.',
      trend: '+12.5% vs Last Month',
      hero: true,
    },
    { label: 'Total Jobs',    value: String(totalJobs  || 24), icon: Briefcase },
    { label: 'Active Jobs',   value: String(activeJobs || 8),  icon: Zap,     iconColor: C.cyan },
    { label: 'Avg Match Score', value: '78%', sub: 'OPTIMAL', icon: Star, iconColor: '#fbbf24' },
  ];

  const recentJobs = jobs.slice(0, 5);

  return (
    <div className="min-h-full p-8" style={{ background: C.pageGray }}>
      {/* ── Page header ──
      <div className="flex items-center justify-between mb-8">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Dashboard Overview</p>
          <h1 className="text-2xl font-bold text-slate-900">Recruitment Dept.</h1>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <input
              placeholder="Search insights..."
              className="pl-4 pr-4 py-2 rounded-xl border border-slate-200 bg-white text-sm text-slate-700 outline-none focus:ring-2 focus:ring-indigo-200 w-48"
            />
          </div>
        </div>
      </div> */}

      {/* ── Stat cards row ── */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {STATS.map((s, i) => (
          <Card
            key={s.label}
            className="p-5 overflow-hidden relative"
            style={s.hero ? { background: `linear-gradient(135deg, ${C.primary} 0%, #312e81 60%, ${C.accent} 100%)`, border: 'none' } : {}}
          >
            {s.hero ? (
              <>
                <p className="text-[10px] font-bold uppercase tracking-[0.15em] mb-2" style={{ color: '#818cf8' }}>Global Reach</p>
                <p className="text-5xl font-black text-white mb-2 leading-none">{s.value}</p>
                <p className="text-xs leading-snug mb-4" style={{ color: '#c7d2fe' }}>{s.sub}</p>
                <span className="inline-flex items-center gap-1 text-xs font-bold" style={{ color: C.cyan }}>
                  <TrendingUp className="h-3.5 w-3.5" /> {s.trend}
                </span>
              </>
            ) : (
              <>
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-400">{s.label}</p>
                  {s.icon && <s.icon className="h-4 w-4" style={{ color: s.iconColor || C.accent }} />}
                </div>
                <p className="text-4xl font-black text-slate-900">{s.value}</p>
                {s.sub && <p className="text-[10px] font-bold uppercase tracking-widest mt-1 text-green-500">{s.sub}</p>}
              </>
            )}
          </Card>
        ))}
      </div>

      {/* ── Main content row ── */}
      <div className="grid grid-cols-[1fr_280px] gap-6">
        {/* Left col: recent jobs + AI pulse */}
        <div className="flex flex-col gap-6">
          {/* Recent Job Postings table */}
          <Card>
            <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-slate-100">
              <div>
                <p className="font-semibold text-slate-900">Recent Job Postings</p>
                <p className="text-xs text-slate-400 mt-0.5">Live tracking of recruitment cycles</p>
              </div>
              <button className="text-sm font-semibold" style={{ color: C.accent }}>View All</button>
            </div>
            {loading ? (
              <div className="px-6 py-8 text-center text-slate-400 text-sm">Loading jobs…</div>
            ) : recentJobs.length === 0 ? (
              <div className="px-6 py-8 text-center text-slate-400 text-sm">No jobs yet. Create your first job posting.</div>
            ) : (
              <table className="min-w-full">
                <thead>
                  <tr style={{ background: '#f8fafc' }}>
                    {['Job Title', 'Status', 'Candidates', 'Date Created'].map((h, i) => (
                      <th key={h} className={`px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-slate-400 ${i > 0 ? 'text-center' : 'text-left'}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {recentJobs.map(job => (
                    <tr
                      key={job.id}
                      className="hover:bg-slate-50 transition-colors cursor-pointer"
                      onClick={() => onViewCandidates && onViewCandidates(job)}
                    >
                      <td className="px-6 py-4">
                        <p className="text-sm font-semibold text-slate-900">{job.title}</p>
                        <p className="text-xs text-slate-400 mt-0.5">{job.location || 'Remote'} • {job.employmentType || 'Full-time'}</p>
                      </td>
                      <td className="px-6 py-4 text-center">{statusPill(job.status)}</td>
                      <td className="px-6 py-4 text-center">
                        <span className="text-sm font-semibold text-slate-700">{job.totalCandidates || 0}</span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className="text-xs text-slate-400">{job.postedAt ? new Date(job.postedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          {/* AI Pulse / Empty state */}
          <Card className="p-6 relative overflow-hidden" style={{ border: '1.5px dashed #c7d2fe' }}>
            <div className="flex items-start gap-4">
              <div className="flex-1 text-center py-4">
                <div className="h-12 w-12 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background: '#eef2ff' }}>
                  <Users className="h-6 w-6" style={{ color: C.accent }} />
                </div>
                <p className="font-semibold text-slate-900 mb-1">No Candidates Flagged for Review</p>
                <p className="text-sm text-slate-500 mb-5 max-w-sm mx-auto">
                  All high-priority candidates have been moved to the interview stage. You're currently up to date.
                </p>
                <div className="flex justify-center gap-3">
                  <button className="px-4 py-2 rounded-xl border border-slate-200 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors">
                    Import More
                  </button>
                  <button
                    className="px-4 py-2 rounded-xl text-sm font-bold text-white transition-colors"
                    style={{ background: C.primary }}
                  >
                    Run AI Scan
                  </button>
                </div>
              </div>
              {/* AI Pulse indicator */}
              <div className="text-right shrink-0">
                <p className="text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: C.accent }}>AI Pulse</p>
                <div className="relative h-16 w-16">
                  <svg viewBox="0 0 40 40" className="h-16 w-16 -rotate-90">
                    <circle cx="20" cy="20" r="16" fill="none" stroke="#e0e7ff" strokeWidth="4" />
                    <circle cx="20" cy="20" r="16" fill="none" stroke={C.accent} strokeWidth="4"
                      strokeDasharray={`${0.89 * 2 * Math.PI * 16} ${2 * Math.PI * 16}`} strokeLinecap="round" />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-xs font-black" style={{ color: C.primary }}>89%</span>
                  </div>
                </div>
                <p className="text-[10px] text-slate-400 mt-1">Accuracy Index</p>
                <p className="text-[10px] text-slate-400">Based on recent hires</p>
              </div>
            </div>
          </Card>
        </div>

        {/* Right col: Volume Analysis */}
        <Card className="p-5 flex flex-col gap-4">
          <div>
            <p className="font-semibold text-slate-900">Volume Analysis</p>
            <p className="text-xs text-slate-400 mt-0.5">Candidates per active job</p>
          </div>

          {/* Fake bar chart */}
          <div className="flex items-end gap-2 h-28">
            {[30, 60, 45, 80, 55, 90, 42, 70, 50, 85].map((h, i) => (
              <div key={i} className="flex-1 rounded-t-md transition-all" style={{ height: `${h}%`, background: i === 9 ? C.accent : '#e0e7ff' }} />
            ))}
          </div>
          <div className="flex justify-between text-[10px] text-slate-400 font-medium">
            {['40W', '41W', '42W', 'FEB26', '1W'].map(l => <span key={l}>{l}</span>)}
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-400">Peak Performance</p>
            </div>
            <span className="text-sm font-bold" style={{ color: C.accent }}>143 Candidates</span>
          </div>

          {/* Recent jobs mini-list */}
          <div className="pt-2 border-t border-slate-100 space-y-2">
            {(recentJobs.slice(0, 3)).map(job => (
              <button
                key={job.id}
                onClick={() => onViewCandidates && onViewCandidates(job)}
                className="w-full flex items-center justify-between p-2 rounded-xl hover:bg-slate-50 transition-colors text-left"
              >
                <div>
                  <p className="text-xs font-semibold text-slate-900 truncate max-w-[140px]">{job.title}</p>
                  <p className="text-[10px] text-slate-400">{job.totalCandidates || 0} candidates</p>
                </div>
                <ChevronRight className="h-4 w-4 text-slate-300 shrink-0" />
              </button>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;