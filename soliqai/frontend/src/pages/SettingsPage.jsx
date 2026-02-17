import React, { useEffect, useState } from 'react';
import { settingsService } from '../services/services';
import { Button } from '../components/ui/Button';
import Input from '../components/ui/Input';

const ROLE_OPTIONS = ['admin', 'content_manager', 'user'];

const SettingsPage = () => {
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [runtimeSettings, setRuntimeSettings] = useState({
        model: '',
        top_k: 5,
        available_models: [],
    });
    const [users, setUsers] = useState([]);
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');

    const loadData = async () => {
        setIsLoading(true);
        setError('');

        try {
            const [settingsRes, usersRes] = await Promise.all([
                settingsService.get(),
                settingsService.getUsers(),
            ]);
            setRuntimeSettings(settingsRes.data);
            setUsers(usersRes.data || []);
        } catch (err) {
            console.error('Failed to load settings', err);
            setError(err.response?.data?.detail || 'Failed to load settings');
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
                model: runtimeSettings.model,
                top_k: Number(runtimeSettings.top_k),
            };
            const response = await settingsService.update(payload);
            setRuntimeSettings(response.data);
            setMessage('Settings saved');
        } catch (err) {
            console.error('Failed to update settings', err);
            setError(err.response?.data?.detail || 'Failed to save settings');
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
            alert(err.response?.data?.detail || 'Failed to update role');
        }
    };

    if (isLoading) {
        return (
            <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-500 shadow-sm">
                Loading settings...
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="mb-4 flex items-center gap-3">
                    <h2 className="text-3xl font-extrabold text-[#1f3a60]">Runtime Settings</h2>
                    <span className="rounded-full bg-[#1f3a60]/10 px-3 py-1 text-xs font-bold text-[#1f3a60]">AI Configuration</span>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                    <div>
                        <label className="mb-2 block text-sm font-semibold text-slate-700">Model</label>
                        <select
                            value={runtimeSettings.model}
                            onChange={(event) => setRuntimeSettings((prev) => ({
                                ...prev,
                                model: event.target.value,
                            }))}
                            className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1f3a60]/25"
                        >
                            {(runtimeSettings.available_models || []).map((model) => (
                                <option key={model} value={model}>{model}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="mb-2 block text-sm font-semibold text-slate-700">Top-K</label>
                        <Input
                            type="number"
                            min={1}
                            max={20}
                            value={runtimeSettings.top_k}
                            onChange={(event) => setRuntimeSettings((prev) => ({
                                ...prev,
                                top_k: event.target.value,
                            }))}
                        />
                    </div>
                </div>

                <div className="mt-5 flex flex-wrap items-center gap-3">
                    <Button type="button" onClick={handleSave} isLoading={isSaving}>
                        Save settings
                    </Button>
                    {message && <span className="text-sm font-semibold text-emerald-600">{message}</span>}
                    {error && <span className="text-sm font-semibold text-red-600">{error}</span>}
                </div>
            </section>

            <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-200 px-5 py-4">
                    <h3 className="text-lg font-bold text-[#1f3a60]">Role Management</h3>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full min-w-[740px] text-left">
                        <thead className="bg-slate-50 text-xs uppercase tracking-[0.08em] text-slate-500">
                            <tr>
                                <th className="px-5 py-3 font-semibold">User</th>
                                <th className="px-5 py-3 font-semibold">Role</th>
                                <th className="px-5 py-3 font-semibold">Created</th>
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
