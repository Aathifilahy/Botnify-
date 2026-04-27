export default function ResultPanel({ result }) {
  if (!result) return null

  return (
    <div style={{ marginTop: '1.5rem' }}>
      <h3>🌱 Diagnosis Result</h3>
      {result.mock_mode && <p style={{ background: '#665500', padding: '0.5rem', borderRadius: '8px' }}>⚠️ Mock mode – model not loaded yet</p>}
      <p><strong>Plant:</strong> {result.plant}</p>
      <p><strong>Disease:</strong> {result.disease}</p>
      <div className="confidence-bar">
        <div className="confidence-fill" style={{ width: `${result.confidence * 100}%` }}></div>
      </div>
      <p>Confidence: {(result.confidence * 100).toFixed(1)}%</p>
      <p><strong>💊 Suggested Treatment:</strong> {result.treatment}</p>
      
      {result.top_predictions && (
        <details>
          <summary>🔍 Top 5 predictions</summary>
          <ul>
            {result.top_predictions.map((p, i) => (
              <li key={i}>{p.class}: {(p.confidence * 100).toFixed(1)}%</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}