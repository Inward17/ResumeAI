import React, { useState, useEffect, useRef } from 'react';
import {
  ArrowLeft, Upload, X, Zap, Clock, Users,
  Star, CheckCircle, Github, MapPin, ChevronRight,
  FileText, TrendingUp, BarChart2, Calendar
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import CandidateModal from './CandidateModal';
import { getJobCandidates, uploadResumes, updateCandidateStatus } from '../services/jobService';
import { C } from '../theme';

/* ── Score ring ── */
const ScoreRing = ({ value, label, size = 52 }) => {
  const r = 18;
  const circ = 2 * Math.PI * r;
  const dash = (value / 100) * circ;
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg viewBox="0 0 40 40" width={size} height={size} className="-rotate-90">
          <circle cx="20" cy="20" r={r} fill="none" stroke="#e0e7ff" strokeWidth="4" />
          <circle cx="20" cy="20" r={r} fill="none" stroke={C.accent} strokeWidth="4"
            strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[11px] font-black" style={{ color: C.primary }}>{value}%</span>
        </div>
      </div>
      <span className="text-[10px] text-slate-400 font-semibold text-center leading-tight">{label}</span>
    </div>
  );
};

/* ── Status pill ── */
const StatusPill = ({ status }) => {
  const map = {
    'Interview':   { bg: '#d1fae5', text: '#065f46' },
    'interview':   { bg: '#d1fae5', text: '#065f46' },
    'Shortlisted': { bg: '#e0e7ff', text: '#3730a3' },
    'shortlisted': { bg: '#e0e7ff', text: '#3730a3' },
    'Under Review':{ bg: '#fef3c7', text: '#92400e' },
    'Rejected':    { bg: '#fee2e2', text: '#991b1b' },
  };
  const s = map[status] || { bg: '#f1f5f9', text: '#475569' };
  return (
    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full"
      style={{ background: s.bg, color: s.text }}>
      {status || 'Review'}
    </span>
  );
};

/* ── Candidate list row ── */
const CandidateRow = ({ candidate, onClick, onMoveToInterview }) => {
  const match = Math.round(candidate.jdMatchScore ?? candidate.matchScore ?? 0);
  const verified = candidate.verificationScore ?? 0;
  const isInterview = ['Interview', 'interview', 'Shortlisted', 'shortlisted'].includes(candidate.status);
  return (
    <div className="flex items-center justify-between px-5 py-4 hover:bg-indigo-50/60 transition-colors border-b border-slate-100 last:border-0 group">
      {/* Left: avatar + name — clicking opens dossier */}
      <button onClick={() => onClick(candidate)} className="flex items-center gap-3 flex-1 text-left min-w-0">
        <div className="h-9 w-9 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0"
          style={{ background: C.primary }}>
          {(candidate.name || '?').charAt(0).toUpperCase()}
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-900 truncate">{candidate.name || 'Unknown'}</p>
          <p className="text-xs text-slate-400 truncate">{candidate.email || '—'}</p>
        </div>
      </button>

      {/* Right: score + status + action */}
      <div className="flex items-center gap-3 shrink-0">
        <span
          className="text-xs font-bold px-2.5 py-0.5 rounded-full"
          style={match >= 80
            ? { background: '#cffafe', color: '#0e7490' }
            : match >= 60
            ? { background: '#ede9fe', color: '#5b21b6' }
            : { background: '#fef3c7', color: '#92400e' }}
        >
          {match}% match
        </span>
        <StatusPill status={candidate.status} />
        {!isInterview && (
          <button
            onClick={() => onMoveToInterview(candidate.id)}
            title="Move to Interview"
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold opacity-0 group-hover:opacity-100 transition-opacity"
            style={{ background: '#d1fae5', color: '#065f46' }}
          >
            <Calendar className="h-3 w-3" /> Interview
          </button>
        )}
        {verified >= 80 && (
          <CheckCircle className="h-4 w-4 shrink-0" style={{ color: C.cyan }} />
        )}
        <ChevronRight className="h-4 w-4 text-slate-300 shrink-0" />
      </div>
    </div>
  );
};

