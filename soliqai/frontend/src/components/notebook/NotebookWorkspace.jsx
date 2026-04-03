import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  FilePlus2,
  FileText,
  Loader2,
  MessageSquareText,
  NotebookPen,
  Plus,
} from 'lucide-react';
import { Link } from 'react-router-dom';

import { Button } from '../ui/Button';
import Input from '../ui/Input';
import { cn } from '../../lib/utils';
import { notesService } from '../../services/notesService';
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
  if (normalized.includes('index')) return 'Индексируется';
  if (normalized.includes('ready') || normalized.includes('done') || normalized.includes('success')) return 'Готов';

  return 'В очереди';
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
  const sourceInputRef = useRef(null);
  const [sourcesCollapsed, setSourcesCollapsed] = useState(false);
  const [notesCollapsed, setNotesCollapsed] = useState(false);

  const [sources, setSources] = useState([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sourcesError, setSourcesError] = useState('');
  const [uploadingSource, setUploadingSource] = useState(false);

  const [notes, setNotes] = useState([]);
  const [notesLoading, setNotesLoading] = useState(true);
  const [notesError, setNotesError] = useState('');
  const [noteComposerOpen, setNoteComposerOpen] = useState(false);
  const [noteTitle, setNoteTitle] = useState('');
  const [noteBody, setNoteBody] = useState('');
  const [savingNote, setSavingNote] = useState(false);

  useEffect(() => {
    let active = true;

    const fetchSources = async () => {
      try {
        setSourcesLoading(true);
        setSourcesError('');
        const response = await sourcesService.getAll(notebookId);
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
        const response = await notesService.getAll(notebookId);
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
  }, [notebookId]);

  const noteCountLabel = useMemo(() => {
    if (notes.length === 1) return '1 заметка';
    if (notes.length > 1 && notes.length < 5) return `${notes.length} заметки`;
    return `${notes.length} заметок`;
  }, [notes.length]);

  const handleUploadSourceClick = () => {
    sourceInputRef.current?.click();
  };

  const handleSourceUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setUploadingSource(true);
      setSourcesError('');
      const formData = new FormData();
      formData.append('file', file);
      formData.append('notebook_id', String(notebookId));
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

  const handleCreateNote = async (event) => {
    event.preventDefault();
    if (!noteTitle.trim()) return;

    try {
      setSavingNote(true);
      setNotesError('');
      const response = await notesService.create({
        notebook_id: notebookId,
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
            action={handleUploadSourceClick}
            actionLabel="Добавить источник"
            actionLoading={uploadingSource}
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
            action={() => setNoteComposerOpen((prev) => !prev)}
            actionLabel="Написать заметку"
            actionLoading={savingNote}
            footerLink={{ to: `/notebooks/${notebookId}/notes`, label: 'Открыть все заметки' }}
          >
            {noteComposerOpen ? (
              <form onSubmit={handleCreateNote} className="mb-4 space-y-3 rounded-3xl border border-slate-200 bg-slate-50 p-4">
                <Input value={noteTitle} onChange={(event) => setNoteTitle(event.target.value)} placeholder="Заголовок заметки" />
                <textarea
                  value={noteBody}
                  onChange={(event) => setNoteBody(event.target.value)}
                  placeholder="Кратко зафиксируйте наблюдения, выводы или следующие шаги..."
                  className="min-h-28 w-full rounded-2xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1f3a60]/30"
                />
                <div className="flex items-center justify-end gap-2">
                  <Button type="button" variant="ghost" onClick={() => setNoteComposerOpen(false)}>
                    Отмена
                  </Button>
                  <Button type="submit" isLoading={savingNote} disabled={!noteTitle.trim()}>
                    Сохранить
                  </Button>
                </div>
              </form>
            ) : null}

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
                  <article key={note.id} className="rounded-2xl border border-slate-200 p-4 transition hover:border-slate-300 hover:bg-slate-50">
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
            <ChatPage notebookId={Number(notebookId)} mode="notebookPanel" />
          </section>
        </div>
      </div>
    </div>
  );
};

export default NotebookWorkspace;
