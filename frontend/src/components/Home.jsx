import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight, FileStack, ShieldCheck, Code2, MessageSquareText, PenLine, Users, Mail,
  BriefcaseBusiness, Upload, ListOrdered, MessagesSquare,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useReveal } from '../hooks/useReveal';
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
  { Icon: BriefcaseBusiness, title: 'Create a job', text: 'Add the role, required skills and description, or let the AI draft it.' },
  { Icon: Upload, title: 'Upload resumes', text: 'Drop them all at once. Parsing and verification run in the background.' },
  { Icon: ListOrdered, title: 'Review ranked candidates', text: 'Start from the strongest matches, with the evidence behind every score.' },
  { Icon: MessagesSquare, title: 'Interview', text: 'Use the tailored questions and fact checker, then record the result.' },
];

// Hero illustration: a resume is scanned and becomes a ranked list with scores and evidence ticks
const RANKED = [
  { score: 92, checks: [true, true, true] },
  { score: 78, checks: [true, true, false] },
  { score: 55, checks: [true, false, false] },
];

const Tick = ({ x, y, ok, i }) => (ok ? (
  <g transform={`translate(${x} ${y})`}>
    <circle r="6" className="fill-success-soft ill-pop" style={{ '--i': i }} />
    <path d="M-2.6 0.2 L-0.8 2 L2.8 -1.8" pathLength="1" fill="none" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
      className="stroke-success ill-check" style={{ '--i': i }} />
  </g>
) : (
  <circle cx={x} cy={y} r="5.5" fill="none" strokeWidth="1.2" strokeDasharray="2 2" className="stroke-line-strong" />
));

const HeroIllustration = () => (
  <svg viewBox="0 0 400 290" className="h-auto w-full max-w-md" aria-hidden="true">
    <defs>
      <clipPath id="home-resume-clip"><rect x="16" y="50" width="150" height="200" rx="8" /></clipPath>
    </defs>

    {/* Resume */}
    <rect x="16" y="50" width="150" height="200" rx="8" strokeWidth="1" className="fill-surface stroke-line" />
    <circle cx="44" cy="82" r="14" className="fill-subtle" />
    <rect x="66" y="74" width="72" height="7" rx="3.5" className="fill-line-strong" />
    <rect x="66" y="87" width="48" height="5" rx="2.5" className="fill-line" />
    {[0, 1, 2, 3, 4, 5, 6, 7].map((n) => (
      <rect key={n} x="30" y={116 + n * 15} width={[60, 120, 104, 112, 52, 116, 96, 80][n]} height={n === 0 || n === 4 ? 6 : 5} rx="2.5"
        className={n === 0 || n === 4 ? 'fill-line-strong' : 'fill-line'} />
    ))}
    <g clipPath="url(#home-resume-clip)">
      <g className="ill-scan" style={{ '--scan': '180px' }}>
        <rect x="16" y="38" width="150" height="18" className="fill-primary/10" />
        <rect x="16" y="56" width="150" height="1.5" className="fill-primary" />
      </g>
    </g>

    {/* Arrow */}
    <path d="M172 150 H188" strokeWidth="1.5" strokeLinecap="round" className="stroke-line-strong" />
    <path d="M184 145 L190 150 L184 155" fill="none" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="stroke-line-strong" />

    {/* Ranked list */}
    <rect x="196" y="20" width="188" height="250" rx="8" strokeWidth="1" className="fill-surface stroke-line" />
    {RANKED.map(({ score, checks }, r) => {
      const y = 36 + r * 78;
      return (
        <g key={r}>
          {r > 0 && <path d={`M208 ${y - 8} H372`} strokeWidth="1" className="stroke-line" />}
          <text x="212" y={y + 24} fontSize="14" className="fill-ink-3 font-serif">{r + 1}</text>
          <circle cx="238" cy={y + 20} r="11" className="fill-primary-soft" />
          <rect x="256" y={y + 12} width="74" height="6" rx="3" className="fill-line-strong" />
          <rect x="256" y={y + 23} width="48" height="4" rx="2" className="fill-line" />
          <rect x="212" y={y + 40} width="120" height="6" rx="3" className="fill-subtle" />
          <rect x="212" y={y + 40} width={120 * (score / 100)} height="6" rx="3" style={{ '--i': r }}
            className={`ill-bar ${score >= 75 ? 'fill-primary' : 'fill-warning'}`} />
          <text x="340" y={y + 46} fontSize="10" fontWeight="600" className="fill-ink-2 tabular-nums">{score}</text>
          {checks.map((ok, c) => <Tick key={c} x={218 + c * 18} y={y + 60} ok={ok} i={r * 3 + c} />)}
        </g>
      );
    })}
  </svg>
);

