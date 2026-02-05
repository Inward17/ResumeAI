import React, { useState, useRef, useEffect } from 'react';
import { Upload, FileText, X, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Progress } from './ui/progress';
import { Badge } from './ui/badge';
import { useToast } from '../hooks/use-toast';
import { getJobs, transformJobFromAPI } from '../services/jobService';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const Dashboard = () => {
  const [jobs, setJobs] = useState([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [selectedJobId, setSelectedJobId] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef(null);
  const { toast } = useToast();

  // Fetch jobs on mount
  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    try {
      setJobsLoading(true);
      const data = await getJobs();
      const transformedJobs = data.map(transformJobFromAPI);
      setJobs(transformedJobs);
    } catch (err) {
      console.error('Error fetching jobs:', err);
      toast({
        title: "Error loading jobs",
        description: "Could not load job postings. Please refresh the page.",
        variant: "destructive"
      });
    } finally {
      setJobsLoading(false);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    handleFiles(files);
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    handleFiles(files);
  };

  const handleFiles = (files) => {
    const validFiles = files.filter(file => {
      const isValidType = file.type === 'application/pdf' ||
        file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
        file.type === 'application/msword';
      const isValidSize = file.size <= 10 * 1024 * 1024; // 10MB limit

      if (!isValidType) {
        toast({
          title: "Invalid file type",
          description: `${file.name} is not a supported format. Please upload PDF or Word documents.`,
          variant: "destructive"
        });
        return false;
      }

      if (!isValidSize) {
        toast({
          title: "File too large",
          description: `${file.name} exceeds the 10MB limit.`,
          variant: "destructive"
        });
        return false;
      }

      return true;
    });

    const newFiles = validFiles.map(file => ({
      id: Date.now() + Math.random(),
      name: file.name,
      size: file.size,
      type: file.type,
      progress: 0,
      status: 'pending', // pending, uploading, completed, error
      originalFile: file  // Store original File object for upload
    }));

    setUploadedFiles(prev => [...prev, ...newFiles]);

    // Simulate upload progress
    newFiles.forEach(file => {
      simulateUploadProgress(file.id);
    });
  };

  const simulateUploadProgress = (fileId) => {
    const interval = setInterval(() => {
      setUploadedFiles(prev =>
        prev.map(file => {
          if (file.id === fileId) {
            const newProgress = Math.min(file.progress + Math.random() * 30, 100);
            const newStatus = newProgress === 100 ? 'completed' : 'uploading';
            return { ...file, progress: newProgress, status: newStatus };
          }
          return file;
        })
      );
    }, 200);

    setTimeout(() => {
      clearInterval(interval);
      setUploadedFiles(prev =>
        prev.map(file =>
          file.id === fileId ? { ...file, progress: 100, status: 'completed' } : file
        )
      );
    }, 2000 + Math.random() * 2000);
  };

  const removeFile = (fileId) => {
    setUploadedFiles(prev => prev.filter(file => file.id !== fileId));
  };

  const handleSubmitForScreening = async () => {
    if (!selectedJobId) {
      toast({
        title: "Please select a job posting",
        description: "Choose which job posting these resumes are for.",
        variant: "destructive"
      });
      return;
    }

    if (uploadedFiles.length === 0) {
      toast({
        title: "No files to process",
        description: "Please upload at least one resume before submitting.",
        variant: "destructive"
      });
      return;
    }

    const completedFiles = uploadedFiles.filter(file => file.status === 'completed');
    if (completedFiles.length === 0) {
      toast({
        title: "Files still uploading",
        description: "Please wait for all files to finish uploading.",
        variant: "destructive"
      });
      return;
    }

    setIsUploading(true);

    try {
      // Create FormData with all completed files
      const formData = new FormData();
      completedFiles.forEach(file => {
        if (file.originalFile) {
          formData.append('files', file.originalFile);
        }
      });

      // Upload to backend API
      const response = await fetch(
        `${API_BASE_URL}/api/v1/jobs/${selectedJobId}/upload`,
        {
          method: 'POST',
          body: formData
        }
      );

      if (!response.ok) {
        throw new Error('Upload failed');
      }

      const result = await response.json();

      toast({
        title: "Screening initiated!",
        description: `${result.saved.length} resumes have been submitted for AI screening.`
      });

      // Reset form
      setUploadedFiles([]);
      setSelectedJobId('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error) {
      console.error('Upload error:', error);
      toast({
        title: "Upload failed",
        description: "There was an error uploading the files. Please try again.",
        variant: "destructive"
      });
    } finally {
      setIsUploading(false);
    }
  };

  const selectedJob = jobs.find(job => job.id === selectedJobId);
  const completedFiles = uploadedFiles.filter(file => file.status === 'completed');
  const uploadingFiles = uploadedFiles.filter(file => file.status === 'uploading');
  const activeJobs = jobs.filter(job => job.status === 'Active');

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-slate-600 mt-1">Upload and manage candidate resumes for AI screening</p>
      </div>

      {/* Main Upload Section */}
      <div className="max-w-4xl">
        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl text-slate-900">Upload Resumes</CardTitle>
            <p className="text-sm text-slate-600">Select a job posting and upload candidate resumes for automated screening</p>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Job Selection */}
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-2">
                Select Job Posting
              </label>
              <Select value={selectedJobId} onValueChange={setSelectedJobId} disabled={jobsLoading}>
                <SelectTrigger className="w-full border-slate-300">
                  <SelectValue placeholder={jobsLoading ? "Loading jobs..." : "Choose a job posting..."} />
                </SelectTrigger>
                <SelectContent>
                  {jobsLoading ? (
                    <div className="flex items-center justify-center p-4">
                      <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
                      <span className="ml-2 text-slate-500">Loading...</span>
                    </div>
                  ) : activeJobs.length === 0 ? (
                    <div className="p-4 text-center text-slate-500">
                      No active job postings. Create one first.
                    </div>
                  ) : (
                    activeJobs.map((job) => (
                      <SelectItem key={job.id} value={job.id}>
                        <div className="flex items-center justify-between w-full">
                          <span>{job.title}</span>
                          <Badge className="ml-2 bg-green-100 text-green-800">{job.status}</Badge>
                        </div>
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
              {selectedJob && (
                <p className="text-sm text-slate-600 mt-2">
                  Selected: <span className="font-medium">{selectedJob.title}</span>
                </p>
              )}
            </div>

            {/* File Upload Area */}
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-2">
                Upload Resume Files
              </label>
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-all duration-200 ${isDragOver
                  ? 'border-blue-400 bg-blue-50'
                  : 'border-slate-300 hover:border-slate-400'
                  }`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <Upload className="h-12 w-12 text-slate-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-slate-900 mb-2">
                  Drag and drop resume files here
                </h3>
                <p className="text-slate-600 mb-4">
                  or click below to browse files
                </p>
                <Button
                  variant="outline"
                  onClick={() => fileInputRef.current?.click()}
                  className="border-slate-300 text-slate-700 hover:bg-slate-50"
                >
                  Browse Files
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.doc,.docx"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <p className="text-xs text-slate-500 mt-4">
                  Supported formats: PDF, DOC, DOCX (Max 10MB per file)
                </p>
              </div>
            </div>

            {/* Uploaded Files List */}
            {uploadedFiles.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-slate-900 mb-3">
                  Uploaded Files ({uploadedFiles.length})
                </h4>
                <div className="space-y-3">
                  {uploadedFiles.map((file) => (
                    <div key={file.id} className="flex items-center space-x-3 p-3 bg-slate-50 rounded-lg">
                      <FileText className="h-5 w-5 text-slate-600 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-900 truncate">
                          {file.name}
                        </p>
                        <p className="text-xs text-slate-500">
                          {(file.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                        {file.status === 'uploading' && (
                          <div className="mt-2">
                            <div className="flex justify-between text-xs text-slate-600 mb-1">
                              <span>Uploading...</span>
                              <span>{Math.round(file.progress)}%</span>
                            </div>
                            <Progress value={file.progress} className="h-1" />
                          </div>
                        )}
                      </div>
                      <div className="flex items-center space-x-2">
                        {file.status === 'completed' && (
                          <CheckCircle className="h-4 w-4 text-green-600" />
                        )}
                        {file.status === 'error' && (
                          <AlertCircle className="h-4 w-4 text-red-600" />
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeFile(file.id)}
                          className="text-slate-400 hover:text-slate-600"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Submit Button */}
            <div className="flex justify-end">
              <Button
                onClick={handleSubmitForScreening}
                disabled={!selectedJobId || uploadedFiles.length === 0 || completedFiles.length === 0 || isUploading}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 disabled:text-slate-500"
              >
                {isUploading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Processing...
                  </>
                ) : (
                  `Submit ${completedFiles.length} Resume${completedFiles.length !== 1 ? 's' : ''} for Screening`
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Quick Stats */}
        {uploadedFiles.length > 0 && (
          <div className="grid grid-cols-3 gap-4 mt-6">
            <Card className="border-slate-200">
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold text-slate-900">{uploadedFiles.length}</p>
                <p className="text-sm text-slate-600">Total Files</p>
              </CardContent>
            </Card>
            <Card className="border-slate-200">
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold text-green-600">{completedFiles.length}</p>
                <p className="text-sm text-slate-600">Ready to Process</p>
              </CardContent>
            </Card>
            <Card className="border-slate-200">
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold text-amber-600">{uploadingFiles.length}</p>
                <p className="text-sm text-slate-600">Uploading</p>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;