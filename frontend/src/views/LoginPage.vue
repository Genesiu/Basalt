<template>
  <div class="login-layout">
    <!-- Left Visual Panel -->
    <div class="hero-panel">
      <div class="hero-content">
        <div class="brand">
          <div class="brand-icon"></div>
          <span class="brand-text">Basalt</span>
        </div>
        <h1 class="hero-title">业务连续性与安全管控平台</h1>
        <p class="hero-desc">本系统基于国家标准 GB/T 22239-2019《网络安全等级保护基本要求》构建，所有数据通讯及流转均已纳入加密边界防护与系统级审计规范。</p>
        <div class="certification-badge">
          <span class="dot-live"></span>
          等保三级安全基线已启用
        </div>
      </div>
      <div class="abstract-ring"></div>
      <div class="abstract-ring ring-inner"></div>
    </div>
    
    <!-- Right Form Panel -->
    <div class="form-panel">
      <div class="form-wrapper">

        <!-- 正常登录表单 -->
        <template v-if="!showChangePwd">
          <h2 class="form-title">身份鉴别</h2>
          <p class="form-subtitle">请使用授权账户登录系统。</p>
          
          <transition name="toast">
            <div v-if="errorMessage" class="luxury-toast">
              <svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
              </svg>
              <span>{{ errorMessage }}</span>
            </div>
          </transition>
          
          <form @submit.prevent="handleLogin" class="form-body">
            <div class="input-group">
              <label class="input-label">账号</label>
              <input type="text" v-model="username" placeholder="请输入用户名" class="luxury-input" required />
            </div>
            <div class="input-group">
              <label class="input-label">密码</label>
              <input type="password" v-model="password" placeholder="请输入密码" class="luxury-input" required />
            </div>
            <div class="input-group" v-if="totpRequired">
              <label class="input-label">动态验证码 (TOTP)</label>
              <input type="text" v-model="totpCode" placeholder="请输入 6 位动态口令" class="luxury-input" maxlength="6" inputmode="numeric" />
            </div>
            <button type="submit" class="luxury-btn mt-6" :disabled="loading">
              {{ loading ? '验证中...' : '登录' }}
            </button>
          </form>
        </template>

        <!-- 修改密码表单 -->
        <template v-else>
          <h2 class="form-title">修改密码</h2>
          <p class="form-subtitle">{{ changePwdReason }}</p>

          <transition name="toast">
            <div v-if="errorMessage" class="luxury-toast">
              <svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
              </svg>
              <span>{{ errorMessage }}</span>
            </div>
          </transition>

          <transition name="toast">
            <div v-if="successMessage" class="luxury-toast" style="background: rgba(16,185,129,0.15); border-color: rgba(16,185,129,0.4);">
              <span>{{ successMessage }}</span>
            </div>
          </transition>

          <form @submit.prevent="handleChangePassword" class="form-body">
            <div class="input-group">
              <label class="input-label">原密码</label>
              <input type="password" v-model="oldPassword" placeholder="请输入当前密码" class="luxury-input" required />
            </div>
            <div class="input-group">
              <label class="input-label">新密码</label>
              <input type="password" v-model="newPassword" placeholder="至少8位，含大小写+数字+特殊字符" class="luxury-input" required />
            </div>
            <div class="input-group">
              <label class="input-label">确认新密码</label>
              <input type="password" v-model="confirmPassword" placeholder="请再次输入新密码" class="luxury-input" required />
            </div>
            <button type="submit" class="luxury-btn mt-6" :disabled="loading">
              {{ loading ? '提交中...' : '确认修改' }}
            </button>
            <button type="button" class="secondary-btn mt-4" style="width:100%" @click="showChangePwd = false; errorMessage = ''">
              返回登录
            </button>
          </form>
        </template>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import request from '../utils/request';

const router = useRouter();
const username = ref('sysadmin');
const password = ref('');
const totpCode = ref('');
const totpRequired = ref(false);
const loading = ref(false);
const errorMessage = ref('');
const successMessage = ref('');

// 改密状态
const showChangePwd = ref(false);
const changePwdReason = ref('');
const oldPassword = ref('');
const newPassword = ref('');
const confirmPassword = ref('');  // Added: 二次确认
// 改密时需要一个临时 token，先用密码正确登录拿到（密码过期场景下需先登录一次拿 token）
const changePwdToken = ref('');

