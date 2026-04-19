import { createRouter, createWebHistory } from 'vue-router';

// Async lazy loading
const LoginPage = () => import('../views/LoginPage.vue');
const AdminDashboard = () => import('../views/AdminDashboard.vue');

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'Login', component: LoginPage },
  { path: '/dashboard', name: 'Dashboard', component: AdminDashboard, meta: { requiresAuth: true } }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('basalt_token');
  if (to.meta.requiresAuth && !token) {
    next('/login');
  } else {
    next();
  }
});

export default router;
