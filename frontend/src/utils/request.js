import axios from 'axios';
import router from '../router';

const request = axios.create({
  // Modified: [L-04 安全修复] 使用相对路径，由 Vite proxy 或生产环境反向代理处理
  baseURL: '/api/v1',
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
    // Modified: 401 时自动跳转登录页（会话过期/Token 无效）
    if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
      localStorage.removeItem('basalt_token');
      router.push('/login');
    }
    return Promise.reject(error);
  }
);

export default request;
