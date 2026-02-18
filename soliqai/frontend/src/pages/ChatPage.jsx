import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, Paperclip, Shield, ThumbsDown, ThumbsUp, User } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { chatService } from '../services/services';
import { Button } from '../components/ui/Button';
import Input from '../components/ui/Input';
import { cn } from '../lib/utils';

const INITIAL_ASSISTANT_MESSAGE = {
    role: 'assistant',
    content: 'Здравствуйте! Я SoliqAI, ваш налоговый помощник. Задавайте вопросы.',
};

const QUICK_QUESTIONS = [
    'Как оплатить НДС?',
    'Ставки налога на патент 2024',
    'Как сдать налоговую декларацию?',
    'Найти ближайшую налоговую инспекцию',
];

const CHAT_HISTORY_STORAGE_PREFIX = 'soliqai.chat.history.';
const MAX_PERSISTED_MESSAGES = 100;
const PENDING_MESSAGE_TTL_MS = 120000;
const PENDING_PLACEHOLDER_TEXT = 'Думаю...';
const INTERRUPTED_PENDING_TEXT = 'Запрос был прерван при смене раздела. Отправьте вопрос снова.';

const resolveCurrentUsername = () => {
    if (typeof window === 'undefined') return 'anonymous';
    const token = localStorage.getItem('token');
    if (!token) return 'anonymous';

    try {
        const payloadPart = token.split('.')[1];
        if (!payloadPart) return 'anonymous';
        const base64 = payloadPart.replace(/-/g, '+').replace(/_/g, '/');
        const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=');
        const payload = JSON.parse(atob(padded));
        const username = payload?.sub;
        return typeof username === 'string' && username.trim() ? username.trim() : 'anonymous';
    } catch {
        return 'anonymous';
    }
};

const getChatStorageKey = () => `${CHAT_HISTORY_STORAGE_PREFIX}${resolveCurrentUsername()}`;

const createRequestId = () => {
    const now = Date.now();
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return `req-${now}-${crypto.randomUUID()}`;
    }
    return `req-${now}-${Math.random().toString(16).slice(2)}`;
};

const getCreatedAtFromRequestId = (requestId) => {
    if (typeof requestId !== 'string') return null;
    const match = requestId.match(/^req-(\d+)-/);
    if (!match) return null;
    const parsed = Number(match[1]);
    return Number.isFinite(parsed) ? parsed : null;
};

const normalizeMessage = (message) => {
    if (!message || typeof message !== 'object') return null;
    if (message.role !== 'assistant' && message.role !== 'user') return null;
    if (typeof message.content !== 'string') return null;

    const normalized = {
        role: message.role,
        content: message.content,
    };

    if (message.pending === true) {
        normalized.pending = true;
        normalized.requestId = typeof message.requestId === 'string' ? message.requestId : createRequestId();
        normalized.createdAt = typeof message.createdAt === 'number' ? message.createdAt : Date.now();
    }

    if (Array.isArray(message.sources)) {
        normalized.sources = message.sources;
    }

    if (typeof message.logId === 'number') {
        normalized.logId = message.logId;
    }

    if (message.feedback === 'up' || message.feedback === 'down') {
        normalized.feedback = message.feedback;
    }

    return normalized;
};

const normalizeMessages = (messages) => {
    const sanitized = Array.isArray(messages)
        ? messages.map(normalizeMessage).filter(Boolean)
        : [];

    if (sanitized.length === 0) return [INITIAL_ASSISTANT_MESSAGE];
    if (sanitized[0].role !== 'assistant') return [INITIAL_ASSISTANT_MESSAGE, ...sanitized];
    return sanitized;
};

const replacePendingMessageByRequestId = (messages, requestId, nextMessage) => {
    if (!requestId) return [...messages, nextMessage];

    let replaced = false;
    const updated = messages.map((message) => {
        if (!replaced && message.pending === true && message.requestId === requestId) {
            replaced = true;
            return nextMessage;
        }
        return message;
    });

    if (!replaced) {
        updated.push(nextMessage);
    }

    return updated;
};

