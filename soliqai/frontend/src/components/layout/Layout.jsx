import React, { useEffect, useMemo, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import {
    ChevronLeft,
    ChevronRight,
    Bookmark,
    CalendarDays,
    ChartNoAxesCombined,
    Clock3,
    FileText,
    LogOut,
    MessageSquare,
    Settings,
    Trash2,
    UserCircle2,
} from 'lucide-react';
import { Button } from '../ui/Button';
import { cn } from '../../lib/utils';
import { NotebookHeaderContext } from './NotebookHeaderContext';

const NAV_ITEMS = [
    { name: 'Все источники', href: '/sources', icon: FileText },
    { name: 'Блокноты', href: '/notebooks', icon: Bookmark },
    { name: 'Чат', href: '/chat', icon: MessageSquare },
    { name: 'Логи', href: '/admin/logs', icon: ChartNoAxesCombined },
    { name: 'Настройки', href: '/settings', icon: Settings },
];

const resolvePageMeta = (pathname) => {
    if (pathname === '/' || pathname.startsWith('/chat')) {
        return { title: 'KnowledgeAI', badge: 'AI over sources', searchPlaceholder: 'Введите ваш вопрос...' };
    }
    if (pathname.startsWith('/ask')) {
        return { title: 'Ask', badge: 'One-shot analysis', searchPlaceholder: 'Поиск Ask запросов...' };
    }
    if (pathname.startsWith('/notes')) {
        return { title: 'Notes', badge: 'Knowledge capture', searchPlaceholder: 'Поиск notes...' };
    }
    if (pathname.startsWith('/insights')) {
        return { title: 'Insights', badge: 'Structured findings', searchPlaceholder: 'Поиск insights...' };
    }
    if (/^\/notebooks\/[^/]+(\/|$)/.test(pathname)) {
        return { title: 'Блокнот', badge: 'Контекст', searchPlaceholder: 'Поиск внутри блокнота...' };
    }
    if (pathname.startsWith('/notebooks')) {
        return { title: 'Блокноты', badge: 'Контекст', searchPlaceholder: 'Поиск notebooks...' };
    }
    if (pathname.startsWith('/sources') || pathname.startsWith('/admin/sources') || pathname.startsWith('/admin/documents')) {
        return { title: 'Все источники', badge: 'Центр источников', searchPlaceholder: 'Поиск sources...' };
    }
    if (pathname.startsWith('/admin/logs')) {
        return { title: 'Логи и Аналитика', badge: 'Мониторинг', searchPlaceholder: 'Поиск по ID запроса...' };
    }
    if (pathname.startsWith('/settings')) {
        return { title: 'Настройки', badge: 'Система', searchPlaceholder: 'Поиск пользователей...' };
    }

    return { title: 'KnowledgeAI', badge: 'Workspace', searchPlaceholder: 'Поиск...' };
};

const isActiveLink = (pathname, href) => pathname === href || (href !== '/' && pathname.startsWith(`${href}/`));

const isNotebookDetailRoute = (pathname) => /^\/notebooks\/[^/]+(?:\/.*)?$/.test(pathname);

/** Декодирует payload JWT токена без внешних библиотек */
const decodeJwtPayload = (token) => {
    try {
        const parts = token.split('.');
        if (parts.length !== 3) return null;
        const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        const decoded = JSON.parse(atob(payload));
        return decoded;
    } catch {
        return null;
    }
};

const Layout = () => {
    const location = useLocation();
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();

    // --- User Info из JWT ---
    const userInfo = useMemo(() => {
        const token = localStorage.getItem('token');
        if (!token) return { username: 'Пользователь', email: '' };
        const payload = decodeJwtPayload(token);
        const username = payload?.sub || 'Пользователь';
        return {
            username,
            email: `${username}@knowledge.local`,
        };
    }, []);

    // --- Язык: читаем из localStorage, по умолчанию TJ ---
    const [activeLang, setActiveLang] = useState(() => localStorage.getItem('lang') || 'TJ');
    const [notebookHeader, setNotebookHeader] = useState(null);
    const [notebookActions, setNotebookActions] = useState(null);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('knowledgeai.sidebarCollapsed') === 'true');

    const handleLangSwitch = (lang) => {
        setActiveLang(lang);
        localStorage.setItem('lang', lang);
    };

    // --- Поиск через URL searchParams ---
    const searchValue = searchParams.get('q') || '';

    const handleSearchChange = (e) => {
        const val = e.target.value;
        if (val) {
            setSearchParams({ q: val });
        } else {
            setSearchParams({});
        }
    };

    // Сбрасываем поиск при смене страницы
    useEffect(() => {
        setSearchParams({});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [location.pathname]);

    const pageMeta = resolvePageMeta(location.pathname);
    const notebookDetailRoute = isNotebookDetailRoute(location.pathname);

    const handleLogout = () => {
        localStorage.removeItem('token');
        navigate('/login', { replace: true });
    };

    const handleToggleSidebar = () => {
        setSidebarCollapsed((prev) => {
            const next = !prev;
            localStorage.setItem('knowledgeai.sidebarCollapsed', String(next));
            return next;
        });
    };

    return (
        <NotebookHeaderContext.Provider value={{ notebookHeader, setNotebookHeader, notebookActions, setNotebookActions }}>
        <div className="min-h-screen bg-[#f3f5f8] lg:flex lg:h-screen lg:overflow-hidden">
            <aside className={cn(
                'hidden flex-col bg-[#1f3a60] text-white transition-[width] duration-300 lg:flex lg:h-screen',
                sidebarCollapsed ? 'w-[84px]' : 'w-64'
            )}>
                <div className={cn('flex h-16 items-center border-b border-white/10', sidebarCollapsed ? 'justify-center px-3' : 'gap-3 px-5')}>
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#c5a059] text-sm font-extrabold text-[#1f3a60] shadow-lg">
                        S
                    </div>
                    {!sidebarCollapsed ? (
                    <div>
                        <p className="text-2xl font-bold leading-none">KnowledgeAI</p>
                    </div>
                    ) : null}
                </div>

                <div className={cn('border-b border-white/10 py-3', sidebarCollapsed ? 'px-3' : 'px-4')}>
                    <button
                        type="button"
                        onClick={handleToggleSidebar}
                        className={cn(
                            'flex w-full items-center rounded-lg border border-white/15 text-sm font-semibold text-slate-200 transition hover:bg-white/10 hover:text-white',
                            sidebarCollapsed ? 'justify-center px-0 py-2.5' : 'justify-between px-3 py-2.5'
                        )}
                        aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                    >
                        {!sidebarCollapsed ? <span>Скрыть меню</span> : null}
                        {sidebarCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
                    </button>
                </div>

                <nav className={cn('flex-1 space-y-1 py-5', sidebarCollapsed ? 'px-2' : 'px-3')}>
                    {NAV_ITEMS.map((item) => {
                        const Icon = item.icon;
                        const active = isActiveLink(location.pathname, item.href);

                        return (
                            <Link
                                key={item.name}
                                to={item.href}
                                className={cn(
                                    'group flex items-center rounded-lg py-2.5 text-sm font-semibold transition-all',
                                    sidebarCollapsed ? 'justify-center px-2' : 'gap-3 px-3',
                                    active
                                        ? 'bg-white/12 text-[#c5a059] shadow-[inset_3px_0_0_0_#c5a059]'
                                        : 'text-slate-200/85 hover:bg-white/8 hover:text-white',
                                )}
                                title={sidebarCollapsed ? item.name : undefined}
                            >
                                <Icon className={cn('h-[18px] w-[18px]', active ? 'text-[#c5a059]' : 'text-slate-300 group-hover:text-white')} />
                                {!sidebarCollapsed ? item.name : null}
                            </Link>
                        );
                    })}
                </nav>

                <div className={cn('border-t border-white/10', sidebarCollapsed ? 'p-2' : 'p-4')}>
                    <div className={cn('mb-3 rounded-xl bg-white/5', sidebarCollapsed ? 'flex justify-center p-2.5' : 'flex items-center gap-3 p-2.5')}>
                        <UserCircle2 className="h-9 w-9 text-slate-300" />
                        {!sidebarCollapsed ? (
                        <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-white">{userInfo.username}</p>
                            <p className="truncate text-xs text-slate-300">{userInfo.email}</p>
                        </div>
                        ) : null}
                    </div>
                    <button
                        type="button"
                        onClick={handleLogout}
                        className={cn(
                            'flex w-full items-center justify-center rounded-lg border border-white/20 text-sm font-semibold text-white transition hover:bg-white/10',
                            sidebarCollapsed ? 'px-0 py-2.5' : 'gap-2 px-3 py-2'
                        )}
                        title={sidebarCollapsed ? 'Выйти' : undefined}
                    >
                        <LogOut className="h-4 w-4" />
                        {!sidebarCollapsed ? 'Выйти' : null}
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
                            {!notebookDetailRoute ? (
                                <div className="flex items-center gap-3">
                                    <h1 className="text-xl lg:text-2xl font-extrabold text-[#1f3a60]">{pageMeta.title}</h1>
                                    <span className="rounded-full bg-[#1f3a60]/10 px-2.5 py-0.5 text-[10px] lg:text-xs font-bold text-[#1f3a60]">
                                        {pageMeta.badge}
                                    </span>
                                </div>
                            ) : notebookHeader ? (
                                <div className="flex min-w-0 flex-col gap-1">
                                    <div className="flex min-w-0 items-center gap-2">
                                        <span className="rounded-full bg-[#1f3a60]/10 px-2.5 py-0.5 text-[10px] font-bold text-[#1f3a60]">
                                            Блокнот #{notebookHeader.id}
                                        </span>
                                        <h1 className="truncate text-lg lg:text-2xl font-extrabold text-[#1f3a60]">
                                            {notebookHeader.name}
                                        </h1>
                                    </div>
                                    {notebookHeader.description ? (
                                        <p className="truncate text-sm text-slate-500">{notebookHeader.description}</p>
                                    ) : null}
                                    <div className="flex flex-wrap items-center gap-3 text-[11px] font-medium text-slate-400">
                                        <div className="inline-flex items-center gap-1.5">
                                            <CalendarDays className="h-3.5 w-3.5" />
                                            <span>Создан: {notebookHeader.createdAtText}</span>
                                        </div>
                                        <div className="inline-flex items-center gap-1.5">
                                            <Clock3 className="h-3.5 w-3.5" />
                                            <span>Обновлен: {notebookHeader.updatedAtText}</span>
                                        </div>
                                        <div className="inline-flex items-center gap-1.5">
                                            <Bookmark className="h-3.5 w-3.5" />
                                            <span>Профиль: {notebookHeader.domainProfile}</span>
                                        </div>
                                    </div>
                                </div>
                            ) : null}
                        </div>

                        <div className="flex w-full items-center gap-3 sm:w-auto">
                            {!notebookDetailRoute ? (
                                <>
                                    <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1 mr-2">
                                        {['TJ', 'RU'].map((lang) => (
                                            <button
                                                key={lang}
                                                type="button"
                                                onClick={() => handleLangSwitch(lang)}
                                                className={cn(
                                                    'rounded-md px-2 py-0.5 text-[10px] font-bold transition',
                                                    activeLang === lang
                                                        ? 'bg-white text-[#1f3a60] shadow-sm'
                                                        : 'text-slate-500 hover:text-slate-700',
                                                )}
                                            >
                                                {lang}
                                            </button>
                                        ))}
                                    </div>

                                    <div className="relative flex-1 sm:w-64 sm:flex-none">
                                        <input
                                            type="text"
                                            value={searchValue}
                                            onChange={handleSearchChange}
                                            placeholder={pageMeta.searchPlaceholder}
                                            className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1f3a60]/30"
                                        />
                                    </div>

                                <div className="hidden items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-500 xl:flex">
                                    <span className="mr-2 inline-block h-2 w-2 rounded-full bg-green-500"></span>
                                    Система работает
                                </div>
                                </>
                            ) : notebookActions ? (
                                <div className="flex flex-wrap items-center justify-end gap-2">
                                    <Button
                                        type="button"
                                        variant="outline"
                                        className="justify-center"
                                        disabled={notebookActions.archiveDisabled}
                                        title={notebookActions.archiveTitle}
                                        onClick={notebookActions.onArchive}
                                    >
                                        Архивировать
                                    </Button>
                                    <Button
                                        type="button"
                                        variant="destructive"
                                        className="justify-center"
                                        disabled={notebookActions.deleteDisabled}
                                        title={notebookActions.deleteTitle}
                                        onClick={notebookActions.onDelete}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                        Удалить
                                    </Button>
                                </div>
                            ) : null}

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

                <main className="soft-grid flex-1 overflow-auto p-6">
                    <Outlet />
                </main>
            </div>
        </div>
        </NotebookHeaderContext.Provider>
    );
};

export default Layout;
