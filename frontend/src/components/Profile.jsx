import React, { useState } from 'react';
import {
  User, Mail, Phone, MapPin, Zap, Shield, Key,
  Monitor, Save, ChevronRight, TrendingUp, Star,
  Lock, Smartphone, AlertTriangle, CheckCircle
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/use-toast';
import { C } from '../theme';

/* ── Shared card ── */
const Card = ({ children, className = '' }) => (
  <div className={`bg-white rounded-2xl border border-slate-200 shadow-sm ${className}`}>
    {children}
  </div>
);

/* ── Section header ── */
const SectionHeader = ({ icon: Icon, title, action }) => (
  <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
    <div className="flex items-center gap-2">
      {Icon && <Icon className="h-4 w-4 text-slate-400" />}
      <p className="font-semibold text-slate-900">{title}</p>
    </div>
    {action}
  </div>
);

/* ── Toggle switch ── */
const Toggle = ({ checked, onChange }) => (
  <button
    onClick={() => onChange(!checked)}
    className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none"
    style={{ background: checked ? C.accent : '#e2e8f0' }}
  >
    <span
      className="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform duration-200"
      style={{ transform: checked ? 'translateX(22px)' : 'translateX(4px)' }}
    />
  </button>
);

/* ── Styled input ── */
const FInput = ({ label, id, icon: Icon, ...props }) => (
  <div>
    <label htmlFor={id} className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
      {label}
    </label>
    <div className="relative">
      {Icon && <Icon className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />}
      <input
        id={id}
        {...props}
        className={`w-full py-2.5 rounded-xl border border-slate-200 bg-white text-sm text-slate-800 outline-none focus:ring-2 focus:ring-indigo-200 transition ${Icon ? 'pl-9 pr-4' : 'px-4'}`}
      />
    </div>
  </div>
);

/* ── Score ring ── */
const ScoreRing = ({ value }) => {
  const r = 30;
  const circ = 2 * Math.PI * r;
  const dash = (value / 100) * circ;
  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: 80, height: 80 }}>
        <svg viewBox="0 0 70 70" width={80} height={80} className="-rotate-90">
          <circle cx="35" cy="35" r={r} fill="none" stroke="#e0e7ff" strokeWidth="6" />
          <circle cx="35" cy="35" r={r} fill="none" stroke={C.cyan} strokeWidth="6"
            strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl font-black" style={{ color: C.primary }}>{value}</span>
        </div>
      </div>
    </div>
  );
};

