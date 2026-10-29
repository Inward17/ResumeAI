import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/use-toast';
import { previewInvite, acceptInvite } from '../services/orgService';
import { Card, Button, EmptyState, PageContainer } from './common';

/** /join/:token — accept an invitation (the route is behind sign-in, so the invitee signs in first) */
const JoinOrg = () => {
  const { token } = useParams();
  const { user, logout } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [invite, setInvite] = useState(null);
  const [error, setError] = useState(null);
  const [joining, setJoining] = useState(false);

  useEffect(() => {
    previewInvite(token).then(setInvite).catch((err) => setError(err.message));
  }, [token]);

  const join = async () => {
    setJoining(true);
    try {
      await acceptInvite(token);
      toast({ title: `Welcome to ${invite.org_name}` });
      window.dispatchEvent(new Event('resumeai:org'));
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(err.message);
      setJoining(false);
    }
  };

  const switchAccount = async () => {
    await logout();
    navigate('/login', { state: { from: { pathname: `/join/${token}` } } });
  };

  return (
    <PageContainer className="flex min-h-full max-w-lg items-center">
      <Card className="w-full">
        {error ? (
          <EmptyState icon={AlertTriangle} title="Can't join this workspace" description={error}
            action={<Button variant="secondary" onClick={() => navigate('/dashboard')}>Go to your workspace</Button>} />
        ) : !invite ? (
          <div className="flex justify-center p-12"><Loader2 className="h-5 w-5 animate-spin text-ink-3" aria-label="Loading invitation" /></div>
        ) : (
          <div className="p-8 text-center">
            <p className="text-xs font-medium uppercase tracking-[0.08em] text-ink-3">Invitation</p>
            <h1 className="mt-2 font-serif text-4xl leading-tight text-ink">Join {invite.org_name}</h1>
            <p className="mt-2 text-sm text-ink-3">
              {invite.invited_by} invited <span className="text-ink-2">{invite.email}</span> as {invite.role === 'admin' ? 'an admin' : 'a member'}.
              You'll share the workspace's jobs and candidates.
            </p>
            {invite.email_matches ? (
              <Button size="lg" className="mt-6 w-full" onClick={join} disabled={joining}>
                {joining ? 'Joining…' : `Join ${invite.org_name}`}
              </Button>
            ) : (
              <div className="mt-6 rounded-md border border-warning/30 bg-warning-soft p-3 text-left text-sm text-warning">
                You're signed in as {user?.email}. Sign in with {invite.email} to accept.
                <Button variant="secondary" size="sm" className="mt-2 w-full" onClick={switchAccount}>Switch account</Button>
              </div>
            )}
          </div>
        )}
      </Card>
    </PageContainer>
  );
};

export default JoinOrg;
