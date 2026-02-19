import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { logsService } from '../services/services';
import {
    Download,
    Filter,
    ThumbsDown,
    ThumbsUp,
    Timer,
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import Input from '../components/ui/Input';
import { cn } from '../lib/utils';

const parseSourcesCount = (sources) => {
    if (Array.isArray(sources)) return sources.length;

    if (typeof sources === 'string') {
        try {
            const parsed = JSON.parse(sources);
            return Array.isArray(parsed) ? parsed.length : 0;
        } catch {
            return 0;
        }
    }

    return 0;
};

const formatDateTime = (value) => {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '-';

    return new Intl.DateTimeFormat('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    }).format(date);
};

const AdminLogsPage = () => {
    const [logs, setLogs] = useState([]);
    const [analytics, setAnalytics] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isExporting, setIsExporting] = useState(false);
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');

    // Поиск читаем из URL param ?q= (устанавливается хедером)
    const [searchParams] = useSearchParams();
    const query = searchParams.get('q') || '';

    const fetchData = useCallback(async (filters = {}) => {
        const from = filters.startDate ?? '';
        const to = filters.endDate ?? '';
        setIsLoading(true);
        try {
            const [logsRes, analyticsRes] = await Promise.all([
                logsService.getAll({
                    startDate: from,
                    endDate: to,
                }),
                logsService.getAnalytics(),
            ]);
            setLogs(logsRes.data || []);
            setAnalytics(analyticsRes.data || null);
        } catch (error) {
            console.error('Failed to fetch data', error);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData({ startDate: '', endDate: '' });
    }, [fetchData]);

    const applyDateFilter = async () => {
        await fetchData({ startDate, endDate });
    };

    const resetDateFilter = async () => {
        setStartDate('');
        setEndDate('');
        await fetchData({ startDate: '', endDate: '' });
    };

    const handleExport = async () => {
        setIsExporting(true);
        try {
            const response = await logsService.exportCsv({ startDate, endDate });
            const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `logs_export_${new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')}.csv`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Failed to export logs', error);
            alert('Не удалось экспортировать логи');
        } finally {
            setIsExporting(false);
        }
    };

    const filteredLogs = useMemo(() => {
        const term = query.trim().toLowerCase();
        if (!term) return logs;

        return logs.filter((log) => {
            const searchText = `${log.question} ${log.answer} ${log.id}`.toLowerCase();
            return searchText.includes(term);
        });
    }, [logs, query]);

    const totalChats = analytics?.total_requests ?? analytics?.total_logs ?? logs.length;
    const positiveFeedback = analytics?.positive_feedback ?? analytics?.ups ?? 0;
    const negativeFeedback = analytics?.negative_feedback ?? analytics?.downs ?? 0;
    const avgResponseMs = Number(analytics?.avg_response_time_ms ?? 0);
    const avgResponseSeconds = avgResponseMs > 0 ? (avgResponseMs / 1000).toFixed(2) : '0.00';

    return (
        <div className="space-y-6 px-4">
            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-center gap-3">
                    <Input
                        value={query}
                        readOnly
                        placeholder="Поиск через строку выше..."
                        className="min-w-[220px] flex-1 bg-slate-50 cursor-default"
                        title="Используйте поиск в верхней панели"
                    />

                    <Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} className="w-40" />
                    <Input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} className="w-40" />

                    <Button type="button" variant="outline" onClick={applyDateFilter}>
                        <Filter className="h-4 w-4" />
                        Фильтры
                    </Button>

                    <Button type="button" variant="secondary" onClick={handleExport} disabled={isExporting}>
                        <Download className="h-4 w-4" />
                        {isExporting ? 'Экспорт...' : 'Экспорт отчета'}
                    </Button>

                    <Button type="button" variant="ghost" onClick={resetDateFilter}>
                        Сброс
                    </Button>
                </div>
            </section>

            <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl bg-[#1f3a60] p-5 text-white shadow-md">
                    <p className="text-xs font-semibold uppercase tracking-[0.08em] text-white/70">Всего запросов</p>
                    <p className="mt-1 text-4xl font-extrabold">{totalChats}</p>
                    <p className="mt-2 text-xs text-white/70">Отслеживаемые диалоги</p>
                </div>

                <div className="rounded-2xl bg-[#1f3a60] p-5 text-white shadow-md">
                    <div className="flex items-center justify-between">
                        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-white/70">Положительные отзывы</p>
                        <ThumbsUp className="h-4 w-4 text-emerald-300" />
                    </div>
                    <p className="mt-1 text-4xl font-extrabold">{positiveFeedback}</p>
                    <p className="mt-2 text-xs text-white/70">Полезные ответы</p>
                </div>

                <div className="rounded-2xl bg-[#1f3a60] p-5 text-white shadow-md">
                    <div className="flex items-center justify-between">
                        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-white/70">Среднее время ответа</p>
                        <Timer className="h-4 w-4 text-[#c5a059]" />
                    </div>
                    <p className="mt-1 text-4xl font-extrabold">{avgResponseSeconds}s</p>
                    <p className="mt-2 text-xs text-emerald-200">Оптимально</p>
                </div>

                <div className="rounded-2xl bg-[#1f3a60] p-5 text-white shadow-md">
                    <div className="flex items-center justify-between">
                        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-white/70">Отрицательные отзывы</p>
                        <ThumbsDown className="h-4 w-4 text-rose-300" />
                    </div>
                    <p className="mt-1 text-4xl font-extrabold">{negativeFeedback}</p>
                    <p className="mt-2 text-xs text-white/70">Требует улучшения</p>
                </div>
            </section>

            {Array.isArray(analytics?.top_questions) && analytics.top_questions.length > 0 && (
                <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <h3 className="text-lg font-bold text-[#1f3a60]">Топ вопросов</h3>
                    <div className="mt-3 flex flex-wrap gap-2">
                        {analytics.top_questions.map((item) => (
                            <span key={item.question} className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-600">
                                {item.question}
                                <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px]">{item.count}</span>
                            </span>
                        ))}
                    </div>
                </section>
            )}

            <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-200 px-5 py-4">
                    <h3 className="text-lg font-bold text-[#1f3a60]">Недавние чаты</h3>
                    <p className="mt-1 text-sm text-slate-500">Показано {filteredLogs.length} из {logs.length} записей</p>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full min-w-[980px] text-left">
                        <thead className="bg-slate-50 text-xs uppercase tracking-[0.08em] text-slate-500">
                            <tr>
                                <th className="px-5 py-3 font-semibold">Вопрос</th>
                                <th className="px-5 py-3 font-semibold">Кол-во источников</th>
                                <th className="px-5 py-3 font-semibold">Время ответа</th>
                                <th className="px-5 py-3 font-semibold">Отзыв</th>
                                <th className="px-5 py-3 font-semibold">Создано</th>
                            </tr>
                        </thead>

                        <tbody>
                            {isLoading ? (
                                <tr>
                                    <td colSpan="5" className="px-5 py-10 text-center text-sm text-slate-500">Загрузка...</td>
                                </tr>
                            ) : filteredLogs.length === 0 ? (
                                <tr>
                                    <td colSpan="5" className="px-5 py-10 text-center text-sm text-slate-500">Логи не найдены</td>
                                </tr>
                            ) : (
                                filteredLogs.map((log) => {
                                    const sourceCount = parseSourcesCount(log.sources);
                                    const responseTime = Number(log.time_ms || 0) / 1000;

                                    return (
                                        <tr
                                            key={log.id}
                                            className={cn(
                                                'border-t border-slate-100 text-sm',
                                                log.rating === 'down' ? 'bg-amber-50/50' : 'hover:bg-slate-50/70',
                                            )}
                                        >
                                            <td className="px-5 py-3">
                                                <div className="max-w-xl">
                                                    <p className="truncate font-semibold text-slate-800" title={log.question}>{log.question}</p>
                                                    <p className="truncate text-xs text-slate-500" title={log.answer}>{log.answer}</p>
                                                </div>
                                            </td>

                                            <td className="px-5 py-3">
                                                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
                                                    {sourceCount} ист.
                                                </span>
                                            </td>

                                            <td className="px-5 py-3 font-semibold text-slate-600">
                                                {responseTime.toFixed(2)}s
                                            </td>

                                            <td className="px-5 py-3">
                                                {log.rating === 'up' && <ThumbsUp className="h-4 w-4 text-emerald-600" />}
                                                {log.rating === 'down' && <ThumbsDown className="h-4 w-4 text-red-600" />}
                                                {!log.rating && <span className="text-slate-300">-</span>}
                                            </td>

                                            <td className="px-5 py-3 text-slate-500">
                                                {formatDateTime(log.created_at)}
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
};

export default AdminLogsPage;
