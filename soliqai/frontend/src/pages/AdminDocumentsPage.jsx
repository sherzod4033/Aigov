import React, { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import {
    AlertTriangle,
    CheckCircle2,
    CloudUpload,
    FileText,
    Loader2,
    MoreVertical,
    Trash2,
} from 'lucide-react';
import api from '../services/api';
import { Button } from '../components/ui/Button';
import { cn } from '../lib/utils';

const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'txt'];
const ALLOWED_MIME_TYPES = new Set([
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
    'application/octet-stream',
    'binary/octet-stream',
    'application/zip',
]);

const STATUS_ORDER = ['all', 'ready', 'indexing', 'error'];

const STATUS_META = {
    ready: {
        label: 'Ready',
        badgeClass: 'bg-emerald-100 text-emerald-700',
        dotClass: 'bg-emerald-500',
    },
    indexing: {
        label: 'Indexing',
        badgeClass: 'bg-amber-100 text-amber-700',
        dotClass: 'bg-amber-500',
    },
    error: {
        label: 'Error',
        badgeClass: 'bg-red-100 text-red-700',
        dotClass: 'bg-red-500',
    },
};

const resolveStatus = (status) => {
    const normalized = String(status || '').toLowerCase();

    if (['indexed', 'ready', 'completed'].includes(normalized)) return 'ready';
    if (['pending', 'indexing', 'processing'].includes(normalized)) return 'indexing';
    if (['error', 'failed'].includes(normalized)) return 'error';
    return 'indexing';
};

