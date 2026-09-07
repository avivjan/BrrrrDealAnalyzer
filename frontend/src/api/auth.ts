import { apiClient } from './index';

/**
 * Passkey authentication (SECURITY_PLAN.md §3.2). The API sets HttpOnly
 * cookies; nothing here touches a token. `options` is the JSON that
 * `@simplewebauthn/browser` consumes verbatim.
 */

export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
  reps_user: string | null;
  role: string;
}

export interface SessionStatus {
  status: 'ok' | 'pending_approval';
  user: AuthUser;
  device_id: string;
  device_status: string;
  auth_mode: 'off' | 'shadow' | 'enforce';
  device_policy: 'off' | 'log' | 'enforce';
}

export interface AuthConfig {
  auth_mode: 'off' | 'shadow' | 'enforce';
  device_policy: 'off' | 'log' | 'enforce';
  rp_id: string;
}

export interface OAuthTxn {
  txn: string;
  client_name: string;
  redirect_uri: string | null;
  scopes: string[];
}

export interface DeviceInfo {
  id: string;
  user_id: string;
  user_display_name: string;
  kind: 'browser' | 'mcp' | string;
  label: string;
  platform: string | null;
  status: 'pending' | 'trusted' | 'revoked' | string;
  first_seen_at: string;
  last_seen_at: string;
  last_ip: string | null;
  approved_at: string | null;
  is_current: boolean;
}

export interface SessionInfo {
  id: string;
  device_id: string;
  device_label: string;
  kind: string;
  created_at: string;
  last_seen_at: string;
  ip: string | null;
  is_current: boolean;
}

export interface CredentialInfo {
  id: string;
  label: string;
  created_at: string;
  last_used_at: string | null;
  backup_state: boolean;
  transports: string | null;
}

export interface CeremonyOptions {
  challenge_id: string;
  options: string;
  username?: string | null;
}

export const authApi = {
  async config(): Promise<AuthConfig> {
    return (await apiClient.get<AuthConfig>('/auth/config')).data;
  },
  async me(): Promise<SessionStatus> {
    return (await apiClient.get<SessionStatus>('/auth/me')).data;
  },
  async refresh(): Promise<SessionStatus> {
    return (await apiClient.post<SessionStatus>('/auth/refresh')).data;
  },
  async logout(): Promise<void> {
    await apiClient.delete('/auth/session');
  },
  async registerOptions(token: string): Promise<CeremonyOptions> {
    return (await apiClient.post<CeremonyOptions>('/auth/register/options', { token })).data;
  },
  async registerVerify(token: string, challengeId: string, credential: unknown, label?: string): Promise<SessionStatus> {
    return (
      await apiClient.post<SessionStatus>('/auth/register/verify', {
        token,
        challenge_id: challengeId,
        credential,
        label: label || undefined,
      })
    ).data;
  },
  async loginOptions(): Promise<CeremonyOptions> {
    return (await apiClient.post<CeremonyOptions>('/auth/login/options')).data;
  },
  async loginVerify(challengeId: string, credential: unknown): Promise<SessionStatus> {
    return (await apiClient.post<SessionStatus>('/auth/login/verify', { challenge_id: challengeId, credential })).data;
  },
  async reauthOptions(): Promise<CeremonyOptions> {
    return (await apiClient.post<CeremonyOptions>('/auth/reauth/options')).data;
  },
  async reauthVerify(challengeId: string, credential: unknown): Promise<SessionStatus> {
    return (await apiClient.post<SessionStatus>('/auth/reauth/verify', { challenge_id: challengeId, credential })).data;
  },
  async enrollmentToken(): Promise<{ token: string; expires_in_minutes: number }> {
    return (await apiClient.post<{ token: string; expires_in_minutes: number }>('/auth/enrollment-tokens')).data;
  },
  /** MCP connector consent (MCP_AUTH_MODE=oauth): what is asking, then approve. */
  async oauthTxn(txn: string): Promise<OAuthTxn> {
    return (await apiClient.get<OAuthTxn>(`/auth/oauth/txn/${encodeURIComponent(txn)}`)).data;
  },
  async oauthApprove(txn: string): Promise<{ redirect_uri: string }> {
    return (await apiClient.post<{ redirect_uri: string }>('/auth/oauth/approve', { txn })).data;
  },
  /** Trusted devices, sessions and passkeys (SECURITY_PLAN.md §3.4). */
  async devices(): Promise<DeviceInfo[]> {
    return (await apiClient.get<DeviceInfo[]>('/devices')).data;
  },
  async renameDevice(id: string, label: string): Promise<DeviceInfo> {
    return (await apiClient.patch<DeviceInfo>(`/devices/${encodeURIComponent(id)}`, { label })).data;
  },
  async approveDevice(id: string): Promise<DeviceInfo> {
    return (await apiClient.post<DeviceInfo>(`/devices/${encodeURIComponent(id)}/approve`)).data;
  },
  async revokeDevice(id: string): Promise<DeviceInfo> {
    return (await apiClient.post<DeviceInfo>(`/devices/${encodeURIComponent(id)}/revoke`)).data;
  },
  async sessions(): Promise<SessionInfo[]> {
    return (await apiClient.get<SessionInfo[]>('/sessions')).data;
  },
  async endSession(id: string): Promise<void> {
    await apiClient.delete(`/sessions/${encodeURIComponent(id)}`);
  },
  async endOtherSessions(): Promise<void> {
    await apiClient.post('/sessions/end-others');
  },
  async credentials(): Promise<CredentialInfo[]> {
    return (await apiClient.get<CredentialInfo[]>('/credentials')).data;
  },
  async deleteCredential(id: string): Promise<void> {
    await apiClient.delete(`/credentials/${encodeURIComponent(id)}`);
  },
};
