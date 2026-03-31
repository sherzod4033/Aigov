import api from './api';


export const sourcesService = {
  getAll: (notebookId) => api.get(`/sources/${notebookId ? `?notebook_id=${notebookId}` : ''}`),
  upload: (formData) => api.post('/sources/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  }),
  attachExisting: (payload) => api.post('/sources/attach', payload),
  delete: (id) => api.delete(`/sources/${id}`),
};


export const documentsService = sourcesService;
