import React, { useState, useEffect, useMemo } from 'react';
import { ArrowLeft, Search, MoreHorizontal, User, CheckCircle, XCircle, Clock, Loader2 } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Avatar, AvatarImage, AvatarFallback } from './ui/avatar';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const CandidateDetails = ({ job, onBack, onViewCandidate }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch candidates from API
  useEffect(() => {
    const fetchCandidates = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch(`${API_BASE_URL}/api/v1/jobs/${job.id}/candidates`);

        if (!response.ok) {
          throw new Error('Failed to fetch candidates');
        }

        const data = await response.json();

        // Transform API response to component format
        const transformedCandidates = data.candidates.map(candidate => ({
          id: candidate.candidate_id,
          name: candidate.name || 'Unknown',
          email: candidate.email || '',
          phone: candidate.phone || '',
          jdMatchScore: candidate.jd_match_score || candidate.score_details?.skills_match_score || 0,
          verificationScore: candidate.verification_score || candidate.score_details?.overall_score || 0,
          status: candidate.status || 'Under Review',
          applicationDate: candidate.application_date,
          scoreDetails: candidate.score_details || {},
          verificationStatus: candidate.verification_status
        }));

        setCandidates(transformedCandidates);
      } catch (err) {
        console.error('Error fetching candidates:', err);
        setError('Failed to load candidates');
      } finally {
        setLoading(false);
      }
    };

    fetchCandidates();
  }, [job.id]);

  const filteredCandidates = useMemo(() => {
    return candidates.filter(candidate => {
      const matchesSearch = candidate.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        candidate.email.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesStatus = statusFilter === 'All' || candidate.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [candidates, searchQuery, statusFilter]);

  const getProgressColor = (score) => {
    if (score >= 80) return 'bg-green-500';
    if (score >= 60) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'Shortlisted':
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case 'Rejected':
        return <XCircle className="h-4 w-4 text-red-600" />;
      default:
        return <Clock className="h-4 w-4 text-amber-600" />;
    }
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'Shortlisted':
        return 'bg-green-100 text-green-800 hover:bg-green-200';
      case 'Rejected':
        return 'bg-red-100 text-red-800 hover:bg-red-200';
      default:
        return 'bg-amber-100 text-amber-800 hover:bg-amber-200';
    }
  };

  const statusCounts = useMemo(() => {
    const counts = candidates.reduce((acc, candidate) => {
      acc[candidate.status] = (acc[candidate.status] || 0) + 1;
      return acc;
    }, {});
    counts.All = candidates.length;
    return counts;
  }, [candidates]);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto" />
          <p className="mt-2 text-slate-500">Loading candidates...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6">
        <Button
          variant="ghost"
          onClick={onBack}
          className="mb-4 text-slate-600 hover:text-slate-900 transition-colors duration-200"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Job Postings
        </Button>

        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Candidates for {job.title}</h1>
            <p className="text-slate-600 mt-1">{filteredCandidates.length} of {candidates.length} candidates</p>
          </div>

          {/* Search Bar */}
          <div className="relative w-full sm:w-96">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 h-4 w-4" />
            <Input
              placeholder="Search candidates..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 border-slate-300 focus:border-blue-500 transition-colors duration-200"
            />
          </div>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="text-center py-8 text-red-600">
          <p>{error}</p>
          <Button variant="outline" className="mt-2" onClick={() => window.location.reload()}>
            Retry
          </Button>
        </div>
      )}

      {/* Filter Buttons */}
      <div className="flex flex-wrap gap-2 mb-6">
        {['All', 'Shortlisted', 'Rejected', 'Under Review'].map((status) => (
          <Button
            key={status}
            variant={statusFilter === status ? "default" : "outline"}
            onClick={() => setStatusFilter(status)}
            className={`transition-all duration-200 ${statusFilter === status
                ? 'bg-blue-600 hover:bg-blue-700'
                : 'border-slate-300 text-slate-700 hover:bg-slate-50'
              }`}
          >
            {status} ({statusCounts[status] || 0})
          </Button>
        ))}
      </div>

      {/* Candidates Table */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
        <Table>
          <TableHeader>
            <TableRow className="border-slate-200">
              <TableHead className="font-semibold text-slate-900">Candidate</TableHead>
              <TableHead className="font-semibold text-slate-900">Skills Match</TableHead>
              <TableHead className="font-semibold text-slate-900">Overall Score</TableHead>
              <TableHead className="font-semibold text-slate-900">Status</TableHead>
              <TableHead className="font-semibold text-slate-900 text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredCandidates.map((candidate) => (
              <TableRow
                key={candidate.id}
                className="border-slate-200 hover:bg-slate-50 transition-colors duration-200"
              >
                <TableCell>
                  <div className="flex items-center space-x-3">
                    <Avatar className="h-10 w-10">
                      <AvatarFallback>
                        <User className="h-5 w-5" />
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <p className="font-medium text-slate-900">{candidate.name}</p>
                      <p className="text-sm text-slate-500">{candidate.email}</p>
                    </div>
                  </div>
                </TableCell>

                <TableCell>
                  <div className="flex items-center space-x-2">
                    <div className="w-24 bg-slate-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all duration-300 ${getProgressColor(candidate.jdMatchScore)}`}
                        style={{ width: `${Math.min(candidate.jdMatchScore, 100)}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium text-slate-900 min-w-[3rem]">
                      {candidate.jdMatchScore}%
                    </span>
                  </div>
                </TableCell>

                <TableCell>
                  <div className="flex items-center space-x-2">
                    <div className="w-24 bg-slate-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all duration-300 ${getProgressColor(candidate.verificationScore)}`}
                        style={{ width: `${Math.min(candidate.verificationScore, 100)}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium text-slate-900 min-w-[3rem]">
                      {candidate.verificationScore}%
                    </span>
                  </div>
                </TableCell>

                <TableCell>
                  <Badge className={`${getStatusBadgeClass(candidate.status)} transition-colors duration-200`}>
                    <div className="flex items-center space-x-1">
                      {getStatusIcon(candidate.status)}
                      <span>{candidate.status}</span>
                    </div>
                  </Badge>
                </TableCell>

                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onViewCandidate(candidate)}
                    className="text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-all duration-200"
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        {filteredCandidates.length === 0 && !loading && (
          <div className="text-center py-12">
            <User className="h-16 w-16 text-slate-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-900 mb-2">No candidates found</h3>
            <p className="text-slate-500">
              {candidates.length === 0
                ? "No resumes have been uploaded for this job yet"
                : "Try adjusting your search or filter criteria"}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default CandidateDetails;