/**
 * RSA 前端加密工具
 * 使用后端提供的 RSA 公钥加密登录凭据，防止明文传输
 */
import JSEncrypt from 'jsencrypt';
import request from './request';

let _publicKey = null;

/**
 * 从后端获取 RSA 公钥（带缓存）
 */
export async function fetchPublicKey() {
  if (_publicKey) return _publicKey;
  const res = await request.get('/auth/public-key');
  _publicKey = res.data.public_key;
  return _publicKey;
}

/**
 * 用 RSA 公钥加密 JSON 对象
 * @param {Object} payload - 要加密的数据，如 { username, password }
 * @returns {string} Base64 编码的密文
 */
export async function rsaEncrypt(payload) {
  const publicKey = await fetchPublicKey();
  const encrypt = new JSEncrypt();
  encrypt.setPublicKey(publicKey);
  const encrypted = encrypt.encrypt(JSON.stringify(payload));
  if (!encrypted) {
    throw new Error('RSA 加密失败，请刷新页面重试。');
  }
  return encrypted;
}

/**
 * 清除缓存的公钥（用于密钥轮换场景）
 */
export function clearPublicKeyCache() {
  _publicKey = null;
}
