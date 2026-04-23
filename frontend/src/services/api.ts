import axios from "axios"

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"
const API_KEY = import.meta.env.VITE_API_KEY || "dev-secret-key-change-in-production"

// Axios instance — swap auth header here when upgrading from API key to JWT
export const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
  },
  timeout: 30000,
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    console.error("API error:", err.response?.data || err.message)
    return Promise.reject(err)
  }
)

export const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000"
