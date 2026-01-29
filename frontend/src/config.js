/**
 * Frontend Configuration
 * 
 * Centralized configuration loaded from environment variables.
 * Uses Vite's import.meta.env for build-time variable injection.
 */

/**
 * API Base URL
 * - Production: Empty string (uses relative paths for same-origin requests)
 * - Development: VITE_API_URL env var or localhost fallback
 */
export const API_URL = import.meta.env.PROD 
    ? '' 
    : (import.meta.env.VITE_API_URL || 'http://localhost:8000');

/**
 * Environment mode
 */
export const IS_PRODUCTION = import.meta.env.PROD;
export const IS_DEVELOPMENT = import.meta.env.DEV;

/**
 * App metadata
 */
export const APP_NAME = 'Predictive Maintenance';
export const APP_VERSION = '1.0.0';
