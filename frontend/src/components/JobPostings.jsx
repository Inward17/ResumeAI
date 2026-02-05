import React, { useState, useEffect } from 'react';
import { Plus, Users, CheckCircle, Clock, Eye, Edit, Loader2, AlertCircle } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import JobModal from './JobModal';
import { getJobs, createJob, updateJob, transformJobFromAPI, transformJobToAPI } from '../services/jobService';
import { useToast } from '../hooks/use-toast';

const JobPostings = ({ onViewCandidates }) => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingJob, setEditingJob] = useState(null);
  const { toast } = useToast();

  // Fetch jobs on mount
  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getJobs();
      const transformedJobs = data.map(transformJobFromAPI);
      setJobs(transformedJobs);
    } catch (err) {
      setError('Failed to load jobs. Please try again.');
      console.error('Error fetching jobs:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadgeVariant = (status) => {
    return status === 'Active' ? 'default' : 'secondary';
  };

  const handleAddNewJob = () => {
    setEditingJob(null);
    setIsModalOpen(true);
  };

  const handleEditJob = (job) => {
    setEditingJob(job);
    setIsModalOpen(true);
  };

  const handleSaveJob = async (jobData) => {
    try {
      const apiData = transformJobToAPI(jobData);

      if (editingJob) {
        // Update existing job
        const updated = await updateJob(editingJob.id, apiData);
        const transformedJob = transformJobFromAPI(updated);
        setJobs(prev => prev.map(job =>
          job.id === editingJob.id ? transformedJob : job
        ));
        toast({
          title: "Job updated successfully",
          description: `${jobData.title} has been updated.`
        });
      } else {
        // Create new job
        const created = await createJob(apiData);
        const transformedJob = transformJobFromAPI(created);
        setJobs(prev => [transformedJob, ...prev]);
        toast({
          title: "Job created successfully",
          description: `${jobData.title} has been created.`
        });
      }

      setIsModalOpen(false);
      setEditingJob(null);
    } catch (err) {
      toast({
        title: "Error saving job",
        description: err.message,
        variant: "destructive"
      });
    }
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingJob(null);
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto" />
          <p className="mt-2 text-slate-500">Loading jobs...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="p-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Job Postings</h1>
            <p className="text-slate-600 mt-1">Manage your active job positions and candidates</p>
          </div>
          <Button
            onClick={handleAddNewJob}
            className="bg-blue-600 hover:bg-blue-700 transition-colors duration-200"
          >
            <Plus className="mr-2 h-4 w-4" />
            Add New Job
          </Button>
        </div>

        {/* Error State */}
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="flex items-center justify-between">
              <span>{error}</span>
              <Button variant="outline" size="sm" onClick={fetchJobs}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Job Postings Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {jobs.map((job) => (
            <Card key={job.id} className="hover:shadow-lg transition-all duration-300 border-slate-200 hover:border-blue-200 relative group">
              <CardHeader className="pb-4">
                <div className="flex justify-between items-start">
                  <CardTitle className="text-lg font-semibold text-slate-900 line-clamp-2 flex-1 pr-2">
                    {job.title}
                  </CardTitle>
                  <div className="flex items-center space-x-2">
                    <Badge
                      variant={getStatusBadgeVariant(job.status)}
                      className={`${job.status === 'Active'
                        ? 'bg-green-100 text-green-800 hover:bg-green-200'
                        : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
                        } transition-colors duration-200`}
                    >
                      {job.status}
                    </Badge>
                    {/* Edit button - appears on hover */}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleEditJob(job);
                      }}
                      className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 text-slate-600 hover:text-slate-900 hover:bg-slate-100 p-1 h-8 w-8"
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                {/* Additional job info */}
                <div className="text-sm text-slate-600 space-y-1">
                  {job.experienceLevel && (
                    <p>Experience: {job.experienceLevel}</p>
                  )}
                  {job.location && (
                    <p>Location: {job.location}</p>
                  )}
                  {job.employmentType && (
                    <p>Type: {job.employmentType}</p>
                  )}
                </div>
              </CardHeader>

              <CardContent className="space-y-4">
                {/* Skills preview */}
                {job.requirements && job.requirements.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-slate-700 mb-2">Key Skills:</p>
                    <div className="flex flex-wrap gap-1">
                      {job.requirements.slice(0, 3).map((skill, index) => (
                        <Badge key={index} variant="outline" className="text-xs border-slate-300 text-slate-600">
                          {skill}
                        </Badge>
                      ))}
                      {job.requirements.length > 3 && (
                        <Badge variant="outline" className="text-xs border-slate-300 text-slate-600">
                          +{job.requirements.length - 3} more
                        </Badge>
                      )}
                    </div>
                  </div>
                )}

                {/* Metrics */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center">
                    <div className="flex items-center justify-center mb-1">
                      <Users className="h-4 w-4 text-blue-600 mr-1" />
                    </div>
                    <p className="text-2xl font-bold text-slate-900">{job.totalCandidates}</p>
                    <p className="text-xs text-slate-500">Candidates</p>
                  </div>

                  <div className="text-center">
                    <div className="flex items-center justify-center mb-1">
                      <CheckCircle className="h-4 w-4 text-green-600 mr-1" />
                    </div>
                    <p className="text-2xl font-bold text-slate-900">{job.screened}</p>
                    <p className="text-xs text-slate-500">Screened</p>
                  </div>

                  <div className="text-center">
                    <div className="flex items-center justify-center mb-1">
                      <Clock className="h-4 w-4 text-amber-600 mr-1" />
                    </div>
                    <p className="text-2xl font-bold text-slate-900">{job.shortlisted}</p>
                    <p className="text-xs text-slate-500">Shortlisted</p>
                  </div>
                </div>

                {/* Action Button */}
                <Button
                  variant="outline"
                  className="w-full border-blue-200 text-blue-700 hover:bg-blue-50 hover:border-blue-300 transition-all duration-200"
                  onClick={() => onViewCandidates(job)}
                >
                  <Eye className="mr-2 h-4 w-4" />
                  View Candidates
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Empty State */}
        {!loading && jobs.length === 0 && (
          <div className="text-center py-12">
            <Users className="h-16 w-16 text-slate-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-900 mb-2">No job postings yet</h3>
            <p className="text-slate-500 mb-6">Get started by creating your first job posting</p>
            <Button onClick={handleAddNewJob} className="bg-blue-600 hover:bg-blue-700">
              <Plus className="mr-2 h-4 w-4" />
              Add New Job
            </Button>
          </div>
        )}
      </div>

      {/* Job Modal */}
      <JobModal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        job={editingJob}
        onSave={handleSaveJob}
      />
    </>
  );
};

export default JobPostings;