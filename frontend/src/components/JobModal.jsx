import React, { useState, useEffect } from 'react';
import { X, Plus, Tag } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Switch } from './ui/switch';
import { Badge } from './ui/badge';
import { useToast } from '../hooks/use-toast';

const JobModal = ({ isOpen, onClose, job = null, onSave }) => {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    requirements: [],
    experienceLevel: '',
    employmentType: '',
    location: '',
    status: 'Active'
  });
  const [currentSkill, setCurrentSkill] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const { toast } = useToast();

  // Predefined skill suggestions
  const skillSuggestions = [
    'JavaScript', 'React', 'Node.js', 'Python', 'Django', 'Flask', 'Java', 'Spring Boot',
    'TypeScript', 'Angular', 'Vue.js', 'Express.js', 'MongoDB', 'PostgreSQL', 'MySQL',
    'Redis', 'Docker', 'Kubernetes', 'AWS', 'Azure', 'GCP', 'Git', 'Jenkins', 'CI/CD',
    'REST APIs', 'GraphQL', 'Microservices', 'Agile', 'Scrum', 'TDD', 'Unit Testing',
    'Leadership', 'Team Management', 'Product Strategy', 'Data Analysis', 'Machine Learning',
    'TensorFlow', 'PyTorch', 'SQL', 'NoSQL', 'Figma', 'Adobe Creative Suite', 'UI/UX Design'
  ];

  useEffect(() => {
    if (job) {
      setFormData({
        title: job.title || '',
        description: job.description || '',
        requirements: job.requirements || [],
        experienceLevel: job.experienceLevel || '',
        employmentType: job.employmentType || '',
        location: job.location || '',
        status: job.status || 'Active'
      });
    } else {
      setFormData({
        title: '',
        description: '',
        requirements: [],
        experienceLevel: '',
        employmentType: '',
        location: '',
        status: 'Active'
      });
    }
  }, [job, isOpen]);

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleAddSkill = (skill = currentSkill.trim()) => {
    if (skill && !formData.requirements.includes(skill)) {
      setFormData(prev => ({
        ...prev,
        requirements: [...prev.requirements, skill]
      }));
      setCurrentSkill('');
    }
  };

  const handleRemoveSkill = (skillToRemove) => {
    setFormData(prev => ({
      ...prev,
      requirements: prev.requirements.filter(skill => skill !== skillToRemove)
    }));
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      handleAddSkill();
    }
  };

  const handleSave = async () => {
    // Basic validation
    if (!formData.title.trim()) {
      toast({
        title: "Job title is required",
        description: "Please enter a job title.",
        variant: "destructive"
      });
      return;
    }

    if (!formData.description.trim()) {
      toast({
        title: "Job description is required",
        description: "Please enter a job description.",
        variant: "destructive"
      });
      return;
    }

    if (formData.requirements.length === 0) {
      toast({
        title: "Skills are required",
        description: "Please add at least one required skill.",
        variant: "destructive"
      });
      return;
    }

    setIsSaving(true);

    try {
      // Pass data to parent for API call
      await onSave(formData);
    } catch (error) {
      toast({
        title: "Error saving job",
        description: error.message || "Please try again.",
        variant: "destructive"
      });
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b border-slate-200">
          <h2 className="text-2xl font-bold text-slate-900">
            {job ? 'Edit Job Posting' : 'Create New Job Posting'}
          </h2>
          <Button variant="ghost" onClick={onClose} className="hover:bg-slate-100">
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-8rem)]">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Left Column */}
            <div className="space-y-6">
              {/* Job Title */}
              <div>
                <Label htmlFor="title" className="text-sm font-medium text-slate-900">
                  Job Title *
                </Label>
                <Input
                  id="title"
                  value={formData.title}
                  onChange={(e) => handleInputChange('title', e.target.value)}
                  placeholder="e.g., Senior Fullstack Developer"
                  className="mt-1"
                />
              </div>

              {/* Experience Level */}
              <div>
                <Label className="text-sm font-medium text-slate-900">
                  Experience Level
                </Label>
                <Select value={formData.experienceLevel} onValueChange={(value) => handleInputChange('experienceLevel', value)}>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Select experience level" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Entry Level">Entry Level (0-2 years)</SelectItem>
                    <SelectItem value="Mid Level">Mid Level (2-5 years)</SelectItem>
                    <SelectItem value="Senior">Senior (5-8 years)</SelectItem>
                    <SelectItem value="Lead">Lead (8+ years)</SelectItem>
                    <SelectItem value="Executive">Executive</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Employment Type */}
              <div>
                <Label className="text-sm font-medium text-slate-900">
                  Employment Type
                </Label>
                <Select value={formData.employmentType} onValueChange={(value) => handleInputChange('employmentType', value)}>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Select employment type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Full-time">Full-time</SelectItem>
                    <SelectItem value="Part-time">Part-time</SelectItem>
                    <SelectItem value="Contract">Contract</SelectItem>
                    <SelectItem value="Freelance">Freelance</SelectItem>
                    <SelectItem value="Internship">Internship</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Location */}
              <div>
                <Label htmlFor="location" className="text-sm font-medium text-slate-900">
                  Location
                </Label>
                <Input
                  id="location"
                  value={formData.location}
                  onChange={(e) => handleInputChange('location', e.target.value)}
                  placeholder="e.g., Remote, New York, NY"
                  className="mt-1"
                />
              </div>

              {/* Status */}
              <div>
                <Label className="text-sm font-medium text-slate-900">
                  Job Status
                </Label>
                <div className="flex items-center space-x-3 mt-2">
                  <Switch
                    checked={formData.status === 'Active'}
                    onCheckedChange={(checked) => handleInputChange('status', checked ? 'Active' : 'Closed')}
                  />
                  <span className="text-sm text-slate-600">
                    {formData.status === 'Active' ? 'Active - Accepting applications' : 'Closed - Not accepting applications'}
                  </span>
                </div>
              </div>
            </div>

            {/* Right Column */}
            <div className="space-y-6">
              {/* Job Description */}
              <div>
                <Label htmlFor="description" className="text-sm font-medium text-slate-900">
                  Job Description *
                </Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => handleInputChange('description', e.target.value)}
                  placeholder="Describe the role, responsibilities, and what you're looking for in a candidate..."
                  className="mt-1 min-h-[120px]"
                />
              </div>

              {/* Required Skills */}
              <div>
                <Label className="text-sm font-medium text-slate-900">
                  Required Skills *
                </Label>
                <div className="mt-2">
                  <div className="flex space-x-2 mb-3">
                    <Input
                      value={currentSkill}
                      onChange={(e) => setCurrentSkill(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Type a skill and press Enter"
                      className="flex-1"
                    />
                    <Button
                      type="button"
                      onClick={() => handleAddSkill()}
                      variant="outline"
                      size="sm"
                      disabled={!currentSkill.trim()}
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>

                  {/* Current Skills */}
                  {formData.requirements.length > 0 && (
                    <div className="mb-4">
                      <div className="flex flex-wrap gap-2">
                        {formData.requirements.map((skill, index) => (
                          <Badge
                            key={index}
                            variant="secondary"
                            className="flex items-center space-x-1 bg-blue-100 text-blue-800 hover:bg-blue-200"
                          >
                            <Tag className="h-3 w-3" />
                            <span>{skill}</span>
                            <button
                              onClick={() => handleRemoveSkill(skill)}
                              className="ml-1 hover:text-red-600"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Skill Suggestions */}
                  <div>
                    <p className="text-xs text-slate-500 mb-2">Popular skills:</p>
                    <div className="flex flex-wrap gap-1">
                      {skillSuggestions
                        .filter(skill => !formData.requirements.includes(skill))
                        .slice(0, 12)
                        .map((skill) => (
                          <button
                            key={skill}
                            onClick={() => handleAddSkill(skill)}
                            className="text-xs px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded transition-colors duration-200"
                          >
                            {skill}
                          </button>
                        ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end space-x-3 p-6 border-t border-slate-200 bg-slate-50">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving} className="bg-blue-600 hover:bg-blue-700">
            {isSaving ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                {job ? 'Updating...' : 'Creating...'}
              </>
            ) : (
              job ? 'Update Job' : 'Create Job'
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default JobModal;