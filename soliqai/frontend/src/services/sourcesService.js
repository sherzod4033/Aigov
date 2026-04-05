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
  getPreviewBlob: (id) => api.get(`/sources/${id}/preview`, { responseType: 'blob' }),
  getChunkContext: (docId, chunkId, neighbors = 2) =>
    api.get(`/sources/${docId}/chunk/${chunkId}/context?neighbors=${neighbors}`),
};


export const documentsService = sourcesService;
