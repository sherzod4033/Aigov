import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const TOKEN_REFRESH_THRESHOLD_SECONDS = 5 * 60;

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

let refreshTokenPromise = null;

const decodeJwtPayload = (token) => {
    try {
        const payload = token.split('.')[1];
        if (!payload) return null;
        const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
        const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), '=');
        return JSON.parse(atob(padded));
    } catch {
        return null;
    }
};

const shouldRefreshToken = (token) => {
    const payload = decodeJwtPayload(token);
    if (!payload?.exp) return false;

    const secondsUntilExpiry = payload.exp - Math.floor(Date.now() / 1000);
    return secondsUntilExpiry > 0 && secondsUntilExpiry <= TOKEN_REFRESH_THRESHOLD_SECONDS;
};

const isAuthRequest = (url = '') => (
    url.includes('/auth/login') ||
    url.includes('/auth/register') ||
    url.includes('/auth/refresh')
);

const refreshAccessToken = async () => {
    const token = localStorage.getItem('token');
    if (!token) return null;

    if (!refreshTokenPromise) {
        refreshTokenPromise = axios.post(`${API_BASE_URL}/auth/refresh`, null, {
            headers: {
                Authorization: `Bearer ${token}`,
            },
        })
            .then((response) => {
                const nextToken = response.data?.access_token;
                if (nextToken) {
                    localStorage.setItem('token', nextToken);
                    return nextToken;
                }
                return token;
            })
            .catch(() => token)
            .finally(() => {
                refreshTokenPromise = null;
            });
    }

    return refreshTokenPromise;
};

export const getAuthorizedToken = async (url = '') => {
    let token = localStorage.getItem('token');
    if (token && !isAuthRequest(url) && shouldRefreshToken(token)) {
        token = await refreshAccessToken();
    }
    return token;
};

api.interceptors.request.use(
    async (config) => {
        const token = await getAuthorizedToken(config.url);
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Response interceptor to handle auth errors
api.interceptors.response.use(
    (response) => response,
    (error) => {
        return Promise.reject(error);
    }
);

export default api;
