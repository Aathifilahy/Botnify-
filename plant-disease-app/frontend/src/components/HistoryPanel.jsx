import { useState, useEffect } from 'react'
import { getSessionId } from '../session'   // <-- ADD THIS

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000'

export default function HistoryPanel() {
  const [scans, setScans] = useState([])
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(true)

  const fetchHistory = async () => {
    setLoading(true)
    const sessionId = getSessionId()           // <-- ADD THIS
    try {
      const res = await fetch(`${API_URL}/history?page=${page}&limit=10`, {
        headers: {
          'X-Session-Id': sessionId,          // <-- ADD HEADER
        }
      })
      const data = await res.json()
      setScans(data.scans)
      setTotalPages(data.pages)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const deleteScan = async (id) => {
    if (!confirm('Delete this scan?')) return
    const sessionId = getSessionId()           // <-- ADD THIS
    await fetch(`${API_URL}/history/${id}`, {
      method: 'DELETE',
      headers: {
        'X-Session-Id': sessionId,            // <-- ADD HEADER
      }
    })
    fetchHistory()
  }

  useEffect(() => {
    fetchHistory()
  }, [page])

  if (loading) return <div className="card">Loading history...</div>

  return (
    <div className="card">
      <h3>📋 Previous Scans</h3>
      {scans.length === 0 && <p>No scans yet. Upload a leaf image first.</p>}
      {scans.map(scan => (
        <div key={scan._id} style={{ borderBottom: '1px solid #3c7a5a', padding: '1rem 0', display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <img src={scan.image_url} alt="leaf" style={{ width: '70px', height: '70px', objectFit: 'cover', borderRadius: '12px' }} />
          <div style={{ flex: 1 }}>
            <strong>{scan.plant}</strong> — {scan.disease}<br />
            <small>Confidence: {(scan.confidence * 100).toFixed(0)}% &nbsp;|&nbsp; {new Date(scan.created_at).toLocaleString()}</small>
          </div>
          <button onClick={() => deleteScan(scan._id)} style={{ background: '#8b3c3c' }}>🗑️</button>
        </div>
      ))}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1rem' }}>
        <button disabled={page === 1} onClick={() => setPage(p => p-1)}>◀ Previous</button>
        <span>Page {page} of {totalPages}</span>
        <button disabled={page === totalPages} onClick={() => setPage(p => p+1)}>Next ▶</button>
      </div>
    </div>
  )
}