const resolvePendingMessages = (messages) => {
    const now = Date.now();
    let changed = false;

    const updated = messages.map((message) => {
        if (message.pending !== true) return message;
        const createdAt = typeof message.createdAt === 'number' ? message.createdAt : now;
        if (now - createdAt <= PENDING_MESSAGE_TTL_MS) return message;
        changed = true;
        return {
            role: 'assistant',
            content: INTERRUPTED_PENDING_TEXT,
        };
    });

    return { messages: updated, changed };
};

const loadMessagesFromStorage = (storageKey) => {
    if (typeof window === 'undefined') return [INITIAL_ASSISTANT_MESSAGE];

    try {
        const raw = localStorage.getItem(storageKey);
        if (!raw) return [INITIAL_ASSISTANT_MESSAGE];
        const normalized = normalizeMessages(JSON.parse(raw));
        const { messages: resolved, changed } = resolvePendingMessages(normalized);
        if (changed) {
            localStorage.setItem(storageKey, JSON.stringify(resolved));
        }
        return resolved;
    } catch {
        return [INITIAL_ASSISTANT_MESSAGE];
    }
};

const persistMessagesToStorage = (storageKey, messages) => {
    if (typeof window === 'undefined') return;

    try {
        const normalized = normalizeMessages(messages).slice(-MAX_PERSISTED_MESSAGES);
        localStorage.setItem(storageKey, JSON.stringify(normalized));
    } catch (error) {
        console.error('Failed to persist chat history', error);
    }
};

const renderInlineMarkdown = (text) => {
    const parts = (text || '').split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g).filter(Boolean);

    return parts.map((part, index) => {
        if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>;
        }

        if (part.startsWith('`') && part.endsWith('`')) {
            return (
                <code key={`${part}-${index}`} className="rounded bg-slate-100 px-1 py-0.5 text-slate-700">
                    {part.slice(1, -1)}
                </code>
            );
        }

        const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
        if (linkMatch) {
            const [, label, href] = linkMatch;
            return (
                <a
                    key={`${part}-${index}`}
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    className="font-semibold text-[#1f3a60] hover:underline"
                >
                    {label}
                </a>
            );
        }

        return <React.Fragment key={`${part}-${index}`}>{part}</React.Fragment>;
    });
};

const MarkdownContent = ({ content }) => {
    const lines = (content || '').split('\n');

    return (
        <div className="space-y-1.5 leading-relaxed">
            {lines.map((line, index) => {
                if (line.startsWith('### ')) {
                    return <h3 key={index} className="text-sm font-semibold">{renderInlineMarkdown(line.slice(4))}</h3>;
                }
                if (line.startsWith('## ')) {
                    return <h2 key={index} className="text-base font-semibold">{renderInlineMarkdown(line.slice(3))}</h2>;
                }
                if (line.startsWith('# ')) {
                    return <h1 key={index} className="text-lg font-bold">{renderInlineMarkdown(line.slice(2))}</h1>;
                }
                if (line.startsWith('- ')) {
                    return (
                        <div key={index} className="flex items-start gap-2 pl-1">
                            <span className="mt-1">•</span>
                            <span>{renderInlineMarkdown(line.slice(2))}</span>
                        </div>
                    );
                }
                return <p key={index} className="whitespace-pre-wrap">{renderInlineMarkdown(line)}</p>;
            })}
        </div>
    );
};

const formatTodayLabel = () => {
    const date = new Date();
    const formatted = new Intl.DateTimeFormat('en-US', {
        month: 'long',
        day: 'numeric',
    }).format(date);
    return `Today, ${formatted}`;
};

