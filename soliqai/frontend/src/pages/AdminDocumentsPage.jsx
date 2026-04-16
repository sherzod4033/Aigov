import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import {
    AlertTriangle,
    CheckCircle2,
    CloudUpload,
    Eye,
    FileText,
    Loader2,
    MoreVertical,
    Trash2,
    X,
} from 'lucide-react';
import api from '../services/api';
import { Button } from '../components/ui/Button';
import { cn } from '../lib/utils';
import { useLocale } from '../i18n';
import { formatDocumentLanguage, formatLocaleDate } from '../lib/locale';

const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'txt'];
const ALLOWED_MIME_TYPES = new Set([
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
    'application/octet-stream',
    'binary/octet-stream',
    'application/zip',
]);

const normalizeMimeType = (mimeType) => String(mimeType || '').split(';', 1)[0].trim().toLowerCase();

const STATUS_ORDER = ['all', 'ready', 'indexing', 'error'];

const ACTIVE_NOTEBOOK_STORAGE_KEY = 'knowledgeai.activeNotebookId';

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

const resolveNotebookId = (notebookId) => {
    if (notebookId !== undefined) {
        return notebookId == null ? null : Number(notebookId);
    }

    const storedValue = localStorage.getItem(ACTIVE_NOTEBOOK_STORAGE_KEY);
    return storedValue ? Number(storedValue) : null;
};

