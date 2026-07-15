import { ref } from 'vue'

const TOKEN_KEY = 'xhs_access_token'
const USERNAME_KEY = 'xhs_username'

export const authToken = ref(localStorage.getItem(TOKEN_KEY) || '')
export const currentUsername = ref(localStorage.getItem(USERNAME_KEY) || '')

export function isAuthenticated() {
  return Boolean(authToken.value || localStorage.getItem(TOKEN_KEY))
}

export function setAuth(token: string, username: string) {
  authToken.value = token
  currentUsername.value = username
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USERNAME_KEY, username)
}

export function clearAuth() {
  authToken.value = ''
  currentUsername.value = ''
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USERNAME_KEY)
}

export function getToken() {
  return authToken.value || localStorage.getItem(TOKEN_KEY) || ''
}