const Profile = () => {
  const { user } = useAuth();
  const { toast } = useToast();

  // Personal info state
  const [personal, setPersonal] = useState({
    fullName:  user?.displayName || 'Alex Rivera',
    email:     user?.email || 'alex.rivera@precisioncurator.io',
    phone:     '+1 (555) 892-0432',
    location:  'San Francisco, CA',
  });

  // Notification prefs
  const [notifs, setNotifs] = useState({
    emailScreening:    true,
    inAppApplications: true,
    weeklyReports:     false,
    jobPostingUpdates: true,
    candidateShortlist: true,
  });

  // AI params
  const [aiParams, setAiParams] = useState({
    defaultJobActive: true,
    highScoreAlerts:  true,
  });

  const [saving, setSaving] = useState(false);

  const handleSavePersonal = async (e) => {
    e.preventDefault();
    setSaving(true);
    await new Promise(r => setTimeout(r, 600));
    setSaving(false);
    toast({ title: 'Profile updated', description: 'Your personal information has been saved.' });
  };

  const handleSaveNotifs = async () => {
    setSaving(true);
    await new Promise(r => setTimeout(r, 400));
    setSaving(false);
    toast({ title: 'Preferences saved', description: 'Notification settings updated.' });
  };

  const setNotif = (key, val) => setNotifs(p => ({ ...p, [key]: val }));
  const setAi    = (key, val) => setAiParams(p => ({ ...p, [key]: val }));

  return (
    <div className="min-h-full p-8" style={{ background: C.pageGray }}>
      {/* ── Page header ── */}
      <div className="mb-8">
        <h1 className="text-2xl font-black text-slate-900">Account Settings</h1>
        <p className="text-sm text-slate-400 mt-1">
          Manage your professional identity, security preferences, and AI-driven recruitment parameters.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_300px] gap-6">
        {/* ── LEFT COL ── */}
        <div className="flex flex-col gap-6">

          {/* Personal Information */}
          <Card>
            <SectionHeader icon={User} title="Personal Information" />
            <form onSubmit={handleSavePersonal} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <FInput id="fullName" label="Full Name" icon={User}
                  value={personal.fullName}
                  onChange={e => setPersonal(p => ({ ...p, fullName: e.target.value }))}
                />
                <FInput id="email" label="Email Address" icon={Mail} type="email"
                  value={personal.email}
                  onChange={e => setPersonal(p => ({ ...p, email: e.target.value }))}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <FInput id="phone" label="Phone Number" icon={Phone}
                  value={personal.phone}
                  onChange={e => setPersonal(p => ({ ...p, phone: e.target.value }))}
                />
                <FInput id="location" label="Location" icon={MapPin}
                  value={personal.location}
                  onChange={e => setPersonal(p => ({ ...p, location: e.target.value }))}
                />
              </div>
              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                  style={{ background: C.primary }}
                >
                  <Save className="h-4 w-4" />
                  {saving ? 'Saving…' : 'Save Changes'}
                </button>
              </div>
            </form>
          </Card>

          {/* Notifications */}
          <Card>
            <SectionHeader icon={Zap} title="Notifications" />
            <div className="p-6 space-y-5">
              {[
                { key: 'emailScreening',    label: 'Email me when screening is complete',     sub: 'Get notified when AI screening finishes' },
                { key: 'inAppApplications', label: 'In-app notifications for new applications', sub: 'Show notifications when candidates apply' },
                { key: 'weeklyReports',     label: 'Weekly email reports',                     sub: 'Receive weekly summary of activities' },
                { key: 'jobPostingUpdates', label: 'Job posting updates',                      sub: 'Get notified about changes to job postings' },
                { key: 'candidateShortlist',label: 'Candidate shortlisted notifications',      sub: 'Email when candidates are shortlisted' },
              ].map(({ key, label, sub }) => (
                <div key={key} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{label}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{sub}</p>
                  </div>
                  <Toggle checked={notifs[key]} onChange={val => setNotif(key, val)} />
                </div>
              ))}
              <div className="flex justify-end pt-2 border-t border-slate-100">
                <button
                  onClick={handleSaveNotifs}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-white"
                  style={{ background: C.accent }}
                >
                  <Save className="h-4 w-4" /> Save Preferences
                </button>
              </div>
            </div>
          </Card>

          {/* AI Parameters */}
          <Card>
            <SectionHeader icon={Star} title="AI Parameters" />
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                {[
                  { key: 'defaultJobActive', label: 'Default Job Status', sub: 'Set new pipelines to Active' },
                  { key: 'highScoreAlerts',  label: 'High Score Alerts',  sub: 'Match threshold > 90%' },
                ].map(({ key, label, sub }) => (
                  <div
                    key={key}
                    className="flex items-center justify-between p-4 rounded-xl border border-slate-200"
                  >
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{label}</p>
                      <p className="text-xs text-slate-400 mt-0.5">{sub}</p>
                    </div>
                    <Toggle checked={aiParams[key]} onChange={val => setAi(key, val)} />
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </div>

        {/* ── RIGHT COL ── */}
        <div className="flex flex-col gap-5">

          {/* AI Efficiency Index */}
          <div
            className="rounded-2xl p-5"
            style={{ background: `linear-gradient(135deg, ${C.primary} 0%, #312e81 60%, ${C.accent} 100%)` }}
          >
            <div className="flex items-center gap-2 mb-3">
              <Zap className="h-4 w-4" style={{ color: C.cyan }} />
              <p className="text-xs font-bold uppercase tracking-widest" style={{ color: '#818cf8' }}>
                AI Efficiency Index
              </p>
            </div>
            <div className="flex items-center gap-4 mb-3">
              <ScoreRing value={94} />
              <div>
                <p className="text-4xl font-black text-white leading-none">94.2<span className="text-lg font-semibold" style={{ color: '#818cf8' }}>%</span></p>
                <p className="text-xs mt-1 leading-snug" style={{ color: '#c7d2fe' }}>
                  Your matching accuracy is 12% higher than the global benchmark.
                </p>
              </div>
            </div>
            <div className="space-y-1.5 pt-3 border-t border-indigo-700">
              {[
                { label: 'Interview Rate', value: '74%' },
                { label: 'Precision Score', value: '96%' },
              ].map(({ label, value }) => (
                <div key={label} className="flex items-center justify-between text-xs">
                  <span style={{ color: '#a5b4fc' }}>{label}</span>
                  <div className="flex items-center gap-2">
                    <div className="h-1 w-20 rounded-full bg-indigo-800 overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: value, background: C.cyan }} />
                    </div>
                    <span className="font-bold text-white">{value}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Security */}
          <Card>
            <SectionHeader icon={Shield} title="Security" />
            <div className="p-4 space-y-3">
              {/* Account Password */}
              <div className="p-3 rounded-xl border border-slate-200 hover:border-indigo-200 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Key className="h-4 w-4 text-slate-400" />
                    <div>
                      <p className="text-sm font-semibold text-slate-900">Account Password</p>
                    </div>
                  </div>
                  <button className="text-xs font-bold" style={{ color: C.accent }}>Change</button>
                </div>
              </div>

              {/* MFA */}
              <div className="p-3 rounded-xl border border-slate-200">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Smartphone className="h-4 w-4 text-slate-400" />
                    <div>
                      <p className="text-sm font-semibold text-slate-900">Multi-factor Auth</p>
                      <p className="text-xs text-slate-400">Added security layer</p>
                    </div>
                  </div>
                  <Toggle checked={false} onChange={() => toast({ title: 'MFA setup coming soon' })} />
                </div>
              </div>

              {/* Active sessions */}
              <div className="p-3 rounded-xl border border-slate-200">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Monitor className="h-4 w-4 text-slate-400" />
                    <div>
                      <p className="text-sm font-semibold text-slate-900">Active Sessions</p>
                      <p className="text-xs flex items-center gap-1 mt-0.5">
                        <span className="text-slate-400">Mac Book Pro · London, UK</span>
                        <span className="font-bold text-green-500">· Active Now</span>
                      </p>
                    </div>
                  </div>
                  <ChevronRight className="h-4 w-4 text-slate-300" />
                </div>
              </div>
            </div>
          </Card>

          {/* Curator Tip */}
          <div className="rounded-2xl border border-indigo-100 p-4" style={{ background: '#f5f3ff' }}>
            <div className="flex items-start gap-3">
              <div className="h-8 w-8 rounded-full flex items-center justify-center shrink-0" style={{ background: C.primary }}>
                <Zap className="h-4 w-4 text-white" />
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-widest mb-1" style={{ color: C.accent }}>Curator Tip</p>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Regularly auditing your AI matching thresholds ensures that high-quality candidates
                  aren't filtered out by overly restrictive initial parameters.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Profile;