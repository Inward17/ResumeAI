import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Loader2, Mail, Lock, AlertCircle } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { cn } from '../../lib/utils';
import { AuthShell, AuthAlert, authInput, GoogleIcon, Divider } from './AuthShell';
import { Button } from '../common';

const strengthOf = (password) => {
    if (!password) return null;
    const variety = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(password)).length;
    if (password.length < 8) return { label: 'Too short', bar: 'bg-danger w-1/4', text: 'text-danger' };
    if (password.length < 12 && variety < 3) return { label: 'Fair', bar: 'bg-warning w-2/4', text: 'text-warning' };
    if (variety < 3) return { label: 'Good', bar: 'bg-primary w-3/4', text: 'text-primary-text' };
    return { label: 'Strong', bar: 'bg-success w-full', text: 'text-success' };
};

const Register = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [googleLoading, setGoogleLoading] = useState(false);

    const { register, loginWithGoogle } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    // e.g. back to an invitation link after signing up
    const destination = location.state?.from?.pathname || '/dashboard';
    const strength = strengthOf(password);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        if (password.length < 8) return setError('Use at least 8 characters for your password.');
        if (password !== confirmPassword) return setError('The passwords don’t match.');
        setLoading(true);
        const result = await register(email, password);
        setLoading(false);
        if (result.success) navigate(destination, { replace: true });
        else setError(result.error);
        return undefined;
    };

    const handleGoogleLogin = async () => {
        setError('');
        setGoogleLoading(true);
        const result = await loginWithGoogle();
        setGoogleLoading(false);
        if (result.success) navigate(destination, { replace: true });
        else setError(result.error);
    };

    const busy = loading || googleLoading;

    return (
        <AuthShell
            title="Create your account"
            subtitle="Start screening candidates in minutes."
            footer={<>Already have an account? <Link to="/login" state={location.state} className="font-medium text-primary-text hover:underline">Sign in</Link></>}
        >
            {error && (
                <AuthAlert><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />{error}</AuthAlert>
            )}

            <Button variant="secondary" size="lg" onClick={handleGoogleLogin} disabled={busy} className="w-full">
                {googleLoading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <GoogleIcon />}
                Sign up with Google
            </Button>

            <Divider />

            <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                    <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-ink-2">Work email</label>
                    <div className="relative">
                        <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
                        <input id="email" type="email" autoComplete="email" required placeholder="name@company.com"
                            value={email} onChange={(e) => setEmail(e.target.value)} className={authInput} />
                    </div>
                </div>
                <div>
                    <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-ink-2">Password</label>
                    <div className="relative">
                        <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
                        <input id="password" type="password" autoComplete="new-password" required placeholder="At least 8 characters"
                            aria-describedby="password-strength" value={password} onChange={(e) => setPassword(e.target.value)} className={authInput} />
                    </div>
                    {strength && (
                        <div id="password-strength" className="mt-2 flex items-center gap-3">
                            <div className="h-1 flex-1 overflow-hidden rounded-full bg-subtle">
                                <div className={cn('h-full rounded-full transition-all', strength.bar)} />
                            </div>
                            <span className={cn('text-xs font-semibold', strength.text)}>{strength.label}</span>
                        </div>
                    )}
                </div>
                <div>
                    <label htmlFor="confirm-password" className="mb-1.5 block text-sm font-medium text-ink-2">Confirm password</label>
                    <div className="relative">
                        <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" aria-hidden="true" />
                        <input id="confirm-password" type="password" autoComplete="new-password" required placeholder="Repeat your password"
                            value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className={authInput} />
                    </div>
                </div>
                <Button type="submit" size="lg" disabled={busy} className="w-full">
                    {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
                    {loading ? 'Creating account…' : 'Create account'}
                </Button>
            </form>
        </AuthShell>
    );
};

export default Register;
