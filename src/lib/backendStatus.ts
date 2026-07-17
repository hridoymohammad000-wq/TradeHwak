import { BackendConnectionStatus } from '../api/client';

export interface BackendStatusPresentation {
  label: string;
  detail: string;
  dotClass: string;
  textClass: string;
}

export function getBackendStatusPresentation(status: BackendConnectionStatus): BackendStatusPresentation {
  switch (status) {
    case 'connected':
      return {
        label: 'Connected',
        detail: 'Authenticated backend health check passed.',
        dotClass: 'bg-emerald-500',
        textClass: 'text-emerald-400',
      };
    case 'connecting':
      return {
        label: 'Connecting',
        detail: 'Checking backend availability and session.',
        dotClass: 'bg-amber-400 animate-pulse',
        textClass: 'text-amber-400',
      };
    case 'unauthorized':
      return {
        label: 'Unauthorized',
        detail: 'Access token or authenticated session is invalid.',
        dotClass: 'bg-rose-500',
        textClass: 'text-rose-400',
      };
    case 'disconnected':
      return {
        label: 'Disconnected',
        detail: 'The configured backend cannot be reached.',
        dotClass: 'bg-slate-500',
        textClass: 'text-slate-400',
      };
    default:
      return {
        label: 'Backend Error',
        detail: 'The backend responded with an invalid or failed result.',
        dotClass: 'bg-rose-500',
        textClass: 'text-rose-400',
      };
  }
}
