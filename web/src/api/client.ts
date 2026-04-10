import axios from 'axios';
import type { ApiError } from '@/types';

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const apiError: ApiError = error.response.data;
      throw new Error(apiError.detail || `API Error: ${error.response.status}`);
    }
    if (error.request) {
      throw new Error('Network error - no response received');
    }
    throw new Error(error.message || 'Unknown error');
  },
);

export default client;
