import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Loader2, Mail, Lock, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Checkbox } from '../ui/checkbox';
import { AuthShell, AuthAlert, authInput, GoogleIcon, Divider } from './AuthShell';
import { Button } from '../common';
import { redirectTarget } from './ProtectedRoute';

const Login = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [rememberMe, setRememberMe] = useState(true);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [loading, setLoading] = useState(false);
    const [googleLoading, setGoogleLoading] = useState(false);

    const { login, loginWithGoogle, resetPassword } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const destination = redirectTarget(location);

    const finish = (result) => {
        if (result.success) navigate(destination, { replace: true });
        else setError(result.error);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setNotice('');
        setLoading(true);
        finish(await login(email, password, rememberMe));
        setLoading(false);
    };

    const handleGoogleLogin = async () => {
        setError('');
        setNotice('');
        setGoogleLoading(true);
        finish(await loginWithGoogle());
        setGoogleLoading(false);
    };

    const handleForgotPassword = async () => {
        setError('');
        setNotice('');
        if (!email) {
            setError('Enter your email address above, then choose "Forgot password?" again.');
            return;
        }
        const result = await resetPassword(email);
        if (result.success) setNotice(`If an account exists for ${email}, a reset link is on its way.`);
        else setError(result.error);
    };

    const busy = loading || googleLoading;

    return (
        <AuthShell
            title="Welcome back"
            subtitle="Sign in to your ResumeAI workspace."
            footer={<>Don&apos;t have an account? <Link to="/register" state={location.state} className="font-medium text-primary-text hover:underline">Create one</Link></>}
        >
            {error && (
                <AuthAlert><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />{error}</AuthAlert>
            )}
            {notice && (
                <AuthAlert tone="success"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />{notice}</AuthAlert>
            )}

            <Button variant="secondary" size="lg" onClick={handleGoogleLogin} disabled={busy} className="w-full">
                {googleLoading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <GoogleIcon />}
                Continue with Google
            </Button>

            <Divider />

            <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                    <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-ink-2">Email</label>
                    <div className="relative">
                        <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
                        <input id="email" type="email" autoComplete="email" required placeholder="name@company.com"
                            value={email} onChange={(e) => setEmail(e.target.value)} className={authInput} />
                    </div>
                </div>
                <div>
                    <div className="mb-1.5 flex items-center justify-between">
                        <label htmlFor="password" className="text-sm font-medium text-ink-2">Password</label>
                        <button type="button" onClick={handleForgotPassword} className="text-sm font-medium text-primary-text hover:underline">
                            Forgot password?
                        </button>
                    </div>
                    <div className="relative">
                        <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
                        <input id="password" type="password" autoComplete="current-password" required placeholder="Your password"
                            value={password} onChange={(e) => setPassword(e.target.value)} className={authInput} />
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Checkbox id="remember" checked={rememberMe} onCheckedChange={(v) => setRememberMe(v === true)}
                         />
                    <label htmlFor="remember" className="cursor-pointer text-sm text-ink-2">Keep me signed in</label>
                </div>
                <Button type="submit" size="lg" disabled={busy} className="w-full">
                    {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
                    {loading ? 'Signing in…' : 'Sign in'}
                </Button>
            </form>
        </AuthShell>
    );
};

export default Login;
