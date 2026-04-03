import React, { useState } from 'react';
import {
  Users, CreditCard, Plug, Key, Palette,
  Plus, Trash2, Edit, Upload, Sliders,
  UserPlus, ShieldCheck, TrendingUp, BarChart3, Zap,
  ExternalLink, CheckCircle, Copy, RotateCcw,
  Building2, MoreHorizontal, ArrowUpRight
} from 'lucide-react';
import { Switch } from './ui/switch';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Slider } from './ui/slider';
import { useToast } from '../hooks/use-toast';
import { C } from '../theme';

/* COLOR aliases for backwards compat within this file */
const COLOR = {
  ink:        C.primaryDark,
  primary:    C.primary,
  mid:        'var(--color-primary-container)',
  accent:     C.accent,
  accentSoft: 'var(--color-accent)',
  pageGray:   C.pageGray,
  white:      C.white,
};


const TABS = [
  { id: 'users',         label: 'Users',         Icon: Users },
  { id: 'billing',       label: 'Billing',        Icon: CreditCard },
  { id: 'integrations',  label: 'Integrations',   Icon: Plug },
  { id: 'api',           label: 'API Keys',        Icon: Key },
  { id: 'customization', label: 'Customization',   Icon: Palette },
];

/* ─────────────────────────────────────────────────────────────
   SHARED SUB-COMPONENTS
─────────────────────────────────────────────────────────────── */

/** White card with a thin border and subtle shadow */
const Panel = ({ children, className = '' }) => (
  <div className={`bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden ${className}`}>
    {children}
  </div>
);

/** Standard panel header row */
const PanelHeader = ({ title, subtitle, action }) => (
  <div className="flex items-start justify-between px-6 pt-6 pb-4 border-b border-slate-100">
    <div>
      <p className="font-semibold text-slate-900">{title}</p>
      {subtitle && <p className="text-sm text-slate-500 mt-0.5">{subtitle}</p>}
    </div>
    {action}
  </div>
);

/** Dark indigo gradient insight card */
const InsightPanel = ({ tag, title, body, link }) => (
  <div
    className="rounded-2xl p-5 flex flex-col gap-2"
    style={{ background: `linear-gradient(135deg, ${COLOR.primary} 0%, ${COLOR.mid} 60%, ${COLOR.accent} 100%)` }}
  >
    {tag && (
      <span className="text-[10px] font-bold tracking-widest uppercase"
        style={{ color: 'var(--color-primary-light)' }}>
        {tag}
      </span>
    )}
    <p className="font-bold text-white text-base leading-snug">{title}</p>
    <p className="text-sm leading-relaxed" style={{ color: 'var(--color-primary-lighter)' }}>{body}</p>
    {link && (
      <button className="mt-1 flex items-center gap-1 text-sm font-medium" style={{ color: 'var(--color-primary-light)' }}>
        {link} <ArrowUpRight className="h-3.5 w-3.5" />
      </button>
    )}
  </div>
);

/** Security audit mini-card */
const SecurityCard = () => (
  <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 flex flex-col items-center text-center gap-2">
    <div className="h-10 w-10 rounded-xl flex items-center justify-center"
      style={{ background: 'var(--color-primary-light)' }}>
      <ShieldCheck className="h-5 w-5" style={{ color: COLOR.accent }} />
    </div>
    <p className="font-semibold text-slate-900 text-sm">Security Audit</p>
    <p className="text-xs text-slate-500 leading-relaxed">
      Last security check was 2 days ago. No vulnerabilities detected in API keys.
    </p>
  </div>
);

/** Role pill badge */
const RoleBadge = ({ role }) => {
  const styles = {
    Admin:           { bg: 'var(--color-info-bg)', text: 'var(--color-info)' },
    Owner:           { bg: 'var(--color-info-bg)', text: 'var(--color-info)' },
    Recruiter:       { bg: 'var(--color-accent-light)', text: 'var(--color-accent)' },
    'Hiring Manager':{ bg: 'var(--color-accent-light)', text: 'var(--color-accent)' },
    Viewer:          { bg: 'var(--color-border-faint)', text: 'var(--color-text-secondary)' },
  };
  const s = styles[role] || styles.Viewer;
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider"
      style={{ background: s.bg, color: s.text }}>
      {role}
    </span>
  );
};

/** User avatar with initials */
const Avatar = ({ name }) => {
  const initials = name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
  return (
    <div className="h-8 w-8 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0"
      style={{ background: COLOR.primary }}>
      {initials}
    </div>
  );
};

