import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FilePlus2,
  FileText,
  Link2,
  Loader2,
  MessageSquareText,
  NotebookPen,
  Plus,
  Search,
  X,
} from 'lucide-react';
import { Link } from 'react-router-dom';

import { Button } from '../ui/Button';
import Input from '../ui/Input';
import { cn } from '../../lib/utils';
import { notesService } from '../../services/notesService';
import { notebooksService } from '../../services/notebooksService';
import { sourcesService } from '../../services/sourcesService';
import ChatPage from '../../pages/ChatPage';

const formatDate = (value) => {
  if (!value) return '—';

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';

  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(parsed);
};

const formatSize = (size) => {
  if (!Number.isFinite(size)) return '—';
  if (size < 1024) return `${size} Б`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} КБ`;
  return `${(size / (1024 * 1024)).toFixed(1)} МБ`;
};

const getSourceStatusLabel = (status) => {
  const normalized = String(status || '').toLowerCase();

  if (normalized.includes('error')) return 'Ошибка';
  if (normalized === 'indexed' || normalized.includes('ready') || normalized.includes('done') || normalized.includes('success')) return 'Готов';
  if (normalized.includes('index')) return 'Индексируется';

  return 'В очереди';
};

const getNotebookLabel = (source, notebookNameById) => {
  if (source.notebook_id == null) return 'Сейчас не привязан к блокноту';

  return notebookNameById[source.notebook_id] || `Блокнот #${source.notebook_id}`;
};

/* ── Split-dropdown button (like Google NotebookLM) ─────────────────────── */
const AddSourceSplitButton = ({ onUpload, onExisting, isLoading }) => {
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!open) return undefined;
    const handleClick = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  return (
    <div ref={containerRef} className="relative flex w-full">
      {/* Primary action */}
      <button
        type="button"
        onClick={onUpload}
        disabled={isLoading}
        className="flex flex-1 items-center justify-center gap-2 rounded-l-lg bg-[#1f3a60] px-4 py-2 text-sm font-semibold text-white shadow-[0_8px_18px_rgba(31,58,96,0.22)] transition hover:bg-[#162945] disabled:pointer-events-none disabled:opacity-60"
      >
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Plus className="h-4 w-4" />
        )}
        Добавить источник
      </button>

      {/* Divider */}
      <div className="w-px bg-white/20" />

      {/* Chevron toggle */}
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        disabled={isLoading}
        className="flex items-center justify-center rounded-r-lg bg-[#1f3a60] px-2.5 py-2 text-white shadow-[0_8px_18px_rgba(31,58,96,0.22)] transition hover:bg-[#162945] disabled:pointer-events-none disabled:opacity-60"
        aria-label="Открыть меню добавления источника"
        aria-expanded={open}
      >
        <ChevronDown className={cn('h-4 w-4 transition-transform duration-150', open && 'rotate-180')} />
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1.5 w-full overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg">
          <button
            type="button"
            onClick={() => { setOpen(false); onUpload(); }}
            className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-sm text-slate-700 transition hover:bg-slate-50"
          >
            <Plus className="h-4 w-4 text-slate-400" />
            Добавить источник
          </button>
          <button
            type="button"
            onClick={() => { setOpen(false); onExisting(); }}
            className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-sm text-slate-700 transition hover:bg-slate-50"
          >
            <Link2 className="h-4 w-4 text-slate-400" />
            Добавить существующие источники
          </button>
        </div>
      )}
    </div>
  );
};

