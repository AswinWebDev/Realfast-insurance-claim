import axios from 'axios'

const api = axios.create({ baseURL: 'http://localhost:8000/api' })

export const getMembers = () => api.get('/members/').then(r => r.data)
export const getMember = id => api.get(`/members/${id}`).then(r => r.data)
export const getPolicies = () => api.get('/policies/').then(r => r.data)

export const submitClaim = payload => api.post('/claims/', payload).then(r => r.data)
export const getClaims = memberId => api.get('/claims/', { params: { member_id: memberId } }).then(r => r.data)
export const getClaim = id => api.get(`/claims/${id}`).then(r => r.data)
export const updateClaimStatus = (id, status, notes) =>
  api.patch(`/claims/${id}/status`, { status, notes }).then(r => r.data)

export const resolveReview = (claimId, lineItemId, outcome, notes) =>
  api.patch(`/claims/${claimId}/line-items/${lineItemId}/review`, { outcome, notes }).then(r => r.data)

export const fileDispute = (claimId, lineItemId, reason) =>
  api.post(`/claims/${claimId}/line-items/${lineItemId}/disputes`, { reason }).then(r => r.data)
export const resolveDispute = (claimId, lineItemId, disputeId, outcome, resolution_notes) =>
  api.patch(`/claims/${claimId}/line-items/${lineItemId}/disputes/${disputeId}`, { outcome, resolution_notes }).then(r => r.data)