const Home = () => {
  const { user, loading } = useAuth();
  const featuresRef = useReveal();
  const stepsRef = useReveal();

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
        <section className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-10 px-4 pb-16 pt-14 md:px-8 md:pb-24 md:pt-20 lg:grid-cols-[minmax(0,1fr)_26rem]">
          <div>
          <p className="animate-fade-up text-xs font-medium uppercase tracking-[0.08em] text-primary-text">AI resume screening for hiring teams</p>
          <h1 style={{ '--i': 1 }} className="animate-fade-up mt-4 max-w-3xl font-serif text-[2.6rem] leading-[1.05] tracking-[-0.01em] text-ink sm:text-6xl md:text-7xl">
            Screen resumes with <em>evidence</em>, not guesswork.
          </h1>
          <p style={{ '--i': 2 }} className="animate-fade-up mt-5 max-w-2xl text-base leading-relaxed text-ink-2 md:text-lg">
            ResumeAI is a hiring workspace for recruiters. It parses every resume, scores it against your job,
            checks the candidate's claims against GitHub, LinkedIn and the web, and ranks the pipeline so you start
            with the strongest, most credible people.
          </p>
          <div style={{ '--i': 3 }} className="animate-fade-up mt-8 flex flex-wrap gap-3">
            {!loading && (user ? (
              <Link to="/dashboard" className={buttonClass('primary', 'lg')}>Open dashboard <ArrowRight aria-hidden="true" /></Link>
            ) : (
              <>
                <Link to="/register" className={buttonClass('primary', 'lg')}>Get started <ArrowRight aria-hidden="true" /></Link>
                <Link to="/login" className={buttonClass('secondary', 'lg')}>Sign in</Link>
              </>
            ))}
          </div>
          </div>
          <div style={{ '--i': 2 }} className="animate-fade-up flex justify-center lg:justify-end">
            <HeroIllustration />
          </div>
        </section>

        {/* Features */}
        <section aria-labelledby="features" className="border-y border-line bg-surface">
          <div className="mx-auto max-w-6xl px-4 py-16 md:px-8 md:py-20">
            <h2 id="features" className="font-serif text-4xl leading-tight text-ink">What it does</h2>
            <ul ref={featuresRef} className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map(({ Icon, title, text }, i) => (
                <li key={title} style={{ '--i': i }}
                  className="rounded-lg border border-line bg-canvas p-6 transition duration-200 ease-out hover:border-line-strong hover:shadow-pop motion-safe:hover:-translate-y-0.5">
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
          <ol ref={stepsRef} className="mt-10 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(({ Icon, title, text }, i) => (
              <li key={title} style={{ '--i': i }} className="border-t border-line-strong pt-4">
                <div className="flex items-center justify-between">
                  <span className="font-serif text-3xl leading-none tabular-nums text-primary-text" aria-hidden="true">{i + 1}</span>
                  <span className="flex h-10 w-10 items-center justify-center rounded-full border border-line bg-surface">
                    <Icon className="h-[18px] w-[18px] text-ink-2" strokeWidth={1.75} aria-hidden="true" />
                  </span>
                </div>
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