const formatSize = (size) => {
    const bytes = Number(size || 0);
    if (bytes < 1024) return `${bytes} B`;
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(0)} KB`;
    return `${(kb / 1024).toFixed(1)} MB`;
};

const formatDate = (value) => {
    if (!value) return '-';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return '-';
    return new Intl.DateTimeFormat('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
    }).format(parsed);
};

const getLanguageTag = (language) => {
    const normalized = String(language || '').trim().toUpperCase();
    if (normalized === 'TJ') return { text: 'TJ', className: 'bg-yellow-100 text-yellow-800' };
    return { text: 'RU', className: 'bg-blue-100 text-blue-700' };
};

const AdminDocumentsPage = () => {
    const [documents, setDocuments] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadError, setUploadError] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [searchTerm, setSearchTerm] = useState('');

    const {
        register,
        handleSubmit,
        reset,
        watch,
    } = useForm();

    const selectedFile = watch('file')?.[0];

    const fetchDocuments = async () => {
        try {
            const response = await api.get('/documents/');
            setDocuments(response.data || []);
        } catch (error) {
            console.error('Failed to fetch documents:', error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchDocuments();
    }, []);

    const stats = useMemo(() => {
        const counts = {
            all: documents.length,
            ready: 0,
            indexing: 0,
            error: 0,
        };

        documents.forEach((doc) => {
            const status = resolveStatus(doc.status);
            counts[status] += 1;
        });

        return counts;
    }, [documents]);

    const filteredDocuments = useMemo(() => {
        const query = searchTerm.trim().toLowerCase();

        return documents.filter((doc) => {
            const status = resolveStatus(doc.status);
            const statusMatch = statusFilter === 'all' || statusFilter === status;
            const queryMatch = !query || String(doc.name || '').toLowerCase().includes(query);
            return statusMatch && queryMatch;
        });
    }, [documents, searchTerm, statusFilter]);

    const onUpload = async (data) => {
        const selected = data.file?.[0];
        if (!selected) return;

        const ext = selected.name.split('.').pop()?.toLowerCase() || '';
        const hasAllowedExt = ALLOWED_EXTENSIONS.includes(ext);
        const hasAllowedMime = ALLOWED_MIME_TYPES.has((selected.type || '').toLowerCase());

        if (!hasAllowedExt || !hasAllowedMime) {
            setUploadError('Allowed formats: PDF, DOCX, TXT. Please choose a valid file.');
            return;
        }

        setIsUploading(true);
        setUploadError('');

        const formData = new FormData();
        formData.append('file', selected);

        try {
            await api.post('/documents/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            reset();
            await fetchDocuments();
        } catch (error) {
            console.error('Upload failed:', error);
            setUploadError(error.response?.data?.detail || 'Failed to upload document');
        } finally {
            setIsUploading(false);
        }
    };

    const onDelete = async (id) => {
        if (!window.confirm('Are you sure you want to delete this document?')) return;

        try {
            await api.delete(`/documents/${id}`);
            setDocuments((prev) => prev.filter((doc) => doc.id !== id));
        } catch (error) {
            console.error('Delete failed:', error);
            alert('Failed to delete document');
        }
    };

    return (
        <div className="space-y-6">
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                        <h2 className="text-3xl font-extrabold text-[#1f3a60]">Documents</h2>
                        <span className="rounded-full bg-[#1f3a60]/10 px-3 py-1 text-xs font-bold text-[#1f3a60]">
                            {documents.length} Files
                        </span>
                    </div>

                    <input
                        value={searchTerm}
                        onChange={(event) => setSearchTerm(event.target.value)}
                        placeholder="Search documents..."
                        className="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#1f3a60]/30 sm:w-72"
                    />
                </div>

                <form onSubmit={handleSubmit(onUpload)} className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
                    <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[#1f3a60]/10 text-[#1f3a60]">
                        <CloudUpload className="h-7 w-7" />
                    </div>
                    <h3 className="text-2xl font-bold text-slate-800">Drag and drop files here</h3>
                    <p className="mt-1 text-sm text-slate-500">Supported formats: PDF, DOCX, TXT (Max 50MB)</p>

                    <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
                        <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-[#c5a059] px-5 py-2 text-sm font-semibold text-white transition hover:bg-[#b18f4e]">
                            <CloudUpload className="h-4 w-4" />
                            Choose file
                            <input
                                type="file"
                                className="hidden"
                                accept=".pdf,.docx,.txt,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                {...register('file', { required: true })}
                            />
                        </label>

                        <Button type="submit" disabled={isUploading || !selectedFile}>
                            {isUploading ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Uploading...
                                </>
                            ) : (
                                'Upload file'
                            )}
                        </Button>
                    </div>

                    {selectedFile && (
                        <p className="mt-3 text-sm font-semibold text-slate-600">
                            Selected: {selectedFile.name}
                        </p>
                    )}

                    {uploadError && (
                        <p className="mt-3 text-sm font-semibold text-red-600">{uploadError}</p>
                    )}
                </form>
            </section>

            <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
                    <div className="flex flex-wrap gap-2">
                        {STATUS_ORDER.map((status) => (
                            <button
                                key={status}
                                type="button"
                                onClick={() => setStatusFilter(status)}
                                className={cn(
                                    'rounded-lg px-3 py-1.5 text-xs font-semibold transition',
                                    statusFilter === status
                                        ? 'bg-[#1f3a60] text-white'
                                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
                                )}
                            >
                                {status === 'all' ? 'All' : STATUS_META[status].label}
                                <span className="ml-1">{stats[status]}</span>
                            </button>
                        ))}
                    </div>

                    <div className="text-sm font-semibold text-slate-500">Sort by: Date (Newest)</div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full min-w-[820px] text-left">
                        <thead className="bg-slate-50 text-xs uppercase tracking-[0.08em] text-slate-500">
                            <tr>
                                <th className="px-5 py-3 font-semibold">Filename</th>
                                <th className="px-5 py-3 font-semibold">Language</th>
                                <th className="px-5 py-3 font-semibold">Upload date</th>
                                <th className="px-5 py-3 font-semibold">Size</th>
                                <th className="px-5 py-3 font-semibold">Status</th>
                                <th className="px-5 py-3 text-right font-semibold">Actions</th>
                            </tr>
                        </thead>

                        <tbody>
                            {isLoading ? (
                                <tr>
                                    <td colSpan="6" className="px-5 py-12 text-center text-slate-500">
                                        <div className="inline-flex items-center gap-2">
                                            <Loader2 className="h-5 w-5 animate-spin" />
                                            Loading documents...
                                        </div>
                                    </td>
                                </tr>
                            ) : filteredDocuments.length === 0 ? (
                                <tr>
                                    <td colSpan="6" className="px-5 py-12 text-center text-slate-500">
                                        No documents found.
                                    </td>
                                </tr>
                            ) : (
                                filteredDocuments.map((doc) => {
                                    const statusKey = resolveStatus(doc.status);
                                    const statusMeta = STATUS_META[statusKey];
                                    const languageTag = getLanguageTag(doc.language);

                                    return (
                                        <tr key={doc.id} className="border-t border-slate-100 text-sm hover:bg-slate-50/70">
                                            <td className="px-5 py-3">
                                                <div className="flex items-center gap-3">
                                                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-100 text-red-500">
                                                        <FileText className="h-4 w-4" />
                                                    </div>
                                                    <div>
                                                        <p className="font-semibold text-slate-800">{doc.name}</p>
                                                        <p className="text-xs text-slate-400">ID #{doc.id}</p>
                                                    </div>
                                                </div>
                                            </td>

                                            <td className="px-5 py-3">
                                                <span className={cn('rounded px-2 py-0.5 text-xs font-semibold', languageTag.className)}>
                                                    {languageTag.text}
                                                </span>
                                            </td>

                                            <td className="px-5 py-3 text-slate-500">
                                                {formatDate(doc.created_at)}
                                            </td>

                                            <td className="px-5 py-3 text-slate-500">
                                                {formatSize(doc.size)}
                                            </td>

                                            <td className="px-5 py-3">
                                                <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold', statusMeta.badgeClass)}>
                                                    {statusKey === 'indexing' ? (
                                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                    ) : statusKey === 'error' ? (
                                                        <AlertTriangle className="h-3.5 w-3.5" />
                                                    ) : (
                                                        <CheckCircle2 className="h-3.5 w-3.5" />
                                                    )}
                                                    {statusMeta.label}
                                                </span>
                                            </td>

                                            <td className="px-5 py-3 text-right">
                                                <div className="inline-flex items-center gap-1">
                                                    <button
                                                        type="button"
                                                        onClick={() => onDelete(doc.id)}
                                                        className="rounded-md p-1.5 text-slate-500 transition hover:bg-red-50 hover:text-red-600"
                                                        title="Delete"
                                                    >
                                                        <Trash2 className="h-4 w-4" />
                                                    </button>
                                                    <button
                                                        type="button"
                                                        className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
                                                    >
                                                        <MoreVertical className="h-4 w-4" />
                                                    </button>
                                                </div>
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

export default AdminDocumentsPage;
