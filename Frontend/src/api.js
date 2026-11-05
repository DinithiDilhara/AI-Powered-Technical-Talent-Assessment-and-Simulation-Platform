const API_BASE_URL = (
  import.meta.env.VITE_API_URL || 'http://localhost:8000'
).replace(/\/+$/, '');

function getErrorMessage(payload, fallback) {
  const detail = payload?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => item?.msg).filter(Boolean);
    if (messages.length) return messages.join(' ');
  }
  return fallback;
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function apiRequest(path, { token, body, headers, ...options } = {}) {
  const requestHeaders = new Headers(headers);
  if (body !== undefined) requestHeaders.set('Content-Type', 'application/json');
  if (token) requestHeaders.set('Authorization', `Bearer ${token}`);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: requestHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: 'omit',
    });
  } catch {
    throw new Error('Unable to connect to TalentForge. Check that the backend is running.');
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // Keep the status-based message when the server returns no JSON body.
  }

  if (!response.ok) {
    const fallback = response.status >= 500
      ? 'The server could not complete your request. Please try again.'
      : 'The request could not be completed.';
    throw new ApiError(getErrorMessage(payload, fallback), response.status);
  }

  return payload;
}
