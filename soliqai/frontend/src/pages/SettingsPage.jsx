import React, { useEffect, useState } from 'react';
import { settingsService } from '../services/settingsService';
import { Button } from '../components/ui/Button';

const ROLE_OPTIONS = ['admin', 'content_manager', 'user'];

const normalizeSelectedModel = (currentValue, availableModels) => {
    if (!Array.isArray(availableModels) || availableModels.length === 0) {
        return '';
    }

    return availableModels.includes(currentValue) ? currentValue : availableModels[0];
};

const SettingsPage = () => {
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [runtimeSettings, setRuntimeSettings] = useState({
        chat_model: '',
        embedding_model: '',
        enable_condense_query: true,
        available_models: [],
        available_chat_models: [],
        available_embedding_models: [],
        ollama_available: true,
        ollama_error: '',
    });
    const [users, setUsers] = useState([]);
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');
    const canSave = Boolean(runtimeSettings.chat_model && runtimeSettings.embedding_model);

    const loadData = async () => {
        setIsLoading(true);
        setError('');

        try {
            const [settingsRes, usersRes] = await Promise.all([
                settingsService.get(),
                settingsService.getUsers(),
            ]);
            const settingsData = settingsRes.data || {};
            setRuntimeSettings({
                ...settingsData,
                chat_model: normalizeSelectedModel(
                    settingsData.chat_model || settingsData.model || '',
                    settingsData.available_chat_models || []
                ),
                embedding_model: normalizeSelectedModel(
                    settingsData.embedding_model || '',
                    settingsData.available_embedding_models || []
                ),
            });
            setUsers(usersRes.data || []);
        } catch (err) {
            console.error('Failed to load settings', err);
            setError(err.response?.data?.detail || 'Не удалось загрузить настройки');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    const handleSave = async () => {
        setIsSaving(true);
        setMessage('');
        setError('');

        try {
            const payload = {
                chat_model: runtimeSettings.chat_model,
                embedding_model: runtimeSettings.embedding_model,
                enable_condense_query: runtimeSettings.enable_condense_query,
            };
            const response = await settingsService.update(payload);
            const settingsData = response.data || {};
            setRuntimeSettings({
                ...settingsData,
                chat_model: normalizeSelectedModel(
                    settingsData.chat_model || settingsData.model || '',
                    settingsData.available_chat_models || []
                ),
                embedding_model: normalizeSelectedModel(
                    settingsData.embedding_model || '',
                    settingsData.available_embedding_models || []
                ),
            });
            setMessage('Настройки сохранены');
        } catch (err) {
            console.error('Failed to update settings', err);
            setError(err.response?.data?.detail || 'Не удалось сохранить настройки');
        } finally {
            setIsSaving(false);
        }
    };

    const handleRoleChange = async (userId, role) => {
        try {
            await settingsService.updateUserRole(userId, role);
            setUsers((prev) => prev.map((user) => (
                user.id === userId ? { ...user, role } : user
            )));
        } catch (err) {
            console.error('Failed to update role', err);
            alert(err.response?.data?.detail || 'Не удалось обновить роль');
        }
    };

    if (isLoading) {
        return (
            <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-500 shadow-sm">
                Загрузка настроек...
            </div>
        );
    }

    return (
        <div className="space-y-6 px-4">
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="mb-4 flex items-center gap-3">
                    <h2 className="text-3xl font-extrabold text-[#1f3a60]">Настройки выполнения</h2>
                    <span className="rounded-full bg-[#1f3a60]/10 px-3 py-1 text-xs font-bold text-[#1f3a60]">Конфигурация ИИ</span>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                    <div>
                        <label className="mb-2 block text-sm font-semibold text-slate-700">Chat model</label>
                        <select
                            value={runtimeSettings.chat_model}
                            onChange={(event) => setRuntimeSettings((prev) => ({
                                ...prev,
                                chat_model: event.target.value,
                            }))}
                            disabled={!runtimeSettings.available_chat_models?.length}
                            className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1f3a60]/25 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {runtimeSettings.available_chat_models?.length ? (
                                runtimeSettings.available_chat_models.map((model) => (
                                    <option key={model} value={model}>{model}</option>
                                ))
                            ) : (
                                <option value="">Нет доступных chat-моделей</option>
                            )}
                        </select>
                    </div>

                    <div>
                        <label className="mb-2 block text-sm font-semibold text-slate-700">Embedding model</label>
                        <select
                            value={runtimeSettings.embedding_model}
                            onChange={(event) => setRuntimeSettings((prev) => ({
                                ...prev,
                                embedding_model: event.target.value,
                            }))}
                            disabled={!runtimeSettings.available_embedding_models?.length}
                            className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1f3a60]/25 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {runtimeSettings.available_embedding_models?.length ? (
                                runtimeSettings.available_embedding_models.map((model) => (
                                    <option key={model} value={model}>{model}</option>
                                ))
                            ) : (
                                <option value="">Нет доступных embedding-моделей</option>
                            )}
                        </select>
                        <p className="mt-2 text-xs text-slate-500">
                            Список подгружается из Ollama. Выбор доступен только из найденных моделей.
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                            После смены embedding model нужно переиндексировать документы.
                        </p>
                        {!runtimeSettings.ollama_available && (
                            <p className="mt-2 text-xs font-semibold text-amber-600">
                                Не удалось получить список моделей из Ollama: {runtimeSettings.ollama_error || 'сервис недоступен'}.
                            </p>
                        )}
                    </div>
                </div>

                <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <label className="flex items-start gap-3">
                        <input
                            type="checkbox"
                            checked={Boolean(runtimeSettings.enable_condense_query)}
                            onChange={(event) => setRuntimeSettings((prev) => ({
                                ...prev,
                                enable_condense_query: event.target.checked,
                            }))}
                            className="mt-1 h-4 w-4 rounded border-slate-300 text-[#1f3a60] focus:ring-[#1f3a60]/25"
                        />
                        <span>
                            <span className="block text-sm font-semibold text-slate-800">Condense query</span>
                            <span className="mt-1 block text-xs text-slate-500">
                                Если включено, система сначала переформулирует вопрос в самостоятельный поисковый запрос. Отключение может ускорить ответы, но хуже обрабатывает короткие follow-up вопросы из истории чата.
                            </span>
                        </span>
                    </label>
                </div>

                <div className="mt-5 flex flex-wrap items-center gap-3">
                    <Button type="button" onClick={handleSave} isLoading={isSaving} disabled={!canSave}>
                        Сохранить настройки
                    </Button>
                    {message && <span className="text-sm font-semibold text-emerald-600">{message}</span>}
                    {error && <span className="text-sm font-semibold text-red-600">{error}</span>}
                </div>
            </section>

            <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-200 px-5 py-4">
                    <h3 className="text-lg font-bold text-[#1f3a60]">Управление ролями</h3>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full min-w-[740px] text-left">
                        <thead className="bg-slate-50 text-xs uppercase tracking-[0.08em] text-slate-500">
                            <tr>
                                <th className="px-5 py-3 font-semibold">Пользователь</th>
                                <th className="px-5 py-3 font-semibold">Роль</th>
                                <th className="px-5 py-3 font-semibold">Создан</th>
                            </tr>
                        </thead>

                        <tbody>
                            {users.map((user) => (
                                <tr key={user.id} className="border-t border-slate-100 text-sm hover:bg-slate-50">
                                    <td className="px-5 py-3 font-semibold text-slate-800">{user.username}</td>
                                    <td className="px-5 py-3">
                                        <select
                                            value={user.role}
                                            onChange={(event) => handleRoleChange(user.id, event.target.value)}
                                            className="h-9 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1f3a60]/25"
                                        >
                                            {ROLE_OPTIONS.map((role) => (
                                                <option key={role} value={role}>{role}</option>
                                            ))}
                                        </select>
                                    </td>
                                    <td className="px-5 py-3 text-slate-500">
                                        {new Date(user.created_at).toLocaleString()}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
};

export default SettingsPage;
