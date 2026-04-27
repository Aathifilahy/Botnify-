import { useState } from 'react'
import ResultPanel from './ResultPanel'
import { getSessionId } from '../session'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000'

export default function ImageUploader({ onScanComplete }) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (file) {
      setSelectedFile(file)
      setPreview(URL.createObjectURL(file))
      setResult(null)
      setError(null)
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) return
    setLoading(true)
    setError(null)
    const formData = new FormData()
    formData.append('image', selectedFile)

    try {
      const sessionId = getSessionId()   // ← ADD THIS
      const response = await fetch(`${API_URL}/predict`, {
        method: 'POST',
        headers: {
          'X-Session-Id': sessionId,    // ← ADD HEADER
        },
        body: formData
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Prediction failed')
      setResult(data)
      onScanComplete()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <input type="file" accept="image/*" onChange={handleFileChange} />
      {preview && <img src={preview} alt="Preview" style={{ maxWidth: '100%', marginTop: '1rem', borderRadius: '16px' }} />}
      <div style={{ marginTop: '1rem' }}>
        <button onClick={handleUpload} disabled={!selectedFile || loading}>
          {loading ? 'Analyzing...' : '🔍 Identify Disease'}
        </button>
      </div>
      {error && <p style={{ color: '#ffaa88' }}>❌ {error}</p>}
      {result && <ResultPanel result={result} />}
    </div>
  )
}