<template>
  <div class="admin-layout">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-icon"></div>
        <span class="brand-text">Basalt 管控平台</span>
      </div>
      <div class="nav-section">
        <div class="nav-title">用户与权限</div>
        <div class="nav-item" v-if="hasPerm('user:manage')" :class="{ active: tab === 'users' }" @click="tab = 'users'">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
          用户管理
        </div>
        <div class="nav-item" v-if="hasPerm('role:manage')" :class="{ active: tab === 'roles' }" @click="tab = 'roles'">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm14 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z"/></svg>
          角色与权限
        </div>
        <div class="nav-title" style="margin-top:16px">安全与审计</div>
        <div class="nav-item" v-if="hasPerm('policy:manage')" :class="{ active: tab === 'policy' }" @click="tab = 'policy'">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"/></svg>
          安全策略
        </div>
        <div class="nav-item" v-if="hasPerm('audit:view')" :class="{ active: tab === 'audit' }" @click="tab = 'audit'">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
          审计日志
        </div>
        <div class="nav-title" style="margin-top:16px">运维与合规</div>
        <div class="nav-item" v-if="hasPerm('policy:manage')" :class="{ active: tab === 'backup' }" @click="tab = 'backup'">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"/></svg>
          备份管理
        </div>
        <div class="nav-item" :class="{ active: tab === 'compliance' }" @click="tab = 'compliance'">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
          等保指引
        </div>
        <div class="nav-title" style="margin-top:16px">个人</div>
        <div class="nav-item" :class="{ active: tab === 'profile' }" @click="tab = 'profile'">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
          个人资料
        </div>
      </div>
      <div class="sidebar-footer">
        <div class="user-block">
          <div class="avatar">{{ (myProfile.username || '?')[0].toUpperCase() }}</div>
          <div class="user-meta">
            <div class="uname">{{ myProfile.username || '—' }}</div>
            <div class="urole">{{ myProfile.role_name || myProfile.role_code || '—' }}</div>
          </div>
        </div>
      </div>
    </aside>

    <main class="main-content">
      <header class="top-bar">
        <span class="page-title">{{ titles[tab] }}</span>
        <button class="logout-btn" @click="logout">退出登录</button>
      </header>

      <div class="canvas">

        <!-- ========== 审计日志 ========== -->
        <section v-if="tab === 'audit'" class="card">
          <div class="card-head between">
            <h3>操作审计记录</h3>
            <div style="display:flex;gap:8px">
              <button class="btn-s" @click="exportAuditCSV" v-if="hasPerm('audit:export')">📥 导出 CSV</button>
              <button class="btn-s" @click="loadAudit">刷新</button>
            </div>
          </div>
          <table class="tbl">
            <thead><tr><th>时间</th><th>操作人</th><th>动作</th><th>来源IP</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-if="auditLogs.length===0"><td colspan="6" class="empty">暂无审计记录。</td></tr>
              <tr v-for="l in auditLogs" :key="l.id">
                <td class="mono">{{ l.timestamp }}</td>
                <td class="bold">{{ l.user_id }}</td>
                <td>{{ l.action }}</td>
                <td class="mono">{{ l.ip_address }}</td>
                <td><span class="pill" :class="l.status==='SUCCESS'?'ok':'fail'">{{ l.status }}</span></td>
                <td><button class="link-btn" @click="showDetail(l)">详情</button></td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- ========== 安全策略 ========== -->
        <section v-if="tab === 'policy'" class="card">
          <div class="card-head"><h3>等保基线参数配置</h3></div>
          <p class="desc">依据 GB/T 22239-2019 第三级安全计算环境要求配置。</p>
          <div class="form-grid">
            <div class="field"><label>登录失败锁定次数</label><input type="number" v-model="cfg.LOGIN_MAX_FAILURES" min="1" max="99" class="ipt"></div>
            <div class="field"><label>锁定时长（分钟）</label><input type="number" v-model="cfg.LOGIN_LOCKOUT_MINUTES" min="1" max="1440" class="ipt"></div>
            <div class="field"><label>会话超时（分钟）</label><input type="number" v-model="cfg.SESSION_TIMEOUT_MINS" min="5" max="120" class="ipt"></div>
            <div class="field"><label>口令有效期（天）</label><input type="number" v-model="cfg.PWD_MAX_AGE_DAYS" min="30" max="365" class="ipt"></div>
          </div>
          <div class="field" style="margin-top:16px">
            <label class="chk-label"><input type="checkbox" v-model="cfg.PWD_COMPLEXITY_ENFORCE"> 强制口令复杂度（大小写+数字+特殊字符，≥8位）</label>
          </div>
          <div class="actions"><button class="btn-p" @click="saveCfg" :disabled="saving">{{ saving ? '保存中...' : '保存配置' }}</button></div>

          <div class="divider"></div>
          <div class="card-head between" style="padding:0"><h3>IP 访问控制白名单</h3></div>
          <p class="desc">未配置白名单时仅允许 localhost 访问受控接口。</p>
          <div class="form-row">
            <input v-model="newIP" placeholder="例: 192.168.1.0/24" class="ipt" style="flex:1">
            <input v-model="newIPDesc" placeholder="备注" class="ipt" style="flex:1">
            <button class="btn-p" @click="addIP" style="white-space:nowrap">添加</button>
          </div>
          <table class="tbl" style="margin-top:12px">
            <thead><tr><th>IP / 网段</th><th>备注</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-if="ipList.length===0"><td colspan="3" class="empty">空</td></tr>
              <tr v-for="w in ipList" :key="w.id">
                <td class="mono bold">{{ w.ip_network }}</td>
                <td>{{ w.description }}</td>
                <td><button class="del-btn" @click="delIP(w.id)">删除</button></td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- ========== 角色管理 ========== -->
        <section v-if="tab === 'roles'" class="card">
          <div class="card-head between">
            <h3>系统角色表</h3>
            <button class="btn-p" @click="openCreateRole">新建角色</button>
          </div>
          <table class="tbl">
            <thead><tr><th>ID</th><th>角色代码</th><th>角色名称</th><th>权限节点</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-if="rolesList.length===0"><td colspan="5" class="empty">无角色数据</td></tr>
              <tr v-for="r in rolesList" :key="r.id">
                <td class="mono">{{ r.id }}</td>
                <td class="bold mono">{{ r.code }}</td>
                <td>{{ r.name }}</td>
                <td>
                  <span class="role-tag" v-for="p in r.permissions" :key="p" style="margin-right:4px">{{ permMap[p] || p }}</span>
                </td>
                <td class="act-cell">
                  <button class="link-btn" @click="editRole(r)">编辑角色</button>
                </td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- ========== 用户管理 ========== -->
        <section v-if="tab === 'users'" class="card">
          <div class="card-head between">
            <h3>系统用户管理</h3>
            <button class="btn-p" @click="showCreateUser = true">创建用户</button>
          </div>
          <table class="tbl">
            <thead><tr><th>ID</th><th>用户名</th><th>角色</th><th>状态</th><th>TOTP</th><th>密码更新</th><th>最后登录</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-if="userList.length===0"><td colspan="8" class="empty">无用户数据</td></tr>
              <tr v-for="u in userList" :key="u.id">
                <td class="mono">{{ u.id }}</td>
                <td class="bold">{{ u.username }}</td>
                <td><span class="role-tag">{{ u.role_name }}</span></td>
                <td><span class="pill" :class="u.is_active?'ok':'fail'">{{ u.is_active ? '活跃' : '停用' }}</span></td>
                <td>{{ u.totp_enabled ? '已绑定' : '未绑定' }}</td>
                <td class="mono">{{ u.password_updated_at || '—' }}</td>
                <td class="mono">{{ u.last_login_at || '—' }}</td>
                <td class="act-cell">
                  <button class="link-btn" @click="editUser(u)">编辑</button>
                  <button class="del-btn" v-if="u.is_active" @click="disableUser(u.id)">停用</button>
                  <button class="link-btn" v-else @click="enableUser(u.id)">启用</button>
                </td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- ========== 个人中心 ========== -->
        <section v-if="tab === 'profile'" class="card">
          <!-- Added: 管理员 TOTP 强制绑定提示（等保 8.1.4.1h） -->
          <div v-if="myProfile.totp_force_required" class="alert-banner">
            ⚠️ 您的管理员角色要求绑定双因子认证（TOTP），请立即前往下方完成绑定，否则后续登录将受限。
          </div>
          <div class="card-head"><h3>个人资料</h3></div>
          <div class="profile-list">
            <div class="pf-item"><span class="pf-label">用户名</span><span class="pf-val">{{ myProfile.username }}</span></div>
            <div class="pf-item"><span class="pf-label">角色</span><span class="pf-val">{{ myProfile.role_name || myProfile.role_code || '—' }}</span></div>
            <div class="pf-item"><span class="pf-label">账号状态</span><span class="pf-val">{{ myProfile.is_active ? '活跃' : '停用' }}</span></div>
            <div class="pf-item"><span class="pf-label">双因子认证</span><span class="pf-val" :class="myProfile.totp_enabled ? 'val-ok' : 'val-warn'">{{ myProfile.totp_enabled ? '✓ 已绑定' : '✗ 未绑定' }}</span></div>
            <div class="pf-item"><span class="pf-label">密码更新时间</span><span class="pf-val">{{ myProfile.password_updated_at || '未记录' }}</span></div>
            <div class="pf-item"><span class="pf-label">最后登录</span><span class="pf-val">{{ myProfile.last_login_at || '从未登录' }}</span></div>
          </div>

          <div class="divider"></div>
          <h4 class="sub-title">修改密码</h4>
          <div class="form-grid narrow">
            <div class="field"><label>原密码</label><input type="password" v-model="pwdOld" class="ipt" placeholder="当前密码"></div>
            <div class="field"><label>新密码</label><input type="password" v-model="pwdNew" class="ipt" placeholder="至少8位,含大小写+数字+特殊字符"></div>
            <div class="field"><label>确认新密码</label><input type="password" v-model="pwdConfirm" class="ipt" placeholder="再次输入新密码"></div>
          </div>
          <div class="actions">
            <button class="btn-p" @click="changePwd" :disabled="saving">修改密码</button>
            <span v-if="pwdMsg" class="inline-msg" :class="pwdMsgType">{{ pwdMsg }}</span>
          </div>

          <div class="divider"></div>
          <h4 class="sub-title">双因子认证 (TOTP)</h4>
          <template v-if="myProfile.totp_enabled">
            <p class="desc">TOTP 已绑定，登录时需要输入动态验证码。如需重置请联系安全管理员。</p>
          </template>
          <template v-else>
            <p class="desc">尚未绑定 TOTP。绑定后每次登录需使用 Google Authenticator 等应用输入动态验证码。</p>
            <button class="btn-p" @click="setupTotp">开始绑定</button>
          </template>
        </section>

        <!-- ========== 备份管理 ========== -->
        <section v-if="tab === 'backup'" class="card">
          <div class="card-head between">
            <h3>数据库备份调度管理</h3>
            <button class="btn-p" @click="triggerBackup" :disabled="backupRunning">{{ backupRunning ? '备份中...' : '立即备份' }}</button>
          </div>
          <p class="desc">内置 APScheduler 调度器，替代系统 crontab。所有配置变更均记入审计日志。</p>

          <div class="form-grid">
            <div class="field">
              <label>调度状态</label>
              <div class="switch-row">
                <label class="switch">
                  <input type="checkbox" v-model="backupCfg.enabled">
                  <span class="slider"></span>
                </label>
                <span class="switch-label">{{ backupCfg.enabled ? '已开启' : '已关闭' }}</span>
              </div>
            </div>
            <div class="field">
              <label>执行时间（24小时制）</label>
              <div style="display:flex;gap:8px;align-items:center">
                <input type="number" v-model.number="backupCfg.cron_hour" min="0" max="23" class="ipt" style="width:70px"> 时
                <input type="number" v-model.number="backupCfg.cron_minute" min="0" max="59" class="ipt" style="width:70px"> 分
              </div>
            </div>
            <div class="field">
              <label>备份目录</label>
              <input v-model="backupCfg.backup_dir" class="ipt" placeholder="/opt/basalt/backups">
            </div>
            <div class="field">
              <label>保留天数</label>
              <input type="number" v-model.number="backupCfg.keep_days" min="1" max="365" class="ipt">
            </div>
          </div>
          <div class="actions">
            <button class="btn-p" @click="saveBackupCfg" :disabled="saving">{{ saving ? '保存中...' : '保存配置' }}</button>
            <span v-if="backupMsg" class="inline-msg" :class="backupMsgType">{{ backupMsg }}</span>
          </div>

          <div class="divider"></div>
          <h4 class="sub-title">最近备份记录</h4>
          <table class="tbl">
            <thead><tr><th>文件名</th><th>大小</th><th>时间</th></tr></thead>
            <tbody>
              <tr v-if="backupList.length===0"><td colspan="3" class="empty">暂无备份记录</td></tr>
              <tr v-for="b in backupList" :key="b.filename">
                <td class="mono">{{ b.filename }}</td>
                <td>{{ b.size_kb }} KB</td>
                <td class="mono">{{ b.time }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="lastBackupResult" class="backup-result">
            <span class="pill ok">✓ 最近备份</span>
            <span class="mono" style="margin-left:8px">{{ lastBackupResult.file }} ({{ lastBackupResult.size_kb }} KB)</span>
          </div>
        </section>

        <!-- ========== 等保指引 ========== -->
        <section v-if="tab === 'compliance'" class="card">
          <div class="card-head"><h3>GB/T 22239-2019 等保三级测评指引</h3></div>
          <p class="desc">以下是测评师现场核查所需的验证路径，可直接点击或告知测评师访问对应地址。</p>

          <div class="compliance-grid">
            <div class="cpl-group">
              <h4 class="cpl-title">一、身份鉴别（8.1.4.1）</h4>
              <div class="cpl-item" @click="tab='policy'">
                <span class="cpl-code">a-d</span>
                <span class="cpl-text">密码复杂度 / 有效期 / 登录锁定</span>
                <span class="cpl-loc">→ 菜单「安全策略」</span>
              </div>
              <div class="cpl-item" @click="tab='users'">
                <span class="cpl-code">e</span>
                <span class="cpl-text">首次登录强制改密</span>
                <span class="cpl-loc">→ 菜单「用户管理」创建用户后验证</span>
              </div>
              <div class="cpl-item" @click="tab='profile'">
                <span class="cpl-code">h</span>
                <span class="cpl-text">多因素认证（TOTP）</span>
                <span class="cpl-loc">→ 菜单「个人资料」TOTP 区域</span>
              </div>
            </div>

            <div class="cpl-group">
              <h4 class="cpl-title">二、访问控制（8.1.4.2）</h4>
              <div class="cpl-item" @click="tab='roles'">
                <span class="cpl-code">a-b</span>
                <span class="cpl-text">动态 RBAC / 三员分立</span>
                <span class="cpl-loc">→ 菜单「角色与权限」</span>
              </div>
              <div class="cpl-item" @click="tab='roles'">
                <span class="cpl-code">g-h</span>
                <span class="cpl-text">安全标记（MAC）</span>
                <span class="cpl-loc">→ 菜单「角色与权限」max_clearance 字段</span>
              </div>
            </div>

            <div class="cpl-group">
              <h4 class="cpl-title">三、安全审计（8.1.4.3）</h4>
              <div class="cpl-item" @click="tab='audit'">
                <span class="cpl-code">a-b</span>
                <span class="cpl-text">审计日志查看 / 详情</span>
                <span class="cpl-loc">→ 菜单「审计日志」</span>
              </div>
              <div class="cpl-item">
                <span class="cpl-code">c</span>
                <span class="cpl-text">审计防删改（SQLite 触发器）</span>
                <span class="cpl-loc">→ 命令行: DELETE FROM audit_logs → 触发器拦截</span>
              </div>
              <div class="cpl-item" @click="tab='audit'">
                <span class="cpl-code">f</span>
                <span class="cpl-text">审计 CSV 导出</span>
                <span class="cpl-loc">→ 菜单「审计日志」→ 导出 CSV 按钮</span>
              </div>
            </div>

            <div class="cpl-group">
              <h4 class="cpl-title">四、入侵防范（8.1.4.4）</h4>
              <div class="cpl-item" @click="tab='policy'">
                <span class="cpl-code">c</span>
                <span class="cpl-text">IP 白名单</span>
                <span class="cpl-loc">→ 菜单「安全策略」→ IP 访问控制白名单</span>
              </div>
            </div>

            <div class="cpl-group">
              <h4 class="cpl-title">五、数据安全（8.1.4.7-10）</h4>
              <div class="cpl-item" @click="tab='backup'">
                <span class="cpl-code">8.1.4.9</span>
                <span class="cpl-text">数据备份与恢复</span>
                <span class="cpl-loc">→ 菜单「备份管理」</span>
              </div>
              <div class="cpl-item">
                <span class="cpl-code">8.1.4.7</span>
                <span class="cpl-text">数据加密（AES-256-GCM）</span>
                <span class="cpl-loc">→ 代码: core/crypto.py → AESCipher</span>
              </div>
            </div>

            <div class="cpl-group">
              <h4 class="cpl-title">六、API 验证快速入口</h4>
              <div class="cpl-item">
                <span class="cpl-code">📋</span>
                <span class="cpl-text">完整 API 交互式文档</span>
                <span class="cpl-loc"><a :href="apiBaseUrl + '/docs'" target="_blank" class="api-link">打开 Swagger UI (/docs)</a></span>
              </div>
              <div class="cpl-item">
                <span class="cpl-code">💚</span>
                <span class="cpl-text">系统健康检测</span>
                <span class="cpl-loc"><a :href="apiBaseUrl + '/health'" target="_blank" class="api-link">GET /health</a></span>
              </div>
            </div>
          </div>
        </section>

      </div>
    </main>

    <!-- ===== 审计详情弹窗 ===== -->
    <div class="modal-overlay" v-if="detailLog" @click.self="detailLog=null">
      <div class="modal">
        <div class="modal-head between">
          <h3>审计日志详情 #{{ detailLog.id }}</h3>
          <button class="close-btn" @click="detailLog=null">&times;</button>
        </div>
        <div class="modal-body">
          <div class="detail-row"><span>时间</span><span>{{ detailLog.timestamp }}</span></div>
          <div class="detail-row"><span>操作人</span><span>{{ detailLog.user_id }}</span></div>
          <div class="detail-row"><span>动作</span><span>{{ detailLog.action }}</span></div>
          <div class="detail-row"><span>来源 IP</span><span>{{ detailLog.ip_address }}</span></div>
          <div class="detail-row"><span>资源</span><span style="word-break:break-all">{{ detailLog.resource }}</span></div>
          <div class="detail-row"><span>状态</span><span><span class="pill" :class="detailLog.status==='SUCCESS'?'ok':'fail'">{{ detailLog.status }}</span></span></div>
          <div class="detail-full"><span>详情数据</span><pre>{{ formatDetails(detailLog.details) }}</pre></div>
        </div>
      </div>
    </div>

    <!-- ===== 创建/编辑角色弹窗 ===== -->
    <div class="modal-overlay" v-if="editingRole" @click.self="editingRole=null">
      <div class="modal">
        <div class="modal-head between">
          <h3>{{ editingRole.id ? '编辑角色' : '创建新角色' }}</h3>
          <button class="close-btn" @click="editingRole=null">&times;</button>
        </div>
        <div class="modal-body">
          <div class="field"><label>角色代号 (英文)</label>
            <input v-model="editingRole.code" class="ipt" placeholder="例如 hr_admin" :disabled="['sysadmin','auditadmin'].includes(editingRole.code)">
          </div>
          <div class="field"><label>角色名称 (展示用)</label>
            <input v-model="editingRole.name" class="ipt" placeholder="例如 人事管理员">
          </div>
          <div class="field">
            <label>赋予权限节点</label>
            <div style="background:var(--slate-900); border:1px solid var(--slate-700); padding:10px; border-radius:5px; display:flex; flex-direction:column; gap:8px;">
              <label class="chk-label" v-for="(v, k) in permMap" :key="k">
                <input type="checkbox" :value="k" v-model="editingRole.permissions"> {{ v }} ({{ k }})
              </label>
            </div>
          </div>
          <div class="actions"><button class="btn-p" @click="saveRole">保存角色树</button></div>
        </div>
      </div>
    </div>

    <!-- ===== 创建用户弹窗 ===== -->
    <div class="modal-overlay" v-if="showCreateUser" @click.self="showCreateUser=false">
      <div class="modal">
        <div class="modal-head between">
          <h3>创建用户</h3>
          <button class="close-btn" @click="showCreateUser=false">&times;</button>
        </div>
        <div class="modal-body">
          <div class="field"><label>用户名</label><input v-model="newUser.username" class="ipt" placeholder="唯一标识"></div>
          <div class="field"><label>密码</label><input type="password" v-model="newUser.password" class="ipt" placeholder="至少8位,含大小写+数字+特殊字符"></div>
          <div class="field"><label>分配角色</label>
            <select v-model="newUser.role_code" class="ipt">
              <option v-for="r in rolesList" :value="r.code" :key="r.code">{{ r.name }}</option>
            </select>
          </div>
          <div class="actions"><button class="btn-p" @click="createUser">确认创建</button></div>
        </div>
      </div>
    </div>

    <!-- ===== 编辑用户弹窗 ===== -->
    <div class="modal-overlay" v-if="editingUser" @click.self="editingUser=null">
      <div class="modal">
        <div class="modal-head between">
          <h3>编辑用户: {{ editingUser.username }}</h3>
          <button class="close-btn" @click="editingUser=null">&times;</button>
        </div>
        <div class="modal-body">
          <div class="field"><label>分配角色</label>
            <select v-model="editingUser.role_code" class="ipt">
              <option v-for="r in rolesList" :value="r.code" :key="r.code">{{ r.name }}</option>
            </select>
          </div>
          <div class="actions"><button class="btn-p" @click="saveUser">保存</button></div>
        </div>
      </div>
    </div>

    <!-- ===== TOTP 绑定弹窗 ===== -->
    <div class="modal-overlay" v-if="showTotpModal" @click.self="cancelTotp">
      <div class="modal" style="width:480px">
        <div class="modal-head between">
          <h3>绑定双因子认证 (TOTP)</h3>
          <button class="close-btn" @click="cancelTotp">&times;</button>
        </div>
        <div class="modal-body" style="text-align:center">
          <p class="desc" style="text-align:left;margin-bottom:16px">请使用 Google Authenticator、Microsoft Authenticator 或其他 TOTP 应用扫描下方二维码：</p>
          <div class="qr-container">
            <img v-if="totpQrDataUrl" :src="totpQrDataUrl" alt="TOTP QR Code" class="qr-img" />
            <p v-else style="color:var(--slate-500)">正在生成二维码...</p>
          </div>
          <div class="divider"></div>
          <p class="desc" style="text-align:left">如无法扫码，请手动输入以下密钥：</p>
          <code class="totp-secret">{{ totpSecret }}</code>
          <div class="divider"></div>
          <p style="font-size:13px;color:var(--slate-300);text-align:left">扫码成功后，请输入 Authenticator 上显示的 6 位验证码以完成绑定：</p>
          <div style="margin:16px 0">
            <input v-model="totpVerifyCode" class="ipt" style="width:200px;text-align:center;font-size:24px;letter-spacing:8px;font-family:monospace" maxlength="6" placeholder="000000" autocomplete="off">
          </div>
          <span v-if="totpMsg" class="inline-msg" :class="totpMsgType">{{ totpMsg }}</span>
          <div class="actions" style="justify-content:center;margin-top:16px">
            <button class="btn-p" @click="confirmTotpBind" :disabled="totpVerifying">
              {{ totpVerifying ? '验证中...' : '验证并绑定' }}
            </button>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import QRCode from 'qrcode';
import request from '../utils/request';

const router = useRouter();
const saving = ref(false);

const permMap = {
  'audit:view': '调阅操作审计日志',
  'audit:export': '导出审计日志报告',
  'policy:manage': '修改基线策略及白名单',
  'user:manage': '增删改系统用户成员',
  'role:manage': '定义并变更角色架构树'
};

const myProfile = ref({ permissions: [] });
// 当配置取向加载完毕，默认将 tab 置为 profile，如果本身权限里有对应再置为 default
const tab = ref('profile');

const titles = { audit: '安全审计中心', policy: '安全策略与白名单', roles: '动态角色体系架构', users: '系统用户管理', backup: '备份管理', compliance: '等保三级测评指引', profile: '个人安全中心' };

const hasPerm = (p) => myProfile.value.permissions?.includes(p);

// API base URL for compliance guide links
const apiBaseUrl = 'http://localhost:8000';

// Data
const auditLogs = ref([]);
const detailLog = ref(null);
const cfg = ref({ LOGIN_MAX_FAILURES: 5, LOGIN_LOCKOUT_MINUTES: 30, SESSION_TIMEOUT_MINS: 15, PWD_MAX_AGE_DAYS: 90, PWD_COMPLEXITY_ENFORCE: true });
const ipList = ref([]);
const newIP = ref('');
const newIPDesc = ref('');

const rolesList = ref([]);
const editingRole = ref(null); 

const userList = ref([]);
const showCreateUser = ref(false);
const newUser = ref({ username: '', password: '', role_code: 'ordinary' });
const editingUser = ref(null);

const pwdOld = ref('');
const pwdNew = ref('');
const pwdConfirm = ref('');
const pwdMsg = ref('');
const pwdMsgType = ref('ok');
const totpSecret = ref('');
const totpUri = ref('');
const totpQrDataUrl = ref('');
const showTotpModal = ref(false);
const totpVerifyCode = ref('');
const totpVerifying = ref(false);
const totpMsg = ref('');
const totpMsgType = ref('ok');

// Backup data
const backupCfg = ref({ enabled: true, cron_hour: 2, cron_minute: 0, backup_dir: '', keep_days: 30 });
const backupList = ref([]);
const backupRunning = ref(false);
const lastBackupResult = ref(null);
const backupMsg = ref('');
const backupMsgType = ref('ok');

const formatDetails = (d) => {
  if (!d) return '（无）';
  try { return JSON.stringify(JSON.parse(d), null, 2); } catch { return d; }
};

// Init
onMounted(async () => {
  await loadProfile();
  // 根据权限决定跳转的 tab
  if (hasPerm('audit:view')) tab.value = 'audit';
  else if (hasPerm('policy:manage')) tab.value = 'policy';
  else if (hasPerm('user:manage')) tab.value = 'users';
  
  if (hasPerm('role:manage')) loadRoles();

  // Added: 等保 8.1.4.1f — 会话超时心跳（60秒轮询）
  // 连续 2 次 401 才判定超时，避免偶发网络问题干扰用户操作
  let heartbeatFailCount = 0;
  const heartbeatInterval = setInterval(async () => {
    try {
      await request.get('/users/me');
      heartbeatFailCount = 0; // 成功则重置计数
    } catch (e) {
      if (e.response?.status === 401) {
        heartbeatFailCount++;
        if (heartbeatFailCount >= 2) {
          clearInterval(heartbeatInterval);
          localStorage.removeItem('basalt_token');
          router.push('/login');
        }
      }
    }
  }, 60000);
});

watch(tab, (v) => {
  if (v === 'audit' && hasPerm('audit:view')) loadAudit();
  if (v === 'policy' && hasPerm('policy:manage')) { loadConfig(); loadIPList(); }
  if (v === 'roles' && hasPerm('role:manage')) loadRoles();
  if (v === 'users' && hasPerm('user:manage')) { loadUsers(); loadRoles(); }
  if (v === 'backup' && hasPerm('policy:manage')) loadBackupStatus();
  if (v === 'profile') loadProfile();
});

// ---- API calls ----
const loadProfile = async () => { 
  try { 
    myProfile.value = (await request.get('/users/me')).data; 
  } catch(e) { 
    console.error(e); 
    if(e.response?.status === 401) { router.push('/login'); }
  } 
};

// 角色 API
const loadRoles = async () => {
    try { rolesList.value = (await request.get('/roles/')).data; } catch(e) { console.error(e); }
};
const openCreateRole = () => { editingRole.value = { code: '', name: '', permissions: [] }; };
const editRole = (r) => { editingRole.value = JSON.parse(JSON.stringify(r)); };
const saveRole = async () => {
  try {
    if (editingRole.value.id) {
        await request.put(`/roles/${editingRole.value.id}`, editingRole.value);
    } else {
        await request.post('/roles/', editingRole.value);
    }
    editingRole.value = null;
    loadRoles();
  } catch(e) { alert(e.response?.data?.detail || '保存角色失败'); }
};

// 审计 API
const loadAudit = async () => { try { auditLogs.value = (await request.get('/audit/')).data; } catch(e) { console.error(e); } };
const showDetail = (log) => { detailLog.value = log; };

// Added: 等保 8.1.5d — 审计日志 CSV 导出
const exportAuditCSV = async () => {
  try {
    const res = await request.get('/audit/export/csv', { responseType: 'blob' });
    const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit_export_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  } catch(e) { alert(e.response?.data?.detail || '导出失败'); }
};

// 配置与白名单 API
const loadConfig = async () => {
  try {
    const d = (await request.get('/config/')).data;
    cfg.value = {
      LOGIN_MAX_FAILURES: parseInt(d.LOGIN_MAX_FAILURES) || 5,
      LOGIN_LOCKOUT_MINUTES: parseInt(d.LOGIN_LOCKOUT_MINUTES) || 30,
      SESSION_TIMEOUT_MINS: parseInt(d.SESSION_TIMEOUT_MINS) || 15,
      PWD_MAX_AGE_DAYS: parseInt(d.PWD_MAX_AGE_DAYS) || 90,
      PWD_COMPLEXITY_ENFORCE: d.PWD_COMPLEXITY_ENFORCE === 'true'
    };
  } catch(e) { console.error(e); }
};
const saveCfg = async () => {
  saving.value = true;
  try {
    await request.put('/config/', {
      LOGIN_MAX_FAILURES: cfg.value.LOGIN_MAX_FAILURES.toString(),
      LOGIN_LOCKOUT_MINUTES: cfg.value.LOGIN_LOCKOUT_MINUTES.toString(),
      SESSION_TIMEOUT_MINS: cfg.value.SESSION_TIMEOUT_MINS.toString(),
      PWD_MAX_AGE_DAYS: cfg.value.PWD_MAX_AGE_DAYS.toString(),
      PWD_COMPLEXITY_ENFORCE: cfg.value.PWD_COMPLEXITY_ENFORCE ? 'true' : 'false'
    });
    alert('配置已保存。');
  } catch(e) { alert(e.response?.data?.detail || '保存失败'); }
  finally { saving.value = false; }
};

const loadIPList = async () => { try { ipList.value = (await request.get('/config/whitelist')).data; } catch(e) { console.error(e); } };
const addIP = async () => {
  if (!newIP.value) return;
  try { await request.post('/config/whitelist', { ip_network: newIP.value, description: newIPDesc.value }); newIP.value = ''; newIPDesc.value = ''; loadIPList(); }
  catch(e) { alert(e.response?.data?.detail || '添加失败'); }
};
const delIP = async (id) => { if (!confirm('确认删除？')) return; try { await request.delete(`/config/whitelist/${id}`); loadIPList(); } catch(e) { alert('删除失败'); } };

// 用户 API
const loadUsers = async () => { try { userList.value = (await request.get('/users/')).data; } catch(e) { console.error(e); } };
const createUser = async () => {
  try {
    await request.post('/users/', newUser.value);
    showCreateUser.value = false;
    newUser.value = { username: '', password: '', role_code: 'ordinary' };
    loadUsers();
    alert('用户创建成功。');
  } catch(e) { alert(e.response?.data?.detail || '创建失败'); }
};
const editUser = (u) => { editingUser.value = { id: u.id, username: u.username, role_code: u.role_code }; };
const saveUser = async () => {
  try {
    await request.put(`/users/${editingUser.value.id}`, { role_code: editingUser.value.role_code });
    editingUser.value = null;
    loadUsers();
  } catch(e) { alert(e.response?.data?.detail || '更新失败'); }
};
const disableUser = async (id) => { if (!confirm('确认停用？')) return; try { await request.delete(`/users/${id}`); loadUsers(); } catch(e) { alert(e.response?.data?.detail || '操作失败'); } };
const enableUser = async (id) => { try { await request.put(`/users/${id}`, { is_active: true }); loadUsers(); } catch(e) { alert(e.response?.data?.detail || '操作失败'); } };

const changePwd = async () => {
  pwdMsg.value = '';
  if (!pwdOld.value || !pwdNew.value || !pwdConfirm.value) {
    pwdMsg.value = '请填写全部密码字段'; pwdMsgType.value = 'fail'; return;
  }
  if (pwdNew.value !== pwdConfirm.value) {
    pwdMsg.value = '两次输入的新密码不一致'; pwdMsgType.value = 'fail'; return;
  }
  saving.value = true;
  try {
    const res = await request.put('/users/me', { old_password: pwdOld.value, new_password: pwdNew.value });
    pwdMsg.value = '✓ ' + res.data.message; pwdMsgType.value = 'ok';
    pwdOld.value = ''; pwdNew.value = ''; pwdConfirm.value = '';
    setTimeout(() => {
      localStorage.removeItem('basalt_token');
      router.push('/login');
    }, 1500);
  } catch(e) {
    pwdMsg.value = '✗ ' + (e.response?.data?.detail || '修改失败'); pwdMsgType.value = 'fail';
  }
  finally { saving.value = false; }
};

const setupTotp = async () => {
  try {
    const res = await request.post('/auth/totp/setup');
    totpSecret.value = res.data.secret;
    totpUri.value = res.data.provisioning_uri;
    totpQrDataUrl.value = await QRCode.toDataURL(res.data.provisioning_uri, {
      width: 240, margin: 2,
      color: { dark: '#e2e8f0', light: '#0f172a' }
    });
    showTotpModal.value = true;
  } catch(e) { alert(e.response?.data?.detail || '绑定失败'); }
};

const cancelTotp = async () => {
  showTotpModal.value = false;
  totpSecret.value = '';
  totpUri.value = '';
  totpQrDataUrl.value = '';
  totpVerifyCode.value = '';
  totpMsg.value = '';
  loadProfile();
};

const confirmTotpBind = async () => {
  if (!totpVerifyCode.value || totpVerifyCode.value.length !== 6) {
    totpMsg.value = '请输入 6 位验证码'; totpMsgType.value = 'fail'; return;
  }
  totpVerifying.value = true;
  totpMsg.value = '';
  try {
    const res = await request.post('/auth/totp/verify', {
      // Modified: [C-02 前端适配] secret 不再提交，由服务端缓存提供
      code: totpVerifyCode.value
    });
    totpMsg.value = '✓ ' + res.data.message; totpMsgType.value = 'ok';
    setTimeout(() => {
      showTotpModal.value = false;
      totpSecret.value = '';
      totpUri.value = '';
      totpQrDataUrl.value = '';
      totpVerifyCode.value = '';
      totpMsg.value = '';
      loadProfile();
    }, 1500);
  } catch(e) {
    totpMsg.value = '✗ ' + (e.response?.data?.detail || '验证失败'); totpMsgType.value = 'fail';
  }
  finally { totpVerifying.value = false; }
};

// Backup API
const loadBackupStatus = async () => {
  try {
    const res = await request.get('/compliance/backup/status');
    backupCfg.value = {
      enabled: res.data.enabled,
      cron_hour: res.data.cron_hour,
      cron_minute: res.data.cron_minute,
      backup_dir: res.data.backup_dir,
      keep_days: res.data.keep_days
    };
    backupList.value = res.data.recent_backups || [];
  } catch(e) { console.error(e); }
};
const saveBackupCfg = async () => {
  saving.value = true;
  backupMsg.value = '';
  try {
    const res = await request.put('/compliance/backup/config', backupCfg.value);
    backupMsg.value = res.data?.message || '✓ 配置已保存';
    backupMsgType.value = 'ok';
    await loadBackupStatus();
  } catch(e) {
    backupMsg.value = '✗ ' + (e.response?.data?.detail || '保存失败');
    backupMsgType.value = 'fail';
  }
  finally { saving.value = false; }
};
const triggerBackup = async () => {
  backupRunning.value = true;
  backupMsg.value = '';
  try {
    const res = await request.post('/compliance/backup/trigger');
    lastBackupResult.value = res.data.result;
    backupMsg.value = '✓ 备份完成: ' + (res.data.result?.file || '成功');
    backupMsgType.value = 'ok';
    await loadBackupStatus();
  } catch(e) {
    backupMsg.value = '✗ ' + (e.response?.data?.detail || '备份失败');
    backupMsgType.value = 'fail';
  }
  finally { backupRunning.value = false; }
};

const logout = () => { localStorage.removeItem('basalt_token'); router.push('/login'); };
</script>

<style scoped>
.admin-layout { display:flex; height:100vh; width:100vw; background:var(--bg-app); overflow:hidden; }

/* Sidebar */
.sidebar { width:240px; background:var(--slate-900); border-right:1px solid var(--border-subtle); display:flex; flex-direction:column; }
.brand { display:flex; align-items:center; padding:20px; border-bottom:1px solid rgba(255,255,255,0.04); }
.brand-icon { width:18px; height:18px; border-radius:3px; background:var(--slate-50); margin-right:10px; border:1px solid var(--slate-400); box-shadow:inset 0 0 0 4px var(--slate-900); }
.brand-text { font-weight:600; font-size:14px; color:var(--text-title); letter-spacing:.5px; }
.nav-section { padding:20px 12px; flex:1; }
.nav-title { font-size:10px; text-transform:uppercase; color:var(--slate-500); letter-spacing:1.5px; margin-bottom:12px; padding-left:8px; }
.nav-item { display:flex; align-items:center; padding:9px 12px; border-radius:6px; color:var(--slate-400); font-size:13px; margin-bottom:2px; cursor:pointer; transition:all .15s; }
.nav-item:hover { background:rgba(255,255,255,.04); color:var(--slate-300); }
.nav-item.active { background:rgba(255,255,255,.08); color:var(--slate-50); font-weight:500; }
.nav-icon { width:16px; height:16px; margin-right:10px; flex-shrink:0; }
.sidebar-footer { padding:16px; border-top:1px solid var(--border-subtle); }
.user-block { display:flex; align-items:center; }
.avatar { width:30px; height:30px; border-radius:4px; background:var(--slate-800); color:var(--slate-300); display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:700; margin-right:10px; border:1px solid var(--slate-700); }
.user-meta .uname { font-size:12px; color:var(--text-title); font-weight:500; }
.user-meta .urole { font-size:10px; color:var(--slate-500); }

/* Main */
.main-content { flex:1; display:flex; flex-direction:column; overflow:hidden; }
.top-bar { height:56px; display:flex; align-items:center; justify-content:space-between; padding:0 28px; border-bottom:1px solid var(--border-subtle); }
.page-title { font-size:14px; font-weight:500; color:var(--text-title); }
.logout-btn { background:transparent; border:1px solid var(--slate-700); color:var(--slate-300); padding:5px 12px; border-radius:5px; font-size:12px; cursor:pointer; }
.logout-btn:hover { background:var(--slate-800); }
.canvas { padding:24px 28px; flex:1; overflow-y:auto; }

/* Card */
.card { background:var(--bg-surface); border:1px solid var(--border-subtle); border-radius:10px; padding:24px; margin-bottom:20px; }
.card-head { margin-bottom:16px; }
.card-head h3 { margin:0; font-size:15px; }
.between { display:flex; justify-content:space-between; align-items:center; }
.desc { color:var(--slate-500); font-size:12px; margin-bottom:16px; }
.sub-title { font-size:14px; margin-bottom:12px; color:var(--slate-200); }
.divider { border-top:1px solid var(--slate-800); margin:24px 0; }
.actions { margin-top:16px; display:flex; gap:8px; }

/* Table */
.tbl { width:100%; border-collapse:collapse; text-align:left; }
.tbl th { font-size:11px; font-weight:500; color:var(--slate-500); text-transform:uppercase; letter-spacing:.5px; padding:10px 12px; border-bottom:1px solid var(--slate-800); }
.tbl td { padding:10px 12px; font-size:13px; border-bottom:1px solid var(--slate-800); color:var(--slate-300); }
.tbl tr:hover { background:rgba(30,41,59,.3); }
.empty { text-align:center; padding:32px 0; color:var(--slate-500); }
.mono { font-family:monospace; font-size:12px; color:var(--slate-400); }
.bold { font-weight:500; color:var(--text-title); }
.act-cell { display:flex; gap:6px; }

/* Buttons */
.btn-p { background:var(--primary-500); border:none; color:#fff; padding:7px 16px; border-radius:5px; font-size:13px; cursor:pointer; }
.btn-p:hover { background:var(--primary-600, #0050d0); }
.btn-p:disabled { opacity:.5; cursor:not-allowed; }
.btn-s { background:var(--slate-800); border:1px solid var(--slate-700); color:var(--slate-100); padding:6px 14px; border-radius:5px; font-size:12px; cursor:pointer; }
.btn-s:hover { background:var(--slate-700); }
.link-btn { background:none; border:none; color:var(--primary-400); font-size:12px; cursor:pointer; padding:2px 4px; }
.link-btn:hover { text-decoration:underline; }
.del-btn { background:none; border:1px solid rgba(239,68,68,.3); color:#ef4444; padding:3px 8px; border-radius:4px; font-size:11px; cursor:pointer; }
.del-btn:hover { background:rgba(239,68,68,.1); }

/* Pills / Tags */
.pill { display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:500; }
.pill.ok { background:rgba(16,185,129,.12); color:#34d399; }
.pill.fail { background:rgba(239,68,68,.12); color:#ef4444; }
.role-tag { font-size:11px; padding:2px 8px; border-radius:4px; background:var(--slate-800); color:var(--slate-300); border:1px solid var(--slate-700); }

/* Forms */
.form-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.form-grid.narrow { max-width:500px; }
.form-row { display:flex; gap:8px; }
.field { margin-bottom:12px; }
.field label { display:block; font-size:11px; color:var(--slate-400); margin-bottom:5px; text-transform:uppercase; letter-spacing:.4px; }
.ipt { width:100%; background:var(--slate-900); border:1px solid var(--slate-700); color:var(--slate-100); padding:8px 10px; border-radius:5px; font-size:13px; }
.ipt:focus { outline:none; border-color:var(--primary-500); }
select.ipt { appearance:auto; }
.chk-label { display:flex; align-items:center; gap:8px; font-size:13px; color:var(--slate-300); cursor:pointer; }

/* Profile */
.profile-list { max-width:600px; }
.pf-item { display:flex; justify-content:space-between; padding:12px 0; border-bottom:1px solid var(--slate-800); }
.pf-label { font-size:13px; color:var(--slate-500); }
.pf-val { font-size:13px; color:var(--text-title); font-weight:500; }

/* Inline message toast */
.inline-msg { font-size:13px; padding:4px 12px; border-radius:4px; margin-left:12px; animation:fadeIn .3s; }
.inline-msg.ok { color:#34d399; background:rgba(16,185,129,.1); }
.inline-msg.fail { color:#ef4444; background:rgba(239,68,68,.1); }
@keyframes fadeIn { from { opacity:0; transform:translateY(-4px); } to { opacity:1; transform:translateY(0); } }
.val-ok { color:#34d399; }
.val-warn { color:#f59e0b; }

/* Added: 管理员 TOTP 强制绑定告警横幅 */
.alert-banner { background:rgba(245,158,11,.12); border:1px solid rgba(245,158,11,.3); color:#f59e0b; padding:12px 16px; border-radius:8px; font-size:13px; margin-bottom:16px; line-height:1.5; }

/* TOTP */
.totp-secret { display:block; background:var(--bg-app); padding:10px 14px; border-radius:4px; font-size:15px; color:var(--primary-400); margin-top:8px; user-select:all; letter-spacing:2px; font-family:monospace; text-align:center; border:1px solid var(--slate-700); }
.qr-container { padding:20px 0; }
.qr-img { width:240px; height:240px; border-radius:8px; border:2px solid var(--slate-700); }

/* Modal */
.modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,.6); display:flex; align-items:center; justify-content:center; z-index:100; }
.modal { background:var(--bg-surface); border:1px solid var(--border-subtle); border-radius:10px; width:560px; max-height:80vh; overflow-y:auto; }
.modal-head { padding:16px 20px; border-bottom:1px solid var(--slate-800); }
.modal-head h3 { margin:0; font-size:15px; }
.close-btn { background:none; border:none; color:var(--slate-400); font-size:24px; cursor:pointer; line-height:1; }
.modal-body { padding:20px; }
.modal-body .field { margin-bottom:16px; }
.detail-row { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--slate-800); font-size:13px; }
.detail-row span:first-child { color:var(--slate-500); min-width:80px; }
.detail-row span:last-child { color:var(--text-title); text-align:right; }
.detail-full { margin-top:12px; }
.detail-full span { display:block; font-size:12px; color:var(--slate-500); margin-bottom:6px; }
.detail-full pre { background:var(--slate-900); padding:12px; border-radius:6px; font-size:12px; color:var(--slate-300); white-space:pre-wrap; word-break:break-all; margin:0; max-height:200px; overflow-y:auto; }

/* Switch toggle */
.switch-row { display:flex; align-items:center; gap:10px; }
.switch { position:relative; display:inline-block; width:40px; height:22px; }
.switch input { opacity:0; width:0; height:0; }
.slider { position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background:var(--slate-700); border-radius:22px; transition:.3s; }
.slider::before { content:""; position:absolute; height:16px; width:16px; left:3px; bottom:3px; background:#fff; border-radius:50%; transition:.3s; }
.switch input:checked + .slider { background:var(--primary-500); }
.switch input:checked + .slider::before { transform:translateX(18px); }
.switch-label { font-size:13px; color:var(--slate-300); }

/* Backup result */
.backup-result { margin-top:12px; padding:10px 14px; background:rgba(16,185,129,.06); border:1px solid rgba(16,185,129,.15); border-radius:6px; display:flex; align-items:center; }

/* Compliance grid */
.compliance-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.cpl-group { background:var(--slate-900); border:1px solid var(--slate-800); border-radius:8px; padding:16px; }
.cpl-title { font-size:13px; color:var(--primary-400); margin:0 0 12px 0; padding-bottom:8px; border-bottom:1px solid var(--slate-800); }
.cpl-item { display:flex; align-items:center; gap:8px; padding:8px 10px; margin-bottom:4px; border-radius:5px; cursor:pointer; transition:all .15s; }
.cpl-item:hover { background:rgba(255,255,255,.04); }
.cpl-code { font-size:11px; font-weight:700; color:var(--slate-500); min-width:42px; font-family:monospace; }
.cpl-text { font-size:12px; color:var(--slate-300); flex:1; }
.cpl-loc { font-size:11px; color:var(--primary-400); white-space:nowrap; }
.api-link { color:var(--primary-400); text-decoration:none; }
.api-link:hover { text-decoration:underline; }
</style>
