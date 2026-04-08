import { env } from '$env/dynamic/public';

export const apiBaseUrl = env.PUBLIC_API_BASE_URL || '/api/v1';
export const backendBaseUrl = env.PUBLIC_BACKEND_BASE_URL || apiBaseUrl.replace(/\/api\/v1$/, '');
