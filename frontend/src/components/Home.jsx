import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight, FileStack, ShieldCheck, Code2, MessageSquareText, PenLine, Users, Mail,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import BrandMark from './BrandMark';
import { Github } from './BrandIcons';
import { buttonClass } from './common';
import { ThemeToggle } from './Sidebar';

// Only features that are live on main
const FEATURES = [
  {
    Icon: FileStack,
    title: 'Bulk upload and AI parsing',
    text: 'Drop a batch of PDF, DOCX or TXT resumes on a job. Each one is parsed and scored skill by skill against the job description, with live progress.',
  },
  {
    Icon: ShieldCheck,
    title: 'Credibility checks',
    text: "Claims are checked against the candidate's GitHub, LinkedIn and the web, and combined into one credibility score next to the role match.",
  },
  {
    Icon: Code2,
    title: 'Coding profiles, portfolios and projects',
    text: 'Linked coding profiles, portfolios and community accounts are looked up, and the AI can review deployed projects. Shown as evidence; they never change a score.',
  },
  {
    Icon: MessageSquareText,
    title: 'Interview kit',
    text: 'Questions tailored to the job and the resume, a checklist to score answers, and a fact checker you can ask about any claim.',
  },
  {
    Icon: PenLine,
    title: 'AI job descriptions',
    text: 'Write a job description from the title, level and required skills, with notes on wording that may put candidates off.',
  },
  {
    Icon: Mail,
    title: 'Cover letters',
    text: 'Attach a letter to a candidate or upload letters with the resumes. They are paired to their resume, summarised and compared with it.',
  },
  {
    Icon: Users,
    title: 'Team roles',
    text: 'Owner, admin, recruiter, hiring manager and interviewer. Hiring managers and interviewers see only the jobs they are assigned to.',
  },
];

const STEPS = [
  { title: 'Create a job', text: 'Add the role, required skills and description, or let the AI draft it.' },
  { title: 'Upload resumes', text: 'Drop them all at once. Parsing and verification run in the background.' },
  { title: 'Review ranked candidates', text: 'Start from the strongest matches, with the evidence behind every score.' },
  { title: 'Interview', text: 'Use the tailored questions and fact checker, then record the result.' },
];

const Home = () => {
  const { user, loading } = useAuth();

  // Nothing until auth settles, so signed-in users don't see "Sign in" flash
  const actions = loading ? null : user ? (
    <Link to="/dashboard" className={buttonClass('primary', 'md')}>Open dashboard</Link>
  ) : (
    <>
      <Link to="/login" className={buttonClass('ghost', 'md')}>Sign in</Link>
      <Link to="/register" className={buttonClass('primary', 'md')}>Get started</Link>
    </>
  );

  return (
    <div className="min-h-[100dvh] bg-canvas text-ink">
      <a href="#main" className="sr-only z-50 rounded-lg bg-surface px-3 py-2 text-sm font-medium focus:not-sr-only focus:absolute focus:left-3 focus:top-3">
        Skip to content
      </a>

      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 md:px-8">
          <Link to="/" className="rounded-md" aria-label="ResumeAI home"><BrandMark /></Link>
          <nav aria-label="Account" className="flex items-center gap-1 sm:gap-2">
            <ThemeToggle />
            {actions}
          </nav>
        </div>
      </header>

      <main id="main">
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-4 pb-16 pt-14 md:px-8 md:pb-24 md:pt-24">
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-primary-text">AI resume screening for hiring teams</p>
          <h1 className="mt-4 max-w-3xl font-serif text-[2.6rem] leading-[1.05] tracking-[-0.01em] text-ink sm:text-6xl md:text-7xl">
            Screen resumes with <em>evidence</em>, not guesswork.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-ink-2 md:text-lg">
            ResumeAI is a hiring workspace for recruiters. It parses every resume, scores it against your job,
            checks the candidate's claims against GitHub, LinkedIn and the web, and ranks the pipeline so you start
            with the strongest, most credible people.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            {!loading && (user ? (
              <Link to="/dashboard" className={buttonClass('primary', 'lg')}>Open dashboard <ArrowRight aria-hidden="true" /></Link>
            ) : (
              <>
                <Link to="/register" className={buttonClass('primary', 'lg')}>Get started <ArrowRight aria-hidden="true" /></Link>
                <Link to="/login" className={buttonClass('secondary', 'lg')}>Sign in</Link>
              </>
            ))}
          </div>
        </section>

        {/* Features */}
        <section aria-labelledby="features" className="border-y border-line bg-surface">
          <div className="mx-auto max-w-6xl px-4 py-16 md:px-8 md:py-20">
            <h2 id="features" className="font-serif text-4xl leading-tight text-ink">What it does</h2>
            <ul className="mt-10 grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map(({ Icon, title, text }) => (
                <li key={title} className="bg-surface p-6">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary-soft">
                    <Icon className="h-[18px] w-[18px] text-primary-soft-fg" strokeWidth={1.75} aria-hidden="true" />
                  </div>
                  <h3 className="mt-4 text-sm font-semibold text-ink">{title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-ink-3">{text}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* How it works */}
        <section aria-labelledby="how" className="mx-auto max-w-6xl px-4 py-16 md:px-8 md:py-20">
          <h2 id="how" className="font-serif text-4xl leading-tight text-ink">How it works</h2>
          <ol className="mt-10 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(({ title, text }, i) => (
              <li key={title} className="border-t border-line-strong pt-4">
                <span className="font-serif text-3xl leading-none tabular-nums text-primary-text" aria-hidden="true">{i + 1}</span>
                <h3 className="mt-3 text-sm font-semibold text-ink">{title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-ink-3">{text}</p>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-6 text-sm text-ink-3 sm:flex-row sm:items-center sm:justify-between md:px-8">
          <BrandMark />
          <a href="https://github.com/Inward17/ResumeAI" target="_blank" rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md hover:text-ink">
            <Github className="h-4 w-4" aria-hidden="true" /> Source on GitHub
          </a>
        </div>
      </footer>
    </div>
  );
};

export default Home;
