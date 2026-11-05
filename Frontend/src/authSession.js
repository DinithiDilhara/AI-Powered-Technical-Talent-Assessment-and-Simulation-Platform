const TOKEN_KEY = 'tf_access_token';
const USER_KEY = 'tf_auth_user';

export function readAuthSession(storage = globalThis.sessionStorage) {
  try {
    const token = storage?.getItem(TOKEN_KEY);
    const user = JSON.parse(storage?.getItem(USER_KEY) || 'null');
    return token && user && Number.isInteger(user.id) ? { token, user } : null;
  } catch {
    return null;
  }
}

export function writeAuthSession(session, storage = globalThis.sessionStorage) {
  try {
    if (session?.token && session?.user) {
      storage?.setItem(TOKEN_KEY, session.token);
      storage?.setItem(USER_KEY, JSON.stringify(session.user));
    } else {
      storage?.removeItem(TOKEN_KEY);
      storage?.removeItem(USER_KEY);
    }
  } catch {
    // Keep the active session in memory if browser storage is unavailable.
  }
}
