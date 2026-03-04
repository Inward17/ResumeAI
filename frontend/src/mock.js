// Mock data for TrueView Dashboard

export const mockUser = {
  name: "Sarah Johnson",
  role: "HR Manager",
  email: "sarah.johnson@trueview.com",
  avatar: "https://images.unsplash.com/photo-1494790108755-2616b612b5e5?w=100&h=100&fit=crop&crop=face"
};

export const mockJobPostings = [
  {
    id: "job-1",
    title: "Senior Backend Engineer",
    status: "Active",
    totalCandidates: 128,
    screened: 95,
    shortlisted: 12,
    description: "We're looking for an experienced backend engineer to join our core platform team.",
    requirements: ["Python", "Django", "PostgreSQL", "AWS", "Docker", "Kubernetes", "Team Leadership"]
  },
  {
    id: "job-2",
    title: "Frontend React Developer",
    status: "Active",
    totalCandidates: 89,
    screened: 76,
    shortlisted: 8,
    description: "Join our frontend team to build beautiful user experiences.",
    requirements: ["React", "TypeScript", "Next.js", "Tailwind CSS", "GraphQL", "Testing"]
  },
  {
    id: "job-3",
    title: "DevOps Engineer",
    status: "Active",
    totalCandidates: 67,
    screened: 52,
    shortlisted: 6,
    description: "Help us scale our infrastructure and deployment processes.",
    requirements: ["AWS", "Kubernetes", "Terraform", "Docker", "Jenkins", "Monitoring"]
  },
  {
    id: "job-4",
    title: "Product Manager",
    status: "Closed",
    totalCandidates: 156,
    screened: 156,
    shortlisted: 15,
    description: "Drive product strategy and work closely with engineering teams.",
    requirements: ["Product Strategy", "Agile", "Analytics", "User Research", "Roadmap Planning"]
  },
  {
    id: "job-5",
    title: "UX/UI Designer",
    status: "Active",
    totalCandidates: 94,
    screened: 71,
    shortlisted: 9,
    description: "Create intuitive and beautiful user experiences for our platform.",
    requirements: ["Figma", "User Research", "Prototyping", "Design Systems", "Accessibility"]
  },
  {
    id: "job-6",
    title: "Data Scientist",
    status: "Active",
    totalCandidates: 78,
    screened: 45,
    shortlisted: 7,
    description: "Join our AI team to improve our resume screening algorithms.",
    requirements: ["Python", "Machine Learning", "TensorFlow", "Statistics", "SQL", "Deep Learning"]
  }
];

export const generateMockCandidates = (jobId) => {
  const firstNames = ["John", "Sarah", "Michael", "Emma", "David", "Lisa", "James", "Maria", "Robert", "Jennifer", "William", "Jessica", "Thomas", "Ashley", "Christopher", "Amanda", "Daniel", "Emily", "Matthew", "Michelle"];
  const lastNames = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"];

  const statuses = ["Shortlisted", "Rejected", "Pending Review"];
  const candidates = [];

  const jobRequirements = mockJobPostings.find(job => job.id === jobId)?.requirements || [];

  for (let i = 0; i < 22; i++) {
    const firstName = firstNames[Math.floor(Math.random() * firstNames.length)];
    const lastName = lastNames[Math.floor(Math.random() * lastNames.length)];
    const jdMatchScore = Math.floor(Math.random() * 40) + 60; // 60-100
    const verificationScore = Math.floor(Math.random() * 30) + 70; // 70-100
    const status = statuses[Math.floor(Math.random() * statuses.length)];

    // Generate skill matches based on job requirements
    const skillMatches = jobRequirements.map(req => ({
      skill: req,
      score: Math.floor(Math.random() * 5) + 6, // 6-10
      found: Math.random() > 0.2 // 80% chance of having the skill
    }));

    candidates.push({
      id: `candidate-${jobId}-${i + 1}`,
      name: `${firstName} ${lastName}`,
      email: `${firstName.toLowerCase()}.${lastName.toLowerCase()}@email.com`,
      phone: `+1 (555) ${Math.floor(Math.random() * 900) + 100}-${Math.floor(Math.random() * 9000) + 1000}`,
      avatar: `https://images.unsplash.com/photo-${1500000000000 + Math.floor(Math.random() * 100000000)}?w=100&h=100&fit=crop&crop=face`,
      jdMatchScore,
      verificationScore,
      status,
      linkedin: `https://linkedin.com/in/${firstName.toLowerCase()}-${lastName.toLowerCase()}`,
      github: `https://github.com/${firstName.toLowerCase()}${lastName.toLowerCase()}`,
      skillMatches,
      aiAnalysis: {
        recommendation: jdMatchScore >= 80 ? "Strongly Recommended" : jdMatchScore >= 65 ? "Recommended" : "Not Recommended",
        reasoning: jdMatchScore >= 80
          ? "This candidate demonstrates exceptional alignment with the job requirements. Their technical skills, experience level, and background make them an ideal fit for this position. Strong portfolio and consistent career progression indicate high potential for success."
          : jdMatchScore >= 65
            ? "This candidate shows good potential with solid technical skills that align well with most job requirements. While there are a few gaps in their experience, their core competencies and learning ability suggest they could be successful in this role with proper onboarding."
            : "While this candidate has some relevant experience, there are significant gaps between their background and the job requirements. Several key technical skills are missing, and their experience level may not match the seniority needed for this position."
      },
      verification: {
        experience: Math.random() > 0.3,
        education: Math.random() > 0.2,
        projects: Math.random() > 0.35
      }
    });
  }

  return candidates;
};