import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const ingestEvent = (payload) => api.post('/events/', payload)
export const getAllStudents = () => api.get('/students/')
export const getStudentState = (uid) => api.get(`/students/${uid}/state/`)
export const getStudentTimeline = (uid) => api.get(`/students/${uid}/timeline/`)
export const getStudentAudit = (uid) => api.get(`/students/${uid}/audit/`)
export const getStudentRisk = (uid) => api.get(`/students/${uid}/risk/`)
export const getRawEvents = (uid) => api.get(`/events/raw/${uid ? `?userId=${uid}` : ''}`)
export const getAllAudit = () => api.get('/audit/')
export const replayEvents = (userId) => api.post('/replay/', userId ? { userId } : {})
