import api from './api';

export const chatService = {
    sendMessage: (question) => api.post('/chat/', { question }),
    sendFeedback: (logId, rating) => api.post(`/logs/${logId}/rating`, { rating }),
};

export const faqService = {
    getAll: ({ skip = 0, limit = 100, q = '', category = '' } = {}) => {
        const params = new URLSearchParams();
        params.set('skip', skip);
        params.set('limit', limit);
        if (q.trim()) params.set('q', q.trim());
        if (category.trim()) params.set('category', category.trim());
        return api.get(`/faq/?${params.toString()}`);
    },
    getCategories: () => api.get('/faq/categories'),
    create: (data) => api.post('/faq/', data),
    update: (id, data) => api.put(`/faq/${id}`, data),
    delete: (id) => api.delete(`/faq/${id}`),
};

export const logsService = {
    getAll: ({ skip = 0, limit = 100, startDate, endDate } = {}) => {
        const params = new URLSearchParams();
        params.set('skip', skip);
        params.set('limit', limit);
        if (startDate) params.set('start_date', startDate);
        if (endDate) params.set('end_date', endDate);
        return api.get(`/logs/?${params.toString()}`);
    },
    getAnalytics: () => api.get('/analytics/'),
    addToFaq: (logId, payload = {}) => api.post(`/logs/${logId}/to-faq`, payload),
};

export const documentsService = {
    getAll: () => api.get('/documents/'),
    upload: (formData) => api.post('/documents/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    }),
    delete: (id) => api.delete(`/documents/${id}`),
};

export const settingsService = {
    get: () => api.get('/settings/'),
    update: (payload) => api.put('/settings/', payload),
    getUsers: () => api.get('/settings/users'),
    updateUserRole: (userId, role) => api.put(`/settings/users/${userId}/role`, { role }),
};
