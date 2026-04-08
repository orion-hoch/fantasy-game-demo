import { env } from '$env/dynamic/public';

const rawApiBaseUrl = env.PUBLIC_API_BASE_URL || '/api/v1';

export const apiBaseUrl = rawApiBaseUrl.replace(/\/+$/, '') || '/api/v1';
export const backendBaseUrl = env.PUBLIC_BACKEND_BASE_URL || apiBaseUrl.replace(/\/api\/v1$/, '');
