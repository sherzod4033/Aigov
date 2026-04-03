import React, { useEffect, useMemo, useState } from 'react';
import { Outlet, useParams } from 'react-router-dom';

import { useNotebookHeader } from '../components/layout/NotebookHeaderContext';
import { notebooksService } from '../services/notebooksService';
import { notesService } from '../services/notesService';
import { sourcesService } from '../services/sourcesService';

const ACTIVE_NOTEBOOK_STORAGE_KEY = 'knowledgeai.activeNotebookId';

const formatNotebookDate = (value) => {
  if (!value) return '—';

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';

  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed);
};

const resolveLatestNotebookActivity = (notebook, sources, notes) => {
  const candidates = [notebook?.created_at];

  (sources || []).forEach((source) => {
    candidates.push(source?.created_at);
  });

  (notes || []).forEach((note) => {
    candidates.push(note?.updated_at || note?.created_at);
  });

  const timestamps = candidates
    .map((value) => new Date(value).getTime())
    .filter((value) => Number.isFinite(value));

  if (timestamps.length === 0) return null;

  return new Date(Math.max(...timestamps)).toISOString();
};

const NotebookLayout = () => {
  const { notebookId } = useParams();
  const [notebook, setNotebook] = useState(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const { setNotebookHeader, setNotebookActions } = useNotebookHeader();

  useEffect(() => {
    if (!notebookId) return;
    localStorage.setItem(ACTIVE_NOTEBOOK_STORAGE_KEY, notebookId);
  }, [notebookId]);

  useEffect(() => {
    let isMounted = true;

    const fetchNotebook = async () => {
      if (!notebookId) return;

      try {
        setIsLoading(true);
        setError('');
        const [notebookResponse, sourcesResponse, notesResponse] = await Promise.allSettled([
          notebooksService.getById(notebookId),
          sourcesService.getAll(notebookId),
          notesService.getAll(notebookId),
        ]);

        if (!isMounted) return;

        if (notebookResponse.status !== 'fulfilled') {
          throw notebookResponse.reason;
        }

        const nextNotebook = notebookResponse.value.data || null;
        const nextSources = sourcesResponse.status === 'fulfilled' ? (sourcesResponse.value.data || []) : [];
        const nextNotes = notesResponse.status === 'fulfilled' ? (notesResponse.value.data || []) : [];

        setNotebook(nextNotebook);
        setLastUpdatedAt(resolveLatestNotebookActivity(nextNotebook, nextSources, nextNotes));
      } catch (fetchError) {
        if (!isMounted) return;
        console.error('Failed to fetch notebook', fetchError);
        setNotebook(null);
        setLastUpdatedAt(null);
        setError(fetchError.response?.data?.detail || 'Не удалось загрузить блокнот.');
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchNotebook();

    return () => {
      isMounted = false;
    };
  }, [notebookId]);

  const contextValue = useMemo(
    () => ({ notebook, isLoading, error, lastUpdatedAt }),
    [notebook, isLoading, error, lastUpdatedAt],
  );

  useEffect(() => {
    if (!notebook || !notebookId) {
      setNotebookHeader(null);
      return undefined;
    }

    setNotebookHeader({
      id: notebookId,
      name: notebook.name || 'Блокнот',
      description: notebook.description || '',
      createdAtText: formatNotebookDate(notebook.created_at),
      updatedAtText: formatNotebookDate(lastUpdatedAt || notebook.created_at),
      domainProfile: notebook.domain_profile || '—',
    });

    return () => {
      setNotebookHeader(null);
    };
  }, [notebook, notebookId, lastUpdatedAt, setNotebookHeader]);

  useEffect(() => {
    setNotebookActions({
      onArchive: undefined,
      onDelete: undefined,
      archiveDisabled: true,
      deleteDisabled: true,
      archiveTitle: 'Архивация пока не поддерживается API',
      deleteTitle: 'Удаление пока не поддерживается API',
    });

    return () => {
      setNotebookActions(null);
    };
  }, [setNotebookActions]);

  return (
    <div className="flex h-full flex-col gap-6">
      <Outlet context={contextValue} />
    </div>
  );
};

export default NotebookLayout;