const handleLogin = async () => {
  if (!username.value || !password.value) return;
  loading.value = true;
  errorMessage.value = '';
  
  try {
    const params = new URLSearchParams();
    params.append('username', username.value);
    params.append('password', password.value);
    if (totpCode.value) {
      params.append('scope', totpCode.value);
    }
    
    const res = await request.post('/auth/login', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    
    localStorage.setItem('basalt_token', res.data.access_token);
    router.push('/dashboard');
    
  } catch (error) {
    if (error.response) {
      const detail = error.response.data.detail || '登录失败';
      const headers = error.response.headers;
      
      if (headers['x-totp-required'] === 'true') {
        totpRequired.value = true;
        errorMessage.value = detail;
      } else if (headers['x-password-expired'] === 'true') {
        // 密码过期，切换到改密表单
        showChangePwd.value = true;
        changePwdReason.value = detail;
        oldPassword.value = password.value;
        errorMessage.value = '';
      } else {
        errorMessage.value = detail;
      }
    } else {
      errorMessage.value = '无法连接服务器。';
    }
  } finally {
    loading.value = false;
  }
};

const handleChangePassword = async () => {
  if (!oldPassword.value || !newPassword.value || !confirmPassword.value) return;
  // Added: 前端二次确认校验
  if (newPassword.value !== confirmPassword.value) {
    errorMessage.value = '两次输入的新密码不一致，请重新输入。';
    return;
  }
  loading.value = true;
  errorMessage.value = '';
  successMessage.value = '';

  try {
    const res = await request.post('/auth/reset-expired-password', {
      username: username.value,
      old_password: oldPassword.value,
      new_password: newPassword.value
    });

    successMessage.value = res.data.message || '密码修改成功，请使用新密码登录。';
    password.value = '';
    setTimeout(() => {
      showChangePwd.value = false;
      successMessage.value = '';
    }, 2000);
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || '修改失败';
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  background-color: var(--bg-app);
  overflow: hidden;
}
.hero-panel {
  flex: 1.2;
  position: relative;
  background: var(--slate-900);
  background-image: linear-gradient(145deg, var(--slate-900) 40%, var(--slate-950) 100%);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  padding: 0 10%;
  overflow: hidden;
}
.hero-content { position: relative; z-index: 10; max-width: 480px; }
.brand { display: flex; align-items: center; margin-bottom: 48px; }
.brand-icon {
  width: 24px; height: 24px; border-radius: 4px;
  background: var(--slate-50); margin-right: 12px;
  box-shadow: inset 0 0 0 6px var(--slate-900);
  border: 1px solid var(--slate-400);
}
.brand-text { font-weight: 700; font-size: 16px; letter-spacing: 1px; color: var(--text-title); text-transform: uppercase; }
.hero-title { font-size: 38px; line-height: 1.2; margin-bottom: 24px; color: var(--slate-50); font-weight: 700; letter-spacing: -0.02em; }
.hero-desc { font-size: 16px; color: var(--slate-400); line-height: 1.6; margin-bottom: 48px; }
.certification-badge {
  display: inline-flex; align-items: center;
  background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2);
  color: var(--success-400); padding: 8px 16px; border-radius: 999px;
  font-size: 12px; font-weight: 600; letter-spacing: 0.5px;
}
.dot-live {
  width: 6px; height: 6px; background: var(--success-400); border-radius: 50%;
  margin-right: 8px; box-shadow: 0 0 8px var(--success-400); animation: pulse 2s infinite;
}
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
.abstract-ring {
  position: absolute; top: -20%; left: -10%; width: 800px; height: 800px;
  border-radius: 50%; border: 1px solid rgba(255,255,255,0.05); z-index: 1;
}
.ring-inner { top: 10%; left: 20%; width: 600px; height: 600px; border: 1px solid rgba(255,255,255,0.02); }
.form-panel { flex: 0.8; display: flex; align-items: center; justify-content: center; background: var(--bg-app); }
.form-wrapper { width: 100%; max-width: 380px; }
.form-title { font-size: 28px; margin-bottom: 8px; }
.form-subtitle { color: var(--slate-500); margin-bottom: 40px; font-size: 14px; }
.input-group { margin-bottom: 20px; }
.input-label { display: block; font-size: 12px; font-weight: 500; color: var(--slate-400); margin-bottom: 8px; letter-spacing: 0.5px; }
.mt-4 { margin-top: 16px; }
.mt-6 { margin-top: 32px; }
.luxury-toast {
  display: flex; align-items: center; background: var(--danger-900);
  border: 1px solid var(--danger-500); color: #fff; padding: 12px 16px;
  border-radius: 8px; margin-bottom: 24px; font-size: 13px;
}
.toast-icon { width: 18px; height: 18px; margin-right: 10px; flex-shrink: 0; }
.secondary-btn {
  background: var(--slate-800); border: 1px solid var(--slate-700);
  color: var(--slate-100); padding: 10px 16px; border-radius: 6px;
  font-size: 14px; cursor: pointer; transition: all 0.2s ease; text-align: center;
}
.secondary-btn:hover { background: var(--slate-700); }
</style>