/* ── Main Component ── */
const CandidatePipeline = ({ job, onBack }) => {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null); // {processed, total}
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);
  const { toast } = useToast();

  const fetchCandidates = async () => {
    try {
      setLoading(true);
      const data = await getJobCandidates(job.id);
      setCandidates(data || []);
    } catch (err) {
      // Silently fail — backend not running is OK for demo
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchCandidates(); }, [job.id]);

  const uploadFiles = async (files) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadProgress({ processed: 0, total: files.length });
    try {
      await uploadResumes(job.id, files);
      setUploadProgress({ processed: files.length, total: files.length });
      toast({ title: 'Resumes uploaded', description: `${files.length} resume(s) processed by AI.` });
      setTimeout(() => {
        setUploading(false);
        setUploadProgress(null);
        fetchCandidates();
      }, 1500);
    } catch (err) {
      toast({ title: 'Upload error', description: err.message, variant: 'destructive' });
      setUploading(false);
      setUploadProgress(null);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    uploadFiles(e.dataTransfer.files);
  };

  const handleStatusUpdate = async (candidateId, status) => {
    try {
      await updateCandidateStatus(job.id, candidateId, status);
      setCandidates(prev => prev.map(c => c.id === candidateId ? { ...c, status } : c));
      toast({ title: 'Status updated' });
    } catch (err) {
      toast({ title: 'Error updating status', variant: 'destructive' });
    }
  };

  const topMatch = candidates.length > 0
    ? Math.max(...candidates.map(c => c.jdMatchScore ?? c.matchScore ?? 0))
    : 0;

  return (
    <div className="min-h-full p-8" style={{ background: C.pageGray }}>
      {/* ── Back + header ── */}
      <div className="mb-6">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-slate-700 transition-colors mb-4"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Postings
        </button>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-black text-slate-900">{job.title}</h1>
            <div className="flex items-center gap-4 text-xs text-slate-400 mt-1">
              {job.location && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{job.location}</span>}
              {job.employmentType && <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{job.employmentType}</span>}
              <span className="flex items-center gap-1"><Users className="h-3 w-3" />{candidates.length} Active Candidates</span>
            </div>
          </div>
          {/* Pipeline velocity */}
          <div className="text-right">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Pipeline Velocity</p>
            <p className="text-2xl font-black" style={{ color: C.primary }}>4.2 <span className="text-base font-semibold">Days</span></p>
            <p className="text-xs text-slate-400">Average time to AI verification</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
        {/* Left: Upload + Candidate list */}
        <div className="flex flex-col gap-5">
          {/* Upload zone */}
          <div
            className="rounded-2xl border-2 border-dashed p-6 flex flex-col items-center gap-3 text-center transition-colors"
            style={{
              borderColor: dragOver ? C.accent : '#c7d2fe',
              background: dragOver ? '#eef2ff' : 'white',
            }}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.doc"
              className="hidden"
              onChange={e => uploadFiles(e.target.files)}
            />
            <div className="h-12 w-12 rounded-2xl flex items-center justify-center" style={{ background: '#eef2ff' }}>
              <Upload className="h-6 w-6" style={{ color: C.accent }} />
            </div>
            <div>
              <p className="font-bold text-slate-900">Upload Resumes</p>
              <p className="text-sm text-slate-400 mt-0.5">
                Drag and drop PDF/DOCX files here. Our AI will automatically parse skills and experience.
              </p>
            </div>
            <button
              className="px-5 py-2 rounded-xl text-sm font-bold text-white mt-1"
              style={{ background: C.primary }}
              onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
            >
              Choose Files
            </button>

            {/* Upload progress overlay */}
            {uploading && uploadProgress && (
              <div className="w-full mt-2">
                <div className="flex justify-between text-xs mb-1 text-slate-500">
                  <span>Processing… {uploadProgress.processed}/{uploadProgress.total}</span>
                  <span>{Math.round((uploadProgress.processed / uploadProgress.total) * 100)}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-slate-200 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${(uploadProgress.processed / uploadProgress.total) * 100}%`, background: C.accent }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Candidate list */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <p className="font-semibold text-slate-900">Candidate Analysis</p>
              <span className="text-xs text-slate-400">{candidates.length} candidates</span>
            </div>
            {loading ? (
              <div className="px-5 py-8 text-center text-slate-400 text-sm">Loading candidates…</div>
            ) : candidates.length === 0 ? (
              <div className="px-5 py-10 text-center">
                <FileText className="h-8 w-8 text-slate-300 mx-auto mb-2" />
                <p className="text-slate-400 text-sm">No candidates yet. Upload resumes above to get started.</p>
              </div>
            ) : (
              <div>
                {candidates.map(c => (
                  <CandidateRow
                    key={c.id}
                    candidate={c}
                    onClick={setSelectedCandidate}
                    onMoveToInterview={(candidateId) => handleStatusUpdate(candidateId, 'Interview')}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: live analysis + stats */}
        <div className="flex flex-col gap-5">
          {/* Live Analysis card */}
          <div
            className="rounded-2xl p-5"
            style={{ background: `linear-gradient(135deg, ${C.primary} 0%, #312e81 60%, ${C.accent} 100%)` }}
          >
            <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: '#818cf8' }}>Live Analysis</p>
            <div className="flex items-center gap-4 mb-4">
              <div>
                <p className="text-xs text-indigo-300 font-semibold">Top Match</p>
                <p className="text-3xl font-black text-white">{topMatch}%</p>
              </div>
              <div className="w-px h-10 bg-indigo-700" />
              <div>
                <p className="text-xs text-indigo-300 font-semibold">Remaining</p>
                <p className="text-3xl font-black text-white">{String(Math.max(0, 5 - candidates.length)).padStart(2, '0')}</p>
              </div>
            </div>
            {uploading ? (
              <div>
                <div className="flex justify-between text-xs text-indigo-300 mb-1.5">
                  <span>AI Processing</span>
                  <span>{uploadProgress ? Math.round((uploadProgress.processed / uploadProgress.total) * 100) : 0}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-indigo-800 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${uploadProgress ? (uploadProgress.processed / uploadProgress.total) * 100 : 0}%`, background: C.cyan }}
                  />
                </div>
              </div>
            ) : (
              <p className="text-xs leading-relaxed" style={{ color: '#c7d2fe' }}>
                AI analysis complete. {candidates.length > 0 ? `${candidates.filter(c => (c.jdMatchScore ?? 0) >= 80).length} candidates meet the 80% threshold.` : 'Upload resumes to begin analysis.'}
              </p>
            )}
          </div>

          {/* Score breakdown */}
          {candidates.length > 0 && (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
              <p className="font-semibold text-slate-900 mb-4">Score Breakdown</p>
              <div className="grid grid-cols-3 gap-2">
                <ScoreRing value={topMatch} label="Top Match" />
                <ScoreRing
                  value={Math.round(candidates.reduce((s, c) => s + (c.jdMatchScore ?? 0), 0) / (candidates.length || 1))}
                  label="Avg Match"
                />
                <ScoreRing
                  value={Math.round(candidates.reduce((s, c) => s + (c.verificationScore ?? 0), 0) / (candidates.length || 1))}
                  label="Avg Verify"
                />
              </div>
            </div>
          )}

          {/* Job description preview */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
            <p className="font-semibold text-slate-900 mb-2">Job Overview</p>
            <p className="text-xs text-slate-500 leading-relaxed line-clamp-6">{job.description || 'No description provided.'}</p>
            {job.requirements?.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-3">
                {job.requirements.slice(0, 6).map(skill => (
                  <span key={skill} className="text-[11px] px-2 py-0.5 rounded-full font-medium"
                    style={{ background: '#eef2ff', color: C.accent }}>{skill}</span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Candidate Dossier Modal */}
      {selectedCandidate && (
        <CandidateModal
          candidate={selectedCandidate}
          job={job}
          onClose={() => setSelectedCandidate(null)}
          onStatusUpdate={handleStatusUpdate}
        />
      )}
    </div>
  );
};

export default CandidatePipeline;
