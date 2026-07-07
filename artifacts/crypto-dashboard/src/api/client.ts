import type { ApiEnvelope, BackendConnectionInfo } from './types';

// Local development uses Vite's /api proxy. Production should set
// VITE_API_BASE_URL to the Render backend URL ending in /api.
const DEFAULT_API_BASE_URL = '/api';

function resolveApiBaseUrl(rawValue: string | undefined): string {
  const value = rawValue?.trim() || DEFAULT_API_BASE_URL;
  const isAbsoluteHttpUrl = /^https?:\/\//i.test(value);
  const isRootRelativeUrl = value.startsWith('/');

  if (!isAbsoluteHttpUrl && !isRootRelativeUrl) {
    throw new Error(
      'VITE_API_BASE_URL must be an absolute http(s) URL or a root-relative path.',
    );
  }

  return value.replace(/\/+$/, '');
}

export const API_BASE_URL = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL,
);

export class ApiError extends Error {
  status: number;

  constructor(message: string, status = 500) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function buildUrl(path: string, query?: Record<string, string | number | boolean | undefined | null>) {
  // Support both absolute URLs (http://...) and relative base paths (/api).
  const base = API_BASE_URL.startsWith('/')
    ? `${window.location.origin}${API_BASE_URL}`
    : API_BASE_URL;
  const url = new URL(`${base}${path}`);

  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    }
  }

  return url;
}

async function parseError(response: Response): Promise<ApiError> {
  let message = 'Backend unavailable';

  try {
    const payload = await response.json();
    if (typeof payload?.detail === 'string') {
      message = payload.detail;
    } else if (typeof payload?.message === 'string') {
      message = payload.message;
    }
  } catch {
    if (response.status >= 500) {
      message = 'Backend unavailable';
    } else {
      message = 'Request failed';
    }
  }

  return new ApiError(message, response.status);
}

async function request<T>(
  method: 'GET' | 'POST',
  path: string,
  options?: {
    body?: unknown;
    query?: Record<string, string | number | boolean | undefined | null>;
    signal?: AbortSignal;
  },
): Promise<ApiEnvelope<T>> {
  const headers = new Headers();
  let body: string | undefined;

  if (options?.body !== undefined) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options?.query), {
      method,
      headers,
      body,
      signal: options?.signal,
    });
  } catch {
    throw new ApiError('Backend unavailable', 0);
  }

  if (!response.ok) {
    throw await parseError(response);
  }

  const payload = (await response.json()) as ApiEnvelope<T>;
  if (!payload || typeof payload !== 'object' || !('data' in payload)) {
    throw new ApiError('Invalid backend response', response.status);
  }

  return payload;
}

export function getRequest<T>(
  path: string,
  options?: {
    query?: Record<string, string | number | boolean | undefined | null>;
    signal?: AbortSignal;
  },
) {
  return request<T>('GET', path, options);
}

export function postRequest<T>(
  path: string,
  options?: {
    body?: unknown;
    query?: Record<string, string | number | boolean | undefined | null>;
    signal?: AbortSignal;
  },
) {
  return request<T>('POST', path, options);
}

export function getBackendConnectionInfo(): BackendConnectionInfo {
  const resolvedBase = API_BASE_URL.startsWith('/')
    ? `${window.location.origin}${API_BASE_URL}`
    : API_BASE_URL;
  const url = new URL(resolvedBase);
  return {
    baseUrl: API_BASE_URL,
    host: url.hostname,
    port: url.port || (url.protocol === 'https:' ? '443' : '80'),
  };
}
