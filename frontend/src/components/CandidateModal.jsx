import React, { useState } from 'react';
import { ArrowRight, CalendarPlus } from 'lucide-react';
import Modal from './Modal';
import { CANDIDATE_STATUSES } from '../lib/statuses';
import { DEFAULT_PREFERENCES } from '../lib/preferences';
import { Button, Select } from './common';
import CandidateDossier from './CandidateDossier';
import { ScheduleDialog } from './Scheduling';

const CandidateModal = ({ open, candidate, job, prefs = DEFAULT_PREFERENCES, onClose, onStatusUpdate, onTakeInterview, onScheduled }) => {
  const [scheduling, setScheduling] = useState(false);
  if (!candidate) return null;

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
          <div className="flex flex-wrap items-center gap-3">
            {job && (
              <Button variant="secondary" onClick={() => setScheduling(true)}>
                <CalendarPlus aria-hidden="true" /> Schedule interview
              </Button>
            )}
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
        </div>
      )}
    >
      {/* Radix unmounts the content while closed, so the dossier only fetches while open */}
      <CandidateDossier candidate={candidate} job={job} prefs={prefs} />
      {job && (
        <ScheduleDialog open={scheduling} onOpenChange={setScheduling} job={job} candidate={candidate}
          onDone={(r) => { if (r.candidateStatus) onStatusUpdate?.(candidate.id, r.candidateStatus); onScheduled?.(); }} />
      )}
    </Modal>
  );
};

export default CandidateModal;
