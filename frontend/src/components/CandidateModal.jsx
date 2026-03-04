import React from 'react';
import { X, ExternalLink, CheckCircle, XCircle, AlertCircle, User, Mail, Phone, Github, Linkedin } from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Avatar, AvatarImage, AvatarFallback } from './ui/avatar';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Separator } from './ui/separator';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const CandidateModal = ({ candidate, job, onClose, onStatusUpdate }) => {
  if (!candidate) return null;

  // Derive AI recommendation from scores
  const overallScore = candidate.verificationScore || candidate.scoreDetails?.overall_score || 0;
  const getRecommendation = (score) => {
    if (score >= 80) return 'Strongly Recommended';
    if (score >= 60) return 'Recommended';
    return 'Not Recommended';
  };

  const recommendation = candidate.aiAnalysis?.recommendation || getRecommendation(overallScore);
  const reasoning = candidate.aiAnalysis?.reasoning ||
    (overallScore >= 80
      ? "This candidate demonstrates strong alignment with the job requirements based on verification scores."
      : overallScore >= 60
        ? "This candidate shows good potential with solid verification scores."
        : "This candidate may need additional review based on current verification scores.");

  const getRecommendationIcon = (rec) => {
    switch (rec) {
      case 'Strongly Recommended':
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case 'Recommended':
        return <AlertCircle className="h-5 w-5 text-amber-600" />;
      default:
        return <XCircle className="h-5 w-5 text-red-600" />;
    }
  };

  const getRecommendationBadgeClass = (rec) => {
    switch (rec) {
      case 'Strongly Recommended':
        return 'bg-green-100 text-green-800';
      case 'Recommended':
        return 'bg-amber-100 text-amber-800';
      default:
        return 'bg-red-100 text-red-800';
    }
  };

  // Use verification status from API or defaults
  const verification = candidate.verification || candidate.verificationStatus || {
    github: 'pending',
    linkedin: 'pending',
    webCheck: 'pending'
  };

  // Skill matches are computed once at upload time and stored in the DB.
  // candidate.skillMatches is set by CandidateDetails.jsx transform (from score_details.skill_matches).
  const skillMatches = candidate.skillMatches || candidate.skill_matches || [];

  const updateStatus = async (newStatus) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/jobs/${job.id}/candidates/${candidate.id || candidate.candidate_id}/status`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (!response.ok) {
        throw new Error('Failed to update status');
      }

      const result = await response.json();
      if (onStatusUpdate) {
        onStatusUpdate();
      }
      onClose();
    } catch (error) {
      console.error('Error updating status:', error);
      // Ideally show a toast notification here
    }
  };

  const getScoreColor = (score) => {
    if (score >= 8) return 'text-green-600';
    if (score >= 6) return 'text-amber-600';
    return 'text-red-600';
  };

  const isVerified = (status) => status === 'verified' || status === true;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b border-slate-200">
          <h2 className="text-2xl font-bold text-slate-900">Candidate Report</h2>
          <Button variant="ghost" onClick={onClose} className="hover:bg-slate-100">
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Content */}
        <div className="flex flex-col lg:flex-row max-h-[calc(90vh-8rem)] overflow-hidden">
          {/* Left Column */}
          <div className="lg:w-1/2 p-6 overflow-y-auto border-r border-slate-200">
            {/* Candidate Info */}
            <div className="flex items-center space-x-4 mb-6">
              <Avatar className="h-16 w-16">
                <AvatarImage src={candidate.avatar} alt={candidate.name} />
                <AvatarFallback>
                  <User className="h-8 w-8" />
                </AvatarFallback>
              </Avatar>
              <div className="flex-1">
                <h3 className="text-xl font-semibold text-slate-900">{candidate.name || 'Unknown'}</h3>
                <div className="flex items-center space-x-4 text-sm text-slate-600 mt-2">
                  {candidate.email && (
                    <div className="flex items-center space-x-1">
                      <Mail className="h-4 w-4" />
                      <span>{candidate.email}</span>
                    </div>
                  )}
                  {candidate.phone && (
                    <div className="flex items-center space-x-1">
                      <Phone className="h-4 w-4" />
                      <span>{candidate.phone}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Profile Links */}
            <div className="flex space-x-3 mb-6">
              {candidate.linkedin && (
                <Button
                  variant="outline"
                  size="sm"
                  className="flex items-center space-x-2 border-blue-200 text-blue-700 hover:bg-blue-50"
                  onClick={() => window.open(candidate.linkedin, '_blank')}
                >
                  <Linkedin className="h-4 w-4" />
                  <span>LinkedIn</span>
                  <ExternalLink className="h-3 w-3" />
                </Button>
              )}
              {candidate.github && (
                <Button
                  variant="outline"
                  size="sm"
                  className="flex items-center space-x-2 border-slate-200 text-slate-700 hover:bg-slate-50"
                  onClick={() => window.open(candidate.github, '_blank')}
                >
                  <Github className="h-4 w-4" />
                  <span>GitHub</span>
                  <ExternalLink className="h-3 w-3" />
                </Button>
              )}
            </div>

            {/* AI Analysis */}
            <Card className="mb-6">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <span>AI Analysis</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <div className="flex items-center space-x-2 mb-2">
                    {getRecommendationIcon(recommendation)}
                    <Badge className={getRecommendationBadgeClass(recommendation)}>
                      {recommendation}
                    </Badge>
                  </div>
                </div>

                <div>
                  <h4 className="font-medium text-slate-900 mb-2">Reasoning</h4>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    {reasoning}
                  </p>
                </div>

                {/* Score Details */}
                {candidate.scoreDetails && (
                  <div className="mt-4 pt-4 border-t border-slate-100">
                    <h4 className="font-medium text-slate-900 mb-2">Score Breakdown</h4>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>Overall: <span className="font-semibold">{candidate.scoreDetails.overall_score}%</span></div>
                      <div>GitHub Score: <span className="font-semibold">{candidate.scoreDetails.skills_match_score}%</span></div>
                      <div>Experience: <span className="font-semibold">{candidate.scoreDetails.experience_match_score}%</span></div>
                      <div>Verification Bonus: <span className="font-semibold">+{candidate.scoreDetails.verification_bonus}</span></div>
                      {candidate.scoreDetails.jd_match_score !== undefined && (
                        <div className="col-span-2">JD Match: <span className="font-semibold">{candidate.scoreDetails.jd_match_score?.toFixed(1)}/10</span></div>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Action Buttons */}
            <div className="flex space-x-3">
              <Button
                onClick={() => updateStatus('Shortlisted')}
                className="flex-1 bg-green-600 hover:bg-green-700 transition-colors duration-200"
              >
                Shortlist
              </Button>
              <Button
                variant="outline"
                onClick={() => updateStatus('Rejected')}
                className="flex-1 border-red-200 text-red-700 hover:bg-red-50"
              >
                Reject
              </Button>
              <Button
                variant="outline"
                onClick={() => updateStatus('On Hold')}
                className="flex-1 border-amber-200 text-amber-700 hover:bg-amber-50"
              >
                Keep on Hold
              </Button>
            </div>
          </div>

          {/* Right Column */}
          <div className="lg:w-1/2 p-6 overflow-y-auto">
            {/* JD Match Breakdown */}
            <Card className="mb-6">
              <CardHeader>
                <CardTitle>JD Match Breakdown</CardTitle>
              </CardHeader>
              <CardContent>

                {/* ── Unified JD score header ── */}
                <div className="flex justify-between items-center mb-1">
                  <div>
                    <span className="text-sm font-semibold text-slate-900">Unified JD Score</span>
                    <p className="text-xs text-slate-400 mt-0.5">Evidence-weighted across skills, experience, projects &amp; GitHub</p>
                  </div>
                  <span className={`text-2xl font-bold ${candidate.scoreDetails?.jd_match_score >= 7 ? 'text-green-600' :
                      candidate.scoreDetails?.jd_match_score >= 4 ? 'text-amber-600' : 'text-red-500'
                    }`}>
                    {candidate.scoreDetails?.jd_match_score != null
                      ? candidate.scoreDetails.jd_match_score.toFixed(1)
                      : '—'}
                    <span className="text-sm font-normal text-slate-400">/10</span>
                  </span>
                </div>

                {/* ── Overall score bar ── */}
                {candidate.scoreDetails?.jd_match_score != null && (
                  <div className="w-full bg-slate-100 rounded-full h-1.5 mb-5">
                    <div
                      className={`h-1.5 rounded-full transition-all ${candidate.scoreDetails.jd_match_score >= 7 ? 'bg-green-500' :
                          candidate.scoreDetails.jd_match_score >= 4 ? 'bg-amber-500' : 'bg-red-500'
                        }`}
                      style={{ width: `${(candidate.scoreDetails.jd_match_score / 10) * 100}%` }}
                    />
                  </div>
                )}

                {/* ── Per-skill evidence breakdown ── */}
                {skillMatches.length > 0 ? (
                  <div className="space-y-4 border-t border-slate-100 pt-4">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Required Skills</p>
                    {skillMatches.map((skill, index) => {
                      const ev = skill.evidence || {};
                      const evidenceSources = [
                        { key: 'github', label: 'GitHub' },
                        { key: 'experience', label: 'Exp' },
                        { key: 'projects', label: 'Projects' },
                        { key: 'skills', label: 'Skills' },
                      ];
                      return (
                        <div key={index} className="space-y-1.5">
                          {/* Skill name + score */}
                          <div className="flex justify-between items-center">
                            <div className="flex items-center space-x-2">
                              <span className="text-sm font-medium text-slate-900">{skill.skill}</span>
                              {skill.canonical && skill.canonical !== skill.skill.toLowerCase() && (
                                <span className="text-xs text-slate-400 italic">({skill.canonical})</span>
                              )}
                            </div>
                            <div className="flex items-center space-x-2">
                              <span className={`text-sm font-bold ${getScoreColor(skill.score)}`}>
                                {typeof skill.score === 'number' ? skill.score.toFixed(1) : '—'}/10
                              </span>
                              {skill.found
                                ? <CheckCircle className="h-4 w-4 text-green-600" />
                                : <XCircle className="h-4 w-4 text-red-400" />}
                            </div>
                          </div>
                          {/* Mini score bar */}
                          <div className="w-full bg-slate-100 rounded-full h-1">
                            <div
                              className={`h-1 rounded-full transition-all ${skill.score >= 7 ? 'bg-green-500' :
                                  skill.score >= 4 ? 'bg-amber-500' : 'bg-red-400'
                                }`}
                              style={{ width: `${Math.min((skill.score / 10) * 100, 100)}%` }}
                            />
                          </div>
                          {/* Evidence source indicators */}
                          {Object.keys(ev).length > 0 && (
                            <div className="flex items-center space-x-3 pl-0.5">
                              {evidenceSources.map(({ key, label }) => {
                                const sim = ev[key];
                                if (sim === undefined) return null;
                                const strong = sim >= 0.55;
                                const partial = sim >= 0.40;
                                return (
                                  <span
                                    key={key}
                                    className={`text-xs flex items-center space-x-0.5 ${strong ? 'text-green-600' : partial ? 'text-amber-500' : 'text-slate-300'
                                      }`}
                                    title={`${label}: ${(sim * 100).toFixed(0)}% similarity`}
                                  >
                                    <span>{strong ? '✓' : partial ? '~' : '✗'}</span>
                                    <span>{label}</span>
                                  </span>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-slate-400 border-t border-slate-100 pt-4">
                    Skill scores not yet available. Re-upload this resume to generate evidence scores.
                  </p>
                )}
              </CardContent>
            </Card>


            {/* Profile Verification */}
            <Card>
              <CardHeader>
                <CardTitle>Profile Verification</CardTitle>
                <p className="text-sm text-slate-600">Verification status across sources</p>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium text-slate-900">GitHub</span>
                    {isVerified(verification.github) ? (
                      <div className="flex items-center space-x-2">
                        <span className="text-sm text-green-600">Verified</span>
                        <CheckCircle className="h-4 w-4 text-green-600" />
                      </div>
                    ) : (
                      <div className="flex items-center space-x-2">
                        <span className="text-sm text-slate-500">{verification.github || 'Pending'}</span>
                        <AlertCircle className="h-4 w-4 text-amber-600" />
                      </div>
                    )}
                  </div>

                  <Separator />

                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium text-slate-900">LinkedIn</span>
                    {isVerified(verification.linkedin) ? (
                      <div className="flex items-center space-x-2">
                        <span className="text-sm text-green-600">Verified</span>
                        <CheckCircle className="h-4 w-4 text-green-600" />
                      </div>
                    ) : (
                      <div className="flex items-center space-x-2">
                        <span className="text-sm text-slate-500">{verification.linkedin || 'Pending'}</span>
                        <AlertCircle className="h-4 w-4 text-amber-600" />
                      </div>
                    )}
                  </div>

                  <Separator />

                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium text-slate-900">Web Check</span>
                    {isVerified(verification.webCheck) ? (
                      <div className="flex items-center space-x-2">
                        <span className="text-sm text-green-600">Verified</span>
                        <CheckCircle className="h-4 w-4 text-green-600" />
                      </div>
                    ) : (
                      <div className="flex items-center space-x-2">
                        <span className="text-sm text-slate-500">{verification.webCheck || 'Pending'}</span>
                        <AlertCircle className="h-4 w-4 text-amber-600" />
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CandidateModal;