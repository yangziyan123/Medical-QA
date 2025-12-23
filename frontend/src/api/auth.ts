import { apiClient } from './client'

export type UserResponse = { id: string; username: string; role: string }
export type RegisterResponse = { user: UserResponse }
export type TokenResponse = { access_token: string; token_type: string }

export async function apiRegister(username: string, password: string): Promise<RegisterResponse> {
  const { data } = await apiClient.post('/api/auth/register', { username, password })
  return data
}

export async function apiLogin(username: string, password: string): Promise<TokenResponse> {
  const { data } = await apiClient.post('/api/auth/login', { username, password })
  return data
}

export async function apiMe(): Promise<UserResponse> {
  const { data } = await apiClient.get('/api/auth/me')
  return data
}

