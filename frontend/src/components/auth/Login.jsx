import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Loader2, Mail, Lock, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Checkbox } from '../ui/checkbox';
import { AuthShell, authInput, GoogleIcon, Divider } from './AuthShell';
import { PrimaryButton, SecondaryButton } from '../common';

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
    const destination = location.state?.from?.pathname || '/dashboard';

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
            footer={<>Don&apos;t have an account? <Link to="/register" className="font-semibold text-brand-accent hover:underline">Create one</Link></>}
        >
            {error && (
                <div role="alert" className="mb-4 flex items-start gap-2 rounded-xl bg-red-50 px-3 py-2.5 text-sm text-red-800 ring-1 ring-inset ring-red-200">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />{error}
                </div>
            )}
            {notice && (
                <div role="status" className="mb-4 flex items-start gap-2 rounded-xl bg-emerald-50 px-3 py-2.5 text-sm text-emerald-800 ring-1 ring-inset ring-emerald-200">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />{notice}
                </div>
            )}

            <SecondaryButton onClick={handleGoogleLogin} disabled={busy} className="w-full">
                {googleLoading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <GoogleIcon />}
                Continue with Google
            </SecondaryButton>

            <Divider />

            <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                    <label htmlFor="email" className="mb-1.5 block text-sm font-semibold text-slate-700">Email</label>
                    <div className="relative">
                        <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
                        <input id="email" type="email" autoComplete="email" required placeholder="name@company.com"
                            value={email} onChange={(e) => setEmail(e.target.value)} className={authInput} />
                    </div>
                </div>
                <div>
                    <div className="mb-1.5 flex items-center justify-between">
                        <label htmlFor="password" className="text-sm font-semibold text-slate-700">Password</label>
                        <button type="button" onClick={handleForgotPassword} className="text-sm font-semibold text-brand-accent hover:underline">
                            Forgot password?
                        </button>
                    </div>
                    <div className="relative">
                        <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
                        <input id="password" type="password" autoComplete="current-password" required placeholder="Your password"
                            value={password} onChange={(e) => setPassword(e.target.value)} className={authInput} />
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Checkbox id="remember" checked={rememberMe} onCheckedChange={(v) => setRememberMe(v === true)}
                        className="border-slate-300 data-[state=checked]:border-brand data-[state=checked]:bg-brand" />
                    <label htmlFor="remember" className="cursor-pointer text-sm text-slate-700">Keep me signed in</label>
                </div>
                <PrimaryButton type="submit" disabled={busy} className="w-full">
                    {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
                    {loading ? 'Signing in…' : 'Sign in'}
                </PrimaryButton>
            </form>
        </AuthShell>
    );
};

export default Login;
