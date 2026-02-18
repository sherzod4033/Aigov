import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { Eye, EyeOff, Lock, Shield, User } from 'lucide-react';
import api from '../services/api';
import { Button } from '../components/ui/Button';
import Input from '../components/ui/Input';
import { Card, CardContent, CardFooter, CardHeader } from '../components/ui/Card';

const LoginPage = () => {
    const navigate = useNavigate();
    const {
        register,
        handleSubmit,
        formState: { errors },
    } = useForm();

    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [showPassword, setShowPassword] = useState(false);

    const onSubmit = async (data) => {
        setIsLoading(true);
        setError('');

        try {
            const formData = new FormData();
            formData.append('username', data.username);
            formData.append('password', data.password);

            const response = await api.post('/auth/login/access-token', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });

            localStorage.setItem('token', response.data.access_token);
            navigate('/');
        } catch (err) {
            console.error(err);
            setError('Неверное имя пользователя или пароль');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="login-pattern relative min-h-screen overflow-hidden px-4 py-6 text-slate-100">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.08),transparent_64%)]" />

            <div className="relative mx-auto flex min-h-[calc(100vh-3rem)] max-w-6xl flex-col">
                <header className="flex justify-end">
                    <div className="inline-flex items-center gap-1 rounded-lg border border-white/20 bg-white/10 p-1 text-xs font-semibold">
                        <button type="button" className="rounded-md bg-white px-3 py-1 text-[#1f3a60]">TJ</button>
                        <button type="button" className="rounded-md px-3 py-1 text-white/80">RU</button>
                    </div>
                </header>

                <main className="flex flex-1 items-center justify-center py-8">
                    <Card className="w-full max-w-md overflow-hidden border-none bg-white text-slate-800 shadow-[0_28px_60px_rgba(8,20,42,0.45)]">
                        <div className="h-1.5 w-full bg-[#c5a059]" />

                        <CardHeader className="items-center pb-3 pt-8 text-center">
                            <div className="mb-3 flex items-center gap-3">
                                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#1f3a60] text-[#c5a059] shadow-sm">
                                    <Shield className="h-6 w-6" />
                                </div>
                                <div className="text-left">
                                    <p className="text-4xl font-extrabold leading-none text-[#1f3a60]">Soliq<span className="text-[#c5a059]">AI</span></p>
                                    <p className="mt-1 text-sm font-semibold text-slate-500">Умный налоговый помощник</p>
                                </div>
                            </div>
                        </CardHeader>

                        <CardContent>
                            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                                <div>
                                    <label htmlFor="username" className="mb-1 block text-sm font-semibold text-[#1f3a60]">
                                        Имя пользователя
                                    </label>
                                    <div className="relative">
                                        <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                                        <Input
                                            id="username"
                                            className="h-11 pl-9"
                                            placeholder="user@soliq.tj"
                                            {...register('username', { required: 'Введите имя пользователя' })}
                                        />
                                    </div>
                                    {errors.username && <p className="mt-1 text-xs font-medium text-red-600">{errors.username.message}</p>}
                                </div>

                                <div>
                                    <label htmlFor="password" className="mb-1 block text-sm font-semibold text-[#1f3a60]">
                                        Пароль
                                    </label>
                                    <div className="relative">
                                        <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                                        <Input
                                            id="password"
                                            type={showPassword ? 'text' : 'password'}
                                            className="h-11 pl-9 pr-10"
                                            placeholder="••••••••"
                                            {...register('password', { required: 'Введите пароль' })}
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShowPassword((prev) => !prev)}
                                            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                                            aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                                        >
                                            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                        </button>
                                    </div>
                                    {errors.password && <p className="mt-1 text-xs font-medium text-red-600">{errors.password.message}</p>}
                                </div>

                                <div className="flex items-center justify-between text-sm">
                                    <label className="inline-flex items-center gap-2 text-slate-600">
                                        <input type="checkbox" className="h-4 w-4 rounded border-slate-300 text-[#1f3a60] focus:ring-[#1f3a60]/30" />
                                        Дар хотир нигоҳ дор
                                    </label>
                                    <button type="button" className="font-semibold text-[#1f3a60] hover:text-[#162945]">
                                        Забыли пароль?
                                    </button>
                                </div>

                                {error && (
                                    <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">
                                        {error}
                                    </div>
                                )}

                                <Button type="submit" className="h-11 w-full text-[13px] tracking-[0.08em]" isLoading={isLoading}>
                                    ВОЙТИ
                                </Button>
                            </form>
                        </CardContent>

                        <CardFooter className="justify-center border-t border-slate-100 pb-7 pt-5 text-sm text-slate-500">
                            <span>
                                Нужна помощь?{' '}
                                <Link to="/register" className="font-semibold text-[#1f3a60] hover:text-[#162945]">
                                    Техническая поддержка
                                </Link>
                            </span>
                        </CardFooter>
                    </Card>
                </main>

                <footer className="pb-2 text-center text-xs font-medium text-white/55">
                    © 2026 Правительство Республики Таджикистан. Все права защищены.
                </footer>
            </div>
        </div>
    );
};

export default LoginPage;
