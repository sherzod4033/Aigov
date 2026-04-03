import api from './api';


export const chatService = {
  sendMessage: (question, notebookId) => api.post('/chat/', { question, notebook_id: notebookId ?? null }),
  sendFeedback: (logId, rating) => api.post(`/logs/${logId}/rating`, { rating }),
};
