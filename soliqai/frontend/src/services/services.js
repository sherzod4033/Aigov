import api from './api';

export const chatService = {
    sendMessage: (question) => api.post('/chat/', { question }),
    sendFeedback: (logId, rating) => api.post(`/logs/${logId}/rating`, { rating }),
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
    exportCsv: ({ startDate, endDate } = {}) => {
        const params = new URLSearchParams();
        if (startDate) params.set('start_date', startDate);
        if (endDate) params.set('end_date', endDate);
        const queryString = params.toString();
        return api.get(`/logs/export${queryString ? `?${queryString}` : ''}`, {
            responseType: 'blob',
        });
    },
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
