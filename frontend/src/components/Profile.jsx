import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, LogOut } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/use-toast';
import { UserAvatar } from './Sidebar';
import { Card, CardHeader, PageContainer, PageHeader, Button, Field, Input, ComingSoon, formatDate } from './common';

const PROVIDER_LABELS = { 'google.com': 'Google', password: 'Email and password' };

const Row = ({ label, children }) => (
  <div className="flex flex-col gap-1 px-5 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
    <dt className="text-sm text-ink-3">{label}</dt>
    <dd className="text-sm font-medium text-ink">{children}</dd>
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
    <PageContainer className="max-w-3xl">
      <PageHeader title="Your account" description="Your profile and sign-in settings." />

      <div className="space-y-6">
        <Card>
          <CardHeader title="Profile" />
          <form onSubmit={handleSaveName}>
            <div className="space-y-5 p-5">
              <div className="flex items-center gap-4">
                <UserAvatar user={user} className="h-12 w-12 text-base" />
                <div className="min-w-0">
                  <p className="truncate font-medium text-ink">{displayName}</p>
                  <p className="truncate text-sm text-ink-3">{user?.email}</p>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Full name" htmlFor="display-name">
                  <Input id="display-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" autoComplete="name" />
                </Field>
                <Field label="Email" htmlFor="email" hint="Your sign-in email can't be changed here.">
                  <Input id="email" value={user?.email || ''} disabled />
                </Field>
              </div>
            </div>
            <div className="flex justify-end border-t border-line bg-subtle/50 px-5 py-3">
              <Button type="submit" disabled={!nameChanged || saving}>{saving ? 'Saving…' : 'Save name'}</Button>
            </div>
          </form>
        </Card>

        <Card>
          <CardHeader title="Sign-in & security" />
          <dl className="divide-y divide-line">
            <Row label="Sign-in method">{providers.map((p) => PROVIDER_LABELS[p] || p).join(', ') || '—'}</Row>
            <Row label="Password">
              {hasPassword ? (
                <Button variant="secondary" size="sm" onClick={handleResetPassword} disabled={sendingReset}>
                  {sendingReset ? 'Sending…' : 'Email me a reset link'}
                </Button>
              ) : <span className="font-normal text-ink-3">Managed by your Google account</span>}
            </Row>
            <Row label="Two-factor authentication"><ComingSoon /></Row>
            <Row label="Account created">{formatDate(user?.metadata?.creationTime)}</Row>
            <Row label="Last sign-in">{formatDate(user?.metadata?.lastSignInTime)}</Row>
          </dl>
          <p className="flex items-start gap-2 border-t border-line px-5 py-3 text-xs text-ink-3">
            <Shield className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            Your jobs and candidates are private to your account. Every request to the API is verified with your sign-in token.
          </p>
        </Card>

        <Card>
          <CardHeader title="Notifications" action={<ComingSoon />} />
          <p className="p-5 text-sm text-ink-3">
            Email alerts when screening finishes or candidates are shortlisted. Until then, progress is shown live on each job&apos;s pipeline.
          </p>
        </Card>

        <Card className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-ink">Log out</p>
            <p className="text-sm text-ink-3">End your session on this device.</p>
          </div>
          <Button variant="danger-outline" onClick={handleLogout}><LogOut aria-hidden="true" /> Log out</Button>
        </Card>
      </div>
    </PageContainer>
  );
};

export default Profile;
