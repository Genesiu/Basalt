import axios from 'axios';
import router from '../router';

const request = axios.create({
  baseURL: 'http://127.0.0.1:8000/api/v1',
  timeout: 10000
});

// Request interceptor: inject token
request.interceptors.request.use(config => {
  const token = localStorage.getItem('basalt_token');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor
request.interceptors.response.use(
  response => response,
  error => {
    return Promise.reject(error);
  }
);

export default request;