/** Primary dark-indigo button */
const PrimaryBtn = ({ children, onClick, disabled, type = 'button', className = '' }) => (
  <button
    type={type}
    onClick={onClick}
    disabled={disabled}
    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-50 ${className}`}
    style={{ background: COLOR.primary }}
  >
    {children}
  </button>
);

/** Outline button */
const OutlineBtn = ({ children, onClick, className = '' }) => (
  <button
    onClick={onClick}
    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-slate-700 border border-slate-300 bg-white hover:bg-slate-50 transition-colors ${className}`}
  >
    {children}
  </button>
);

/* ─────────────────────────────────────────────────────────────
   MAIN COMPONENT
─────────────────────────────────────────────────────────────── */
const Settings = () => {
  const [activeTab, setActiveTab] = useState('users');
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [inviteData, setInviteData] = useState({ email: '', role: '' });
  const [isSaving, setIsSaving] = useState(false);
  const { toast } = useToast();

  /* ── Data ── */
  const [users] = useState([
    { id: 1, name: 'Julian Rivera',   email: 'j.rivera@neuralrecruit.ai', role: 'Owner' },
    { id: 2, name: 'Sarah Chen',      email: 's.chen@neuralrecruit.ai',   role: 'Recruiter' },
    { id: 3, name: 'Alex Thompson',   email: 'a.thompson@neuralrecruit.ai', role: 'Hiring Manager' },
    { id: 4, name: 'Elena Rodriguez', email: 'e.rod@neuralrecruit.ai',    role: 'Viewer' },
  ]);

  const [subscription] = useState({
    plan: 'Pro Plan',
    resumesUsed: 75, resumesLimit: 100,
    jobPostingsUsed: 5, jobPostingsLimit: 10,
  });

  const [integrations, setIntegrations] = useState([
    { id: 1, name: 'Slack',              description: 'Get notifications in Slack channels',      connected: true,  brandColor: '#611f69' },
    { id: 2, name: 'Google Calendar',    description: 'Schedule interviews automatically',         connected: false, brandColor: '#4285F4' },
    { id: 3, name: 'LinkedIn Recruiter', description: 'Import candidate profiles',                 connected: true,  brandColor: '#0a66c2' },
    { id: 4, name: 'Greenhouse ATS',     description: 'Sync with your existing ATS',              connected: false, brandColor: '#24b47e' },
    { id: 5, name: 'Microsoft Teams',    description: 'Team collaboration and notifications',      connected: false, brandColor: '#6264a7' },
  ]);

  const [apiKeys] = useState([
    { id: 1, name: 'Production API',  key: 'sk_live_••••••••••••••••', created: '2024-01-15', lastUsed: '2 hours ago' },
    { id: 2, name: 'Development API', key: 'sk_test_••••••••••••••••', created: '2024-01-10', lastUsed: '1 day ago'   },
  ]);

  const [scoringThresholds, setScoringThresholds] = useState({
    jdMatchThreshold: [75],
    verificationThreshold: [80],
  });

  /* ── Handlers ── */
  const handleInviteUser = () => {
    if (!inviteData.email || !inviteData.role) {
      toast({ title: 'Missing information', description: 'Please fill in all fields.', variant: 'destructive' });
      return;
    }
    setIsSaving(true);
    setTimeout(() => {
      setIsSaving(false);
      setIsInviteModalOpen(false);
      setInviteData({ email: '', role: '' });
      toast({ title: 'Invitation sent', description: `Invitation sent to ${inviteData.email}` });
    }, 1000);
  };

  const handleToggleIntegration = (id) => {
    const integration = integrations.find(i => i.id === id);
    setIntegrations(prev => prev.map(i => i.id === id ? { ...i, connected: !i.connected } : i));
    toast({
      title: integration.connected ? 'Integration disconnected' : 'Integration connected',
      description: `${integration.name} has been ${integration.connected ? 'disconnected' : 'connected'}.`,
    });
  };

  const handleGenerateApiKey = () =>
    toast({ title: 'API Key generated', description: 'New API key has been generated successfully.' });

  const handleSaveThresholds = () => {
    setIsSaving(true);
    setTimeout(() => {
      setIsSaving(false);
      toast({ title: 'Thresholds updated', description: 'Scoring thresholds have been saved.' });
    }, 1000);
  };

  const handleLogoUpload = () =>
    toast({ title: 'Photo upload', description: 'Logo upload functionality will be available soon.' });

  /* ── Render ── */
  return (
    <div className="min-h-full p-8" style={{ background: COLOR.pageGray }}>

      {/* ── Page title ── */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Workspace Settings</h1>
        <p className="text-sm text-slate-500 mt-0.5">Manage your workspace and company preferences</p>
      </div>

      {/* ── Underline tab bar ── */}
      <div className="flex gap-0 border-b border-slate-200 mb-8">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`
              px-5 py-2.5 text-sm font-semibold border-b-2 -mb-px transition-colors whitespace-nowrap
              ${activeTab !== id ? 'border-transparent text-slate-500 hover:text-slate-700' : ''}
            `}
            style={activeTab === id ? { borderBottomColor: COLOR.primary, color: COLOR.primary } : {}}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ══════════════════════════════════════════════════
          USERS
      ══════════════════════════════════════════════════ */}
      {activeTab === 'users' && (
        <div className="flex flex-col gap-6">
          {/* Team table */}
          <Panel>
            <PanelHeader
              title="Team Management"
              subtitle="Manage your team members and their respective workspace access levels."
              action={
                <Dialog open={isInviteModalOpen} onOpenChange={setIsInviteModalOpen}>
                  <DialogTrigger asChild>
                    <PrimaryBtn onClick={() => {}}>
                      <UserPlus className="h-4 w-4" /> Invite User
                    </PrimaryBtn>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader><DialogTitle>Invite Team Member</DialogTitle></DialogHeader>
                    <div className="space-y-4 mt-4">
                      <div>
                        <Label htmlFor="inviteEmail">Email Address</Label>
                        <Input
                          id="inviteEmail" type="email" value={inviteData.email}
                          onChange={e => setInviteData(p => ({ ...p, email: e.target.value }))}
                          placeholder="colleague@company.com" className="mt-1"
                        />
                      </div>
                      <div>
                        <Label>Role</Label>
                        <Select value={inviteData.role} onValueChange={v => setInviteData(p => ({ ...p, role: v }))}>
                          <SelectTrigger className="mt-1"><SelectValue placeholder="Select a role" /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Owner">Owner – Full access</SelectItem>
                            <SelectItem value="Recruiter">Recruiter – Manage jobs and candidates</SelectItem>
                            <SelectItem value="Hiring Manager">Hiring Manager – Manage candidates</SelectItem>
                            <SelectItem value="Viewer">Viewer – Read-only access</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="flex justify-end gap-2 pt-2">
                        <OutlineBtn onClick={() => setIsInviteModalOpen(false)}>Cancel</OutlineBtn>
                        <PrimaryBtn onClick={handleInviteUser} disabled={isSaving}>
                          {isSaving ? 'Sending…' : 'Send Invitation'}
                        </PrimaryBtn>
                      </div>
                    </div>
                  </DialogContent>
                </Dialog>
              }
            />

            {/* Table */}
            <table className="min-w-full">
              <thead>
                <tr style={{ background: 'var(--color-sidebar-bg)' }}>
                  {['Name', 'Email Address', 'Role', 'Actions'].map((h, i) => (
                    <th
                      key={h}
                      className={`px-6 py-3 text-xs font-bold uppercase tracking-wider ${i === 3 ? 'text-right' : 'text-left'}`}
                      style={{ color: COLOR.accent }}
                    >{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map(user => (
                  <tr key={user.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <Avatar name={user.name} />
                        <span className="text-sm font-semibold text-slate-900">{user.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">{user.email}</td>
                    <td className="px-6 py-4"><RoleBadge role={user.role} /></td>
                    <td className="px-6 py-4 text-right">
                      <button className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors">
                        <MoreHorizontal className="h-5 w-5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          {/* Insight + security row */}
          <div className="grid grid-cols-1 md:grid-cols-[1fr_240px] gap-4">
            <InsightPanel
              tag="Workspace Usage"
              title="Team Efficiency Insights"
              body="Your workspace has seen a 24% increase in interview collaboration this month. Consider upgrading roles for Sarah Chen to manage new postings."
              link="View Full Analytics"
            />
            <SecurityCard />
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════
          BILLING
      ══════════════════════════════════════════════════ */}
      {activeTab === 'billing' && (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Current plan card */}
            <Panel>
              <PanelHeader title="Current Plan" />
              <div className="px-6 py-5 space-y-5">
                <div className="flex items-center justify-between">
                  <p className="text-xl font-bold text-slate-900">{subscription.plan}</p>
                  <OutlineBtn onClick={() => {}}>Change Plan</OutlineBtn>
                </div>
                {/* Progress bars */}
                {[
                  { label: 'Resumes Screened This Month', used: subscription.resumesUsed, limit: subscription.resumesLimit },
                  { label: 'Active Job Postings', used: subscription.jobPostingsUsed, limit: subscription.jobPostingsLimit },
                ].map(item => (
                  <div key={item.label}>
                    <div className="flex justify-between text-sm mb-1.5">
                      <span className="text-slate-700 font-medium">{item.label}</span>
                      <span className="font-bold" style={{ color: COLOR.accent }}>
                        {item.used}/{item.limit}
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{ width: `${(item.used / item.limit) * 100}%`, background: COLOR.accent }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Panel>

            {/* Payment history */}
            <Panel>
              <PanelHeader title="Payment History" />
              <div className="divide-y divide-slate-100">
                {[
                  { date: 'Jan 1, 2024', amount: '$99.00' },
                  { date: 'Dec 1, 2023', amount: '$99.00' },
                  { date: 'Nov 1, 2023', amount: '$99.00' },
                ].map((inv, i) => (
                  <div key={i} className="flex items-center justify-between px-6 py-4">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{inv.amount}</p>
                      <p className="text-xs text-slate-500">{inv.date}</p>
                    </div>
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-green-100 text-green-700 uppercase">
                      <CheckCircle className="h-3 w-3" /> Paid
                    </span>
                  </div>
                ))}
              </div>
            </Panel>
          </div>

          {/* Insight + payment method row */}
          <div className="grid grid-cols-1 md:grid-cols-[1fr_240px] gap-4">
            <InsightPanel
              tag="Billing Efficiency"
              title="Billing Efficiency"
              body="Your Pro Plan currently covers all your recruiting needs. Based on your current growth, you'll reach 90% capacity by next quarter."
            />
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Payment Method</p>
              <div className="flex items-center gap-3 mb-3">
                <div className="h-9 w-9 rounded-lg flex items-center justify-center"
                  style={{ background: 'var(--color-primary-light)' }}>
                  <CreditCard className="h-4 w-4" style={{ color: COLOR.accent }} />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">Visa ending in •••• 4242</p>
                  <p className="text-xs text-slate-400">Expires 09/26</p>
                </div>
              </div>
              <button className="text-sm font-semibold" style={{ color: COLOR.accent }}>Update card</button>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════
          INTEGRATIONS
      ══════════════════════════════════════════════════ */}
      {activeTab === 'integrations' && (
        <div className="max-w-3xl flex flex-col gap-6">
          <Panel>
            <PanelHeader title="Available Integrations" subtitle="Manage your workspace and company preferences" />
            <div className="divide-y divide-slate-100">
              {integrations.map(integration => (
                <div
                  key={integration.id}
                  className="flex items-center justify-between px-6 py-5 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    {/* Brand coloured initial */}
                    <div
                      className="h-10 w-10 rounded-xl flex items-center justify-center text-white text-sm font-bold shrink-0"
                      style={{ background: integration.brandColor }}
                    >
                      {integration.name.charAt(0)}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{integration.name}</p>
                      <p className="text-xs text-slate-500 mt-0.5">{integration.description}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span
                      className="text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider"
                      style={integration.connected
                        ? { background: COLOR.primary, color: '#fff' }
                        : { background: 'var(--color-surface-container)', color: 'var(--color-primary)' }}
                    >
                      {integration.connected ? 'Connected' : 'Not Connected'}
                    </span>
                    <Switch
                      checked={integration.connected}
                      onCheckedChange={() => handleToggleIntegration(integration.id)}
                    />
                  </div>
                </div>
              ))}
            </div>
            <div className="px-6 py-4 border-t border-slate-100 text-center">
              <button
                className="text-sm font-semibold inline-flex items-center gap-1 hover:opacity-80 transition-opacity"
                style={{ color: COLOR.accent }}
              >
                Request a custom integration <ExternalLink className="h-3.5 w-3.5" />
              </button>
            </div>
          </Panel>
        </div>
      )}

      {/* ══════════════════════════════════════════════════
          API KEYS
      ══════════════════════════════════════════════════ */}
      {activeTab === 'api' && (
        <div className="flex flex-col gap-6">
          <Panel>
            <PanelHeader
              title="API Authentication"
              subtitle="Manage secure access keys for your integrations and developer tools."
              action={
                <PrimaryBtn onClick={handleGenerateApiKey}>
                  <Plus className="h-4 w-4" /> Generate New Key
                </PrimaryBtn>
              }
            />
            <div className="divide-y divide-slate-100">
              {apiKeys.map(keyItem => (
                <div key={keyItem.id} className="px-6 py-5">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{keyItem.name}</p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Created {keyItem.created} · Last used {keyItem.lastUsed}
                      </p>
                    </div>
                    <div className="flex gap-1">
                      <button className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors" title="Copy">
                        <Copy className="h-4 w-4" />
                      </button>
                      <button className="p-1.5 rounded-lg hover:bg-amber-50 text-slate-400 hover:text-amber-600 transition-colors" title="Rotate">
                        <RotateCcw className="h-4 w-4" />
                      </button>
                      <button className="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-600 transition-colors" title="Revoke">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                  <code className="block w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm font-mono text-slate-700 select-all">
                    {keyItem.key}
                  </code>
                </div>
              ))}
            </div>
          </Panel>

          <div className="grid grid-cols-1 md:grid-cols-[1fr_240px] gap-4">
            <InsightPanel
              tag="Key Rotation Policy"
              title="Key Rotation Policy"
              body="Your Development API key hasn't been rotated in over 90 days. We recommend updating it for enhanced security infrastructure."
            />
            <SecurityCard />
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════
          CUSTOMIZATION
      ══════════════════════════════════════════════════ */}
      {activeTab === 'customization' && (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_240px] gap-6 items-start">
            <div className="flex flex-col gap-6">
              {/* Scoring thresholds */}
              <Panel>
                <PanelHeader
                  title="Scoring Thresholds"
                  subtitle="Configure when candidates are flagged or marked as low match."
                  action={<Sliders className="h-5 w-5 text-slate-400" />}
                />
                <div className="px-6 py-6 space-y-8">
                  {[
                    {
                      key: 'jdMatchThreshold',
                      label: 'JD Match Score Threshold',
                      hint: 'Candidates below this threshold will be marked as low match',
                    },
                    {
                      key: 'verificationThreshold',
                      label: 'Verification Score Threshold',
                      hint: 'Candidates below this threshold will be flagged for manual review',
                    },
                  ].map(item => (
                    <div key={item.key}>
                      <div className="flex justify-between items-center mb-1">
                        <Label className="text-sm font-semibold text-slate-900">{item.label}</Label>
                        <span className="text-sm font-bold" style={{ color: COLOR.accent }}>
                          {scoringThresholds[item.key][0]}%
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mb-4">{item.hint}</p>
                      <Slider
                        value={scoringThresholds[item.key]}
                        onValueChange={v => setScoringThresholds(p => ({ ...p, [item.key]: v }))}
                        max={100}
                        step={5}
                        className="w-full"
                      />
                    </div>
                  ))}
                  <PrimaryBtn onClick={handleSaveThresholds} disabled={isSaving}>
                    {isSaving ? 'Saving…' : 'Save Thresholds'}
                  </PrimaryBtn>
                </div>
              </Panel>

              {/* Company branding */}
              <Panel>
                <PanelHeader title="Company Branding" subtitle="Customize the look and feel of your workspace." />
                <div className="px-6 py-6">
                  <Label className="text-sm font-semibold text-slate-900">Company Logo</Label>
                  <div className="flex items-center gap-5 mt-3">
                    <div
                      className="h-16 w-16 rounded-2xl flex items-center justify-center shrink-0"
                      style={{ background: 'var(--color-primary-light)', border: `2px solid var(--color-surface-highest)` }}
                    >
                      <Building2 className="h-7 w-7" style={{ color: COLOR.accent }} />
                    </div>
                    <div>
                      <OutlineBtn onClick={handleLogoUpload}>
                        <Upload className="h-4 w-4" /> Upload New Logo
                      </OutlineBtn>
                      <p className="text-xs text-slate-400 mt-2">Recommended: 200×200px, PNG or JPG</p>
                    </div>
                  </div>
                  <div className="mt-6">
                    <PrimaryBtn onClick={handleSaveThresholds} disabled={isSaving}>
                      {isSaving ? 'Saving…' : 'Save Branding'}
                    </PrimaryBtn>
                  </div>
                </div>
              </Panel>
            </div>

            {/* Right column */}
            <div className="flex flex-col gap-4">
              <InsightPanel
                tag="Team Efficiency Insights"
                title="Team Efficiency Insights"
                body="Your workspace has seen a 24% increase in interview collaboration this month. Consider upgrading roles for Sarah Chen to manage new postings."
                link="View Full Analytics"
              />
              <SecurityCard />
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default Settings;