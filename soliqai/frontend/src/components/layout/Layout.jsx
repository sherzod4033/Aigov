import React from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
    Bell,
    ChartNoAxesCombined,
    FileText,
    LogOut,
    MessageSquare,
    Search,
    Settings,
    ShieldCheck,
    UserCircle2,
} from 'lucide-react';
import { cn } from '../../lib/utils';

const NAV_ITEMS = [
    { name: 'Чат', href: '/', icon: MessageSquare },
    { name: 'Документы', href: '/admin/documents', icon: FileText },
    { name: 'Логи', href: '/admin/logs', icon: ChartNoAxesCombined },
    { name: 'Настройки', href: '/settings', icon: Settings },
];

const resolvePageMeta = (pathname) => {
    if (pathname === '/') {
        return { title: 'SoliqAI', badge: 'Налоговый помощник', searchPlaceholder: 'Введите ваш вопрос...' };
    }
    if (pathname.startsWith('/admin/documents')) {
        return { title: 'Документы', badge: 'Центр документов', searchPlaceholder: 'Поиск документов...' };
    }
    if (pathname.startsWith('/admin/logs')) {
        return { title: 'Логи и Аналитика', badge: 'Мониторинг', searchPlaceholder: 'Поиск по ID запроса...' };
    }
    if (pathname.startsWith('/settings')) {
        return { title: 'Настройки', badge: 'Система', searchPlaceholder: 'Поиск пользователей...' };
    }

    return { title: 'SoliqAI', badge: 'Портал', searchPlaceholder: 'Поиск...' };
};

const isActiveLink = (pathname, href) => pathname === href || (href !== '/' && pathname.startsWith(`${href}/`));

const Layout = () => {
    const location = useLocation();
    const navigate = useNavigate();

    const pageMeta = resolvePageMeta(location.pathname);

    const handleLogout = () => {
        localStorage.removeItem('token');
        navigate('/login', { replace: true });
    };

    return (
        <div className="min-h-screen bg-[#f3f5f8] lg:flex lg:h-screen lg:overflow-hidden">
            <aside className="hidden w-64 flex-col bg-[#1f3a60] text-white lg:flex lg:h-screen">
                <div className="flex h-16 items-center gap-3 border-b border-white/10 px-5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#c5a059] text-sm font-extrabold text-[#1f3a60] shadow-lg">
                        S
                    </div>
                    <div>
                        <p className="text-2xl font-bold leading-none">SoliqAI</p>
                    </div>
                </div>

                <nav className="flex-1 space-y-1 px-3 py-5">
                    {NAV_ITEMS.map((item) => {
                        const Icon = item.icon;
                        const active = isActiveLink(location.pathname, item.href);

                        return (
                            <Link
                                key={item.name}
                                to={item.href}
                                className={cn(
                                    'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold transition-all',
                                    active
                                        ? 'bg-white/12 text-[#c5a059] shadow-[inset_3px_0_0_0_#c5a059]'
                                        : 'text-slate-200/85 hover:bg-white/8 hover:text-white',
                                )}
                            >
                                <Icon className={cn('h-[18px] w-[18px]', active ? 'text-[#c5a059]' : 'text-slate-300 group-hover:text-white')} />
                                {item.name}
                            </Link>
                        );
                    })}
                </nav>

                <div className="border-t border-white/10 p-4">
                    <div className="mb-3 flex items-center gap-3 rounded-xl bg-white/5 p-2.5">
                        <UserCircle2 className="h-9 w-9 text-slate-300" />
                        <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-white">Admin User</p>
                            <p className="truncate text-xs text-slate-300">admin@soliq.tj</p>
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={handleLogout}
                        className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/20 px-3 py-2 text-sm font-semibold text-white transition hover:bg-white/10"
                    >
                        <LogOut className="h-4 w-4" />
                        Выйти
                    </button>
                </div>
            </aside>

            <div className="flex min-h-screen flex-1 flex-col lg:h-screen">
                <header className="border-b border-slate-200 bg-white px-4 py-3 sm:px-6 lg:px-8">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex items-center gap-3">
                            <div className="lg:hidden flex h-8 w-8 items-center justify-center rounded-lg bg-[#1f3a60] text-sm font-extrabold text-[#c5a059]">
                                S
                            </div>
                            <div className="flex items-center gap-3">
                                <h1 className="text-xl lg:text-2xl font-extrabold text-[#1f3a60]">{pageMeta.title}</h1>
                                <span className="rounded-full bg-[#1f3a60]/10 px-2.5 py-0.5 text-[10px] lg:text-xs font-bold text-[#1f3a60]">
                                    {pageMeta.badge}
                                </span>
                            </div>
                        </div>

                        <div className="flex w-full items-center gap-3 sm:w-auto">
                            <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1 mr-2">
                                <button type="button" className="rounded-md bg-white px-2 py-0.5 text-[10px] font-bold text-[#1f3a60] shadow-sm">TJ</button>
                                <button type="button" className="rounded-md px-2 py-0.5 text-[10px] font-bold text-slate-500">RU</button>
                            </div>

                            <div className="relative flex-1 sm:w-64 sm:flex-none">
                                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                                <input
                                    type="text"
                                    placeholder={pageMeta.searchPlaceholder}
                                    className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 pl-9 pr-3 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1f3a60]/30"
                                />
                            </div>

                            <div className="hidden items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-500 xl:flex">
                                <span className="mr-2 inline-block h-2 w-2 rounded-full bg-green-500"></span>
                                Система работает
                            </div>

                            <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50 hover:text-[#1f3a60]">
                                <Bell className="h-4 w-4" />
                            </button>

                            <button
                                type="button"
                                onClick={handleLogout}
                                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50 hover:text-red-600 lg:hidden"
                                aria-label="Logout"
                            >
                                <LogOut className="h-4 w-4" />
                            </button>
                        </div>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2 lg:hidden">
                        {NAV_ITEMS.map((item) => (
                            <Link
                                key={item.name}
                                to={item.href}
                                className={cn(
                                    'rounded-lg border px-3 py-1 text-[11px] font-semibold',
                                    isActiveLink(location.pathname, item.href)
                                        ? 'border-[#1f3a60] bg-[#1f3a60] text-white'
                                        : 'border-slate-300 bg-white text-slate-600'
                                )}
                            >
                                {item.name}
                            </Link>
                        ))}
                    </div>
                </header>

                <main className="soft-grid flex-1 overflow-auto">
                    <Outlet />
                </main>
            </div>
        </div>
    );
};

export default Layout;