const ChatPage = () => {
    const { register, handleSubmit, reset } = useForm();
    const chatStorageKey = getChatStorageKey();
    const [messages, setMessages] = useState(() => loadMessagesFromStorage(chatStorageKey));
    const messagesEndRef = useRef(null);

    const hasPendingMessage = messages.some((message) => message.pending === true);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    useEffect(() => {
        setMessages(loadMessagesFromStorage(chatStorageKey));
    }, [chatStorageKey]);

    useEffect(() => {
        persistMessagesToStorage(chatStorageKey, messages);
    }, [chatStorageKey, messages]);

    const submitMessage = async (messageText) => {
        const cleanMessage = (messageText || '').trim();
        if (!cleanMessage || hasPendingMessage) return;

        const requestId = createRequestId();
        const userMessage = { role: 'user', content: cleanMessage };
        const pendingMessage = {
            role: 'assistant',
            content: PENDING_PLACEHOLDER_TEXT,
            pending: true,
            requestId,
            createdAt: getCreatedAtFromRequestId(requestId),
        };

        setMessages((prev) => {
            const updated = [...prev, userMessage, pendingMessage];
            persistMessagesToStorage(chatStorageKey, updated);
            return updated;
        });
        reset();

        try {
            const response = await chatService.sendMessage(cleanMessage);
            const botMessage = {
                role: 'assistant',
                content: response.data.answer,
                sources: response.data.sources,
                logId: response.data.log_id,
            };

            const stored = loadMessagesFromStorage(chatStorageKey);
            const storageUpdated = replacePendingMessageByRequestId(stored, requestId, botMessage);
            persistMessagesToStorage(chatStorageKey, storageUpdated);
            setMessages((prev) => replacePendingMessageByRequestId(prev, requestId, botMessage));
        } catch (error) {
            console.error(error);
            // Check if it's an authentication error
            const isAuthError = error.response?.status === 403 || error.response?.status === 401;
            const errorContent = isAuthError
                ? 'Ваша сессия истекла. Пожалуйста, войдите снова.'
                : 'Извините, произошла ошибка при обработке вашего запроса.';
            const errorMessage = { role: 'assistant', content: errorContent };
            const stored = loadMessagesFromStorage(chatStorageKey);
            const storageUpdated = replacePendingMessageByRequestId(stored, requestId, errorMessage);
            persistMessagesToStorage(chatStorageKey, storageUpdated);
            setMessages((prev) => replacePendingMessageByRequestId(prev, requestId, errorMessage));
        }
    };

    const onSubmit = async (data) => {
        await submitMessage(data.message);
    };

    const handleQuickQuestion = async (question) => {
        if (hasPendingMessage) return;
        await submitMessage(question);
    };

    const handleClearChat = () => {
        if (hasPendingMessage) return;
        setMessages([INITIAL_ASSISTANT_MESSAGE]);
        reset();
    };

    const handleFeedback = async (logId, rating, index) => {
        if (!logId) return;

        try {
            await chatService.sendFeedback(logId, rating);
            setMessages((prev) => {
                const next = [...prev];
                next[index] = { ...next[index], feedback: rating };
                return next;
            });
        } catch (error) {
            console.error('Failed to send feedback', error);
        }
    };

    const renderSources = (sources) => {
        if (!Array.isArray(sources) || sources.length === 0) return null;

        return (
            <details className="mt-3 rounded-lg border border-slate-200 bg-white/70 px-3 py-2 text-xs text-slate-500">
                <summary className="cursor-pointer list-none font-semibold uppercase tracking-[0.08em] text-[#1f3a60]">
                    Правовые источники и ссылки
                </summary>
                <div className="mt-2 space-y-1.5">
                    {sources.map((source, sourceIdx) => {
                        if (typeof source === 'string') {
                            return <div key={sourceIdx}>Source: {source}</div>;
                        }

                        const docName = source.doc_name || `Document #${source.doc_id ?? 'N/A'}`;
                        const page = source.page ? `, page ${source.page}` : '';
                        const quote = source.quote ? ` — ${source.quote}` : '';

                        return <div key={source.chunk_id || sourceIdx}>{docName}{page}{quote}</div>;
                    })}
                </div>
            </details>
        );
    };

    return (
        <div className="h-full w-full">
            <div className="flex h-full flex-col overflow-hidden bg-white lg:border-l lg:border-slate-200">
                <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
                    <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-500">
                        {formatTodayLabel()}
                    </div>
                    <Button variant="ghost" size="sm" onClick={handleClearChat} disabled={hasPendingMessage}>
                        Очистить чат
                    </Button>
                </div>

                <div className="scrollbar-soft flex-1 space-y-6 overflow-y-auto bg-[#f6f8fc] px-4 py-6 sm:px-8">
                    {messages.map((msg, idx) => (
                        <div
                            key={`${msg.role}-${idx}`}
                            className={cn(
                                'flex w-full items-start gap-3',
                                msg.role === 'user' ? 'justify-end' : 'justify-start',
                            )}
                        >
                            {msg.role === 'assistant' && (
                                <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#1f3a60] text-[#c5a059]">
                                    <Shield className="h-4 w-4" />
                                </div>
                            )}

                            <div
                                className={cn(
                                    'max-w-[85%] rounded-2xl px-4 py-3 text-[15px] leading-relaxed shadow-sm sm:max-w-[74%]',
                                    msg.role === 'user'
                                        ? 'rounded-tr-md bg-[#1f3a60] text-white'
                                        : 'rounded-tl-md border border-slate-200 bg-[#f2f4f7] text-slate-700',
                                    msg.pending === true && 'animate-pulse',
                                )}
                            >
                                {msg.role === 'assistant'
                                    ? <MarkdownContent content={msg.content} />
                                    : <div className="whitespace-pre-wrap">{msg.content}</div>}

                                {renderSources(msg.sources)}

                                {msg.role === 'assistant' && msg.logId && (
                                    <div className="mt-3 flex gap-2 border-t border-slate-200 pt-2">
                                        <button
                                            onClick={() => handleFeedback(msg.logId, 'up', idx)}
                                            className={cn(
                                                'rounded-md p-1.5 transition',
                                                msg.feedback === 'up' ? 'bg-green-100 text-green-600' : 'text-slate-400 hover:bg-slate-100',
                                            )}
                                            title="Good answer"
                                        >
                                            <ThumbsUp className="h-4 w-4" />
                                        </button>
                                        <button
                                            onClick={() => handleFeedback(msg.logId, 'down', idx)}
                                            className={cn(
                                                'rounded-md p-1.5 transition',
                                                msg.feedback === 'down' ? 'bg-red-100 text-red-600' : 'text-slate-400 hover:bg-slate-100',
                                            )}
                                            title="Bad answer"
                                        >
                                            <ThumbsDown className="h-4 w-4" />
                                        </button>
                                    </div>
                                )}
                            </div>

                            {msg.role === 'user' && (
                                <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500">
                                    <User className="h-4 w-4" />
                                </div>
                            )}
                        </div>
                    ))}

                    <div ref={messagesEndRef} />
                </div>

                <div className="border-t border-slate-200 bg-white px-4 py-4 sm:px-6">
                    <div className="mb-3 flex flex-wrap gap-2">
                        {QUICK_QUESTIONS.map((question) => (
                            <button
                                key={question}
                                type="button"
                                onClick={() => handleQuickQuestion(question)}
                                disabled={hasPendingMessage}
                                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-100 disabled:opacity-55"
                            >
                                {question}
                            </button>
                        ))}
                    </div>

                    <form onSubmit={handleSubmit(onSubmit)} className="relative">
                        <Paperclip className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                        <Input
                            className="h-12 rounded-xl border-slate-300 bg-slate-50 pl-10 pr-14 focus:bg-white"
                            placeholder="Введите ваш вопрос о налоговом законодательстве..."
                            autoComplete="off"
                            {...register('message')}
                        />
                        <Button
                            type="submit"
                            size="icon"
                            className="absolute right-2 top-1/2 h-9 w-9 -translate-y-1/2 rounded-lg"
                            disabled={hasPendingMessage}
                        >
                            <ArrowRight className="h-4 w-4" />
                        </Button>
                    </form>

                    <p className="mt-2 text-center text-[11px] font-medium text-slate-400">
                        SoliqAI может ошибаться. Проверяйте важную информацию в официальном Налоговом кодексе Таджикистана.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default ChatPage;
