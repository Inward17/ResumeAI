import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, Mail, Shield, KeyRound, Bell, LogOut, Save, Smartphone } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/use-toast';
import { Avatar, AvatarImage, AvatarFallback } from './ui/avatar';
import { Card, CardHeader, PageContainer, PageHeader, PrimaryButton, SecondaryButton, ComingSoon, formatDate } from './common';

const PROVIDER_LABELS = { 'google.com': 'Google', password: 'Email and password' };

const InfoRow = ({ label, children }) => (
  <div className="flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between">
    <dt className="text-sm text-slate-600">{label}</dt>
    <dd className="text-sm font-semibold text-slate-900">{children}</dd>
  </div>
);

const Profile = () => {
  const { user, updateDisplayName, resetPassword, logout } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [name, setName] = useState(user?.displayName || '');
  const [saving, setSaving] = useState(false);
  const [sendingReset, setSendingReset] = useState(false);

  const providers = (user?.providerData || []).map((p) => p.providerId);
  const hasPassword = providers.includes('password');
  const displayName = user?.displayName || user?.email?.split('@')[0] || 'Your account';
  const nameChanged = name.trim() && name.trim() !== (user?.displayName || '');

  const handleSaveName = async (e) => {
    e.preventDefault();
    if (!nameChanged) return;
    setSaving(true);
    const result = await updateDisplayName(name.trim());
    setSaving(false);
    toast(result.success
      ? { title: 'Name updated' }
      : { title: 'Could not update name', description: result.error, variant: 'destructive' });
  };

  const handleResetPassword = async () => {
    setSendingReset(true);
    const result = await resetPassword(user.email);
    setSendingReset(false);
    toast(result.success
      ? { title: 'Password reset email sent', description: `Check ${user.email} for a link to set a new password.` }
      : { title: 'Could not send reset email', description: result.error, variant: 'destructive' });
  };

  const handleLogout = async () => {
    const result = await logout();
    if (result.success) navigate('/login');
  };

  return (
    <PageContainer>
      <PageHeader eyebrow="Account" title="Your account" description="Your profile and sign-in settings." />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          <Card>
            <CardHeader title="Profile" subtitle="How your name appears in ResumeAI." />
            <form onSubmit={handleSaveName} className="space-y-5 p-5 md:p-6">
              <div className="flex items-center gap-4">
                <Avatar className="h-14 w-14 border-2 border-brand">
                  {user?.photoURL && <AvatarImage src={user.photoURL} alt="" />}
                  <AvatarFallback className="bg-brand text-lg font-bold text-white">{displayName.charAt(0).toUpperCase()}</AvatarFallback>
                </Avatar>
                <div className="min-w-0">
                  <p className="truncate font-semibold text-slate-900">{displayName}</p>
                  <p className="truncate text-sm text-slate-600">{user?.email}</p>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label htmlFor="display-name" className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-slate-600">Full name</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
                    <input id="display-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name"
                      className="w-full rounded-xl border border-slate-200 py-2.5 pl-9 pr-3 text-sm text-slate-900 outline-none focus:border-brand-accent focus:ring-2 focus:ring-brand-soft" />
                  </div>
                </div>
                <div>
                  <label htmlFor="email" className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-slate-600">Email</label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
                    <input id="email" value={user?.email || ''} readOnly aria-describedby="email-help"
                      className="w-full cursor-not-allowed rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-9 pr-3 text-sm text-slate-700" />
                  </div>
                  <p id="email-help" className="mt-1 text-xs text-slate-500">Your sign-in email can&apos;t be changed here.</p>
                </div>
              </div>
              <div className="flex justify-end">
                <PrimaryButton type="submit" disabled={!nameChanged || saving}>
                  <Save className="h-4 w-4" aria-hidden="true" /> {saving ? 'Saving…' : 'Save name'}
                </PrimaryButton>
              </div>
            </form>
          </Card>

          <Card>
            <CardHeader title="Notifications" subtitle="Email alerts when screening finishes or candidates are shortlisted." action={<ComingSoon />} />
            <p className="flex items-center gap-2 p-5 text-sm text-slate-600 md:p-6">
              <Bell className="h-4 w-4 text-slate-500" aria-hidden="true" />
              Notification preferences are not available yet. Screening progress is shown live on each job&apos;s pipeline page.
            </p>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Sign-in & security" />
            <dl className="divide-y divide-slate-100 px-5 md:px-6">
              <InfoRow label="Sign-in method">{providers.map((p) => PROVIDER_LABELS[p] || p).join(', ') || '—'}</InfoRow>
              <InfoRow label="Account created">{formatDate(user?.metadata?.creationTime)}</InfoRow>
              <InfoRow label="Last sign-in">{formatDate(user?.metadata?.lastSignInTime)}</InfoRow>
            </dl>
            <div className="space-y-3 border-t border-slate-100 p-5 md:p-6">
              <div className="flex items-start gap-3">
                <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-900">Password</p>
                  {hasPassword ? (
                    <SecondaryButton onClick={handleResetPassword} disabled={sendingReset} className="mt-2 px-3 py-2 text-xs">
                      {sendingReset ? 'Sending…' : 'Email me a reset link'}
                    </SecondaryButton>
                  ) : (
                    <p className="text-xs text-slate-600">Managed by your Google account.</p>
                  )}
                </div>
              </div>
              <div className="flex items-start gap-3">
                <Smartphone className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
                <div className="flex flex-1 items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-900">Two-factor authentication</p>
                  <ComingSoon />
                </div>
              </div>
              <div className="flex items-start gap-3">
                <Shield className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
                <p className="text-xs text-slate-600">Your jobs and candidates are private to your account. Every request to the API is verified with your sign-in token.</p>
              </div>
            </div>
          </Card>

          <SecondaryButton onClick={handleLogout} className="w-full text-red-700 hover:bg-red-50">
            <LogOut className="h-4 w-4" aria-hidden="true" /> Log out
          </SecondaryButton>
        </div>
      </div>
    </PageContainer>
  );
};

export default Profile;
