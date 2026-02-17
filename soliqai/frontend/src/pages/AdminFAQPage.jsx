import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Edit2, Search, Star, Trash2, X } from 'lucide-react';
import { faqService } from '../services/services';
import { Button } from '../components/ui/Button';
import Input from '../components/ui/Input';
import { cn } from '../lib/utils';

const defaultFormValues = {
    question: '',
    answer: '',
    category: '',
    priority: 0,
};

const AdminFAQPage = () => {
    const [faqs, setFaqs] = useState([]);
    const [categories, setCategories] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [editingId, setEditingId] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [categoryFilter, setCategoryFilter] = useState('');

    const {
        register,
        handleSubmit,
        reset,
        setValue,
        watch,
    } = useForm({ defaultValues: defaultFormValues });

    const priority = Number(watch('priority') || 0);

    const fetchFaqs = useCallback(async (filters = {}) => {
        const query = filters.q ?? '';
        const category = filters.category ?? '';
        setIsLoading(true);
        try {
            const response = await faqService.getAll({
                q: query,
                category,
            });
            setFaqs(response.data || []);

            const categoriesResponse = await faqService.getCategories();
            setCategories(categoriesResponse.data || []);
        } catch (error) {
            console.error('Failed to fetch FAQs', error);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchFaqs({ q: '', category: '' });
    }, [fetchFaqs]);

    const visibleFaqs = useMemo(() => {
        const query = searchQuery.trim().toLowerCase();
        return faqs.filter((faq) => {
            const matchQuery = !query || `${faq.question} ${faq.answer} ${faq.category || ''}`.toLowerCase().includes(query);
            const matchCategory = !categoryFilter || faq.category === categoryFilter;
            return matchQuery && matchCategory;
        });
    }, [faqs, searchQuery, categoryFilter]);

    const onSubmit = async (data) => {
        const payload = {
            question: data.question,
            answer: data.answer,
            category: data.category || null,
            priority: Number(data.priority || 0),
        };

        try {
            if (editingId) {
                await faqService.update(editingId, payload);
                setEditingId(null);
            } else {
                await faqService.create(payload);
            }

            reset(defaultFormValues);
            await fetchFaqs({ q: searchQuery, category: categoryFilter });
        } catch (error) {
            console.error('Failed to save FAQ', error);
        }
    };

    const handleEdit = (faq) => {
        setEditingId(faq.id);
        setValue('question', faq.question || '');
        setValue('answer', faq.answer || '');
        setValue('category', faq.category || '');
        setValue('priority', faq.priority || 0);
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Are you sure?')) return;

        try {
            await faqService.delete(id);
            if (editingId === id) {
                setEditingId(null);
                reset(defaultFormValues);
            }
            await fetchFaqs({ q: searchQuery, category: categoryFilter });
        } catch (error) {
            console.error('Failed to delete FAQ', error);
        }
    };

    const handleCancel = () => {
        setEditingId(null);
        reset(defaultFormValues);
    };

    const applyFilters = async () => {
        await fetchFaqs({ q: searchQuery, category: categoryFilter });
    };

    const resetFilters = async () => {
        setSearchQuery('');
        setCategoryFilter('');
        await fetchFaqs({ q: '', category: '' });
    };

    const selectCategoryChip = async (category) => {
        setCategoryFilter(category);
        await fetchFaqs({ q: searchQuery, category });
    };

    return (
        <div className="grid gap-6 xl:grid-cols-[400px_1fr]">
            <section className="flex h-[calc(100vh-13rem)] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-200 p-4">
                    <div className="mb-3 flex items-center gap-2">
                        <div className="relative flex-1">
                            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                            <Input
                                value={searchQuery}
                                onChange={(event) => setSearchQuery(event.target.value)}
                                className="pl-9"
                                placeholder="Search by keyword or ID..."
                            />
                        </div>
                        <Button type="button" variant="outline" onClick={applyFilters} className="shrink-0">
                            Search
                        </Button>
                    </div>

                    <div className="flex flex-wrap gap-2">
                        <button
                            type="button"
                            onClick={() => selectCategoryChip('')}
                            className={cn(
                                'rounded-full px-3 py-1.5 text-xs font-semibold transition',
                                categoryFilter === '' ? 'bg-[#1f3a60] text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                            )}
                        >
                            All FAQs
                            <span className="ml-1 rounded bg-white/25 px-1.5 py-0.5 text-[10px]">{faqs.length}</span>
                        </button>

                        {categories.map((category) => (
                            <button
                                key={category}
                                type="button"
                                onClick={() => selectCategoryChip(category)}
                                className={cn(
                                    'rounded-full px-3 py-1.5 text-xs font-semibold transition',
                                    categoryFilter === category
                                        ? 'bg-[#1f3a60] text-white'
                                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                )}
                            >
                                {category}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="scrollbar-soft flex-1 space-y-3 overflow-y-auto bg-slate-50 p-3">
                    {isLoading ? (
                        <div className="rounded-xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
                            Loading FAQs...
                        </div>
                    ) : visibleFaqs.length === 0 ? (
                        <div className="rounded-xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
                            No FAQs found
                        </div>
                    ) : (
                        visibleFaqs.map((faq) => {
                            const active = editingId === faq.id;

                            return (
                                <article
                                    key={faq.id}
                                    onClick={() => handleEdit(faq)}
                                    className={cn(
                                        'cursor-pointer rounded-xl border bg-white p-4 shadow-sm transition hover:border-[#1f3a60]/40 hover:shadow-md',
                                        active ? 'border-[#1f3a60]' : 'border-slate-200',
                                    )}
                                >
                                    <div className="mb-2 flex items-center justify-between gap-2">
                                        <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-blue-700">
                                            {faq.category || 'General'}
                                        </span>

                                        <div className="flex items-center gap-0.5">
                                            {Array.from({ length: 5 }).map((_, idx) => (
                                                <Star
                                                    key={`${faq.id}-star-${idx}`}
                                                    className={cn(
                                                        'h-3.5 w-3.5',
                                                        idx < Number(faq.priority || 0)
                                                            ? 'fill-amber-400 text-amber-400'
                                                            : 'text-slate-300',
                                                    )}
                                                />
                                            ))}
                                        </div>
                                    </div>

                                    <h3 className="mb-2 text-sm font-bold leading-snug text-slate-800">{faq.question}</h3>
                                    <p className="mb-3 text-xs leading-relaxed text-slate-500 [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2] overflow-hidden">
                                        {faq.answer}
                                    </p>

                                    <div className="flex items-center justify-between border-t border-slate-100 pt-2 text-[10px] text-slate-400">
                                        <span>ID: #{faq.id}</span>
                                        <div className="flex items-center gap-1">
                                            <button
                                                type="button"
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    handleEdit(faq);
                                                }}
                                                className="rounded p-1 transition hover:bg-slate-100 hover:text-[#1f3a60]"
                                            >
                                                <Edit2 className="h-3.5 w-3.5" />
                                            </button>
                                            <button
                                                type="button"
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    handleDelete(faq.id);
                                                }}
                                                className="rounded p-1 transition hover:bg-red-50 hover:text-red-600"
                                            >
                                                <Trash2 className="h-3.5 w-3.5" />
                                            </button>
                                        </div>
                                    </div>
                                </article>
                            );
                        })
                    )}
                </div>

                <div className="border-t border-slate-200 p-3">
                    <Button type="button" variant="ghost" className="w-full" onClick={resetFilters}>
                        Reset filters
                    </Button>
                </div>
            </section>

            <section className="h-[calc(100vh-13rem)] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="h-full overflow-y-auto p-6">
                    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
                        <div>
                            <h2 className="text-3xl font-extrabold text-[#1f3a60]">{editingId ? 'Edit FAQ Entry' : 'Create FAQ Entry'}</h2>
                            <p className="mt-1 text-sm text-slate-500">Update your knowledge base and keep answers synchronized with the AI model.</p>
                        </div>

                        <div className="flex items-center gap-2">
                            {editingId && (
                                <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold uppercase tracking-wide text-emerald-700">
                                    Published
                                </span>
                            )}
                            <Button type="button" variant="outline" onClick={handleCancel}>
                                <X className="h-4 w-4" />
                                New entry
                            </Button>
                        </div>
                    </div>

                    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6">
                        <div className="flex border-b border-slate-200 text-sm font-semibold">
                            <button type="button" className="border-b-2 border-[#1f3a60] px-4 py-2 text-[#1f3a60]">English</button>
                            <button type="button" className="px-4 py-2 text-slate-400">Тоҷикӣ</button>
                            <button type="button" className="px-4 py-2 text-slate-400">Русский</button>
                        </div>

                        <div>
                            <label className="mb-2 block text-sm font-semibold text-slate-700">
                                Question <span className="text-red-500">*</span>
                            </label>
                            <textarea
                                className="min-h-[88px] w-full resize-none rounded-lg border border-slate-300 px-4 py-3 text-sm text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-[#1f3a60]/25"
                                placeholder="Enter the frequently asked question..."
                                {...register('question', { required: true })}
                            />
                            <p className="mt-1 text-xs text-slate-400">Be specific. This text drives semantic search quality.</p>
                        </div>

                        <div className="grid gap-5 md:grid-cols-2">
                            <div>
                                <label className="mb-2 block text-sm font-semibold text-slate-700">Category</label>
                                <Input placeholder="Taxation" {...register('category')} />
                            </div>

                            <div>
                                <label className="mb-2 block text-sm font-semibold text-slate-700">Relevance Priority (1-5)</label>
                                <div className="flex items-center gap-1">
                                    {Array.from({ length: 5 }).map((_, idx) => {
                                        const value = idx + 1;
                                        return (
                                            <button
                                                key={`priority-${value}`}
                                                type="button"
                                                onClick={() => setValue('priority', value)}
                                                className="rounded p-1 transition hover:scale-105"
                                            >
                                                <Star
                                                    className={cn(
                                                        'h-6 w-6',
                                                        value <= priority
                                                            ? 'fill-amber-400 text-amber-400'
                                                            : 'text-slate-300',
                                                    )}
                                                />
                                            </button>
                                        );
                                    })}
                                </div>
                                <input type="hidden" {...register('priority')} />
                            </div>
                        </div>

                        <div>
                            <label className="mb-2 block text-sm font-semibold text-slate-700">
                                Answer <span className="text-red-500">*</span>
                            </label>

                            <div className="flex items-center gap-1 rounded-t-lg border border-b-0 border-slate-300 bg-slate-50 px-2 py-1">
                                <button type="button" className="rounded p-1 text-sm font-bold text-slate-500 hover:bg-slate-200">B</button>
                                <button type="button" className="rounded p-1 text-sm italic text-slate-500 hover:bg-slate-200">I</button>
                                <button type="button" className="rounded p-1 text-sm underline text-slate-500 hover:bg-slate-200">U</button>
                                <span className="mx-1 h-5 w-px bg-slate-300" />
                                <button type="button" className="rounded p-1 text-xs text-slate-500 hover:bg-slate-200">• List</button>
                                <button type="button" className="rounded p-1 text-xs text-slate-500 hover:bg-slate-200">1. List</button>
                            </div>

                            <textarea
                                className="min-h-[220px] w-full rounded-b-lg border border-slate-300 px-4 py-3 text-sm leading-relaxed text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-[#1f3a60]/25"
                                placeholder="Provide a complete legal answer..."
                                {...register('answer', { required: true })}
                            />
                        </div>

                        <div className="flex flex-wrap items-center justify-end gap-3">
                            {editingId && (
                                <Button type="button" variant="destructive" onClick={() => handleDelete(editingId)}>
                                    <Trash2 className="h-4 w-4" />
                                    Delete
                                </Button>
                            )}
                            <Button type="button" variant="outline" onClick={handleCancel}>
                                Cancel
                            </Button>
                            <Button type="submit">
                                {editingId ? 'Save Changes' : 'Create FAQ'}
                            </Button>
                        </div>
                    </form>
                </div>
            </section>
        </div>
    );
};

export default AdminFAQPage;