const NotebookSidePanel = ({
  icon: Icon,
  title,
  collapsed,
  onToggle,
  action,
  actionLabel,
  actionLoading,
  actionDisabled,
  renderAction,
  children,
  footerLink,
}) => {
  return (
    <section
      className={cn(
        'relative flex h-[68vh] min-h-[540px] shrink-0 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm transition-[width] duration-300 ease-out',
        collapsed ? 'w-11' : 'w-[19rem] xl:w-[21rem]',
      )}
    >
      {collapsed ? (
        <button
          type="button"
          onClick={onToggle}
          className="flex h-full w-full flex-col items-center justify-between bg-slate-50 py-4 text-slate-500 transition hover:bg-slate-100 hover:text-[#1f3a60]"
          aria-label={`Развернуть панель ${title}`}
        >
          <ChevronRight className="h-4 w-4" />
          <div className="flex items-center gap-2" style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>
            <Icon className="h-4 w-4" />
            <span className="text-xs font-semibold tracking-[0.24em] uppercase">{title}</span>
          </div>
          <span className="h-4 w-4" />
        </button>
      ) : (
        <div className="flex h-full min-h-0 w-full flex-col">
          <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-4">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full bg-[#1f3a60]/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#1f3a60]">
                <Icon className="h-3.5 w-3.5" />
                {title}
              </div>
            </div>

            <button
              type="button"
              onClick={onToggle}
              className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 transition hover:border-slate-300 hover:text-slate-900"
              aria-label={`Свернуть панель ${title}`}
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </div>

          <div className="border-b border-slate-200 px-4 py-3">
            {renderAction ? renderAction() : (
              <Button
                type="button"
                onClick={action}
                isLoading={actionLoading}
                disabled={actionDisabled}
                className="w-full justify-center"
              >
                <Plus className="h-4 w-4" />
                {actionLabel}
              </Button>
            )}
          </div>

          <div className="scrollbar-soft min-h-0 flex-1 overflow-y-auto px-4 py-4">{children}</div>

          {footerLink ? (
            <div className="border-t border-slate-200 px-4 py-3">
              <Link to={footerLink.to} className="text-sm font-semibold text-[#1f3a60] transition hover:text-[#162945] hover:underline">
                {footerLink.label}
              </Link>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
};

const EmptyPanelState = ({ icon: Icon, title, description }) => (
  <div className="flex h-full min-h-[280px] flex-col items-center justify-center rounded-3xl border border-dashed border-slate-200 bg-slate-50/70 px-6 text-center">
    <div className="rounded-2xl bg-white p-4 text-[#1f3a60] shadow-sm">
      <Icon className="h-6 w-6" />
    </div>
    <p className="mt-4 text-sm font-semibold text-slate-800">{title}</p>
    <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>
  </div>
);

const NotebookWorkspace = ({ notebookId }) => {
  const currentNotebookId = Number(notebookId);
  const sourceInputRef = useRef(null);
  const [sourcesCollapsed, setSourcesCollapsed] = useState(false);
  const [notesCollapsed, setNotesCollapsed] = useState(false);

  const [sources, setSources] = useState([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sourcesError, setSourcesError] = useState('');
  const [uploadingSource, setUploadingSource] = useState(false);
  const [sourceSheetOpen, setSourceSheetOpen] = useState(false);
  const [sourceSheetMode, setSourceSheetMode] = useState('actions');
  const [sourceSearch, setSourceSearch] = useState('');
  const [existingSources, setExistingSources] = useState([]);
  const [existingSourcesLoading, setExistingSourcesLoading] = useState(false);
  const [existingSourcesError, setExistingSourcesError] = useState('');
  const [selectedExistingSourceIds, setSelectedExistingSourceIds] = useState([]);
  const [attachingExistingSources, setAttachingExistingSources] = useState(false);
  const [notebooks, setNotebooks] = useState([]);

  const [notes, setNotes] = useState([]);
  const [notesLoading, setNotesLoading] = useState(true);
  const [notesError, setNotesError] = useState('');
  const [selectedNote, setSelectedNote] = useState(null);
  const [noteComposerOpen, setNoteComposerOpen] = useState(false);
  const [noteTitle, setNoteTitle] = useState('');
  const [noteBody, setNoteBody] = useState('');
  const [savingNote, setSavingNote] = useState(false);

  const loadSources = async ({ keepLoading = false } = {}) => {
    try {
      if (!keepLoading) {
        setSourcesLoading(true);
      }
      setSourcesError('');
      const response = await sourcesService.getAll(currentNotebookId);
      setSources(response.data || []);
    } catch (error) {
      console.error('Failed to fetch notebook sources', error);
      setSources([]);
      setSourcesError(error.response?.data?.detail || 'Не удалось загрузить источники.');
    } finally {
      if (!keepLoading) {
        setSourcesLoading(false);
      }
    }
  };

  useEffect(() => {
    let active = true;

    const fetchSources = async () => {
      try {
        setSourcesLoading(true);
        setSourcesError('');
        const response = await sourcesService.getAll(currentNotebookId);
        if (!active) return;
        setSources(response.data || []);
      } catch (error) {
        if (!active) return;
        console.error('Failed to fetch notebook sources', error);
        setSources([]);
        setSourcesError(error.response?.data?.detail || 'Не удалось загрузить источники.');
      } finally {
        if (active) {
          setSourcesLoading(false);
        }
      }
    };

    const fetchNotes = async () => {
      try {
        setNotesLoading(true);
        setNotesError('');
        const response = await notesService.getAll(currentNotebookId);
        if (!active) return;
        setNotes(response.data || []);
      } catch (error) {
        if (!active) return;
        console.error('Failed to fetch notebook notes', error);
        setNotes([]);
        setNotesError(error.response?.data?.detail || 'Не удалось загрузить заметки.');
      } finally {
        if (active) {
          setNotesLoading(false);
        }
      }
    };

    fetchSources();
    fetchNotes();

    return () => {
      active = false;
    };
  }, [currentNotebookId]);

  useEffect(() => {
    if (!sourceSheetOpen || sourceSheetMode !== 'existing') return undefined;

    let active = true;

    const fetchExistingSources = async () => {
      try {
        setExistingSourcesLoading(true);
        setExistingSourcesError('');
        const [sourcesResponse, notebooksResponse] = await Promise.all([
          sourcesService.getAll(),
          notebooksService.getAll(),
        ]);

        if (!active) return;

        setExistingSources(sourcesResponse.data || []);
        setNotebooks(notebooksResponse.data || []);
      } catch (error) {
        if (!active) return;
        console.error('Failed to fetch existing sources', error);
        setExistingSources([]);
        setNotebooks([]);
        setExistingSourcesError(error.response?.data?.detail || 'Не удалось загрузить существующие источники.');
      } finally {
        if (active) {
          setExistingSourcesLoading(false);
        }
      }
    };

    fetchExistingSources();

    return () => {
      active = false;
    };
  }, [sourceSheetMode, sourceSheetOpen]);

  const noteCountLabel = useMemo(() => {
    if (notes.length === 1) return '1 заметка';
    if (notes.length > 1 && notes.length < 5) return `${notes.length} заметки`;
    return `${notes.length} заметок`;
  }, [notes.length]);

  const notebookNameById = useMemo(
    () => Object.fromEntries((notebooks || []).map((notebook) => [notebook.id, notebook.name])),
    [notebooks],
  );

  const attachableSources = useMemo(
    () => existingSources.filter((source) => source.notebook_id !== currentNotebookId),
    [currentNotebookId, existingSources],
  );

  const closeSourceSheet = () => {
    setSourceSheetOpen(false);
    setSourceSheetMode('actions');
    setExistingSourcesError('');
    setSelectedExistingSourceIds([]);
    setSourceSearch('');
  };


  const handleUploadSourceClick = () => {
    closeSourceSheet();
    sourceInputRef.current?.click();
  };

  const handleOpenExistingSources = () => {
    setExistingSourcesError('');
    setSelectedExistingSourceIds([]);
    setSourceSheetMode('existing');
    setSourceSheetOpen(true);
  };

  const handleExistingSourceSelection = (sourceId) => {
    setSelectedExistingSourceIds((prev) => (
      prev.includes(sourceId)
        ? prev.filter((id) => id !== sourceId)
        : [...prev, sourceId]
    ));
  };

  const handleSourceUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setUploadingSource(true);
      setSourcesError('');
      const formData = new FormData();
      formData.append('file', file);
      formData.append('notebook_id', String(currentNotebookId));
      const response = await sourcesService.upload(formData);
      setSources((prev) => [response.data, ...prev]);
      setSourcesCollapsed(false);
    } catch (error) {
      console.error('Failed to upload source', error);
      setSourcesError(error.response?.data?.detail || 'Не удалось добавить источник.');
    } finally {
      setUploadingSource(false);
      event.target.value = '';
    }
  };

  const handleAttachExistingSources = async () => {
    if (selectedExistingSourceIds.length === 0) return;

    try {
      setAttachingExistingSources(true);
      setExistingSourcesError('');
      await sourcesService.attachExisting({
        notebook_id: currentNotebookId,
        source_ids: selectedExistingSourceIds,
      });
      await loadSources({ keepLoading: true });
      setSourcesCollapsed(false);
      closeSourceSheet();
    } catch (error) {
      console.error('Failed to attach existing sources', error);
      setExistingSourcesError(error.response?.data?.detail || 'Не удалось добавить существующие источники.');
    } finally {
      setAttachingExistingSources(false);
    }
  };

  const handleCreateNote = async (event) => {
    event.preventDefault();
    if (!noteTitle.trim()) return;

    try {
      setSavingNote(true);
      setNotesError('');
      const response = await notesService.create({
        notebook_id: currentNotebookId,
        title: noteTitle.trim(),
        body: noteBody.trim(),
      });

      setNotes((prev) => [response.data, ...prev]);
      setNoteTitle('');
      setNoteBody('');
      setNoteComposerOpen(false);
      setNotesCollapsed(false);
    } catch (error) {
      console.error('Failed to create note', error);
      setNotesError(error.response?.data?.detail || 'Не удалось создать заметку.');
    } finally {
      setSavingNote(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <input ref={sourceInputRef} type="file" className="hidden" onChange={handleSourceUpload} />

      <div className="overflow-x-auto pb-1">
        <div className="flex min-h-0 min-w-[940px] gap-4">
          <NotebookSidePanel
            icon={FileText}
            title="Источники"
            collapsed={sourcesCollapsed}
            onToggle={() => setSourcesCollapsed((prev) => !prev)}
            renderAction={() => (
              <AddSourceSplitButton
                onUpload={handleUploadSourceClick}
                onExisting={handleOpenExistingSources}
                isLoading={uploadingSource}
              />
            )}
            footerLink={{ to: `/notebooks/${notebookId}/sources`, label: 'Открыть все источники' }}
          >
            {sourcesLoading ? (
              <div className="flex h-full items-center justify-center text-sm text-slate-500">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Загружаем источники...
              </div>
            ) : sourcesError ? (
              <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                {sourcesError}
              </div>
            ) : sources.length === 0 ? (
              <EmptyPanelState
                icon={FilePlus2}
                title="Источников пока нет"
                description="Добавьте первый файл в этот блокнот, чтобы использовать его в заметках и чате."
              />
            ) : (
              <div className="space-y-3">
                {sources.map((source) => (
                  <article key={source.id} className="rounded-2xl border border-slate-200 p-4 transition hover:border-slate-300 hover:bg-slate-50">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-slate-900">{source.name}</p>
                        <p className="mt-1 text-xs text-slate-400">ID #{source.id}</p>
                      </div>
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                        {getSourceStatusLabel(source.status)}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                      <span>Добавлен {formatDate(source.created_at)}</span>
                      <span>{formatSize(source.size)}</span>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </NotebookSidePanel>

          <NotebookSidePanel
            icon={NotebookPen}
            title="Заметки"
            collapsed={notesCollapsed}
            onToggle={() => setNotesCollapsed((prev) => !prev)}
            action={() => setNoteComposerOpen(true)}
            actionLabel="Написать заметку"
            footerLink={{ to: `/notebooks/${notebookId}/notes`, label: 'Открыть все заметки' }}
          >

            {notesLoading ? (
              <div className="flex h-full items-center justify-center text-sm text-slate-500">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Загружаем заметки...
              </div>
            ) : notesError ? (
              <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                {notesError}
              </div>
            ) : notes.length === 0 ? (
              <EmptyPanelState
                icon={MessageSquareText}
                title="Заметок пока нет"
                description="Создайте первую заметку, чтобы зафиксировать выводы по материалам этого блокнота."
              />
            ) : (
              <div className="space-y-3">
                <div className="rounded-2xl bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                  {noteCountLabel}
                </div>
                {notes.map((note) => (
                  <article
                    key={note.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedNote(note)}
                    onKeyDown={(e) => e.key === 'Enter' && setSelectedNote(note)}
                    className="cursor-pointer rounded-2xl border border-slate-200 p-4 transition hover:border-[#1f3a60]/40 hover:bg-slate-50"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="text-sm font-semibold text-slate-900">{note.title}</h3>
                      <span className="rounded-full bg-[#1f3a60]/10 px-2.5 py-1 text-[11px] font-semibold text-[#1f3a60]">
                        {note.kind || 'manual'}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-4 whitespace-pre-wrap text-sm leading-6 text-slate-500">
                      {note.body || 'Без текста'}
                    </p>
                    <div className="mt-3 text-xs text-slate-400">Обновлено {formatDate(note.updated_at || note.created_at)}</div>
                  </article>
                ))}
              </div>
            )}
          </NotebookSidePanel>

          <section className="flex h-[68vh] min-h-[540px] min-w-[24rem] flex-1 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
            <ChatPage notebookId={currentNotebookId} mode="notebookPanel" />
          </section>
        </div>
      </div>

      {/* Existing-sources MODAL — opened via dropdown “Добавить существующие источники” */}
      {sourceSheetOpen && sourceSheetMode === 'existing' ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Добавить существующие источники"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-[2px]"
            onClick={closeSourceSheet}
          />

          {/* Dialog */}
          <div className="relative flex w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
            {/* Header */}
            <div className="flex items-start justify-between gap-4 px-6 py-5">
              <div>
                <div className="flex items-center gap-2">
                  <Link2 className="h-4 w-4 text-[#1f3a60]" />
                  <p className="text-[15px] font-semibold text-slate-900">Добавить существующие источники</p>
                </div>
                <p className="mt-1 text-sm text-slate-500">
                  Выберите существующие источники из всех блокнотов для добавления в текущий.
                </p>
              </div>
              <button
                type="button"
                onClick={closeSourceSheet}
                className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                aria-label="Закрыть"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Search */}
            <div className="px-6 pb-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Поиск источников по названию или URL..."
                  value={sourceSearch}
                  onChange={(e) => setSourceSearch(e.target.value)}
                  className="h-10 w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 text-sm text-slate-800 placeholder-slate-400 transition focus:border-[#1f3a60] focus:outline-none focus:ring-2 focus:ring-[#1f3a60]/20"
                />
              </div>
            </div>

            {/* Body */}
            <div className="min-h-[240px] flex-1 overflow-y-auto px-6 pb-2">
              {existingSourcesLoading ? (
                <div className="flex h-48 items-center justify-center text-sm text-slate-500">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Загружаем доступные источники...
                </div>
              ) : existingSourcesError ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                  {existingSourcesError}
                </div>
              ) : (() => {
                const filtered = attachableSources.filter((s) =>
                  !sourceSearch.trim() ||
                  s.name?.toLowerCase().includes(sourceSearch.toLowerCase())
                );
                if (filtered.length === 0) {
                  return (
                    <div className="flex h-48 flex-col items-center justify-center gap-2 text-sm text-slate-500">
                      <FileText className="h-8 w-8 text-slate-300" />
                      {attachableSources.length === 0 ? 'Блокноты не найдены.' : 'Ничего не найдено.'}
                    </div>
                  );
                }
                return (
                  <div className="space-y-2 py-2">
                    {filtered.map((source) => {
                      const isSelected = selectedExistingSourceIds.includes(source.id);
                      return (
                        <label
                          key={source.id}
                          className={cn(
                            'flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 transition',
                            isSelected
                              ? 'border-[#1f3a60] bg-[#1f3a60]/5'
                              : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50',
                          )}
                        >
                          <input
                            type="checkbox"
                            className="h-4 w-4 shrink-0 rounded border-slate-300 text-[#1f3a60] focus:ring-[#1f3a60]"
                            checked={isSelected}
                            onChange={() => handleExistingSourceSelection(source.id)}
                          />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-semibold text-slate-900">{source.name}</p>
                            <p className="mt-0.5 text-xs text-slate-400">
                              {getNotebookLabel(source, notebookNameById)} · {formatSize(source.size)}
                            </p>
                          </div>
                          <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                            {getSourceStatusLabel(source.status)}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                );
              })()}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 border-t border-slate-200 px-6 py-4">
              <Button type="button" variant="ghost" onClick={closeSourceSheet}>
                Отмена
              </Button>
              <Button
                type="button"
                onClick={handleAttachExistingSources}
                isLoading={attachingExistingSources}
                disabled={
                  selectedExistingSourceIds.length === 0 ||
                  existingSourcesLoading ||
                  attachableSources.length === 0
                }
              >
                Добавить выбранное
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Note VIEW modal */}
      {selectedNote ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Просмотр заметки"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-[2px]"
            onClick={() => setSelectedNote(null)}
          />

          {/* Dialog */}
          <div className="relative flex w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
            {/* Header */}
            <div className="flex items-start justify-between gap-4 px-6 py-5">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <NotebookPen className="h-4 w-4 shrink-0 text-[#1f3a60]" />
                  <p className="truncate text-[15px] font-semibold text-slate-900">{selectedNote.title}</p>
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  Создано {formatDate(selectedNote.created_at)}
                  {selectedNote.updated_at && selectedNote.updated_at !== selectedNote.created_at
                    ? ` · Изменено ${formatDate(selectedNote.updated_at)}`
                    : ''}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedNote(null)}
                className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                aria-label="Закрыть"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Body */}
            <div className="max-h-[60vh] overflow-y-auto px-6 pb-6">
              {selectedNote.body ? (
                <p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">{selectedNote.body}</p>
              ) : (
                <p className="text-sm italic text-slate-400">Текст заметки отсутствует.</p>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between border-t border-slate-200 px-6 py-4">
              <span className="rounded-full bg-[#1f3a60]/10 px-3 py-1 text-[11px] font-semibold text-[#1f3a60]">
                {selectedNote.kind || 'manual'}
              </span>
              <Button type="button" variant="ghost" onClick={() => setSelectedNote(null)}>
                Закрыть
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Note composer MODAL */}
      {noteComposerOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Написать заметку"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-[2px]"
            onClick={() => { setNoteComposerOpen(false); setNoteTitle(''); setNoteBody(''); }}
          />

          {/* Dialog */}
          <div className="relative flex w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
            {/* Header */}
            <div className="flex items-start justify-between gap-4 px-6 py-5">
              <div>
                <div className="flex items-center gap-2">
                  <NotebookPen className="h-4 w-4 text-[#1f3a60]" />
                  <p className="text-[15px] font-semibold text-slate-900">Написать заметку</p>
                </div>
                <p className="mt-1 text-sm text-slate-500">
                  Зафиксируйте наблюдения, выводы или следующие шаги.
                </p>
              </div>
              <button
                type="button"
                onClick={() => { setNoteComposerOpen(false); setNoteTitle(''); setNoteBody(''); }}
                className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                aria-label="Закрыть"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Form body */}
            <form onSubmit={handleCreateNote} className="flex flex-col gap-4 px-6 pb-6">
              <input
                type="text"
                value={noteTitle}
                onChange={(e) => setNoteTitle(e.target.value)}
                placeholder="Заголовок заметки"
                className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-800 placeholder-slate-400 transition focus:border-[#1f3a60] focus:outline-none focus:ring-2 focus:ring-[#1f3a60]/20"
                autoFocus
              />
              <textarea
                value={noteBody}
                onChange={(e) => setNoteBody(e.target.value)}
                placeholder="Кратко зафиксируйте наблюдения, выводы или следующие шаги..."
                rows={6}
                className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 placeholder-slate-400 transition focus:border-[#1f3a60] focus:outline-none focus:ring-2 focus:ring-[#1f3a60]/20"
              />
              {notesError ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                  {notesError}
                </div>
              ) : null}
              <div className="flex items-center justify-end gap-3 border-t border-slate-200 pt-4">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => { setNoteComposerOpen(false); setNoteTitle(''); setNoteBody(''); }}
                >
                  Отмена
                </Button>
                <Button type="submit" isLoading={savingNote} disabled={!noteTitle.trim()}>
                  Сохранить
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default NotebookWorkspace;