const AdminDocumentsPage = ({ notebookId }) => {
    const { locale, t } = useLocale();
    const [documents, setDocuments] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadError, setUploadError] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [isDragActive, setIsDragActive] = useState(false);
    const [sortField, setSortField] = useState('created_at');
    const [sortOrder, setSortOrder] = useState('desc');

    // Поиск читаем из URL param ?q= (устанавливается хедером)
    const [searchParams] = useSearchParams();
    const searchTerm = searchParams.get('q') || '';
    const [draggedFiles, setDraggedFiles] = useState([]);
    const [chunksModal, setChunksModal] = useState({
        isOpen: false,
        docId: null,
        docName: '',
        chunks: [],
        isLoading: false,
        error: null,
    });

    const {
        register,
        reset,
        watch,
    } = useForm();

    const selectedFile = watch('file')?.[0];
    const effectiveNotebookId = resolveNotebookId(notebookId);
    const statusMeta = useMemo(() => ({
        ready: {
            label: t('documents.status.ready'),
            badgeClass: 'bg-emerald-100 text-emerald-700',
        },
        indexing: {
            label: t('documents.status.indexing'),
            badgeClass: 'bg-amber-100 text-amber-700',
        },
        error: {
            label: t('documents.status.error'),
            badgeClass: 'bg-red-100 text-red-700',
        },
    }), [t]);

    const fetchDocuments = useCallback(async () => {
        try {
            const response = await api.get(`/sources/${effectiveNotebookId ? `?notebook_id=${effectiveNotebookId}` : ''}`);
            setDocuments(response.data || []);
        } catch (error) {
            console.error('Failed to fetch sources:', error);
        } finally {
            setIsLoading(false);
        }
    }, [effectiveNotebookId]);

    const validateFile = useCallback((file) => {
        const ext = file.name.split('.').pop()?.toLowerCase() || '';
        const hasAllowedExt = ALLOWED_EXTENSIONS.includes(ext);
        if (!hasAllowedExt) return false;
        if (ext === 'txt') return true;

        const hasAllowedMime = ALLOWED_MIME_TYPES.has(normalizeMimeType(file.type));
        return hasAllowedExt && hasAllowedMime;
    }, []);

    const handleDragEnter = useCallback((event) => {
        event.preventDefault();
        event.stopPropagation();
        setIsDragActive(true);
        setUploadError('');
    }, []);

    const handleDragLeave = useCallback((event) => {
        event.preventDefault();
        event.stopPropagation();
        setIsDragActive(false);
    }, []);

    const handleDragOver = useCallback((event) => {
        event.preventDefault();
        event.stopPropagation();
    }, []);

    const handleDrop = useCallback((event) => {
        event.preventDefault();
        event.stopPropagation();
        setIsDragActive(false);

        const files = Array.from(event.dataTransfer.files);
        const validFiles = files.filter(validateFile);
        const invalidFiles = files.filter((f) => !validateFile(f));

        if (invalidFiles.length > 0) {
            setUploadError(t('documents.unsupportedFiles', { files: invalidFiles.map((f) => f.name).join(', ') }));
        }

        if (validFiles.length > 0) {
            setDraggedFiles(validFiles);
            setUploadError('');
        }
    }, [t, validateFile]);

    const uploadFiles = useCallback(async (files) => {
        if (!files || files.length === 0) return;

        setIsUploading(true);
        setUploadError('');

        const uploadPromises = files.map(async (file) => {
            const formData = new FormData();
            formData.append('file', file);
            if (effectiveNotebookId) {
                formData.append('notebook_id', String(effectiveNotebookId));
            }

            try {
                await api.post('/sources/upload', formData, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                });
                return { success: true, name: file.name };
            } catch (error) {
                return { success: false, name: file.name, error: error.response?.data?.detail || t('documents.uploadError') };
            }
        });

        const results = await Promise.all(uploadPromises);
        const failed = results.filter((r) => !r.success);

        if (failed.length > 0) {
            setUploadError(
                t('notebook.uploadFailed', { files: failed.map((f) => `${f.name}${f.error ? ` (${f.error})` : ''}`).join(', ') })
            );
        }

        setDraggedFiles([]);
        reset();
        await fetchDocuments();
        setIsUploading(false);
    }, [effectiveNotebookId, fetchDocuments, reset, t]);

    const fetchChunks = useCallback(async (docId, docName) => {
        setChunksModal({
            isOpen: true,
            docId,
            docName,
            chunks: [],
            isLoading: true,
            error: null,
        });

        try {
            const response = await api.get(`/sources/${docId}/chunks`);
            setChunksModal((prev) => ({
                ...prev,
                chunks: response.data || [],
                isLoading: false,
            }));
        } catch (error) {
            console.error('Failed to fetch chunks:', error);
            setChunksModal((prev) => ({
                ...prev,
                isLoading: false,
                error: error.response?.data?.detail || t('documents.chunksLoadFailed'),
            }));
        }
    }, [t]);

    const closeChunksModal = useCallback(() => {
        setChunksModal({
            isOpen: false,
            docId: null,
            docName: '',
            chunks: [],
            isLoading: false,
            error: null,
        });
    }, []);

    useEffect(() => {
        fetchDocuments();
    }, [fetchDocuments]);

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

    const sortedDocuments = useMemo(() => {
        const sorted = [...filteredDocuments];
        sorted.sort((a, b) => {
            let valA = a[sortField];
            let valB = b[sortField];

            if (sortField === 'name') {
                valA = String(valA || '').toLowerCase();
                valB = String(valB || '').toLowerCase();
                if (valA < valB) return sortOrder === 'asc' ? -1 : 1;
                if (valA > valB) return sortOrder === 'asc' ? 1 : -1;
                return 0;
            } else if (sortField === 'created_at') {
                const timeA = new Date(valA || 0).getTime();
                const timeB = new Date(valB || 0).getTime();
                return sortOrder === 'asc' ? timeA - timeB : timeB - timeA;
            } else if (sortField === 'size') {
                const sizeA = Number(valA || 0);
                const sizeB = Number(valB || 0);
                return sortOrder === 'asc' ? sizeA - sizeB : sizeB - sizeA;
            }
            return 0;
        });
        return sorted;
    }, [filteredDocuments, sortField, sortOrder]);

    const onDelete = async (id) => {
        if (!window.confirm(t('documents.deleteConfirm'))) return;

        try {
            await api.delete(`/sources/${id}`);
            setDocuments((prev) => prev.filter((doc) => doc.id !== id));
        } catch (error) {
            console.error('Delete failed:', error);
            alert(t('documents.deleteFailed'));
        }
    };

    return (
        <div className="space-y-6 px-4">
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">

                <div
                    onDragEnter={handleDragEnter}
                    onDragLeave={handleDragLeave}
                    onDragOver={handleDragOver}
                    onDrop={handleDrop}
                    className={cn(
                        'rounded-2xl border-2 border-dashed p-8 text-center transition-all duration-200',
                        isDragActive
                            ? 'border-[#1f3a60] bg-[#1f3a60]/5'
                            : 'border-slate-300 bg-slate-50',
                    )}
                >
                    <div className={cn(
                        'mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full transition-all duration-200',
                        isDragActive
                            ? 'bg-[#1f3a60] text-white'
                            : 'bg-[#1f3a60]/10 text-[#1f3a60]',
                    )}>
                        <CloudUpload className={cn('h-7 w-7', isDragActive && 'animate-bounce')} />
                    </div>
                    <h3 className="text-2xl font-bold text-slate-800">
                        {isDragActive ? t('documents.dropActive') : t('documents.dropIdle')}
                    </h3>
                    <p className="mt-1 text-sm text-slate-500">{t('documents.supportedFormats')}</p>

                    <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
                        <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-[#c5a059] px-5 py-2 text-sm font-semibold text-white transition hover:bg-[#b18f4e]">
                            <CloudUpload className="h-4 w-4" />
                            {t('documents.chooseFile')}
                            <input
                                type="file"
                                multiple
                                className="hidden"
                                accept=".pdf,.docx,.txt,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                {...register('file')}
                                onChange={(e) => {
                                    const files = Array.from(e.target.files || []);
                                    const valid = [];
                                    for (const file of files) {
                                        if (validateFile(file)) {
                                            valid.push(file);
                                        }
                                    }
                                    if (valid.length > 0) {
                                        setDraggedFiles(valid);
                                        setUploadError('');
                                    } else if (files.length > 0) {
                                        setUploadError(t('documents.invalidFormats'));
                                    }
                                }}
                            />
                        </label>

                        <Button
                            type="button"
                            disabled={isUploading || (draggedFiles.length === 0 && !selectedFile)}
                            onClick={() => uploadFiles(draggedFiles.length > 0 ? draggedFiles : selectedFile ? [selectedFile] : [])}
                        >
                            {isUploading ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    {t('documents.uploadLoading')}
                                </>
                            ) : draggedFiles.length > 1 ? (
                                t('documents.uploadMany', { count: draggedFiles.length })
                            ) : (
                                t('documents.uploadOne')
                            )}
                        </Button>
                    </div>

                    {(draggedFiles.length > 0 || selectedFile) && (
                        <div className="mt-4 rounded-lg bg-emerald-50 p-3">
                            <p className="text-sm font-semibold text-emerald-700">
                                {t('documents.pendingUpload', { files: (draggedFiles.length > 0 ? draggedFiles : selectedFile ? [selectedFile] : []).map((f) => f.name).join(', ') })}
                            </p>
                        </div>
                    )}

                    {uploadError && (
                        <p className="mt-3 text-sm font-semibold text-red-600">{uploadError}</p>
                    )}
                </div>
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
                                {status === 'all' ? t('documents.status.all') : statusMeta[status].label}
                                <span className="ml-1">{stats[status]}</span>
                            </button>
                        ))}
                    </div>

                    <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-slate-500">{t('documents.sort')}</span>
                        <select
                            value={`${sortField}-${sortOrder}`}
                            onChange={(e) => {
                                const [field, order] = e.target.value.split('-');
                                setSortField(field);
                                setSortOrder(order);
                            }}
                            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700 outline-none focus:border-[#1f3a60] focus:ring-1 focus:ring-[#1f3a60]"
                        >
                            <option value="created_at-desc">{t('documents.sortOptions.dateDesc')}</option>
                            <option value="created_at-asc">{t('documents.sortOptions.dateAsc')}</option>
                            <option value="name-asc">{t('documents.sortOptions.nameAsc')}</option>
                            <option value="name-desc">{t('documents.sortOptions.nameDesc')}</option>
                            <option value="size-desc">{t('documents.sortOptions.sizeDesc')}</option>
                            <option value="size-asc">{t('documents.sortOptions.sizeAsc')}</option>
                        </select>
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full min-w-[820px] text-left">
                        <thead className="bg-slate-50 text-xs uppercase tracking-[0.08em] text-slate-500">
                            <tr>
                                <th className="px-5 py-3 font-semibold">{t('documents.table.fileName')}</th>
                                <th className="px-5 py-3 font-semibold">{t('documents.table.language')}</th>
                                <th className="px-5 py-3 font-semibold">{t('documents.table.uploadedAt')}</th>
                                <th className="px-5 py-3 font-semibold">{t('documents.table.size')}</th>
                                <th className="px-5 py-3 font-semibold">{t('documents.table.status')}</th>
                                <th className="px-5 py-3 text-right font-semibold">{t('documents.table.actions')}</th>
                            </tr>
                        </thead>

                        <tbody>
                            {isLoading ? (
                                <tr>
                                    <td colSpan="6" className="px-5 py-12 text-center text-slate-500">
                                        <div className="inline-flex items-center gap-2">
                                            <Loader2 className="h-5 w-5 animate-spin" />
                                            {t('documents.loading')}
                                        </div>
                                    </td>
                                </tr>
                            ) : sortedDocuments.length === 0 ? (
                                <tr>
                                    <td colSpan="6" className="px-5 py-12 text-center text-slate-500">
                                        {t('documents.empty')}
                                    </td>
                                </tr>
                            ) : (
                                sortedDocuments.map((doc) => {
                                    const statusKey = resolveStatus(doc.status);
                                    const documentStatusMeta = statusMeta[statusKey];
                                    const languageTag = formatDocumentLanguage(doc.language);

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
                                                {formatLocaleDate(doc.created_at, locale, {
                                                    month: 'short',
                                                    day: 'numeric',
                                                    year: 'numeric',
                                                })}
                                            </td>

                                            <td className="px-5 py-3 text-slate-500">
                                                {formatSize(doc.size)}
                                            </td>

                                            <td className="px-5 py-3">
                                                <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold', documentStatusMeta.badgeClass)}>
                                                    {statusKey === 'indexing' ? (
                                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                    ) : statusKey === 'error' ? (
                                                        <AlertTriangle className="h-3.5 w-3.5" />
                                                    ) : (
                                                        <CheckCircle2 className="h-3.5 w-3.5" />
                                                    )}
                                                    {documentStatusMeta.label}
                                                </span>
                                            </td>

                                            <td className="px-5 py-3 text-right">
                                                <div className="inline-flex items-center gap-1">
                                                    <button
                                                        type="button"
                                                        onClick={() => fetchChunks(doc.id, doc.name)}
                                                        className="rounded-md p-1.5 text-slate-500 transition hover:bg-blue-50 hover:text-blue-600"
                                                        title={t('documents.viewChunks')}
                                                    >
                                                        <Eye className="h-4 w-4" />
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => onDelete(doc.id)}
                                                        className="rounded-md p-1.5 text-slate-500 transition hover:bg-red-50 hover:text-red-600"
                                                        title={t('documents.delete')}
                                                    >
                                                        <Trash2 className="h-4 w-4" />
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

            {/* Chunks Modal */}
            {chunksModal.isOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
                    <div className="max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-xl">
                        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
                            <div>
                                <h3 className="text-lg font-bold text-slate-800">{t('documents.chunksTitle')}</h3>
                                <p className="text-sm text-slate-500">{chunksModal.docName}</p>
                            </div>
                            <button
                                type="button"
                                onClick={closeChunksModal}
                                className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
                                aria-label={t('documents.close')}
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>

                        <div className="max-h-[calc(90vh-80px)] overflow-y-auto p-6">
                            {chunksModal.isLoading ? (
                                <div className="flex items-center justify-center py-12 text-slate-500">
                                    <Loader2 className="h-6 w-6 animate-spin" />
                                    <span className="ml-2">{t('documents.loadingChunks')}</span>
                                </div>
                            ) : chunksModal.error ? (
                                <div className="rounded-lg bg-red-50 p-4 text-center text-red-600">
                                    {chunksModal.error}
                                </div>
                            ) : chunksModal.chunks.length === 0 ? (
                                <div className="rounded-lg bg-slate-50 p-8 text-center text-slate-500">
                                    {t('documents.emptyChunks')}
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    <div className="mb-4 text-sm text-slate-500">
                                        {t('documents.totalChunks', { count: chunksModal.chunks.length })}
                                    </div>
                                    {chunksModal.chunks.map((chunk, index) => (
                                        <div
                                            key={chunk.id || index}
                                            className="rounded-xl border border-slate-200 bg-slate-50 p-4"
                                        >
                                            <div className="mb-2 flex items-center gap-2">
                                                <span className="rounded-full bg-[#1f3a60]/10 px-2 py-0.5 text-xs font-semibold text-[#1f3a60]">
                                                    {t('documents.page', { page: chunk.page || '?' })}
                                                </span>
                                                <span className="text-xs text-slate-400">
                                                    {t('documents.id', { id: chunk.id })}
                                                </span>
                                            </div>
                                            <p className="text-sm leading-relaxed text-slate-700 whitespace-pre-wrap">
                                                {chunk.text}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default AdminDocumentsPage;
